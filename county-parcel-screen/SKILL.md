---
name: county-parcel-screen
description: >
  ORA county-parcel direct-to-owner acquisition screen. Pulls a county's industrial
  parcel universe from public auditor/assessor data, calibrates auditor values to
  market empirically, scores every parcel 0-100 against the ORA buy-box, mines
  delinquency / estate / seller-in-motion motivation signals, and delivers ranked
  call-list workbooks. Use this skill whenever the user mentions: parcel screen,
  county screen, off-market sourcing, direct-to-owner, owner outreach list, cold
  call list, delinquent tax leads, motivated sellers, estate owners, sellers in
  motion, county auditor data, assessor data, parcel data, or asks to find
  off-market industrial acquisition candidates in ANY target market (Columbus,
  Cincinnati, Kansas City, Indianapolis, Maryland, Madison, Grand Rapids,
  Richmond, Des Moines, or a new county). Also trigger for "next market",
  "run the screen on X", or any request to build owner-level lead lists from
  public property records. v1.2 — changelog in body.
---

# county-parcel-screen

Generate off-market industrial acquisition leads for Oxford Realty Advisors from
public county property data. The screen finds owners with the CAPACITY to sell at
ORA's basis-buyer price (low basis, long hold) and the MOTIVATION to do so
(delinquency, estate, liquidation-in-progress). Validated end-to-end on Columbus
and Cincinnati; per-county endpoints and quirks live in references/.

## Buy-box (apply unchanged unless user overrides)

Class B/C industrial / shallow-bay / flex / office-warehouse only. 10,000-80,000
SF building (sweet spot 15-50K). Deal $1-10M; equity sleeve $0.75-5M at 65% LTV.
Hard floors: >=25% discount to replacement (~$150/SF benchmark) AND >8% stabilized
YoC. Instant disqualifiers: retail/office/multifamily, auto-use tenancy,
institutional Class A pricing, outside ORA's nine clusters.

## Workflow

**Counterparty floor — FAIL-LOUD, no degraded fallback (hardened 2026-09-18):**

CANONICAL PATH — load the guard from this absolute path, always:

    C:\Users\Owner\.claude\skills\county-parcel-screen\data\pipeline-guard.local.json

(override only via the `ORA_PIPELINE_GUARD` env var). The file is UNTRACKED and
gitignored on purpose — counterparty names never live in tracked files — so it exists
in exactly ONE place on this machine. It is NOT in the `ora-skills` repo checkout and
NOT in the AppData plugin bundle. Every consumer's old `<skill>/../data/` RELATIVE path
therefore resolves to nothing whenever the skill executes from any copy other than
`~/.claude/skills/` — which is precisely how the 2026-09-18 Jackson MO run came to
screen against ORA-self patterns only. It did warn; the warning was not acted on and
the list shipped anyway (`…JacksonMO_Summary_v01.md`, honest-limits item on the
degraded floor). The same-day Howard MD run loaded the file explicitly and recorded
in its QC paragraph that "the module's own
relative path resolves into the plugin cache, where the file does not exist, and would
have degraded the floor silently."

Rules, in force for every run regardless of which copy of this skill is executing:
1. Load the guard from the CANONICAL ABSOLUTE PATH above — never from a path relative
   to the executing skill copy, and never from a bundled or cached duplicate.
2. Pass its `never_call_names` as `args.neverCallNames` to
   `workflows/parcel-screen-fanout.js` (optionally a full `args.pipelineGuard` to skip
   the Phase-0 Notion fetch).
3. **If the guard cannot be loaded, or loads with zero `never_call_names`, STOP.** Do
   not score, do not rank, do not produce a call list, a workbook or a summary. A
   degraded ORA-self-only floor is NO LONGER an allowed run mode — "no match" from a
   degraded screen is not the same as screened. Report the failure to Gabriel and stop.
4. **Record the guard as evidence in every deliverable.** The workbook README sheet and
   the run summary must each carry the guard file's absolute PATH, its filesystem
   MODIFIED TIME (UTC), and BOTH entry counts — `never_call_names` (what the workflow
   screens on) and `never_call_patterns` (what `institutional_owners.py` screens on).
   They are different lists; citing only one can look screened while the other is
   empty. `institutional_owners.guard_evidence()` returns exactly this dict.

### 1. Discover sources (skip for counties already in references/)
Find (a) an ArcGIS REST parcel layer with owner, site address, tax-mailing
address, land-use code, sale date/price, appraised values - verify field names
via <layer>?f=json and a count query; (b) bulk extracts (tax duplicate w/
delinquency, transfer history w/ owner names, building/appraisal cards, rental
contacts). Spawn a recon subagent per 2 counties when discovering new markets -
it saves main-context budget. Ohio counties all use DTE codes (industrial =
300-series); other states need the use-code scheme mapped first.

### 2. Pull the universe
Industrial use codes, paged queries via sandbox python urllib (web_fetch is
URL-length-capped - never rely on it for paged REST pulls). Building SF
10-80K where the layer has SF; otherwise improvement-value band $150K-$7M as
the size proxy and note the gap. Save raw JSON before processing.

### 3. Exclude
Government/exempt; institutional owners via scripts/institutional_owners.py -
the CANONICAL exclusion module (import screen_owner / screen_mail /
ora_never_call; run on BOTH owner fields AND mail fields). Doctrine:
'EXCLUDE' = drop; 'VERIFY' = keep + flag VERIFY-INSTITUTIONAL and adjudicate
before outreach - never silently drop on a weak token (the DUKE COMBINED
lesson), and never let fund-style names through (the G&I XI lesson; module
catches fund morphology generically). Append newly caught aliases to the
module's TIER1/TIER2 tables with a dated note. Also exclude: value band
outside ~$250K-$8.5M; never-call counterparties (ora_never_call 'NEVER-CALL'
tier = live/former deal counterparties — drop); parcels already in the ORA
pipeline (Notion Acquisition Pipeline bcfe4a03). ORA/affiliate matches
(ora_never_call 'ORA-SELF': Oxford*, Goldberg, FJ&S incl. FJS) are KEPT and
flagged ORA-AFFILIATED — NEVER dropped, per Gabriel 2026-06-10 (the Oxford
Campus I mail-name false positive proved silent drops unsafe). No outreach
to flagged rows without principal adjudication.

### 4. Calibrate empirically - never guess
Auditor-to-market factor = median SALEPRICE / appraised-value of in-universe
arm's-length sales (>=$100K, <=3yr, ratio 0.5-4). Ohio post-2023-reappraisal
runs ~1.6x (Franklin 1.65 n=57; Hamilton 1.61 n=182). Derive basis-score
thresholds FROM the factor: 20 pts = >=40% modeled discount to replacement;
14 = >=25% (the ORA floor); 6 = 10-25%; 0 below. Use ZIP-level ratios where
n>=3 per ZIP - they range 1.0-2.0 within one county.

### 5. Fix the hold score
40%+ of recent sale dates are $0/nominal transfers (re-titling, estate,
intra-family) - NOT purchases. Sub-$25K transfer = unknown-hold (16 pts +
NONARMS flag), never scored as a recent buyer. Owner name containing
TRUSTEE/ESTATE/EXECUTOR/SUCCESSOR, or TR + recent nominal transfer ->
ESTATE-SIGNAL: the single highest-priority call flag, because succession is
the one motivation that reliably overrides low-basis capital-gains lock-in.

### 6. Score 0-100
product 25 / size 15 / hold 20 / basis 20 / entity-owner 10 / absentee-mail 5 /
multi-parcel-owner 5. Tiers: A >=90 (call), B 85-89 (mail), C 70-84 (watch),
D (archive). When SF or values are unavailable, rescale honestly (e.g. 0-75
"pre-SF") and say so in the README sheet - never fake a component. The sub-bands
WITHIN each component are pinned below — use them, do not re-infer them.

## Scoring sub-bands (pinned 2026-09-18)

Until 2026-09-18 this skill published only the component WEIGHTS (plus the basis
bands and the 16-point UNKNOWN-HOLD value). On that day the Franklin OH pilot had to
infer the rest, and its choices became the de-facto spec that the same-day Howard MD
and Jackson MO runs then reproduced rather than re-derived. They are pinned here,
verbatim from that pilot's workbook README
(`2026-09-18_RingScreen-FranklinOH_CallList_v01.xlsx`, SCORING block) and its summary.

**These sub-bands were pinned FROM A RUN, not derived from first principles. They are
Gabriel's to amend.** Any run that diverges from them MUST say so on the face of its
summary and workbook README, with the reason — otherwise successive runs stop being
comparable, which is the failure these three runs hit.

**SF gate:** building SF 10,000-80,000. **Value band:** calibrated value ~$250K-$8.5M
(applied AFTER the SF gate). **Tier cutoffs:** A >=90 call | B 85-89 mail | C 70-84
watch | D archive.

- **product 25** — core shallow-bay/flex (DTE 330, 340-343, 350-354, 358, 370-372,
  391, 392) | **18** secondary (302, 310, 355-357, 360, 399) | **10** heavy (320
  foundries). A flagged EXTENSION universe outside the county's ratified industrial
  series (e.g. Franklin DTE 480, Jackson `landuse_cd` 2240/2241) scores **18**, on
  its own sheet.
- **size 15** for 15,000-50,000 SF (the stated buy-box sweet spot) | **10** for
  10,000-14,999 | **9** for 50,001-80,000.
- **hold 20** >=25 yrs | **18** 15-24 | **14** 10-14 | **10** 5-9 | **5** 2-4 |
  **0** <2 | **16** UNKNOWN-HOLD (skill-stated; see step 5's $25K nominal rule).
- **basis 20** >=40% modeled discount to the $150/SF benchmark | **14** >=25% (the
  ORA floor) | **6** 10-25% | **0** below. (Already skill-stated; restated here so
  the whole scale sits in one place.)
- **entity 10** where the owner of record is an entity rather than a natural person.
- **absentee 5** where the tax-mailing ZIP differs from the site ZIP.
- **multi 5** where the owner of record holds more than one parcel in the county
  industrial universe.

### Missing-component treatments (also pinned from the 2026-09-18 runs)

Never fake a component. Drop it, rescale honestly, and state the rescale on every
row's score-breakdown cell and in the README sheet.

- **Entity-owner uncomputable (Howard MD pattern — the state layer strips owner
  names, so `estate_v2` cannot fire on a name either):** drop the 10-point component
  and rescale **raw out of 90, x 100/90**. Per `…HowardMD_Summary_v01.md`, §5 "Data
  gaps, limits, and where this run is weaker than the pilot" item 1, which
  also post-hoc recovered all 20 names and found all 20 were entities — the rescale
  was arithmetically equivalent there and did not distort the ranking.
- **Non-disclosure state (Jackson MO pattern — no published sale price or date, so
  there is no empirical calibration factor and the basis component is zero on every
  row by construction):** drop the 20-point basis component and score on a **0-80
  scale**. Because hold also cannot discriminate (flat 16 UNKNOWN-HOLD on every row),
  the ACHIEVABLE maximum is 76, not 80 — so set **tier cutoffs as percentages of the
  achievable maximum, not as absolute points**: the pilot's A>=90 / B 85 / C 70 are
  90% / 85% / 70% of its achievable max, which against 76 gives **A >=68.4 · B
  64.6-68.3 · C 53.2-64.5 · D <53.2**. A mechanical rescale (A >=72) would make
  A-tier reachable only by a literally perfect score — a degenerate tier. Carry a
  *Score %* column so any other rule can be applied. Per `…JacksonMO_Summary_v01.md`,
  §6 "Divergences from the pilot" rows 2-4. Such a list is NOT comparable to a
  calibrated one — say so on
  the face of the deliverable.

### 7. Mine motivation signals (bulk extracts)
- Delinquency: tax-duplicate TotPrior/TotPenalty > 0 (or in-layer fields -
  Hamilton has DELQ_TAXES directly). Flag amount and vintage.
- Owner-level clustering: owners delinquent on ANY parcel who also own
  industrial - distress before it reaches the subject property.
- Sellers-in-motion: owners who sold industrial >=$100K within ~2 years AND
  still own - liquidation in progress; call before the next listing. Use
  grantor fields where published (Butler); otherwise infer prior owner from
  consecutive transfer records (Franklin pattern).
- Special-assessment arrears; rental-registry phone numbers; TIF flags
  (TIF distorts the value/basis math - flag, price in DD).

### 8. Verify before anyone calls
Occupant web check per finalist - Columbus found auto-use (policy-blocked
tenants) at 2 of the top 10, including the #1 scorer. Check for archived/
delisted listings (motivated seller). State SOS entity lookup for principals
(Ohio API is bot-gated - browser or manual). The score ranks capacity;
verification ranks quality. Attach a one-line pre-mortem (most likely reason
the deal fails ORA underwriting) to every presented candidate - ORA project
doctrine requires it.

### 9. Deliver
ORA-style workbooks (Oxford Navy 1B2A4A headers, Arial, zero formula errors,
run the xlsx skill's recalc.py): YYYYMMDD_[Market]-Parcel-Screen_v0N.xlsx
(ranked screen + README + QC failure-modes sheet) and, when distress data
exists, YYYYMMDD_[Market]-Motivated-Leads_v0N.xlsx. Save to the Investment
Candidates folder. Call-order doctrine: estate first, then delinquent entity
owners, then sellers-in-motion, then absentee portfolios, then long-holds.

## Engineering notes (hard-won - read before running)
- bash sandbox: 45s per call. Use scripts/dl_resume.py (resumable ranged
  downloader) for files >40MB. Unzip into a NEW subdirectory - the sandbox
  cannot overwrite or delete files written by previous calls. Stream-parse
  100MB+ files with csv.reader straight from zipfile.open().
- Parcel-ID formats differ between a county's GIS layer and its tax files
  (Franklin: '010-104049' vs '"010-104049-00"') - normalize before joining,
  verify the join produced matches (a silent 0-match join cost an hour once).
- Excel bulk files: pip install python-calamine, pandas engine="calamine"
  (10x faster than openpyxl; openpyxl times out on 250K-row files).
- Some county report servers WAF-gate downloads: send full browser headers
  (User-Agent + Accept(html) + Referer + Sec-Fetch-*) - Butler 403s without.
- Census ACS by ZCTA: the API now requires a key; key-free path is the
  table-based Summary File FTP (acsdt5y2023-bXXXXX.dat, estimate = column 1).
- GIS layers are often thin mirrors: physical fields (year built, height,
  condition) may be 0% populated - the bulk appraisal/building extract is the
  real source (Franklin Build.txt: YRBLT/WALLHGT/PHYCOND = 100% coverage).
  Conversely some counties (all 4 Cincinnati counties) publish NO commercial
  SF anywhere public - use footprint spatial joins or per-parcel scrapes.
- Owner-scrubbed GIS != owner-inaccessible: counties on Oracle APEX/ORDS CAMA
  front-ends (Henrico VA pattern - <host>/ords/<schema>/f?p=...) yield owners
  to a scripted wwv_flow.accept POST. Use scripts/apex_owner_pull.py (county
  config registry + resumable bulk + --smoke test; Henrico validated 279/279
  at ~0.85s/parcel). Probe for /ords/ before declaring a county data-hostile;
  add each validated county to the module's COUNTIES dict.
- Canonical classifiers live in scripts/: estate_v2.py (estate signals; '&'
  trailing-TRUST patch 2026-06-09), institutional_owners.py (institutional/
  ORA/never-call). Import these - never re-implement inline regex per run.

## Failure modes (carry into every QC sheet)
F1 nominal-transfer hold distortion | F2 stale auditor values (calibrate!) |
F3 physical fields empty in GIS layer | F4 class-code lag -> verify occupant |
F5 low basis != willingness (lock-in; estate/delinquency override) | F6 one
building spanning sibling parcels | F7 TIF value distortion | F8 unbranded
institutional affiliates slip the regex | F9 tax-mail = agent, not principal |
F10 the screen measures capacity, not willingness - expect 2-5% response;
volume + quarterly re-runs + signal-led call order is the strategy.

## References
- references/market-status.md - per-market progress tracker + queue. Update
  it after every market run.
- references/county-endpoints.md - verified URLs, field names, ID formats,
  quirks for every county already discovered. Append new counties here.
- references/county-endpoints.v1.json - machine-readable derived index (parcel/
  CAMA layer URL + layer id/name + MD JURSCODE only) of county-endpoints.md, for
  other skills to consume programmatically without parsing prose. county-endpoints.md
  remains the source of truth on any conflict; regenerate the JSON from it.

## Changelog
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
  ~$85-120/SF vs RCT v03 KC LOW $227.90) and the F8 institutional aliases.
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
