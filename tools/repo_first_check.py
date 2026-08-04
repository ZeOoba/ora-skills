#!/usr/bin/env python
"""REPO-FIRST violation detector: is the AppData runtime cache AHEAD of the repo?

The problem this exists for
---------------------------
`tools/sync_appdata_mirror.py --check-staged` (pre-commit Check 4) copies every
staged skill's shipped files INTO the runtime-cache mirror. It is additive-only
in intent, but it overwrites unconditionally -- so a skill that was edited
platform-side and never committed (a REPO-FIRST violation) is silently CLOBBERED
by the next commit that touches it. The evidence of the violation is destroyed by
the very mechanism meant to keep the two stores together.

That is not hypothetical. acquisition-underwriting drifted cache-ahead twice in
eight days (v4.5 on 2026-07-25, v4.6 on 2026-07-27), and the weekly
`ora-skill-store-drift-check` (Mon 12:10) is the only thing that has ever caught
it -- up to seven days late, and only if no commit clobbered it first.

What this does
--------------
Runs BEFORE the mirror sync. For each skill it classifies the direction of any
cache-vs-repo difference, reusing the exact same pure classifier the shared-dep
path already uses (`pending_reimport.classify_shared_copy`):

    IN-SYNC      cache == repo working file
    REPO-AHEAD   cache is an older point on HEAD's history  -> normal; reimport fixes it
    CACHE-AHEAD  cache content was never committed anywhere -> REPO-FIRST VIOLATION
    DIVERGENT    cache matches a commit off HEAD's ancestry -> manual reconcile
    UNKNOWN      git unavailable / file untracked

On CACHE-AHEAD or DIVERGENT it (a) prints a loud warning and (b) RESCUES the
cache copy to `_staging/repo-first-rescue/<skill>/` so the about-to-be-clobbered
content survives for review.

It NEVER blocks a commit -- same posture as Check 4, and for the same reason: a
mirror-state finding is not a content-quality finding, and a false positive here
must not be able to stop Gabriel committing. Fail-open on every error path.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from package_skills import is_bundled  # noqa: E402
from pending_reimport import (  # noqa: E402
    CACHE_ROOT,
    REPO,
    _file_history_hashes,
    _isdir_long,
    _isfile_long,
    _normalized_hash_bytes,
    _read_bytes_long,
    _win_long,
    all_skill_dirs,
    classify_shared_copy,
)

RESCUE_DIR = REPO / '_staging' / 'repo-first-rescue'


def _hash_file(path: Path):
    """EOL-normalized content hash, with trailing NUL padding stripped.

    NUL padding is a platform-upload artifact, not content (ora-skill-store-drift-check
    step 2b) -- a padded-but-identical cache file must read IN-SYNC, not CACHE-AHEAD,
    or this check would false-positive on every padded skill.

    Long-path-safe (pending_reimport._read_bytes_long) -- a deep cache path past
    MAX_PATH must raise OSError like a genuinely missing/locked file, not silently
    misread, since this already degrades to None on OSError.
    """
    try:
        return _normalized_hash_bytes(_read_bytes_long(path).rstrip(b'\x00'))
    except OSError:
        return None


def _staged_skills() -> list[str]:
    try:
        out = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            cwd=REPO, capture_output=True, text=True, check=False,
        ).stdout
    except OSError:
        return []
    skills = set()
    for line in out.splitlines():
        top = line.split('/')[0]
        if top and (REPO / top / 'SKILL.md').is_file():
            skills.add(top)
    return sorted(skills)


def _packaged_rel_paths(skill: str) -> list[str]:
    sd = REPO / skill
    rels = []
    for p in sd.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(sd).as_posix()
        try:
            keep = is_bundled(rel)
        except TypeError:
            keep = is_bundled(str(p))
        if keep:
            rels.append(rel)
    return sorted(rels)


def classify_skill(skill: str):
    """-> (verdict, [(relpath, verdict), ...]). Worst verdict wins."""
    cache_dir = Path(CACHE_ROOT) / skill
    if not _isdir_long(cache_dir):
        return 'NOT-INSTALLED', []

    order = {'IN-SYNC': 0, 'REPO-AHEAD': 1, 'UNKNOWN': 2, 'DIVERGENT': 3, 'CACHE-AHEAD': 4}
    per_file, worst = [], 'IN-SYNC'

    for rel in _packaged_rel_paths(skill):
        repo_p, cache_p = REPO / skill / rel, cache_dir / rel
        if not _isfile_long(cache_p):
            continue                      # MISSING-IN-CACHE is the reimport path's finding
        repo_h, cache_h = _hash_file(repo_p), _hash_file(cache_p)
        if repo_h is None or cache_h is None:
            verdict = 'UNKNOWN'
        elif repo_h == cache_h:
            verdict = 'IN-SYNC'
        else:
            anc, allh = _file_history_hashes(REPO, f'{skill}/{rel}')
            verdict = classify_shared_copy(cache_h, repo_h, anc, allh)
        per_file.append((rel, verdict))
        if order.get(verdict, 2) > order.get(worst, 0):
            worst = verdict
    return worst, per_file


def rescue(skill: str, rels: list[str]) -> Path | None:
    dest = RESCUE_DIR / skill
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for rel in rels:
            src = Path(CACHE_ROOT) / skill / rel
            tgt = dest / rel
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_win_long(src), tgt)  # long-path-safe source read
        return dest
    except OSError as exc:                # never let a rescue failure block anything
        print(f'repo_first_check: rescue copy failed for {skill}: {exc}', file=sys.stderr)
        return None


def main() -> int:
    argv = sys.argv[1:]
    skills = _staged_skills() if '--check-staged' in argv else all_skill_dirs(REPO)
    quiet = '--check-staged' in argv

    findings = []
    for skill in skills:
        try:
            verdict, per_file = classify_skill(skill)
        except Exception as exc:          # fail open, always
            print(f'repo_first_check: {skill} check errored ({exc}) -- skipped', file=sys.stderr)
            continue
        if verdict in ('CACHE-AHEAD', 'DIVERGENT'):
            findings.append((skill, verdict, per_file))
        elif not quiet:
            print(f'  {skill:<34} {verdict}')

    why = {
        'CACHE-AHEAD': 'runtime cache holds content that was never committed on ANY branch',
        'DIVERGENT': 'runtime cache matches a commit OFF this branch\'s ancestry',
    }
    fix = {
        'CACHE-AHEAD': 'Edited platform-side and never committed -- commit it to the repo first.',
        'DIVERGENT': 'Installed from another branch -- reconcile the branches, do not auto-reimport.',
    }
    for skill, verdict, per_file in findings:
        bad = [rel for rel, v in per_file if v in ('CACHE-AHEAD', 'DIVERGENT')]
        print('', file=sys.stderr)
        print(f'!! REPO-FIRST {verdict}: {skill}', file=sys.stderr)
        for rel in bad:
            print(f'     {rel} -- {why[verdict]}', file=sys.stderr)
        print(f'   {fix[verdict]}', file=sys.stderr)
        print('   The mirror sync that runs next WILL overwrite it.', file=sys.stderr)
        dest = rescue(skill, bad)
        if dest:
            print(f'   Rescued the cache copy -> {dest}', file=sys.stderr)
            print('   Reconcile it into the repo before relying on either store.', file=sys.stderr)

    if not findings and not quiet:
        print('repo_first_check: no cache-ahead skills (repo leads the platform)')
    return 0                              # advisory only -- never blocks


if __name__ == '__main__':
    sys.exit(main())
