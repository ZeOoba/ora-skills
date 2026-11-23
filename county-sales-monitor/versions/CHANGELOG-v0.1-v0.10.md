# county-sales-monitor changelog archive, v0.1 to v0.10

Full-text entries rolled off the inline Changelog under the 6-entry retention rule (2026-11-23, Automation Audit R34-5), copied verbatim, newest first.

- **v0.10 (2026-10-30):** Cook IL promoted to Tier A (Worker adapter
  `src/counties/cook.ts`, `ZeOoba/ora-county-sales-monitor` PR #7). Indiana's
  statewide SDF file verified as a partial-price source (Tier B entry above;
  adapter planned). Cook multi-PIN deeds group on the published `doc_no`; SF is summed per
  valuation group only when every group lies wholly inside the deed, otherwise
  unknown with the cap still applied. Takes effect on the Worker's next
  supervised deploy. No change to scored or governor constants.
- v0.9.1 (2026-10-29): Spelled out the cross-skill path of `dl_resume.py`. This was a reference-path clarification only (wording; no change to procedures, scored or governor constants): NO change to scored or governor constants.
- **v0.9 (2026-10-15):**
  Closes the open Worker defect recorded in v0.8. Step 3's government/exempt
  exclusion was implemented for Baltimore (`EXCLASS`) and Polk (DOR quality) but
  not for Franklin, whose parcel layer carries no exempt field (`EXPLUC` empty on
  all 219 industrial-class parcels sold since 2025-10-02; `TOTVALUEEXP` reflects partial exemptions; `PCLASS` is
  "I" throughout). The fix is a current-owner (buyer) name test in the Worker's
  Franklin adapter (`ZeOoba/ora-county-sales-monitor` PR #5, commit `fe32c9f`,
  merged to `main` as `32abe0b`; `src/counties/exempt.ts`). Decisions (Gabriel,
  2026-10-15): (A) scope is government plus PUBLIC institutions (state, city, county, authorities, public
  colleges and schools); churches, other nonprofits and private institutions are
  KEPT, so this is narrower than Polk's "Government or Exempt" class, which also
  removed a church and a nonprofit; (B) rows already written are left in place,
  not deleted; (C) a numbered deed with any government parcel is dropped whole.
  Seller is never tested (Franklin Seller is inferred, and an inferred seller
  never drives a flag). The filter runs after deed enrichment so exclusions cannot
  trip the degraded-pull WARN, and an excluded sale is never reported as a
  dropped group, so `planRegroup` cannot retire its existing rows. Coverage Notes
  gain the line `N government/public-institution sale(s) excluded.` No change to
  `rules.ts`, the schema, county labels or the key format. Pre-deploy evidence:
  typecheck, lint and 57 of 57 tests clean; a read-only live pull of the Franklin
  layer (window start 2025-10-15) went from 208 raw to 204 kept with 4 sales
  excluded; the name test run on 91 distinct live Franklin owner names flagged 21,
  all public bodies, and kept private owners such as OHIOHEALTH CORPORATION and
  OHIO POWER COMPANY. The `simulate` comps cycle moved Franklin from 164 to 160
  rows and the harness's own median from USD 117.77 to USD 113.14 (Columbus State
  Community College, USD 236.05/SF, was the only excluded sale with a $/SF; see the
  post-deploy note below for the Coverage-basis figures). **Orphaned rows:** the four existing
  Franklin comps below were written before the filter and are now excluded, so
  they stay in the Comps DB with a frozen `Last Synced` and no longer update.
  Treat them as excluded when reading the database; do not count them toward
  Franklin medians or volumes:
  `Franklin|130-011588|2026-02-09|0` (State of Ohio),
  `Franklin|520-165723|2026-05-19|0` (City of Columbus),
  `Franklin|010-282683|2026-01-29|0` (Columbus Regional Airport Authority),
  `Franklin|010-005337|2025-12-23|1950000` (Columbus State Community College,
  the only one with a $/SF). Known limits (best effort, also in the Worker
  README): a public body whose name contains a church-type word is kept; a
  public body ending in the abbreviation "CO" is missed; a private college is
  not recognised as public; a suffix-less private name that reads like a public
  body (for example "STATE OF THE ART STORAGE") would be dropped. Known
  unrelated issues: the Worker's `npm run simulate` fails a date-dependent
  assertion in its own harness (`test/simulate.ts:73`), identically on unmodified
  `main`; and GitHub Actions jobs die in about 3 seconds with no logs on every
  run in both the Worker repo and ora-skills, so CI status is not evidence about
  these changes. **Deployed 2026-10-15** from `main` at `32abe0b` with no schema
  change; the existing Worker was updated, not duplicated (the same two managed
  databases received the new cycle; no new databases appeared). **First
  post-deploy cycle, run date 2026-10-15 (window start 2025-10-15), read from
  Notion:** the Franklin Coverage row is OK and its Notes read "4
  government/public-institution sale(s) excluded", as predicted. Franklin
  Transactions 160 (167 on 2026-10-10), clean $/SF rows 40, NONARMS rows 90,
  median USD 100.68. That median reproduces exactly from the Comps DB: the 40 clean
  rows have a median of (100.64 + 100.71) / 2. The filter's own effect on it is
  about USD 0.04 (removing the USD 236.05/SF college row moves the median from 100.71
  to 100.68), so the filter is not what moved it from USD 117.77 on 2026-10-10. That
  fall coincides with the window rolling forward five days and new sales posting
  (the Comps DB now holds a USD 35.73/SF sale dated 2026-10-09), on a distribution
  with a gap around the middle (100.71, 113.14, 117.77), where a few rows
  crossing the window edge move the median this far; the exact rows that left the
  window were not diffed. The `simulate` figures above (a USD 113.14
  median) are on the harness basis, which includes RATIO-REVIEW rows and takes
  the upper middle value, so they do not compare to the Coverage median. Comps DB
  after the cycle: Franklin 172 rows / 172 distinct Comp Keys (160 upserted this
  cycle, equal to the Coverage Transactions), Polk 64 / 64, Baltimore Co 38 / 38;
  0 duplicate Comp Keys; 0 LATE-POSTED; `Price PSF` never 0 and blank on every
  NONARMS, CONTRACT-SALE and SF-INCOMPLETE row. The four orphaned keys above are
  present and unchanged (Last Synced 2026-10-10, same flags, the college row
  still carrying its USD 236.05/SF).
- **v0.8 (2026-10-15):** Post-deploy verification of the Worker databases and a
  fresh parity run against the legacy pilot (read-only; no Worker or database
  change). Worker DB state 2026-10-15: 273 comps (Franklin 171 / Baltimore Co 38
  / Polk 64), 273 distinct Comp Keys, 0 duplicates, `Price PSF` never 0 and blank
  on all 147 NONARMS / CONTRACT-SALE / SF-INCOMPLETE rows, 0 LATE-POSTED; Coverage
  holds 7 rows per cycle (cycles 2026-10-02, 10-03, 10-10). Parity, window
  2025-10-01 to 2026-08-15, strict County+Parcel+Date+Price: 189 matched of 258
  legacy rows; 227 equivalent at transaction level. Strict misses are 17 Baltimore
  Co rows with a NULL price in both databases (SQL NULL never equals NULL; 38 of
  38 match once NULL-safe), 14 Polk rows where the legacy ID is the 14-digit `dp`
  and the Worker lists the member `gp` PINs, and 7 Franklin legacy rows vs 14
  Worker rows from multi-parcel deed granularity (priced deeds roll up in the
  Worker; USD 0 NONARMS deeds emit one row per parcel and now carry SF). The 31
  remaining legacy-only rows resolve to: 20 with SF >= 150K (Worker SF gate), 2
  Franklin deeds legacy marked SF-UNPUBLISHED that are over the cap (USD 15.4M
  Action Group parcel 010-000782 at 153,412 SF; USD 137.8M NLF Columbus parcel
  495-286103 at 1,600,052 SF), 3 Franklin sales dated 2025-10-01 before the
  Worker's first window start, 4 Franklin parcels (Westerville Rd, USD 0 on
  2026-07-29) whose GIS `SALEDATE` was overwritten by a 2026-08-18 USD 13,005,000
  resale (G7, verified against the live layer), and 2 Polk sales whose DOR
  `quality` is "Government or Exempt" (a church and a nonprofit; verified in the
  live CSV), which the Worker excludes by design. This closes the "1 Polk
  unexplained" row in v0.6. The Coverage `Transactions` count runs below the
  Comps row count by design: the Comps DB never deletes, so rows whose sale date
  has aged past the rolling 365-day window stay (10-10: 167 / 37 / 62 vs 171 /
  38 / 64; 4 / 1 / 2 rows dated before 2025-10-10). **Open defect (Worker, not
  fixed here):** Step 3's government/exempt exclusion is implemented for Baltimore
  (`EXCLASS`) and Polk (DOR quality) but NOT for Franklin; two USD 0 NONARMS rows
  with government buyers (State of Ohio, City of Columbus) are in the Franklin
  set. Ruled a Worker defect by Gabriel 2026-10-15; fix is a Worker change
  (src/counties/franklin.ts) and needs a separate approved redeploy.
- **v0.7 (2026-10-02):** Worker follow-ups ratified by Gabriel the same day.
  (1) `RATIO-REVIEW` splits ratio-only trips out of `NONARMS` (Franklin 20 rows,
  Baltimore Co 1, Polk 0 on the first run; coverage medians unchanged by design).
  (2) Franklin Transfer ingest adds Convey Number, Instrument Type, deed-published
  parcel counts and an inferred, labelled prior-owner Seller; deed-numbered groups
  replace the buyer-name inference. First deployed cycle: Franklin 173 -> 169 rows
  (5 superseded rows deleted, 1 regrouped row added; 3 of the 5 are large groups
  now correctly over the 150K SF cap: a USD 117M Parsons Ave foundry, a USD 137.7M Shook
  Rd group, a USD 15.4M Reynoldsburg-New Albany group, each with a single parcel above
  the cap on its own), Baltimore 38 and Polk 64 unchanged, 194 of 215 sales
  matched (199 before the same-day-deed ambiguity rule withheld 5; the other 16
  unmatched are all dated after the 09-15 drop). Adversarial review took three
  rounds; defects found and fixed before deploy: orphaned group keys, false
  LATE-POSTED on regroup, doubled $/SF on a deed member left without a number,
  deletes sent ahead of their replacement rows, SF cap bypass through the
  multi-parcel guard. New failure modes G11, G12. Seller inferred rule left OFF
  for the shared-stem test (Gabriel, 2026-10-02). IsValid remains unusable. Open:
  per-county ratio bands; two priced in-window Franklin sales hidden by the GIS
  last-sale field (G7) are findable via the transfer history if recovery is wanted.
- **v0.6 (2026-10-02):** Pull, filter and format now run as a hosted Notion
  Worker (`@notionhq/workers` locked at 0.9.2; two weekly incremental syncs; Tier A comps only;
  no secrets). First cycle 2026-10-02: 275 comps (Franklin 173 / Baltimore Co 38
  / Polk 64), 275 distinct keys, 0 LATE-POSTED (baseline cycle), `Price PSF`
  blank on every NONARMS / CONTRACT-SALE / SF-INCOMPLETE row and never 0;
  coverage database 7 rows. Clean $/SF medians (coverage rows): Franklin
  USD 115.46, Baltimore Co USD 155.68, Polk USD 120.08. Parity vs the legacy pilot
  (strict County+Parcel+Date+Price, 2025-10-01 to 2026-08-15; the worker's own
  window starts 2025-10-02): 207 matched (Franklin 119 / Baltimore 38 / Polk
  50); 51 legacy-only, 32 new-only. Legacy-only causes: multi-parcel
  representation 23 (incl. 3 Franklin parcels the worker rolls into one
  MULTI-PARCEL-INFERRED row), Franklin rows with SF >= 150K that the legacy
  kept and the worker's SF gate drops 20, window edge 3, other 5 (4 Franklin
  last-sale-only `SALEDATE` overwrites, G7; 1 Polk unexplained). Use-code lists and the 25D / 46A Polk
  exclusions are unchanged from v0.5; the flag set (adds SF-INCOMPLETE and
  MULTI-PARCEL-INFERRED), PSF blanking on SF-INCOMPLETE, the 365-day re-pull
  and the First-Seen-based LATE-POSTED rule differ from the v0.5 manual
  workflow. Polk sales export observation: see `county-endpoints.md`.
- **v0.5 (2026-08-15):** Post-pilot QC pass on the live Notion data (304 rows
  queried directly, not just re-read from agent reports) confirmed row counts
  and key-uniqueness clean, but surfaced one real finding the original pilot
  reports missed: Baltimore Co MD's TRADATE field runs ~4+ months behind
  (clean taper Feb-Apr 2026, zero May-Aug despite the window running current)
  — worse than Franklin's known ~1-month lag. Documented in the Tier A
  coverage note and carved out of Step 8's coverage-regression check so the
  monthly scheduled task doesn't misread expected Baltimore Co quiet months
  as a finding. Same fact added to county-parcel-screen's `county-endpoints.md`.
- **v0.4 (2026-08-15):** First live pilot run executed — all three Tier A
  counties, 12-month window (2025-08-15 to 2026-08-15), 304 transactions
  written to the Notion database (Franklin OH 179, Polk IA 80, Baltimore Co
  MD 45). No endpoint drift on any documented field, but all three counties
  surfaced real gaps in county-parcel-screen's `county-endpoints.md` that this
  skill's agents correctly did NOT patch themselves (per instruction): Franklin's
  GIS `VALID` field is null-populated and useless (its transfer file's `IsValid`
  works instead); Polk's `quality` DOR validity column was undocumented;
  Baltimore's `CONVEY1=4` conveyance code (driving ~half its "transfers") is
  undocumented anywhere public. Franklin's NONARMS rate (81.6%) ran well above
  the ~40% Ohio baseline — partly real, partly the documented G8 stale-assessment
  failure mode tripping the ratio test on genuine high-value 2025-26 sales.
  Per-county medians: Franklin USD 120.27/SF (n=25), Baltimore Co USD 152.51/SF
  (n=18), Polk USD 105.04/SF (n=43) — not blended into a portfolio figure, the
  three markets aren't comparable on one number. Franklin also found its bulk
  transfer file lags the live GIS layer by ~1 month (25 of 179 rows had no
  transfer-file match yet, Seller reported "not published" rather than guessed).
  No scheduled task registered — still a separate future step.
- **v0.3 (2026-08-15):** Gabriel ratified the remaining four open questions:
  Notion database nests under Knowledge Base `3386ecd8` (not standalone);
  first-run lookback is 12 months for all three Tier A counties; comps stay
  Notion-only for now (no auto-flow into `markets.md`); next step is building
  the Tier A pilot directly, not a skill-creator eval loop. KC cluster
  handling remains deferred (genuinely not urgent — out of scope until Tier B
  expansion). Nothing left blocking the pilot build.
- **v0.2 (2026-08-15):** Gabriel ratified four scope decisions: monthly
  cadence (not weekly), Notion database as the delivery surface (not a
  workbook), Tier A pilot only at launch (Franklin OH / Baltimore Co MD /
  Polk IA — Tier B expansion is a distinct later pass), and Louisville /
  Jefferson Co KY deferred until after the nine existing clusters ship.
  Sections updated throughout to match.
- **v0.1 (2026-08-15):** Initial DRAFT for Gabriel's review. Specification only —
  no pilot run, no scheduled task, no scripts, no evals. Coverage tiers derived
  from county-parcel-screen `market-status.md` + `county-endpoints.md` as of the
  2026-07-24 revision; Tier B counties are documented-but-unexercised for a
  windowed sales pull.
