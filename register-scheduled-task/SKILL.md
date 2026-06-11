---
name: register-scheduled-task
description: Register, update, or retire an Oxford Realty Advisors scheduled task via the supervised create_scheduled_task / update_scheduled_task MCP tools ONLY. JSON-splice registration is PROHIBITED (proven registered-but-unscheduled 2026-06-09). Use when the user says register scheduled task, register this as a scheduled task, schedule this to run, add a cron task, create a recurring automation, update a scheduled task's cron, retire a scheduled task, or when any skill/workflow needs a new recurring job. Encodes the dual-fleet registry model (CC/MCP + LAMS/Cowork), ORA routing canon (ggoldberg-only; Daily Brief sole cc-Eric exception), COM-only send path, and the registration QC gate. v2.1 (2026-06-11)
---

# Register Scheduled Task (ORA) — v2.1

**RULE 1 — MCP ONLY.** Register and update tasks EXCLUSIVELY via the `create_scheduled_task` / `update_scheduled_task` MCP tools, in a SUPERVISED session, on the surface where the task should run. If the MCP tool is unavailable in the current session (e.g., unsupervised/scheduled context), STOP and tell Gabriel to run the registration from a supervised session — do not improvise a filesystem path.

**RULE 2 — JSON-SPLICE PROHIBITED.** Direct edits to `scheduled-tasks.json` (the v1.0 "Desktop Commander splice" procedure) are BANNED. Proof: the 2026-06-09 fleet rebuild left splice-registered tasks present in the JSON but never picked up by the scheduler — registered-but-unscheduled. `ora-cowork-heartbeat` went dark 2026-05-31→06-10 in exactly this failure mode. The registry file is the scheduler's private state, not an API.

## Dual-fleet registry model (both live; neither is "the" store)

| Fleet | Registry | SKILL.md store | Register from |
|---|---|---|---|
| CC/MCP | `claude-code-sessions` registry | `~/.claude/scheduled-tasks/{task-id}/` | Claude Code (supervised) |
| LAMS/Cowork | `local-agent-mode-sessions` registry | `OneDrive — Oxford Capital Partners (1)\Documents\Claude\Scheduled\{task-id}\` | Cowork (supervised) |

- Cowork-created tasks land in the LAMS registry BY DESIGN — do not migrate them to the CC store; monitors are store-agnostic.
- Both fleets fire only while the Desktop app is open. Dead-man chain: ora-cowork-heartbeat → Notion page `35c6ecd8…` → GitHub watchdog.
- **Path note:** `C:\Users\Owner\AppData\Local\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\...` is the SAME file as the corresponding `C:\Users\Owner\AppData\Roaming\Claude\...` path via MSIX virtualization. It is never a second store; never write to either directly (Rule 2).

## Procedure (new task)

1. **Naming:** task id = kebab-case, `ora-` prefix for firm automations. Check `list_scheduled_tasks` first — if the id exists, this is an UPDATE (`update_scheduled_task`), not a new registration. Never duplicate ids across either fleet.
2. **Surface selection:** decide which fleet the task belongs to (Cowork artifact/skill dependencies → LAMS; filesystem/git/probe work → CC) and register from THAT surface.
3. **SKILL.md content** (passed as the task prompt or stored in the fleet's SKILL.md store) must state:
   - guard conditions (e.g., "first business day only — exit silently otherwise" when cron over-fires);
   - steps with explicit data sources (Notion collection IDs, folder paths, memory names);
   - output destinations (Notion Ops Hub `32b6ecd8` block, file outputs with ISO-date prefix);
   - **email convention:** Outlook COM via `C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1` — the SOLE send path (Composio retired 2026-06-11, NO fallback; Rube EOL 2026-05-15; Gmail disabled). TO `ggoldberg@oxfordra.net` ONLY — the cc to `egoldberg@oxfordra.net` is sanctioned for the ora-am-brief Daily Brief ALONE. On non-zero exit: retry once, flag loudly in the Notion completion row, do NOT halt;
   - "never fabricate" + structured QUESTIONS FOR GABRIEL escalation for data gaps;
   - pointers to sibling skills/tasks instead of duplicating their logic.
4. **Register:** call `create_scheduled_task` with cron (ET, 5-field) and the prompt. Cron notes: quarterly-on-first-business-day → `30 6 1-3 1,4,7,10 *` + in-skill business-day guard; avoid `*/n` day-of-month patterns (drift); avoid the 05:00–09:30 pileup window and same-minute collisions with existing tasks.
5. **Verify (mandatory — no "done" without evidence):** call `list_scheduled_tasks` and paste the returned entry (id, cron, enabled, next-fire). A registry-file grep is NOT verification (Rule 2 lesson: file presence ≠ scheduled).

## Update / retire

- **UPDATE:** `update_scheduled_task` (cron and/or prompt). Re-verify via `list_scheduled_tasks`.
- **RETIRE:** disable via `update_scheduled_task`; move the SKILL.md directory to `_archive_YYYY-MM-DD_retired\` in its store; note in Ops Hub. Never delete history silently. Update the fleet disposition ledger (`00_Governance/outputs/`).
- **RETIRE — ARCHIVE FIRST, DELETE SECOND (hard ordering):** the Cowork Scheduled-sidebar delete is FOLDER-DESTRUCTIVE — it hard-deletes the task's SKILL.md folder along with the registry entry, bypassing the Windows Recycle Bin (OneDrive online recycle bin ~93d is the only recovery; 2026-06-11 incident: `scheduled-task-integrity-guard` kept-by-design backups lost this way). Therefore: (1) MOVE the task folder to the dated `_archive_*` folder, (2) VERIFY the move landed, (3) only THEN delete the registry entry in the UI. Log planned removals to `memory/event_log.md` with the literal token `RATIFIED` + the task id — `registry-membership-probe.py` auto-ratifies such drops (≤14d window) instead of raising a false [ACTION].

## QC gate before declaring done

`list_scheduled_tasks` shows the entry · id unique across BOTH fleets · cron fires as intended (state the next 2 fire dates ET) · routing = ggoldberg-only (or sanctioned Daily-Brief exception) · send path = COM script only · no JSON edits anywhere · automation-health-monitor coverage flagged for its next list revision.

## Changelog

- **v2.1 (2026-06-11):** RETIRE hardened — ARCHIVE FIRST, DELETE SECOND ordering added after the sidebar-delete folder-destruction incident (UI delete hard-deletes the task folder, bypassing the Recycle Bin); RATIFIED event_log convention encoded for probe auto-ratification.
- **v2.0 (2026-06-11):** Full inversion of v1.0. MCP-only supervised registration; JSON-splice PROHIBITED (2026-06-09 registered-but-unscheduled proof); MSIX LocalCache path documented as the same file via virtualization (was wrongly framed as an alternate registry path); dual-fleet model encoded; email convention rewritten to COM-sole + ggoldberg-only routing (was Composio + cc-both, both superseded — Composio removed 2026-06-11, routing canon 2026-06-10).
- **v1.0:** Desktop Commander splice procedure (RETIRED — do not follow).
