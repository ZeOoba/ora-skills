# Verified County Endpoints — ORA Parcel Data Recovery (v2)
Replaces `references/endpoints.md`. v2 corrections (2026-06-16): Jackson `total_sqft` relabeled LAND;
added FEMA USA Structures fallback, Franklin OH, and the Indianapolis metro. Match rates from the runs noted.

## ⚠️ v2 critical corrections
- **Jackson MO `total_sqft` is LAND area, NOT building SF** (v1 was wrong — it equals the screen "Land
  SF"; a 195,971 parcel survived the >50K-SF kill gate). Use FEMA USA Structures (below) for Jackson
  building SF.
- **Marion IN `ESTSQFT` is LOT square footage, not building** — never use as building SF.
- Always run the **land-vs-building unit-assertion gate** (SKILL.md QC, Edit 2 above) before shipping
  any recovered SF.

## FEMA USA Structures — universal building-SF fallback (NEW)
For any county with no usable footprint/CAMA building source:
- **Service:** `https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/USA_Structures_View/FeatureServer/0`
  — field `SQFEET` (true building sq ft; vintage ~2016–2020, post-2020 construction missing).
- **Method:** spatial-intersect FEMA structures with the county parcel polygon; FEMA-vs-county geometry
  is misregistered, so use **Intersects + majority-in (>50%)**, not Contains; for straddlers,
  area-proportional clip. Take area from `SQFEET`, never recompute from Web Mercator.
- Footprint = ground-floor floor ⇒ multi-story understated; tag `method=fema_structures_majority_in`.

## Franklin County, OH (Columbus) — land area + building SF (NEW) — 1,130/1,132 (99.8%)
- **Endpoint:** `https://gis.franklincountyohio.gov/hosting/rest/services/ParcelFeatures/Parcel_Features/MapServer/0` (layer "Tax Parcel").
- **Join:** `PARCELID`, dashed exactly as screens ship (`010-113471`).
- **Fields:** `STATEDAREA` = land **square feet** (aliased "Legal Acres" but is sq ft — 24,107 = 0.55
  ac); `BLDGAREA` (matches auditor bldg SF); `ACRES` (GIS) is null service-wide — use `STATEDAREA`.
- **FAR:** Bldg SF ÷ `STATEDAREA` directly (STATEDAREA already sq ft — do NOT ×43,560).

## Jackson County, MO (KC) — building SF via FEMA — 1,762/1,839 (95.8%)
- **Building SF:** FEMA USA Structures (above) intersected (majority-in) with parcel polygons
  `https://jcgis.jacksongov.org/arcgis/rest/services/ParcelViewer/ParcelsAscendRelate/MapServer/1`
  (join `Name`, dashed). Jackson County GIS has NO native footprint/structure layer.
- **Land area:** screen "Land SF" (= the Ascend `total_sqft`, which is LAND). **Do NOT use `total_sqft`
  as building SF.**
- **Caveats:** `gis.jacksongov.org` (no `jc`) is a different, unreachable host. Underground complexes
  carry multi-million SF — flag >1M. Ascend "Assessed/Auditor $" is fractional (÷0.32 for market).

## Clay County, MO (KC) — 447/514 (87.0%)
- **Building SF:** footprint layer 0 (st_area) at `https://gisweb.claycountymo.gov/s/rest/services/InternetmapParcel2/MapServer`
  via county proxy `…/proxy/proxy.ashx?<url>` (injects token); layer 3 "Taxable Parcels" for CAMA.
  Renumbered parcels: assessor `/pub/rest/parcels?situs=` (needs Referer).
- **Caveats:** `actual_year_built`/`total_area` residential-only ⇒ commercial SF = footprint. Values
  market-basis (~$30/SF) — no ratio.

## Wyandotte County, KS / UG KCK — 733/797 (92.0%)
- **Building SF:** AGOL `services1.arcgis.com/Qo2HHQp8vgPs2wg3` `Building_Footprint/FeatureServer/1`
  (`Shape__Area`, sq ft) intersected with `Parcel_py_Values/FeatureServer/0` (join `PARCEL_NBR`).
  Footprints ≤2020-12.
- **CRITICAL:** UG's published `SqFootage`/`SQFT` are LAND (≈acre×43,560) — never building.
- **Values:** `Commercial_18_19/FeatureServer/1` (join `PARCEL` string) `AppraisedTotal2019` — STALE
  2019; KS commercial market = assessed/0.25. Live CAMA `landsweb.wycokck.org`/`maps.wycokck.org` was
  down 2026-06-11 — recheck before any Wyandotte reprice.

## Hamilton County, OH (Cincinnati) — ~185 (Top-150 + leads)
- **Parcels+values:** CAGIS `…/COUNTYWIDE/AuditorParcelInformation/MapServer/15` (join `PARCELID`
  12-digit; `MKT_TOTAL_VAL`, `DELQ_TAXES`, `ACREDEED`, `LUCLASS`).
- **SF:** `COUNTYWIDE/PlanimetricLayers/MapServer/6` "Building Polygons" (`SQFT`, `EST_STORY`)
  spatial-intersect with L15 geometry. L17 SQFT is residential-only.

## Butler County, OH — 206/206 (100%)
- **PIN/LUC/YrBlt + ACRES:** `https://maps.butlercountyauditor.org/arcgis/rest/services/PARCELSEARCH/MapServer/0`
  (value fields null).
- **Building GBA (true, multi-story captured):** Tyler iasWorld datalet
  `https://propertysearch.bcohio.gov/Datalets/Datalet.aspx?mode=commercial&UseSearch=no&pin=<PIN>` —
  sum `AREA` of "COMMERCIAL INTERIOR/EXTERIOR (ALL CARDS)". No Butler footprint layer exists.
- **Values:** same host `mode=profileall` (100% values, TY2025).

## Clermont County, OH — 250/365 (68%)
- **Building SF (fast):** footprint ArcGIS
  `https://maps.clermontcountyohio.gov/server/rest/services/WMAS/BuildingOutlines/MapServer/0`
  (`PIN`; `area` already sq ft), summed per PIN. PINs carry trailing dots — preserve.
- **Bulk CAMA (alt):** `https://www.clermontauditor.org/wp-content/uploads/PublicAccess/CLERMONT_AA407.ZIP`
  (iasWorld DAT: SF = Σ COMINTEXT.AREA; values APRVAL.DAT; delq CHARGE.DAT). Footprint-less
  vacant/300-LUC = NO-SF.

## Warren County, OH — 311/452 (68%)
- **Account map + land + values:** nightly export
  `https://auditor.warrencountyohio.gov/propertysearch/PublicDataExport/DownloadData` (SummaryData.csv
  ParcelNumber→AccountNumber; **strips leading zeros** — normalize). ValuesData.csv — sum component
  rows per account-year.
- **Building SF:** scrape `…/PropertySearch/Summary/Building?account_nbr=<acct>` per building.
- **v2 caveat (corrects v1):** the CommercialBuilding/FloorData export files carry rows but `AREA` is
  **zero-filled** (still unusable); the per-building AJAX **zero-fills non-primary buildings** (server
  defect) — scrape captures the PRIMARY building only ⇒ multi-building GBA UNDERSTATED. Tag
  `scrape-primary-bldg(of N; total UNDERSTATED)`; SF-verify any multi-bldg row that screens IN before
  LOI. ~54 Area=0 sound-value parcels = NO-SF.

## Indianapolis metro (NEW)
- **Marion:** parcels `https://gis.indy.gov/.../sde_Parcel/sde_Parcel/MapServer/5` (`ACREAGE`, join
  `STATEPARCELNUMBER` dashed); buildings `…/sde_Buildings/sde_Buildings/MapServer/0` (join
  `PARCEL_TAG`; `SHAPE.STArea()` sq ft, SR 2965). **Do NOT use parcel `ESTSQFT` — it is LOT SF.**
  1,786/1,908 (93.3%).
- **Hamilton-IN:** parcels `https://gis1.hamiltoncounty.in.gov/.../HamCoParcelsPublic/FeatureServer/0`
  (`DEEDACRES`, `STPRCLNO`) + `HamCoBuildingFootprints/FeatureServer/6` (`Shape__Area`, SR 6459,
  majority-in). 255/282 (90.4%).
- **Boone / Hendricks / Johnson:** land from state parcels
  `https://gisdata.in.gov/server/rest/services/Hosted/Parcel_Boundaries_of_Indiana_Current/FeatureServer/0`
  (reproject to EPSG:2965; join `state_parcel_id`); building SF from **FEMA USA Structures**
  (majority-in). 77–87%. Post-2020 construction beyond FEMA vintage = NO-SF; upgrade via
  Schneider/Beacon scrape for true GBA + stories.

## Statutory assessment ratios (value-basis)
- MO commercial market = assessed / 0.32 · KS commercial appraised = assessed / 0.25 · OH auditor
  values = 100% market.

## Still not researched
Baltimore-MD SDAT name-recovery; Henrico mail addresses; Madison/Dane WI NO-SF rows; Indianapolis
collar true-GBA upgrade (Schneider/Beacon).
