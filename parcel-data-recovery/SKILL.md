---
name: parcel-data-recovery
description: County-level building SF, market value, year-built, and tax-delinquency recovery for Oxford Realty Advisors off-market parcel screens. Use when the user mentions: recover SF, missing building SF, parcel data gap, UNSCREENABLE rows, DATA-GAP rows, county GIS pull, footprint SF, assessor values, CAMA extract, refresh parcel data, re-run P1 on recovered data, off-market master rebuild, or when an off-market screen workbook has rows lacking Bldg SF or auditor values. Encodes verified endpoints (2026-06-11) for Jackson MO, Wyandotte KS, Clay MO, Hamilton/Butler/Clermont/Warren OH, footprint-vs-GBA rules, value-basis conversions, P1 Buy Box recompute math, and the v03/v04 QC gate. v1.0
---

# Parcel Data Recovery — ORA Off-Market Screens

Recovers the inputs that block P1 Buy Box economics (building SF, market value, year built, delinquency) from county GIS/CAMA sources, then recomputes P1 and rebuilds the off-market master workbook.

## Iron rules

1. **Never fabricate.** Unrecoverable parcels are omitted from recovery CSVs, never estimated.
2. **Never overwrite shipped data.** Recovered SF/values fill blanks only. QC asserts zero overwrites.
3. **Provenance per row.** Every filled cell carries a `SF Source`/`Value Source` tag with method + endpoint.
4. **Footprint SF is a floor.** Footprint-intersect methods give ground-floor area; multi-story GBA is understated. Tag `method=footprint_intersect`; keep stories where available.
5. **Stale values never rank.** Values older than the current assessment cycle (e.g., Wyandotte 2019) are tagged `[STALE est]`, verdicts carry the tag, and stale rows are excluded from cross-market Top-100 ranking.
6. **Versioning.** Output is always a NEW version of the master (`YYYYMMDD_AllMarkets-OffMarket-Master_v##.xlsx`); prior versions are never deleted.

## Workflow

1. **Scope** — identify counties with `Bldg SF` and/or value blanks in the master (UNSCREENABLE / DATA-GAP verdicts).
2. **Probe** — verify endpoints in `references/endpoints.md` are live (county servers go down; UG WyCo was 521 at origin on 2026-06-11 — recheck `landsweb.wycokck.org` and `maps.wycokck.org` before any Wyandotte reprice).
3. **Recover** — batch ArcGIS REST queries (`WHERE <pin-field> IN (...)`, chunks of ~75) or bulk CAMA downloads per endpoints reference. Parallelize counties across subagents for large scopes. Write incremental CSVs (resumable): `sf_<Metro>_<County>.csv`, `values_<Metro>_<County>.csv` with columns `parcel_id` (EXACT input format), `bldg_sf`, `yr_built`, `land_use`, `mkt_lnd`, `mkt_imp`, `mkt_total`, `delq_taxes`, `method`, `source_url`.
4. **Sanity** — modeled $/SF medians must land ~$25–45/SF for shallow-bay in ORA markets. Median ~$10–15 ⇒ fractional assessed value (apply statutory ratio: MO commercial /0.32, KS commercial /0.25, OH values are 100% market). Document `value_basis` per county.
5. **Recompute P1** (constants per Buy Box & Scorecard v1.0, calibrated 2026-06-09):
   - NOI = SF × rent × 0.95 × 0.96 − 0.15 × SF (placeholder rent grid until rent-comp P2)
   - Walk = NOI / 0.08 · YoC = NOI / modeled
   - Vintage floor = 0.25 if yr ≥ 2000 else 0.30 · Disc = 1 − (modeled/SF)/RCT_LOW
   - Basis/25 = clip((Disc − floor)/(0.55 − floor) × 25) · Yield/20 = clip((YoC − 0.08)/0.03 × 20)
   - Motiv/10 additive: estate +5, delinquency +4 (delq > $1,000), in-motion +3, absentee +2, non-arms +1, hold ≥ 15y +1, cap 10
   - VA/6: +2 if land SF / bldg SF ≥ 2.5 (only when acres present) · Mkt/12 per metro baseline
   - Gates: SF > 50K KILL (note aggregate-SF caveat for footprint sums) · modeled < $400K or > $12M KILL · MaxP/Modeled < 0.60 KILL basis-improbable; 0.60–1.0 CLEAR-AT-DISCOUNT; ≥ 1.0 CLEAR
   - RCT LOW: Columbus 124.86 · KC 117.80 · Cincinnati 121.61 (= Columbus × 0.974, RSMeans CCI Cin 89.9/Col 92.3) · Baltimore 150.45 · Madison 124.27 · GR 109.15 · Richmond 119.56 · DSM 117.80 (KC proxy) — always cite RCT version; replace [est] rows when RCT updates.
6. **Rebuild** — regenerate master with provenance columns (`SF Source`, `Value Source`, `Delq Taxes`, `P1 Note`), re-rank Top 100 across metros (T2-QUEUE only, stale-value rows excluded), update Summary verdict counts, append README + QC provenance rows.
7. **QC gate** (all must pass before delivery): row counts preserved per tab; zero shipped-SF overwrites; Exclusions parcels absent from all tabs; Top 100 all-T2/no-stale/sorted; spot-check Basis/Yield/NOI math on ≥3 rows per metro; $/SF medians in range; delq Motiv within 0–10.
8. **Deliver** — present workbook; mirror to SharePoint `Investment Candidates -- 2026` when write access exists; route summaries to ggoldberg@oxfordra.net ONLY (routing canon 2026-06-10).

## Known scope gaps (next passes)

- Indianapolis (Marion/Hendricks/Boone/Hamilton-IN/Johnson) and Madison NO-SF rows — endpoints not yet researched.
- Wyandotte reprice blocked on UG origin outage (2019 values in use, tagged).
- Jackson MO yr-built effectively unpublished for commercial (13/1,807).
- Hamilton CAGIS footprint YEAR_BUILT unpopulated; vintage floor defaults to 0.30.
