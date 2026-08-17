#!/usr/bin/env python3
"""sync_local_skills_mirror.py - keep ~/.claude/skills/<skill> in sync with the repo.

WHY THIS EXISTS (2026-08-16, Automation Audit Revision 13 R13-2 / Revision 15/16
fix): ora-setup-audit itself was found DIVERGED — the canonical repo copy
(~/ora-skills/ora-setup-audit/SKILL.md) had moved to v1.4 while the Code-surface
local mirror (~/.claude/skills/ora-setup-audit/SKILL.md), which is what the
`Skill` tool actually resolves for Code sessions on this machine, was still at
v1.3. Nothing kept the two in sync — the existing post-commit hook
(pending_reimport.py) only tracks drift against the separate Cowork/AppData
runtime cache, a different store entirely, and never touches this local mirror.
A guard that lives inside the mirrored file (ora-setup-audit's own Step 0
self-check) is structurally unable to catch this for itself: it can only compare
versions AFTER being loaded, by which point a stale mirror has already been
resolved and handed to the session.

This script closes that gap at the source, the same way pending_reimport.py
closes the analogous gap for the Cowork cache: invoked from
tools/hooks/post-commit, non-blocking, it looks at what the commit touched,
and for every skill that ALREADY has a local mirror under ~/.claude/skills/,
re-copies the current bundled content over it. It deliberately does NOT create
new mirrors for skills that were never locally mirrored -- update-in-place only.

Usage:
  python tools/sync_local_skills_mirror.py [<commit>]   # default HEAD
"""
import filecmp
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pending_reimport import changed_files, affected_skills  # noqa: E402
from package_skills import REPO, skill_source_files  # noqa: E402

LOCAL_SKILLS_DIR = Path(r'C:\Users\Owner\.claude\skills')


def sync_skill(skill: str, repo_root: Path = REPO, mirror_root: Path = LOCAL_SKILLS_DIR) -> str:
    """Copy this skill's current bundled content over its local mirror, if one
    exists. Returns a one-line status string; never raises.

    repo_root/mirror_root default to the real ora-skills repo and the real
    ~/.claude/skills, but are parameterized so tests can point at synthetic
    fixture trees instead."""
    mirror_dir = mirror_root / skill
    if not mirror_dir.is_dir():
        return f'{skill}: no local mirror, skipped'
    try:
        src_files = skill_source_files(skill, repo_root=repo_root)
    except Exception as exc:  # noqa: BLE001 - never block the commit
        return f'{skill}: could not resolve source files ({exc})'
    copied = 0
    for rel_posix, src_path in src_files.items():
        dest_path = mirror_dir / rel_posix
        if dest_path.is_file() and filecmp.cmp(src_path, dest_path, shallow=False):
            continue
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest_path)
            copied += 1
        except Exception as exc:  # noqa: BLE001
            return f'{skill}: FAILED copying {rel_posix} ({exc})'
    if copied == 0:
        return f'{skill}: mirror already in sync'
    return f'{skill}: synced {copied} file(s) to local mirror'


def main() -> None:
    commit = sys.argv[1] if len(sys.argv) > 1 else 'HEAD'
    try:
        files = changed_files(commit)
        hits = affected_skills(files)
    except Exception as exc:  # noqa: BLE001 - never block the commit
        print(f'sync_local_skills_mirror: could not inspect {commit} ({exc})')
        return
    if not hits:
        return
    for skill in sorted(hits):
        print(f'local-mirror: {sync_skill(skill)}')


if __name__ == '__main__':
    main()
