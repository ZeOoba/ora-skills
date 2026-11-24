---
name: "disposition-analysis"
description: "Use when the user mentions: should we sell, hold or sell, disposition, dispose of, exit an asset, recycle or prune the portfolio, 1031, like-kind exchange, replace an asset, refinance vs sell, harvest gains, cash out, when to sell, keeping vs selling a property, seller financing, depreciation recapture, or estate step-up — the Oxford Realty Advisors hold / refinance / 1031 / sell decision engine."
---

# Disposition Analysis — Oxford Realty Advisors (v1.4)

You are evaluating whether ORA should HOLD, REFINANCE, 1031-EXCHANGE, or make a TAXABLE SALE of an asset. ORA is a generational-hold family office; the burden of proof is on selling, and recycling is almost always done via 1031. Every analysis carries the tax overlay — a sale's "true" cost is the headline price minus the tax a hold would have avoided.

## Default posture (the thumb on the scale)
1. **HOLD + cash-out refinance is the default.** Debt is not income — a refi pulls tax-free liquidity without triggering gain, recapture, or forfeiting the step-up. Exhaust this before considering any sale.
2. **If capital must be recycled into a better asset, default to a 1031 exchange.** ORA almost always 1031s. This defers both capital gain and ALL recapture (§1245 + §1250) indefinitely via carryover basis.
3. **A taxable sale is the exception** — only when no like-kind replacement fits, the asset is structurally impaired, or a non-deferrable need exists. It must clear a high bar because it forfeits the step-up and crystallizes recapture.

## Workflow

### Step 0 — Pre-discussion fact pull (MANDATORY before any price, buyer or structure discussion)
No sale price, buyer approach, seller-financing term or 1031 plan is discussed until this block is filled. Each line cites its source document (executed copy, not drafts); anything not found = `[DATA-GAP: item]` and is listed as an open item, never estimated silently. Search the property folder (`Business\<Property>\`), the Corporate and Settlement folder, the Notion Property Register / Tenant Database rows, and the live Master Workbook.

| # | Item | What to pull | Typical source |
|---|---|---|---|
| 1 | **Ownership entity** | Title holder (deed), members/beneficiaries (operating agreement), trust status (grantor vs non-grantor; estate inclusion → step-up availability), who signs | Deed, operating agreement, trust docs; Property Register notes |
| 2 | **Tax basis** | Purchase price/date, 1031 chain (replacement? carryover basis from which property), accumulated depreciation, cost-seg (§1245 portion), capital improvements; adjusted basis | Settlement statement/HUD-1, QI exchange docs, depreciation schedule from CPA (Klein) |
| 3 | **Debt** | Balance, rate, maturity, prepay/defeasance, due-on-sale, guaranties; or confirm unencumbered | Payoff statement, loan docs, Master Workbook, title |
| 4 | **Leases** | EXECUTED lease: expiry, renewal options + notice deadlines, rent schedule, recoveries, guaranties/deposits, **ROFR/ROFO/purchase options**, assignment on sale | Executed lease + amendments (OCR scans if needed) |
| 5 | **Broker agreements** | Every listing agreement and commission letter touching the property: tail periods, **tenant-purchase clauses**, exclusives still open; compare signed copy vs redlines | Property folder: search Commission / Listing / Brokerage; email |
| 6 | **Other encumbrances** | Solar/roof leases, easements, ground lease, recorded restrictions, environmental | Title, CapEx log, Notion |
| 7 | **Taxes on transfer & reassessment** | Current assessed value vs likely sale price (reassessment risk to buyer/tenant); state + county transfer and recordation rates | Tax bill; county/state rate pages |
| 8 | **Market** | Current cap-rate range and $/SF sale comps for the submarket, dated and cited | Broker research (CBRE/C&W/Lee), recorded sales |

Output the block as a table at the top of every disposition memo, then proceed.

### Step 1 — Why is a sale on the table?
Classify the trigger: liquidity need (→ refi first), underperformance / structural impairment (→ 1031 into better basis), market-peak harvesting (→ 1031, rarely taxable), portfolio rebalance / concentration, or forced (partnership, estate, lender). The trigger sets which paths are live.

### Step 2 — Build the HOLD case
Forward 5–10-yr NOI, refi capacity at 65% LTV (tax-free proceeds available now), continued after-tax IRR on the held basis (REPS-qualified, no recapture — per Taxpayer Profile). This is the benchmark every disposition path must beat.

### Step 3 — Quantify the disposition tax (the charge)
Compute, per the Tax-Inclusive Standard recapture block:
- Amount realized (net of selling costs) → adjusted basis (cost − accumulated depreciation incl. cost-seg) → total gain.
- Decompose: **§1245 recapture** (cost-seg personal property, ordinary up to 37% + 3.8% NIIT) → **unrecaptured §1250** (building SL, 25% + NIIT) → **LTCG** (appreciation above cost, 20% + NIIT) → **+ state** (OH + apportionment).
- Total tax on sale, and the **forfeited step-up** (the income tax heirs would never have paid). The cost of a taxable sale = sale tax + the present value of the step-up given up.

### Step 4 — Compare the four paths
Side by side, after-tax to ORA:
- **HOLD + refi:** tax-free liquidity now; keeps step-up; continued NOI growth.
- **1031 exchange (default recycle):** defers gain + recapture; carryover basis (depreciation does NOT reset — continue old schedule on the replacement); net equity rolls 100%. Model the replacement's basis and go-forward depreciation. Watch **boot** (cash or debt relief = taxable to that extent) — structure to avoid.
- **Taxable sale:** net proceeds AFTER the Step-3 tax charge; only wins if the redeployment return on the smaller after-tax pile beats hold + 1031.
- **Estate/transfer (generational):** for next-gen assets, the step-up at death eliminates all recapture — usually dominates a lifetime sale; layer valuation-discount gifting of LLC interests (balance vs forgone step-up). Confirm the owner actually gets a step-up: assets of a non-grantor irrevocable trust outside the estate generally do not.
- **Seller-financed (installment) sale:** price it at its **cash-equivalent value** (PV of down payment + note payments + balloon at the buyer's market loan rate), never at headline. Required checks: (a) note rate ≥ applicable federal rate for the note term at contract (else imputed interest re-characterizes price); (b) **§453A** interest charge if installment notes arising in the year exceed $5M at year-end — size the note ≤ $5M where possible; (c) §1245/cost-seg recapture is recognized in the year of sale; unrecaptured §1250 gain comes out of the first payments (Reg. 1.453-12); (d) **the note is boot — it cannot be 1031-exchanged**; only cash at closing can go through a QI (hybrid: down payment via QI, note on installment method); (e) balloon refinanceability: buyer's balance at maturity vs 65% of realistic value; (f) collateral cushion: note ÷ market value (not ÷ contract price); (g) guaranty, escrows, due-on-sale, no secondary debt.

### Step 5 — 1031 execution guardrails (when recycling)
- Like-kind = any US real property held for investment/business → broad (industrial ↔ flex ↔ land ↔ retail all qualify).
- **45-day** replacement identification, **180-day** close (or tax-return due date). Use a **Qualified Intermediary** — seller cannot touch proceeds.
- **Equal-or-up rule:** replace equal/greater value AND equity AND debt to fully defer; any shortfall (cash or debt relief) = taxable boot.
- Reverse and improvement exchanges available if timing/identification is tight.
- Basis carries over (minus boot, plus new cash) → the replacement inherits a low basis and continues the old depreciation; factor this into the replacement's after-tax model.

### Step 6 — Recommendation
State HOLD / REFI / 1031 / SELL with the tax-charged numbers and the one-line reason. Default to the most tax-deferring path that meets the trigger; only recommend a taxable sale when it clears the hold-and-1031 benchmark after the full tax charge. Flag any boot, §461(l)/timing interaction, and the estate consequence. A SELL or 1031 PSA follows Gabriel's `debt-management` INTERIM aggregate-LTV checklist (`debt-management/references/ltv-interim-netting-checklist.md`).

### Step 7 — Log the ruling (2026-07-29)
Append one row to `memory/disposition-ledger.md` — the post-acquisition lifecycle ledger (Date | Property | Event | Terms/Amount | Rationale | Source). Event = the ruling (HOLD / REFI / 1031 / SELL); for a HOLD, Terms/Amount is "No transaction" plus the live refi lever if quantified. This is a DIFFERENT file from `memory/deal-decision-ledger.md`, which is scoped to PRE-acquisition pipeline decisions (PASS/SKIP/DROP/PARK/CLOSE) only — never write a disposition ruling there. If this is the property's first-ever row in disposition-ledger.md, also add the ACQUIRED baseline row (purchase price, date, source) before the new ruling row, so the ledger is self-contained per property.

## Conventions
- Pull defaults from the ORA Taxpayer Profile (REPS qualified, 1031 default, rates) and the Tax-Inclusive Underwriting Standard.
- Rates: §1245 ordinary 37% + 3.8% NIIT · unrecaptured §1250 25% + NIIT · LTCG 20% + NIIT · + state of the property/owner (OH apportionment; **MD: up to 6.5% + 2% capital-gains surtax, which reaches fiduciaries**). Confirm current law / state with CPA.
- Refi comparison uses the acquisition-underwriting refi rule (10-yr UST + 200 bps; ~7.0% in Nov 2026), never the retired fixed 6.50%. Value held assets at the market exit cap for their market from acquisition-underwriting (MD/DC 7.25%; sale-valuation band 6.75–7.50% in Nov 2026), cited and dated.
- Never present a disposition without the forfeited-step-up + recapture charge. Refi-before-sale is the default. 1031-before-taxable-sale is the default for recycling.
- Output: concise decision memo (paths table + recommendation); for a live decision, build the four-path after-tax comparison in the IRR model.

## Cross-skill
acquisition-underwriting (replacement-asset underwrite for 1031 targets) · deal-comparison (replacement vs hold) · the IRR model's Tax Analysis tab (recapture block) · portfolio-reporting (concentration/rebalance triggers) · disposition-ledger.md (Step 7 log, new 2026-07-29).

## Changelog

- v1.5 (2026-11-24): Added Step 0 mandatory pre-discussion fact pull (ownership entity, basis, debt, leases, broker agreements, encumbrances, transfer/reassessment, market) after the 55 New Plant Court review required each item to be dug up by hand — including a signed 2022 JLL letter granting 2% on a tenant purchase. Added the seller-financed/installment-sale path (cash-equivalent pricing, AFR, §453A $5M, note-is-boot 1031 conflict, balloon refinance test), MD tax rates, and the current refi/cap references. No governor constant changed.
- v1.4 (2026-10-26): Step 6 pointer: a SELL or 1031 PSA follows the `debt-management` v1.6 INTERIM aggregate-LTV checklist. Pointer only; no model, tax treatment, or trigger vocabulary changed. No governor constant changed (DSCR 1.25x; 40% aggregate; 65% per-property).
- v1.3 (2026-09-07): ORA Automation Audit R23-9-adjacent — reciprocal to debt-management v1.4. Added a one-clause deferral: once refi is chosen, EXECUTION (term sheets, lender selection) routes to debt-management. This skill keeps ownership of the strategic hold/refi/1031/sell call itself. No model, tax treatment, or trigger vocabulary otherwise changed.
- v1.2 (2026-08-24): Description trimmed to restore headroom (was 1001/1024,
  headroom 23 -- close-out work-order item 4). Dropped the implementation-detail
  clause naming the ledger file path (the ledger itself, and every tax/exchange
  rule clause, is unchanged); no trigger vocabulary removed.
  `description_budget.py` now reports headroom 73.