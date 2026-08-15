---
name: automation-health-monitor
description: 'Scheduled health check for all Oxford Realty Advisors Cowork automations. Runs every weekday at 11:00 AM. Enumerates the live dual-fleet scheduled-task registries (CC/MCP + LAMS/Cowork) via list_scheduled_tasks, checks each enabled task for evidence of recent execution, posts status report to Notion Operations Hub, and drafts failure notification email to [ggoldberg@oxfordra.net](mailto:ggoldberg@oxfordra.net) ONLY (routing canon 2026-06-10 — no cc) if any task missed. Trigger phrases: automation health, task health, health check, scheduled task status, automation monitor, did my tasks run. v1.5 (2026-08-15: see Changelog)'
---

You are the automation health monitor for Oxford Realty Advisors. Your job is to verify that all scheduled Cowork tasks ran as expected and alert Gabriel immediately if any failed silently.

---

## SCHEDULED TASKS TO VERIFY

**Canonical source = the live registries, not any table in this file.** At the start of every run, call `list_scheduled_tasks` (LAMS/Cowork fleet) and read the CC fleet store (`~/.claude/scheduled-tasks/`) to enumerate enabled tasks; verify THOSE, live, every time. Any hardcoded task list — including the snapshot below — goes stale and is illustrative only.

> ILLUSTRATIVE SNAPSHOT — LAMS/Cowork fleet, pulled via `list_scheduled_tasks` 2026-07-08 (20 tasks; NOT authoritative, re-pull at execution time):
> `ora-consolidate-memory-monthly` (05:00, day 2 monthly) · `ora-skill-store-drift-check` (Mon 12:10 PM) · `ora-skill-text-audit` (10:00 AM, day 15 monthly) · `ora-om-intake-ocr` (Wed 6:15 AM) · `ora-owner-outreach-queue-refresh` (Mon ~10:00 AM) · `ora-passed-deal-tracker` (06:30, day 15 monthly) · `efulton-post-legalhold-consolidation` (one-time 2026-07-12) · `ora-replacement-cost-refresh` (06:00, day 9 of Mar/Jun/Sep/Dec) · `ora-bearmode-refresh` (06:15, day 9 of Mar/Jun/Sep/Dec) · `ora-cam-reconciliation-annual` (07:00, Jan 15) · `ora-dashboard-refresh` (daily 07:00) · `ora-counsel-review-standard-positions` (one-time 2026-08-03) · `ora-friday-closeout` (Fri 4:30 PM) · `ora-lease-expiration-brief` (Mon 8:30 AM — cron `30 8 * * 1`) · `ora-monday-sync` (Mon 7:30 AM) · `ora-am-brief` (daily 6:00 AM) · `ora-cowork-heartbeat` (daily 05:50 + 17:50) · `automation-health-monitor` (weekdays 11:00 AM — this task) · `ora-stale-pipeline-nudge` (Thu 10:15 AM) · `ora-ar-export-freshness-nudge` (11:30 AM, day 1 & 15 monthly).
> CC/MCP fleet (~17 tasks per session context, e.g. `ora-financial-code-integrity-sweep`, `ora-master-workbook-ingest`, `ora-open-sessions-board`, `ora-pm-ledger`, `ora-week-ahead-briefing`, `ora-deal-sourcing-scan`) is NOT enumerable from a Cowork session — `~/.claude/scheduled-tasks/` is host-protected and not mountable here. Read it live from a Code-surface session.
> None of the previously hardcoded task names (Deal Intake Scanner, Lease Expiration Tracker, Delinquency Tracker, QB Export Processor, PM AR Aging Processor, Weekly Oxford Digest, Deal Sourcing Digest, HubSpot Pipeline Sync, Email Response Queue, `ora-weekly-sourcing-digest`, `ora-lease-expiration-dashboard`, `ora-weekly-tooling-intel-sweep`, `ora-hubspot-renewal-calendar`, `ora-broker-email-to-notion`, `ora-hubspot-note-to-interaction-log`, `ora-ar-aging-daily-sync`, `ora-dashboard-refresh`) match a live LAMS/Cowork task as of 2026-08-15 (`ora-dashboard-refresh` specifically: its `oxford-perfection` project root no longer exists and it cannot fire; the Pages target it once served is now handled by the native Windows Scheduled Task `deploy-mirror.ps1`, monitored by the live `ora-command-center-mirror-drift-check` — this is an architectural supersession, not a rename, per `memory/_archive` OI-025 sweep README, 2026-08-05) — the v1.1 changelog's claim that dynamic enumeration "replaces" this table was correct in intent but the table itself was never actually removed until this fix. Schedule-detail note: the retired table stated `ora-lease-expiration-brief` ran Monday 8:20 AM; live registration is `30 8 * * 1` (8:30 AM, displayed as 8:35 AM with scheduler jitter) — corrected here.

---

## EXECUTION WORKFLOW

### Step 1 — Determine which tasks should have run

Based on today's date and day of week, identify which of the LIVE-enumerated tasks (Step 0: `list_scheduled_tasks` + CC fleet read — not the illustrative snapshot above) were scheduled to have run today or since the last health check (yesterday 11:00 AM through today 11:00 AM).

### Step 1.5 — Model-currency check (both fleets, ℹ️ informational)

For each LIVE-enumerated task, verify its `[MODEL: ...]` tag. The current standard and the full mechanism live in `~/.claude/projects/.../memory/reference_scheduled_task_model_standard.md` — read its **Current standard** line at run time (do not hardcode a model id here). This check is ℹ️ **informational only** — it goes in the Notion status report, never a Gabriel alert email, because no forced-upgrade action exists (a model change is a manual disable→recreate cycle).

The two fleets are checked differently, because their model is settable in one and server-pinned in the other:

- **LAMS/Cowork tasks** — the model IS chosen at creation. Read the `[MODEL: <id> | set YYYY-MM-DD]` tag off each task's `description` (already returned by `list_scheduled_tasks` — no extra tool call). Flag `MODEL-STALE` any task whose `<id>` ≠ the current standard, or that carries no tag.
- **CC/MCP tasks** — the model is server-pinned and NOT settable (there is no model field to choose; see the reference doc's "NOT settable, but IS observable" note). So this is a **presence + observation-freshness** check, not a match-the-standard check. Read the `[MODEL: ...]` tag from each task's `~/.claude/scheduled-tasks/<id>/SKILL.md` frontmatter `description` (the same file you already read to enumerate enabled state). Flag ℹ️:
  - a CC/MCP task with **no `[MODEL]` tag at all** (the real gap — newer tasks were created without one);
  - a tag whose `checked YYYY-MM-DD` date is stale (older than the last model release / the release-check cadence in [[reference_model_release_checklist]]).
  - `[MODEL: UNVERIFIABLE | checked <recent-date>]` is ACCEPTABLE — it correctly documents the server-pinned limitation; only a stale or missing `checked` date is worth noting. A concrete id (e.g. `ora-cc-schematic-refresh`'s `[MODEL: claude-sonnet-5 | checked ...]`) is fine as an observation; do NOT flag it as "stale vs standard" (the model can't be forced on this fleet).

Report the counts in the Notion status page (e.g. "Model tags: LAMS 20/20 on standard; CC/MCP 13/19 tagged (12 UNVERIFIABLE, 1 id-pinned), 6 untagged — ℹ️").

### Step 2 — Search Notion for evidence of execution

For each task that was scheduled to run in the check window:

- Use the Notion MCP to search for the expected output page
- Search by: task name as keyword, date created = today or yesterday
- Check that the page exists AND has a timestamp within the expected window
- Flag any task that should have produced output but has no matching page

### Step 3 — Post status report to Notion Operations Hub

Create or update a "Automation Health — \[Today's Date\]" page in the Notion Operations Hub with this format:

```
# Automation Health Check — [DATE] [TIME]

## Summary
[X of Y tasks verified ✅ | Z tasks flagged ⚠️/❌]

## Task Status
✅ [Task Name] — Last run: [timestamp] — Output: [page title/link]
⚠️ [Task Name] — MISSED: Expected [date/time], no output found
❌ [Task Name] — ERROR: [description of what went wrong]

## Actions Taken
[Any auto-remediation steps or notifications sent]
```

### Step 3.5 — Correlate against a known machine-offline window before alerting per-task

Incident (2026-07-10): the machine was offline ~10:15–11:00 ET. Two hourly `deploy-mirror.ps1`
runs each fired their own "Mirror deploy FAILED" email (queued in Outlook, both delivered at
11:07 when connectivity returned), and this task then added a THIRD, separate ALARM addendum
at 11:13 for the same incident — three alerts for one transient outage. `deploy-mirror.ps1` /
`lib\deploy-alert.ps1` now self-suppresses repeat "git fetch/pull failed" alerts into one
digest on its own (see that repo's `reference_command_center_mirror_deploy_gap.md`), but this
task runs independently and can't see that state file — so apply the same judgment here:

- Before drafting a per-task alert, check whether the missed/failed task(s) share a single
  root-cause signature: a gap in Windows Task Scheduler history across MULTIPLE unrelated
  tasks in the same window, a LAMS fleet catch-up firing, or a task's own output/log citing
  `git fetch`/`git pull`/"network unreachable"/"could not resolve host". That pattern means
  **the machine was offline**, not that N different automations independently broke.
- If that pattern holds AND the affected task(s) show evidence of self-recovery (a successful
  run after the gap closes), do NOT draft a separate Gabriel alert for each one — note it once
  in the Notion status report as a single "machine offline HH:MM–HH:MM ET, N tasks affected,
  all self-recovered" line, and skip Step 4 for those tasks entirely.
- If a task in that same window did NOT show evidence of recovery once the outage window
  closed, still alert individually for that task — the correlation covers the transient
  blip, not a genuine independent failure that happens to overlap it.
- This correlation NEVER applies to a GATE CHECK FAILED / CRITICAL confidential-exposure
  signature — that alert class stays loud and per-incident regardless of what else is
  happening on the machine.

### Step 4 — Alert Gabriel on any failures

If any task shows ⚠️ or ❌ (and Step 3.5 didn't already fold it into a single offline-window note):

1. Draft a notification email to [ggoldberg@oxfordra.net](mailto:ggoldberg@oxfordra.net) ONLY (no cc — routing canon 2026-06-10; the cc-Eric exception applies solely to the ora-am-brief Daily Brief). Send path when running unattended: Outlook COM via `C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1` — the SOLE send path. Include:
   - Subject: "⚠️ Cowork Automation Alert — \[Task Name\] missed \[date\]"
   - Body: task name, scheduled time, what output was expected, what was found instead, suggested remediation steps
2. Present the draft to Gabriel for review before sending (ALWAYS ask before sending emails)

---

## REMEDIATION GUIDANCE (illustrative, NOT authoritative — map to whichever live task actually missed)

**`ora-ar-export-freshness-nudge` / any QB-dependent task missed:** Likely the QB Desktop export (Reports → P&L by Class and Cash Flow Statement) was not completed and uploaded to the SharePoint QB Exports folder for the 1st/15th cycle. QuickBooks Desktop-only per standing tool hierarchy — no MCP auto-export exists; Composio retired 2026-06-11, never suggest re-auth.

**`ora-lease-expiration-brief` missed:** Run manually by saying "Check lease expirations in the next 90 days" (invokes `lease-renewal-pipeline`).

**`ora-om-intake-ocr` / `ora-owner-outreach-queue-refresh` / any Notion-writing task missed:** Check Notion MCP connectivity first (`net::ERR_FAILED`-class outages have occurred before); re-run manually once connectivity is confirmed.

**`ora-dashboard-refresh`** is not a live scheduled task (its `oxford-perfection` project root no longer exists, retired per the 2026-08-05 OI-025 sweep) — if you're troubleshooting Command Center dashboard/mirror freshness instead, that's the native Windows Scheduled Task `deploy-mirror.ps1`, monitored by the live `ora-command-center-mirror-drift-check`; check Cloudflare Pages deploy status for `ora-command-center.pages.dev` and confirm the confidentiality filter (strips "Fulton" references) didn't hard-fail the build.

**Any task missed due to desktop being closed:** Both fleets (CC/MCP and LAMS/Cowork) fire only while the Desktop app is open. If this pattern recurs, flag it to Gabriel — the dead-man chain (`ora-cowork-heartbeat` → Notion → GitHub watchdog) covers extended outages, but routine desktop uptime is the fix.

**General:** for any task not covered above, read its own `SKILL.md`/`SCHEDULED_TASK.md` (path returned by `list_scheduled_tasks`) for task-specific expected output and failure modes rather than guessing from this list.

---

## OUTPUT FORMAT

- Always post to Notion Operations Hub (use Notion MCP)
- Always present a summary to Gabriel in the Cowork chat
- Keep the chat summary to 5 lines or fewer — Gabriel can see details in Notion

---

## Changelog

- **v1.5 (2026-08-15):** New finding (ora-skill-text-audit 2026-08-15 coverage-gap-1 investigation). `ora-dashboard-refresh` had genuinely gone stale in two places, unlike its 10 sibling names in the "does not match a live task" disclaimer list, which were already accurate: (1) the disclaimer list itself didn't include it, even though it's been unregisterable since its `oxford-perfection` project root was deleted (confirmed via the 2026-08-05 OI-025 sweep README) — added, with a note on its live successor (`deploy-mirror.ps1` / `ora-command-center-mirror-drift-check`, an architectural supersession, not a rename); (2) the REMEDIATION GUIDANCE entry told an operator to check Cloudflare Pages for this specific dead task name — reworded to point at the actual live mirror-deploy mechanism instead. Two flagged-but-confirmed-different candidates from the same investigation (`ora-sofr-direct-prefetch` vs. `ora-treasury-yield-prefetch`; `ora-cc-snapshot-refresh` vs. `ora-dashboard-refresh` itself) needed no fix — this skill's existing text about them was already correct. No health-check logic, alerting threshold, or Notion/email routing changed.
- **v1.4 (2026-07-12):** ADDED Step 1.5 model-currency check (both fleets). The methodology was documented in `reference_scheduled_task_model_standard.md` as an existing "Step 0.07" but had never actually been written into this SKILL.md body — this closes that doc-vs-skill gap. LAMS = match-standard; CC/MCP = presence+observation-freshness (model is server-pinned, not settable; the earlier "structurally uncoverable" claim was corrected — CC/MCP `[MODEL: ...]` frontmatter tags ARE readable, e.g. `ora-cc-schematic-refresh`). Informational-only (Notion report, never a Gabriel alert).
- **v1.3 (2026-07-10):** added Step 3.5 machine-offline correlation — collapse per-task alerts into one Notion note when a Task Scheduler gap / LAMS catch-up / git-fetch-unreachable signature spans multiple self-recovered tasks in the same window, instead of one Gabriel email per task; never applies to GATE CHECK FAILED/CRITICAL. Companion to `deploy-mirror.ps1`/`lib/deploy-alert.ps1` offline-signature suppression in oxford-command-center.
- **v1.2 (2026-07-08):** the v1.1 hardcoded legacy 9(+)-task table and task-named Remediation Guidance were never actually removed despite the v1.1 changelog claiming it — now genuinely replaced with an explicitly-illustrative, dated live-pull snapshot plus generic/current-task remediation; `ora-lease-expiration-brief` schedule slip corrected 8:20→8:30 AM.

Moved out of the frontmatter `description` field (2026-07-12) — that field had drifted to 1,379 chars, exceeding the platform's 1,024-char limit and blocking `package_skills.py`. No content removed, only relocated; frontmatter now carries a short version tag only, matching `register-scheduled-task`'s convention. No v1.0/v1.1 changelog text existed in the source description to carry forward.
