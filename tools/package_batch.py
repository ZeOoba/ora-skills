#!/usr/bin/env python3
"""Package a batch of skills for a Save-skill re-import in one command.

    python tools/package_batch.py OUT_DIR SKILL [SKILL ...] [--no-baseline] [--allow-dirty]

Runs, in order, stopping at the first non-zero step:
  1. guard  -- every SKILL dir exists and, with its shared root deps (package_skills
               SHARED_ROOT_DEPS), has no uncommitted changes (a package must match the
               repo, or precheck fails later for a confusing reason); OUT_DIR is not the
               repo or a skill dir, and holds no .skill from another batch (emit hashes
               EVERY *.skill in OUT_DIR into the handoff manifest);
  2. reimport_correlate.py baseline SKILL...   (skip with --no-baseline);
  3. package_skills.py OUT_DIR SKILL...;
  4. stage_transfer.py emit OUT_DIR             (writes HANDOFF.sha256.json);
  5. reimport_correlate.py precheck OUT_DIR/SKILL.skill...

WHY: each batch used to be a hand-copied .ps1 with the skill list edited in place.
Editing one on 2026-11-02 produced a false PRECHECK_EXIT=2 (a mangled argument list),
and package_skills.py with NO skill names packages EVERY skill, so a botched edit can
silently stage the whole repo. This script takes the names as arguments and refuses
an empty list.

--allow-dirty skips the uncommitted-changes check and passes --allow-dirty-shared to
package_skills.py, so a deliberate dirty package is overridable in one place.

Exit codes: 0 all steps OK; 2 usage / guard failure; otherwise the failing step's code
(128+N for a step killed by signal N, the shell convention).
"""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))
from package_skills import SHARED_ROOT_DEPS, _dep_pair, resolve_outdir_collision  # noqa: E402


def build_steps(out_dir, skills, baseline=True, allow_dirty=False):
    """The ordered (label, argv, cwd) steps. Pure: no I/O, so it is unit-testable."""
    py = sys.executable
    out = str(Path(out_dir).resolve())
    steps = []
    if baseline:
        steps.append(("baseline", [py, str(TOOLS / "reimport_correlate.py"), "baseline", *skills], str(REPO)))
    package = [py, str(TOOLS / "package_skills.py"), out, *skills]
    if allow_dirty:
        package.append("--allow-dirty-shared")
    steps.append(("package", package, str(REPO)))
    steps.append(("emit", [py, str(TOOLS / "stage_transfer.py"), "emit", out], str(REPO)))
    steps.append(("precheck", [py, str(TOOLS / "reimport_correlate.py"), "precheck",
                               *[str(Path(out) / f"{s}.skill") for s in skills]], str(REPO)))
    return steps


def guard_out_dir(out_dir, skills, repo=REPO):
    """Problems with OUT_DIR itself (empty = OK). Runs before any step, so a swapped
    argument or a stale package never reaches the baseline step's side effects."""
    out = Path(out_dir)
    collision = resolve_outdir_collision(out, repo)
    if collision:
        return [f"OUT_DIR {out_dir} resolves to {collision} -- usage is OUT_DIR SKILL [SKILL ...]"]
    if not out.is_dir():
        return []
    ours = {f"{s}.skill" for s in skills}
    stale = sorted(f.name for f in out.glob("*.skill") if f.name not in ours)
    if stale:
        return [f"OUT_DIR {out_dir} already holds .skill files outside this batch {stale}; "
                "emit would put them in HANDOFF.sha256.json -- use a fresh OUT_DIR"]
    return []


def guard(skills, allow_dirty=False, runner=subprocess.run):
    """Return a list of problems (empty = OK)."""
    problems = []
    for s in skills:
        if s.startswith("-") or "/" in s or "\\" in s:
            problems.append(f"{s!r}: not a skill directory name")
            continue
        if not (REPO / s / "SKILL.md").is_file():
            problems.append(f"{s}: no {s}/SKILL.md in {REPO}")
            continue
        if not allow_dirty:
            deps = [_dep_pair(d)[0] for d in SHARED_ROOT_DEPS.get(s, [])]
            r = runner(["git", "-C", str(REPO), "status", "--porcelain", "--", s, *deps],
                       capture_output=True, text=True)
            if r.returncode != 0:
                problems.append(f"{s}: git status failed: {r.stderr.strip()}")
            elif r.stdout.strip():
                problems.append(f"{s}: uncommitted changes (commit first, or pass --allow-dirty):\n"
                                + r.stdout.rstrip())
    return problems


def main(argv=None, runner=subprocess.run):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0 if argv else 2
    baseline = "--no-baseline" not in argv
    allow_dirty = "--allow-dirty" in argv
    pos = [a for a in argv if a not in ("--no-baseline", "--allow-dirty")]
    unknown = [a for a in pos if a.startswith("--")]
    if unknown:
        print(f"package_batch: unknown option(s) {unknown}", file=sys.stderr)
        return 2
    if len(pos) < 2:
        print("package_batch: need OUT_DIR and at least one SKILL "
              "(package_skills.py with no names would package every skill)", file=sys.stderr)
        return 2
    out_dir, skills = pos[0], list(dict.fromkeys(pos[1:]))
    problems = guard_out_dir(out_dir, skills) + guard(skills, allow_dirty, runner)
    if problems:
        for p in problems:
            print(f"GUARD  {p}", file=sys.stderr)
        return 2
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    head = runner(["git", "-C", str(REPO), "log", "--oneline", "-1"], capture_output=True, text=True)
    print(f"repo: {REPO} @ {head.stdout.strip()}")
    for label, cmd, cwd in build_steps(out_dir, skills, baseline, allow_dirty):
        print(f"--- {label}")
        r = runner(cmd, cwd=cwd)
        if r.returncode != 0:
            print(f"STOP: step '{label}' exited {r.returncode}", file=sys.stderr)
            # a negative code is a POSIX signal kill; sys.exit(-9) would surface as 247
            return r.returncode if r.returncode > 0 else 128 - r.returncode
    print(f"OK: {len(skills)} package(s) in {Path(out_dir).resolve()} -- hand over HANDOFF.sha256.json with them")
    return 0


if __name__ == "__main__":
    sys.exit(main())
