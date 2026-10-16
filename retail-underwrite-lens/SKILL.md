---
name: "retail-underwrite-lens"
description: "Use when underwriting a retail strip or neighborhood center under ORA acquisition-underwriting FULL mode (Stage 2.9 alt-asset track) and the model needs the retail lens tabs: rent-basis cases, required-rent solve, rent grid, rent-normalization scenario, outlot option, comp-implied income value."
---

# Retail Underwrite Lens (template)

Layers on `acquisition-underwriting`. The industrial Basis/Yield/IRR floors stay the governing test; these tabs are lenses reported beside them. Origin: East Pointe Plaza, 2026-10-01, built by hand over three revisions. Build in this order so nothing is rebuilt.

## Tabs and sections

1. **Rent Roll tab** with printed Rent/SF, computed Rent/SF, implied base (printed x SF) and the per-suite gap, plus aggregate gap. Run rent-roll-qc Step 0A first.
2. **Rent-basis cases (formula-linked, live engines):** Base (roll base plus separate recoveries), Case A (roll all-in, no separate recoveries), Case K (P&L collected base plus recoveries). Each shows PGI rent, stabilized NOI, going-in cap, yield on cost, walk price (8% yield on cost), gap to ask, and levered/unlevered IRR and equity multiple at ask and at its own walk price from full re-levered engines. Default price-watch ceiling = evidence-weighted case.
3. **NOI bridge** from 2025A normalized NOI to stabilized NOI with a zero-tie to the Pro Forma, and the share of stabilized NOI resting on any unverified rent-roll gap.
4. **Required-rent solve:** blended gross rent per leasable SF that clears 8% yield on cost at the ask, holding ORA's vacancy, management, reserves and reassessed tax. Plus a $11-$15 rent grid (NOI, cap, yield on cost, price clearing 8%).
5. **Rent-normalization scenario:** capture percentage (default 50%) of the gap to a labelled [EST] target gross rent, phased over Years 2-4, with renewal TI and no LC; full engine at ask and at walk; walk price with uplift counted as NOI (labelled lens ceiling, not base).
6. **Outlot option:** NNN rent low/mid/high, value at an outlot cap, all-in cost including site work, net value creation, yield on cost. Option value only; flag entitlement, parking ratio and stormwater as unverified.
7. **Stage 2.9 income value:** comp-implied value at the market cap band, $/SF comp band, ask vs each; side-by-side with the industrial-floor lens.
8. **Trade area and traffic table** from the OM, verified against the OM image (road labels are easily mislabelled).
9. **Retail replacement-cost caveat:** RCT v03 is an industrial proxy; require insurance or contractor verification pre-LOI.

## Rules

- No retail deduction in scoring when the user says so; report Gate 6 as a flag.
- Static values are allowed only as labelled cross-checks; any IRR quoted in a lens must come from a live engine.
- Keep Base, Case A and Case K visible in the memo; never present only the most favorable.
- Rent-roll footnotes (ROFR, ROFO, options) and landlord-pays vacancy codes go in the tenant table and the carry term.
- Recalculate with 0 errors and zero ties before delivery; render the memo and scan for stale figures.