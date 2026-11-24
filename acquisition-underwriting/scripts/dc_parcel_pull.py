#!/usr/bin/env python3
"""dc_parcel_pull.py — standard DC intake step (ORA acquisition-underwriting, Stage -1 Rules 1/8/10).
One call per parcel returns: owner, last sale, current + proposed assessment (land/improvement), the
10-year real-property tax history with penalties/interest/fees, a late-payment flag, CAMA year built /
GBA, FEMA flood zone at the parcel centroid, and the implied next bill.

Sources (no key, public ArcGIS REST; verified 2026-11-24):
  DCGIS Property_and_Land_WebMercator MapServer/40  (ITS public extract: assessments, sale, tax history)
  DCGIS Property_and_Land_WebMercator FeatureServer/23 (CAMA commercial) / 25 (CAMA residential) / 24 (condo)
  FEMA NFHL MapServer/28 (flood hazard zones)
NOT in these layers: BID tax, public-space fees, special assessments -> confirm on MyTax.DC (Tax History tab).

Usage:
  python dc_parcel_pull.py --ssl "0067 0066"            # square + lot (suffix optional, e.g. "0199 0821" or "5128N 0012")
  python dc_parcel_pull.py --address "1500 21ST ST NW"
  options: --json out.json  --md out.md
"""
import argparse, json, sys, urllib.parse, urllib.request, datetime as dt
BASE="https://maps2.dcgis.dc.gov/dcgis/rest/services/DCGIS_DATA/Property_and_Land_WebMercator"
NFHL="https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer/28/query"
CLASS2=[(5_000_000,0.0165),(10_000_000,0.0177),(float('inf'),0.0189)]   # whole-value rate by AV band (DC OTR, FY2026)
RATES={'1':0.0085,'3':0.05,'4':0.10}
def get(url,params,timeout=40):
    q=url+"?"+urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(q,headers={'User-Agent':'ORA-intake/1.0'}),timeout=timeout) as r:
        return json.load(r)
def ssl_key(s):
    p=s.split()
    if len(p)!=2: raise SystemExit("SSL must be 'SQUARE LOT', e.g. '0067 0066'")
    sq,lot=p
    return f"{sq:<8}{lot}" if len(sq)<=8 else f"{sq}{lot}"   # DC pads square+suffix to 8 chars
def ms(ts): return dt.datetime.fromtimestamp(ts/1000,dt.timezone.utc).date().isoformat() if ts else None
def class_rate(cls,av):
    if str(cls)=='2':
        for cap,r in CLASS2:
            if av<=cap: return r
    return RATES.get(str(cls))
def pull(ssl=None,address=None):
    where=f"SSL='{ssl_key(ssl)}'" if ssl else f"PREMISEADD LIKE '{address.upper().strip()}%'"
    d=get(f"{BASE}/MapServer/40/query",dict(where=where,outFields='*',returnGeometry='true',outSR=4326,f='json'))
    feats=d.get('features',[])
    if not feats: raise SystemExit(f"No parcel for {where}")
    if len(feats)>1: print(f"[warn] {len(feats)} parcels matched; using the first. Refine with --ssl.",file=sys.stderr)
    a=feats[0]['attributes']; geom=feats[0].get('geometry',{})
    ssl_q=a['SSL']
    out=dict(ssl=ssl_q.split(),premise=a.get('PREMISEADD'),owner=a.get('OWNERNAME'),owner_mailing=f"{a.get('ADDRESS1','')} {a.get('CITYSTZIP','')}".strip(),
             use=f"{a.get('USECODE')} {a.get('PROPTYPE')}",tax_class=a.get('CLASSTYPE'),neighborhood=f"{a.get('NBHD')} {a.get('NBHDNAME')}",ward=a.get('PRMSWARD'),
             land_sf=a.get('LANDAREA'),
             sale=dict(price=a.get('SALEPRICE'),date=ms(a.get('SALEDATE')),code=a.get('ACCEPTCODE'),type=a.get('SALETYPE')),
             assessment=dict(current_total=a.get('OLDTOTAL'),current_land=a.get('OLDLAND'),current_impr=a.get('OLDIMPR'),
                             proposed_total=a.get('NEWTOTAL'),proposed_land=a.get('NEWLAND'),proposed_impr=a.get('NEWIMPR'),
                             billed_basis=a.get('ASSESSMENT'),annual_tax=a.get('ANNUALTAX'),tax_rate_per_100=a.get('TAXRATE')),
             extract_date=ms(a.get('EXTRACTDAT')))
    # tax history: CY1/CY2 = current-year halves; PY1..PY10 = prior years
    hist=[]
    cy=[a.get(f'CY{h}YEAR') for h in (1,2)]
    if cy[0]:
        row=dict(ty=a['CY1YEAR'],tax=0,pen=0,int=0,fee=0,due=0,paid=0)
        for h in (1,2):
            for k,f in (('tax','TAX'),('pen','PEN'),('int','INT'),('fee','FEE'),('due','TOTDUE'),('paid','COLL')):
                row[k]+=a.get(f'CY{h}{f}') or 0
        hist.append(row)
    for i in range(1,11):
        y=a.get(f'PY{i}YEAR')
        if not y: continue
        hist.append(dict(ty=y,tax=a.get(f'PY{i}TAX') or 0,pen=a.get(f'PY{i}PEN') or 0,int=a.get(f'PY{i}INT') or 0,fee=a.get(f'PY{i}FEE') or 0,
                         due=a.get(f'PY{i}TOTDUE') or 0,paid=a.get(f'PY{i}COLL') or 0,credit=a.get(f'PY{i}CR') or 0))
    for h in hist:
        h['late']=bool(h['pen'] and h['pen']>5)
        h['unpaid']=round(max(0,(h['due'] or 0)-(h['paid'] or 0)),2)
    out['tax_history']=hist
    late=[h['ty'] for h in hist if h['late']]
    out['flags']=dict(late_payment_years=late, late_payment_count=len(late), years_checked=len([h for h in hist if h['tax']]),
                      unpaid_balance=round(sum(h['unpaid'] for h in hist),2),
                      ask_side_note="Late payments are a Seller/Motivation signal (tax delinquency/distress), not a buyer cost.")
    pa=out['assessment']['proposed_total'] or 0
    r=class_rate(a.get('CLASSTYPE'),pa)
    out['next_bill']=dict(assessment=pa,rate=r,real_property_tax=round(pa*r,2) if r else None,
                          note="Next TY bill on the proposed assessment (TY = Oct-Sep; halves due 3/31 and 9/15). Excludes BID / public space / special assessments.")
    # CAMA
    for lyr in (23,25,24):
        try:
            c=get(f"{BASE}/FeatureServer/{lyr}/query",dict(where=f"SSL='{ssl_q}'",outFields='*',f='json'))
            if c.get('features'):
                out['cama']=dict(layer=lyr,**{k:v for k,v in c['features'][0]['attributes'].items() if v is not None}); break
        except Exception as e:
            out.setdefault('warnings',[]).append(f"CAMA layer {lyr}: {e}")
    # FEMA at centroid
    try:
        ring=geom.get('rings',[[]])[0]
        if ring:
            x=sum(p[0] for p in ring)/len(ring); y=sum(p[1] for p in ring)/len(ring)
            f=get(NFHL,dict(geometry=f"{x},{y}",geometryType='esriGeometryPoint',inSR=4326,spatialRel='esriSpatialRelIntersects',
                            outFields='FLD_ZONE,ZONE_SUBTY,SFHA_TF,DFIRM_ID',returnGeometry='false',f='json'))
            z=f.get('features',[{}])[0].get('attributes',{}) if f.get('features') else {}
            out['flood']=dict(point=[round(x,6),round(y,6)],zone=z.get('FLD_ZONE'),subtype=z.get('ZONE_SUBTY'),sfha=z.get('SFHA_TF'),dfirm=z.get('DFIRM_ID'),
                              note="Centroid query; a pad-level determination still needs the building footprint (ora-flood-zoning-dd).")
    except Exception as e:
        out.setdefault('warnings',[]).append(f"FEMA NFHL: {e}")
    out['not_covered']="BID tax, public-space rental fees, special assessments, assessment history before the current/proposed pair (use tax history ÷ the year's Class rate as an implied AV, [EST]): confirm on MyTax.DC."
    return out
def to_md(o):
    a=o['assessment']; L=[f"# DC parcel intake — {o['premise']} (SSL {' '.join(o['ssl'])})",
      f"- Owner: {o['owner']} · mailing {o['owner_mailing']}",
      f"- Use {o['use']} · Class {o['tax_class']} · {o['neighborhood']} · Ward {o['ward']} · land {o['land_sf']:,.0f} SF",
      f"- Last sale: {o['sale']['date']} ${o['sale']['price']:,.0f} ({o['sale']['code']}, {o['sale']['type']})" if o['sale']['price'] else "- Last sale: [DATA-GAP]",
      f"- Assessment current ${a['current_total']:,.0f} (land ${a['current_land']:,.0f}) → proposed ${a['proposed_total']:,.0f} (land ${a['proposed_land']:,.0f})",
      f"- Next real property bill on proposed: ${o['next_bill']['real_property_tax']:,.2f} at {o['next_bill']['rate']*100:.2f}%" if o['next_bill']['real_property_tax'] else "",
      f"- Late payment in {o['flags']['late_payment_count']} of {o['flags']['years_checked']} years: {o['flags']['late_payment_years']} · unpaid ${o['flags']['unpaid_balance']:,.2f}",
      ]
    if 'cama' in o: L.append(f"- CAMA (layer {o['cama']['layer']}): AYB {o['cama'].get('AYB')} · EYB {o['cama'].get('EYB')} · GBA {o['cama'].get('LIVING_GBA') or o['cama'].get('GBA')}")
    if 'flood' in o: L.append(f"- FEMA: Zone {o['flood']['zone']} ({o['flood']['subtype']}), SFHA {o['flood']['sfha']}, DFIRM {o['flood']['dfirm']}")
    L+=["","| TY | Tax | Penalty | Interest | Fees | Paid | Late |","|---|---|---|---|---|---|---|"]
    for h in o['tax_history']:
        L.append(f"| {h['ty']} | {h['tax']:,.2f} | {h['pen']:,.2f} | {h['int']:,.2f} | {h['fee']:,.2f} | {h['paid']:,.2f} | {'YES' if h['late'] else ''} |")
    L+=["",f"Not covered: {o['not_covered']}",f"Extract date: {o['extract_date']}"]
    return "\n".join(x for x in L if x is not None)
if __name__=='__main__':
    ap=argparse.ArgumentParser(); g=ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--ssl'); g.add_argument('--address'); ap.add_argument('--json'); ap.add_argument('--md')
    A=ap.parse_args(); o=pull(A.ssl,A.address)
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')   # ORA: Windows console (cp1252) cannot print the report
    if A.json: json.dump(o,open(A.json,'w',encoding='utf-8'),indent=1)
    md=to_md(o); print(md)
    if A.md: open(A.md,'w',encoding='utf-8').write(md)
