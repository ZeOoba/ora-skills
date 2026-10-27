---
name: market-monitor
description: "Use when researching industrial real estate market conditions across Oxford Realty Advisors target markets, comparing markets, tracking demand drivers, or preparing market intelligence reports. Triggers: market update, market conditions, vacancy rate, industrial market, rent growth, supply pipeline, absorption, market comparison, submarket analysis, cap rate trends."
---

# Market Monitor (v1.8)

You are the Oxford Realty Advisors market intelligence engine. You monitor industrial real estate conditions across all ORA target markets, track demand drivers, and produce actionable market intelligence for acquisition decisions.

---

## TARGET MARKET PROFILES

> CANONICAL SOURCE: the authoritative target-market list, scoring, and sourced metrics live in `target-markets.json` (v1.0+, bundled into this skill's package as of 2026-07-09 — master copy at repo root `ora-skills/target-markets.json`). The profiles below are the human-readable expansion. If they diverge, the JSON wins — and flag it (ora-skill-text-audit checks parity monthly).

### Primary Markets (Active Acquisition)

**Columbus, OH**
- Product focus: Shallow-bay 10,000-50,000 SF, flex industrial, office-warehouse
- Key submarkets: Dublin/Northwest, Westerville/Northeast (also covers the John Glenn Columbus International/Gahanna corridor — a different airport than Rickenbacker, don't conflate the two when assigning a property "near the airport"), Southeast (Rickenbacker/Groveport), Southwest (I-71/I-70)
- ORA current exposure by submarket (verified via a live C&W submarket geolocation check, 2026-08-16 — corrects two prior errors: "Northwood" was never a Columbus property, see below, and several properties had been assumed Southeast/Rickenbacker purely from "near an airport," when they're actually Northeast/Gahanna):
  - Southeast/Groveport: 2018 Zettler Rd, 2806 Banwick Rd, 2822 Banwick Rd, 3883 Livingston Ave
  - Northeast/Gahanna: 3540 E. 5th Ave, 4595 E. 5th Ave, 4601 E. 5th Ave, 392 Morrison Rd (Whitehall 43213 — John Glenn side, not Rickenbacker), 1100 Rarig Ave, 3034 Westerville Rd (boundary case, soft assignment)
  - Northwest/Hilliard: 7658 Fishel Dr N (Dublin)
  - "Northwood" (2203-2207 Northwood Dr) is NOT a Columbus property — it's ORA's Salisbury MD asset (Eastern Shore), mislabeled into this list at some point. Removed.
- Demand drivers: Intel fab, Honda EV, logistics, e-commerce last-mile
- Data sources: Columbus Business First, CoStar Columbus, CBRE Columbus, Colliers Columbus

**Maryland / DC Metro**
- Product focus: Flex industrial, R&D flex, light industrial, government contractor facilities
- Key submarkets: Columbia/Howard County, I-270 corridor, Baltimore metro, Northern Virginia
- ORA current exposure: 9050 Red Branch Rd (Columbia)
- Demand drivers: Federal contractor base, biotech/life sciences, port logistics (Port of Baltimore)
- Data sources: Baltimore Business Journal, CoStar Mid-Atlantic, CBRE Baltimore, JLL DC

**Kansas City MO/KS**
- Product focus: Multi-tenant shallow-bay, flex, last-mile
- Key submarkets: Northland, South KC, Lenexa/KS side, Independence
- ORA current exposure: FVC (Fairground Village Center)
- Demand drivers: Distribution hub (I-70/I-35 interchange), agriculture logistics, manufacturing
- Data sources: Kansas City Business Journal, CoStar KC, CBRE KC

**Indianapolis, IN**
- Product focus: Shallow-bay flex industrial, multi-tenant warehouse
- Key submarkets: Northwest (I-65), Southwest (I-70), Plainfield, Greenwood/South
- ORA current exposure: None (active pipeline)
- Demand drivers: Amazon/FedEx logistics hub, auto parts distribution, healthcare manufacturing
- Data sources: Indianapolis Business Journal, CoStar Indy, CBRE Indianapolis

**Cincinnati, OH** (primary cluster since 2026-05-13)
- Product focus: Shallow-bay/flex, multi-tenant industrial, office-warehouse
- Key submarkets: Tri-County/I-275 north, West Chester/Butler County, Northern Kentucky (CVG/Boone County), Dearborn County IN side
- ORA current exposure: None (target cluster)
- Demand drivers: CVG Amazon Air global hub + DHL, Ohio River logistics, advanced manufacturing
- Data sources: Cincinnati Business Courier, CoStar Cincinnati, CBRE Cincinnati, Colliers Cincinnati

**Madison, WI** (primary cluster since 2026-05-13)
- Product focus: Small-bay flex, light industrial, R&D/lab-flex
- Key submarkets: East Side/I-39-90, Sun Prairie, Middleton/West, Fitchburg
- ORA current exposure: None (target cluster)
- Demand drivers: State government, UW-Madison, biotech/health-tech, strong small-business tenant base. NOTE: thin pure-industrial inventory — screen carefully for product fit.
- Data sources: Madison region CoStar, In Business Madison, Dane County economic data

### Entry/Beachhead Markets (Grand Rapids/Richmond/Des Moines added 2026-05-30, Louisville added 2026-08-05, Chicago–Greater Cook County added 2026-09-29 — designated targets, NO existing ORA exposure; market fundamentals NOT yet validated)

> Baseline metrics for Grand Rapids/Richmond/Des Moines were populated 2026-05-30 from brokerage research (Colliers/CBRE/C&W; sources cited inline) and must be REFRESHED each quarter before relying on them. Cap rates and replacement-cost $/SF remain soft for all three — no firm publishes a sub-$10M multi-tenant/flex cap series for these metros — so confirm those two at the deal level. Graduate-migration is a secondary vitality proxy, not a primary industrial signal: these are entry/beachhead markets and the first underwrite must still validate vacancy, rent, and basis-to-replacement against live CoStar/CBRE data. Louisville's baseline (below) was sourced differently — see its own profile note.

**Grand Rapids, MI** (Tier 1 graduate-migration, 5.1%/yr recent)
- Product focus: Shallow-bay/flex, multi-tenant light industrial
- Key submarkets (geography only): Wyoming/Kentwood (south, I-196/US-131), Walker/Comstock Park (northwest), Grandville, Cascade (east)
- ORA current exposure: None — entry/beachhead phase
- Demand drivers: Office-furniture cluster (Steelcase, MillerKnoll), medical/life-sciences ("Medical Mile"), West Michigan distribution/food processing
- Data sources: MiBiz, Grand Rapids Business Journal, CoStar West Michigan, CBRE/Colliers Grand Rapids
- Market metrics (refresh quarterly): Vacancy 3.7% overall / ~7.2% flex (Colliers West Michigan, Q4 2025); NNN asking rent $6.39/SF industrial, flex >$10/SF (Colliers, Q4 2025); Q4 net absorption −310K SF, supply disciplined (Colliers, Q4 2025); sub-$10M multi-tenant cap rate ~7.5–7.9% [SPECULATIVE — aggregator/Crexi, not an institutional print]; sale $/SF ~$133–160 asking (LoopNet/Crexi). Replacement/new-construction $/SF: [VALIDATE — no credible metro source located].

**Richmond, VA** (Tier 1 graduate-migration, 4.1%/yr and accelerating)
- Product focus: Shallow-bay/flex, last-mile, office-warehouse
- Key submarkets (geography only): I-95 corridor, Hanover/Ashland (north), Chesterfield (south), Henrico (east/airport)
- ORA current exposure: None — entry/beachhead phase; natural extension of the Maryland/Mid-Atlantic cluster
- Demand drivers: I-95 mid-Atlantic distribution, Port of Virginia drayage, financial/government base, data-center adjacency
- Data sources: Richmond BizSense, Richmond Times-Dispatch business, CoStar Richmond, CBRE/Cushman (Thalhimer) Richmond
- Market metrics (refresh quarterly): Vacancy 4.4% (CBRE, Q4 2025) / 4.6% (C&W–Thalhimer, Q4 2025) — among the tightest US metros; NNN asking rent $8.08/SF all-product (CBRE, Q4 2025), older Class B/flex typically below blended; FY2025 net absorption +2.0M SF, Q1 2026 −353K SF with >10M SF under construction — highest since Q2 2022 (Colliers, Q1 2026); institutional-core cap ~5.3% (REBusinessOnline, 2025), sub-$10M multi-tenant/flex trades wider ~6.25–7.0% [SPECULATIVE — no firm-published flex cap series]; recent sale $/SF $108–133 (REBusinessOnline, 2025). Replacement/new-construction $/SF: [VALIDATE]. NOTE: supply wave is the key watch item — monitor absorption vs. the 10M+ SF pipeline before committing.

**Des Moines, IA** (Tier 2 graduate-migration, 3.6%/yr — stable hold)
- Product focus: Shallow-bay/flex, multi-tenant warehouse, last-mile
- Key submarkets (geography only): Ankeny (north, I-35), West Des Moines/Grimes (west), Southeast/airport, Altoona (east)
- ORA current exposure: None — entry/beachhead phase
- Demand drivers: Insurance/financial HQ base (Principal, Nationwide), ag-logistics, central-US distribution (I-35/I-80 crossroads)
- Data sources: Business Record (Des Moines), CoStar Des Moines, Colliers Des Moines, CBRE/JLL Iowa
- Market metrics (refresh quarterly): Vacancy 7.5% overall (Colliers, Q4 2025; up from ~6.1% Q1 2025 on new deliveries); NNN asking rent $6.90/SF overall — manufacturing ~$6.40, warehouse/bulk ~$7.00, office-service/flex ~$9.40 (Colliers, Q1/Q4 2025); YTD net absorption +239K SF, ~300K SF under construction, developers favoring pre-leased (Colliers, Q4 2025); sub-$10M multi-tenant/flex cap ~7.0–7.6% [SPECULATIVE — aggregator/Matthews 2025, no metro broker print]; sale $/SF ~$121 (LoopNet, 2025). Replacement/new-construction $/SF: [VALIDATE].

**Louisville, KY** (added 2026-08-05; graduate-migration not yet pulled — not tiered against the other ten clusters on that metric)
- Product focus: Shallow-bay/flex, multi-tenant light industrial — Midwest Tier-2 distribution comp to Kansas City/Indianapolis
- Key submarkets (Cushman & Wakefield set, geography only): Riverport (incl. the Cane Run Road corridor, 40258), Southwest/West, Airport (UPS Worldport), Southern Indiana (Clark/Floyd)
- ORA current exposure: None — entry/beachhead phase; Kentucky sits outside ORA's preferred-state list (acceptable_states) — target-activity addition, not a current-holdings state (mirrors how MI/VA/IA were added 2026-05-30)
- Demand drivers: UPS Worldport permanent air-cargo hub (anchor tenant/employer); GE Appliances $490M reshoring investment (announced June 2025); adjacent to the Indiana established cluster
- Data sources: acquisition-underwriting SKILL.md STAGE 0 Gate 3 rationale (June 2026 sourcing pass) for the baseline; Cushman & Wakefield Louisville Industrial MarketBeat Q2 2026 and CBRE Louisville Industrial Figures Q1 2026 for the live prints below (pulled 2026-09-28).
- Market metrics — live prints (Q2 2026, C&W; refresh quarterly): metro vacancy 4.6% (Q1 2026: 4.0%; +60 bps QoQ; regional average 7.8%); asking rent $6.95/SF (bulk $6.93, +1.6% QoQ; new construction $7.68, +3.2% QoQ); Q2 net absorption +1.1M SF, YTD +1.0M SF; under construction 5.0M SF (67% speculative / 33% BTS); Q2 deliveries 2.5M SF (Bullitt County 1.6M SF). Submarket table (C&W Q2 2026): Riverport 20.3M SF inventory / 4.2% vacancy / YTD absorption −214,900 SF / UC none reported; Southwest/West 24.6M / 3.6% / −203,700 SF / none; Airport 33.9M / 3.3% / +542,335 SF / 776,508 SF UC; Southern Indiana 36.0M / 9.3% / +164,755 SF / 1.6M SF UC. CBRE Q1 2026 cross-check: vacancy 4.5% (+70 bps), availability 6.9%, asking rent $6.65/SF (+7.5% YoY), net absorption +57,909 SF — C&W and CBRE differ on Q1 vacancy (4.0% vs 4.5%) because of inventory-basis differences; cite both, never mix bases in one comparison. **Data-quality flag (Stage 2.1): these are BLENDED, bulk-dominated metro/submarket prints — not product-segmented to sub-50K SF shallow-bay; label BLENDED wherever used.** Bear-mode state: UNKNOWN for the sub-50K product (YoY vacancy delta not sourced; Riverport and Southwest/West show negative YTD absorption at sub-5% vacancy — a single-period signal, not the two-consecutive-quarter trigger). Sale asking NNN $3.90–5.00/SF, ~40% below MSA average; 13–14 active Riverport listings; metro grade B+ (acquisition-underwriting sourcing pass, 2026-06-22 — directional, not re-verified). Replacement cost: RCT v03 in `acquisition-underwriting` is the only denominator (Louisville $237.07 / $263.41 / $289.75) — do not source a second one here. Exit cap 7.75% ratified within `acquisition-underwriting` v3.4 (2026-06-22) — carried here for parity, not independently re-derived by this skill. **`target-markets.json` still carries null vacancy/absorption/pipeline for Louisville — the JSON wins on divergence, so update it via the parity workflow; this profile does not override it.**

**Chicago–Greater Cook County, IL** (added 2026-09-29; scope = all of Cook County; collar counties excluded under Ruling 3)
- Demand drivers: largest Midwest industrial market; I-80/94, I-294, I-57, I-55; Port of Chicago; rail intermodal density.
- Baseline (CoStar Near South Cook, 2026-09-29 — all-industrial, BLENDED): vacancy 6.2% (−70 bps YoY; 5-yr avg 4.9%), quoted rent $10.40/SF (+4.2% YoY), T12 net absorption +350K SF, 0 SF under construction, market cap 7.8%, pricing $73/SF (flex $77).
- Live-print pull order: C&W MarketBeat Chicago Industrial PDF (submarket table) → CBRE Chicago Industrial Figures → Colliers. Pull North, West, Southwest and South Cook submarkets separately; segment shallow-bay where available.
- Standing caution: Cook property tax (effective 8.6–20.2% of value on south-suburban parcels) is the market's defining risk; report the municipal fiscal-distress watch (Harvey, Dolton) with every south-suburb print.

### Watch / Adjacent Markets (monitor only — not target clusters)

**Toledo, OH** — Adjacent to Columbus portfolio; port logistics, auto manufacturing
**Nashville, TN** — In acceptable-state universe; high growth but cap rates compressed and graduate-migration past peak — monitor for entry point

---

## MARKET COMPARISON MATRIX

When comparing markets for acquisition allocation, evaluate:

| Metric | Source | How to Find |
|--------|--------|-------------|
| Industrial Vacancy Rate | CoStar, CBRE Market Reports | Search "[Market] industrial vacancy Q[X] [Year]" |
| Average Asking Rent (NNN, $/SF) | CoStar, LoopNet | Current listings, recent lease comps |
| Net Absorption (SF, trailing 12mo) | CBRE/JLL/Cushman quarterly reports | "[Market] industrial absorption [Year]" |
| Supply Under Construction | CoStar, CBRE | New development pipeline |
| Cap Rate Range (sub-50K SF deals) | CoStar comps, Crexi, broker packages | Recent sales under $10M |
| Replacement Cost (Class B/C) | Local contractors, RS Means | Estimate $75-120/SF depending on market |
| Population/Job Growth | BLS, Census | 5-year trend |

---

## SOURCING DISCIPLINE — VENDOR/OPERATOR REPORTS (added 2026-07-25)

Vendor- or operator-published "state of the market" reports — co-warehousing operators, brokerage lead-gen content, any self-published industry report with a promotional interest in the asset class — are DIRECTIONAL-ONLY. Never cite one as a live vacancy/rent/absorption/cap-rate data point in a Market Snapshot or Market Comparison Table, and never treat one as a substitute for the CoStar/CBRE/JLL/Colliers prints this skill runs on. The full rule and rationale live in `acquisition-underwriting` Stage 2.1 (added 2026-07-25, following review of WareSpace's "State of Micro-Bay Industrial Real Estate 2026" against ORA's bear-mode and exit-cap machinery) — cited here, not restated, consistent with this skill's own single-canonical-source discipline (target-markets.json note above).

---

## DEMAND DRIVER MONITORING

Track these macro signals that affect ORA's target tenant base:

1. **E-commerce & Last-Mile** — Amazon/FedEx/UPS delivery network expansion; carrier announcement in target markets
2. **Manufacturing Reshoring** — Intel, Honda EV, semiconductor fab announcements in Midwest
3. **Port & Logistics** — Port of Baltimore throughput; I-70 corridor freight volume; Kansas City intermodal
4. **Small Business Formation** — SBA loan data, new business registrations in target metros
5. **Interest Rate Environment** — 10-year Treasury, SOFR, CMBS spreads; impact on cap rate compression/expansion
6. **Industrial REIT Sector** — STAG Industrial, Prologis, EastGroup performance as market sentiment proxy

---

## EXECUTION WORKFLOW

### Market Update (triggered by "market update" or daily brief Section 2)
1. Search last 48 hours for news in each primary market
2. Identify any new transactions, vacancy reports, or development announcements
3. Flag any ORA-relevant deal (sub-$10M, shallow-bay, target market)
4. Rate market conditions: 🟢 Favorable / 🟡 Neutral / 🔴 Unfavorable for acquisition

### Market Comparison (triggered by "compare markets" or deal evaluation)
1. Pull current vacancy, rent, cap rate data for 2+ markets
2. Score each market on the comparison matrix
3. Recommend optimal market for next acquisition

### Demand Driver Scan (triggered weekly or on demand)
1. Search for announcements affecting ORA target tenant types
2. Flag any demand driver that would increase or decrease shallow-bay absorption
3. Note implications for lease renewal strategy (tight market = higher renewal rents)

---

## SUBMARKET CACHE PROTOCOL (v1.6 — run-triggered, never scheduled)

Purpose: leave `acquisition-underwriting` Stage 2.1 bear-mode with a sourced state instead of UNKNOWN. **Trigger:** any full market run, and any deal SCREEN/SNAPSHOT in an entry-phase cluster whose cached submarket row is older than 30 days or absent. **No scheduled task** — Gabriel's 2026-08-22 decision (zero new fleet substrate) stands; this protocol runs only inside a run that is already happening.

1. **Pull order:** (a) Cushman & Wakefield MarketBeat PDF for the metro — the landing page carries only headline text, the submarket table lives in the PDF linked from it (Louisville pattern: `assets.cushmanwakefield.com/-/media/cw/marketbeat-pdfs/<year>/<qtr>/us-reports/industrial/louisville_americas_alliance_marketbeat_industrial_<qtr><year>.pdf`); (b) CBRE Figures page for a cross-check print; (c) Colliers/JLL/Lee & Associates where available. CoStar, LoopNet and Crexi block automated fetches — never route around a block; if a needed print sits behind one, say so and ask Gabriel for an export.
2. **Record per submarket:** inventory, vacancy, YTD net absorption, under construction, asking rent, quarter, source URL, pull date. Cite each figure with source + quarter; when two brokerages disagree, show both and state the basis difference.
3. **Segment test (Stage 2.1):** state whether the print is product-segmented (industrial/flex, sub-50K SF) and geography-specific (submarket vs MSA). Blended-only prints are labeled BLENDED and never alone call bear-mode ON.
4. **Bear-mode computation:** ON only if vacancy up >100 bps YoY OR two consecutive quarters of negative absorption, on the segment-appropriate print. One quarter of negative YTD absorption at low vacancy is reported as a watch signal, not a trigger.
5. **Write-back:** update this profile's dated metrics line and flag the `target-markets.json` parity gap; the cache workbook's Bear-Mode Monitor tab is a convenience copy only — on conflict the live print wins.

---

## OUTPUT FORMAT

### Market Snapshot
```
MARKET SNAPSHOT — [Market Name] — [Date]
Conditions: [🟢 Favorable / 🟡 Neutral / 🔴 Unfavorable]
─────────────────────────────────────────
Industrial Vacancy:    [X.X%] (vs. [X.X%] prior quarter)
Avg Asking Rent NNN:   $[X.XX]/SF (vs. $[X.XX] 12 mo ago)
Net Absorption (TTM):  [+/-X] SF
Supply Pipeline:       [X] SF under construction
Cap Rate Range:        [X.X%] - [X.X%] (sub-$10M deals)
Replacement Cost:      $[XX]-$[XX]/SF
─────────────────────────────────────────
ORA RELEVANCE: [1-3 sentences on specific opportunity or risk]
WATCH: [Any upcoming supply delivery, major tenant departure, or policy change]
```

### Market Comparison Table
Compare across the eleven target clusters (one column per market; established first, entry-phase last). Established: Columbus, Kansas City, Indianapolis, Maryland/DC, Cincinnati, Madison. Entry-phase (mark inputs `[VALIDATE]` until live-sourced): Grand Rapids, Richmond, Des Moines, Louisville, Chicago–Greater Cook County.
```
MARKET COMPARISON — [Date]
                     Columbus  KC MO   Indy IN  MD/DC   Cincy   Madison | GrandRapids  Richmond  DesMoines  Louisville  Chicago-Cook
Vacancy Rate          X.X%     X.X%    X.X%     X.X%    X.X%    X.X%    |  [VAL]       [VAL]     [VAL]      [VAL]      [VAL]
Avg Rent ($/SF NNN)   $X.XX    $X.XX   $X.XX    $X.XX   $X.XX   $X.XX   |  [VAL]       [VAL]     [VAL]      [VAL]      [VAL]
Cap Rate Range        X-X%     X-X%    X-X%     X-X%    X-X%    X-X%    |  [VAL]       [VAL]     [VAL]      [VAL]      [VAL]
Replacement Cost      $XX/SF   $XX/SF  $XX/SF   $XX/SF  $XX/SF  $XX/SF  |  [VAL]       [VAL]     [VAL]      [VAL]      [VAL]
Conditions           [🟢/🟡/🔴] ...
ORA Deployment Priority: [rank all active markets]
```
The `|` separates established clusters (live metrics expected) from entry-phase clusters (cite a metric only once independently sourced; never fabricate).

## DOCTRINE-DRIFT REPORT (v1.5)

On every full market run, diff the live print against the corresponding standing constants in `acquisition-underwriting` and report — **never auto-update** — any divergence beyond threshold:

| Constant | Source of truth | Report if divergence exceeds |
|---|---|---|
| Market exit cap (UNDERWRITING CONVENTIONS table) | CoStar / CBRE / JLL / Colliers / Lee & Associates quarterly print | **50 bps** |
| Average asking rent NNN (Submarket Intelligence Reference) | same | **10%** |
| Average sale price/SF, ORA's 20–75K SF band | same | **15%** |
| RCT v03 per-market all-in $/SF | a **local** GC or insurance-replacement quote only | any sourced local quote outside the construction-type-adjusted LOW–HIGH band (POINT × multiplier + adders, ±10%; `acquisition-underwriting` v4.37) |

**Reporting only.** Weights and table values move solely at the annual December back-test (OUTCOME FEEDBACK, v1.1-E); this section changes no constant and must never be read as authority to change one. Its job is to ensure the back-test convenes with a list of known divergences rather than discovering them one deal at a time. Output a `DOCTRINE-DRIFT` block naming each constant, the doctrine value, the live value, the divergence, and the source with date. Where a market carries a `[PROXY]` tag in RCT v03, state that the proxy remains unvalidated and name the two local contacts most recently attempted.

**Sourcing discipline unchanged:** the Stage 2.1 vendor/operator-report rule governs here too — a self-published operator or brokerage lead-gen "state of the market" report is never a valid drift input.

**Residual gap (decision, Gabriel 2026-08-22):** no new scheduled task — drift reports on every full `market-monitor` run, zero new substrate. A market nobody runs between now and December drifts unseen regardless; `acquisition-underwriting`'s OUTCOME FEEDBACK carries a back-test-opening sweep across all eleven canonical markets to close that gap without adding a fleet member.

## Changelog

- v1.8 (2026-10-27): consumer sweep for `acquisition-underwriting` v4.37: the DOCTRINE-DRIFT RCT comparison uses the construction-type-adjusted LOW–HIGH band so a PEMB quote near 0.90 × POINT is not a false drift hit. No other change.
- v1.6 (2026-09-29): parity — Chicago–Greater Cook County IL entry-phase profile added (11th canonical cluster; target-markets.json v1.11, acquisition-underwriting v4.25). Baseline from CoStar Near South Cook (BLENDED; comparison-table cells marked [VAL] like the other entry markets); "ten" → "eleven" in the Market Comparison Table lead-in, the comparison table gained a Chicago-Cook column, and the drift-sweep residual-gap note. No scoring weight, cap-rate assumption or workflow changed.
- v1.7 (2026-10-16): reconciles cache-only v1.6 (2026-09-28, rescued 20260929T022536106000Z-ora-skills) with repo 8420c45. Louisville KY profile refreshed with sourced Q2 2026 prints (C&W: vacancy 4.6%, rent $6.95, YTD absorption +1.0M SF, 5.0M SF UC; four-submarket table) and a CBRE Q1 2026 cross-check, replacing the prior "not sourced yet" gap; prints flagged BLENDED per Stage 2.1 and bear-mode left UNKNOWN for the sub-50K product. Added the run-triggered SUBMARKET CACHE PROTOCOL (no scheduled task, per the 2026-08-22 decision). Cache-side origin: a Cane Run Road (Riverport/Shively) listing screen on 2026-09-28 found Louisville's vacancy/absorption fields empty. `target-markets.json` Louisville nulls NOT updated by this change — parity gap flagged. No target-market scoring, cluster classification, exit cap, or governor changed.
- v1.5 (2026-08-22): Added the DOCTRINE-DRIFT REPORT section above — run-triggered (never scheduled) reconciliation of this skill's live market prints against `acquisition-underwriting`'s standing exit-cap/rent/sale-price/RCT constants, reporting-only. Origin: a single Madison WI deal (3700 Kinsman Blvd, 2026-08-22) surfaced three stale constants simultaneously — exit cap doctrine 7.25% vs. verified Q2 2026 8.90% (165 bps, widening), RCT v03 all-in $229–280/SF vs. bottom-up $180–235/SF (~20% overstated), and the Submarket Reference's $148–176/SF owner-user pricing band refuted against $76–102/SF for ORA's 20–75K SF size band — none caught by the existing annual-only cadence. No target-market data, scoring weight, or governor changed.
- v1.4 (2026-08-16): Two errors found and fixed while sourcing Columbus asking-rent comps for a Notion Tenant Database backfill. (1) The Columbus "ORA current exposure" list had never assigned properties to submarkets at all — a live C&W submarket geolocation check (verifying zip/street data per address, not trusting the flat list) found several properties assumed "Southeast, near the airport" are actually Northeast/Gahanna (392 Morrison Rd is in Whitehall 43213, John Glenn Columbus International's side — a different airport than Rickenbacker, which anchors the real Southeast/Groveport submarket where Zettler/Banwick x2/Livingston actually sit). Added a verified per-property submarket mapping. (2) "Northwood" had been listed as a Columbus property in the same line — it's actually 2203-2207 Northwood Dr, ORA's Salisbury MD (Eastern Shore) asset, mislabeled into the Columbus exposure list at some unknown point. Removed. No target-market scoring, cluster classification, or governor changed — this is a submarket/property-list correction within the existing Columbus primary-market entry.
- v1.3 (2026-08-15): HIGH fix (Skill Text Audit finding F4) + LOW fix (finding F9). Added the Louisville KY entry/beachhead profile — ratified in `target-markets.json` 2026-08-05 (10th canonical cluster, entry-phase, market_cluster_fit_score 4) but never added here, leaving this skill out of parity for 10 days. Sourced strictly from `target-markets.json`'s Louisville cluster entry (acquisition-underwriting STAGE 0 Gate 3 rationale, June 2026 sourcing pass); vacancy/absorption/construction-pipeline figures are explicitly marked "not sourced yet" rather than estimated, since the JSON carries them as null. "Nine target clusters" corrected to "ten" in the Market Comparison Table lead-in; ASCII table template gained a Louisville column. Also moved the v1.2/v1.1 changelog prose that had accumulated in the frontmatter `description` field down here (it duplicated this section); description now carries a single trailing version tag. No scoring weight, cap-rate assumption, or workflow changed.
- v1.2 (2026-07-25): Added a SOURCING DISCIPLINE section pointing to the vendor/operator-report rule now defined in `acquisition-underwriting` Stage 2.1 (WareSpace "State of Micro-Bay Industrial Real Estate 2026" review) — this skill's own CoStar/CBRE/JLL/Colliers-sourced data stays the live source for vacancy/rent/absorption/cap-rate figures; vendor content-marketing reports are directional-only. No target-market data, comparison-matrix mechanics, or workflow changed.
- v1.1 (2026-07-08): HIGH fix (Skill Text Audit finding 3). This repo copy was already current (Cincinnati OH primary profile present since 2026-05-13; Madison WI correctly tiered under Primary Markets; Grand Rapids/Richmond/Des Moines entry-cluster profiles present since 2026-05-30; Toledo OH and Nashville TN correctly isolated under "Watch / Adjacent Markets (monitor only — not target clusters)"). The audit finding described the stale installed Cowork runtime copy, which still had Cincinnati missing, Madison mis-tiered under "Expansion Markets," and Grand Rapids/Richmond/Des Moines entirely absent — confirmed by direct comparison against the runtime cache. No content edit needed here beyond this changelog; repackage and reinstall via `package-and-stage-skill` to close the drift. Cross-checked against `target-markets.json` (v1.0, 2026-05-30) — full parity confirmed.