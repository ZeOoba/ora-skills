---
name: fleet-advisory-remediation
description: Auto-triage a fleet-status/setup-self-audit advisory report across the dual CC/MCP + LAMS/Cowork scheduled-task fleet — register complete-but-unregistered "dark" task folders, delete expired one-time registry entries, route stale-data-producer symptoms to orphaned-task-forensics for root-causing, and hand off fixes the current session's fleet can't reach (spawn a background task for the other fleet rather than guessing at data outside this session's registry). Use when the user pastes or references a fleet-status/setup-self-audit/automation-health-monitor advisory report, says fix these advisories, dark tasks, fleet hygiene sweep, or clean up the scheduled-task fleet. v1.0
license: ORA Internal
---

# Fleet Advisory Remediation

Turns a `fleet-status.py`/`setup-self-audit.py`/`automation-health-monitor` advisory dump into triaged, executed (where safe) or handed-off (where not) fixes — replacing the ad hoc `TaskCreate`/`TaskUpdate` scratch list this has been rebuilt as at least twice.

## Scope

Mechanical categories only: dark (complete-but-unregistered) task folders, expired one-time registry entries, and routing (not resolving) stale-producer symptoms and cross-fleet scheduling issues. This skill does not decide policy (e.g. whether a task should exist at all) — it executes the mechanical fix or surfaces the decision, never both silently.

## Triggers

A pasted advisory block from `fleet-status.py`, `setup-self-audit.py`, or the `automation-health-monitor` scheduled task's own output; "fix these advisories", "clean up the fleet", "dark tasks", "fleet hygiene".

## Inputs

- The advisory report text (never-ran tasks, expired one-time entries, throttle skips, same-time collisions, dark/unregistered folders, stale-producer flags).
- Live registry state via `fleet-status.py` / `list_scheduled_tasks` (CC/MCP fleet only — this session cannot see or write the LAMS/Cowork registry directly).

## Standard Workflows

1. **Parse the advisory into categories:** dark tasks, expired one-time entries, throttle skips, same-time collisions/AM pileup, stale-producer flags. Build a todo list (`TaskCreate`/`TaskUpdate`), one item per category, not per individual advisory line.
2. **Dark tasks (complete-but-unregistered folders):** for each, read its `SKILL.md` to confirm it's genuinely complete (not a half-written draft), then register via the `register-scheduled-task` skill's supervised `create_scheduled_task` path — never splice the registry JSON directly. If a dark folder looks incomplete or its purpose is unclear, surface it rather than registering blind.
3. **Expired one-time entries:** confirm the `fireAt` timestamp is genuinely past and the task shows as already-fired-or-disabled, then delete the registry entry (the entry only — never the folder, which may hold useful history) via the supervised path.
4. **Stale-producer flags:** do not root-cause these yourself — hand off to the `orphaned-task-forensics` skill's Workflow A. This skill's job is *recognizing* the symptom in the advisory and routing it, not re-deriving the trace-and-verify procedure inline.
5. **Same-time collisions / AM pileup:** this session (CC/MCP fleet only) can identify and propose a redistribution for tasks living in *this* registry, but cannot safely resolve collisions that involve LAMS/Cowork-side tasks — blind rescheduling risks breaking a producer→consumer chain that spans fleets. Where a collision is entirely within the CC/MCP fleet, propose a specific retime and get confirmation before applying. Where it spans fleets, produce the proposal and explicitly flag that the LAMS half needs a joint Code+Cowork pass — do not guess at LAMS cron data this session cannot see.
6. **Cross-fleet items generally:** if a fix requires writing to the LAMS/Cowork registry, this CC/MCP session cannot do it directly (per `register-scheduled-task` doctrine — registration happens on the surface that owns the target registry). Use `mcp__ccd_session__spawn_task` to flag it for a Cowork-side session rather than leaving it silently unaddressed in the todo list.
7. **Log every category's resolution** (fixed / handed-off / needs-decision) to `event_log.md` in one consolidated entry, not one per line item.

## Outputs

- Registered dark tasks (via the supervised path only).
- Deleted expired one-time entries.
- A spawned background task for any LAMS/Cowork-side fix this session can't reach directly.
- One consolidated `event_log.md` entry.
- For stale-producer flags: a handoff to `orphaned-task-forensics`, not an inline resolution.

## Boundaries

- Never splice scheduled-task registry JSON directly — always the supervised `create_scheduled_task`/`update_scheduled_task`/deletion path.
- Never resolve a cross-fleet scheduling collision by guessing at the other fleet's cron list — propose, don't apply, for anything touching LAMS from a CC/MCP session.
- Never root-cause a stale-producer symptom inline — route to `orphaned-task-forensics` so the trace/recover/verify discipline there (including "verify absorption before treating an archived task as redundant") is actually applied, not skipped under time pressure.

## Dependencies

- `register-scheduled-task` (registration/deletion mechanics)
- `orphaned-task-forensics` (stale-producer root-causing)
- `automation-health-monitor` (the advisory source this skill consumes)

## Changelog

- v1.0 (2026-07-11): initial. Formalizes a remediation loop previously rebuilt ad hoc via a scratch TaskCreate/TaskUpdate list at least twice, surfaced by a workflow-audit session mining recent transcripts.
