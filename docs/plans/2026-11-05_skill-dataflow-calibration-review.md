# Skill System Review: Data Flows, Calibration and Learning Loops (2026-11-05)

Scope: every skill in `ora-skills` at `3edcc5c0`, the live CC scheduled-task specs that read them, the store-only skills in the runtime cache, and the two Notion databases the acquisition and tenant loops write (Deal Sourcing Log and Tenant Database schemas read live, read-only, 2026-11-05).

The lens is new. The 2026-10-30 catalog review covered usage, overlap and size. `2026-11-05_skill-improvement-plan.md` covers staleness, conformance and token cost. This review asks three different questions:

- Does what one skill writes match what the next one reads?
- Are predictions checked against outcomes?
- Do lessons turn into doctrine that is then regression-tested?

Nothing here repeats either plan.

**Method.** Four read-only review threads (acquisition-funnel contracts, operations and finance contracts, calibration and learning loops, single-source-of-truth drift), followed by direct verification of every finding acted on. Live checks:
- The Notion schemas.
- The live fleet roster.
- The 2026-10-17 back-test package.
- The deal decision ledger.
- Session transcripts, searched for the staged v4.42 patch.

## Headline

**No learning loop is closed end to end today.** ORA's acquisition doctrine has an unusually complete capture design:
- immutable score snapshots;
- the lost-deal ledger;
- passed-deal clearing prices;
- RULE EVIDENCE with sunsets;
- the closed-deal variance review;
- the retro-underwrite dataset.

What it lacks is the part that turns captures into changes:
- **Nothing convenes the December back-test.** It is the only session where scorecard weights can move, and 14 Rule Evidence entries sunset at it (13 explicit, 1 by the single-incident default).
- **Its main input does not exist.** The BackTestDataset workbook was never built, and none of the five Pre-December checklist steps is done.
- **The staged December package is stale.** 22 of its 25 patches sit on stale bases.
- **The regression harness is stranded.** Its poll is disabled, so 19 doctrine versions have not been replayed since 2026-09-13.
- **A ratified ruling is missing.** The 2026-11-04 Falls Commerce rulings were recorded as "staged as v4.42 patch", and no such patch exists anywhere searched.
- **The outcome data the loops need is thin or polluted:**
  - ORA's own closings were never stamped `WON`, so the lost-deal sweep could read an acquisition as a lost bid.
  - The owner-outreach channel logged 0 responses on 277 letters in 90 days.
  - Velocity is measured only up to the LOI, and 0 LOIs went out in the trailing 90 days.

Data contracts also break at the funnel's front door:
- **The pre-screen misses five clusters.** `verified-deal-recon`'s prompt named only the seven holdings states.
- **The inbox triage agent has the same defect.** The `deal-flow-triage` agent in ora-claude-config carries the same state list.
- **The tenant loop writes to properties that don't exist.** The lease-abstraction upsert to Notion used property names the live Tenant Database does not have.

## What this change set does

| PR | Contents |
|---|---|
| This PR | `annual-cycle` v1.3: the Acquisition Doctrine Back-Test workflow and calendar rows; P&L source and output naming. `tools/backtest_agenda.py`: a read-only agenda compiler (Rule Evidence at sunset, with RULE EVIDENCE default sunsets; ledger integrity; decision-ledger lessons; staged-patch base status). `tools/doctrine_consistency.py`: a CI guard for cluster counts, target geography and DSCR-at-aggregate-LTV. `deal-retirement` v1.7: `WON` stamp, `Days LOI to Close`, variance-review marks. `verified-deal-recon` v1.4, `submarket-spatial-analysis` v1.11, `insurance-climate-risk-comparison` v1.2: geography and cluster count. Packaging: `annual-cycle` and `submarket-spatial-analysis` join `SHARED_ROOT_DEPS` (they now cite `target-markets.json`), `verified-deal-recon` is exempted in `skill_ci_gates.py` (it cites the file but reads nothing at run time), and the README diagram count follows. |
| Companion PR (asset-ops contracts) | `lease-abstraction-pipeline` upsert to the live schema plus `SOURCE_CLASS`; AR freshness gates (`exception-detection`, `document-assembly`); landlord signing entity from the Voice roster; Master Workbook first for debt and AUM (`debt-management`, `portfolio-reporting`); stranded-task pointers (`tax-appeal`, `capex-budgeting`). |

`acquisition-underwriting` is untouched. Editing it would take version v4.42, the number the ledger records for the unlanded 2026-11-04 rulings. Edits below its first `## ` heading also force an 18-agent harness run. Its reference fixes (L-F4, S2) ride its next version, and the drift guard allowlists them with that reason.

## Findings

Severity is business impact against ORA's priorities: acquisition velocity first, then operations, then institutional quality. Disposition values:
- **PR1** / **PR2**: fixed in this change set.
- **TASK**: a live scheduled-task spec edit, made through `register-scheduled-task`.
- **CFG**: an ora-claude-config change.
- **ASK**: Gabriel decides.
- **NEXT-AU**: rides the next `acquisition-underwriting` version.
- **LATER**: next review.

### L — Calibration and learning loops

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| L1 | HIGH | The December back-test has no trigger. 14 Rule Evidence entries are due at it: 13 with an explicit "December 2026" sunset, plus RE-4.30-1 by the single-incident default. `acquisition-underwriting` and `ora-passed-deal-tracker` both name `annual-cycle` as its home, and `annual-cycle` had no row, section or task for it. | PR1: workflow and rows, manual, Gabriel convenes. ASK: date and prep owner. |
| L2 | HIGH | No BackTestDataset exists on disk, and none of the Pre-December checklist steps is done. The ACQUIRED rows in `disposition-ledger.md` sit right at the n = 10 sample threshold, so one data gap drops the analysis back under INSUFFICIENT SAMPLE [FORECAST]. | ASK: prep owner. `annual-cycle` step 2 now names the checklist. |
| L3 | HIGH | The store-only `deal-log-refresh` step 5 rewrites `ORA Max Defensible Price`, Walk Price and score fields in place after an LOI. That breaks the immutability that `acquisition-underwriting` (OUTCOME FEEDBACK) and `loi-generation` Phase 6c rely on: hindsight bias in the only calibration channel. | LATER: capture the skill into git (catalog review F2), then add a freeze guard once `LOI Sent Date` or `LOI Outcome` is set. |
| L4 | HIGH | No skill ever wrote `LOI Outcome = WON`. A closed deal stayed `PENDING` on the tracker's lost-bid sweep, and its own recorded deed could become the "winning price". | PR1: `deal-retirement` step 2b. TASK: the tracker treats an ORA-LLC grantee as NONARMS. ASK: a one-time backfill of rows for deals already closed. |
| L5 | HIGH | The 2026-11-04 Falls Commerce rulings (Milwaukee exit row 8.75%; Amendment H premium inadmissible if any building is below its own floor; office-finish downtime) are marked "staged as v4.42 patch". No patch exists in the repo, the worktrees, the store, memory, `Claude_Workspace` or Code transcripts. It was probably staged in a Cowork session. A second claimant to the label exists: unmerged branch `claude/fix-ltv-enforcement-2026-10-17-f355fb` (`5c214ec3`, 2026-10-18) labels a pending-debt-register change v4.42 through v4.44. | ASK: locate or re-draft. It lands as the next `acquisition-underwriting` version with Rule Evidence lines and a harness run. See S7. |
| L6 | MED-HIGH | Lessons land in the sourcing scan the same day, but not in the scorecard. Three of the 10-30 REFINED rows are PARTIAL in `acquisition-underwriting`, and the 11-04 rows have not landed. | On the agenda: `backtest_agenda.py` section 3 lists every REFINED and VALIDATED row in the window. |
| L7 | MED-HIGH | The regression route is dark. `ora-acquisition-underwriting-eval-harness` is disabled; the last scheduled run was 2026-09-13 at v4.22. An ad-hoc run on 2026-09-29 FLAGGED REDACTED-119 at 16.67 against a golden of 26.81, with no review on record. | ASK: re-enable the poll, or run one supervised replay before December. `annual-cycle` step 5 adds the post-ratification replay. |
| L8 | MED | The 2026-10-17 December package has 22 of 25 patches on stale bases. All 14 doctrine patches are on v4.29 or v4.32 against the current v4.41, plus 8 consumer patches. | Surfaced by `backtest_agenda.py --patches`. Re-base before the session (`annual-cycle` step 1). |
| L9 | MED | Evidence-ledger integrity: `RE-4.40-1` is issued to two different rules. The `acquisition-underwriting` index has two v4.40 rows (and `loi-generation` two v1.16s; concurrent sessions). `RE-4.30-1` is single-incident with no sunset, and 22 entries are `[UNQUANTIFIED]`. | Surfaced by the tool. Re-key at the session; the `SKILL.md` body cites `RE-4.40-1`, so a re-key needs a harness run. |
| L10 | MED | The closed-deal variance review has no trigger. `deal-retirement` proposed +6/+12-month checks against the ratified 12/24/36. The two 2026 closings cross 12 months around 2027-01-28. | PR1: marks aligned, still proposal-only. ASK: register the checks. |
| L11 | MED | The command-center calibration loop never grades. `resolveDueOutcomes` runs only from `ora-calibration-snapshot`, which is disabled, so the next slot it could take is 2027-01-01. | ASK (new evidence for the 10-30 deferral). |
| L12 | HIGH-MED | The off-market channel captures no outcomes: 277 letters in 90 days, `outreach-responses.csv` absent, 16 call-sheet owners with 0 outcomes. The monthly conversion report did not run because the 11-02 driver hit a FATAL first. Parcel-score weights can never be calibrated. | TASK: run the conversion report independently and add an "unlogged letters" line to the email. The driver edit is in Business OneDrive (Invariant 5: needs permission). |
| L13 | HIGH | Velocity is measured only up to the LOI. 0 LOIs in the trailing 90 days. Stall detection (`ora-deal-command-board`, `ora-deal-aging-sla`) is disabled. `Days LOI to Close` was written only for lost bids (the tracker's Step 4b records the winner's close); ORA's own closings never wrote it. | PR1: `deal-retirement` writes it for ORA's closings, and notes that velocity reads must filter on `WON`. LATER: add LOI→PSA→close and channel conversion to the sourcing scorecard (Business OneDrive script: permission). |
| L14 | LOW-MED | Operating predictions have no loop: tenant risk and renewal probability, tax-appeal outcomes, remaining useful life, insurance quotes. | LATER: persist dated predictions first. |

### F — Acquisition-funnel contracts

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| F1 | HIGH | The pre-screen geography is the seven holdings states. Grand Rapids, Richmond, Des Moines, Louisville and Chicago read as out of scope, and TN reads as a target. LTV was given unqualified as "<= 40%". The same list is in ora-claude-config's `deal-flow-triage` (the broker-inbox gatekeeper, which PASSes on geography) and `deal-recon` agents. | PR1: `verified-deal-recon` v1.4 plus the CI guard. CFG: both agents (HIGH). |
| F2 | HIGH | `acquisition-proposal-generation` sends real offers (3700 REDACTED-158, $3.8M) but never writes the Sourcing Log fields. A losing proposal is invisible to the lost-deal ledger and the scorecard. | ASK, tied to catalog F6 (retire or keep). |
| F3 | MED | `loi-generation` Phase 6c writes `PENDING` plus an offer price at draft, while an unsent LOI is meant to be `EXPIRED-UNSENT` with a blank price. The only lapse detector (`ora-deal-aging-sla` 3c) is disabled, so drafts look like live bids to the tracker. | ASK. Recommendation: leave `LOI Outcome` empty at draft and let 7b set `PENDING` on a confirmed send. |
| F4 | MED | The back-test reference names "Clearing Price" and "ORA Walk"; the live properties are `Winning Price` and `Walk Price`. | NEXT-AU. `annual-cycle` step 3 carries the live names now. |
| F5 | MED-HIGH | The off-market master contract is undocumented. Its required columns live only in private builder scripts, and `owner-outreach` disagrees with its task on Notion writes and the stale guard. | LATER: `county-parcel-screen/references/master-contract.md`. |
| F6 | MED | The comps database moved to the Worker DB. The tracker and the sales-monitor task still cite the legacy DB and its 3-county coverage, and AU COMPS mode never reads either. | TASK, plus NEXT-AU (comp-grid pointer). |
| F7 | MED | `ora-entry-market-scan` writes a different field set from `ora-deal-sourcing-scan`: no `Ask at First Sighting`, `Construction Type` or `Listing URL`; hyphenated verdicts. Price cuts and construction checks silently skip entry-market rows. | TASK. |
| F8 | MED | The v4.37 construction-type sweep missed the sourcing scan and `ora-sourcing-construction-verify`. | TASK. |
| F9 | MED | Skills name disabled tasks as live readers: `ora-deal-aging-sla`, `ora-deal-command-board`, `ora-pm-ledger`, `ora-calibration-snapshot`. | PR1 (`deal-retirement`) and PR2 (`exception-detection`, `tax-appeal`). The rest: NEXT-AU and LATER. |
| F10 | LOW-MED | Several smaller funnel gaps. | LATER (pointers) and ASK (checkout state). |

F10 covers:
- `deal-comparison` uses its own GO vocabulary.
- The recon brief is never persisted.
- `ora-broker-touch-cadence` excludes brokers in Madison, Richmond and Chicago.
- `ora-cc-acq-sync-weekly` is a silent no-op: the command-center checkout sits on a stale branch without `acq-sync.ts`.

### O — Operations and finance contracts

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| O1 | HIGH | The lease-abstraction upsert writes properties that don't exist (`Lease End`, `Current Rent (monthly)`, `Guaranty`, `Property`, `Suite`) and one that is read-only (`Days Until Expiration`, a formula). It sets no `Lease Status`, so new rows fall out of the renewal pipeline and exception scans, and it writes Year-1 rent over current rent. | PR2. |
| O2 | HIGH | The Notion AR fields have no live producer: the DB names `pm-ar-aging-processor`, which is not on the fleet. They still drive exception scans and Templates 8–11, including the demand letter. | PR2: freshness gate. TASK: the `ora-am-brief` AR path. ASK: restore a producer. |
| O3 | HIGH | Debt figures come from a Notion debt schedule known to be stale, not the Master Workbook `External Loans Summary`. | PR2 (`debt-management`, `portfolio-reporting`). TASK: `ora-am-brief` Block D. |
| O4 | MED | Tenant letters take the landlord from a Notion select with firm-level options only, so they can sign as the firm, not the property LLC. | PR2: Voice roster. |
| O5 | MED | The annual chain names no P&L source; its naming did not match the tasks; it claimed a SharePoint mirror that no task does. | PR1 (`annual-cycle`). TASK: `ora-year-end-review` precondition path. |
| O6 | MED | The capital chain is empty end to end. `capex-budgeting` builds its own register. The "Capex & Contractor Pricing Ledger" cited by the variance review and `solar-lease-underwriting` exists nowhere. | PR2 (pointer). ASK: where the pricing ledger lives. The variance review's CapEx-actuals source should be the Notion CapEx & Maintenance Log (NEXT-AU). |
| O7 | MED | `SOURCE_CLASS` is consumed by `estoppel-request-generation` and never defined by its producer. | PR2. |
| O8 | MED | `lease-addendum` and `lease-generation` never write executed changes back to Notion, the abstract or HubSpot. | LATER. |
| O9 | MED | Live tasks depend on dark producers: the SOFR prefetch, the AR nudge, the tenant-HubSpot reconciliation and the `deal-aging-sla` query recipe. | TASK / ASK. |
| O10 | LOW | The `exception-detection` rent rule divides by SF twice, and $2.50/SF/month is $30/SF/yr, so it flags every tenant. | ASK: the threshold. |
| O11 | LOW-MED | Residuals found while fixing O1–O3. | LATER. |

O11 covers four residuals:
- An `UPLOAD`-class lease copy passes `lease-renewal-pipeline`'s source check, which looks only for `ARCHIVE COPY` and unexecuted.
- Lease dates have two owners: `rent-roll-reconciliation` Step 4 also overwrites the start and end dates.
- On create, the Year-1 rent is stale for a lease already past its first year. The schedule period covering today would be closer.
- `portfolio-reporting` still reads debt and NOI from Notion first (Loan Portfolio Tracker, Property Financials DB).

### S — Single source of truth and design

| ID | Sev | Finding | Disposition |
|---|---|---|---|
| S1 | HIGH | `portfolio-growth` tests DSCR at the 40% aggregate LTV instead of per-property sizing. `deal-comparison` v1.2 fixed the same defect with Gabriel's approval. | ASK (Invariant 4). The guard allowlists it with that reason. |
| S2 | MED | Cluster counts drifted ("ten canonical markets", "10 target-market clusters", "other 9"). | PR1 (`insurance-climate-risk-comparison`). The AU reference lines: NEXT-AU, allowlisted. |
| S3 | MED | Target geography was restated as the holdings states. | PR1 plus the guard. CFG: agents. |
| S4 | MED | Firm counts disagree: 26 vs 27 vs ~14 properties; 513K vs ~600K SF; ~$57M vs ~$60M AUM. | ASK: the canonical count for outbound and for internal use. |
| S5 | LOW | 8-character Notion short IDs collide (shared prefixes), and Ops Hub is labeled both page and DB. | LATER. |
| S6 | — | No existing probe checks semantic restatements (buybox and governor probes check numbers only). | PR1: `tools/doctrine_consistency.py`, run by `tools/run_suite.sh` in CI. |
| S7 | MED | Version labels collide between concurrent sessions: two `acquisition-underwriting` v4.40s, two `loi-generation` v1.16s, and two claimants to the next AU version (L5). An installed copy cannot be identified by version, and Rule Evidence IDs (`RE-<version>-<n>`) inherit the collision (L9). | LATER (CFG): allocate doctrine versions the way OI ids already are (`~/.claude/maintenance/allocate-oi-id.py`); `backtest_agenda.py` already reports duplicate labels. |

## What works and should not be touched

- **The lost-deal capture design.** It has three parts:
  - `ORA Max Defensible Price` fixed at LOI time;
  - the R1–R6 classifier;
  - the mandatory INSUFFICIENT SAMPLE banner.
- **The diligence-exit arm:** `TERMINATED-DILIGENCE`, plus the `Exclude from Calibration` and `Duplicate Of` loop.
- **The scan → construction-verify handoff key.** `Construction Type = Unknown — CONFIRM`, `CONSTRUCTION-CHECKED` and the done-file match across both specs.
- **RULE EVIDENCE itself:** the admission rule, sunsets and testable metrics. The agenda compiler only makes it operable.
- **Data discipline already in some tasks:** `ora-annual-budget-kickoff`'s Sources & Gaps tab, the T1–T6 tie-outs in `ora-master-workbook-ingest`, and the freshness gates in `ora-recovery-billing-monthly`. Other tasks should copy these.

## Follow-up work outside this repo

1. **ora-claude-config:**
   - geography in the `deal-flow-triage` and `deal-recon` agents;
   - a geography probe beside `buybox-drift-probe.py`, so agents and memory are guarded too.
2. **Scheduled-task spec batch (through `register-scheduled-task`):**
   - Passed-deal tracker: ORA-affiliated grantee as NONARMS, the Worker comps DB, the v4.37 pointer.
   - Entry-market scan field alignment.
   - Sourcing scan v4.37 multiplier.
   - `ora-am-brief` AR path and debt source.
   - `ora-year-end-review` precondition path.
   - Outreach conversion report.
3. **Store-only skills into git:** `deal-log-refresh` first (L3), then the rest (catalog review F2).
