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

import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
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
    read_entries,
    write_entries,
)

RESCUE_DIR = REPO / '_staging' / 'repo-first-rescue'

# The reverse-direction companion to _staging/PENDING_REIMPORT.md (which only ever
# tracks repo-ahead-of-cache, seeded at commit time). This ledger is written by a
# FULL SWEEP (`python tools/repo_first_check.py`, no --check-staged) so a skill nobody
# is currently committing to -- exactly how masterlease-jurisdiction-rebase drifted
# unnoticed three times on 2026-08-04 -- still gets caught and stays durably visible
# past this run's console output, instead of requiring someone to think to run this by
# hand and read it before the terminal scrolls.
LEDGER = REPO / '_staging' / 'STORE_AHEAD_OF_REPO.md'

LEDGER_HEADER = (
    '# STORE AHEAD OF REPO -- runtime cache holds content never committed to this repo\n'
    '#\n'
    '# UNTRACKED local state (see .gitignore). Written by a FULL-SWEEP run of\n'
    '# tools/repo_first_check.py (`python tools/repo_first_check.py`, no --check-staged --\n'
    '# that flag only inspects skills already staged in the commit about to happen and\n'
    '# cannot see this direction of drift on a skill nobody is committing to). Each line is\n'
    '# a skill where the AppData runtime cache is CACHE-AHEAD or DIVERGENT vs this repo on\n'
    '# at least one shipped file -- i.e. edited platform-side (Cowork create-skill /\n'
    '# save_skill / a direct cache write) and never committed here. This is the REVERSE of\n'
    '# _staging/PENDING_REIMPORT.md (repo-ahead-of-cache, pending a Save-skill reimport).\n'
    '# Companion rescue copies of the about-to-be-clobbered cache content (if a commit has\n'
    '# since touched the skill) live under _staging/repo-first-rescue/<skill>/.\n'
    '#\n'
    '# THIS LEDGER IS DERIVED, NOT AN EVENT LOG -- unlike PENDING_REIMPORT.md, no line here\n'
    '# is ever hand-cleared. It reflects live state as of the last full-sweep run: commit the\n'
    '# drifted file(s) into the repo (repo-first rule) and the entry clears itself on the\n'
    '# next full sweep once content matches again. The "pending since" timestamp is carried\n'
    '# forward from a skill\'s first-seen run so staleness is visible even as the ledger\n'
    '# content itself refreshes every run.\n'
    '\n'
)


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


def _staged_skills(repo_root: Path = REPO) -> list[str]:
    try:
        out = subprocess.run(
            ['git', 'diff', '--cached', '--name-only'],
            cwd=repo_root, capture_output=True, text=True, check=False,
        ).stdout
    except OSError:
        return []
    skills = set()
    for line in out.splitlines():
        top = line.split('/')[0]
        if top and (repo_root / top / 'SKILL.md').is_file():
            skills.add(top)
    return sorted(skills)


def _packaged_rel_paths(skill: str, repo_root: Path = REPO) -> list[str]:
    sd = repo_root / skill
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


def classify_skill(skill: str, repo_root: Path = REPO, cache_root: Path = CACHE_ROOT):
    """-> (verdict, [(relpath, verdict), ...]). Worst verdict wins.

    repo_root/cache_root are parameterized (matching every other drift function in
    this repo -- pending_reimport.sweep_drift, skill_drift_report.report) so this can
    be exercised against a synthetic fixture tree in tests, not just the live stores.
    """
    cache_dir = Path(cache_root) / skill
    if not _isdir_long(cache_dir):
        return 'NOT-INSTALLED', []

    # DIVERGENT outranks CACHE-AHEAD (2026-08-04 fix, found writing this function's
    # first tests): CACHE-AHEAD has one clean fix ("commit it"), but DIVERGENT means
    # the cache matches a commit OFF this branch's ancestry -- a branch-level mixup
    # that needs manual reconciliation and must NOT be auto-reimported, matching
    # skill_drift_report.combine_verdict's own DIVERGENT/UNKNOWN-always-wins ordering.
    # A skill with one file of each must report DIVERGENT, the more cautious verdict --
    # the previous ordering silently downgraded it to CACHE-AHEAD's simpler "just
    # commit it" fix, which is wrong for the DIVERGENT file specifically.
    order = {'IN-SYNC': 0, 'REPO-AHEAD': 1, 'UNKNOWN': 2, 'CACHE-AHEAD': 3, 'DIVERGENT': 4}
    per_file, worst = [], 'IN-SYNC'

    for rel in _packaged_rel_paths(skill, repo_root):
        repo_p, cache_p = repo_root / skill / rel, cache_dir / rel
        if not _isfile_long(cache_p):
            continue                      # MISSING-IN-CACHE is the reimport path's finding
        repo_h, cache_h = _hash_file(repo_p), _hash_file(cache_p)
        if repo_h is None or cache_h is None:
            verdict = 'UNKNOWN'
        elif repo_h == cache_h:
            verdict = 'IN-SYNC'
        else:
            anc, allh = _file_history_hashes(repo_root, f'{skill}/{rel}')
            verdict = classify_shared_copy(cache_h, repo_h, anc, allh)
        per_file.append((rel, verdict))
        if order.get(verdict, 2) > order.get(worst, 0):
            worst = verdict
    return worst, per_file


def _now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')


def _sweep_findings(repo_root: Path = REPO, cache_root: Path = CACHE_ROOT):
    """[(skill, verdict, per_file)] for every skill in the repo, full sweep -- not
    just a commit's staged set. This is the only path that can see a skill nobody is
    currently committing to, which is exactly how masterlease-jurisdiction-rebase
    drifted unnoticed on 2026-08-04: no commit touched it, so --check-staged never
    looked at it at all."""
    out = []
    for skill in all_skill_dirs(repo_root):
        try:
            verdict, per_file = classify_skill(skill, repo_root, cache_root)
        except Exception as exc:          # fail open, always -- one bad skill must
            print(f'repo_first_check: {skill} check errored ({exc}) -- skipped',  # not
                  file=sys.stderr)         # abort the sweep for every other skill
            continue
        if verdict in ('CACHE-AHEAD', 'DIVERGENT'):
            out.append((skill, verdict, per_file))
    return out


def record_ledger(findings, ledger_path: Path = LEDGER) -> list[str]:
    """Persist full-sweep CACHE-AHEAD/DIVERGENT findings to the durable
    STORE_AHEAD_OF_REPO ledger. A full sweep is cheap and authoritative for "right
    now", so each call REPLACES the ledger contents rather than merging -- but each
    skill's original "pending since" timestamp is carried forward from the prior
    ledger (read_entries) so staleness stays visible instead of resetting to now on
    every run. Returns the skill names that were in the previous ledger but are no
    longer drifted -- auto-cleared, via write_entries()'s existing
    empty-ledger-deletes-the-file convention (shared with PENDING_REIMPORT.md).
    """
    existing = read_entries(ledger_path)
    now = _now()
    entries = {}
    for skill, verdict, per_file in findings:
        bad = [rel for rel, v in per_file if v in ('CACHE-AHEAD', 'DIVERGENT')]
        since = now
        m = re.search(r'pending since (\S+)', existing.get(skill, ''))
        if m:
            since = m.group(1)
        entries[skill] = (
            f'- {skill} | pending since {since} | direction: {verdict} | '
            f'files: {", ".join(bad) if bad else "(see console output)"} | '
            f'remedy: commit to the repo first -- the mirror sync (pre-commit Check 4) '
            f'will otherwise clobber this on the next commit that touches this skill'
        )
    write_entries(entries, ledger_path, LEDGER_HEADER)
    return sorted(set(existing) - set(entries))


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
    check_staged = '--check-staged' in argv
    skills = _staged_skills() if check_staged else all_skill_dirs(REPO)
    quiet = check_staged

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
        # Each bad FILE keeps its OWN verdict for the why/fix text (2026-08-04 fix,
        # found writing this function's first tests) -- a skill can have one
        # CACHE-AHEAD file and one DIVERGENT file, and the skill-level aggregate
        # `verdict` (the worse of the two, used only for the banner line) previously
        # mislabeled every file with that single verdict's explanation, telling a
        # DIVERGENT file's reader to "just commit it" when the real fix is "reconcile
        # the branches, do not auto-reimport."
        bad = [(rel, v) for rel, v in per_file if v in ('CACHE-AHEAD', 'DIVERGENT')]
        print('', file=sys.stderr)
        print(f'!! REPO-FIRST {verdict}: {skill}', file=sys.stderr)
        for rel, v in bad:
            print(f'     {rel} -- {why[v]}', file=sys.stderr)
        for v in ('CACHE-AHEAD', 'DIVERGENT'):
            if v in {bv for _, bv in bad}:
                print(f'   {fix[v]}', file=sys.stderr)
        print('   The mirror sync that runs next WILL overwrite it.', file=sys.stderr)
        dest = rescue(skill, [rel for rel, _ in bad])
        if dest:
            print(f'   Rescued the cache copy -> {dest}', file=sys.stderr)
            print('   Reconcile it into the repo before relying on either store.', file=sys.stderr)

    if not check_staged:
        # Full sweep only -- --check-staged's narrower staged-skill scope would
        # otherwise make the ledger flicker skills in and out on every unrelated
        # commit. The full sweep is the only mode that ever sees a skill nobody is
        # currently committing to, so it's the only mode that owns this ledger.
        cleared = record_ledger(findings)
        if cleared:
            noun = 'entry' if len(cleared) == 1 else 'entries'
            print(f'repo_first_check: cleared {len(cleared)} resolved ledger {noun} '
                  f'-> {LEDGER.name}: {", ".join(cleared)}')
        elif findings:
            print(f'repo_first_check: {len(findings)} skill(s) recorded -> {LEDGER}')

    if not findings and not quiet:
        print('repo_first_check: no cache-ahead skills (repo leads the platform)')
    return 0                              # advisory only -- never blocks


if __name__ == '__main__':
    sys.exit(main())
