# county-parcel-screen — archived changelog, v1.0–v1.3

Moved out of `SKILL.md` on 2026-09-22 (body split). Provenance only — every operative rule is restated in the skill body, which is authoritative. Newest first.

- **v1.3 (2026-09-18):** Deepened the long-hold ownership-tenure signal — chosen as
  ORA's best FREE motivation proxy after mortgage-maturity mining was ruled out as
  paid-data-only the same day (memory:
  `reference_mortgage_maturity_signal_not_bulk_accessible_2026-09-18.md`).
  **UNLIKE v1.2, THIS MOVES SCORES.** Four changes. **(1) Hold is now a graduated
  curve**, `20 x (1-e^(-(y-2)/8)) / (1-e^(-4.5))`, 0 below 2 yrs, capped at 20 from
  38 yrs — tau = 8 yrs (the shallow-bay hold/refi cycle), normalised to reach 20.0
  at 38 yrs, one year inside the **39-year commercial straight-line depreciation
  life**. That anchor is the non-hand-waving answer to why D&A Berwick's 38-year
  hold is near-maximal: basis decay, depreciation exhaustion and owner life-cycle
  have all run to completion, so a 45-year hold carries no more information.
  Marginal signal 5->15 yrs = +9.9 pts vs 25->35 yrs = +0.8 pts (~12x), and the
  2-point cliff at the old 24/25-yr bucket boundary is gone. **(2) The 16-point
  UNKNOWN-HOLD default is RETIRED** — it silently asserted a ~14.6-yr hold on rows
  with no hold evidence, and carried 80% of the Howard MD and 100% of the Jackson
  MO lists. Replaced by a coverage test: <=20% unknown -> score those rows 0, flag
  `HOLD-UNKNOWN`, carry a `Hold ceiling` (= score + 20) column, never rescale;
  >20% -> drop the component list-wide and tier on percentages of the achievable
  maximum. Jackson's treatment is revised accordingly from 0-80/achievable-76 to
  **0-60/achievable-60** (A >=54.0 · B 51.0-53.9 · C 42.0-50.9 · D <42.0) — the old
  flat 16 was a constant offset that added no discrimination but inflated every
  score. Also added: a nominal latest transfer now falls back to the PRIOR
  arms-length transfer (`HOLD-PRE-NOMINAL`) instead of going straight to unknown.
  **(3) Sibling-parcel consolidation (closes F6)**, flagged unresolved by all three
  2026-09-18 runs. Parcels are scored individually and never dropped, then grouped
  into RELATIONSHIPS by normalised owner name + normalised mail street/ZIP5, or by
  shared deed reference with agreeing addresses; same-address/different-name and
  same-deed/different-address cases are FLAGGED `RELATIONSHIP-CANDIDATE`, never
  auto-merged; members must be within 0.5 mi or contiguous. Roll-up carries combined
  SF (NOT re-gated against the 10-80K per-building gate), max member tenure, and
  member count. The `multi` component is regraded 0/2/3/4/5 on relationship
  membership rather than a flat 5 for any multi-parcel county owner. Documented FP
  risks (common LLC names, agent mailing addresses, stale blanket deeds, land
  condos, name-stripped MD counties) and FN risks (generational deed resets — the
  most damaging — alias drift, per-parcel SPEs, counties publishing neither deed nor
  mail address). **Consolidation changes the UNIT of the list, not the scores; a run
  reporting higher scores after consolidating has a bug.** **(4) New
  hold-data-availability table by ORA market** — Ohio's rich transfer history does
  not generalise and neither does Missouri's total absence. Verified absent: Warren
  OH, Jackson/Clay MO, Wyandotte KS, Hanover VA, suburban Dane WI. Date-free proxy
  only: Kent MI (Proposal-A `TaxableValue`/`SEVValue` uncapping gap — a magnitude,
  not a date). Year-granularity only: Dallas IA. Unknown/never established: Platte
  MO, Johnson KS, Jefferson KY (Louisville was never screened). Best in class: Polk
  IA. **Indianapolis is the highest-value open gap** — a disclosure state whose v01
  run clearly reached transfer dates, but `county-endpoints.md` carries no
  Indianapolis section at all; re-derive before relying on it.
  **MARYLAND HOLD GAP CLOSED — it was a run defect, not a data gap.** The Howard run
  reported 16 of 20 rows UNKNOWN-HOLD and concluded the statewide layer "publishes no
  transfer date at all", routing the fix to deed-by-deed mdlandrec work. Re-queried
  live: `TRADATE` is populated on **708 of 786** Howard `LU='I'` parcels (90.1%) and
  **255 of 279** in the 10-80K SF band (91.4%), with `CONSIDR1`, `CONVEY1` and
  `DR1LIBER`/`DR1FOLIO` alongside; a 40-row sample returned 38. The trap is that
  `SDATDATE`/`MDPVDATE` are extract VINTAGE stamps and `LASTASSD` is the assessment
  cycle — none is the transfer date — and that MD `LU` is alphabetic, so an
  Ohio-reflex `LU LIKE '4%'` filter returns zero rows silently. The field was already
  documented in the Anne Arundel entry ("same field set"). `county-endpoints.md` now
  carries the MD hold recipe (arms-length gate on `CONVEY1`, walk back through the
  Socrata `ed4q-f8tm` three sale segments + grantor names when segment 1 is nominal),
  the better Harford (`TRANS_DATE`, 100%) and Anne Arundel (`ASST_TRANSFER_DATE`,
  95.4%) county layers, statewide population by jurisdiction, and a
  do-not-re-investigate note that mdlandrec (registration-gated, manual, no API) and
  free bulk transfer/recordation-tax rolls (nonexistent) are both moot.
  **Franklin re-score (175 rows, on-disk v02 data, no county re-query):** mean delta
  **-4.1** (106 down / 46 up / 23 unchanged); tiers A 38->28, B 32->23, C 79->71,
  D 26->53, 59 rows change tier. **The movement is almost entirely the retired
  UNKNOWN-HOLD default, not the curve** — 34 rows (19.4%) lose 16 points; the curve
  alone moves rows by <=3. **D&A Berwick behaves exactly as designed: both parcels
  hold 100.0 and rise to ranks 1-2 (from 1 and 3), consolidating into ONE
  relationship — 2 parcels, 46,000 SF, 38 yrs.** 13 clusters cover 33 rows, so the
  list collapses from 175 parcel rows to **155 conversations**. The largest
  relationship found is AIRPORT PLAZA LTD at **4 parcels / 119,640 SF**, previously
  scattered across two sheets. `BERWICK CENTRE DEVELOPMENT CO` was correctly NOT
  merged with D&A Berwick (different mail address) — the conjunctive rule working.
  Top-5 reshuffle: Modern Builders 4->3, BSC Columbus 10->5, Airport Plaza 2->4 and
  FRG-X-DMD-OH 5->7 (both lose `multi` points as single-parcel members of their
  clusters). **Watch item: Franklin sits at 19.4% UNKNOWN-HOLD, one row short of
  flipping to the >20% drop-the-component branch** — a genuinely fragile boundary on
  this data set; re-check it every run rather than assuming the branch. Expected
  qualitatively if the other two are re-run, NOT re-run live here: **Howard MD**
  changes most — 16 UNKNOWN-HOLD rows become real tenures off `TRADATE`, the run
  leaves the >20% branch entirely and returns to a full 0-100 scale, Rumsey Road's
  three parcels (120,060 SF, one liber) merge into one relationship, and the
  long-hold rows the summary could only infer from deed vintage (Standard Court
  /05290, Rumsey /06228) should score their way up rather than needing a manual
  call-order override. **Jackson MO** changes least in ranking and most in
  presentation: no transfer date exists at any price, so it stays on the dropped-hold
  branch, but the scale becomes 0-60 with tiers on the achievable maximum, and
  Deevic's four contiguous parcels plus Monopoly's adjacent holding collapse the
  seven-name list to roughly four conversations as its own summary predicted.
- **v1.2 (2026-09-18):** Findings from three same-day adjacent-parcel ring screens
  (Franklin OH pilot, Howard MD, Jackson MO). **No scored constant changed** — the
  component weights, basis bands, UNKNOWN-HOLD 16, SF gate, value band and tier
  cutoffs are all as previously ratified; this pins the previously-unpublished
  SUB-BANDS within each component so runs are reproducible, and documents the two
  missing-component rescales those runs had to invent (Howard: entity-owner
  uncomputable → 0-90 ×100/90; Jackson: non-disclosure state → basis dropped, 0-80
  scale, tiers as percentages of the achievable 76). Sub-bands were pinned FROM the
  Franklin pilot run and are Gabriel's to amend; divergent runs must say so.
  **Counterparty floor is now FAIL-LOUD.** The guard file
  `data/pipeline-guard.local.json` is untracked/gitignored and exists in exactly one
  place (`~/.claude/skills/county-parcel-screen/data/`), so every consumer's old
  `__file__`-relative path resolved to nothing when the skill ran from the repo
  checkout or the AppData plugin bundle — and degraded to an ORA-self-only floor with
  a warning nobody acted on. The Jackson MO run shipped a call list screened that way;
  the Howard run loaded the file explicitly and recorded the near-miss.
  `institutional_owners.py` and `test-pipeline-match.mjs` now load the CANONICAL
  ABSOLUTE PATH (`ORA_PIPELINE_GUARD` overrides) and raise / exit-1 rather than
  degrade; `parcel-screen-fanout.js` receives the floor from its caller and now THROWS
  when it is absent — or when it is the old ORA-self pair — instead of warning. The
  guard is validated on BOTH `never_call_names` and `never_call_patterns` in
  `institutional_owners.py` (the two are different lists screened on different paths;
  the `.mjs` and the workflow screen on names only, and validate that). Every
  deliverable must record the guard's path, UTC mtime and both counts
  (`guard_evidence()`).
  `test-pipeline-match.mjs` gains a regression that fails if the removed ORA-self
  fallback returns, and no longer passes by skipping its deal cases when the guard is
  missing — the state in which the floor is actually broken. Two endpoint corrections in
  `county-endpoints.md`: Franklin `IsValid` is NOT usable as an arms-length gate (reads
  'F' on real deeds — use the $25K nominal rule), and Jackson's geometry layer
  (`ParcelsAscendRelate/FeatureServer/1`) can return 999 rows on a 1,000-row page while
  still setting `exceededTransferLimit=true`, so page on the flag, not the row count
  (a short-page loop silently truncated 2,999 of 4,666). The Jackson paging quirk is
  mirrored into `county-endpoints.v1.json`; the Franklin `IsValid` correction is not,
  because that derived index carries no deed/transfer fields. Still open, unchanged:
  the replacement-cost benchmark conflict (SKILL.md ~$150/SF vs ora-am-brief
  ~$85-120/SF vs RCT v03 KC LOW) and the F8 institutional aliases.
- **v1.1 (2026-07-19):** Added references/county-endpoints.v1.json (schema_version
  1.0) - live-verified (real `?f=json` requests, not re-cited from memory) against
  all 22 counties already documented in county-endpoints.md. 19 VERIFIED, 2
  VERIFIED-PARTIAL (Clay MO, Platte MO - geometry live but attribute-thin, matches
  existing doc), 2 NOT-FOUND (Johnson KS paid-gate, Polk IA has no ArcGIS REST
  parcel layer - CSV export only). Caught and corrected two live drifts since the
  2026-06-09/11 source-doc runs: Dane County WI's statewide parcel service was
  renamed (`Wisconsin_Statewide_Parcels` -> `Wisconsin_Statewide_Parcels_DB`, layer
  rolled to the 2026 vintage) - fixed in county-endpoints.md same pass; Kent County
  MI's primary Hosted/ParcelsWithCondos layer now requires a token (was public
  2026-06-09) - registry points to the still-public OpenData mirror instead, flagged
  for periodic re-check. Also resolved two URLs county-endpoints.md had left
  truncated: Baltimore County MD's own polygon+owner-name GIS layer, and Richmond
  City VA's parcel layer (`services1.arcgis.com`, not bare `services.arcgis.com`,
  which 400s). Built to satisfy ora-flood-zoning-dd v1.2's Step 1 cross-link
  (parcel-geometry lookup for the pad/yard flood split).
- **v1.0:** initial - validated Franklin (Columbus) + Hamilton/Butler/Clermont/
  Warren (Cincinnati), June 2026.
