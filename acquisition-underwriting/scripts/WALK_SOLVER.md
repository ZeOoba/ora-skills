# ORA Walk-Price Solver

Takes an offering memorandum (OM) to ORA's walk price in under a second, the same way every time. The solver inverts the acquisition-underwriting STAGE 1 floors (v4.49 / RCT v03) in closed form and reports which floor binds.

## Why it exists

Every walk price used to be re-derived by hand or by an LLM from a 395-line doctrine. That doctrine has had six pricing-relevant amendments since July (RCT v03, construction multiplier, the v4.33 unlevered IRR floor, the v4.37 UST+200 refi, the v4.40 vacancy premium and the v4.44/45 DSCR basis). The skill's own Pre-v4.37 walks rule already requires re-solving older walks. The command-center engine still uses a DSCR proxy and has no IRR leg. This tool is the deterministic reference: given the same inputs, it always returns the same walk.

## What it solves

| Leg | Max price such that… |
|---|---|
| Basis | all-in ≤ (1 − vintage floor 65%→60%) × (RCT LOW × construction multiplier × SF + land) |
| Yield | stabilized NOI (net of reserves) ÷ all-in ≥ 8.0% |
| IRR | 10-yr **unlevered** IRR ≥ max(10%, UST + 550 bps), +100 bps if majority-vacant |

`all-in = price × 1.02 + CapEx + lease-up carry`. **Walk = the lowest leg.** All floors are flags, not kills (Ruling 5).

It also reports, at the walk price:
- Refi proceeds, sized to the lesser of 65% LTV and 1.25x DSCR, at UST + 200 bps, 25-yr amortization and 1% cost, with the binding constraint.
- The DSCR floor test: DSCR at a 65%-LTV loan on stabilized NOI must be at least 1.25x.
- The breakeven exit cap below which DSCR binds.
- Levered IRR, reported only and never used as a floor.
- For Amendment H portfolios: per-building walks, their sum, and the largest premium that still clears blended YoC ≥ 8% and the portfolio IRR at the highest building floor.

## Use

Run from `acquisition-underwriting/scripts/`:

```bash
python -m ora_walk deal.json --fetch-ust          # live FRED DGS10 30-day avg (no key, no user data sent)
python -m ora_walk deal.json --ust 0.0452         # supplied UST (cite source/date)
python -m ora_walk walk_examples/example_portfolio.json --ust 0.0452 --json
python test_walk_solver.py                        # 60 tests; every doctrine constant pinned
```

`ora_walk/doctrine.py` pins SKILL.md v4.51 (v4.46 through v4.51 changed no governor or scored constant; v4.51 mirrors the Rollover Block tables; v4.49 moved the RCT figures to the private `rct-table.local.json`; the values date from v4.45). Any SKILL.md version that changes a constant mirrored there must update `doctrine.py` and the `DoctrinePins` tests in the same PR.

Deal fields (see `ora_walk/solver.py: Deal`): `name, sf, stabilized_noi` (pre-reserves, stabilization-year $), plus optional:
- Location and building:
  - `market` (aliases accepted).
  - `year_built`, `renovation_spend`, `renovation_year`: drive the R% effective vintage. An asserted `effective_vintage` can only tighten it.
  - `construction_type`: tilt-up, precast, cmu, brick, hybrid or pemb. Null means unknown and gets the strictest PEMB multiplier. There is no numeric override.
  - `adders`: named entries from the SKILL.md schedule. site_work and paving_lighting never stack.
  - `land_value`: Ruling 4, $0 until the FEMA determination lands.
  - `vacant_sf_at_close`: drives the majority-vacant premium.
- Cost and lease-up: `capex, lease_up_carry, in_place_noi, stabilization_year`.
- Pricing and exit: `ask_price, majority_vacant, exit_cap, sale_cost_pct, reserves_psf`.

Examples with synthetic data are in `walk_examples/`.

## NOI input basis (read this)

`stabilized_noi` and `in_place_noi` must already be net of the vacancy line, credit loss and the 4% EGI management fee. The vacancy line each year is MAX(5% structural, expected modeled downtime): the 5% is a floor, never added on top. For `in_place_noi` that downtime covers space vacant at close and in-place leases expiring in Year 1. The solver deducts only reserves. If you feed OM NOI at 100% occupancy, every leg is overstated.

NOI grows at the market Base of 2.5%. The 3% escalator is a contractual minimum, not a growth rate, and anything above 2.5% is flagged.

## Lease-up timing and rollover (v4.51)

Before v4.51 the solver treated stabilized NOI as arriving in full from the stabilization year and modeled no lease expiry, so when the IRR floor bound its walk ran about 12% above the full model (2026-11-14 Walker MI lease-up test: +12.5%). Five optional `Deal` fields close the gap:

| Field | Meaning | Default when omitted |
|---|---|---|
| `cash_rent_start_month` | First month of cash rent counted from close (after downtime and free rent). Year rent is pro-rated by months paid. | Off: whole-year stabilization as before |
| `lease_expiry_month` | Last month of the lease (or of the largest suite) inside the hold. Rollover then applies one time. | No rollover, flagged when a lease-up deal has none |
| `renewal_prob` | Probability the tenant renews. | Rollover Block (a) by SF band: ≤5K 65%, ≤10K 70%, ≤25K 72%, larger 75% |
| `rollover_downtime_months` | Downtime if it does not renew, including free rent. | Rollover Block (b): ≤10K 5, ≤25K 9, larger 12, plus 2 months free |
| `rollover_cost` | EXPECTED re-leasing TI + LC dollars at expiry (renewal and new weighted). | 0, flagged when the rollover year falls inside the hold or the exit year |

In each rollover month the expected rent loss is (1 − renewal_prob). The year's vacancy line is MAX(5% structural, expected downtime share), the same MAX rule as the model, so downtime is never stacked on the 5%. `rollover_cost` comes out of cash flow in the rollover year. Both feed the IRR leg and the refi sizing; the YoC and basis legs are unchanged.

For a deal where IRR binds, still confirm the walk against the full UNDERWRITE model. With these fields set, the test deal's walk came within 2.0% of the model.

## Guards against walks looser than doctrine

The solver raises an error for:
- negative cost inputs;
- `in_place_noi` with no lease-up year;
- an unknown construction type, or a repeated or stacked adder;
- an effective vintage that is in the future or earlier than the build year;
- an exit cap outside 3–20%.

It flags, rather than rejects:
- an exit-cap override below the market cap;
- growth above 2.5%;
- a lease-up deal with no `vacant_sf_at_close`;
- a lease-up deal with no modeled rollover (`lease_expiry_month` missing), labelled LOOSER THAN DOCTRINE;
- `rollover_cost` of $0 when the rollover year falls inside the hold or the exit year;
- `lease_up_carry` below the Lease-Up Block TI default alone ($8.00/SF × vacant SF at close);
- Year-1 NOI (`in_place_noi`, or stabilized NOI when modeled stabilized at close) above the occupied share of stabilized NOI, whenever `vacant_sf_at_close` is given. The share is SF pro-rata, grossed up for the 5% structural vacancy already netted into stabilized NOI and capped at stabilized NOI, so vacancy of 5% or less does not flag. It assumes no Year-1 rollover downtime on occupied suites.

The majority-vacant premium is derived from `vacant_sf_at_close`, and setting it to `False` cannot remove it.

In a portfolio, each building is re-tested at its walk plus its pro-rata share of the premium. Any building that breaches a floor is flagged by name.

## Conservative-by-default choices

| Missing or uncertain input | What the solver does |
|---|---|
| Vintage | Uses the strictest 65% basis floor. |
| Construction type | Applies 0.88 or 0.90 (strictest PEMB) and flags it. |
| Market without an RCT row | Uses the cheapest market's row (Chicago–Cook), the strictest floor. |
| Market without an exit cap | Uses 7.75% and flags it. |
| Reserves | Deducts $0.15/SF before both YoC and IRR. |
| Lease-up carry | Taken at t0. |
| Land | $0 unless supplied. |

## Governance

- `doctrine.py` is a read-only mirror of SKILL.md. If the two disagree, SKILL.md wins.
- `DoctrinePins` tests fail if a governor constant moves (Hard Invariant 4).
- Re-confirm the exit caps and the refi spread at the annual December back-test.
