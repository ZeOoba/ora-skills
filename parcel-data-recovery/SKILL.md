---
name: parcel-data-recovery
description: County-level building SF, market value, year-built, and tax-delinquency recovery for Oxford Realty Advisors off-market parcel screens. Use when the user mentions: recover SF, missing building SF, parcel data gap, UNSCREENABLE rows, DATA-GAP rows, county GIS pull, footprint SF, assessor values, CAMA extract, refresh parcel data, re-run P1 on recovered data, off-market master rebuild, or when an off-market screen workbook has rows lacking Bldg SF or auditor values. Encodes verified endpoints (2026-06-11) for Jackson MO, Wyandotte KS, Clay MO, Hamilton/Butler/Clermont/Warren OH, footprint-vs-GBA rules, value-basis conversions (calibrated per-county, never assumed — Iron rule 10), P1 Buy Box recompute math, and the v03/v04 QC gate. v1.4 (2026-07-12)
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
7. **Assert SF meaning before use.** Any field feeding building SF must be proven to be BUILDING area, not land. Field labels lie (confirmed cases: Franklin OH `STATEDAREA` = sq ft despite an alias of "Legal Acres"; Jackson MO `total_sqft` = land; Marion IN `ESTSQFT` = lot). A SF field that ≈ parcel land area, or that equals the screen's own land column, is land — reject it.
8. **WAF-blocked exact-match filters — fall back client-side.** Some county ArcGIS/CAMA endpoints reject or silently empty-return `WHERE <field>=<value>` queries (WAF strips or 403s the `=` operator) while `IN (...)`, wildcard/`LIKE`, or an unfiltered paginated pull succeed against the same data. A zero-row or error response to an `=` filter against an endpoint known to hold the record is NOT proof of absence. On empty/error: retry as `IN ('value')`; if that also fails, pull the full/paginated table unfiltered and filter client-side post-fetch. Never record a parcel as unrecoverable off an `=`-filtered 403 alone.
9. **Multi-row owner/deed records — key on type, not order.** Deed and Mail-To tables frequently return >1 row per `parcel_id` (joint owners, trustee + trust, prior + current owner, deed history). Taking the first matching row is an arbitrary pick, not a resolved owner. Resolve on an explicit type/role/status field (`OwnerType`, `IsCurrent`, `Primary`, most-recent `DeedDate`) instead. If no such field exists in the source table, the parcel is NOT auto-resolvable — quarantine it (`NO-OWNER(ambiguous)`) for manual resolution rather than guessing.
10. **Assessed→Modeled-Market conversion is calibrated, never assumed (added v1.4, 2026-07-12).** A recovered value field's basis relative to true market value is NOT self-evident from a field name or a general statutory rule, even one already relied on elsewhere in this skill (MO commercial /0.32, KS commercial /0.25, "OH auditor values = 100% market"). Those defaults hold at the *state* level in aggregate but are not guaranteed at the *county* level once a county's recovery method changes (e.g., a different CAMA export, a redacted public-view service, an undocumented secondary values layer). Precedent: Clermont and Warren OH (2026-07-12) — 736 rows had real recovered SF and a real recovered value field, but no county-specific test confirmed that field was already at parity with true market value; Hamilton/Butler OH's own ratios did not hold as a clean fixed multiplier row-to-row, ruling out a blind carry-over of the "100% market" default to the two new counties. Ratified resolution (Gabriel, 2026-07-12): pull a **~15-20 parcel sale-comp sample per county** and derive a **county-specific calibration ratio** (sale price ÷ recovered value field, median across the sample) before scoring or promoting that county's rows. Do NOT: (a) apply a statutory or "another county's" ratio uncalibrated, or (b) leave the rows in permanent DATA-GAP with no plan — either is a unilateral valuation call this skill does not have standing to make. If a comp-sample pull cannot be completed in the current pass, tag the county `DATA-GAP: methodology decided, calibration pending` (not `KILL`, not shipped, not silently reverted to a blind ratio) and name the row count blocked, so the gap has a visible size and owner rather than sitting open indefinitely.

## Workflow

1. **Scope** — identify counties with `Bldg SF` and/or value blanks in the master (UNSCREENABLE / DATA-GAP verdicts).
2. **Probe** — verify endpoints in `references/endpoints.md` are live (county servers go down; UG WyCo was 521 at origin on 2026-06-11 — recheck `landsweb.wycokck.org` and `maps.wycokck.org` before any Wyandotte reprice). Confirm whether the endpoint accepts `=` filters before relying on empty results (Iron rule 8); note `IN`-only endpoints in `references/endpoints.md`.
3. **Recover** — batch ArcGIS REST queries (`WHERE <pin-field> IN (...)`, chunks of ~75) or bulk CAMA downloads per endpoints reference. Parallelize counties across subagents for large scopes. Write incremental CSVs (resumable): `sf_<Metro>_<County>.csv`, `values_<Metro>_<County>.csv` with columns `parcel_id` (EXACT input format), `bldg_sf`, `yr_built`, `land_use`, `mkt_lnd`, `mkt_imp`, `mkt_total`, `delq_taxes`, `method`, `source_url`.
4. **Sanity** — modeled $/SF medians must land ~$25–45/SF for shallow-bay in ORA markets. Median ~$10–15 ⇒ fractional assessed value; the MO /0.32, KS /0.25, and OH-100%-market defaults are STARTING hypotheses per Iron rule 10, not automatic conversions — confirm each county's basis against its own comp sample before applying, and never carry a ratio over from a different county on assumption alone. Document `value_basis` per county, including how it was confirmed (comp sample, statutory + spot-check, or "unconfirmed — DATA-GAP per Iron rule 10"). Run the unit-assertion gate below (workflow step 7). The $/SF and FAR medians are the same instrument pointed at value and at area — both must pass before recompute.
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

   **Unit-assertion gate** (run per county, before any FAR or economics ship):
   1. **bldg < land:** for ≥90% of rows, recovered `bldg_sf` < `land_sf`. A county where bldg ≥ land for a large share is using a land field as building SF — STOP, re-source.
   2. **Kill-gate consistency:** no parcel the screen KEPT may carry recovered "building SF" > 50,000 unless independently confirmed multi-building; >50K on a kept row is a land-field tell.
   3. **FAR-median band:** county median FAR must land ~0.10–0.50 (shallow-bay range). Median ≈ 1.0 ⇒ land-as-building (the Marion `ESTSQFT` signature); median < 0.03 ⇒ building-as-land or wrong join.
   4. **Source-field provenance:** every recovered SF carries the exact source field name + verified unit in its `method`/`source_url` tag (e.g. "FEMA SQFEET", "iasWorld AREA sum", "footprint Shape__Area sqft").
   5. **No reprojected areas:** take area from the authoritative source field; never recompute from Web Mercator geometry.

   Any sub-gate failure ⇒ that county's SF is quarantined (kept blank, tagged `NO-SF(recover)`), never shipped.

   **Filter/owner-resolution gate** (added v1.2, run alongside the unit-assertion gate):
   1. No row quarantined solely on an `=`-filter 403/empty-result without an `IN`/unfiltered retry per Iron rule 8.
   2. No owner/mail-to field populated from a multi-row match without an explicit type-field resolution (Iron rule 9); ambiguous multi-row parcels carry `NO-OWNER(ambiguous)`, never a silent first-match value.
8. **Deliver** — present workbook; mirror to SharePoint `Investment Candidates -- 2026` when write access exists; route summaries to ggoldberg@oxfordra.net ONLY (routing canon 2026-06-10).

## Known scope gaps (next passes)

- Madison/Dane WI NO-SF rows, Baltimore-MD SDAT name-recovery, Henrico mail addresses — endpoints not yet researched. Indianapolis metro endpoints added in v1.1 (`references/endpoints.md`); collar counties (Boone/Hendricks/Johnson) still need a Schneider/Beacon upgrade pass for true GBA beyond the FEMA-fallback vintage.
- Wyandotte reprice blocked on UG origin outage (2019 values in use, tagged).
- Jackson MO yr-built effectively unpublished for commercial (13/1,807).
- Hamilton CAGIS footprint YEAR_BUILT unpopulated; vintage floor defaults to 0.30.

## Changelog

- **v1.4 (2026-07-12):** Added Iron rule 10 — Assessed→Modeled-Market conversion is calibrated per-county via a sale-comp sample, never assumed from a statutory default or carried over from another county. Prompted by Clermont/Warren OH (736 rows): both had real recovered SF and value fields, but Hamilton/Butler's own ratios didn't hold as a clean fixed multiplier, ruling out a blind "OH = 100% market" carry-over. Gabriel ratified the calibration approach (~15-20 comp sample per county) over both a blind-ratio shortcut and permanent DATA-GAP exclusion. Workflow step 4 updated to treat the existing MO/KS/OH defaults as starting hypotheses requiring confirmation, not automatic conversions.
- **v1.3 (2026-07-12):** endpoints.md v3 — Hamilton OH CAGIS outage re-confirmed + OGRIP/FEMA bypass added; Chesterfield VA `ASSESSED` field root-caused (renamed to `TotalAssessment`, not removed) + live endpoint added; Des Moines/Dallas IA metro researched for the first time (Polk candidate endpoints identified, live-reachability pending off-sandbox retest; Dallas confirmed no bulk API). Also moved this changelog out of the frontmatter `description` field (which had drifted to 1,521 chars, exceeding the platform's 1,024-char limit and blocking `package_skills.py`) into this body section — no content removed, only relocated; frontmatter now carries a short version tag only, matching `register-scheduled-task`'s convention.
- **v1.2 (2026-07-12):** added Iron rules 8-9 — WAF-blocked `=`-filter client-side fallback, and explicit-type-field resolution for multi-row Deed/Mail-To or joint-owner records (no first-match).
- **v1.1 (2026-07-11):** merged 2026-06-16 unit-assertion QC gate (Iron rule 7) + endpoints v2 — fixes Jackson MO `total_sqft` land/building mislabel, adds FEMA USA Structures fallback + Indianapolis metro, documents Warren County OH multi-building scrape defect.
- **v1.0:** initial.
