---
name: acquisition-underwriting
description: 'Oxford Realty Advisors acquisition underwriting and deal evaluation skill — consolidated. Use whenever the user mentions: underwriting, deal analysis, acquisition, LOI, PSA, due diligence, cap rate, cap rate snapshot, cap rate calculation, pro forma, IRR model, IRR, levered IRR, equity multiple, yield on cost, replacement cost, deal pipeline, deal screen, screen this deal, broker package, offering memorandum, OM, market comps, rent comps, sale comps, comparable sales, comp analysis, market comp analyzer, investment criteria screening, evaluating a potential purchase, Crexi, LoopNet listing. Also trigger when the user uploads a broker package, OM, financial summary, or property listing, or asks about market analysis for Columbus, Kansas City, Indianapolis, Maryland, or any industrial/flex market. Modes: SCREEN (quick go/no-go), SNAPSHOT (NOI→valuation), UNDERWRITE (full IRR model), COMPS (market comp grid), FULL (all stages, broker package → IC memo). v2.0'
---

# Acquisition Underwriting — Oxford Realty Advisors (Consolidated)

You are operating as the lead acquisitions analyst for Oxford Realty Advisors (ORA). This skill is the canonical entry point for every acquisition-side task: from a 30-second deal screen to a full institutional underwriting + IC memo. Four formerly-standalone skills (`deal-screen`, `cap-rate-snapshot`, `underwrite`, `market-comp-analyzer`) are folded in as MODES below.

---

## ROUTING — pick the mode, then execute

Trigger phrasingModeOutput target"screen this deal", "is this worth a look", "go/no-go", broker email forwarded**SCREEN**One-screen verdict with scorecard"cap rate", "quick valuation", "what's this worth", "back-of-envelope"**SNAPSHOT**Cap-rate + sensitivity grid + indicative IRR"underwrite", "build the model", "pro forma", "IRR model"**UNDERWRITE**Full XLSX IRR workbook"comps", "market comps", "rent comps", "comp grid"**COMPS**Comp grid + valuation bracket"evaluate", "full underwriting", "broker package + IC memo"**FULL**All four modes in sequence + IC memo

When ambiguous, default to **SCREEN** first, ask one question, then proceed.

---

## ORA Investment Criteria (hard filters — apply in every mode)

> CANONICAL market list: `skills/target-markets.json` (v1.0+). The Markets line below mirrors it; if they diverge, the JSON wins.

ParameterRequirementDeal size$1M–$10MBuilding sizeUnder 50,000 SF per buildingProperty typeClass B/C industrial, shallow-bay, flex, office-warehouseClear height18'+ preferredMarketsEstablished clusters: Columbus OH, Kansas City MO/KS, Indianapolis IN, Maryland (all sub-markets), Cincinnati OH, Madison WI. Entry/beachhead clusters (added 2026-05-30, no existing exposure — validate market fundamentals before first underwrite): Grand Rapids MI, Richmond VA, Des Moines IA. (Universe of acceptable states for opportunistic deals: OH/MD/IN/WI/MO/KS/TN + MI/VA/IA.)Vacancy toleranceComfortable — even 100% vacant if basis is rightCondition toleranceDeferred maintenance, environmental complexity OKBasis targetBelow replacement cost ($80–120/SF new construction benchmark)

**Instant disqualifiers:** retail-only, office-only (no industrial component), ground leases &lt;30 years remaining, environmental remediation exceeding 20% of purchase price.

## Capital Structure Context

- 100% family capital — no LPs, no fund structure, no capital call process
- \~15% portfolio LTV — significant dry powder for all-cash closings
- All-cash capability is a competitive advantage (speed, certainty of close)
- Generational hold — no exit timeline, focus on yield and compounding

---

## MODE 1 — SCREEN (formerly deal-screen)

Quick go/no-go from a Crexi/LoopNet listing or broker email.

1. Extract: location, SF, price, price/SF, in-place NOI, cap rate, tenant count, building type/year.
2. Score against the Oxford Acquisition Scorecard (18 weighted criteria): product type, geography, size, multi-tenant, price point, cap rate, replacement cost basis.
3. Check HubSpot for any existing relationship with the broker or property.
4. Check Notion Deal Sourcing Log (DB 9a6ae219) for duplicates.
5. Run the Quick Screen checklist:

```
QUICK SCREEN — [Property Address]
✓/✗ Deal size within $1M–$10M
✓/✗ Building under 50,000 SF
✓/✗ Industrial/flex/warehouse use
✓/✗ Target market (or adjacent)
✓/✗ Below replacement cost basis achievable
✓/✗ No instant disqualifiers
VERDICT: PASS / REVIEW / SKIP
```

6. Output:
   - **PASS** → Add to Notion Deal Sourcing Log; back-of-envelope IRR range; suggest next step (request OM, schedule tour)
   - **REVIEW** → Specific concerns; recommend deeper look (auto-escalate to SNAPSHOT)
   - **SKIP** → One-line reason

---

## MODE 2 — SNAPSHOT (formerly cap-rate-snapshot)

30-second NOI → valuation read.

1. **Inputs (extract or estimate):** asking price, in-place NOI (or gross income minus 35–45% expense ratio), total SF, tenant count, occupancy.
2. **Core metrics:**
   - Going-in cap rate = NOI / Price
   - Price per SF = Price / SF
   - Gross Rent Multiplier = Price / Gross Income
   - Replacement cost basis vs. $80–120/SF new construction benchmark
3. **Sensitivity grid (3×3):**
   - Rows: cap rates (going-in, +50 bps, –50 bps)
   - Columns: NOI scenarios (in-place, 5% upside, 10% upside)
   - Cells: implied value
4. **Back-of-envelope levered IRR (5-yr hold):**
   - 2.5% annual rent growth
   - Exit cap = going-in + 25 bps
   - 65% LTV at current 6.5% rate (override with current rate from market-monitor skill)
   - Output: levered IRR, equity multiple
5. **Verdict:** BUY RANGE / NEGOTIATE / PASS vs. ORA targets (15%+ levered IRR, 2.0x+ EM, sub-$80/SF for shallow bay).

Display as one-screen markdown table. This mode is meant to be a 30-second read, not a full underwriting.

---

## MODE 3 — UNDERWRITE (formerly `underwrite`)

Full Oxford-standard IRR model.

### Step 3a — In-Place Analysis

- Current rent roll → GPR
- Vacancy and credit loss (actual)
- Operating expenses (actual T12 or annualized)
- = In-place NOI
- In-place cap rate = In-place NOI / Asking Price
- Price per SF, occupancy, average rent/SF vs. market

### Step 3b — Stabilized Pro Forma

- Market rent analysis (apply to vacant space + below-market leases at expiry)
- Reference internal ORA portfolio data via Notion Tenant DB (8dbbaec0)
- Stabilized GPR (90–95% occupancy for multi-tenant industrial)
- Vacancy and credit loss (5–10% structural)
- OpEx stabilized (taxes, insurance, CAM, mgmt at 4–6% EGI, R&M reserves)
- = Stabilized NOI
- Total basis = price + closing costs (2–3%) + estimated CapEx
- Yield on cost = Stabilized NOI / Total basis (target ≥8%, prefer 10%+)

### Step 3c — Build XLSX (always)

1. Read `Oxford IRR Model Template.xlsx` from `OneDrive\Claude_Workspace\01_Cowork_OS\Cowork_OS_Workspace\` for the standard 5-tab structure.
2. Create a new file: `YYYYMMDD_[Address]_Model_v##.xlsx` (per ORA naming convention).
3. Populate all 5 tabs:
   - **Inputs** — purchase price, SF, units, in-place rents, vacancy, OpEx, CapEx
   - **Rent Roll** — per-tenant detail with escalations and renewal probability (cross-reference `tenant-intelligence` skill)
   - **Pro Forma** — 10-year cash flow
   - **Returns** — Unlevered IRR, Levered IRR, EM, CoC by year
   - **Sensitivity** — Exit Cap × Refi Rate matrix, plus Bear / Base / Bull on occupancy and rent
4. Flag any assumption deviating from ORA standards (3% rent growth, 5% vacancy, 7.5% exit cap).
5. Calculate: Unlevered IRR, Levered IRR, EM, Year 1 NOI, Price/SF, Going-in Cap Rate.

### Step 3d — Sensitivity Table (always include)

ScenarioOccupancyRent/SFNOICap RateYield on CostBear–10% occ–10% rent$%%Baseassumedassumed$%%Bull+5% occ+5% rent$%%

---

## MODE 4 — COMPS (formerly market-comp-analyzer)

Structured market comp grid for an acquisition candidate.

### Step 4a — Define comp set

- Property type: match subject (default shallow bay flex/warehouse)
- Geography: 5-mile radius or same submarket
- Size: ±50% of subject SF
- Timeframe: sales within last 24 months

### Step 4b — Pull comps

- Sources (in priority): CoStar (where available), Crexi, LoopNet, local broker sites, Notion `Acquisition Pipeline Tracker` (bcfe4a03) for prior ORA bids/closes, places_search for geography validation
- Per sale comp: address, sale date, sale price, price/SF, cap rate, SF, year built, occupancy at sale, buyer, seller, broker
- Target: 5–8 sale comps + 5–8 lease comps
- Per lease comp: tenant, address, SF, rent/SF (NNN vs gross), term, TI, free rent

### Step 4c — Market context

- Submarket vacancy rate and trend (cross-reference `market-monitor` skill)
- Average asking rent and rent growth
- New construction pipeline (12–24 months)
- Major employers and economic drivers
- Population/job growth trends

### Step 4d — Comp grid + valuation bracket

- Sale comps table sorted by relevance to subject
- Lease comps table sorted by date
- Adjustment narrative (subject premium / discount vs. comp average)
- Low / mid / high price/SF bracket
- Implied value range and recommended offer range

**Save as:** `Market-Comps [Address] [YYYY-MM-DD].html` in the deal folder; display summary in chat.

**Comp quality rules:**

- Prioritize flex/warehouse over office or retail comps
- Prefer multi-tenant over single-tenant comps
- Note portfolio sales (price/SF distorted)
- Flag comps older than 18 months as potentially stale

---

## MODE 5 — FULL (broker package → IC memo)

Run modes 1 → 2 → 4 → 3 in sequence. Then:

### LOI Generation

When the user says "draft the LOI" (or after FULL completes with PASS), **hand off to the `loi-generation` skill** — it is the SOLE LOI path (16-point QC Gate, four modular conditional blocks, seven state overlays, ORA letterhead + proof-of-funds). Do NOT draft an LOI inline here, via the `docx` skill, or from the generic `document-assembly` template library — any of those bypasses the QC Gate.

Pass `loi-generation` the deal context produced above (offer price + pricing basis, all-cash / no financing contingency, target DD and closing timelines, buyer entity). LOIs ALWAYS require Gabriel's approval before sending to a broker or seller.

### Due Diligence Checklist

Hand off to `deal-execution` skill at LOI executed → under contract.

### IC Memo

Auto-populate from Notion Acquisition Pipeline Tracker + the IRR model + comp grid. Use 12-section Blackstone-standard structure (per `document-assembly` skill).

---

## Deal Pipeline Tracking

- Stages: Sourced → Screened → LOI → Under Contract → DD → Closing → Closed (mirror in HubSpot + Notion `Acquisition Pipeline Tracker` bcfe4a03)
- Log broker contacts in `Broker Relationships` Notion DB (48e43778)
- Store deal files and underwriting models in SharePoint (M365 MCP)

## Output Formats

- **SCREEN**: inline pass/fail checklist
- **SNAPSHOT**: one-screen markdown table
- **UNDERWRITE**: XLSX workbook (5 tabs, ORA template)
- **COMPS**: HTML report + chat summary
- **FULL / IC memo**: DOCX (institutional style)
- **LOI**: via the `loi-generation` skill (sole QC-gated LOI path; requires Gabriel approval)
- **DD checklist**: Notion page (handoff to `deal-execution`)

## Proactive Flags (run in every mode)

- Basis below $60/SF — strong below-replacement-cost signal
- Environmental items requiring Phase II
- Tenant concentration risk (any tenant &gt;30% of building income)
- Markets showing rent growth acceleration or supply constraints
- Adjacent properties — opportunity to bundle for portfolio premium

## Cross-skill integration

- `rent-comp` — feeds MODE 4 with current submarket lease data (this skill subsumes the structured grid; `rent-comp` remains the data-pull utility)
- `tenant-intelligence` — risk scoring for in-place tenants in MODE 3
- `market-monitor` — submarket conditions and rate environment
- `legal-intelligence` — clause review when LOI/PSA is drafted
- `loi-generation` — SOLE LOI path (16-pt QC Gate + state overlays); route every LOI here
- `deal-execution` — hand off after LOI executed
- `document-assembly` — IC memo, demand letters (NOT LOIs — use `loi-generation`)
- `re-operations` — post-closing operational integration
