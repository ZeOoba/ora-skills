---
name: capex-budgeting
description: "Use when the user mentions: capex budget, capital plan (building-system reserves — for AUM deployment capacity use portfolio-growth), reserve study, multi-year capital, capex schedule, capex forecast, building system replacement, capital reserve, replacement reserve, capex line item, sinking fund, deferred maintenance financial plan, or any task that requires building a capital plan beyond reactive maintenance — multi-year capital expenditure planning and reserve studies for Oxford Realty Advisors, bridging reactive maintenance into financial planning."
license: ORA Internal
---

# Capex Budgeting (v1.2)

Build multi-year capital plans and reserve studies that translate physical asset condition into financial cash-flow obligations.

## Scope

Covers capital plans of 3, 5, 10, and 30-year horizons across the portfolio. Outputs feed annual-cycle, the capex-reserve check in ora-am-brief Block D (Cash Position Snapshot, which absorbed ora-cash-position-snapshot), and lender reserve compliance tests.

## Triggers

Annual budget kickoff, refi reserve negotiation, property acquisition (initial 10-yr capex baseline), reserve adequacy review, deferred maintenance prioritization.

## Inputs

- **(no successor):** `maintenance-analytics` retired 2026-08-05 (zero-use) — predictive failure horizons by system need a manual source (vendor service records, warranty schedules, building-system age from the Notion property database)
- Notion property database (build year, last major capex, building systems)
- Vendor scoreboard (current cost benchmarks)
- QuickBooks capex history (actual vs. budget variance)
- Replacement-cost benchmarks (Marshall & Swift, RSMeans)
- Inflation assumptions (CPI shelter, construction)

## Standard Workflows

### Annual Capex Budget (next FY)
1. Assemble the next-12-month predictive maintenance forecast manually — `maintenance-analytics` retired 2026-08-05 with no successor named; source from vendor service records, warranty schedules, and building-system age.
2. Layer in deferred maintenance items prioritized by criticality.
3. Layer in tenant-driven capex (TI commitments from new leases).
4. Apply inflation to vendor estimates.
5. Output: per-property capex schedule (xlsx) with quarterly draws.
6. Roll up to consolidated capex budget for fund.

### Reserve Study (10-year)
1. Read the asset register from `capital-asset-register` (its Building Asset Register, or its interim `2026-09-17_AssetRegister-VendorPrequal_Register_v01.xlsx` while that Notion database is not created): roof age, HVAC tonnage and age, paving, parking lot, electrical, plumbing, fire/life safety, building envelope. Do not build a parallel register here.
2. Apply expected useful life by system (per RSMeans / industry).
3. Compute annual sinking fund contribution per property.
4. Surface concentration: any year where capex exceeds 1.5× baseline.
5. Output: 10-year reserve study DOCX (ORA Style) with appendix xlsx.

### Refi Reserve Negotiation
1. Lender typically requires X% of revenue or $/SF replacement reserve.
2. Build counter-proposal using ORA reserve study and historical capex actuals.
3. Output: lender reserve memo (DOCX) showing why ORA's plan is sufficient.

### Acquisition Capex Baseline
1. New acquisition under contract: build initial 10-year capex baseline.
2. Use property condition report (PCR) from DD.
3. Output: acquisition capex appendix (xlsx) added to deal IC memo.

## Outputs

- xlsx capex schedules with per-property and consolidated views
- DOCX reserve study for institutional delivery (lenders, LPs)
- Notion update: per-property capex schedule (mirror to Operations Hub)
- File naming: YYYYMMDD_[Property-or-Portfolio]_Capex-Plan_v##.xlsx

## Boundaries

- This skill PLANS capex; it does not commit funds. Vendor engagement and POs are governed by vendor-management skill.
- Forecasts marked [FORECAST] when projecting beyond 36 months.
- Inflation assumptions stated explicitly in every deliverable.

## Dependencies

- **(no successor):** `maintenance-analytics` retired 2026-08-05 — failure horizons need a manual source until one exists
- capital-asset-register skill (Building Asset Register, the reserve study's asset inventory)
- vendor-management skill (vendor cost benchmarks)
- xlsx skill (capex schedule models)
- docx skill (reserve study deliverables)

## Changelog
- **v1.2 (2026-11-05):** Reserve Study step 1 built its own asset register, duplicating `capital-asset-register`. It now reads that skill's Building Asset Register, or its interim xlsx while the Notion database is not created. The Scope line pointed at `ora-cash-position-snapshot`, which was folded into ora-am-brief Block D; it now points at that block's capex-reserve check. Pointers only, because a merge of the two skills is pending separately. No formula or reserve-study method changed. No scored or governor constant changed.
- **v1.1 (2026-08-12):** tombstoned the three dangling `maintenance-analytics` references left by that skill's 2026-08-05 retirement — predictive failure horizons are now an explicit manual source; no formula or reserve-study method changed.
