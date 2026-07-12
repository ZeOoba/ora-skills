---
name: ora-flood-zoning-dd
description: "Resolve the two hardest DD-Critical screen items for Oxford Realty Advisors acquisitions: FEMA flood determination and zoning/permitted-use verification. Use whenever the user mentions: flood zone, FEMA, SFHA, NFHL, floodplain, flood determination, zoning check, zoning designation, permitted use, zoning GIS, or when an acquisition screen/underwrite has unresolved flood or zoning DD-Critical items (Buy Box v1.0 caps any such deal at T2 WATCH). Produces a sourced determination block per parcel. v1.1 (endpoints verified 2026-06-09; batch-write safety rule added 2026-07-12)"
---

# ORA Flood & Zoning DD-Critical Resolution

Purpose: convert "FEMA UNK" and "zoning UNK" into sourced determinations at SCREEN stage. Under Buy Box v1.0, any unresolved DD-Critical item caps a deal at T2 WATCH — resolving these two is usually the cheapest score unlock.

## Decision rules (Buy Box v1.0, ratified 2026-06-09)
- SFHA (Zone A/AE/AH/AO/VE) on the **building pad** = GATE KILL.
- SFHA on **excess land only** = proceed; land valued at **$0 in the basis test until FEMA determination is verified** (then re-credit and re-score — report both as a band, e.g., "58 → 71 if dry").
- Zone X (shaded/unshaded) = no flood constraint; record panel + effective date anyway.
- Zoning at screen = GIS designation + permitted-use check vs the municipal code. A **formal municipal zoning letter remains mandatory pre-LOI** — this skill does not substitute for it.
- NEVER assert flood or zoning status without a named source and date. If every tier fails, report UNVERIFIED explicitly.
- **Never write determinations into the source master in place (added v1.1, 2026-07-12).** When this skill's determinations are applied to an off-market/DD master workbook at batch scale (not a single ad hoc lookup), the writing script must load the CURRENT master, copy it to a NEW version (`YYYYMMDD_[Name]_v##.xlsx`) FIRST, and write all updates only to that copy — never `wb.save()` back onto the path it loaded from. Mirrors `parcel-data-recovery` Iron rule 6 (versioning) and Iron rule 2 (never overwrite shipped data). Precedent: 2026-07-12 Cincinnati/Hamilton-Butler-Clermont-Warren auto-DD flood pass (101 T2-QUEUE rows) wrote its DD-Critical updates directly into `v05` in place — caught after the fact, remediated by hand-copying to `v06`, no data lost, but the deviation should never have been possible. Any batch flood/zoning automation script must copy-then-write from the first line.

## Workflow

### Step 1 — Geocode the parcel
Census geocoder (free, no key):
`https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?address={URL-ENCODED ADDRESS}&benchmark=Public_AR_Current&format=json`
Take lon/lat from `result.addressMatches[0].coordinates` (x=lon, y=lat). For land-heavy parcels, also pull the parcel polygon from the county GIS (Step 3 endpoints) and test pad vs yard separately — a centroid point query is NOT sufficient for the pad/yard split.

### Step 2 — FEMA NFHL point/polygon query (primary)
Base (VERIFIED 2026-06-09): `https://hazards.fema.gov/arcgis/rest/services/public/NFHL/MapServer`
- Layer **28 = Flood Hazard Zones**. Point query:
  `/28/query?geometry={lon},{lat}&geometryType=esriGeometryPoint&inSR=4326&outFields=FLD_ZONE,ZONE_SUBTY,SFHA_TF&returnGeometry=false&f=json`
- `SFHA_TF = "T"` → SFHA. Record FLD_ZONE, ZONE_SUBTY, FIRM panel (layer 3) + effective date.
- Useful layers: 3 FIRM Panels · 16 BFEs · 23 Levees · 27 Flood Hazard Boundaries.
- The service is intermittently unavailable. On timeout/error, retry once, then go to Step 3. Do not loop.

### Step 3 — County/city GIS (flood fallback + zoning primary)
See `references/endpoints.md` for the full directory with VERIFIED/UNVERIFIED status. Hit the REST root with `?f=json` to enumerate services, find floodplain/zoning layers, then point-query as in Step 2. Verified anchors:
- Cincinnati/Hamilton Co: `https://cagisonline.hamilton-co.org/arcgis/rest/services` (CINC_PLANNING = city zoning)
- Indianapolis/Marion Co: `https://xmaps.indy.gov/arcgis/rest/services` (DMDPortal = zoning)
- Johnson Co KS: `https://maps.jocogov.org/arcgis/rest/services`
- Anne Arundel Co MD: `https://gis.aacounty.org/arcgis/rest/services` (OPZ folders)
- Columbus zoning: `https://maps2.columbus.gov/arcgis/rest/services/Schemas/BuildingZoning/MapServer`

### Step 4 — State floodplain fallbacks
OH: `https://gis.ohiodnr.gov/arcgis/rest/services` (DSW_Services) · IN: INFIP viewer (browser) · WI: DNR Surface Water Data Viewer (browser) · MD: `https://mdfloodmaps.net`.

### Step 5 — Browser-only last resort
FEMA MSC `https://msc.fema.gov/portal/search?AddressQuery={address}` and Municode/AmLegal zoning codes are JS apps — use Claude-in-Chrome tools, not raw fetch. Gahanna's code (codelibrary.amlegal.com) sits behind a bot challenge: browser only. Remember the Gahanna IM overlay: front yard barred from parking/outdoor storage/ground solar.

### Step 6 — Permitted-use check
With the zoning designation in hand, list permitted/conditional/prohibited uses relevant to ORA tenancy (warehouse, light mfg, contractor shop, outdoor/IOS storage, fleet parking). Flag: IOS/outdoor storage is the most commonly prohibited use ORA cares about. Cite code section numbers.

## Output format (per parcel)
```
FLOOD: [Zone X / SFHA Zone AE ...] — pad: [IN/OUT of SFHA]; excess land: [IN/OUT/N-A]
  Source: [NFHL layer 28 / county layer], panel [#], eff. [date], queried [date]
  Basis impact: [none / land at $0 pending verification / GATE KILL]
ZONING: [designation] ([jurisdiction]) — permitted: [...]; prohibited/conditional: [IOS? ...]
  Source: [GIS service / code section], queried [date]. Zoning letter still required pre-LOI.
VERDICT IMPACT: [e.g., removes T2 cap; score X → Y]
```
Log results to the Notion Deal Sourcing Log `DD-Critical Status` field for the deal.

## Maintenance
Endpoint directory verified 2026-06-09 (see references/endpoints.md for per-URL status). Re-verify UNVERIFIED entries on first use in that market; entry markets (Grand Rapids, Richmond, Des Moines) are unverified wholesale. Suggest a quarterly verification pass alongside ora-replacement-cost-refresh.

## Changelog
- **v1.1 (2026-07-12):** Added the batch-write safety rule (Decision rules section) after a 2026-07-12 Cincinnati auto-DD flood pass wrote determinations directly into the source master workbook in place instead of a new version — caught and hand-remediated same-session, no data lost, but the skill previously gave batch automation no versioning guardrail of its own (unlike its sibling `parcel-data-recovery`, which has carried this as Iron rule 6 since v1.0). Any future batch-scale use of this skill's output against a master workbook must copy-then-write.
- **v1.0:** initial (endpoints verified 2026-06-09).
