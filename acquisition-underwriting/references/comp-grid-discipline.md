# Comp Grid Discipline

Extracted verbatim from `acquisition-underwriting/SKILL.md` (2026-08-13, progressive-disclosure split) — no content changed, only relocated; the executed-lease rent-basis rule and template columns were added 2026-09-28 (Rent comp grid steps 3, 4 and 6). Referenced by MODES/COMPS, STAGE 2.6 item 4, and STAGE 2.9 item 3.

## COMP GRID DISCIPLINE (v4.11 — absorbed from the retired `rent-comp` skill, 2026-08-12)

**Provenance.** `rent-comp` was retired 2026-08-05 on a justification that did not survive inspection: its RETIRED.md credited `market-monitor` v1.2 with absorbing "comp-sourcing discipline," but that skill's SOURCING DISCIPLINE section is about vendor/operator-report *credibility* and contains no comp-grid method. Two unrelated things sharing a name were conflated. Gabriel ruled 2026-08-12 to absorb the live mechanics here (scoped restore). **Deliberately NOT carried over:** `rent-comp` §3 replacement-cost method (superseded by **RCT v03** — see UNDERWRITING CONVENTIONS in `SKILL.md`; its "≥30% discount" target is the pre-2026-07-14 artifact of a wrong denominator) and §6 benchmark table (superseded by `target-markets.json` + the Submarket Intelligence Reference table in `SKILL.md`). Do not reintroduce either.

**Governing rule:** comps must be **executed transactions, not asking prices**. Broker-quoted "cap rates" without a disclosed NOI are directional-only and tagged `[est]` — the same discipline as the Stage 2.1 vendor-report rule. Asking rents may be used for the *rent* grid (that is what the market is offering) but must be labeled ASK, never blended silently with executed rents.

### Rent comp grid
1. **Multi-source search** — `"[submarket] industrial warehouse lease rate per SF [year]"` · `"[submarket] flex space asking rent [year]"` · `site:loopnet.com` / `site:crexi.com industrial for lease [city] [state]` · `"[submarket] industrial market report [year]"` (CBRE/JLL/Cushman/Colliers/NAI) · `"[city] [state] shallow bay industrial available"`.
2. **Extract per listing:** address · total & available SF · asking rent ($/SF/yr **and** lease type: NNN / MG / Gross) · clear height · year built · loading (dock + drive-in) · listing broker & date · source URL.
3. **Assemble** (columns in this order): | Address | Suite/Block SF | Rent type (Ask / Executed) | Reported rent $/SF | Basis tag (NNN / MG / FS / Gross / +UTIL / Unstated) | NNN-equivalent $/SF [est] | OpEx proxy used and source | Date | Distance to subject (geocoded) | Small-suite flag (<1/3 of subject block) | Clear Height | Year Built | Dock | Drive-In | Source |
4. **Statistics:** median rent/SF (**preferred over mean for small samples**) · mean ± SD · range · interquartile range · trend direction (YoY where available) · **sample size and a data-quality note**. Statistics (median, range) are computed only on the NNN-equivalent column, separately for Ask and Executed. A grid of fewer than 3 comps is reported as directional, never as a market rent conclusion.
5. **Normalize before comparing:** convert all rents to **NNN-equivalent** (subtract estimated CAM/insurance/tax from Gross/MG quotes) · clear-height premium (16'+ over 12–14') · vintage adjustment (post-2000 vs pre-1990) · size adjustment (larger spaces typically lower $/SF). State every adjustment applied; an unnormalized grid is not a comp set.
6. **Executed lease rents must be tagged before they enter a comp grid** (rent-basis rule, added 2026-09-28; companion to `submarket-spatial-analysis` CoStar Report Ingest step 2):
   1. Tag each executed rent NNN / modified gross / full-service (FS) / gross / +UTIL / unstated.
   2. An FS, gross or modified-gross rent is never entered into an NNN grid unconverted. Show the NNN-equivalent beside the reported rent, state the OpEx proxy and its source, and tag it [est].
   3. Asking rents and executed rents sit in separate columns; never average across bases or across ask/executed.
   4. Unstated basis: exclude from the grid or carry as "unstated" outside the statistics until confirmed.
   5. Report suite size for every comp; comps below one-third of the subject's block size are labeled "small-suite".

   *Origin.* 4100 Perimeter Dr (Columbus): NNN asks ($10–$12) were compared with executed starting rents of $8.95 and $9.00 that were full-service (about $6.20–$6.25 NNN-equivalent [est] at $2.75/SF OpEx). The rent gap and a ~$560K uplift extrapolation were overstated; withdrawn in IC Memo v03 / Location Analysis v03.

### Sale comp grid
1. **Search:** `"[submarket] industrial property sold [year]"` (+ prior year) · `site:rebusinessonline.com` / `site:connectcre.com industrial sale [city]` · `"[city] [state] warehouse sold price per square foot"` · `"[submarket] industrial investment sale cap rate"`.
2. **Assemble:** | Address | SF | Sale Price | Price/SF | Cap Rate | NOI (if known) | Occupancy | Buyer | Seller | Date | Source |
3. **Analyze:** median & mean price/SF · median cap rate + range · price/SF **by vintage** (pre-1990 / 1990–2005 / post-2005) · price/SF **by size** (sub-25K / 25–50K / 50–100K / 100K+ SF) · trend vs 6–12 months prior.
4. Feeds the comp-implied cap-rate band in **Comp-based valuation mechanics** (UNDERWRITING CONVENTIONS) and STAGE 2.9's alternative-asset track.

### Full Comp Report output (COMPS mode deliverable)
Via the `xlsx` skill, 5 tabs: **1** Rent Comps (+ stats) · **2** Sale Comps (+ stats) · **3** Replacement Cost (**RCT v03** band — version cited, per UNDERWRITING CONVENTIONS; not the retired §3 method) · **4** Market Context (vacancy, absorption, supply pipeline, employment drivers) · **5** Source Log (every URL + retrieval date). Naming: session-output schema `YYYY-MM-DD_[Topic]_[DocType]_v##.ext` in `/outputs/`.
