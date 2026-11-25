---
name: "property-tax-timing"
description: "Use when an ORA underwrite's property tax lags the purchase: the first year is billed on the seller's assessment and the price reaches the base later (DC, Michigan). Builds the year-by-year tax line, the reset tax year and the A/B/C/PW assessment cases for the model and the walk solver. Trigger on: seller's bill first, tax reset year, DC tax year, new-owner petition, Michigan uncapping, Taxable Value uncaps, tax case A B C, probability-weighted tax. NOT a rate or assessment lookup (use ora-millage-lookup) and NOT an appeal filing or appeal-candidate sweep (use tax-appeal). The reassessment doctrine itself lives in acquisition-underwriting (UNDERWRITING CONVENTIONS, State Reassessment Matrix)."
---

# Property-Tax Timing (v1.1)

In some jurisdictions a sale does not reset the tax base on day one. ORA pays the seller's bill first, and the purchase price reaches the base only at a later tax year, through the assessor or an appeal. Modeling the at-price tax from Year 1 overstates Year-1 NOI and the walk. This skill builds the correct tax line. Companion to `acquisition-underwriting` (UNDERWRITING CONVENTIONS, property tax) and the State Reassessment Matrix.

## When
- Any UNDERWRITE / FULL in DC or Michigan.
- Any other state where the tax year differs from the calendar year or the base resets after a lag (add a profile first; never copy a neighbor).

## Tool
`acquisition-underwriting/scripts/prop_tax_timing.py` (vendored in acquisition-underwriting v4.61). The walk solver reads it through `property_tax` in component mode (`acquisition-underwriting/scripts/WALK_SOLVER.md`); a `growth` other than 2.5% or an `appeal_fee_pct` other than 30% must be declared in `cited_overrides` with its source (an MI CPI-based growth, for example). `schedule(Deal, years, case)` returns the calendar-year (model-year) tax; `dc_reset_ty(close)` returns the first DC tax year the price can reach; `excel_pattern(profile)` prints the workbook formula. Run `python prop_tax_timing.py` first: its tests must reproduce DC 1500 21st (CY2027 USD 62,606.24, CY2028 USD 34,866.56) and MI Walker (USD 25,177.51 / USD 50,343.75).

## Profiles
**DC.** Tax year (TY) runs Oct 1 to Sep 30 and is named by its ending year (TY2027 = Oct 2026 to Sep 2027). Annual 100% market reassessment. TY T is valued as of Jan 1 of T-1; notices by Mar 1; first-level appeal deadline Apr 1. A sale does not reset the base; it is evidence for the assessor or an appeal, and OTR often disqualifies sales from its model.
- Year 1: the assessment in force at close (pull it with `dc_parcel_pull.py`).
- Reset TY = the TY in force at close + 1. A new owner may petition for administrative review within 45 days of the purchase date (OTR), so a close after Apr 1 does not forfeit the next TY: file within 45 days of closing, or by Apr 1, whichever applies.
- Usual outcome: a full reset to the price is the optimistic tail. RPTAC reduced 3.6% (TY2023) and 8.5% (TY2024) of decided Class 2 appeals; practitioners cite 5-25% reductions when an appeal succeeds. Case B governs DC (below).
- Rate: Class 2 whole-value step (1.65% up to USD 5M, 1.77% up to USD 10M, 1.89% above). Add the BID rate (Dupont Circle about 0.0972% of AV) and public-space fees as separate lines.
- Calendar-year cost = 9/12 of TY(CY) + 3/12 of TY(CY+1) in full years.

**Michigan.** Tax year = calendar year (summer and winter bills on that year's Taxable Value, TV). Tax day Dec 31.
- Close year: the seller's capped TV x millage (calendar accrual; local closing custom may prorate on due dates).
- Year after transfer: TV uncaps to SEV (MCL 211.27a(3)); SEV is about 50% of true cash value. After that, TV grows by MIN(CPI, 5%).
- A >50% controlling-interest transfer also uncaps (211.27a(6)(h)). Run the Prop A pre-mortem line from the State Reassessment Matrix.

## Cases (every model carries all four)
- **A** base resets to the price (DC AV = price; MI SEV = 50% x price).
- **B** midpoint of A and C.
- **C** assessor's current value holds and grows (DC current AV; MI assessor SEV).
- **PW** probability-weighted; standing default 20/50/30 (A/B/C), reported only, never governs the walk (Gabriel 2026-11-24, revised the same day after the appeal-outcome evidence).
Governing case: **DC = B** where the assessment exceeds the price (acquisition-underwriting v4.61, RE-4.61-6); every other jurisdiction follows `acquisition-underwriting` (doctrine: reassessed at price, case A) unless Gabriel rules otherwise. Report A and C beside B in DC. Report the IRR, walk and Year-1 / stabilized tax per case. Put the appeal fee (default 30% of the first-year saving, `[EST]`) in the reset year for A and B.

## Workbook pattern
- Inputs: close date, in-place base, assessor value, rate or millage, add-on rates, growth, case selector, weights.
- A tax block above OpEx: AV by TY (per case), real-property tax, add-ons, appeal fee. The OpEx and Carrying Cost tab links to it.
- One live sheet per tax case for the Base scenario, plus a Sensitivity grid of scenario x case. The engine mirror (`uw_tieout.py`) covers every tax row.

## Checks
- Prior bills / AV equal the stated rate exactly (DC 1.65% ties to the cent). A mismatch means a rate tier or exemption is missing.
- Seller late payments (penalty lines) are a Seller/Motivation signal, never a buyer cost.
- Never trend the seller's bill forward as the stabilized tax. Never apply the price-based tax before the reset year.

## Changelog
- v1.1 (2026-11-24): script vendored into acquisition-underwriting/scripts (v4.61); DC governing case B and PW 20/50/30 (Gabriel in-turn 2026-11-24); routing tie-breaks added to the description. The v1.0 platform package bundled the walk solver's files instead of `prop_tax_timing.py`: repackage from this folder.
- v1.0 (2026-11-24): from 1500 21st St NW (DC) and 2900 Northridge, Walker MI. Gabriel in-turn: "A small skill or template for that pattern would help."