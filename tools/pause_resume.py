#!/usr/bin/env python3
"""pause_resume.py -- fleet-symmetry check + resume-task generator for bounded pauses.

WHY THIS EXISTS (2026-08-17): register-scheduled-task v2.12 added a rule that a
bounded pause ("pause all routines until Friday") is not complete until its resume
is registered per fleet, same session/surface/pass. The root incident that forced
that rule was entirely preventable by machine: the LAMS/Cowork half of a dual-fleet
pause landed with no resume because the resume SKILL.md was hand-authored (id list
copy-pasted, typed fire time) rather than generated from the live registry. Hand
transcription is exactly the step that silently drops or never lands.

This tool does NOT register anything -- registration stays MCP-only, in a
supervised session (register-scheduled-task Rule 1). It is read-only against the
registry JSON and against each task's own SKILL.md content.

Subcommands:
  status                          Read-only fleet-symmetry report (both fleets).
  gen-resume --fleet cc|lams --id <resume-task-id> --fire-at "YYYY-MM-DD HH:MM"
             [--exclude id1,id2,...] [--out <path>]
                                   Emit a resume SKILL.md from the LIVE disabled-
                                   recurring-task list for that fleet. Prints to
                                   stdout if --out is omitted.

Usage (from a Desktop Commander PowerShell .ps1 file, per register-scheduled-task's
host-shell discipline -- never inline `powershell -Command`):
  python tools\\pause_resume.py status
  python tools\\pause_resume.py gen-resume --fleet lams --id ora-lams-routine-pause-resume-08-21 --fire-at "2026-08-21 17:05" --exclude ora-passed-deal-tracker
"""
import argparse
import glob
import io
import json
import os
import re
import sys

APPDATA = os.path.expandvars(r"%APPDATA%\Claude")
ROOTS = {
    "cc": os.path.join(APPDATA, "claude-code-sessions"),
    "lams": os.path.join(APPDATA, "local-agent-mode-sessions"),
}
FLEET_LABEL = {"cc": "CC/MCP", "lams": "LAMS/Cowork"}

# Tasks whose loss of coverage during a pause matters more than any other --
# both live on LAMS and are the mechanisms that would otherwise SURFACE a
# missed resume (register-scheduled-task v2.12 -- "never blanket-pause the
# detectors").
DETECTOR_IDS = {"ora-cowork-heartbeat", "automation-health-monitor"}

ID_RE = re.compile(r"\bora-[a-z0-9][a-z0-9\-]*\b|\bautomation-health-monitor\b")


def discover_registry(fleet):
    """Find scheduled-tasks.json under this fleet's root. Per register-scheduled-task's
    Path note: PROBE, don't hardcode a single session-id path -- multiple session dirs
    can exist. If more than one candidate is found, use the most recently modified and
    warn about the rest rather than silently picking one."""
    root = ROOTS[fleet]
    hits = glob.glob(os.path.join(root, "**", "scheduled-tasks.json"), recursive=True)
    if not hits:
        raise SystemExit("no scheduled-tasks.json found under %s" % root)
    hits.sort(key=os.path.getmtime, reverse=True)
    if len(hits) > 1:
        print("WARNING: %d candidate registries under %s -- using newest, ignoring:"
              % (len(hits), root), file=sys.stderr)
        for h in hits[1:]:
            print("  " + h, file=sys.stderr)
    return hits[0]


def load_tasks(fleet):
    path = discover_registry(fleet)
    with io.open(path, encoding="utf8") as f:
        data = json.load(f)
    return data.get("scheduledTasks", []), path


def disabled_recurring(tasks):
    return [t for t in tasks if not t.get("enabled") and t.get("cronExpression")]


def enabled_onetime(tasks):
    return [t for t in tasks if t.get("enabled") and not t.get("cronExpression") and t.get("fireAt")]


def read_skill_text(task):
    fp = task.get("filePath")
    if not fp or not os.path.isfile(fp):
        return ""
    try:
        with io.open(fp, encoding="utf8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def covered_ids(tasks):
    """Union of every ora-*/automation-health-monitor token mentioned anywhere in the
    SKILL.md body of every currently-ENABLED one-time task for this fleet. A resume
    task's own id and any ids it targets both match this pattern; that's fine -- we
    only ever intersect this set against the disabled-recurring id set below."""
    ids = set()
    for t in enabled_onetime(tasks):
        text = read_skill_text(t)
        ids |= set(ID_RE.findall(text))
    return ids


def cmd_status(args):
    exit_code = 0
    for fleet in ("cc", "lams"):
        tasks, path = load_tasks(fleet)
        dis = disabled_recurring(tasks)
        dis_ids = {t["id"] for t in dis}
        covered = covered_ids(tasks) & dis_ids
        missing = sorted(dis_ids - covered)
        detectors_missing = sorted(dis_ids & DETECTOR_IDS)

        print("=" * 78)
        print("%s  (%s)" % (FLEET_LABEL[fleet], path))
        print("  %d recurring disabled | %d covered by a live resume | %d MISSING"
              % (len(dis_ids), len(covered), len(missing)))
        if missing:
            exit_code = 1
            print("  MISSING RESUME for:")
            for i in missing:
                flag = "  <-- DETECTOR" if i in DETECTOR_IDS else ""
                print("    - %s%s" % (i, flag))
        else:
            print("  OK -- every disabled recurring task is named in a live enabled resume.")
        if detectors_missing:
            print("  *** dead-man chain / health-monitor coverage is DOWN for this fleet"
                  " while paused: %s ***" % ", ".join(detectors_missing))
    print("=" * 78)
    if exit_code:
        print("FAIL: at least one fleet has a disabled recurring task with no live resume.")
    else:
        print("PASS: every disabled recurring task across both fleets is covered.")
    return exit_code


RESUME_TEMPLATE = u"""---
name: {task_id}
description: One-time resume — re-enables the {n} {fleet_label} recurring tasks paused {pause_date} at Gabriel's request. Generated by tools/pause_resume.py gen-resume from the live registry (never hand-transcribed — register-scheduled-task v2.12). Auto-disables after firing. One-time task = MODEL-N/A, exempt from the [MODEL:] tag.
---

GENERATED DRAFT — NOT REGISTERED. Register via create_scheduled_task from a
SUPERVISED session on the {fleet_label} surface (register-scheduled-task Rule 1).
{surface_note}

Registration parameters:
  taskId  : {task_id}
  fireAt  : {fire_at} ET
  fleet   : {fleet_label}

---

This is a one-time resume task, generated {gen_date} from the LIVE {fleet_label}
registry (not hand-typed — see tools/pause_resume.py). Re-enable exactly these
{n} task ids via update_scheduled_task(taskId, enabled: true) — pass ONLY the
`enabled` field on each call (do not touch description/prompt/cronExpression, to
avoid reverting hand-edits made to a task's SKILL.md during the pause window):

{id_list}
{exclusions_block}
STEPS:
1. Call list_scheduled_tasks first. For each id above, confirm it still exists and
   that its `path` field resolves to the {fleet_label} store. If any id is missing,
   skip it and note it as "not found — likely retired during pause" rather than
   erroring out.
2. For each id that exists, call update_scheduled_task(taskId: <id>, enabled: true).
3. Call list_scheduled_tasks again to verify every id from the list (that still
   exists) now shows enabled: true. If any failed to flip, retry once.
4. Do NOT touch any task not on this list.
5. Do NOT bump any `[MODEL: ... | checked|set YYYY-MM-DD]` date in this pass —
   re-enabling is not an observation (memory/feedback_verified_null_vs_inferred_null.md;
   register-scheduled-task v2.12 § Bounded pause).
6. If `ora-cowork-heartbeat` or `automation-health-monitor` is in the list above,
   confirm each specifically shows enabled: true and state its next fire time in
   the summary — these are the fleet's own failure-detection mechanisms and were
   dark for the whole pause window.
7. Send ONE summary email via Outlook COM
   (C:\\Users\\Owner\\.claude\\scheduled-tasks\\_shared\\send-via-outlook.ps1 — the
   sole send path) to ggoldberg@oxfordra.net ONLY (no cc). Subject: "{fleet_label}
   routine fleet resumed (paused {pause_date} → {fire_date})". Body: ids
   re-enabled, any not-found/skipped ids, any that failed to flip after retry.
   On COM send failure: retry once; if it still fails, do not halt.
8. Do not fabricate any result. If list_scheduled_tasks or update_scheduled_task
   calls are unavailable in this session, stop and note that plainly (Rule 1).
"""

SURFACE_NOTE = {
    "cc": "Run this from Claude Code.",
    "lams": ("A cloud-sandbox Cowork session carries none of the registry MCP "
             "tools -- run this from a NATIVE on-device Cowork session "
             "(\"Run this task -> On your computer\"), never improvised."),
}


def cmd_gen_resume(args):
    tasks, _ = load_tasks(args.fleet)
    dis = disabled_recurring(tasks)
    exclude = set(x.strip() for x in (args.exclude or "").split(",") if x.strip())
    ids = sorted(t["id"] for t in dis if t["id"] not in exclude)
    if not ids:
        raise SystemExit("no disabled recurring tasks found for fleet=%s (after exclusions) "
                          "-- nothing to generate a resume for" % args.fleet)

    fire_date = args.fire_at.split(" ")[0]
    exclusions_block = ""
    if exclude:
        present = sorted(exclude & {t["id"] for t in dis})
        if present:
            exclusions_block = (
                "\nDELIBERATE EXCLUSIONS (passed via --exclude, verify still correct "
                "before registering): " + ", ".join(present) + "\n"
            )

    body = RESUME_TEMPLATE.format(
        task_id=args.id,
        n=len(ids),
        fleet_label=FLEET_LABEL[args.fleet],
        pause_date=args.pause_date or "[FILL IN]",
        gen_date=args.gen_date or "[FILL IN — Date.now() unavailable, pass --gen-date]",
        fire_at=args.fire_at,
        fire_date=fire_date,
        id_list=", ".join(ids),
        exclusions_block=exclusions_block,
        surface_note=SURFACE_NOTE[args.fleet],
    )
    if args.out:
        with io.open(args.out, "w", encoding="utf8", newline="\n") as f:
            f.write(body)
        print("wrote %s (%d ids)" % (args.out, len(ids)))
    else:
        sys.stdout.write(body)
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status", help="read-only fleet-symmetry report")

    g = sub.add_parser("gen-resume", help="generate a resume SKILL.md from the live registry")
    g.add_argument("--fleet", choices=["cc", "lams"], required=True)
    g.add_argument("--id", required=True, help="the new resume task's id")
    g.add_argument("--fire-at", required=True, help='ET timestamp, e.g. "2026-08-21 17:05"')
    g.add_argument("--exclude", default="", help="comma-separated ids to leave out")
    g.add_argument("--pause-date", default=None, help="ISO date the pause started (for the description/email text)")
    g.add_argument("--gen-date", default=None, help="ISO date this was generated (Date.now() unavailable here)")
    g.add_argument("--out", default=None, help="write to this path instead of stdout")

    args = p.parse_args()
    if args.cmd == "status":
        sys.exit(cmd_status(args))
    elif args.cmd == "gen-resume":
        sys.exit(cmd_gen_resume(args))


if __name__ == "__main__":
    main()
