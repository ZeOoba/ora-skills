---
name: deal-retirement
description: Lifecycle skill triggered on deal closing or kill — retires deal-bound artifacts, scheduled tasks, and Notion staging records; archives DD package to SharePoint. Use when the user mentions: deal closed, deal killed, deal dead, post-closing cleanup, retire deal, archive deal, sunset deal artifacts, deal lifecycle, close-out, post-mortem, or any task related to retiring assets associated with a completed or terminated deal. v1.1 (2026-07-16: closing/kill now append a row to memory/deal-decision-ledger.md and prompt an underwriting-defaults refresh — see Standard Workflows step additions)
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
9. Compare the closing deal's final underwriting assumptions (vacancy, escalation, TI/LC, capex reserve, exit-cap spread, replacement cost) against `memory/standards.md` Part A's underwriting-defaults table. If actuals diverge meaningfully from the table, flag it — don't silently overwrite a ratified default without Gabriel's confirmation.
10. Output: closing summary memo (DOCX) for archival; email Gabriel + Eric.

### Killed Deal Retirement
1. Capture kill reason in Notion (price, DD finding, market change, financing).
2. Update Notion Acquisition Pipeline: status = KILLED, kill date and reason.
3. Add to Notion Knowledge Base "Deals Passed" log with lessons-learned summary.
4. Append a row to `memory/deal-decision-ledger.md` — Verdict = the specific decision reached (PASS/SKIP/DROP/PARK/TERMINATED, matching the kill reason), one-line reason, and the buy-box rule this decision validated or refined (leave "—" if none). This is the durable record the Notion log doesn't provide.
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
- standards.md Part A underwriting-defaults table (closing-workflow divergence check, step 9)
