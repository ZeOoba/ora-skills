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
eight days (v4.5 on 2026-07-25, v4.6 on 2026-07-27); masterlease-jurisdiction-rebase
drifted cache-ahead THREE TIMES in one 2026-08-04 session, twice caught only by a
human manually diffing the two stores. The weekly `ora-skill-store-drift-check`
(Mon 12:10) is SKILL.md-only and up to seven days late -- structurally unable to
catch either incident.

What this does
--------------
For each skill it classifies the direction of any cache-vs-repo difference across
EVERY bundled file (SKILL.md and everything under scripts/, references/, fixtures/,
config/ -- not just SKILL.md), reusing the exact same pure classifier the shared-dep
path already uses (`pending_reimport.classify_shared_copy`):

    IN-SYNC       cache == repo working file
    REPO-AHEAD    cache is an older point on HEAD's history   -> normal; reimport fixes it
    CACHE-AHEAD   cache content was never committed anywhere  -> REPO-FIRST VIOLATION
    DIVERGENT     cache matches a commit off HEAD's ancestry  -> manual reconcile
    REPO-MISSING  cache holds a file the repo doesn't ship at -> REPO-FIRST VIOLATION
                  all (created platform-side, e.g. create-skill    (same remedy class
                  adding a new scripts/ file, never committed)      as CACHE-AHEAD)
    UNKNOWN       git unavailable / file untracked -- NEVER auto-actioned (see BAD_VERDICTS)

On a BAD_VERDICTS finding it (a) prints a loud warning and (b) RESCUES the cache
copy to `_staging/repo-first-rescue/<skill>/` so the about-to-be-clobbered content
survives for review. A FULL-SWEEP run (no `--check-staged`) also persists findings
to the durable `_staging/STORE_AHEAD_OF_REPO.md` ledger.

It NEVER blocks a commit -- same posture as Check 4, and for the same reason: a
mirror-state finding is not a content-quality finding, and a false positive here
must not be able to stop Gabriel committing. Fail-open on every error path, EXCEPT
it never lets an unreachable cache root masquerade as a clean sweep (see main()).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from package_skills import SHARED_ROOT_DEPS, is_bundled  # noqa: E402
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

# Verdicts this module treats as an actionable REPO-FIRST violation: rescued, printed
# loudly, and (full sweep only) ledgered. UNKNOWN is deliberately excluded -- it means
# "could not determine direction" (git unavailable / untracked), and auto-treating an
# unverified state as a confirmed violation would fabricate exactly the kind of finding
# this repo's other drift tools go out of their way never to fabricate.
BAD_VERDICTS = ('CACHE-AHEAD', 'DIVERGENT', 'REPO-MISSING')

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
    '# a skill where the AppData runtime cache is CACHE-AHEAD, DIVERGENT, or REPO-MISSING\n'
    '# (see BAD_VERDICTS) vs this repo on at least one shipped file -- i.e. edited\n'
    '# platform-side (Cowork create-skill / save_skill / a direct cache write) and never\n'
    '# committed here. This is the REVERSE of _staging/PENDING_REIMPORT.md (repo-ahead-of-\n'
    '# cache, pending a Save-skill reimport). Companion rescue copies of the about-to-be-\n'
    '# clobbered cache content (if a commit has since touched the skill) live under\n'
    '# _staging/repo-first-rescue/<skill>/.\n'
    '#\n'
    '# THIS LEDGER IS DERIVED, NOT AN EVENT LOG -- unlike PENDING_REIMPORT.md, no line here\n'
    '# is ever hand-cleared. It reflects live state as of the last full-sweep run: commit the\n'
    '# drifted file(s) into the repo (repo-first rule) and the entry clears itself on the\n'
    '# next full sweep once content matches again. The "pending since" timestamp is carried\n'
    '# forward from a skill\'s first-seen run so staleness is visible even as the ledger\n'
    '# content itself refreshes every run. If the cache root was unreachable when a sweep\n'
    '# ran (e.g. a Cowork bash sandbox -- see _win_long()\'s docstring), that run skipped\n'
    '# this ledger entirely rather than writing one -- an unreachable store is a reporting\n'
    '# gap, never grounds to report every previously-drifted skill as resolved.\n'
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
    """Bundled-shaped relative paths that exist on the REPO side. See
    _cache_only_rel_paths() for the complementary cache-side walk -- a file that
    exists ONLY in the cache is invisible to this function by construction."""
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


def _cache_only_rel_paths(cache_dir: Path, exclude: set[str]) -> list[str]:
    """Bundled-shaped files that exist ONLY in the cache -- created platform-side
    (Cowork create-skill / a direct cache write) with no repo counterpart at all.
    _packaged_rel_paths() only ever walks the repo side, so a brand-new file that
    never existed there is invisible to it (2026-08-04 review finding: this is
    exactly the masterlease-jurisdiction-rebase v1.6 shape, where a new
    scripts/ora_docx_redline.py appeared cache-side before it was ever committed).

    KNOWN LIMITATION: this rglob is not long-path-safe (unlike the individual-file
    checks elsewhere in this module, which route through _isfile_long/_win_long) --
    a bundled file past Windows' MAX_PATH inside a deeply-nested AppData cache path
    can be silently missed the same way plain pathlib misreads any long path (see
    _win_long()'s own docstring for the general hazard). Not fixed here; flag it if
    a cache-only finding needs to be trusted at exactly that depth.
    """
    rels = []
    for p in cache_dir.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(cache_dir).as_posix()
        if rel in exclude:
            continue
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

    # DIVERGENT and REPO-MISSING outrank CACHE-AHEAD (2026-08-04 fix, found writing
    # this function's first tests): CACHE-AHEAD has one clean fix ("commit it"), but
    # DIVERGENT means the cache matches a commit OFF this branch's ancestry -- a
    # branch-level mixup needing manual reconciliation, never auto-reimport. This is
    # NOT claimed to be identical to skill_drift_report.combine_verdict's DIVERGENT/
    # UNKNOWN-always-wins rule (that function decides a whole-skill SAFE-REMEDY
    # verdict; this one only decides which file's problem headlines a skill that
    # already has a confirmed violation) -- it only needs the narrower property that
    # a skill with one file of each reports the more cautious verdict. UNKNOWN is
    # deliberately NOT given top rank the way combine_verdict gives it: promoting an
    # unverified state to the skill's headline verdict here would drive an automatic
    # ledger write and a rescue-copy side effect from a state where direction could
    # not even be determined -- see BAD_VERDICTS.
    order = {'IN-SYNC': 0, 'REPO-AHEAD': 1, 'UNKNOWN': 2, 'CACHE-AHEAD': 3, 'DIVERGENT': 4}
    order['REPO-MISSING'] = order['CACHE-AHEAD']
    per_file, worst = [], 'IN-SYNC'
    repo_rels = _packaged_rel_paths(skill, repo_root)
    # Shared repo-ROOT deps (target-markets.json etc.) are injected into a consuming
    # skill's cache copy at packaging time from OUTSIDE the skill's own folder --
    # they have no same-named file under repo_root/skill/, so the cache-only scan
    # below would otherwise misclassify every one of them as REPO-MISSING (found via
    # live smoke test: 5 real skills flagged on target-markets.json alone).
    # pending_reimport.shared_dep_report()/classify_shared_copy() already direction-
    # checks these correctly against their true repo-root source; exclude them here
    # rather than duplicate (and potentially disagree with) that logic.
    shared_deps = set(SHARED_ROOT_DEPS.get(skill, []))

    for rel in repo_rels:
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

    for rel in _cache_only_rel_paths(cache_dir, set(repo_rels) | shared_deps):
        cache_h = _hash_file(cache_dir / rel)
        if cache_h is None:
            verdict = 'UNKNOWN'
        else:
            anc, allh = _file_history_hashes(repo_root, f'{skill}/{rel}')
            # repo_hash=None -> classify_shared_copy returns REPO-MISSING unconditionally
            # (it never even consults ancestor_hashes for that branch); that is the
            # correct label here regardless -- for this tool's purpose (hunting
            # repo-first violations) a file the repo doesn't ship AT ALL is the same
            # class of problem as CACHE-AHEAD, so it carries the same remedy.
            verdict = classify_shared_copy(cache_h, None, anc, allh)
        per_file.append((rel, verdict))
        if order.get(verdict, 2) > order.get(worst, 0):
            worst = verdict

    return worst, per_file


def _now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')


def _classify_all(skills, repo_root: Path = REPO, cache_root: Path = CACHE_ROOT):
    """[(skill, verdict, per_file)] for EVERY skill in `skills`, whatever the
    verdict -- shared by main()'s two modes and by _sweep_findings(), so there is
    exactly one place that calls classify_skill() in a loop with fail-open error
    handling (previously main() and _sweep_findings() each had their own copy)."""
    out = []
    for skill in skills:
        try:
            verdict, per_file = classify_skill(skill, repo_root, cache_root)
        except Exception as exc:          # fail open, always -- one bad skill must
            print(f'repo_first_check: {skill} check errored ({exc}) -- skipped',  # not
                  file=sys.stderr)         # abort the sweep for every other skill
            continue
        out.append((skill, verdict, per_file))
    return out


def _sweep_findings(repo_root: Path = REPO, cache_root: Path = CACHE_ROOT):
    """BAD_VERDICTS findings only, full sweep across every skill dir in the repo --
    not just a commit's staged set. This is the only path that can see a skill
    nobody is currently committing to, which is exactly how masterlease-
    jurisdiction-rebase drifted unnoticed on 2026-08-04: no commit touched it, so
    --check-staged never looked at it at all.

    Does NOT guard cache-root reachability itself -- see main()'s guard, which sits
    in front of this so an unreachable cache root never reaches record_ledger() as
    an empty (and therefore falsely "everything reconciled") finding set.
    """
    all_results = _classify_all(all_skill_dirs(repo_root), repo_root, cache_root)
    return [(s, v, pf) for s, v, pf in all_results if v in BAD_VERDICTS]


def record_ledger(findings, ledger_path: Path = LEDGER) -> list[str]:
    """Persist full-sweep BAD_VERDICTS findings to the durable STORE_AHEAD_OF_REPO
    ledger. A full sweep is cheap and authoritative for "right now", so each call
    REPLACES the ledger contents rather than merging -- but each skill's original
    "pending since" timestamp is carried forward from the prior ledger (read_entries)
    so staleness stays visible instead of resetting to now on every run. Returns the
    skill names that were in the previous ledger but are no longer drifted --
    auto-cleared, via write_entries()'s existing empty-ledger-deletes-the-file
    convention (shared with PENDING_REIMPORT.md).

    CALLER'S RESPONSIBILITY: `findings` must come from a sweep that actually reached
    a reachable cache root. An empty `findings` list is indistinguishable here from
    "everything reconciled" -- passing it after a failed/unreachable sweep would
    silently wipe every real entry (2026-08-04 review finding). main() guards this
    by checking cache reachability before calling _sweep_findings()/record_ledger()
    at all; any other caller must do the same.
    """
    existing = read_entries(ledger_path)
    now = _now()
    entries = {}
    for skill, verdict, per_file in findings:
        bad = [rel for rel, v in per_file if v in BAD_VERDICTS]
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


def rescue(skill: str, rels: list[str], cache_root: Path = CACHE_ROOT,
           rescue_dir: Path = RESCUE_DIR) -> Path | None:
    dest = rescue_dir / skill
    try:
        dest.mkdir(parents=True, exist_ok=True)
        for rel in rels:
            src = Path(cache_root) / skill / rel
            tgt = dest / rel
            tgt.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(_win_long(src), tgt)  # long-path-safe source read
        return dest
    except OSError as exc:                # never let a rescue failure block anything
        print(f'repo_first_check: rescue copy failed for {skill}: {exc}', file=sys.stderr)
        return None


def run(check_staged: bool, repo_root: Path = REPO, cache_root: Path = CACHE_ROOT,
        ledger_path: Path = LEDGER, rescue_dir: Path = RESCUE_DIR) -> int:
    """Core logic, fully parameterized on every store it touches -- the test seam.
    main() is a thin CLI wrapper around this (mirroring skill_drift_report.report()'s
    own repo_root/cache_root parameterization) so the WHOLE control flow, including
    the cache-reachability guard and the ledger write, can be exercised against a
    disposable fixture tree instead of monkeypatching module globals or risking a
    test writing into the real repo's _staging/ directory.
    """
    quiet = check_staged

    if not _isdir_long(cache_root):
        # Never fabricate: an unreachable cache root must not look like "nothing
        # drifted". Fatal specifically for record_ledger(), which reads an empty
        # findings list as "every previously-drifted skill has reconciled" and WIPES
        # the ledger clean -- reproduced on a fixture during code review, and not
        # hypothetical: _win_long()'s own docstring documents CACHE_ROOT as
        # unresolvable from a Cowork bash sandbox specifically. Same posture as
        # skill_drift_report.report()'s cache_root_unreadable guard: bail before
        # calling classify_skill or record_ledger at all, so an existing ledger is
        # left untouched rather than being read as "resolved".
        print(f'repo_first_check: cache root unreadable ({cache_root}) -- no findings '
              f'computed, ledger left untouched (this is a reporting gap, never a '
              f'clean result)', file=sys.stderr)
        return 0

    skills = _staged_skills(repo_root) if check_staged else all_skill_dirs(repo_root)
    all_results = _classify_all(skills, repo_root, cache_root)
    findings = [(s, v, pf) for s, v, pf in all_results if v in BAD_VERDICTS]

    if not quiet:
        for skill, verdict, _ in all_results:
            if verdict not in BAD_VERDICTS:
                print(f'  {skill:<34} {verdict}')

    why = {
        'CACHE-AHEAD': 'runtime cache holds content that was never committed on ANY branch',
        'DIVERGENT': 'runtime cache matches a commit OFF this branch\'s ancestry',
        'REPO-MISSING': 'runtime cache holds a file the repo does not ship at all (no '
                         'counterpart on any branch)',
    }
    fix = {
        'CACHE-AHEAD': 'Edited platform-side and never committed -- commit it to the repo first.',
        'DIVERGENT': 'Installed from another branch -- reconcile the branches, do not auto-reimport.',
        'REPO-MISSING': 'Created platform-side (create-skill / a direct cache write) with no '
                         'repo counterpart -- commit it to the repo, or delete it from the '
                         'cache if it should not exist.',
    }
    for skill, verdict, per_file in findings:
        # Each bad FILE keeps its OWN verdict for the why/fix text (2026-08-04 fix,
        # found writing this function's first tests) -- a skill can have one
        # CACHE-AHEAD file and one DIVERGENT file, and the skill-level aggregate
        # `verdict` (the worse of the two, used only for the banner line) previously
        # mislabeled every file with that single verdict's explanation, telling a
        # DIVERGENT file's reader to "just commit it" when the real fix is "reconcile
        # the branches, do not auto-reimport."
        bad = [(rel, v) for rel, v in per_file if v in BAD_VERDICTS]
        print('', file=sys.stderr)
        print(f'!! REPO-FIRST {verdict}: {skill}', file=sys.stderr)
        for rel, v in bad:
            print(f'     {rel} -- {why[v]}', file=sys.stderr)
        for v in ('CACHE-AHEAD', 'REPO-MISSING', 'DIVERGENT'):
            if v in {bv for _, bv in bad}:
                print(f'   {fix[v]}', file=sys.stderr)
        print('   The mirror sync that runs next WILL overwrite it.', file=sys.stderr)
        dest = rescue(skill, [rel for rel, _ in bad], cache_root, rescue_dir)
        if dest:
            print(f'   Rescued the cache copy -> {dest}', file=sys.stderr)
            print('   Reconcile it into the repo before relying on either store.', file=sys.stderr)

    if not check_staged:
        # Full sweep only -- --check-staged's narrower staged-skill scope would
        # otherwise make the ledger flicker skills in and out on every unrelated
        # commit. The full sweep is the only mode that ever sees a skill nobody is
        # currently committing to, so it's the only mode that owns this ledger. Safe
        # to call unconditionally here: the cache-reachability guard above already
        # returned before this point if cache_root were unreachable.
        cleared = record_ledger(findings, ledger_path)
        if cleared:
            noun = 'entry' if len(cleared) == 1 else 'entries'
            print(f'repo_first_check: cleared {len(cleared)} resolved ledger {noun} '
                  f'-> {ledger_path.name}: {", ".join(cleared)}')
        elif findings:
            print(f'repo_first_check: {len(findings)} skill(s) recorded -> {ledger_path}')

    if not findings and not quiet:
        print('repo_first_check: no cache-ahead skills (repo leads the platform)')
    return 0                              # advisory only -- never blocks


def main() -> int:
    return run('--check-staged' in sys.argv[1:])


if __name__ == '__main__':
    sys.exit(main())
