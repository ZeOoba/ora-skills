---
name: "outlook-calendar-sync"
description: "Use to add or refresh dated items (deadlines, to-dos, hearings) on Gabriel's Outlook calendar via desktop Outlook COM when the M365 connector cannot write calendar events."
---

# Outlook calendar sync (COM)

Writes events to the default Outlook calendar of ggoldberg@oxfordra.net through the desktop Outlook COM object, on the linked Windows computer. Use it when the user says: add this to my calendar, sync the dashboard dates, put these deadlines on my calendar. The M365 connector's outlook_create_event fails with a missing Calendars.ReadWrite scope until an admin grants consent; try it first only if the user says consent was granted, otherwise go straight to COM.

## Preconditions
- The mcp__remote-devices__Desktop_Commander__ tools (Windows PowerShell) are present and a call succeeds. If not, say the computer is not linked or reachable and offer an .ics file instead (RFC 5545, TZID America/New_York, stable UID per event, import via Outlook Open or Add calendar > Upload from file).
- Desktop Outlook is signed in to ggoldberg@oxfordra.net. Time zone is Eastern; pass local wall-clock times.
- No attendees, no invites, no reminders. Never email anyone from this skill.

## Build the events file
JSON array, one object per event: `{k, s, a, e, allday, busy, loc, b}`.
- `k` stable key (never reuse; the key is what makes re-runs update instead of duplicate).
- `s` subject, prefixed `ORA Power: `. `a` start `yyyy-MM-ddTHH:mm` (or a date for all-day), `e` end (blank for all-day).
- `busy` 0 free, 1 tentative, 2 busy. `loc` location. `b` body (use `\n`).
- Grouping rule used for the Alternative Income dashboard: hearings and confirmed meetings are timed events (busy); every other to-do is rolled into ONE 9:00-9:30 free digest per due date (`t<MMdd>`, subject `ORA Power: N actions due (M P1)`, body lists `P1 T-04: action (counterparty)` lines); timeline deadlines are 9:00 free events; dates beyond 12 months are all-day. Do not duplicate a to-do that is also a timeline event (T-01 = hearing, T-30 = comment due).
- Source of truth for the dashboard build: its todo and timeline datasets. Never invent dates; skip rows without a due date.

## Run
1. Write the JSON and the script below with Desktop_Commander write_file (chunk large files; a very long start_process command fails with spawn EPERM, so always write to files first). Suggested paths: `C:\Users\Owner\AppData\Local\Temp\ora_cal_events.json` and `ora_cal_sync.ps1`.
2. Dry run first: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File <script> -EventsFile <json> -WhatIf` (start_process with shell `cmd`). Review CREATE / UPDATE / STALE lines.
3. Real run without -WhatIf. Re-run with -WhatIf: expect `unchanged=<all>`.
4. Verify through outlook_calendar_search (query `ORA Power`). Cloud sync can lag; say so if only some appear.

STALE lines are events in the calendar whose key is no longer in the file (the item was removed or completed). The script never deletes. Report them to the user and delete only on request.

## Script (tested 10/23/2026: 20 events created, second pass unchanged=20)
```powershell
param([Parameter(Mandatory=$true)][string]$EventsFile, [switch]$WhatIf, [string]$Category = 'ORA Power')
$ErrorActionPreference = 'Stop'
$ev = Get-Content $EventsFile -Raw | ConvertFrom-Json
$ol = New-Object -ComObject Outlook.Application
$cal = $ol.GetNamespace('MAPI').GetDefaultFolder(9)
$items = $cal.Items; $items.IncludeRecurrences = $false
$mine = @($items.Restrict("[Categories] = '$Category'"))
$byKey = @{}; $legacy = @()
foreach ($x in $mine) {
  $p = $x.UserProperties.Find('OraKey')
  if ($p) { $byKey[[string]$p.Value] = $x } else { $legacy += $x }
}
$created = 0; $updated = 0; $same = 0; $seen = @{}
foreach ($e in $ev) {
  $seen[$e.k] = $true
  $start = [datetime]$e.a
  if ($e.allday) { $end = $start.AddDays(1) } else { $end = [datetime]$e.e }
  $body = ($e.b -replace "`n", "`r`n")
  $ap = $byKey[$e.k]
  if (-not $ap) { $ap = $legacy | Where-Object { $_.Subject -eq $e.s -and $_.Start.Date -eq $start.Date } | Select-Object -First 1 }
  if ($ap) {
    $diff = ($ap.Subject -ne $e.s) -or ($ap.Start -ne $start) -or ($ap.End -ne $end) -or (($ap.Body -replace '\s', '') -ne ($body -replace '\s', '')) -or (-not $ap.UserProperties.Find('OraKey'))
    if (-not $diff) { $same++; continue }
    "UPDATE $($e.k)"
    if (-not $WhatIf) {
      $ap.Subject = $e.s; $ap.AllDayEvent = [bool]$e.allday; $ap.Start = $start; $ap.End = $end; $ap.Body = $body; $ap.Location = $e.loc
      if (-not $ap.UserProperties.Find('OraKey')) { $u = $ap.UserProperties.Add('OraKey', 1); $u.Value = $e.k }
      $ap.Save()
    }
    $updated++
  } else {
    "CREATE $($e.k)"
    if (-not $WhatIf) {
      $n = $ol.CreateItem(1)
      $n.Subject = $e.s; $n.Body = $body; $n.AllDayEvent = [bool]$e.allday; $n.Start = $start; $n.End = $end
      $n.BusyStatus = [int]$e.busy; $n.Location = $e.loc; $n.Categories = $Category; $n.ReminderSet = $false
      $u = $n.UserProperties.Add('OraKey', 1); $u.Value = $e.k
      $n.Save()
    }
    $created++
  }
}
foreach ($k in $byKey.Keys) { if (-not $seen[$k]) { "STALE (not in file, left in place): $k - $($byKey[$k].Subject)" } }
"Done. WhatIf=$($WhatIf.IsPresent) created=$created updated=$updated unchanged=$same"
```

## Scheduled sync (do not self-register)
A recurring sync needs Outlook desktop open and a session that can read the dashboard's todo and timeline data. Register it ONLY through the create_scheduled_task MCP in a supervised session on the target surface (never splice scheduled-tasks.json). Task prompt: read the dashboard's current todo and timeline datasets, rebuild the events JSON with the grouping rule above, run the script with -WhatIf then for real, and report created/updated/stale counts to ggoldberg@oxfordra.net via send-via-outlook.ps1 (retry once on a non-zero exit, then flag loudly). Propose a weekday 7:30 am cadence and let the user choose. Confirm before first registration that the chosen surface can read the dashboard data; if it cannot, the task must read a JSON export instead.

## Boundaries
- Calendar writes only; no invites, no email to counterparties.
- Keep subjects prefixed `ORA Power:` and the category `ORA Power` so events are findable and removable as a set.
- Never delete or move existing events that lack the `ORA Power` category.
- Mark any estimated date [FORECAST] in the body.