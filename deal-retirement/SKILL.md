---
name: deal-retirement
description: "Use when a deal closes or is killed and its deal-bound artifacts, scheduled tasks, and Notion staging records need retiring and the DD package archiving to SharePoint. Use when the user mentions: deal closed, deal killed, deal dead, post-closing cleanup, retire deal, archive deal, sunset deal artifacts, deal lifecycle, close-out, post-mortem, or any task related to retiring assets associated with a completed or terminated deal."
license: ORA Internal
---

## Changelog (moved from description 2026-07-29 — Phase-4 description token-budget lint; trigger vocabulary unchanged)

v1.7 (2026-11-05, Gabriel-approved write-once first-sighting rule, business-loops review F-11 — new Killed-workflow step 3e: this skill never writes `Verdict at First Sighting` or `Score at First Sighting` (blank on a row it creates, untouched on a row it updates; a retirement is not a scan prediction), a pass is recorded as `Go / No-Go` = 🔴 Pass and never as `Status = Dead`, and `Dead` is reserved for a listing that is gone; close-out checklist gains the matching line. No score, weight, gate, floor or governor constant changed (DSCR 1.25x; 40% aggregate; 65% per-property).)

v1.6 (2026-10-26, Gabriel-directed — Killed-workflow step 4b prompts Gabriel to mark a killed deal's row on the `debt-management` INTERIM aggregate-LTV ledger WITHDRAWN; pointer only, no other step changed. No governor constant changed (DSCR 1.25x; 40% aggregate; 65% per-property).)

v1.5 (2026-09-19, Gabriel-directed — new Killed-workflow step 4a tags an ORA-side diligence exit after LOI/PSA as `LOI Outcome = TERMINATED-DILIGENCE` rather than `LOST`, so the row reaches `ora-passed-deal-tracker`'s new Step 4e diligence-exit classifier instead of Step 4b's clearing-price classifier, which has no operand where no competitor ever bid. Evidenced by `E Fulton St Portfolio` (Sourcing Log row `37a6ecd8-9e59-8156-912e-dd9680cb1660`): PSA executed $4.0M 2026-04-21, ORA terminated 2026-07-09 on its own AEI Phase II environmental finding, no competing bidder — routed to `LOST` on 2026-09-19 and would have produced a permanent unfillable `UNCLASSIFIED` every month. Spec: `Claude_Workspace/02_Outputs/2026-09-19_TrackerSpec_DiligenceExitArm_Proposal_v01.md` §3.2); v1.4 (2026-09-19, Gabriel-directed — three process gaps surfaced by the 808 Rhoads pass, evidenced in `Claude_Workspace/02_Outputs/2026-09-19_808Rhoads_PassRecord_v01.md` §5: (1) the Killed workflow's old step 3 pointed at a Notion Knowledge Base "Deals Passed" log that does not exist and that nothing reads — repointed to the Deal Sourcing Log row, which is now the named canonical passed-deal record; (2) the workflow wrote only the Pipeline Tracker and the memory ledger while `ora-passed-deal-tracker` sweeps only the Sourcing Log, so a Pipeline-only deal passed without an LOI fell out of the monthly trade sweep entirely — new step 3 makes the Sourcing Log row mandatory, with an existence check, the exact field mapping, and a close-out checklist; (3) no watch-date convention existed for a passed deal — new step 3d fixes one); v1.3 (2026-07-29: Closed Deal Retirement step 9 now appends an ACQUIRED baseline row to memory/disposition-ledger.md, the new post-acquisition lifecycle ledger); v1.2 (2026-07-18: proposes an inline ora-calibration-snapshot trigger, a PROPOSED underwriting-defaults delta vs standards.md Part A, and two proposed +6mo/+12mo actuals-check tasks — all proposals, nothing self-registers); v1.1 (2026-07-16: closing/kill appends to memory/deal-decision-ledger.md)

# Deal Retirement (v1.7)

Lifecycle hygiene skill that retires deal-bound artifacts, scheduled tasks, Notion staging records, and DD packages once a deal closes or is killed.

## Scope

Triggered on deal lifecycle terminal states: CLOSED (acquisition completed) or KILLED (deal terminated before closing).

## Triggers

"Deal closed", "deal killed", "deal dead", "we passed", "retire [deal name]", "archive [deal name]", "post-closing cleanup".

## Inputs

- Deal name / Notion Acquisition Pipeline record
- Closing or kill date
- Deal-specific artifacts (e.g., efulton-dd-tracker)
- Deal-specific scheduled tasks (e.g., efulton-retire-partial-dashboard)
- DD package location (typically SharePoint /Acquisitions/[deal]/)

## Standard Workflows

### Closed Deal Retirement
1. Confirm closing in Notion Acquisition Pipeline; capture closing date and final terms.
2. Update Notion: deal moved from Acquisition Pipeline to Portfolio (with new property record).
3. Move DD package: SharePoint /Acquisitions/[deal]/ → SharePoint /Portfolio/[property]/Acquisition-DD/.
4. Retire deal-specific artifacts: list_artifacts → identify any with deal slug → archive (delete or move to ora-archive folder).
5. Disable deal-specific scheduled tasks via update_scheduled_task with enabled=false.
6. Add property to active operating workflows: lease-renewal pipeline, monthly close checklist, insurance renewal calendar, tax appeal calendar.
7. Schedule one-time post-mortem task at +90 days post-closing.
8. Append a row to `memory/deal-decision-ledger.md` — Verdict = CLOSED, one-line reason (e.g. "closed at $X, financed via Y"), and buy-box rule validated/refined if the deal confirmed or stress-tested a governor or screening heuristic.
9. **[v1.3] Append the ACQUIRED baseline row to `memory/disposition-ledger.md`** — Date = closing date, Property = property address, Event = "ACQUIRED", Terms/Amount = purchase price + financing structure (1031 QI / seller-financed / assumed loan / unencumbered, as applicable), Rationale = "Baseline acquisition", Source = settlement statement or closing memo. This is a DIFFERENT file from step 8's `deal-decision-ledger.md`, which stops at the CLOSED verdict — `disposition-ledger.md` is where the asset's life continues from here (future HOLD/REFI/1031/SALE rulings from disposition-analysis land in the same row-per-event). Do not skip this step believing step 8 already covers it; the two files have no overlap by design (see disposition-ledger.md's own "Scope boundary" note).
10. Compare the closing deal's final underwriting assumptions (vacancy, escalation, TI/LC, capex reserve, exit-cap spread, replacement cost) against `memory/standards.md` Part A's underwriting-defaults table. If actuals diverge meaningfully from the table, flag it — don't silently overwrite a ratified default without Gabriel's confirmation.
11. **[v1.2] Propose triggering `ora-calibration-snapshot`'s scoring logic inline (PROPOSAL — do NOT run unconfirmed):** rather than waiting for the next quarterly cron (1st of Jan/Apr/Jul/Oct), propose to Gabriel running the same observational logic this closing deal would otherwise wait a quarter to feed — `cd C:\Users\Owner\oxford-command-center && npx tsx scripts/calibration-snapshot.ts --task ora-deal-retirement-<deal-slug> --json` — and wait for his go-ahead before executing it. This is the same "propose, don't self-execute" discipline as step 13, not an exception to it: this script writes to the calibration warehouse DB (`resolveDueOutcomes` + `logVerdicts`), so running it is a write action, not a read. **Caveat to surface with the proposal, not silently assume away:** the quarterly cron's own logged verdicts use `emittedBy='snapshot:ora-calibration-snapshot'` for its idempotency dedup; an inline run tagged `--task ora-deal-retirement-<deal-slug>` will carry a different `emittedBy` value and is NOT guaranteed to dedupe against that quarter's later cron run for the same property — flag this explicitly to Gabriel rather than asserting no double-logging risk. If run, inherit that task's own read/observe/log discipline verbatim (`C:\Users\Owner\.claude\scheduled-tasks\ora-calibration-snapshot\SKILL.md`): the script is OBSERVATIONAL ONLY and never throws; it resolves due outcomes and logs current verdicts — it does NOT touch `intel-config.ts`, health weights, or DSCR/LTV governors, and this step doesn't either.
12. **[v1.2] Underwriting-default delta proposal — PROPOSED ONLY, never auto-written (Hard Invariant 4: `standards.md` Part A is a governor-adjacent file):** using the step-10 comparison, for any Part A default assumption where this deal's realized/final input differs from the standing table value beyond a materiality threshold — **≥1.0 pt** for percentage-based assumptions (vacancy/credit loss, rent escalation, expense growth, exit cap) · **≥$0.05/SF** for dollar-per-SF assumptions (TI, flat-basis LC, CapEx reserve) · **≥1.0 pt of term-rent %** for percentage-basis LC (470 McCormick-style 6%-of-term-rent deals — Part A documents both LC conventions as legitimate and deal-structure-dependent per its 2026-07-17 ratification; a flat-$/SF threshold does not apply to a %-of-rent input) · **≥5%** for the Replacement Cost Range — draft a PROPOSED delta block: standing value → this deal's realized value → proposed new default → one-line rationale citing the deal. **This is one deal's data point, not a new default by itself** — say so explicitly in the block (Part A's defaults are a multi-deal central tendency; a single closing is an input to Gabriel's judgment, not a mechanical replacement) so he isn't presented a one-observation delta as if it were already representative. Present the block to Gabriel; do not edit `memory/standards.md` under any circumstance from this workflow — ratification is Gabriel's, exactly like the step-10 flag it extends.
13. **[v1.2] Propose two one-time post-closing actuals-check tasks (PROPOSAL — do not self-register):** "[Deal] +6mo Actuals Check" and "[Deal] +12mo Actuals Check", each comparing this deal's underwriting assumptions (the step-10/12 inputs) against realized operating actuals (rent roll, expense actuals, occupancy) at the +6-month and +12-month marks post-closing. State this as "propose registration via the `register-scheduled-task` skill; do not self-register" — only a supervised `create_scheduled_task`/`update_scheduled_task` MCP call may actually register a task; this workflow has no standing authority to splice the registry and must not attempt to.
14. Output: closing summary memo (DOCX) for archival; email Gabriel + Eric.

### Killed Deal Retirement

**Retiring a deal means writing BOTH Notion databases, always.** The Acquisition Pipeline Tracker records the decision; the Deal Sourcing Log is what `ora-passed-deal-tracker` actually sweeps every month for a later trade. Writing only the first is the failure mode this workflow now exists to prevent — see step 3.

1. Capture kill reason in Notion (price, DD finding, market change, financing).
2. **Acquisition Pipeline Tracker row** (`collection://bcfe4a03-7e61-4ac1-a0bb-c44174fa138b`) — set `Stage` to the terminal value matching the decision (`Passed` for a pass, `Killed` for a kill; the Stage select's exact options govern) **and** write `Kill Reason` as a full dated rationale: decision + date + decider, the floors/tests that drove it with their numbers, and a pointer to the decision brief. Stamp `Last Activity` and `Last Substantive Update` with the decision date. Append a dated `## YYYY-MM-DD — DECISION: <verdict>` section to the page body — never overwrite the existing body. Leave `Next Action Date` EMPTY (step 3d). Leave `LOI Status` at its truthful value; it is a known-unreliable field and nothing may branch on it.
3. **[v1.4] Deal Sourcing Log row — MANDATORY, and this row is the canonical passed-deal record.** Data source `collection://9a6ae219-85a3-4621-899c-c757fd062f8b`. There is no Notion Knowledge Base "Deals Passed" log — one was specified here through v1.3 but was never built, and a repo-wide plus Notion-wide search (2026-09-19) found no such database and **no task or skill that reads one**. So this row, not a lessons-learned page, carries the passed-deal record: one fact, one home. A lessons-learned narrative, where the deal warrants one, goes in `Notes / Flags` on this row and in the step-4 memory ledger.

   **3a — existence check first.** Does a Sourcing Log row already exist for this deal? Query by normalized street address, then by `Total SF`, then by title — the log is known to carry duplicate rows for the same property (`511 Industrial Mile Road`). **If a row exists, UPDATE it. Do not create a second one.** If two rows already exist for the deal, update the one with the richer screening history and surface the duplicate to Gabriel rather than merging or deleting. **Then tick `Exclude from Calibration` on every extra row and set its `Duplicate Of` to the canonical row's bare `app.notion.com/<id>` text** (checkbox property added 2026-09-19, Gabriel-directed) — a `🔁 DUPLICATE` marker in `Notes / Flags` is prose and does not filter, so a duplicate retired to `Status = Dead` still lands inside `ora-passed-deal-tracker` Step 2's watch set and double-counts one pass as calibration evidence. Flag the extra rows only; never the canonical row, and never delete or archive either.

   **3b — field mapping (write every field the deal actually has).**

   | Field | Value |
   |---|---|
   | `Status` | `Passed` |
   | `Verdict` | `PASS` |
   | `Go / No-Go` | `🔴 Pass` |
   | `Walk Price` | the ratified walk price, as computed at screen/IC time |
   | `Ask at First Sighting` | the ask when ORA first saw the deal |
   | `Total SF` · `Year Built` | as verified |
   | `Asset Type` · `Construction Type` | as verified |
   | `Metro / Submarket` | as verified |
   | `Buy Box Score (100)` · `Quality Score` · `Expected Score` · `P(exec) %` | **only where the IC memo/scorecard gives a single number** — see 3c |
   | `First Sighted` · `Date Seen` | first-sighting date |
   | `IC Memo Done` · `IRR Model Built` · `Scorecard Done` | tick each that is true |
   | `Broker / Contact` | the live thread(s), listing side and buy side, stated as such |
   | `DD-Critical Status` | which items cleared, which are still open, and as of when |
   | `Next Action` | `[YYYY-MM-DD] None — deal passed.` plus, if applicable, what a reopen would require |
   | `Notes / Flags` | the dated PASS rationale in full: floors and their numbers, the stale premises corrected, any unresolved conflict in the source data, every deliberately-blank field and why, and pointers to the decision brief and the pipeline row |
   | `Pipeline Deal` (relation) | → the Acquisition Pipeline Tracker page for this deal (Notion back-fills `Sourcing Entry` on that row) |

   **3c — leave these blank, and say in `Notes / Flags` why. Never back-compute a value the deal never had.**

   | Field | Leave blank when |
   |---|---|
   | `Loss Class` | **No LOI was ever drafted or sent.** The classifier is `ora-passed-deal-tracker` §4b's, and it applies ONLY to the LOST-AT-LOI arm (`LOI Outcome` ∈ {LOST, PENDING, WINNER-BUSTED}) — deals ORA actually bid on. With no LOI there is no `ORA Offer Price` and no `ORA Max Defensible Price` (which §4b and `loi-generation` §6c both require to be fixed at LOI time and **never** back-computed). Do not write `UNCLASSIFIED` either: that value signals a *failed classification of a real loss*, and asserting it would misrepresent a screen-stage pass as a lost bid. |
   | `Floor Result` | No single option (PASS / FAIL-BASIS / FAIL-YIELD / FAIL-BOTH / N/A) is truthfully the whole story — e.g. the IRR floor failed while yield-on-cost cleared, or basis fails only at one end of the replacement-cost range. Put the split result in `Notes / Flags` instead of forcing an option. |
   | `Economics Score` (and any number field) | The memo gives a **range**, not a value. A number property cannot hold a range; write the range in `Notes / Flags`. |
   | `Asking Price` | Live sources disagree and the conflict is unresolved. Record both figures with their fetch dates in `Notes / Flags`; do not pick one. |
   | `Source` | No existing select option accurately describes how the deal arrived. Describe the channel in `Notes / Flags`; do not force the nearest option. |
   | `LOI Outcome` · `ORA Offer Price` · `ORA Max Defensible Price` · `Winning Price` and the rest of the Block B properties | No LOI was ever submitted. These belong to the LOST-AT-LOI arm only. |

   **3d — [v1.4] passed-deal watch-date convention.** This is the standing convention; do not invent a per-deal alternative.
   - **A Passed pipeline row keeps `Next Action Date` EMPTY — never a re-check date.** The tracker's `⏰ Action Overdue` formula is `if(prop("Next Action Date") < now(), …)` and carries **no Stage guard**, so any date here renders a retired deal as overdue work. `ora-deal-aging-sla` and `ora-deal-command-board` exclude `Passed` at the Stage filter today, but that exclusion is the only thing standing between a date here and a retired deal aging as if it were live — do not lean on it.
   - **The watch mechanism for a passed deal is `ora-passed-deal-tracker`'s monthly sweep over its Deal Sourcing Log row.** That is what step 3 exists to guarantee. There is no second watch mechanism, and none is needed.
   - **A specific re-engagement trigger, if one exists, is recorded in the Sourcing Log row's `Notes / Flags` as ONE line:** `RE-CHECK: YYYY-MM-DD - <trigger>` (e.g. `RE-CHECK: 2026-12-31 - still vacant and unsold`). One line, that exact prefix — `ora-passed-deal-tracker` Step 4d scans for it. Record a trigger only if the decision record actually states one; a `[SPECULATIVE]` alternative Gabriel did not elect is not a trigger.
   - **`Re-Engagement Flag` / `Re-Engagement Tickler Date` are NOT available for this.** That pair is scoped by `ora-passed-deal-tracker` §4c to WINNER-BUSTED outcomes — a winner's contract falling apart — and repurposing it would put screen-stage passes into the lost-bid reporting arm.

   **3e — [v1.7] first-sighting fields are never written here, and a pass is never `Dead`.**
   - **Never write `Verdict at First Sighting` or `Score at First Sighting`.** On a row this step creates, leave both BLANK: a retirement is not a scan prediction, and only the sourcing scans (`ora-deal-sourcing-scan`, `ora-entry-market-scan`) write them, on row creation only. On a row this step updates, leave both exactly as found, including blank. Never infer them from `Verdict`, `Buy Box Score (100)` or the decision record. They are the scan's original prediction, which `ora-passed-deal-tracker`'s monthly back-test (`maintenance/funnel-backtest.py` in `~/.claude`) grades against the row's later outcome; overwriting or back-filling them destroys that record.
   - **Record the pass as a decision, never as `Status = Dead`.** A pass writes `Go / No-Go` = `🔴 Pass` and `Status` = `Passed` (3b). `Status = Dead` is reserved for a listing that is gone (withdrawn, sold, or no longer offered) with no ORA decision; the back-test cannot tell a `Dead` row with no `Go / No-Go` from a withdrawn listing, so a pass recorded that way drops out of T1 precision. The step-4a diligence exit is the one place this skill writes `Dead`, and that row carries `LOI Outcome = TERMINATED-DILIGENCE`, which the back-test reads as the decision.
4. Append a row to `memory/deal-decision-ledger.md` — Verdict = the specific decision reached (PASS/SKIP/DROP/PARK/TERMINATED, matching the kill reason), one-line reason, and the buy-box rule this decision validated or refined (leave "—" if none). This is the durable off-Notion record. A killed deal never closed, so it gets no row in `disposition-ledger.md` — that file starts only at ACQUIRED.
4a. **[v1.5] Diligence-exit tagging — where ORA bid or contracted and then exited on its OWN diligence finding.** If the kill reason is an ORA-side diligence finding (title, environmental, physical inspection, financing, seller default) on a deal that had reached LOI or PSA — as opposed to a pass at screen, a loss to another bidder, or a seller pull — set the Deal Sourcing Log row's `LOI Outcome = TERMINATED-DILIGENCE` (**not** `LOST`, which means a competitor won and which routes the row into `ora-passed-deal-tracker` Step 4b's clearing-price classifier, where a deal with no competing bidder can never be classified), set `Status = Dead`, and record on the row, for the tracker's Step 4e arm to read: exit cause, PSA execution date, the date the finding first landed in a document ORA holds, the termination date, the contract price in force at termination, and the `P(exec) %` as recorded at LOI/PSA time — which must be left exactly as recorded, never recomputed. Leave `Loss Class` blank (a diligence exit is not a loss and must not enter the lost-deal sample) and leave `Exclude from Calibration` unticked (this row is calibration evidence of a different kind, not a duplicate). Do not restate the finding's substance in the Sourcing Log — cite the report and date; the substance belongs in the step-8 kill memo and the step-4 ledger row.
4b. **[v1.6] INTERIM aggregate-LTV ledger:** if the killed deal has a row on Gabriel's `debt-management` ledger, prompt him to mark it WITHDRAWN with the reason per the INTERIM checklist (`debt-management/references/ltv-interim-netting-checklist.md`).
5. Retire deal-specific artifacts.
6. Disable deal-specific scheduled tasks.
7. Move DD work product: SharePoint /Acquisitions/[deal]/ → SharePoint /Acquisitions/_Archive/Killed/[YYYY]/[deal]/.
8. Output: kill memo (DOCX) summarizing what we learned; email Gabriel + Eric.

**[v1.4] Killed-deal close-out checklist — the workflow is not complete until every line is ticked or explicitly waived in writing with a reason.** Step 3 is the one that silently gets skipped, because the deal already *looks* retired once the Pipeline Tracker says `Passed`.

- [ ] Pipeline row: `Stage` terminal · `Kill Reason` written with date + decider · `Last Activity` / `Last Substantive Update` stamped · body section appended, not overwritten · `Next Action Date` empty
- [ ] Sourcing Log: existence check run (3a) — row **created or updated**, never duplicated
- [ ] Sourcing Log: `Status` = Passed · `Verdict` = PASS · `Go / No-Go` = 🔴 Pass · `Walk Price` · `Ask at First Sighting` written
- [ ] Sourcing Log: `Verdict at First Sighting` and `Score at First Sighting` NOT written (3e) — blank on a created row, untouched on an updated one; the pass is not recorded as `Status = Dead`
- [ ] Sourcing Log: `Pipeline Deal` relation set, and the Pipeline row's `Sourcing Entry` reads back populated
- [ ] Every blank field of 3c named in `Notes / Flags` with its reason; nothing back-computed
- [ ] Watch date: `Next Action Date` left empty, and a `RE-CHECK:` line added to `Notes / Flags` **only** if the decision record states a real trigger
- [ ] If the kill was an ORA-side diligence finding after LOI/PSA: step 4a run — `LOI Outcome` = TERMINATED-DILIGENCE (not LOST), `Status` = Dead, `Loss Class` left blank, `Exclude from Calibration` left unticked
- [ ] `memory/deal-decision-ledger.md` row appended
- [ ] Both rows re-fetched after the write and the values confirmed reading back

### Periodic Lifecycle Audit (suggested quarterly)
1. List all artifacts and scheduled tasks; identify deal-specific by slug pattern.
2. Cross-check against Notion Acquisition Pipeline status.
3. Flag any deal-bound asset where deal status is CLOSED > 30 days OR KILLED > 7 days but asset still active.
4. Output: lifecycle hygiene report.

## Outputs

- DOCX closing or kill memo (ORA Style)
- Notion Acquisition Pipeline status update
- SharePoint folder reorganization
- Artifact and scheduled-task retirements
- File naming: YYYYMMDD_[Deal]_Retirement_v##.docx

## Boundaries

- This skill never deletes raw data — it archives. Recovery is always possible.
- Closing confirmation requires actual Notion status update — do not act on conversational signal alone.
- Scheduled tasks are DISABLED, not deleted, in case rollback is needed.

## Dependencies

- deal-execution skill (final closing context)
- acquisition-underwriting skill (deal context)
- conversation-archival skill (Knowledge Base entries)
- docx skill (memo deliverables)
- **Notion Deal Sourcing Log** (`collection://9a6ae219-85a3-4621-899c-c757fd062f8b`) — the canonical passed-deal record, written by Killed Deal Retirement step 3. **There is no Knowledge Base "Deals Passed" log; do not look for one and do not create one** (verified absent 2026-09-19, and nothing in the fleet reads one).
- **`ora-passed-deal-tracker` scheduled task** (`C:\Users\Owner\.claude\scheduled-tasks\ora-passed-deal-tracker\SKILL.md`) — the sole downstream consumer of the step-3 row, and the sole watch mechanism for a passed deal. It builds its monthly watch list from the Sourcing Log ONLY, which is why step 3 is mandatory.
- **`ora-passed-deal-tracker` Step 2c / Step 4e (DILIGENCE-EXIT arm)** — the downstream consumer of step 4a's `LOI Outcome = TERMINATED-DILIGENCE` key. Step 2c routes the row onto that arm and holds it out of Step 4b; Step 4e reads the exit cause, the discovery/termination dates, the price at exit vs walk, and the as-recorded `P(exec) %`. Writing `LOST` instead strands the row in 4b's clearing-price classifier permanently.
- deal-decision-ledger.md (durable PASS/SKIP/DROP/PARK/CLOSE/TERMINATE record, appended by every closing/kill workflow above)
- disposition-ledger.md (post-acquisition lifecycle record — ACQUIRED baseline row appended by Closed Deal Retirement step 9 only; never touched by the Killed workflow)
- standards.md Part A underwriting-defaults table (closing-workflow divergence check, step 10; PROPOSED delta block, step 12 — Gabriel ratifies, this skill never writes it)
- ora-calibration-snapshot scheduled task (`C:\Users\Owner\.claude\scheduled-tasks\ora-calibration-snapshot\SKILL.md`) — inline-triggered observational scoring logic, step 11
- register-scheduled-task skill (supervised MCP registration path for the two proposed +6mo/+12mo actuals-check tasks, step 13 — this skill only proposes, never registers)
