#!/usr/bin/env python3
"""One-call parcel pull for Franklin County OH deals (ORA).
Usage: python3 franklin_parcel_pull.py --owner "EXAMPLE HOLDINGS LLC%"   |   --address "%SAMPLE DR%"   [--out FILE]
Vendored 2026-11-24 from a Dublin OH multifamily underwrite (ora-flood-zoning-dd v1.9). Needs curl on PATH.
Returns (stdout + JSON file): parcel count, class codes, auditor values, last sale(s), year built,
bed/bath mix, FEMA NFHL zone per parcel polygon, and City of Dublin zoning when the parcels fall in Dublin.
Exit codes: 0 = pulled; 1 = the query ran and matched no parcels; 2 = QUERY FAILED (server error or no response).
A failed sub-query (sales, flood, zoning, FIRM panel) never reads as "no data": it is reported as QUERY FAILED.
Endpoints (verified 2026-11-24):
  Parcels  https://gis.franklincountyohio.gov/hosting/rest/services/ParcelFeatures/Parcel_Features/MapServer/0
  Sales    https://gis.franklincountyohio.gov/hosting/rest/services/RealEstate/Sales_Information/MapServer/0  (stale after 2025-07)
  FEMA     https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28 (zones), /3 (FIRM panels)
  Dublin   https://services1.arcgis.com/NqY8dnPSEdMJhuRw/arcgis/rest/services/Zoning/FeatureServer/1
"""
import argparse, collections, datetime, json, os, re, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor

PARCEL = 'https://gis.franklincountyohio.gov/hosting/rest/services/ParcelFeatures/Parcel_Features/MapServer/0/query'
SALES = 'https://gis.franklincountyohio.gov/hosting/rest/services/RealEstate/Sales_Information/MapServer/0/query'
NFHL = 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer'
DUBLIN = 'https://services1.arcgis.com/NqY8dnPSEdMJhuRw/arcgis/rest/services/Zoning/FeatureServer/1/query'
FIELDS = ('PARCELID,SITEADDRESS,OWNERNME1,MAILNME1,PSTLADDRES,PSTLCITYSTZIP,SALEDATE,SALEPRICE,CLASSCD,CLASSDSCRP,'
          'RESYRBLT,BEDRMS,BATHS,HBATHS,LNDVALUEBASE,BLDVALUEBASE,TOTVALUEBASE,PR_TOTVALUEBASE,ACRES,CVTTXDSCRP,SCHLDSCRP')
PAGE = 1000          # parcel page size requested per call
SALES_CHUNK = 150    # parcel ids per sales IN (...) query
FAILED = 'QUERY FAILED'


def q(url, params, tries=5):
    """GET an ArcGIS REST query. Returns the parsed JSON, or None when every try failed
    (no response, unparseable body, or a server {"error": ...})."""
    args = ['curl', '-s', '-m', '60', '-G', url]
    for k, v in params.items():
        args += ['--data-urlencode', f'{k}={v}']
    for i in range(tries):
        try:
            r = json.loads(subprocess.run(args, capture_output=True, text=True).stdout)
            if isinstance(r, dict) and 'error' not in r:
                return r
        except Exception:
            pass
        if i < tries - 1:
            time.sleep(2 * (i + 1))
    return None


def sql_str(s):
    """Quote a value for an ArcGIS SQL string literal (O'BRIEN -> 'O''BRIEN')."""
    return "'" + s.replace("'", "''") + "'"


def d(ms):
    # epoch ms -> ISO date; timedelta form also handles pre-1970 (negative) values on Windows
    return str(datetime.date(1970, 1, 1) + datetime.timedelta(milliseconds=ms)) if ms else None


def fetch_parcels(where):
    """Page through the parcel layer. Returns (features, error_or_None)."""
    feats, offset = [], 0
    while True:
        r = q(PARCEL, dict(where=where, outFields=FIELDS, returnGeometry='true', outSR='4326', f='json',
                           resultOffset=str(offset), resultRecordCount=str(PAGE), orderByFields='PARCELID'))
        if r is None:
            return feats, f'{FAILED}: parcel layer (page at offset {offset})'
        page = r.get('features', [])
        feats += page
        if not r.get('exceededTransferLimit') or not page:
            return feats, None
        offset += len(page)


def default_out(a):
    key = re.sub(r'[^A-Za-z0-9]+', '_', a.owner or a.address).strip('_')[:40] or 'query'
    return f'parcel_pull_{key}_{datetime.date.today():%Y%m%d}.json'


def write_atomic(path, obj):
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, prefix='.parcel_pull_', suffix='.tmp')
    with os.fdopen(fd, 'w') as fh:
        json.dump(obj, fh, indent=1, default=str)
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--owner')
    g.add_argument('--address')
    ap.add_argument('--out', help='output JSON (default: parcel_pull_<query>_<YYYYMMDD>.json)')
    a = ap.parse_args()
    out_path = a.out or default_out(a)
    where = f"OWNERNME1 LIKE {sql_str(a.owner)}" if a.owner else f"SITEADDRESS LIKE {sql_str(a.address)}"

    feats, err = fetch_parcels(where)
    if err:
        print(err)
        sys.exit(2)
    if not feats:
        print('no parcels (query ran and matched nothing)')
        sys.exit(1)
    P = [f['attributes'] for f in feats]
    s = lambda k: sum((p.get(k) or 0) for p in P)
    out = dict(parcels=len(P), owners=collections.Counter(p.get('OWNERNME1') for p in P).most_common(3),
               mailing=list({(p.get('MAILNME1'), p.get('PSTLADDRES'), p.get('PSTLCITYSTZIP')) for p in P})[:3],
               classes=collections.Counter(f"{p.get('CLASSCD')} {p.get('CLASSDSCRP')}" for p in P).most_common(),
               land=s('LNDVALUEBASE'), bldg=s('BLDVALUEBASE'), total=s('TOTVALUEBASE'), prior_total=s('PR_TOTVALUEBASE'),
               acres=round(s('ACRES'), 3), year_built=collections.Counter(p.get('RESYRBLT') for p in P).most_common(),
               bed_bath=collections.Counter(f"{p.get('BEDRMS')}bd/{p.get('BATHS')}ba/{p.get('HBATHS') or 0}hb" for p in P).most_common(),
               last_sale=collections.Counter(f"{d(p.get('SALEDATE'))} USD {p.get('SALEPRICE') or 0:,.0f}" for p in P).most_common(5),
               tax_district=collections.Counter(p.get('CVTTXDSCRP') for p in P).most_common(2),
               school=collections.Counter(p.get('SCHLDSCRP') for p in P).most_common(2))

    # Sales history, chunked so every parcel is asked about.
    ids = [p['PARCELID'] for p in P if p.get('PARCELID')]
    hist, failed_chunks = set(), 0
    for i in range(0, len(ids), SALES_CHUNK):
        chunk = ','.join(sql_str(x) for x in ids[i:i + SALES_CHUNK])
        sh = q(SALES, dict(where=f'PARCELID IN ({chunk})', returnGeometry='false', f='json',
                           outFields='PARCELID,SALEDATE,SalePrice,SaleType,ParcelCount,GrantorName1,GranteeName1,ValidSale'))
        if sh is None:
            failed_chunks += 1
            continue
        for x in sh.get('features', []):
            t = x['attributes']
            hist.add((d(t.get('SALEDATE')), t.get('SalePrice'), t.get('GrantorName1'), t.get('GranteeName1'), t.get('ValidSale')))
    out['sales_history'] = sorted(hist, key=lambda r: (r[0] or '', str(r[1])))
    if failed_chunks:
        out['sales_history_note'] = f'[{FAILED}: sales layer] {failed_chunks} of {-(-len(ids) // SALES_CHUNK)} chunk(s) failed; history incomplete'
    elif not hist:
        out['sales_history_note'] = '[DATA-GAP: last sale] none in county sales layer (layer stale after 2025-07)'

    # Flood zone (and Dublin zoning) per parcel polygon.
    flood, zoning = collections.Counter(), collections.Counter()
    in_dublin = any('DUBLIN' in (p.get('CVTTXDSCRP') or '') for p in P)
    xs, ys = [], []
    with_geom = [f for f in feats if (f.get('geometry') or {}).get('rings')]
    no_geom = len(feats) - len(with_geom)
    for f in with_geom:
        for ring in f['geometry']['rings']:
            for x, y in ring:
                xs.append(x); ys.append(y)

    def one(f):
        geom = json.dumps({'rings': f['geometry']['rings'], 'spatialReference': {'wkid': 4326}})
        base = dict(geometry=geom, geometryType='esriGeometryPolygon', inSR='4326',
                    spatialRel='esriSpatialRelIntersects', returnGeometry='false', f='json')
        z = q(NFHL + '/28/query', dict(base, outFields='FLD_ZONE,ZONE_SUBTY'))
        fz = FAILED if z is None else (', '.join(sorted({f"{x['attributes']['FLD_ZONE']} {x['attributes']['ZONE_SUBTY'] or ''}".strip()
                                                       for x in z.get('features', [])})) or 'NO ZONE RETURNED')
        zn = None
        if in_dublin:
            zz = q(DUBLIN, dict(base, outFields='Description,Dev_Txt,Ord_Num,PUDClass'))
            zn = FAILED if zz is None else (' | '.join(sorted({f"{x['attributes']['Description']} · {x['attributes']['Dev_Txt']} · {x['attributes']['Ord_Num']} · {x['attributes']['PUDClass']}"
                                                              for x in zz.get('features', [])})) or 'OUTSIDE DUBLIN ZONING LAYER')
        return fz, zn

    with ThreadPoolExecutor(8) as ex:
        for fz, zn in ex.map(one, with_geom):
            flood[fz] += 1
            if zn is not None:
                zoning[zn] += 1
    if no_geom:
        flood['NO-GEOM (parcel has no polygon; flood not tested)'] += no_geom
    out['flood_by_parcel'] = flood.most_common()
    if xs:
        cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
        pan = q(NFHL + '/3/query', dict(geometry=f'{cx},{cy}', geometryType='esriGeometryPoint', inSR='4326',
                                        outFields='FIRM_PAN,EFF_DATE', returnGeometry='false', f='json'))
        out['firm_panel'] = FAILED if pan is None else [(x['attributes']['FIRM_PAN'], d(x['attributes']['EFF_DATE']))
                                                        for x in pan.get('features', [])]
        out['centroid'] = (round(cx, 5), round(cy, 5))
    else:
        out['firm_panel'] = 'NO-GEOM: no parcel polygon returned'
    out['zoning_by_parcel'] = zoning.most_common() if in_dublin else 'not in City of Dublin — use ora-flood-zoning-dd for the municipality'
    out['pulled'] = str(datetime.date.today())
    write_atomic(out_path, out)
    for k, v in out.items():
        print(f'{k}: {v}')
    print(f'written: {out_path}')


if __name__ == '__main__':
    main()
