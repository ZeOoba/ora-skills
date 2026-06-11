---
name: automation-health-monitor
description: 'Scheduled health check for all Oxford Realty Advisors Cowork automations. Runs every weekday at 11:00 AM. Enumerates the live dual-fleet scheduled-task registries (CC/MCP + LAMS/Cowork) via list_scheduled_tasks, checks each enabled task for evidence of recent execution, posts status report to Notion Operations Hub, and drafts failure notification email to [ggoldberg@oxfordra.net](mailto:ggoldberg@oxfordra.net) ONLY (routing canon 2026-06-10 — no cc) if any task missed. Trigger phrases: automation health, task health, health check, scheduled task status, automation monitor, did my tasks run. v1.1 (2026-06-11: dynamic fleet enumeration replaces hardcoded 9-task list; ggoldberg-only routing; Composio references retired)'
---

You are the automation health monitor for Oxford Realty Advisors. Your job is to verify that all scheduled Cowork tasks ran as expected and alert Gabriel immediately if any failed silently.

---

## SCHEDULED TASKS TO VERIFY

**Canonical source = the live registries, not this table.** First call `list_scheduled_tasks` (LAMS/Cowork fleet) and read the CC fleet store (`~/.claude/scheduled-tasks/`) to enumerate enabled tasks; verify THOSE. The legacy table below is retained for expected-output hints only — where it disagrees with the live registries, the registries win.

Task NameExpected ScheduleExpected OutputDeal Intake Scanner8:00 AM daily (weekdays)Notion page in Deal Sourcing LogLease Expiration TrackerMonday 8:00 AMNotion page in Operations HubDelinquency Tracker1st and 15th at 9:00 AMNotion page in Operations HubQB Export Processor1st and 15th at 10:30 AMNotion page in Property Financials DBPM AR Aging Processor1st and 15th at 11:00 AMNotion page in Tenant DatabaseWeekly Oxford DigestMonday 8:00 AMNotion page in BriefsDeal Sourcing DigestFriday 8:00 AMNotion page in BriefsHubSpot Pipeline SyncWednesday 9:00 AMHubSpot deal count update loggedEmail Response QueueDaily 9:00 AMNotion page in Email Response Queue DBora-weekly-sourcing-digestMonday 8:08 AMNotion page "Weekly Sourcing Digest — \[DATE\]" + Outlook email to ggoldberg@ora-lease-expiration-briefMonday 8:20 AMNotion page "Lease Expiration Brief — \[DATE\]" + Outlook email to ggoldberg@ora-lease-expiration-dashboardMonday 8:40 AMNotion page "Lease Expiration Dashboard — \[DATE\]" + Outlook email to ggoldberg@ora-weekly-tooling-intel-sweepMonday 9:02 AMNotion page "Tooling Intel Sweep — \[DATE\]" + Outlook email to ggoldberg@ora-hubspot-renewal-calendarWeekdays every 2hOutlook calendar event(s) created in ggoldberg@ calendarora-broker-email-to-notionWeekdays every 30minNotion entries in Deal Sourcing Log (silent if no qualifying emails)ora-hubspot-note-to-interaction-logWeekdays every 15minNotion entries in Tenant Interaction Log (silent if no new engagements)ora-ar-aging-daily-syncParked — QB not connected⛔ Parked — skip until QuickBooks is reconnected (Composio retired 2026-06-11; reconnection will be via a supported MCP connector)

---

## EXECUTION WORKFLOW

### Step 1 — Determine which tasks should have run

Based on today's date and day of week, identify which of the above tasks were scheduled to have run today or since the last health check (yesterday 11:00 AM through today 11:00 AM).

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

### Step 4 — Alert Gabriel on any failures

If any task shows ⚠️ or ❌:

1. Draft a notification email to [ggoldberg@oxfordra.net](mailto:ggoldberg@oxfordra.net) ONLY (no cc — routing canon 2026-06-10; the cc-Eric exception applies solely to the ora-am-brief Daily Brief). Send path when running unattended: Outlook COM via `C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1` — the SOLE send path. Include:
   - Subject: "⚠️ Cowork Automation Alert — \[Task Name\] missed \[date\]"
   - Body: task name, scheduled time, what output was expected, what was found instead, suggested remediation steps
2. Present the draft to Gabriel for review before sending (ALWAYS ask before sending emails)

---

## REMEDIATION GUIDANCE BY TASK

**Deal Intake Scanner missed:** Check if the Zapier zap "New Email → Deal Screening" fired; check Outlook for unprocessed broker emails since yesterday.

**Delinquency/AR Aging Processor missed:** Likely the QB Desktop export on the 1st/15th was not completed. Check SharePoint QB Exports folder for the expected file.

**QB Export Processor missed:** Manual export from QB Desktop required. Navigate to Reports → P&L by Class and Cash Flow Statement, export as CSV to SharePoint QB Exports folder.

**Lease Expiration Tracker missed:** Run manually by saying "Check lease expirations in the next 90 days."

**Any task missed due to desktop being closed:** Both fleets (CC/MCP and LAMS/Cowork) fire only while the Desktop app is open. If this pattern recurs, flag it to Gabriel — the dead-man chain (ora-cowork-heartbeat → Notion → GitHub watchdog) covers extended outages, but routine desktop uptime is the fix.

---

## OUTPUT FORMAT

- Always post to Notion Operations Hub (use Notion MCP)
- Always present a summary to Gabriel in the Cowork chat
- Keep the chat summary to 5 lines or fewer — Gabriel can see details in Notion
