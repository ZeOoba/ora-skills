---
name: "listing-enrichment-gate"
description: "Verify a broker listing's SF, year built, construction, use class, site coverage, owner and flip history against county/public sources before scoring; run on every new on-market deal before it is scored or logged T1, and for the ora-deal-sourcing-scan STEP 3D T1 verify pass (use code, footprint-to-parcel coverage, listing clear height). Trigger on: enrich this listing, verify listing SF, check the use code, is this really industrial, site coverage, flip history, certify the listing data. NOT a deal verdict — a pursue/pass pre-screen routes to verified-deal-recon and scoring to acquisition-underwriting SCREEN; off-market parcel SF/value gaps route to parcel-data-recovery; FEMA flood and zoning permitted-use determinations route to ora-flood-zoning-dd."
---

# listing-enrichment-gate (v1.4)

Run BEFORE a listing is scored or logged as T1. Output is a PROVISIONAL or CERTIFIED record in the Deal Sourcing Log (collection://9a6ae219-85a3-4621-899c-c757fd062f8b). Dedupe against Deal Sourcing Log and Acquisition Pipeline (bcfe4a03) first.

## Procedure (order matters)
1. **SF variance first (Rule 6).** Compare listing SF to assessor SF and to FEMA/ORNL footprint. <=2% proceed; 2-5% flag, use lower SF; >5% hard stop, cap T2, recompute basis ceiling on the lower verified SF. Multi-building parcels: sum buildings, and state which building the listing SF ties to. A footprint is a two-dimensional roof area, not GBA: where the listing mentions a mezzanine or second floor, say so and treat a footprint shortfall as a flag that still needs an assessor SF, never as proof the listing is overstated.
2. **Owner and transfer history.** Owner name, mail address, last transfer date/price. FLIP FLAG if last arms-length transfer <24 months or price < ask by >10%; note non-consideration transfers (MD CONVEY1=4) as tenure-unknown, not flips.
3. **Year built (Rule 1).** County record; if unpublished, default 1995 and mark source NOT AVAILABLE.
4. **Construction.** Only from a county field (MD SDAT DESCCNST) or verified imagery; otherwise NOT VERIFIED. Never accept listing wording as verified.
5. **Use class / zoning (Rule 8).** County use class vs listing (auto-use, mixed-use, office, RETAIL, other); flag conflicts on the specific parcel, not the address. Output `USE-CODE: <code> | <source>` and an ASSET-CLASS result: INDUSTRIAL/FLEX VERIFIED · RETAIL/OFFICE/OTHER → FAIL, re-route to acquisition-underwriting Stage 2.9 (ALT-ASSET-TRACK) · MIXED/CONFLICT/UNVERIFIED → cap T2. (v1.4; origin 13500 E 40 Hwy, Gordmans anchor.)
6. **Basis test.** Ceiling = floor $/SF x verified SF / 1.02, floor = RCT v03 LOW x (1 - ramp) (LOW: the figures ship privately as `rct-table.local.json` in this skill's folder (public repo); missing or not `RCT v03` → report `RCT TABLE UNAVAILABLE` and skip the basis test, never substitute a figure), ramp 65% at <=1995 to 60% at >=2005. Compare to assessed value; flag DENOMINATOR-SENSITIVE within +/-5 pts.
7. **Height/power/coverage.** Footprint roof HEIGHT (m) is an indicator, not clear height; record listing/OM clear height separately (mixed clear: record the minimum AND maximum bay) and test it at the scan's STEP 3A thresholds. **Site coverage = Σ in-parcel footprint SF ÷ parcel land SF** (footprints from step 1; land SF from the parcel polygon or county land field per the Source table); >60% is a failed physical floor. Power = UNKNOWN until electrician-verified. (v1.4; origin 67 & 76 Washington Ave, ~86% coverage.)
8. **Listing age.** >30 days or unverified date = STALE-LISTING.
9. **Certification.** CERTIFIED only if year built, construction, SF, zoning, tax AND use class (step 5 INDUSTRIAL/FLEX VERIFIED) are ALL verified; else PROVISIONAL. Record score as [floor-ceiling]. Note: this PROVISIONAL is a data-certification state, distinct from the deal-sourcing scan's index-only PROVISIONAL listing rule.
10. **Write** Enrichment Findings, Year Built Source, Construction Source, Enrichment Date, Data Certification, Power Status to Notion.

## Query transport (v1.2)
GIS REST queries with polygon geometry or long envelopes exceed WebFetch's URL-length limit (proxy 403 "url exceeds the maximum fetchable length"). Send them as **POST bodies from Bash/Python** to the public ArcGIS endpoints listed below. This is a transport fix for open county/government GIS services only. It never applies to a host that WebFetch reports as robots-disallowed or blocked (e.g. FEMA NFHL at hazards.fema.gov, LoopNet, Crexi, CoStar, the PVA property-record site): those stay unreached, are recorded as such, and go to the county-hosted mirror or a user-supplied document instead.

## Source table (tested quirks)
- Footprints: `https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/USA_Structures_View/FeatureServer/0` - envelope query on parcel polygon (outSR 4326), keep structures whose centroid is inside parcel (point-in-polygon), dedupe BUILD_ID. Footprint is not GBA. Use POST (see Query transport).
- Hamilton OH: CAGIS mirror, ADDRNO as quoted string; no year built/SF.
- Hamilton IN: `https://gis1.hamiltoncounty.in.gov/arcgis/rest/services/HamCoParcelsPublic/MapServer/0` - fields sq_ft_comm, year_built (often null), OWNNAME, LSTXFRDATE, AVTOTGROSS; use LOCADDRESS LIKE 'num%' and filter by street.
- Jackson MO: `https://jcgis.jacksongov.org/arcgis/rest/services/ParcelViewer/ParcelsAscendRelate/FeatureServer/1` geometry matches on `Name`; attribute layer 2 needs orderByFields=OBJECTID; total_sqft is LAND SF; no year built; non-disclosure state.
- Kent MI: no SF/year built/sales.
- Polk IA: assessor CSVs (year built, bldg_class, gross_area, sales).
- MD statewide: mdgeodata MD_PropertyData MapServer/0 (YEARBLT, SQFTSTRC, DESCCNST, TRADATE, CONSIDR1, CONVEY1; owner names scrubbed).
- Baltimore Co polygons + owner names: `https://bcgis.baltimorecountymd.gov/arcgis/rest/services/Property/Property/MapServer/1` (TAXPIN = state ACCTID[4:]; search FULL_OWNER_NAME and ADDRESS_2 for siblings; same DEED_REF = same acquisition).
- Richmond City VA: parcels `https://services1.arcgis.com/k3vhq11XkBNeeOfM/ArcGIS/rest/services/Parcels/FeatureServer/0` (no street field; use AsrLocationBldgNo + owner) and buildings `.../AssessorProVaGPINlImpDataPublish/FeatureServer/0` (match prop_street LIKE 'num Street%'; one row per building: total_comm_area, year_built, comm_bldg_type).
- **Louisville/Jefferson KY (v1.2, tested 2026-09-28 on 3900, 8301, 8340 and 7508 Cane Run Rd):** LOJIC (`https://gis.lojic.org/maps/rest/services`) gives parcel geometry, zoning, floodplain and address-to-parcel linkage, but NO year built, building SF, owner, transfer or assessed value — those live only on jeffersonpva.ky.gov (bot-gated; do not bypass) and arrive through the PVA record ingest step below. Chain: (1) address point `LojicSolutions/OpenDataAddresses/MapServer/0`, fields HOUSENO, STRNAME, PARCELID (12-digit; equals the LoopNet APN, use it as a cross-check), ZONING_CODE, ZIPCODE; (2) parcel polygon `LojicSolutions/OpenDataPVA/MapServer/1` by PARCELID (fields PARCELID, PIN, LRSN, SHAPE.AREA in sq ft — land area); (3) zoning `LojicSolutions/OpenDataDevelopment/MapServer/15` (ZONING_CODE, ZONING_NAME) and overlays `.../16` at the parcel centroid; (4) FEMA flood as mirrored by the county `PvaGis/CamaFloodContour/MapServer/2` ("Current FEMA Flood Zones": FLD_ZONE, SFHA_TF, ZONE_SUBTY, EFF_DATE) — query with the parcel polygon and report EVERY zone that intersects; (5) footprints inside the parcel via USA Structures. **Quirks:** never use the Census geocoder point to pick a parcel — on Cane Run Rd it landed in a right-of-way parcel (PARCELID 0000SROW0000); use the address point's PARCELID. Zoning layer returns code EZ1 ("ENTERPRISE ZONE") in Riverport — that is a zoning district, so run the Rule 8 permitted-use check against the Land Development Code rather than reading it as industrial. The county flood mirror carries its own effective date (EFF_DATE) and can differ by polygon, so cite it; it is a county GIS source under Stage 2.5 item 1 and does not replace a FEMA determination letter pre-LOI. Address-point ACTIVE=0 appeared on live addresses; its meaning is unverified. `OpenDataAddresses` ZONE_NAME is not the zoning district — ignore it. Listing acreage that does not tie to the parcel's SHAPE.AREA (8340 Cane Run Rd: 6.37 ac listed vs 2.33 ac parcel) means the listing spans other parcels; identify them before any basis view.

### Louisville enrichment script (Bash; POST-based; run `python3 lou.py 3900 "CANE RUN"`)
```python
import sys, json, urllib.request, urllib.parse
B = 'https://gis.lojic.org/maps/rest/services'
FP = 'https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/USA_Structures_View/FeatureServer/0/query'
def post(url, **p):  # POST avoids GET/URL-length limits
    p.setdefault('f', 'json')
    d = json.load(urllib.request.urlopen(urllib.request.Request(url, urllib.parse.urlencode(p).encode()), timeout=60))
    if 'error' in d: raise RuntimeError(d['error'])
    return d
def pip(pt, ring):
    x, y = pt; ins = False
    for i in range(len(ring)):
        (x1, y1), (x2, y2) = ring[i], ring[(i + 1) % len(ring)]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1: ins = not ins
    return ins
def run(no, street):
    a = post(B + '/LojicSolutions/OpenDataAddresses/MapServer/0/query', returnGeometry='false',
             where="HOUSENO=%d AND STRNAME LIKE '%s%%'" % (int(no), street.upper()),
             outFields='FULL_ADDRESS,PARCELID,ZIPCODE,ZONING_CODE,ACTIVE')['features']
    if not a: return print('NO ADDRESS POINT')
    print('address point:', a[0]['attributes']); pid = a[0]['attributes']['PARCELID']
    par = post(B + '/LojicSolutions/OpenDataPVA/MapServer/1/query', where="PARCELID='%s'" % pid,
               outFields='PARCELID,LRSN,SHAPE.AREA', outSR='4326', returnGeometry='true')['features']
    if not par: return print('NO PARCEL POLYGON', pid)
    rings = par[0]['geometry']['rings']; ring = rings[0]
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]; c = '%f,%f' % (sum(xs)/len(xs), sum(ys)/len(ys))
    print('parcel:', par[0]['attributes'])
    for n, lyr, f in (('zoning', 15, 'ZONING_CODE,ZONING_NAME'), ('overlays', 16, 'OVERLAYS_NAME')):
        r = post(B + '/LojicSolutions/OpenDataDevelopment/MapServer/%d/query' % lyr, geometry=c, geometryType='esriGeometryPoint',
                 inSR='4326', outFields=f, returnGeometry='false')['features']
        print(n + ':', [x['attributes'] for x in r] or 'none')
    fl = post(B + '/PvaGis/CamaFloodContour/MapServer/2/query', geometry=json.dumps({'rings': rings, 'spatialReference': {'wkid': 4326}}),
              geometryType='esriGeometryPolygon', inSR='4326', spatialRel='esriSpatialRelIntersects',
              outFields='FLD_ZONE,SFHA_TF,ZONE_SUBTY,EFF_DATE,DFIRM_ID', returnGeometry='false')['features']
    print('flood (every zone intersecting parcel):', [x['attributes'] for x in fl] or 'none returned')
    s = post(FP, geometry='%f,%f,%f,%f' % (min(xs), min(ys), max(xs), max(ys)), geometryType='esriGeometryEnvelope', inSR='4326',
             outSR='4326', spatialRel='esriSpatialRelIntersects', outFields='BUILD_ID,SQFEET,HEIGHT', returnGeometry='true')['features']
    seen, keep = set(), []
    for f in s:
        r = f['geometry']['rings'][0]; ct = (sum(p[0] for p in r)/len(r), sum(p[1] for p in r)/len(r))
        if f['attributes']['BUILD_ID'] not in seen and pip(ct, ring): seen.add(f['attributes']['BUILD_ID']); keep.append(f['attributes'])
    print('footprints in parcel: %d, total %.0f SF (footprint, not GBA)' % (len(keep), sum(k['SQFEET'] for k in keep)))
    for k in sorted(keep, key=lambda k: -k['SQFEET']): print('  ', k)
run(sys.argv[1], sys.argv[2])
```

## PVA record ingest (Louisville; v1.3) — the step that lets a Louisville listing reach CERTIFIED
Trigger: Gabriel supplies a PVA property record (record card, CAMA export or open-records reply) or a broker OM for a parcel already run through the LOJIC chain above. Never fetch the PVA site. The only outbound path is an open-records request drafted for Gabriel (PVA: pva@jeffersonpva.ky.gov, written request, email delivery free, programming billed at an estimate-first hourly rate, commercial requests on the PVA fee schedule, 5-business-day response window — verify current terms on the PVA site); any send needs Gabriel's explicit confirmation.
1. **Text-layer check (acquisition-underwriting Stage -1 Rule 7).** Run `pdfinfo` on any PDF. Rasterizer producer or empty `pdftotext` means no text layer: extract by page-image render and visual read, tag every figure `[OM-visual]`, never treat a failed text pull as an empty record.
2. **Identity match.** The record's parcel ID / LRSN / situs address must equal the LOJIC PARCELID and LRSN already on the roster row. A mismatch, or a record that covers more than one parcel, stops the ingest: reconcile before entering any field.
3. **Extract one record per parcel** into the schema below. Every field carries a source tag (`PVA record <date received>` or `broker OM`). Blank stays null; never infer, never fill from listing wording.
4. **Tie-outs.** (a) Record land acres vs LOJIC SHAPE.AREA / 43,560: a gap above 5% means a multi-parcel or partial record. (b) Sum of record structure areas vs the LOJIC footprint total: the record is authoritative, the footprint stays as a cross-check, and a large gap points to a mezzanine, multi-story or footprint error. (c) Owner of record vs the listing's named seller.
5. **Re-run Procedure steps 1-6 on record data.** Assessor SF replaces footprint as the primary comparator in Rule 6 (footprint remains the cross-check); year built comes from the record (use effective year built for the ramp only where a documented renovation R% qualifies under Stage 1; otherwise actual); construction from the record's construction field; tax from the assessed value or tax bill. Recompute the ceiling and the [floor-ceiling] score.
6. **Transfers.** A sale with blank or nominal consideration is tenure-unknown, not a flip (mirrors the MD CONVEY1=4 rule). FLIP FLAG rule unchanged.
7. **Rule 8(ii) assessment anomaly.** Exempt coding, an absent or stale record, or an assessed value implausible for an industrial improvement of that size caps the verdict at T2 and goes to QUESTIONS FOR GABRIEL.
8. **Certification.** CERTIFIED only when year built, construction, assessor SF, zoning (parcel-level LOJIC district plus the Rule 8 permitted-use check — EZ1 always needs it), tax and use class (Procedure step 5 INDUSTRIAL/FLEX VERIFIED — v1.4) are ALL verified from a source. The county flood mirror and the FEMA determination letter stay DD-Critical pre-LOI items and do not gate CERTIFIED. Score snapshots are immutable: write a new dated row or fields and mark the earlier PROVISIONAL record superseded; never overwrite history.
9. **Conflict Register (Rule 4).** Log every field where listing, footprint and record disagree (field / listing / footprint / record / value used / basis). County record wins on vintage and legal facts.

Ingest schema (one object per parcel): parcel_id; lrsn; situs_address; record_source (PVA record, broker OM); record_date; property_class; year_built; effective_year_built; construction_type; structures (list of: description, gross_area_sf, finished_area_sf, stories); land_acres; owner_name; owner_mail_address; sales (list of: date, consideration, deed_type); assessed_land; assessed_improvements; assessed_total; assessment_year; last_tax_bill; sketch_on_file (yes/no). Every value also carries its source tag.

## Output block
Verified SF (listing / assessor / footprint, variance %), buildings and years, owner + mail, last transfer, use class/zoning, assessed value vs ceiling, flags, next action, certification, [floor-ceiling] score.

## Changelog
- v1.4 (2026-10-30): Step 5 outputs an ASSET-CLASS result (retail/office/other → re-route; mixed/unverified → cap T2); step 7 computes site coverage from footprint ÷ parcel and records clear height; step 9 (and PVA ingest step 8) adds use class to CERTIFIED and disambiguates PROVISIONAL. Description expanded with trigger vocabulary and routing tie-breaks per repo convention. Companion to ora-deal-sourcing-scan v2.9 (Gabriel-approved 2026-10-30). No floor, ramp, RCT value, DSCR, LTV or score weight changed. Origin: 2026-10-30 verified-deal-recon of the 2026-10-27 T1 set. First version authored in the repo (v1.3 was registered verbatim from the store in the preceding commit).
- v1.3 (2026-09-28): Added the PVA record ingest step (identity match, schema, tie-outs, re-run on record data, certification rule, immutable-snapshot write-back) so a Louisville listing can reach CERTIFIED once a PVA record or broker OM is supplied. Includes everything from v1.2 below. No floor, ramp, or threshold changed.
- v1.2 (2026-09-28): Louisville registry gap narrowed — address-point PARCELID, parcel polygon, zoning/overlay and county-hosted FEMA flood mirror all queryable from LOJIC; PVA-only fields remain the gap. Added Query transport rule (POST from Bash for long GIS queries; never for blocked hosts), footprint-vs-GBA caution in step 1, and the tested script. Origin: 3900, 8301, 8340 and 7508 Cane Run Rd screens.