#!/usr/bin/env python3
"""One-call wrapper for the package-and-stage-skill reimport cycle.

Every standalone reimport runs the same sequence: step-0 plugin gate, step-1
git-clean check, shared-dep direction gate, description budget, CreationTime
baseline, ONE packager call, and -- after Gabriel clicks Save skill -- verify,
a single event-log append, ledger clear and the closing sweep. This script
chains the existing tools; it adds no new source of truth.

Usage
-----
    python tools/reimport_cycle.py prep <skill> [<skill> ...] [--out DIR]
        Gates, baseline, package. Stops (exit 1) before packaging if any skill
        is a plugin member, has a dirty tree, or is a shared-dep consumer whose
        dep reads CACHE-AHEAD / DIVERGENT / UNKNOWN. Default --out:
        _staging/<today>/pkg. Prints each package's SHA256 for the cloud-side
        byte check, and whether it is MULTI-FILE (Cowork Save skill only).

    python tools/reimport_cycle.py close <skill> [<skill> ...]
                                     [--note TEXT] [--no-clear] [--no-sweep]
                                     [--baseline "YYYY-MM-DD HH:MM:SS"]
        After the click(s). Runs `reimport_correlate.py postclick --no-append`
        per skill (log liveness + verify). ONLY if every skill is CONFIRMED:
        one combined event-log append via append-event-log.py --entry-file
        (exit 0 required), THEN pending_reimport.py clear per skill, THEN the
        closing sweep (repo_first_check, frontmatter_sweep,
        verify_installed_cache). Any non-CONFIRMED verdict stops with exit 1
        and appends nothing.

Host-only: needs the real AppData cache and main.log (Code surface or the
Desktop Commander bridge). From Cowork bash it inherits CACHE_ROOT blindness.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
APPEND = Path.home() / ".claude" / "maintenance" / "append-event-log.py"
BAD_DEP_LABELS = ("CACHE-AHEAD", "DIVERGENT", "UNKNOWN")

sys.path.insert(0, str(TOOLS))


def _run(args: list[str], echo: bool = True) -> subprocess.CompletedProcess:
    cp = subprocess.run([sys.executable, *args], cwd=REPO, capture_output=True,
                        text=True, encoding="utf-8", errors="replace")
    if echo:
        out = (cp.stdout + cp.stderr).rstrip()
        if out:
            print(out)
    return cp


def gate_failures(skill: str, plugin_of, git_dirty, shared_dep_consumers,
                  dep_report: str) -> list[str]:
    """Pure gate logic (unit-tested). Returns reasons to STOP for one skill."""
    bad = []
    if not (REPO / skill / "SKILL.md").is_file():
        bad.append("no SKILL.md in repo")
    p = plugin_of(skill)
    if p:
        bad.append(f"plugin member of {p!r} -- rebuild the plugin, not a .skill")
    if git_dirty(skill):
        bad.append("dirty working tree -- commit by pathspec first")
    if skill in shared_dep_consumers:
        for line in dep_report.splitlines():
            if any(lbl in line for lbl in BAD_DEP_LABELS) and skill in line:
                bad.append(f"shared dep: {line.strip()}")
    return bad


def _git_dirty(skill: str) -> bool:
    cp = subprocess.run(["git", "status", "--short", "--", f"{skill}/"],
                        cwd=REPO, capture_output=True, text=True)
    return bool(cp.stdout.strip())


def cmd_prep(skills: list[str], out: Path) -> int:
    from package_skills import plugin_of, SHARED_ROOT_DEPS  # noqa: E402
    consumers = set(SHARED_ROOT_DEPS)
    print("== shared-deps")
    deps = _run([str(TOOLS / "pending_reimport.py"), "shared-deps"])
    stop = False
    for s in skills:
        bad = gate_failures(s, plugin_of, _git_dirty, consumers, deps.stdout)
        last = subprocess.run(["git", "log", "-1", "--format=%h %ci %s", "--", f"{s}/"],
                              cwd=REPO, capture_output=True, text=True).stdout.strip()
        print(f"== {s}: last commit {last}")
        for b in bad:
            print(f"   STOP: {b}")
        stop = stop or bool(bad)
    if stop:
        print("prep: gate failed -- nothing packaged.")
        return 1
    _run([str(TOOLS / "description_budget.py"), *skills])
    print("== baseline")
    if _run([str(TOOLS / "reimport_correlate.py"), "baseline", *skills]).returncode:
        return 1
    out.mkdir(parents=True, exist_ok=True)
    print(f"== package -> {out}")
    cp = _run([str(TOOLS / "package_skills.py"), str(out), *skills])
    if cp.returncode:
        print(f"PACKAGER_EXIT={cp.returncode} -- real defect, quote verbatim; do not work around.")
        return cp.returncode
    print("== packages")
    for s in skills:
        pkg = out / f"{s}.skill"
        n = len([e for e in zipfile.ZipFile(pkg).namelist() if not e.endswith("/")])
        kind = "MULTI-FILE (Cowork Save skill only)" if n > 1 else "single-file"
        sha = hashlib.sha256(pkg.read_bytes()).hexdigest().upper()
        print(f"   {pkg.name}  {n} files  {kind}  sha256={sha}")
    return 0


def cmd_close(skills: list[str], note: str | None, clear: bool, sweep: bool,
              baseline: str | None = None) -> int:
    failed = []
    for s in skills:
        print(f"== postclick {s}")
        extra = ["--baseline", baseline] if baseline else []
        if _run([str(TOOLS / "reimport_correlate.py"), "postclick", s,
                 "--no-append", *extra]).returncode:
            failed.append(s)
    if failed:
        print(f"close: STOP -- not CONFIRMED: {', '.join(failed)}. Nothing appended.")
        return 1
    today = _dt.date.today().isoformat()
    body = note or (f"{', '.join(skills)} reimported via Cowork Save-skill; "
                    "reimport_correlate CONFIRMED.")
    entry = REPO / "_staging" / today / "reimport_cycle_entry.md"
    entry.parent.mkdir(parents=True, exist_ok=True)
    entry.write_text(f"## {today} -- {', '.join(skills)} reimport\n\n{body}\n",
                     encoding="utf-8")
    print("== event log")
    if _run([str(APPEND), "--entry-file", str(entry)]).returncode:
        print("close: append FAILED -- ledger NOT cleared.")
        return 1
    # postclick ran with --no-append, so it left the baselines in place; the install is
    # recorded now, so use them up (a kept baseline would CONFIRM this install again).
    consume_rc = _run([str(TOOLS / "reimport_correlate.py"), "consume", *skills]).returncode
    if consume_rc:
        print("close: WARNING -- baseline(s) NOT used up; run `reimport_correlate.py consume "
              f"{' '.join(skills)}` before the next reimport, or it will CONFIRM this one again.")
    if clear:
        for s in skills:
            _run([str(TOOLS / "pending_reimport.py"), "clear", s])
    if sweep:
        print("== closing sweep")
        rc = 0
        for args in (["repo_first_check.py"], ["frontmatter_sweep.py"],
                     ["verify_installed_cache.py", *skills]):
            r = _run([str(TOOLS / args[0]), *args[1:]], echo=False)
            tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
            print(f"   {args[0]}: exit {r.returncode} | {tail[0]}")
            rc |= r.returncode
        _run([str(TOOLS / "pending_reimport.py"), "list"])
        if rc:
            print("close: closing sweep reported findings -- re-run the failing tool.")
            return 1
    return 1 if consume_rc else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("prep")
    p.add_argument("skills", nargs="+")
    p.add_argument("--out", type=Path,
                   default=REPO / "_staging" / _dt.date.today().isoformat() / "pkg")
    c = sub.add_parser("close")
    c.add_argument("skills", nargs="+")
    c.add_argument("--note")
    c.add_argument("--no-clear", action="store_true")
    c.add_argument("--no-sweep", action="store_true")
    c.add_argument("--baseline", help='"YYYY-MM-DD HH:MM:SS" -- when prep ran in another '
                                      'session (baselines are session-scoped)')
    a = ap.parse_args(argv)
    if a.cmd == "prep":
        return cmd_prep(a.skills, a.out)
    return cmd_close(a.skills, a.note, not a.no_clear, not a.no_sweep, a.baseline)


if __name__ == "__main__":
    sys.exit(main())
