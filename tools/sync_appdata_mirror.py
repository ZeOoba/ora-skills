#!/usr/bin/env python3
"""tools/sync_appdata_mirror.py — automates the "dual-write discipline" the
README has documented as a manual convention: every skill change here must
also land in the AppData runtime cache mirror Cowork reads from. That cache
is a rebuildable mirror, never the source of truth — this repo wins on
divergence — but nothing was actually copying the bytes across; a session
had to remember to do it by hand, and the README itself notes the inventory
"has drifted stale before (once for a full month)".

This is a pre-commit hook step (Check 4), not a packaging step: it does NOT
build a .skill/.plugin zip (see package_skills.py / build_plugin.py for
that) — it copies each staged skill's shipped files (the exact set
package_skills.skill_source_files() already computes, so the mirror and a
real package can never disagree about content) directly into whichever
already-installed AppData mirror directories exist for that skill.

Discovery, not a hardcoded path: a skill only has a mirror to sync into if
it has already been imported into Cowork via "Save skill" / Settings ->
Capabilities at least once (the README's own dual-write section assumes
this precondition without stating it). This module globs every
<APPDATA>/Claude/local-agent-mode-sessions/skills-plugin/*/*/skills/<skill>/
directory that already exists rather than assuming a single fixed uuid
pair -- more than one plugin-cache root can exist on one machine, and none
of the 5 skills this repo tracks were found installed under any uuid pair
as of 2026-07-26 (verified by a full-tree search before writing this).

Additive-only by design: copies/overwrites files the skill ships, never
deletes anything already present in the mirror that isn't part of
skill_source_files(). A destructive two-way sync risks deleting installer
metadata this module has no visibility into; an additive copy still closes
the actual gap (stale/missing content after a repo edit) without that risk.

Write gates (2026-09-23): the cache is written only (a) from the PRIMARY
checkout with main checked out -- never a linked worktree or feature branch --
and (b) into a mirror where every SHIPPED file's repo_first_check direction
verdict is IN-SYNC or REPO-AHEAD. Any other shipped-file verdict (CACHE-AHEAD,
DIVERGENT, MAIN-BEHIND-ORIGIN, UNKNOWN) leaves the mirror untouched and is
reported: the cache is what Cowork loads, so rescuing an overwritten copy
afterwards is not enough. Cache-only files (REPO-MISSING) are ignored -- the
additive sync never writes or deletes them.

Never blocks a commit: file-copy failures (permissions, a locked file
mid-Cowork-read) are a mirror-availability problem, not a content-quality
problem — this prints what it did/skipped and always exits 0. Frontmatter
validity is check_staged()'s job (Check 2), not this one's.

CLI (also the tools/hooks/pre-commit entry point):
    python tools/sync_appdata_mirror.py [--check-staged | skill ...]

    --check-staged   sync every skill dir with staged changes (pre-commit's
                      actual call — mirrors package_skills.py's own
                      --check-staged convention)
    --changed-range OLD NEW
                      sync skills whose shipped files changed between two commits
                      (post-merge / post-rewrite: a merge or fast-forward on main
                      runs no pre-commit hook)
    skill ...         sync specific named skill dirs regardless of git state
                      (no args and no --check-staged: sync every tracked
                      skill dir, for a manual full-repo re-sync)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from package_skills import REPO, is_skill_dir, skill_source_files, staged_skill_dirs


def appdata_root() -> Path | None:
    """The Roaming AppData root (%APPDATA%), or None if unresolvable (e.g. a
    non-Windows CI runner) -- callers must treat that as "no mirrors exist",
    never as an error."""
    appdata = os.environ.get('APPDATA')
    return Path(appdata) if appdata else None


def discover_mirror_dirs(skill: str, *, appdata: Path | None = None) -> list[Path]:
    """Every already-existing <APPDATA>/Claude/local-agent-mode-sessions/
    skills-plugin/*/*/skills/<skill>/ directory on this machine, sorted.
    Returns [] if APPDATA is unset, the skills-plugin root doesn't exist, or
    no uuid-pair has this skill installed -- all non-error, "nothing to sync
    into yet" states."""
    root = appdata_root() if appdata is None else appdata
    if root is None:
        return []
    base = root / 'Claude' / 'local-agent-mode-sessions' / 'skills-plugin'
    if not base.is_dir():
        return []
    return sorted(p for p in base.glob(f'*/*/skills/{skill}') if p.is_dir())


# Directions in which overwriting the cache is safe: it holds either exactly the
# repo's content or an older point on HEAD's history. Every other verdict means the
# cache holds something the repo does not (a platform-side edit, a branch copy,
# content from origin/main that local main lacks, or an undeterminable state), and
# writing over it destroys the only copy Cowork loads (2026-09-22 pma-qc v1.3).
WRITABLE_VERDICTS = ('IN-SYNC', 'REPO-AHEAD')


def cache_verdict(skill: str, repo_root: Path, mirror: Path) -> str:
    """Direction verdict for one installed mirror dir, over the files this sync
    would WRITE. repo_first_check.classify_skill headlines the worst file, and it
    ranks a cache-only file (REPO-MISSING) as high as CACHE-AHEAD -- but the additive
    sync never writes or deletes a cache-only file, so counting it would block the
    skill forever after any shipped-file deletion or rename (review finding
    2026-09-23; lease-form-qc was already stuck on cached .pytest_cache junk).
    REPO-MISSING rows are therefore excluded; every other per-file verdict counts.
    RUNTIME-STATE rows (git-ignored cache-only runtime files, e.g. runs/ or
    .pytest_cache/, classified separately since 2026-11-02) are cache-only too, so
    they are excluded for the same reason: counting them would stop the sync for
    good on any skill whose cache holds run state (merge-gate finding, PR #196)."""
    from repo_first_check import classify_skill
    verdict, per_file = classify_skill(skill, repo_root=repo_root, cache_root=mirror.parent)
    if not per_file:
        return verdict
    shipped = [v for _, v in per_file if v not in ('REPO-MISSING', 'RUNTIME-STATE')]
    unsafe = [v for v in shipped if v not in WRITABLE_VERDICTS]
    if unsafe:
        return unsafe[0]
    return 'REPO-AHEAD' if 'REPO-AHEAD' in shipped else 'IN-SYNC'


def _git(*args: str) -> str:
    return subprocess.run(['git', *args], cwd=REPO, capture_output=True, text=True,
                          check=True).stdout.strip()


def is_canonical_checkout() -> bool:
    """True only in the PRIMARY checkout with `main` checked out. A linked worktree
    (git-dir != git-common-dir) or any other branch holds unreviewed content: on
    2026-09-23 a feature-branch commit in a worktree wrote a pre-review
    register-scheduled-task v2.29 over a just-installed v2.28 for 11 minutes."""
    try:
        branch = _git('rev-parse', '--abbrev-ref', 'HEAD')
        git_dir = Path(_git('rev-parse', '--absolute-git-dir')).resolve()
        common = Path(_git('rev-parse', '--git-common-dir'))
        common = (common if common.is_absolute() else REPO / common).resolve()
    except (OSError, subprocess.CalledProcessError):
        return False
    return branch == 'main' and git_dir == common


def sync_skill(skill_dir: Path, *, appdata: Path | None = None) -> list[str]:
    """Copy skill_dir's shipped files into every existing AppData mirror for
    it whose direction verdict is in WRITABLE_VERDICTS. Returns human-readable
    log lines (never raises for a missing mirror -- that's just nothing to
    report beyond an informational line)."""
    skill = skill_dir.name
    lines: list[str] = []
    mirrors = discover_mirror_dirs(skill, appdata=appdata)
    if not mirrors:
        lines.append(f'{skill}: no local AppData mirror installed yet -- nothing to sync.')
        return lines

    files = skill_source_files(skill, repo_root=skill_dir.parent)
    for mirror in mirrors:
        try:
            verdict = cache_verdict(skill, skill_dir.parent, mirror)
        except Exception as exc:  # noqa: BLE001 - fail closed, never block the commit
            verdict = f'UNKNOWN ({exc})'
        if verdict not in WRITABLE_VERDICTS:
            lines.append(f'{skill}: cache {verdict} -- NOT written ({mirror}). '
                         f'Reconcile with repo_first_check.py before reimporting.')
            continue
        copied = 0
        for rel, src in files.items():
            dest = mirror / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
        lines.append(f'{skill}: synced {copied} file(s) -> {mirror}')
    return lines


def _sync_all(skill_dirs) -> None:
    for skill_dir in skill_dirs:
        try:
            for line in sync_skill(skill_dir):
                print(line)
        except OSError as exc:
            # Best-effort: a copy failure (locked file, permissions) is reported,
            # never fatal -- see module docstring.
            print(f'{skill_dir.name}: mirror sync skipped (non-fatal): {exc}', file=sys.stderr)


def skills_changed_between(old: str, new: str) -> list[Path]:
    """Skill dirs whose shipped files differ between two commits."""
    from pending_reimport import affected_skills
    out = _git('diff', '--name-only', old, new)
    return [REPO / s for s in sorted(affected_skills([ln for ln in out.splitlines() if ln]))]


def sync_changed_range(old: str, new: str) -> int:
    """post-merge / post-rewrite entry point: a merge, pull or fast-forward on main
    runs no pre-commit hook, so skills it brings in are synced here -- same gates.
    Always returns 0."""
    if not is_canonical_checkout():
        return 0
    try:
        dirs = skills_changed_between(old, new)
    except Exception as exc:  # noqa: BLE001
        print(f'sync_appdata_mirror: could not diff {old}..{new} ({exc})', file=sys.stderr)
        return 0
    _sync_all(dirs)
    return 0


def check_staged(files: list[str] | None = None) -> int:
    """tools/hooks/pre-commit entry point: sync every skill dir with staged
    changes, but only from the primary checkout on main. Always returns 0 -- a
    mirror-sync hiccup must never block a commit; this is best-effort
    automation, not a correctness gate (see check_staged() in package_skills.py
    for that). A deferred skill is not lost: `pending_reimport.py candidates`
    sweeps repo-vs-cache content, and post-merge syncs it once it lands."""
    dirs = staged_skill_dirs(files)
    if dirs and not is_canonical_checkout():
        print('sync_appdata_mirror: not the primary checkout on main -- runtime cache NOT '
              'written for ' + ', '.join(d.name for d in dirs) + ' (it syncs when the change reaches main in the primary checkout, via post-merge).')
        return 0
    for skill_dir in dirs:
        try:
            for line in sync_skill(skill_dir):
                print(line)
        except OSError as exc:
            # Best-effort: a copy failure (locked file, permissions) is reported,
            # never fatal -- see module docstring.
            print(f'{skill_dir.name}: mirror sync skipped (non-fatal): {exc}', file=sys.stderr)
    return 0


def main() -> None:
    if len(sys.argv) >= 2 and sys.argv[1] == '--check-staged':
        sys.exit(check_staged())
    if len(sys.argv) == 4 and sys.argv[1] == '--changed-range':
        sys.exit(sync_changed_range(sys.argv[2], sys.argv[3]))

    skills = sys.argv[1:] or [d.name for d in REPO.iterdir() if d.is_dir() and is_skill_dir(d.name)]
    for skill in skills:
        for line in sync_skill(REPO / skill):
            print(line)


if __name__ == '__main__':
    main()
