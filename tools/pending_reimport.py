#!/usr/bin/env python3
"""pending_reimport.py - record which skills a commit left cache-stale.

WHY THIS EXISTS (2026-07-16): the Cowork runtime skill cache only re-syncs after
Gabriel's manual Save-skill click. A session that commits (and pushes) a SKILL.md
or the shared target-markets.json WITHOUT repackaging + reimporting leaves the
runtime on the OLD version until the next drift audit happens to catch it -- this
is exactly how acquisition-underwriting sat at v4.0 after v4.1 (b76bf94) was
committed and pushed by a concurrent session.

This helper is invoked by tools/hooks/post-commit. It CANNOT reimport the cache
(the Save-skill click is manual) -- it DETECTS the repo-ahead-of-cache drift at
commit time and writes a durable, human-visible PENDING-REIMPORT ledger so the gap
can't sit silent. package-and-stage-skill (and the drift check) clear an entry once
a confirmed Save-skill install has re-synced the runtime cache.

Ledger: _staging/PENDING_REIMPORT.md (UNTRACKED local state; see .gitignore).

Usage:
  python tools/pending_reimport.py record [<commit>]     # default HEAD
  python tools/pending_reimport.py list
  python tools/pending_reimport.py clear <skill> [...]    # after confirmed reimport
"""
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reuse the packager's single source of truth for the shared-dep fan-out + skip set,
# so this helper and package_skills.py can never disagree about which skills bundle
# a repo-root dependency.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_skills import REPO, SKIP, SHARED_ROOT_DEPS  # noqa: E402

LEDGER = REPO / '_staging' / 'PENDING_REIMPORT.md'

# reverse map: shared repo-root file -> [consumer skills that bundle it]
SHARED_CONSUMERS: dict[str, list[str]] = {}
for _skill, _deps in SHARED_ROOT_DEPS.items():
    for _d in _deps:
        SHARED_CONSUMERS.setdefault(_d, []).append(_skill)

HEADER = (
    '# PENDING REIMPORT — repo is ahead of the Cowork runtime cache\n'
    '#\n'
    '# UNTRACKED local state (see .gitignore). Written by tools/hooks/post-commit.\n'
    '# Each line = a skill whose PACKAGED content was committed but NOT yet reimported\n'
    '# into the runtime cache (Save-skill click is manual). Clear a line after a\n'
    '# CONFIRMED Save-skill install re-syncs the cache:\n'
    '#   python tools/pending_reimport.py clear <skill>\n'
    '# To act on a pending skill: package_skills.py -> present .skill -> Save-skill click.\n'
    '\n'
)


def _git(*args: str) -> str:
    return subprocess.run(
        ['git', '-C', str(REPO), *args],
        capture_output=True, text=True, check=True,
    ).stdout


def changed_files(commit: str) -> list[str]:
    out = _git('diff-tree', '--no-commit-id', '--name-only', '-r', commit)
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def is_skill_dir(top: str) -> bool:
    return top not in SKIP and (REPO / top / 'SKILL.md').is_file()


def affected_skills(files: list[str]) -> dict[str, set[str]]:
    """Map committed files -> skills needing reimport, with the triggering paths."""
    hits: dict[str, set[str]] = {}
    for f in files:
        parts = f.split('/')
        top = parts[0]
        # (a) a bundled file inside a skill directory (everything except PACKAGING-NOTE.md,
        #     which package_skills.py deliberately never bundles).
        if len(parts) > 1 and is_skill_dir(top) and parts[-1] != 'PACKAGING-NOTE.md':
            hits.setdefault(top, set()).add(f)
        # (b) a repo-root shared dependency fans out to every consumer skill.
        if '/' not in f and f in SHARED_CONSUMERS:
            for consumer in SHARED_CONSUMERS[f]:
                hits.setdefault(consumer, set()).add(f'{f} (shared dep)')
    return hits


def read_entries() -> dict[str, str]:
    """Parse existing ledger into {skill: full_line} (skips comments/blanks)."""
    entries: dict[str, str] = {}
    if not LEDGER.is_file():
        return entries
    for ln in LEDGER.read_text(encoding='utf-8').splitlines():
        s = ln.strip()
        if not s or s.startswith('#'):
            continue
        if s.startswith('- '):
            skill = s[2:].split('|', 1)[0].strip()
            if skill:
                entries[skill] = s
    return entries


def write_entries(entries: dict[str, str]) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    if not entries:
        # nothing pending -> remove the ledger so its mere presence always means "work to do"
        if LEDGER.is_file():
            LEDGER.unlink()
        return
    body = '\n'.join(entries[k] for k in sorted(entries)) + '\n'
    LEDGER.write_text(HEADER + body, encoding='utf-8')


def cmd_record(commit: str) -> None:
    files = changed_files(commit)
    hits = affected_skills(files)
    if not hits:
        return
    shorthash = _git('rev-parse', '--short', commit).strip()
    subject = _git('log', '-1', '--format=%s', commit).strip().replace('|', '/')
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    entries = read_entries()
    for skill, triggers in hits.items():
        trig = ', '.join(sorted(triggers))
        entries[skill] = (
            f'- {skill} | pending since {now} | commit {shorthash} "{subject}" | trigger: {trig}'
        )
    write_entries(entries)
    print(f'pending_reimport: recorded {len(hits)} skill(s) -> {LEDGER}')
    for skill in sorted(hits):
        print(f'   {skill}')


def cmd_list() -> None:
    entries = read_entries()
    if not entries:
        print('pending_reimport: none pending (cache in sync with repo)')
        return
    print(f'pending_reimport: {len(entries)} skill(s) awaiting Save-skill reimport:')
    for skill in sorted(entries):
        print(f'   {entries[skill]}')


def cmd_clear(skills: list[str]) -> None:
    entries = read_entries()
    cleared = [s for s in skills if entries.pop(s, None) is not None]
    write_entries(entries)
    if cleared:
        print(f'pending_reimport: cleared {", ".join(cleared)}')
    missing = [s for s in skills if s not in cleared]
    if missing:
        print(f'pending_reimport: not pending (nothing to clear): {", ".join(missing)}')


def main() -> None:
    argv = sys.argv[1:]
    cmd = argv[0] if argv else 'list'
    if cmd == 'record':
        cmd_record(argv[1] if len(argv) > 1 else 'HEAD')
    elif cmd == 'list':
        cmd_list()
    elif cmd == 'clear':
        if len(argv) < 2:
            raise SystemExit('usage: pending_reimport.py clear <skill> [...]')
        cmd_clear(argv[1:])
    else:
        raise SystemExit(__doc__.strip())


if __name__ == '__main__':
    # post-commit must never disrupt the commit: swallow everything on the record path.
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f'pending_reimport: skipped ({exc})', file=sys.stderr)
        sys.exit(0)
