# Verified County Endpoints — ORA Parcel Data Recovery
All verified live 2026-06-11 unless noted. Match rates from the v03 recovery run.

## Jackson County, MO (KC) — 98.3% (1,807/1,839)
- **Endpoint:** `https://jcgis.jacksongov.org/arcgis/rest/services/ParcelViewer/ParcelsAscendRelate/MapServer/2` (table `Ascend_GisInfo`, Tyler/Ascend CAMA relate)
- **Join:** `parcel_number`, dashed format exactly as screens ship (`29-320-30-03-00-0-00-000`)
- **Fields:** `total_sqft` (assessor total bldg SF), `landuse_cd`/`landuse_cd_descr`; `year_built` ~unpopulated for commercial
- **Caveats:** gis.jacksongov.org (no `jc` prefix) is NOT the same host and is unreachable. Underground/cave complexes carry multi-million SF — flag bldg_sf > 1M. Workbook "Assessed/Auditor $" for Jackson is FRACTIONAL assessED (32% statutory): market = assessed / 0.32.

## Wyandotte County, KS / UG KCK — SF 97.9% (779/796); values 75% (597/796, 2019 vintage)
- **SF:** AGOL org `services1.arcgis.com/Qo2HHQp8vgPs2wg3` — `Building_Footprint/FeatureServer/1` footprints (Shape__Area, sq ft) intersected with parcels from `Parcel_py_Values/FeatureServer/0` (join `PARCEL_NBR`). Footprints drawn ≤2020-12; post-2020 construction missing.
- **Values:** `Commercial_18_19/FeatureServer/1`, join `PARCEL` (string; `PARCEL_NBR` there is integer) — `AppraisedTotal2019` etc. **STALE 2019.**
- **CRITICAL:** UG's published `SqFootage`/`SQFT` attributes are LAND area, not building area (verified ≈ ACRE × 43,560). Never use as building SF.
- **Live CAMA:** `landsweb.wycokck.org` / `maps.wycokck.org` — DOWN at origin (521/timeout) 2026-06-11. Recheck before Wyandotte reprice; replace 2019 values when live.

## Clay County, MO (KC) — 97.9% (503/514)
- **Endpoint:** `https://gisweb.claycountymo.gov/s/rest/services/InternetmapParcel2/MapServer` via the county's proxy `…/proxy/proxy.ashx?<url>` (injects required token). Layer 3 "Taxable Parcels" (CAMA attrs), layer 0 "Building Footprints" (geometry-only; st_area).
- **Renumbered parcels:** assessor `/pub/rest/parcels?situs=` JSON API (needs Referer header).
- **Caveats:** `actual_year_built`/`total_area` published for residential only ⇒ commercial SF = footprint-intersect. Workbook values are market-basis (median ~$30/SF) — no ratio conversion.

## Hamilton County, OH (Cincinnati) — 89.4% (1,840/2,058)
- **Parcels+values:** CAGIS `https://cagisonline.hamilton-co.org/arcgis/rest/services/COUNTYWIDE/AuditorParcelInformation/MapServer/15`, join `PARCELID` (12-digit). Fields: `MKTLND`, `MKTIMP`, `MKT_TOTAL_VAL` (full market — fixes the impMktModeled improvements-only defect), `DELQ_TAXES`, `ANNUAL_TAXES`, `ACREDEED`, `SALAMT`, `SALDAT` (Excel serial), `LUCLASS`, `OWNNM1`.
- **SF:** `COUNTYWIDE/PlanimetricLayers/MapServer/6` "Building Polygons" (`SQFT`, `EST_STORY`; `YEAR_BUILT` unpopulated) — spatial intersect with L15 parcel geometry, one POST per parcel (threaded ~12 workers; ~2,000 parcels ≈ 4 bash batches).
- **Caveats:** L17 "Auditor Building Info" SQFT fields are residential-only (null for commercial). 811/1,840 parcels have EST_STORY > 1 — GBA understated by footprint.

## Butler County, OH — SF 89.6% (722/806); values 100%
- **PIN match:** `https://maps.butlercountyauditor.org/arcgis/rest/services/PARCELSEARCH/MapServer/0` (PIN, LUC, YRBLT; value fields null).
- **SF (GBA):** Tyler iasWorld datalet scrape `https://propertysearch.bcohio.gov/Datalets/Datalet.aspx?mode=commercial&UseSearch=no&pin=<PIN>` — sum `AREA` lines of "COMMERCIAL INTERIOR/EXTERIOR (ALL CARDS)".
- **Values:** same host, `mode=profileall` — "Land/Building/Total Value (100%)", tax year 2025; prior-year delinquency from the tax table.

## Clermont County, OH — SF 73.5% (241/328); values 97%
- **Bulk CAMA:** `https://www.clermontauditor.org/wp-content/uploads/PublicAccess/CLERMONT_AA407.ZIP` (full iasWorld DAT tables). SF = Σ `COMINTEXT.AREA` per parcel (cross-check `COMDAT.AREASUM`); values = `APRVAL.DAT` APRLAND/APRBLDG/APRTOT (latest active TAXYR); delq = `CHARGE.DAT` NETDELQ; LUC = PARDAT.
- **Footprint fallback:** `https://maps.clermontcountyohio.gov/server/rest/services/WMAS/BuildingOutlines/MapServer/0` (has `PIN`; `area` already sq ft).
- **Caveats:** PINs carry trailing dots — preserve exactly. OBY.DAT yard items are paving-contaminated; never report as building SF.

## Warren County, OH — SF 76.9% (319/415); values 99.3%
- **Account map:** nightly export `https://auditor.warrencountyohio.gov/propertysearch/PublicDataExport/DownloadData` — SummaryData.csv maps ParcelNumber→AccountNumber. **Export strips leading zeros from parcel numbers** — normalize before joining.
- **SF:** scrape `…/PropertySearch/Summary/Building?account_nbr=<acct>` (+`blg_nbr` per building; sum all buildings). CommercialBuildingData/FloorData CSVs in the export are header-only (county defect).
- **Values:** ValuesData.csv LandMarketValue/BuildingMarketValue — **sum component rows per account-year** (TIF/exempt splits; single-row reads understate). Delq: scrape Summary/Index "Due" row.
- **Caveats:** ~54 parcels carried at Area=0 (sound-value pricing) — no published SF; GIS folders token-locked.

## Statutory assessment ratios (value-basis conversions)
- MO commercial assessed = 32% of market → market = assessed / 0.32
- KS commercial assessed = 25% of appraised → appraised = assessed / 0.25
- OH auditor values are 100% market (35% assessed exists but screens ship market)

## Not yet researched
Indianapolis metro (Marion, Hendricks, Boone, Hamilton-IN, Johnson), Madison/Dane WI NO-SF rows, Baltimore SDAT name-recovery, Henrico mail addresses.
