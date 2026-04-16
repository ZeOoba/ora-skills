---
name: underwrite
description: Build an IRR model for a new acquisition candidate. Use when evaluating a deal, running numbers on a property, or building a pro forma.
user-invocable: true
allowed-tools: Read Glob Grep Edit Write Bash WebSearch WebFetch
---

## Instructions

Build an Oxford-standard IRR acquisition model for the property described in the user's trigger message.

### Step 1 — Locate the template
Read the existing `Oxford IRR Model Template.xlsx` in the Cowork OS folder. Use its 5-tab structure and named ranges exactly — do not invent new tab names, new formula conventions, or new named ranges. If the template is not accessible, halt and tell Ze; do not attempt to reconstruct the template from memory.

### Step 2 — Gather deal inputs
Extract deal inputs from, in this strict priority order:
1. Documents attached to the current message (OM, flyer, broker email)
2. Data explicitly stated in the current user message
3. Prior messages in the current conversation
4. Notion Acquisition Pipeline Tracker, if a matching record exists by address

If a required input (purchase price, SF, in-place rent roll) is not available from any of these sources, ask Ze for it before proceeding. Do not substitute assumed values for missing purchase price, SF, or rent roll inputs. Non-critical inputs (OPEX line items, CapEx) may be populated with Oxford defaults defined in Step 5 below, clearly flagged.

### Step 3 — File naming and location
Create the Excel file at: `C:\Users\Owner\ORA\Operations\outputs\[Property Street Address] IRR Model [MM-YYYY].xlsx`
- Replace `[Property Street Address]` with the numeric and street portion only (e.g., "2530 Agriculture Drive"), no city/state/zip
- Replace `[MM-YYYY]` with the two-digit month and four-digit year of model creation (e.g., "04-2026")

### Step 4 — Populate all 5 tabs
- **Inputs**: Purchase price, SF, units, in-place rents, vacancy, OPEX line items, CapEx budget
- **Rent Roll**: Per-tenant detail with current rent, escalation schedule, lease expiration, renewal probability
- **Pro Forma**: 10-year monthly cash flow projection (120 periods), with annual summary row
- **Returns**: Unlevered IRR (XIRR with exact dates), Levered IRR, Equity Multiple, Cash-on-Cash by year, Year 1 NOI, Going-in Cap Rate, Stabilized Cap Rate, Yield on Cost
- **Sensitivity**: Exit Cap (5 scenarios) vs. Refi Rate (5 scenarios) = 25-cell matrix of Levered IRR

All cash flow formulas must be fully dynamic references to the Inputs tab. Zero hardcoded values in the Pro Forma, Returns, or Sensitivity tabs. Use the ORA color-coded cell convention: blue fill for hard inputs, black text for formulas, green for external links.

### Step 5 — Oxford standard assumptions (use these as defaults when inputs are not available)
- Rent growth: 3% annually
- Vacancy: 5% structural
- Exit cap rate: 7.5% (adjust for market and asset quality; document any deviation)
- Hold period: 10 years
- Acquisition costs: 2.5% of purchase price
- Management fee: 4% of EGI
- Reserves for replacement: $0.15/SF/year

Flag any input that deviates from these defaults at the top of the Inputs tab in a cell titled "Assumption Deviations."

### Step 6 — Compute and display required metrics
Compute and display in the Returns tab: Unlevered IRR, Levered IRR, Equity Multiple, Year 1 NOI, Price/SF (based on rentable SF from Inputs), Going-in Cap Rate (= Year 1 NOI / Purchase Price), Stabilized Cap Rate (= stabilized NOI / Total Basis), Yield on Cost (= Stabilized NOI / Total Basis).

### Step 7 — Self-audit before delivery
Before presenting the model to Ze, verify:
- [ ] All formulas reference the Inputs tab (no hardcoded numbers outside Inputs)
- [ ] XIRR uses exact dates, not period numbers
- [ ] Pro Forma monthly cash flows sum to annual totals (within $1 rounding)
- [ ] Sensitivity matrix has no #REF, #DIV/0, or #N/A errors
- [ ] "Assumption Deviations" cell lists every input that deviates from Step 5 defaults

If any self-audit item fails, fix it before presenting to Ze. Present the model only after all seven items pass.

### Target product
Shallow-bay flex/warehouse, multi-tenant, Mid-Atlantic / Ohio / Midwest.
