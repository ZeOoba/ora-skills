---
name: "annual-cycle"
description: "Year-end and annual planning cycle for Oxford Realty Advisors — twin to monthly-close. Use when the user mentions: year-end, annual close, annual budget, year in review, tax planning, annual report, 1099 cycle, K-1 prep, audit prep, year-end distribution, fiscal year close, annual cycle, personal 1040 review, or any task related to the firm's annual rhythm. v1.1"
---

# Annual Cycle

Coordinate the firm's annual rhythm: budget kickoff, year-end review, tax planning, audit prep, K-1 cycle, LP year-end communications, and (v1.1) the principals' personal-1040 review that every entity K-1 flows into.

## Scope

Calendar-year and fiscal-year activities that occur on an annual basis. Excludes monthly close (see monthly-close skill). The quarterly LP letter previously routed to investor-relations, which was retired 2026-09-09 (Gabriel, in-turn). No replacement owner has been assigned; treat it as manual until re-routed.

## Triggers

Annual budget assembly, year-in-review, year-end tax planning, K-1 distribution cycle, annual audit prep, year-end LP distribution, fiscal-year financial close, personal 1040 draft received.

## Cycle Calendar

| Month | Activity | Trigger |
|-------|----------|---------|
| Jan 5 / Apr 5 / Jun 5 / Sep 5 | Quarterly estimated-tax check (110% safe harbor + projection) | ora-quarterly-estimate-check |
| 1st business day, monthly | REP hour-log tally vs 750 h / >50% / 500 h tests | ora-rep-hours-monthly |
| September | Tax planning prep: projected K-1 income by LP; distribution headroom for tax payments | manual / IR review |
| September–October (on 1040 draft) | **Personal 1040 review**: K-1 tie-out + return lint, before e-file | manual: Personal 1040 Review workflow below |
| October 31 | Cowork audit refresh recommended | quarterly cadence |
| November 1 | Annual budget kickoff | ora-annual-budget-kickoff |
| November 30 | Vendor concentration audit, contract renewals review | manual via vendor-management |
| December 1–14 | Year-end distribution decision; final operating budget review; Q4 estimate sized off the estimate check | manual |
| December 15 | Year-in-review draft | ora-year-end-review |
| December 31 | Fiscal year close | monthly-close + manual |
| January 15 | 1099 prep deadline (mailing Jan 31) | accounting + vendor-management |
| January | Prior-year REP hour summary to preparer; depreciation schedule roll-forward | ora-rep-hours-monthly (Jan run); manual |
| February | LP K-1 prep with CPA; load entity K-1 figures into `k1_register.csv` | manual (investor-relations retired 2026-09-09) |
| March 15 | K-1 issuance to LPs (extended via 7004 if needed) | manual (investor-relations retired 2026-09-09) |
| April | LP communications post-K-1; tax-related Q&A | manual (investor-relations retired 2026-09-09) |

## Standard Workflows

### Annual Budget Assembly (November)
1. Pull TTM and 24-month P&L by property.
2. Apply rent steps from leases (deterministic).
3. Apply renewal probability × forecasted renewal rents (probability-weighted).
4. Layer in capex from capex-budgeting skill.
5. Apply OpEx growth assumptions (insurance, tax via tax-appeal pipeline, R&M).
6. Build per-property budget xlsx; consolidate to fund level.
7. Output: FY[YYYY+1] Operating Budget (xlsx) with executive summary memo (DOCX).

### Year-In-Review (December)
1. Full-year actuals vs. budget by property and consolidated.
2. AUM trajectory: starting AUM, deals closed, NOI growth, ending AUM.
3. Capital deployed YTD, capex completed.
4. LP distributions YTD; capital calls completed.
5. Forward look: next-year pipeline, capital plan, target deployment.
6. Output: Year-In-Review (DOCX, ORA Style) for LP communication and internal archive.

### Year-End Tax Planning (Sept–Dec)
1. Project taxable income per LP based on YTD activity and Q4 plan.
2. Surface tax-loss harvesting candidates (cost segregation, bonus depreciation, 1031 candidates).
3. Coordinate with CPA on 1031 timing if dispositions planned.
4. Price every deduction at the effective marginal rate on rental income, not the top statutory rate. For a REP with QBI that is about 37% × (1 − 20%) = 29.6% federal, with no NIIT. Maryland adds about 9.7% on MACRS but nothing on bonus depreciation, which Maryland disallows.
5. Output: tax planning memo (DOCX) for Gabriel.

### Personal 1040 Review (on receipt of each principal's 1040 draft — before e-file)
Tools live in `OneDrive…\Business\Taxes Estimated + Returns\_ora-tax-tools\` (README there).
1. **K-1 tie-out.**
   - Run `k1_1040_tieout.py --pdf <draft> --year <YYYY> --register k1_register.csv`.
   - Every entity K-1 amount (entity figure × share) must tie, and every QBI-eligible business must appear on Form 8995-A. Matching is by EIN, because statements relabel entities.
   - Exit 1: send each MISS or GAP to the preparer. Exit 2: the PDF has no text layer, so request a native PDF.
2. **Return lint**, checks the script cannot do:
   - **IRA vs. earned income:** any IRA or backdoor Roth contribution in a year with no W-2 and a Schedule C loss is an excess contribution. Correct it by the extended due date.
   - **NIIT consistency:** Form 8960 line 4b must treat every grouped rental the same way. A rental loss left in net investment income while the rental income is excluded understates NIIT.
   - **Exchanges:** every 1031 exchange in the year has a Form 8824 on the entity return. If there is no 8824, the 1040 must not show a deferred gain silently.
   - **Depreciation:** the Schedule E line 18 amounts tie to `ORA_DeprSchedule_Portfolio_v1.0.xlsx` (Return_TieOut sheet). The MD adjustment summary ties to its MD_Tracker sheet.
   - **Estimates:** the overpayment applied forward is no larger than the next year's safe harbor needs.
3. **Timing.** The review runs on the draft, not the filed return. Two of the three TY2025 fixes (IRA excess, QBI omission) surfaced on the extended due date (2026-10-15). Ask the preparer for drafts at least 10 days before the deadline.
4. **Output:** `YYYY-MM-DD_K1Tieout_TY<YYYY>_v01.md` in `Taxes Estimated + Returns\outputs\`. Add any open item to the project Tax Exceptions Log. Update the Individual Return Register in the Taxes + Settlement Statements project.

### Depreciation Schedule Roll-Forward (January, and on each acquisition)
1. Add each new acquisition to `ORA_DeprSchedule_Portfolio_vX.Y.xlsx` (Assets sheet) from its cost seg study: one row per class.
2. When returns are filed, enter the Form 4562 / Schedule E / Form 8825 amounts on Return_TieOut and the MD adjustment summary on MD_Tracker.
3. Any unexplained Diff goes to the Tax Exceptions Log.
4. Update the projection drivers in `estimates_config_<YYYY>.json` from the Summary sheet.

### K-1 Cycle (Feb–March)
1. Coordinate with CPA on entity-level returns.
2. Load each issued K-1's figures into `k1_register.csv` for the personal-1040 tie-out.
3. K-1 cover letter per LP. investor-relations (retired 2026-09-09) previously owned this template; use document-assembly or draft manually until it is re-routed.
4. K-1 distribution via secure channel; track receipt.

## Outputs

- All deliverables follow ORA Institutional Style Guide v1.0+
- File naming: YYYYMMDD_[Activity]_FY[YYYY]_v##.{docx,xlsx}; tax-tool outputs follow the session-output schema `YYYY-MM-DD_[Topic]_[DocType]_v##.ext` in `/outputs/`
- Mirror to SharePoint /Annual/[FY]/

## Boundaries

- Tax planning is advisory only; CPA executes.
- LP communications require Gabriel approval before send.
- 1031 exchanges require explicit Gabriel decision.
- The personal 1040 review reads and reports only. Corrections go through the preparer, and estimated payments are made only by the principals.

## Dependencies

- monthly-close skill (rolls up monthly into annual)
- portfolio-reporting skill (year-end metrics)
- capex-budgeting skill (capital plan)
- ~~investor-relations skill (LP communications)~~ — retired 2026-09-09, no replacement assigned
- tax-appeal skill (tax assumptions)
- cost-seg-tax-layer / disposition-analysis (after-tax rates; use the effective rental rate above)
- register-scheduled-task (ora-quarterly-estimate-check, ora-rep-hours-monthly)
- docx, xlsx, document-assembly skills

## Changelog
- **v1.1 (2026-10-15):** Added the Personal 1040 Review workflow, using the K-1 tie-out script and a five-point lint built from the TY2025 findings. Also added the depreciation schedule roll-forward, the quarterly estimate and monthly REP checks in the calendar, and the effective-rate rule for tax planning.
- **v1.0:** Initial annual cycle.