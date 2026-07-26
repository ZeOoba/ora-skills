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

Never blocks a commit: file-copy failures (permissions, a locked file
mid-Cowork-read) are a mirror-availability problem, not a content-quality
problem — this prints what it did/skipped and always exits 0. Frontmatter
validity is check_staged()'s job (Check 2), not this one's.

CLI (also the tools/hooks/pre-commit entry point):
    python tools/sync_appdata_mirror.py [--check-staged | skill ...]

    --check-staged   sync every skill dir with staged changes (pre-commit's
                      actual call — mirrors package_skills.py's own
                      --check-staged convention)
    skill ...         sync specific named skill dirs regardless of git state
                      (no args and no --check-staged: sync every tracked
                      skill dir, for a manual full-repo re-sync)
"""
from __future__ import annotations

import os
import shutil
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


def sync_skill(skill_dir: Path, *, appdata: Path | None = None) -> list[str]:
    """Copy skill_dir's shipped files into every existing AppData mirror for
    it. Returns human-readable log lines (never raises for a missing
    mirror -- that's just nothing to report beyond an informational line)."""
    skill = skill_dir.name
    lines: list[str] = []
    mirrors = discover_mirror_dirs(skill, appdata=appdata)
    if not mirrors:
        lines.append(f'{skill}: no local AppData mirror installed yet -- nothing to sync.')
        return lines

    files = skill_source_files(skill, repo_root=skill_dir.parent)
    for mirror in mirrors:
        copied = 0
        for rel, src in files.items():
            dest = mirror / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
        lines.append(f'{skill}: synced {copied} file(s) -> {mirror}')
    return lines


def check_staged(files: list[str] | None = None) -> int:
    """tools/hooks/pre-commit entry point: sync every skill dir with staged
    changes. Always returns 0 -- a mirror-sync hiccup must never block a
    commit; this is best-effort automation of a previously-manual step, not
    a correctness gate (see check_staged() in package_skills.py for that)."""
    for skill_dir in staged_skill_dirs(files):
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

    skills = sys.argv[1:] or [d.name for d in REPO.iterdir() if d.is_dir() and is_skill_dir(d.name)]
    for skill in skills:
        for line in sync_skill(REPO / skill):
            print(line)


if __name__ == '__main__':
    main()
