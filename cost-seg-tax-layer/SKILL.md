---
name: "cost-seg-tax-layer"
description: "Use when an ORA underwrite needs after-tax returns: cost-segregation allocation by property type (industrial/flex default, retail override), class-by-class recapture, and a per-state tax layer (WI, OH, IN, MD, MO, KS, TN)."
---

# Cost-Seg & State Tax Layer for ORA Underwrites

v1.1 (2026-10-17): land-allocation method selector, placed-in-service tax-year timing, 7-yr bucket fix and a workbook-vs-memo parity check, from the 8625 Troost Ave external reviews and v05 audit (the workbook used a 57.9% land share built from the Ruling 4 dry-land credit over a hard-coded county total while the memo's mirror used 75.2%; depreciation started in model Year 1 at 11.5/12 although the property was placed in service in December of the prior year). Origin: East Pointe Plaza FULL underwrite (2026-10-01), model v06. The flat 15% cost-seg share and the single hard-coded Wisconsin layer in v01-v04 were replaced by asset-class allocation, class-by-class recapture and a state table. Cost seg is TIMING, not value: it never changes NOI, pre-tax IRR, walk price or any floor test. Report after-tax IRR beside pre-tax, never instead of it.

## 1. Allocation defaults (% of acquisition depreciable basis = price + closing, ex-land)

All allocations are [EST] until an engineering study replaces them. Benchmarks are vendor sources, not primary; say so.

| Case | 5-yr | 7-yr | 15-yr | Total | Use |
|---|---|---|---|---|---|
| Industrial / flex (DEFAULT) | 7% | 0% | 8% | 15% | Shell-heavy, little interior finish; vendor baseline 12-18% (12-15% bare shell, 20-30% if fitted out with racking, power, heavy site work) |
| Retail conservative | 5% | 0% | 12% | 17% | Dated shell, tenant-owned finish |
| Retail strip BASE (override) | 8% | 1% | 17% | 26% | Strip centers 25-40% in vendor studies; parking, lighting, signage, drainage, storefront finish |
| Retail high | 13% | 2% | 22% | 37% | Above the ~32% scrutiny line (90th percentile); needs documentation |

Commercial interquartile range 22-28%; above ~32% draws scrutiny. Pick the property-type row, state which case is selected, and show the other cases as a band.

### 1A. Land allocation (v1.1)

Land is not depreciable, so the land share sets the whole depreciable basis. One selector on the Cost Seg tab picks the method, and every method is linked to the current price (never a hard-coded denominator):

| Method | Land share | Use |
|---|---|---|
| 1 Assessor ratio (DEFAULT) | county land value ÷ county total value, ALL land including SFHA/floodway | No appraisal allocation or study yet |
| 2 County land ÷ all-in basis | county land value ÷ (price + closing + CapEx), capped at 100% | Sensitivity; shows what a price above assessed value does |
| 3 Override | from an appraisal allocation or an engineering cost-seg study | Supersedes 1 and 2 when available |

Never use the acquisition-underwriting Ruling 4 dry-land credit in a tax calculation: it is a basis-test convention, and floodway land is still land for tax. Show the after-tax IRR under methods 1 and 2 as a band, and note when the county value was capped or is stale.

## 2. Federal mechanics

- 100% bonus is permanent for property acquired after Jan 19, 2025 (OBBBA). Used property qualifies if bought from an unrelated seller and not previously used by the taxpayer (IRS bonus FAQ Q3). Pre-1/20/2025 binding contracts stay on the old phase-down.
- QIP covers only improvements the taxpayer makes (lease-up TI), not the acquired building's existing interior. Cost-seg 5/7-yr carve-outs of an acquired building are bonus-eligible as used property.
- Recapture by class, never one lump: 5/7-yr = Section 1245 ordinary; 15-yr bonus in excess of straight-line = Section 1250 additional depreciation (ordinary); straight-line portion of 15-yr plus 39-yr = unrecaptured Section 1250 at 25%; remainder LTCG + NIIT 23.8%. Ordinary rate convention 37% (modeling convention, not Gabriel's bracket).
- NOT modeled, always flag: Section 469 passive-loss and Section 461(l) excess-business-loss limits (loss usability against ORA portfolio passive income needs CPA confirmation), AMT, federal deductibility of state tax / PTE elections, study cost.
- **Placed-in-service timing (v1.1):** drive the schedule by tax year from a placed-in-service month input, not by model year. 39-yr nonresidential: mid-month convention, so a December placement gives 0.5/12 of a year in that tax year and full years after; all bonus on 5/7/15-yr basis falls in the placed-in-service tax year (a 12/31 close puts it at t0, before model Year 1). Disposition year: mid-month (a December sale gives 11.5/12); state if not modeled and size it. Confirm acquisition and placed-in-service dates with the CPA.
- MACRS half-year tables: 5-yr .2000/.3200/.1920/.1152/.1152/.0576; 7-yr .1429/.2449/.1749/.1249/.0893/.0892/.0893/.0446; 15-yr (150DB) .0500/.0950/.0855/.0770/.0693/.0623/.0590/.0590/.0591/.0590/.0591/.0590/.0591/.0590/.0591/.0295.

## 3. State layer: five parameters per state

State/local combined marginal rate; SB = share of 5/7/15-yr basis the state lets you expense in Year 1; DR = share of bonus add-back recovered later over DN years (from Year 2); gain exclusion on non-recapture gain; gain surtax. State depreciation = SB x classBasis (Yr 1) + (1-SB-DR) x MACRS + DR x classBasis/DN (Yr 2..1+DN) + 39-yr straight line. State ordinary recapture = state class depreciation in excess of 15-yr straight-line. State sale tax = rate x ordinary recapture + (rate x (1-exclusion) + surtax) x remaining gain.

| State | Rate (as modeled) | Bonus | Gain treatment | Confidence |
|---|---|---|---|---|
| WI | 7.65% | Decoupled (2014 IRC): SB 0, regular MACRS | 30% exclusion of net LTCG | PRIMARY (WI DOR) |
| OH | 3% business rate above $250K business-income deduction + municipal ~2% [EST] | Decoupled: 5/6 add-back (6/6 if NOL), recovered 1/5 per year over 5 years -> SB 1/6, DR 5/6, DN 5 | No exclusion found | PARTIAL: municipal tax and rental-income business classification unverified |
| IN | 2.95% (2.90% in 2027) + county (Marion 2.02%; range 0.5-3.0%) | Decoupled (S.B. 243, 2026): add-back then regular MACRS | No exclusion found | PARTIAL: county tax on nonresident passive rental income and statute mechanics unverified |
| MD | 6.5% top (5.75% above $250K) + county ~3.2% [EST] (range 2.25-3.3%) | Decoupled since 2002; subtraction schedule unverified -> modeled as regular MACRS | 2% surtax on net capital gain when AGI > $350K | PARTIAL |
| MO | 4.7% (2026 conflicts: 4.7 vs 4.8) | Appears to conform: SB 1 | 100% capital-gain deduction from 2025 (HB 594); unrecaptured Sec 1250 eligibility unverified | PARTIAL |
| KS | 5.58% (SB 269 step-down trigger unverified) | Appears to conform: SB 1 | No preferential rate | PARTIAL |
| TN | No individual tax; 6.5% excise on LLC net earnings (entity level) + 0.25% franchise on net worth (NOT modeled) | TCJA phase-down only: 20% for 2026 (TN DOR Notice 23-07); did not adopt OBBBA 100% -> SB 20% | Gain in net earnings, no exclusion | PARTIAL: family-owned non-code LLC exemption (T.C.A. 67-4-2008) unverified and potentially decisive |

Rules: (a) every state row carries a retrieval date and source; re-verify each tax year, since rates and conformity change with each legislative session. (b) A PARTIAL row is [EST]; never present as settled. (c) For any state not listed, add a row only after reading the state DOR bonus-depreciation guidance; never copy a neighbor. (d) Local taxes fold into the combined rate; say which locality was assumed. (e) Selector, not hard-code: one input chooses the state row for the whole model; run all rows side by side to show the spread (East Pointe: Maryland heaviest at about -34 bp 5-yr / -76 bp 10-yr after-tax vs federal only; Missouri lightest at about -3 / -5 bp).

## 4. Model build pattern (openpyxl + LibreOffice recalc)

- Cost Seg tab: benchmark table with sources, case table (rows read by an Inputs INDEX selector), live results from per-case engines, MACRS tables, rules and caveats.
- State Tax tab: one row per state with the five parameters, confidence, source and note; a live by-state results table from per-state engines.
- Engine rows: acquisition basis (from the §1A selector); class bases 5/7/15 — 5-yr and 7-yr together form the §1245 bucket in DOLLARS (basis × share; never add a percentage to a dollar cell), 15-yr includes the 15-yr share of deferred-maintenance CapEx and lease-up TI as QIP — and 39-yr; a t0 (placed-in-service year) column for bonus and the partial-year 39-yr amount, with its tax effect in the t0 after-tax cash flow; federal depreciation; state depreciation; federal and state tax; exit block by class with a tie row (class depreciation minus cumulative depreciation = 0).
- Verification: an independent Python mirror must reproduce every after-tax IRR to 4+ decimals for every case and state, from the workbook's own cells (land share, bases, timing) — the memo quotes the workbook, and the mirror proves it; pre-tax IRR must be identical across cases; duplicate-key assertion on Returns lines.

## 5. Output block

State the case and state selected, the land-allocation method and share (with the method-2 band), the allocation total, placed-in-service-year federal depreciation, after-tax levered IRR 5-yr/10-yr federal and federal+state, Delta vs no cost seg in bp, ordinary recapture at sale, and every unverified item as [EST] with the CPA question. Tag [SPECULATIVE] / [FORECAST] per ORA register. Recommend an engineering study before relying on any case.