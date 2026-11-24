#!/usr/bin/env python3
"""One-call parcel pull for Franklin County OH deals (ORA).
Usage: python3 franklin_parcel_pull.py --owner "EXAMPLE HOLDINGS LLC%"   |   --address "%SAMPLE DR%"
Vendored 2026-11-24 from a Dublin OH multifamily underwrite (ora-flood-zoning-dd v1.9). Needs curl on PATH.
Returns (stdout JSON + markdown summary): parcel count, class codes, auditor values, last sale(s), year built,
bed/bath mix, FEMA NFHL zone per parcel polygon, and City of Dublin zoning when the parcels fall in Dublin.
Endpoints (verified 2026-11-24):
  Parcels  https://gis.franklincountyohio.gov/hosting/rest/services/ParcelFeatures/Parcel_Features/MapServer/0
  Sales    https://gis.franklincountyohio.gov/hosting/rest/services/RealEstate/Sales_Information/MapServer/0  (stale after 2025-07)
  FEMA     https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28 (zones), /3 (FIRM panels)
  Dublin   https://services1.arcgis.com/NqY8dnPSEdMJhuRw/arcgis/rest/services/Zoning/FeatureServer/1
"""
import argparse, collections, datetime, json, subprocess, sys, time

PARCEL = 'https://gis.franklincountyohio.gov/hosting/rest/services/ParcelFeatures/Parcel_Features/MapServer/0/query'
SALES = 'https://gis.franklincountyohio.gov/hosting/rest/services/RealEstate/Sales_Information/MapServer/0/query'
NFHL = 'https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer'
DUBLIN = 'https://services1.arcgis.com/NqY8dnPSEdMJhuRw/arcgis/rest/services/Zoning/FeatureServer/1/query'
FIELDS = ('PARCELID,SITEADDRESS,OWNERNME1,MAILNME1,PSTLADDRES,PSTLCITYSTZIP,SALEDATE,SALEPRICE,CLASSCD,CLASSDSCRP,'
          'RESYRBLT,BEDRMS,BATHS,HBATHS,LNDVALUEBASE,BLDVALUEBASE,TOTVALUEBASE,PR_TOTVALUEBASE,ACRES,CVTTXDSCRP,SCHLDSCRP')

def q(url, params, tries=5):
    args = ['curl', '-s', '-m', '60', '-G', url]
    for k, v in params.items(): args += ['--data-urlencode', f'{k}={v}']
    for i in range(tries):
        try:
            r = json.loads(subprocess.run(args, capture_output=True, text=True).stdout)
            if 'features' in r or 'error' not in r: return r
        except Exception: pass
        time.sleep(2 * (i + 1))
    return {}

def d(ms):
    # epoch ms -> ISO date; timedelta form also handles pre-1970 (negative) values on Windows
    return str(datetime.date(1970, 1, 1) + datetime.timedelta(milliseconds=ms)) if ms else None

def main():
    ap = argparse.ArgumentParser(); g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--owner'); g.add_argument('--address'); ap.add_argument('--out', default='parcel_pull.json')
    a = ap.parse_args()
    where = f"OWNERNME1 LIKE '{a.owner}'" if a.owner else f"SITEADDRESS LIKE '{a.address}'"
    r = q(PARCEL, dict(where=where, outFields=FIELDS, returnGeometry='true', outSR='4326', f='json'))
    feats = r.get('features', [])
    if not feats: print('no parcels'); sys.exit(1)
    P = [f['attributes'] for f in feats]
    s = lambda k: sum((p[k] or 0) for p in P)
    out = dict(parcels=len(P), owners=collections.Counter(p['OWNERNME1'] for p in P).most_common(3),
               mailing=list({(p['MAILNME1'], p['PSTLADDRES'], p['PSTLCITYSTZIP']) for p in P})[:3],
               classes=collections.Counter(f"{p['CLASSCD']} {p['CLASSDSCRP']}" for p in P).most_common(),
               land=s('LNDVALUEBASE'), bldg=s('BLDVALUEBASE'), total=s('TOTVALUEBASE'), prior_total=s('PR_TOTVALUEBASE'),
               acres=round(s('ACRES'), 3), year_built=collections.Counter(p['RESYRBLT'] for p in P).most_common(),
               bed_bath=collections.Counter(f"{p['BEDRMS']}bd/{p['BATHS']}ba/{p['HBATHS'] or 0}hb" for p in P).most_common(),
               last_sale=collections.Counter(f"{d(p['SALEDATE'])} ${p['SALEPRICE'] or 0:,.0f}" for p in P).most_common(5),
               tax_district=collections.Counter(p['CVTTXDSCRP'] for p in P).most_common(2),
               school=collections.Counter(p['SCHLDSCRP'] for p in P).most_common(2))
    ids = "','".join(p['PARCELID'] for p in P[:200])
    sh = q(SALES, dict(where=f"PARCELID IN ('{ids}')", outFields='PARCELID,SALEDATE,SalePrice,SaleType,ParcelCount,GrantorName1,GranteeName1,ValidSale', returnGeometry='false', f='json'))
    out['sales_history'] = sorted({(d(x['attributes']['SALEDATE']), x['attributes']['SalePrice'], x['attributes']['GrantorName1'], x['attributes']['GranteeName1'], x['attributes']['ValidSale']) for x in sh.get('features', [])})
    if not out['sales_history']: out['sales_history_note'] = '[DATA-GAP: last sale] none in county sales layer (layer stale after 2025-07)'
    flood = collections.Counter(); zoning = collections.Counter(); in_dublin = any('DUBLIN' in (p['CVTTXDSCRP'] or '') for p in P)
    xs, ys = [], []
    for f in feats:
        for ring in f['geometry']['rings']:
            for x, y in ring: xs.append(x); ys.append(y)
    def one(f):
        geom = json.dumps({'rings': f['geometry']['rings'], 'spatialReference': {'wkid': 4326}})
        base = dict(geometry=geom, geometryType='esriGeometryPolygon', inSR='4326', spatialRel='esriSpatialRelIntersects', returnGeometry='false', f='json')
        z = q(NFHL + '/28/query', dict(base, outFields='FLD_ZONE,ZONE_SUBTY'))
        fz = ', '.join(sorted({f"{x['attributes']['FLD_ZONE']} {x['attributes']['ZONE_SUBTY'] or ''}".strip() for x in z.get('features', [])})) or 'ERR'
        zn = None
        if in_dublin:
            zz = q(DUBLIN, dict(base, outFields='Description,Dev_Txt,Ord_Num,PUDClass'))
            zn = ' | '.join(sorted({f"{x['attributes']['Description']} · {x['attributes']['Dev_Txt']} · {x['attributes']['Ord_Num']} · {x['attributes']['PUDClass']}" for x in zz.get('features', [])})) or 'ERR'
        return fz, zn
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(8) as ex:
        for fz, zn in ex.map(one, feats):
            flood[fz] += 1
            if zn is not None: zoning[zn] += 1
    cx, cy = sum(xs) / len(xs), sum(ys) / len(ys)
    pan = q(NFHL + '/3/query', dict(geometry=f'{cx},{cy}', geometryType='esriGeometryPoint', inSR='4326', outFields='FIRM_PAN,EFF_DATE', returnGeometry='false', f='json'))
    out['flood_by_parcel'] = flood.most_common(); out['firm_panel'] = [(x['attributes']['FIRM_PAN'], d(x['attributes']['EFF_DATE'])) for x in pan.get('features', [])]
    out['zoning_by_parcel'] = zoning.most_common() if in_dublin else 'not in City of Dublin — use ora-flood-zoning-dd for the municipality'
    out['centroid'] = (round(cx, 5), round(cy, 5)); out['pulled'] = str(datetime.date.today())
    json.dump(out, open(a.out, 'w'), indent=1, default=str)
    for k, v in out.items(): print(f'{k}: {v}')

if __name__ == '__main__':
    main()
