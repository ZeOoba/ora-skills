# ORA Walk-Price Solver

Takes an offering memorandum (OM) to ORA's walk price in under a second, the same way every time. The solver inverts the acquisition-underwriting STAGE 1 floors (v4.55 / RCT v03) in closed form and reports which floor binds.

## Why it exists

Every walk price used to be re-derived by hand or by an LLM from a 395-line doctrine. That doctrine has had six pricing-relevant amendments since July (RCT v03, construction multiplier, the v4.33 unlevered IRR floor, the v4.37 UST+200 refi, the v4.40 vacancy premium and the v4.44/45 DSCR basis). The skill's own Pre-v4.37 walks rule already requires re-solving older walks. The command-center engine still uses a DSCR proxy and has no IRR leg. This tool is the deterministic reference: given the same inputs, it always returns the same walk.

## What it solves

| Leg | Max price such that… |
|---|---|
| Basis | all-in − credited land ≤ (1 − vintage floor 65%→60%) × (RCT LOW × construction multiplier × SF); credited land = MIN(market land value, 60% × all-in) (v4.53) |
| Yield | stabilized NOI (net of reserves) ÷ all-in ≥ 8.0% |
| IRR | 10-yr **unlevered** IRR ≥ max(10%, UST + 550 bps) + stacked add-ons (v4.53): +100 majority-vacant, +100 single tenant / tenant >50% of rent, +50 tertiary market (Grand Rapids, Richmond, Des Moines) or satellite, +50 environmental-heavy use without a clean Phase II, +100 new operating competency |

`all-in = price × 1.02 + CapEx + lease-up carry`. **Walk = the lowest leg.** All floors are flags, not kills (Ruling 5).

It also reports, at the walk price:
- Refi proceeds, sized to the lesser of 65% LTV and 1.25x DSCR, at UST + 200 bps, 25-yr amortization and 1% cost, with the binding constraint.
- The DSCR floor test: DSCR at a 65%-LTV loan on stabilized NOI must be at least 1.25x.
- The breakeven exit cap below which DSCR binds.
- Levered IRR, reported only and never used as a floor.
- For Amendment H portfolios: per-building walks, their sum, and the portfolio walk. The solver computes the largest premium that still clears blended YoC ≥ 8% and the portfolio IRR at the highest building floor. Since v4.55 that premium is admitted only if every building still clears its own floors at its allocated price. Each walk already sits on its binding floor, so in practice the premium is rejected and the portfolio walk is the sum of walks.

## Use

Run from `acquisition-underwriting/scripts/`:

```bash
python -m ora_walk deal.json --fetch-ust          # live FRED DGS10 30-day avg (no key, no user data sent)
python -m ora_walk deal.json --ust 0.0452         # supplied UST (cite source/date)
python -m ora_walk walk_examples/example_portfolio.json --ust 0.0452 --json
python test_walk_solver.py                        # 116 tests; every doctrine constant pinned
```

`ora_walk/doctrine.py` pins SKILL.md v4.55 (v4.55 adds the Milwaukee exit cap row, `NON_CANONICAL_EXIT_ROWS` and the per-building premium test; v4.54 replaces the v4.52 pro-rata rollover with the branch-by-branch model and mirrors the renewal-economics, management-fee and credit-loss values; v4.53 added the 60% land-credit cap, the 3-comp minimum and the IRR add-ons; v4.46 through v4.52 changed no governor or scored constant; v4.49 moved the RCT figures to the private `rct-table.local.json`). Any SKILL.md version that changes a constant mirrored there must update `doctrine.py` and the `DoctrinePins` tests in the same PR.

Deal fields (see `ora_walk/solver.py: Deal`): `name, sf, stabilized_noi` (pre-reserves, stabilization-year $), plus optional:
- Location and building:
  - `market` (aliases accepted).
  - `year_built`, `renovation_spend`, `renovation_year`: drive the R% effective vintage. An asserted `effective_vintage` can only tighten it.
  - `construction_type`: tilt-up, precast, cmu, brick, hybrid or pemb. Null means unknown and gets the strictest PEMB multiplier. There is no numeric override.
  - `adders`: named entries from the SKILL.md schedule. site_work and paving_lighting never stack.
  - `market_land_value`, `land_comp_count`, `land_flood_cleared` (v4.53): land is credited only with ≥3 executed land comps and a flood determination that clears it (Ruling 4), capped at 60% of all-in. Never an assessor land field. Missing → `[DATA-GAP: land]`, USD 0.
  - IRR add-ons (v4.53): `single_tenant`, `satellite`, `environmental_heavy_use` (lifted by `clean_phase_ii`), `new_operating_competency` (MHC only; multifamily is always false since v4.60, RE-4.60-5). Each is true / false / null; null = not established, flagged DATA-GAP, add-on not applied (Gabriel ruling 2026-11-14). The tertiary add-on is derived from `market`.
  - `vacant_sf_at_close`: drives the majority-vacant premium.
- Cost and lease-up: `capex, lease_up_carry, in_place_noi, stabilization_year`, and optionally `cash_rent_start_month` (first month of cash rent after close; partial-year rent in the lease-up years instead of the linear ramp; `in_place_noi` is then the NOI before any lease-up rent). When `lease_expiry_month` is supplied, `stabilized_noi` nets exactly the 5% vacancy floor; the solver adds the modeled downtime itself.
- Rollover (v4.54, optional): `lease_expiry_month` with `gpr` (stabilization-year gross potential revenue: base rent plus recoveries, before vacancy), `lease_term_months`, `market_rent_ratio` with `base_rent`, `renewal_prob`, `rollover_downtime_months`, `rollover_cost`, and `no_lease_expiry_in_hold`. Probability and downtime default by SF band (Rollover Block (a)/(b)); downtime adds the Lease-Up Block's 2 months free. `rollover_cost` is the expected (renewal/new weighted) re-leasing TI + LC per expiry, in first-expiry dollars.
- Pricing and exit: `ask_price, majority_vacant, exit_cap, sale_cost_pct, reserves_psf`.

Examples with synthetic data are in `walk_examples/`.

## NOI input basis (read this)

`stabilized_noi` and `in_place_noi` must already be net of the vacancy line, credit loss and the 4% EGI management fee. The vacancy line each year is MAX(5% structural, expected modeled downtime): the 5% is a floor, never added on top. For `in_place_noi` that downtime covers space vacant at close and in-place leases expiring in Year 1. The solver deducts only reserves. If you feed OM NOI at 100% occupancy, every leg is overstated.

NOI grows at the market Base of 2.5%. The 3% escalator is a contractual minimum, not a growth rate, and anything above 2.5% is flagged.

Rollover (v4.54) is modeled only when `lease_expiry_month` is supplied, and the model is one whole-building lease: a multi-tenant rent roll stays in the full model's suite-level Rollover Block. Each month of a downtime window (the months after an expiry, for the downtime length) is dark with probability 1 - p, and a dark month loses the rent the new lease would earn at market (plus recoveries), not the renewal-weighted blend. Each year's vacancy line is MAX(5% of gross revenue, expected downtime revenue), on gross revenue: operating expenses stay paid while the space is dark, and only the management fee (4%) and credit loss (1.25%) move with EGI. The lease rolls again branch by branch, as the doctrine cash-flow method runs it: a renewal expires `lease_term_months` after the expiry, and a new lease's term starts after the vacant (b) downtime, with the 2 free months inside the term (Gabriel ruling 2026-11-14) and inside the vacancy line. Branches that expire in the same month merge exactly. With `market_rent_ratio`, base rent resets at each rollover: a renewal captures 50% of the gap to market and a new lease all of it, so the expected level moves (1 - 0.5p) of the remaining gap per rollover; market rent grows with in-place at 2.5%, so the gap is never compounded as growth. Rollover cost comes out of cash flow, never NOI, in the year of the expiry month (renewal TI/LC is committed before the lease ends), weighted by the probability that the expiring lease exists; later expiries grow it at expense growth. Downtime or a reset in the stabilization year moves the yield leg and the refi. At exit, year-11 downtime and reset are capitalized into the exit NOI (stricter than v4.52's one-time buyer credit for downtime), and the expected re-leasing cost of any year-11 expiry comes off the sale proceeds, so a cost never drops out when the expiry moves from year 10 to year 11. An expiry in month 132, the last month of year 11, is a year-11 expiry; a first expiry in month 133 or later rolls outside the modeled years and is a CHECK, not a rollover. A later expiry that `lease_term_months` pushes from month 132 into 133 or later drops out of the walk; only the second expiry is CHECK-flagged for that, so cite the term. Known limits: credit loss in the rollover delta is the 1.25% base case (on a 2.0% weak-credit deal a positive EGI delta is overstated by 0.75% of the delta); the solver has no bear-mode input, so when Stage 2.1 bear-mode is ON enter the Bear rollover parameters (renewal -10 pts, downtime +3 months) as overrides, both together: the downtime override alone can push an exit-year expiry past month 132, raise the IRR leg and draw a LOOSER flag; leasing commissions are not in the TI floor. For a deal where IRR binds, confirm the walk against the full UNDERWRITE model.

## Guards against walks looser than doctrine

The solver raises an error for:
- negative cost inputs;
- `in_place_noi` with no lease-up year;
- an unknown construction type, or a repeated or stacked adder;
- an effective vintage that is in the future or earlier than the build year;
- an exit cap outside 3–20%;
- (v4.54) a non-positive or non-integer month input; non-finite `gpr`, `base_rent`, `market_rent_ratio`, `renewal_prob` or `rollover_cost`; `renewal_prob` outside 0–1; a negative `rollover_cost`; `cash_rent_start_month` on a deal stabilized at close, after the stabilization year begins, or a full year or more before it (the stabilization year would be misstated); any rollover input without `lease_expiry_month`; `lease_expiry_month` before the stabilization year (the Lease-Up Block governs that space), without `gpr`, or in month 132 or earlier with `no_lease_expiry_in_hold`; `gpr` below stabilized NOI grossed up for 5% vacancy, 4% management and 1.25% credit loss (negative operating expenses); `lease_term_months` of 12 or less, or not longer than the downtime; `market_rent_ratio` without `base_rent` (or the reverse), outside 0.25–2.0, or `base_rent` above `gpr`.

It flags, rather than rejects:
- an exit-cap override below the market cap;
- growth above 2.5%;
- a lease-up deal with no `vacant_sf_at_close`;
- `lease_up_carry` below the Lease-Up Block TI default alone ($8.00/SF × vacant SF at close);
- any deal with no `lease_expiry_month` unless `no_lease_expiry_in_hold` is asserted (v4.54: no modeled rollover; for a multi-tenant rent roll the walk is not doctrine-complete);
- a `renewal_prob` or `rollover_downtime_months` override that raises any leg above the same deal solved at the Rollover Block (a)/(b) defaults (v4.54: measured, not assumed, since the direction depends on whether market rent is above in-place; cite the evidence);
- `gpr` equal to `base_rent` (CHECK: on a NNN lease gpr must include recoveries);
- `rollover_cost` below the TI floor per expiry, sf x (p x USD 1.50 renewal TI + (1 - p) x USD 8.00 new-lease TI) at the stricter (lower) of the band and override renewal probability, grown at expense growth to the first expiry year, for any expiry through year 11; LC on top (v4.54);
- `market_rent_ratio` above 1 (CHECK: cite the market-rent comp source);
- `lease_term_months` long enough that every second expiry falls past month 132 (CHECK: no repeat rollover is modeled; cite the lease or a broker opinion);
- overrides that the band defaults would reject as invalid (v4.54: the override is what makes the inputs valid);
- `cash_rent_start_month` before month 12, the Lease-Up Block default of 9 months downtime + 2 months free (v4.54: cite the signed lease or a broker opinion);
- a first expiry early enough that a second could land by month 132 with no `lease_term_months` (the next lease is never rolled), or any expiry before month 132, the end of the exit year, with no `market_rent_ratio` (no rent reset) (v4.54);
- Year-1 NOI (`in_place_noi`, or stabilized NOI when modeled stabilized at close) above the occupied share of stabilized NOI, whenever `vacant_sf_at_close` is given. The share is SF pro-rata, grossed up for the 5% structural vacancy already netted into stabilized NOI and capped at stabilized NOI, so vacancy of 5% or less does not flag. It assumes no Year-1 rollover downtime on occupied suites (suite-level rollover is not modeled; only a whole-building lease rolls, via `lease_expiry_month`).

The majority-vacant premium is derived from `vacant_sf_at_close`, and setting it to `False` cannot remove it.

In a portfolio, each building is re-tested at its walk plus its pro-rata share of the premium. Any building that breaches a floor is flagged by name. Any breach rejects the premium. When that happens, `premium_admissible` is false, `rejected_premium` is set and a PREMIUM REJECTED flag is raised. The breaches print as PREMIUM-TEST lines, not FLOOR-FLAGGED, because at the returned walk every building sits at its own walk. `portfolio_walk_price` falls back to the sum of walks, and `gap_to_ask` and the USD 15M gate read that figure (v4.55, RE-4.55-2).

A market with an exit-cap row but outside the canonical clusters (`NON_CANONICAL_EXIT_ROWS`; v4.55: Milwaukee WI) still gets the Off-cluster flag. The row sets the exit cap only.

## Conservative-by-default choices

| Missing or uncertain input | What the solver does |
|---|---|
| Vintage | Uses the strictest 65% basis floor. |
| Construction type | Applies 0.88 or 0.90 (strictest PEMB) and flags it. |
| Market without an RCT row | Uses the cheapest market's row (Chicago–Cook), the strictest floor. |
| Market without an exit cap | Uses 7.75% and flags it. |
| Reserves | Deducts $0.15/SF before both YoC and IRR. |
| Lease-up carry | Taken at t0. |
| Land | USD 0 unless ≥3 land comps and a cleared flood determination are supplied; flagged `[DATA-GAP: land]` / `[DATA-GAP: land comps]` / Ruling 4. |

## Component mode (v4.61, RE-4.61-3)

A deal JSON with a `components` list runs the Mixed-Use Component Lens (`ora_walk/components.py`):

```
python -m ora_walk walk_examples/1500_21st_St_NW.json --ust 0.05
```

- **Components.** Each component (`name, sf, use, core, rent_psf, growth, downtime_m, free_m, ti_psf, lc_pct, renewal_p, renewal_downtime_m, exit_cap, occ_cap`, plus `in_place_rent_monthly / in_place_bump / first_bump_month / lease_expiry_month` for an in-place lease, `lease_term_m`, `contract_bump`, renewal TI/LC, `renewal_capture` or `renewal_at_contract`, `services_psf`, `vacant_carry_psf`) runs a monthly expected-value schedule: lease-up from vacant at close, or the in-place lease to expiry, then renewal (probability p) or dark downtime + free rent + a new lease at market, repeated inside the 11 modeled years. Re-leasing TI + LC (LC on total lease consideration) lands in the year a new lease starts; renewal TI + LC in the expiry year (conservative side). A renewal at contract keeps the original bump calendar.
- **Building lines.** Vacancy = MAX(5% x GPR, modeled downtime and free rent) every year; credit loss on collected rent; management on EGI. Tax, insurance, R&M, reserves and `fixed_costs` allocate by SF; services and vacant carry by component; management by EGI share. Component NOI sums to building NOI. Below NOI: re-leasing cost and `capital_reserve`. All-in = price x (1 + 2% + `acquisition_tax_pct`) + capex; exit = year-11 component NOI / component exit cap, less `sale_cost_pct`.
- **Basis and Yield all-in** = price x (1 + 2% + `acquisition_tax_pct`) + capex + lease-up TI/LC + lease-up carry (downtime months x stabilized OpEx/SF x SF for each core component vacant at close; a vacant non-core component carries in its cash flow instead), always read on the Base case. The Yield leg reads NOI in `stabilization_year`, derived from the schedule: the first year with every vacant-at-close lease paying all 12 months and, under a DC/MI profile, every month past the tax reset (never a year still billed on the seller's base); a later supplied year is rejected.
- **Doctrine guards.** Every input that departs from its doctrine default (lease term 60 months, TI/LC, free rent, lease-up downtime, rent growth, contract bump, renewal probability/downtime/TI/LC/capture/contract renewal, office-finish, core for an office use, a supplied `stabilization_year`) is measured one at a time: reset to the default, both cases re-solved, LOOSER flagged when any leg was higher. An office component marked core is also flagged directly (lens (c)). `state` is required with `property_tax`; a supplied `stabilization_year` may not precede the tax reset year. Property-tax rate, add-on, growth and appeal fee are bounds-checked (a DC flat rate may not undercut the 1.65% Class 2 floor). A contract bump above 3%, or insurance / R&M at 0, is flagged LOOSER. Any non-default renewal capture or contract renewal is measured against the 50%-capture default. The Basis fields run through the whole-building validator (adders, vintage years, booleans, renovation, land). A non-core exit cap below the market's industrial exit cap is rejected; a core cap below it is flagged LOOSER THAN DOCTRINE. TI, LC, free rent, lease-up downtime, rent growth, renewal TI/LC and capture, reserves, credit loss, management and expense growth below (or above, for growth and capture) the Lease-Up / Rollover Block defaults are flagged; renewal probability / downtime overrides are measured against the defaults (office-finish components, inferred from `use` or set by `office_finish`, default to 12 months, v4.55).
- **Downside** (lens defaults, `[EST]`): non-core occupancy capped at 45%, rent -20%, exit cap +100 bps. Each case's walk is the lowest of Basis, Yield and IRR; the Basis leg uses the Base lease-up cost in both cases. `binding_walk` = the Downside walk (flagged if Base comes out lower).
- **`property_tax`** `{profile: DC|MI|at_price, close_date, current_base, assessor_value, case: A|B|C|PW, addon_rate, rate, growth, appeal_fee_pct}`: DC/MI months use `prop_tax_timing.base_for` (identical to `prop_tax_timing.schedule()` for a first-of-month close); the appeal fee (default 30% of the first-year saving) lands in the reset year for A/B/PW. The walk is always solved on the governing case (DC: B where `assessor_value` x (1 + growth), path C at the reset tax year, exceeds the walk, else A, RE-4.61-6; MI: A); DC takes no flat `rate` (the Class 2 step applies month by month), and a `state` of DC or MI must use its own profile; any other input case, PW included, is reported beside it under `input_case`.
- **`entity_tax`** `{rate, exemption, minimum, land_share, depr_years, cost_seg_5yr, cost_seg_15yr, improvements_life}`: unlevered entity tax (DC UBT: 8.25% rate, exemption and minimum tax per OTR; the fixture carries the figures) on NOI less depreciation (no bonus; building straight line with a mid-month first year, cost-seg shares on MACRS, capital items straight line half-year), losses carried forward, the sale gain taxed in year 10. The IRR leg solves after-tax unlevered IRR = floor by bisection (tax and depreciation move with price).
- **Not modeled here:** refi and levered returns (the full model owns them).

**Real RCT table:** DC has no RCT row, so the Basis leg uses the cheapest market's row (strictest) and binds the 1500 21st fixture far below its IRR legs; a DC or Mid-Atlantic row would change that.

**Fixture acceptance** (input-case IRR legs, `ComponentMode` tests; deal engine 2026-11-24, UST 5.00%): IRR legs Base tax A -0.05%, Downside tax A +0.15%, Base tax C +0.01% (all within 1%). Case B is tested at 2%: `prop_tax_timing` defines B as the midpoint of the price and the assessor value grown to the reset TY, while the v02 engine took the midpoint with the in-force AV (Base B -0.9%, Downside B -1.2% vs the engine's USD 532,529).

**Convention gaps vs the v02 engine** (all small at this deal): reserves grow with expenses here (the engine held them flat); retail new-lease rent is market at lease start, not the calendar-year market row; a new office lease after a non-renewal starts at market, not the renewal-branch rent; a year-11 re-leasing cost comes off the sale proceeds; office renewal rent captures 50% of the gap to market (doctrine) where the engine reset to market; renewal cost lands in the expiry year, the engine booked it in the renewal's first year; the appeal fee is 30% of the full bill saving (Class 2 step and BID), the engine used the 1.65% rate alone.

## Governance

- `doctrine.py` is a read-only mirror of SKILL.md. If the two disagree, SKILL.md wins.
- `DoctrinePins` tests fail if a governor constant moves (Hard Invariant 4).
- Re-confirm the exit caps and the refi spread at the annual December back-test.

## Migrating saved deal files

`scripts/migrate_deal_json.py <file-or-folder> [--dry-run]` updates saved deal JSON files for input changes the solver now refuses. v4.53: `land_value` becomes `market_land_value` with `land_flood_cleared`; `land_comp_count` is left unset, so the land credit stays at zero until at least 3 land comps are recorded. v4.54: a rollover deal with no `gpr` is reported, never guessed. Each changed file keeps a `.pre-v453.json` backup beside it.
