---
name: annual-cycle
description: "Use when the user mentions: year-end, annual close, annual budget, year in review, tax planning, annual report, 1099 cycle, K-1 prep, audit prep, year-end distribution, fiscal year close, annual cycle, or any task related to the firm's annual rhythm — Oxford Realty Advisors' year-end and annual planning cycle, twin to monthly-close. Distinct from portfolio-reporting, which owns investor and portfolio reporting deliverables. Powers the ora-annual-budget-kickoff (first business day of November) and ora-year-end-review (late February, prior fiscal year) scheduled tasks."
license: ORA Internal
---

# Annual Cycle (v1.3)

Coordinate the firm's annual rhythm: budget kickoff, year-end review, tax planning, audit prep, K-1 cycle, LP year-end communications, and (v1.1) the principals' personal-1040 review that every entity K-1 flows into.

## Scope

Calendar-year and fiscal-year activities that occur on an annual basis. Excludes monthly close (see monthly-close skill). The quarterly LP letter previously routed to investor-relations, which was retired 2026-09-09 (Gabriel, in-turn). No replacement owner has been assigned; treat it as manual until re-routed.

## Triggers

Annual budget assembly, year-in-review, year-end tax planning, K-1 distribution cycle, annual audit prep, year-end LP distribution, fiscal-year financial close, personal 1040 draft received, December acquisition back-test, scorecard back-test, back-test agenda, Rule Evidence sunset review.

## Cycle Calendar

| Month | Activity | Trigger |
|-------|----------|---------|
| Jan 5 / Apr 5 / Jun 5 / Sep 5 | Quarterly estimated-tax check (110% safe harbor + projection) | ora-quarterly-estimate-check |
| 1st business day, monthly | REP hour-log tally vs 750 h / >50% / 500 h tests | ora-rep-hours-monthly |
| September | Tax planning prep: projected K-1 income by LP; distribution headroom for tax payments | manual / IR review |
| September–October (on 1040 draft) | **Personal 1040 review**: K-1 tie-out + return lint, before e-file | manual: Personal 1040 Review workflow below |
| October 31 | Cowork audit refresh recommended | quarterly cadence |
| November, 1st business day | Annual budget kickoff | ora-annual-budget-kickoff |
| November, after the budget kickoff | Back-test prep: Pre-December checklist (BackTestDataset), agenda from `tools/backtest_agenda.py`, re-base of staged doctrine patches | manual: Acquisition Doctrine Back-Test workflow below |
| November 30 | Vendor concentration audit, contract renewals review | manual via vendor-management |
| December 1–14 | Year-end distribution decision; final operating budget review; Q4 estimate sized off the estimate check | manual |
| December, after the 15th | **Acquisition doctrine back-test**: the only session where scorecard weights move; floors and defaults ratified in-turn during the year are re-confirmed here | manual: Gabriel convenes; Acquisition Doctrine Back-Test workflow below |
| December 31 | Fiscal year close | monthly-close + manual |
| January 15 | 1099 prep deadline (mailing Jan 31) | accounting + vendor-management |
| January | Prior-year REP hour summary to preparer; depreciation schedule roll-forward | ora-rep-hours-monthly (Jan run); manual |
| February | LP K-1 prep with CPA; load entity K-1 figures into `k1_register.csv` | manual (investor-relations retired 2026-09-09) |
| February, last business day on or before the 28th | Year-in-review of the prior fiscal year (preconditions-gated) | ora-year-end-review |
| March 15 | K-1 issuance to LPs (extended via 7004 if needed) | manual (investor-relations retired 2026-09-09) |
| April | LP communications post-K-1; tax-related Q&A | manual (investor-relations retired 2026-09-09) |

## Standard Workflows

### Annual Budget Assembly (November)
1. Pull TTM and 24-month P&L by property from the Gabriel-ratified P&L staging folder `OneDrive…\Business\Property Financials\` (QuickBooks Desktop and PM-portal exports; never QuickBooks Online) and current rents from the live Master Workbook. State each source's as-of date; label a P&L file more than 60 days old STALE, the gate `ora-recovery-billing-monthly` already applies.
2. Apply rent steps from leases (deterministic).
3. Apply renewal probability × forecasted renewal rents (probability-weighted).
4. Layer in capex from capex-budgeting skill.
5. Apply OpEx growth assumptions (insurance, tax via tax-appeal pipeline, R&M).
6. Build per-property budget xlsx; consolidate to fund level.
7. Output: FY[YYYY+1] Operating Budget (xlsx) with executive summary memo (DOCX).

### Year-In-Review (late February, prior fiscal year)
Runs after the fiscal year closes, never in December: a December run reviews an incomplete year (anchor corrected 2026-04-28). `ora-year-end-review` checks first that full-year QuickBooks Desktop exports, the loan tracker, the CapEx log and closed-date pipeline data are in place, and sends a status memo instead of a review if any is missing.
1. Full-year actuals vs. budget by property and consolidated.
2. AUM trajectory: starting AUM, deals closed, NOI growth, ending AUM.
3. Capital deployed in the fiscal year, capex completed.
4. LP distributions for the fiscal year; capital calls completed.
5. Forward look: next-year pipeline, capital plan, target deployment.
6. Output: Year-In-Review (DOCX, ORA Style) for LP communication and internal archive.

### Acquisition Doctrine Back-Test (December, after the 15th)
`acquisition-underwriting` names this skill as its back-test home. Scorecard weights move only at this session; floors and standing defaults Gabriel ratified in-turn during the year are re-confirmed here, and every single-incident Rule Evidence entry sunsets here (its RULE EVIDENCE admission rule). No scheduled task convenes it: `ora-year-end-review` runs in February and does not cover it. Gabriel convenes it after the December run of `ora-passed-deal-tracker` (the 15th), whose clearing-price tabulation is one of its inputs. The method is `acquisition-underwriting/references/outcome-feedback-and-backtest.md`; read it before convening.
1. **Agenda (by December 10).** From the ora-skills repo run `python tools/backtest_agenda.py --session-date <YYYY-MM-DD> --patches <staged patch folder>`. It is read-only and lists the Rule Evidence entries at their sunset, evidence-ledger integrity problems (duplicate IDs, single-incident rules with no sunset), the REFINED and VALIDATED lessons in `memory/deal-decision-ledger.md`, and each staged patch's base status. A 2026 package was staged on 2026-10-17 at `OneDrive…\Business\Investment Candidates -- 2026\Claude outputs\2026-12_Backtest-Package\`; its doctrine patches were built on v4.29 and v4.32 and must be re-based before the session.
2. **Dataset (by December 10).** Work the Pre-December checklist in the reference: refresh realized marks from the live Master Workbook, enter the construction-cost deflator, score each closed deal from its at-acquisition documents, fill Variance_Review for deals past 12, 24 or 36 months, and add deals closed since. A missing input is a stated gap, never an estimate.
3. **Passed and lost deals.** On the Notion Deal Sourcing Log the live properties are `Walk Price`, `ORA Max Defensible Price`, `Winning Price`, `Winning Price Confidence`, `Loss Class` and `LOI Outcome`. Older text that says "Clearing Price" or "ORA Walk" means `Winning Price` and `Walk Price`.
4. **At the session.** Run the `market-monitor` drift sweep across every cluster in `target-markets.json`, record CONFIRMED / REFUTED / INCONCLUSIVE against each Evidence ID whose Testable metric has data, and take each proposed change to Gabriel. A ratified change lands as a new `acquisition-underwriting` version carrying its Rule Evidence line.
5. **After ratification.** One supervised `acquisition-underwriting-eval-harness` replay at its Opus floor. Goldens are re-baselined only on Gabriel's sign-off.
6. **Output:** `YYYY-MM-DD_FY[YYYY]_Backtest-Minutes_v01.md` in `Claude_Workspace\outputs\`: verdicts per Evidence ID, ratified changes, rejected proposals with reasons, and data gaps to close before the next December.

This workflow proposes nothing by itself and never edits doctrine. Weights, floors and standing defaults change only by Gabriel's ratification; governor constants (DSCR 1.25x; LTV 40% aggregate, 65% per-property) are outside its scope.

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
- File naming: `YYYY-MM-DD_FY[YYYY]_[Deliverable]_v##.{docx,xlsx,md}` in `Claude_Workspace\outputs\`, the form `ora-annual-budget-kickoff` and `ora-year-end-review` write (e.g. `2026-11-02_FY2027_Operating-Budget_v01.xlsx`); tax-tool outputs follow the session-output schema `YYYY-MM-DD_[Topic]_[DocType]_v##.ext` in `/outputs/`
- Mirror to SharePoint /Annual/[FY]/ by hand; neither scheduled task does this step

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
- register-scheduled-task (ora-quarterly-estimate-check, ora-rep-hours-monthly, ora-annual-budget-kickoff, ora-year-end-review)
- docx, xlsx, document-assembly skills
- acquisition-underwriting (back-test method and Rule Evidence ledger), acquisition-underwriting-eval-harness (post-ratification replay), market-monitor (drift sweep), `tools/backtest_agenda.py` (agenda)

## Changelog
- **v1.3 (2026-11-05):** Added the Acquisition Doctrine Back-Test workflow and its two calendar rows. `acquisition-underwriting` and `ora-passed-deal-tracker` both named this skill as the back-test's home, but it had no row, no section and no trigger, so the only session where scorecard weights can move had nothing to convene it, and 14 Rule Evidence entries sunset at it (13 explicit, 1 by the single-incident default). The workflow is manual (Gabriel convenes) and is fed by the new read-only `tools/backtest_agenda.py`. Also: Annual Budget Assembly step 1 names its P&L source and a 60-day staleness label; Outputs naming now matches what both tasks write; the SharePoint mirror is marked manual, since neither task does it. No scored or governor constant changed.
- **v1.2 (2026-10-30):** Year-in-review moved from December 15 to the last business day on or before February 28, matching the 2026-04-28 correction recorded in the archived task spec: a December run cannot review a complete fiscal year. Budget kickoff is now the first business day of November. Both tasks were re-registered on the CC/MCP fleet the same day (they had been registered on neither fleet). No governor constant changed.
- **v1.1 (2026-10-15):** Added the Personal 1040 Review workflow, using the K-1 tie-out script and a five-point lint built from the TY2025 findings. Also added the depreciation schedule roll-forward, the quarterly estimate and monthly REP checks in the calendar, and the effective-rate rule for tax planning.
- **v1.0:** Initial annual cycle.