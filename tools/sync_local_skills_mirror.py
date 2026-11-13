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
  python tools/sync_local_skills_mirror.py [<commit>]   # default HEAD (post-commit)
  python tools/sync_local_skills_mirror.py --all        # sweep every mirror (post-merge,
                                                        # post-rewrite; main branch only)
  python tools/sync_local_skills_mirror.py --all --check  # report drift, exit 1 if any
"""
import filecmp
import subprocess
import time
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pending_reimport import changed_files, affected_skills  # noqa: E402
from package_skills import REPO, retire_stale_private, skill_source_files  # noqa: E402

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
    retired = retire_stale_private(skill, mirror_dir, src_files)
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
    if retired:
        return '; '.join(retired) + (f'; synced {copied} file(s)' if copied else '')
    if copied == 0:
        return f'{skill}: mirror already in sync'
    return f'{skill}: synced {copied} file(s) to local mirror'


BACKUP_ROOT = Path(r'C:\Users\Owner\.claude\archive\skill-mirror-overwrites')


def _norm(path: Path) -> bytes:
    return path.read_bytes().replace(b'\r\n', b'\n')


def sweep_all(repo_root: Path = REPO, mirror_root: Path = LOCAL_SKILLS_DIR,
              backup_root: Path = BACKUP_ROOT, check: bool = False) -> list:
    """Compare EVERY existing local mirror against the repo, independent of git
    history. Returns the sorted names of drifted skills.

    WHY (2026-09-22): the post-commit hook only fires on `git commit`. main
    advances mostly by merge/pull/rebase, which run post-merge/post-rewrite, so
    16 mirrors sat stale behind merged branches (acquisition-underwriting v4.20
    vs repo v4.22, register-scheduled-task v2.21 vs v2.25). This sweep is the
    history-independent repair, wired into post-merge + post-rewrite.

    CRLF-only differences are not drift (same rule as skill_drift_report.py).
    Update-in-place only: never creates a mirror. Every mirror file about to be
    overwritten is first copied under backup_root/<timestamp>/<skill>/, so a
    mirror edited in place (a REPO-FIRST violation) is never lost.
    check=True reports drift and writes nothing."""
    stamp = time.strftime('%Y%m%d-%H%M%S')
    drifted = []
    if not mirror_root.is_dir():
        return drifted
    dirty = dirty_skills(repo_root)
    for mirror_dir in sorted(p for p in mirror_root.iterdir() if p.is_dir()):
        skill = mirror_dir.name
        if not (repo_root / skill / 'SKILL.md').is_file():
            continue
        if not check:
            # The private RCT table is never in git, so uncommitted WIP is no reason to keep a stale copy.
            for line in retire_stale_private(skill, mirror_dir, skill_source_files(skill, repo_root=repo_root)):
                print(f'local-mirror: {line}')
        if skill in dirty:
            # The sweep copies the working tree; never publish uncommitted WIP.
            print(f'local-mirror: {skill}: skipped (uncommitted changes in repo)')
            continue
        try:
            src_files = skill_source_files(skill, repo_root=repo_root)
        except Exception as exc:  # noqa: BLE001
            print(f'local-mirror: {skill}: could not resolve source files ({exc})')
            continue
        stale = [rel for rel, src in src_files.items()
                 if not (mirror_dir / rel).is_file() or _norm(mirror_dir / rel) != _norm(src)]
        if not stale:
            continue
        drifted.append(skill)
        if check:
            print(f'local-mirror: DRIFT {skill} ({len(stale)} file(s))')
            continue
        for rel in stale:
            dest = mirror_dir / rel
            try:
                if dest.is_file():
                    bak = backup_root / stamp / skill / rel
                    bak.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, bak)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_files[rel], dest)
            except Exception as exc:  # noqa: BLE001
                print(f'local-mirror: {skill}: FAILED copying {rel} ({exc})')
        print(f'local-mirror: {skill}: synced {len(stale)} file(s) (backup: {backup_root / stamp})')
    return drifted


def dirty_skills(repo_root: Path = REPO) -> set:
    """Top-level dirs with uncommitted (staged, unstaged or untracked) changes."""
    out = subprocess.run(['git', 'status', '--porcelain', '--untracked-files=all'], cwd=repo_root,
                         capture_output=True, text=True).stdout
    return {ln[3:].strip('"').split('/')[0] for ln in out.splitlines() if len(ln) > 3}


def current_branch() -> str:
    return subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if '--all' in argv:
        check = '--check' in argv
        # A write sweep from a stale feature worktree would roll live mirrors
        # back to that branch's content -- only main may write.
        if not check and current_branch() != 'main':
            print('local-mirror: --all sweep skipped (not on main)')
            return 0
        try:
            drifted = sweep_all(check=check)
        except Exception as exc:  # noqa: BLE001 - never block git
            print(f'sync_local_skills_mirror: sweep failed ({exc})')
            return 0
        return 1 if (check and drifted) else 0
    commit = argv[0] if argv else 'HEAD'
    try:
        files = changed_files(commit)
        hits = affected_skills(files)
    except Exception as exc:  # noqa: BLE001 - never block the commit
        print(f'sync_local_skills_mirror: could not inspect {commit} ({exc})')
        return 0
    for skill in sorted(hits):
        print(f'local-mirror: {sync_skill(skill)}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
