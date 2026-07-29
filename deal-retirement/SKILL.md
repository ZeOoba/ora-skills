---
name: deal-retirement
description: Lifecycle skill triggered on deal closing or kill — retires deal-bound artifacts, scheduled tasks, and Notion staging records; archives DD package to SharePoint. Use when the user mentions: deal closed, deal killed, deal dead, post-closing cleanup, retire deal, archive deal, sunset deal artifacts, deal lifecycle, close-out, post-mortem, or any task related to retiring assets associated with a completed or terminated deal. v1.3 (2026-07-29: Closed Deal Retirement step 9 now appends an ACQUIRED baseline row to memory/disposition-ledger.md, the new post-acquisition lifecycle ledger); v1.2 (2026-07-18: proposes an inline ora-calibration-snapshot trigger, a PROPOSED underwriting-defaults delta vs standards.md Part A, and two proposed +6mo/+12mo actuals-check tasks — all proposals, nothing self-registers); v1.1 (2026-07-16: closing/kill appends to memory/deal-decision-ledger.md)
license: ORA Internal
---

# Deal Retirement

Lifecycle hygiene skill that retires deal-bound artifacts, scheduled tasks, Notion staging records, and DD packages once a deal closes or is killed.

## Scope

Triggered on deal lifecycle terminal states: CLOSED (acquisition completed) or KILLED (deal terminated before closing).

## Triggers

"Deal closed", "deal killed", "deal dead", "we passed", "retire [deal name]", "archive [deal name]", "post-closing cleanup".

## Inputs

- Deal name / Notion Acquisition Pipeline record
- Closing or kill date
- Deal-specific artifacts (e.g., REDACTED-159-dd-tracker)
- Deal-specific scheduled tasks (e.g., REDACTED-159-retire-partial-dashboard)
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
12. **[v1.2] Underwriting-default delta proposal — PROPOSED ONLY, never auto-written (Hard Invariant 4: `standards.md` Part A is a governor-adjacent file):** using the step-10 comparison, for any Part A default assumption where this deal's realized/final input differs from the standing table value beyond a materiality threshold — **≥1.0 pt** for percentage-based assumptions (vacancy/credit loss, rent escalation, expense growth, exit cap) · **≥$0.05/SF** for dollar-per-SF assumptions (TI, flat-basis LC, CapEx reserve) · **≥1.0 pt of term-rent %** for percentage-basis LC (470 REDACTED-148-style 6%-of-term-rent deals — Part A documents both LC conventions as legitimate and deal-structure-dependent per its 2026-07-17 ratification; a flat-$/SF threshold does not apply to a %-of-rent input) · **≥5%** for the Replacement Cost Range — draft a PROPOSED delta block: standing value → this deal's realized value → proposed new default → one-line rationale citing the deal. **This is one deal's data point, not a new default by itself** — say so explicitly in the block (Part A's defaults are a multi-deal central tendency; a single closing is an input to Gabriel's judgment, not a mechanical replacement) so he isn't presented a one-observation delta as if it were already representative. Present the block to Gabriel; do not edit `memory/standards.md` under any circumstance from this workflow — ratification is Gabriel's, exactly like the step-10 flag it extends.
13. **[v1.2] Propose two one-time post-closing actuals-check tasks (PROPOSAL — do not self-register):** "[Deal] +6mo Actuals Check" and "[Deal] +12mo Actuals Check", each comparing this deal's underwriting assumptions (the step-10/12 inputs) against realized operating actuals (rent roll, expense actuals, occupancy) at the +6-month and +12-month marks post-closing. State this as "propose registration via the `register-scheduled-task` skill; do not self-register" — only a supervised `create_scheduled_task`/`update_scheduled_task` MCP call may actually register a task; this workflow has no standing authority to splice the registry and must not attempt to.
14. Output: closing summary memo (DOCX) for archival; email Gabriel + Eric.

### Killed Deal Retirement
1. Capture kill reason in Notion (price, DD finding, market change, financing).
2. Update Notion Acquisition Pipeline: status = KILLED, kill date and reason.
3. Add to Notion Knowledge Base "Deals Passed" log with lessons-learned summary.
4. Append a row to `memory/deal-decision-ledger.md` — Verdict = the specific decision reached (PASS/SKIP/DROP/PARK/TERMINATED, matching the kill reason), one-line reason, and the buy-box rule this decision validated or refined (leave "—" if none). This is the durable record the Notion log doesn't provide. A killed deal never closed, so it gets no row in `disposition-ledger.md` — that file starts only at ACQUIRED.
5. Retire deal-specific artifacts.
6. Disable deal-specific scheduled tasks.
7. Move DD work product: SharePoint /Acquisitions/[deal]/ → SharePoint /Acquisitions/_Archive/Killed/[YYYY]/[deal]/.
8. Output: kill memo (DOCX) summarizing what we learned; email Gabriel + Eric.

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
- deal-decision-ledger.md (durable PASS/SKIP/DROP/PARK/CLOSE/TERMINATE record, appended by every closing/kill workflow above)
- disposition-ledger.md (post-acquisition lifecycle record — ACQUIRED baseline row appended by Closed Deal Retirement step 9 only; never touched by the Killed workflow)
- standards.md Part A underwriting-defaults table (closing-workflow divergence check, step 10; PROPOSED delta block, step 12 — Gabriel ratifies, this skill never writes it)
- ora-calibration-snapshot scheduled task (`C:\Users\Owner\.claude\scheduled-tasks\ora-calibration-snapshot\SKILL.md`) — inline-triggered observational scoring logic, step 11
- register-scheduled-task skill (supervised MCP registration path for the two proposed +6mo/+12mo actuals-check tasks, step 13 — this skill only proposes, never registers)
