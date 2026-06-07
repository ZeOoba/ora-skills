---
name: cap-rate-snapshot
description: Quick NOI-to-valuation calculator. Cap rate, price/SF, and back-of-envelope IRR without a full model.
user-invocable: true
allowed-tools: Read Glob Grep Write WebSearch WebFetch
---

## Instructions

Perform a quick cap rate / valuation snapshot for the property described in $ARGUMENTS.

### Input
The user will provide some combination of: address, asking price, in-place NOI, SF, rent roll summary, or a Crexi/LoopNet link.

### Steps

1. **Extract or estimate key inputs:**
   - Asking price (or price range)
   - In-place NOI (or gross income minus estimated expenses at 35-45% ratio)
   - Total SF
   - Number of tenants / occupancy %

2. **Calculate core metrics:**
   - **Going-in cap rate** = NOI / Price
   - **Price per SF** = Price / SF
   - **Gross Rent Multiplier** = Price / Gross Income
   - **Replacement cost basis** = compare price/SF vs $80-120/SF new construction benchmark for shallow bay

3. **Sensitivity table** — show a 3x3 grid:
   - Rows: cap rates (going-in, +50bps, -50bps)
   - Columns: NOI scenarios (in-place, 5% upside, 10% upside)
   - Values: implied property value at each intersection

4. **Back-of-envelope IRR estimate** (5-year hold):
   - Assume 2.5% annual rent growth
   - Assume exit cap = going-in + 25bps
   - Assume 65% LTV at 6.5% interest rate
   - Output levered IRR and equity multiple

5. **Quick verdict:**
   - Compare to Oxford's target: 15%+ levered IRR, 2.0x+ EM, sub-$80/SF for shallow bay
   - **BUY RANGE** / **NEGOTIATE** / **PASS** recommendation with one-line rationale

### Output Format
Display results in a clean markdown table. Keep it to one screen — this is meant to be a 30-second read, not a full underwriting.
