"""Capture runtime-cache-only skill content into git within minutes of a Save-skill click.

The problem this exists for
---------------------------
A skill saved from Cowork (a `propose_skills` card, create-skill, a Save-skill click on a
package built from an unmerged branch) lands in the AppData runtime cache and NOWHERE
ELSE. Nothing writes it to the repo. `repo_first_check.py` detects that state and rescues
a copy to the untracked `_staging/repo-first-rescue/`, but only when someone runs a sweep
or commits to that skill -- and pre-commit Check 4 (`sync_appdata_mirror.py`) then copies
the older repo file OVER the newer cache copy. On 2026-10-15 a full sweep found 13 skills
in that state, some sitting since 2026-09-17, and estoppel-request-generation's
uncommitted v1.2 was one package install away from being destroyed.

The fix is to stop relying on a sweep: get the cache-only content into git at save time.
There is no hook on the platform's Save-skill click, but a click is observable -- the
platform tears down and recreates the skill's cache directory (see package-and-stage-skill,
"CreationTime discriminator"). This tool runs every few minutes from Windows Task
Scheduler, notices a changed cache directory, and commits the cache-only files VERBATIM to
a capture branch and PR. It does not reconcile: preservation now, review later.

What a run does
---------------
1. Fast path. Fingerprint every installed skill directory (dir CreationTime, file count,
   newest mtime, total bytes) and compare with the last run's fingerprints. Unchanged
   skills are skipped, so an idle run costs a directory walk and nothing else.
2. Pre-filter against this checkout (`repo_first_check.classify_skill`). Only a skill with
   a file classed CACHE-AHEAD or REPO-MISSING -- content never committed on any branch --
   goes further. MAIN-BEHIND-ORIGIN, REPO-AHEAD and DIVERGENT content already exists in
   git and is never captured; YAML quoting / EOL / NUL-padding differences are already
   normalized away by the shared hasher, so platform reserialization is not a capture.
3. Confirm against origin/main in a throwaway detached worktree, so a lagging local main
   cannot make already-merged content look new.
4. De-duplicate: a (skill, {file: hash}) set already captured in an earlier run is not
   captured again.
5. Copy only the flagged files from the cache into the worktree and commit one commit per
   skill. Hooks are disabled for these commits (core.hooksPath -> an empty dir): the
   frontmatter gate must never block preservation, and post-commit would otherwise
   record a false PENDING-REIMPORT for content the cache already holds.
6. Run ~/.claude's fail-closed confidential-terms pre-push scanner over the new commits
   (captured content never passed a human or a Code-surface guard). Only on a pass:
   push the branch and open a PR marked DO-NOT-MERGE-AS-IS. The worktree is removed
   either way. A blocked or failed push leaves the commits on the local branch, exits 1,
   and is retried on the next run.

Usage
-----
    python tools/capture_runtime_cache.py              # fast path: changed skills only
    python tools/capture_runtime_cache.py --full       # every installed skill
    python tools/capture_runtime_cache.py --dry-run    # report only: no commit/push/PR/state
    python tools/capture_runtime_cache.py --full --dry-run

Exit 0 = nothing to do, or captured and pushed. Exit 1 = an error a human must see (push or
PR creation failed, cache root unreachable, worktree failure) -- Task Scheduler's
LastTaskResult then reads non-zero, which automation-health-monitor surfaces.

State and log (untracked) live in the PRIMARY checkout's `_staging/runtime-capture/`:
`state.json` (fingerprints, captured hashes, branches awaiting push) and `capture.log`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pending_reimport import CACHE_ROOT, REPO, _primary_checkout, _read_bytes_long  # noqa: E402
from repo_first_check import NONINTERACTIVE_GIT_ENV, _hash_file, classify_skill  # noqa: E402

CAPTURE_VERDICTS = ('CACHE-AHEAD', 'REPO-MISSING')
STATE_DIR = _primary_checkout(REPO) / '_staging' / 'runtime-capture'
STATE_FILE = STATE_DIR / 'state.json'
LOG_FILE = STATE_DIR / 'capture.log'
LOCK_FILE = STATE_DIR / '.lock'
LOCK_STALE_SECONDS = 30 * 60
WORKTREE_PARENT = REPO.parent / 'ora-skills-wt'
BRANCH_PREFIX = 'capture/runtime-cache-'
CREATE_NO_WINDOW = 0x08000000 if os.name == 'nt' else 0
GIT_ENV = {**os.environ, **NONINTERACTIVE_GIT_ENV}

# Keep each new commit's attribution consistent with the rest of the repo.
TRAILER = 'Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>'


# ---------------------------------------------------------------- pure helpers (tested)

def fingerprint(skill_dir: Path) -> str:
    """Cheap change signature for one installed skill directory. A Save-skill install
    recreates the directory (CreationTime moves); a mirror sync rewrites files in place
    (mtimes/size move). Either changes this string; an idle cache never does."""
    count, newest, size = 0, 0.0, 0
    for p in skill_dir.rglob('*'):
        if p.is_file():
            st = p.stat()
            count += 1
            size += st.st_size
            newest = max(newest, st.st_mtime)
    return f'{skill_dir.stat().st_ctime:.0f}|{count}|{newest:.0f}|{size}'


def changed_skills(current: dict, previous: dict) -> list:
    """Skills whose fingerprint is new or differs from the previous run."""
    return sorted(s for s, fp in current.items() if previous.get(s) != fp)


JUNK_PARTS = ('.pytest_cache', '__pycache__', '.mypy_cache', '.ruff_cache')


def is_junk(rel: str) -> bool:
    """Tool/runtime debris that a cache directory can accumulate but that is never
    skill content (a pytest cache inside the eval harness was the live example)."""
    parts = rel.replace('\\', '/').split('/')
    return any(p in JUNK_PARTS for p in parts) or rel.endswith(('.pyc', '.pyo'))


def files_to_capture(per_file) -> list:
    """Relative paths whose verdict means 'never committed on any branch'."""
    return sorted(rel for rel, verdict in per_file
                  if verdict in CAPTURE_VERDICTS and not is_junk(rel))


def parse_ignore(text: str) -> set:
    """Skill names never to capture: platform/Anthropic-provided skills that live in the
    same runtime cache but are not ORA content. One name per line; '#' comments."""
    out = set()
    for line in text.splitlines():
        name = line.split('#', 1)[0].strip()
        if name:
            out.add(name)
    return out


def already_captured(state: dict, skill: str, key: dict) -> bool:
    """True when this exact {relpath: normalized hash} set was captured before."""
    return any(entry.get('files') == key for entry in state.get('captured', {}).get(skill, []))


def record_capture(state: dict, skill: str, key: dict, branch: str, when: str) -> None:
    state.setdefault('captured', {}).setdefault(skill, []).append(
        {'files': key, 'branch': branch, 'at': when})


def commit_message(skill: str, rels: list, verdicts: dict, cache_ctime: str) -> str:
    lines = [f'capture({skill}): runtime-cache-only content, verbatim', '']
    lines.append('Content saved to the Cowork runtime cache that was never committed on any')
    lines.append('branch, captured unmodified so it cannot be lost to a mirror sync. NOT')
    lines.append('reconciled: review against main before merging (package-and-stage-skill).')
    lines.append('')
    lines.append(f'Cache directory created: {cache_ctime}')
    for rel in rels:
        lines.append(f'- {rel}: {verdicts.get(rel, "?")}')
    lines += ['', TRAILER]
    return '\n'.join(lines) + '\n'


def pr_body(rows: list, stamp: str) -> str:
    """rows: [(skill, [rel...], cache_ctime)]"""
    out = [
        '**DO NOT MERGE AS-IS.** Automated capture by `tools/capture_runtime_cache.py` '
        f'(run {stamp}).',
        '',
        'Each commit copies files that existed only in the Cowork runtime cache '
        '(CACHE-AHEAD / REPO-MISSING: never committed on any branch) into the repo verbatim, '
        'so they survive the next mirror sync. The confidential-terms pre-push scan passed '
        'before push. Commit hooks were disabled for these commits, so frontmatter and '
        'description checks have NOT run.',
        '',
        '| Skill | Captured file(s) | Cache dir created |',
        '|---|---|---|',
    ]
    for skill, rels, ctime in rows:
        out.append(f'| {skill} | {", ".join(rels)} | {ctime} |')
    out += [
        '',
        '**To land this content:** for each skill, compare the captured file with `main`. If '
        'the capture strictly adds to main, it can be merged after `tools/frontmatter_sweep.py` '
        'and the local gates pass. If main has moved since the cache copy was made, reconcile on '
        'a fresh branch (cache as base, re-apply main\'s hunks), bump the version, and close '
        'this PR. Never merge a capture that removes content main has.',
        '',
        'Generated by `tools/capture_runtime_cache.py` (ORA Skill Cache Capture task).',
    ]
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------- side-effecting layer

def _now(fmt='%Y-%m-%dT%H:%M:%SZ') -> str:
    return datetime.now(timezone.utc).strftime(fmt)


def _log(msg: str) -> None:
    line = f'{_now()} {msg}'
    print(line)
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        with open(LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + '\n')
    except OSError:
        pass


def _git(*args, cwd: Path = None, check: bool = True, timeout: int = 180):
    # cwd resolved at call time (not a def-time default) so tests can repoint REPO.
    cwd = REPO if cwd is None else cwd
    r = subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, text=True,
                       env=GIT_ENV, timeout=timeout, creationflags=CREATE_NO_WINDOW)
    if check and r.returncode != 0:
        raise RuntimeError(f'git {" ".join(args)} failed: {r.stderr.strip()[:400]}')
    return r


def _gh(*args, cwd: Path = None):
    cwd = REPO if cwd is None else cwd
    return subprocess.run(['gh', *args], cwd=str(cwd), capture_output=True, text=True,
                          env=GIT_ENV, timeout=120, creationflags=CREATE_NO_WINDOW)


def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {'fingerprints': {}, 'captured': {}, 'pending_push': []}


def save_state(state: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=1, sort_keys=True), encoding='utf-8')
    os.replace(tmp, STATE_FILE)


def acquire_lock() -> bool:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        if LOCK_FILE.exists() and time.time() - LOCK_FILE.stat().st_mtime < LOCK_STALE_SECONDS:
            return False
        LOCK_FILE.write_text(str(os.getpid()), encoding='utf-8')
        return True
    except OSError:
        return False


def release_lock() -> None:
    try:
        LOCK_FILE.unlink()
    except OSError:
        pass


IGNORE_FILE = Path(__file__).resolve().parent / 'runtime_capture_ignore.txt'


def load_ignore() -> set:
    try:
        return parse_ignore(IGNORE_FILE.read_text(encoding='utf-8'))
    except OSError:
        return set()


def installed_skills(cache_root: Path, ignore: set = frozenset()) -> list:
    return sorted(d.name for d in cache_root.iterdir()
                  if (d / 'SKILL.md').is_file() and d.name not in ignore)


def git_ignored(wt: Path, paths: list) -> set:
    """Subset of repo-relative paths the repo's own .gitignore excludes."""
    if not paths:
        return set()
    r = _git('check-ignore', '--', *paths, cwd=wt, check=False)
    return {line.strip() for line in r.stdout.splitlines() if line.strip()}


def _ctime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_ctime, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


SCANNER = Path.home() / '.claude' / 'hooks' / 'git-prepush-confidential-scan.py'


def prepush_stdin(branch: str, sha: str) -> str:
    """git pre-push stdin for a brand-new remote ref, so the scanner bounds its scan to
    origin/main..sha -- exactly the captured commits."""
    return f'refs/heads/{branch} {sha} refs/heads/{branch} {"0" * 40}\n'


def confidential_gate(branch: str, scanner: Path = None) -> tuple:
    """Run ~/.claude's fail-closed confidential-terms pre-push scanner over the capture
    commits before anything leaves the machine. Captured content was written platform-
    side and never passed a human or a Code-surface guard, so this push must clear the
    same gate ~/.claude's own pushes do. Missing scanner = blocked (fail-closed). The
    scanner never echoes a term, so its output is safe to log."""
    scanner = SCANNER if scanner is None else scanner
    if not Path(scanner).is_file():
        return False, f'confidential scanner not found at {scanner} (fail-closed)'
    sha = _git('rev-parse', branch).stdout.strip()
    r = subprocess.run([sys.executable, str(scanner), 'origin', 'capture'], cwd=str(REPO),
                       input=prepush_stdin(branch, sha), capture_output=True, text=True,
                       env=GIT_ENV, timeout=300, creationflags=CREATE_NO_WINDOW)
    detail = ' '.join((r.stdout + ' ' + r.stderr).split())[:400]
    return r.returncode == 0, detail


def push_and_pr(entry: dict) -> str:
    """Push entry['branch'] and make sure a PR exists for it. Idempotent, so a branch
    left in state['pending_push'] by a failed run is simply retried. Returns the PR URL.
    Refuses to push unless the confidential-terms scan passes."""
    branch = entry['branch']
    ok, detail = confidential_gate(branch)
    if not ok:
        raise RuntimeError(f'confidential scan BLOCKED push of {branch} -- commits kept '
                           f'locally; review before pushing. Scanner: {detail}')
    _git('push', '-u', 'origin', branch, timeout=300)
    existing = _gh('pr', 'list', '--head', branch, '--state', 'all', '--json', 'url', '--jq', '.[0].url')
    if existing.returncode == 0 and existing.stdout.strip():
        return existing.stdout.strip()
    rows = [tuple(r) for r in entry['rows']]
    with tempfile.NamedTemporaryFile('w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(pr_body(rows, entry['stamp']))
        body = f.name
    try:
        title = (f'capture: runtime-cache-only content for {len(rows)} skill(s) '
                 f'({entry["stamp"]}) -- DO NOT MERGE AS-IS')
        r = _gh('pr', 'create', '--base', 'main', '--head', branch, '--title', title,
                '--body-file', body)
    finally:
        os.unlink(body)
    if r.returncode != 0:
        raise RuntimeError(f'gh pr create failed: {(r.stderr or r.stdout).strip()[:400]}')
    return r.stdout.strip().splitlines()[-1]


def run(full: bool, dry_run: bool, cache_root: Path = CACHE_ROOT) -> int:
    if not cache_root.is_dir():
        _log(f'ERROR cache root unreachable: {cache_root}')
        return 1
    state = load_state()
    for k, default in (('fingerprints', {}), ('captured', {}), ('pending_push', [])):
        state.setdefault(k, default)
    rc = 0

    if not dry_run:
        for entry in list(state['pending_push']):
            try:
                url = push_and_pr(entry)
                state['pending_push'].remove(entry)
                _log(f'retry ok: {entry["branch"]} -> {url}')
            except Exception as e:  # noqa: BLE001 -- any failure is reported, retried next run
                _log(f'ERROR retry {entry["branch"]}: {e}')
                rc = 1
        save_state(state)

    skills = installed_skills(cache_root, load_ignore())
    fps = {s: fingerprint(cache_root / s) for s in skills}
    candidates = skills if full else changed_skills(fps, state['fingerprints'])

    # Pre-filter against this checkout: cheap, and sound -- content that is in local
    # history is in git, so only a local CACHE-AHEAD/REPO-MISSING can be a capture.
    pre = [s for s in candidates
           if files_to_capture(classify_skill(s, REPO, cache_root)[1])]
    if not pre:
        if not dry_run:
            state['fingerprints'].update(fps)
            save_state(state)
        _log(f'scan: {len(skills)} installed, {len(candidates)} checked, nothing to capture'
             + (' (dry-run)' if dry_run else ''))
        return rc

    _git('fetch', '--quiet', 'origin', 'main', check=False)
    stamp = _now('%Y%m%dT%H%M%SZ')
    branch = BRANCH_PREFIX + stamp
    wt = WORKTREE_PARENT / f'_runtime-capture-{stamp}'
    WORKTREE_PARENT.mkdir(parents=True, exist_ok=True)
    _git('worktree', 'add', '--detach', str(wt), 'origin/main', timeout=300)
    no_hooks = Path(tempfile.mkdtemp(prefix='ora-nohooks-'))
    rows, made_branch = [], False
    try:
        for s in pre:
            per = classify_skill(s, wt, cache_root)[1]
            rels = files_to_capture(per)
            ignored = git_ignored(wt, [f'{s}/{rel}' for rel in rels])
            rels = [rel for rel in rels if f'{s}/{rel}' not in ignored]
            if not rels:
                _log(f'{s}: nothing never-committed left after origin/main + .gitignore '
                     '-- not captured')
                continue
            key = {rel: _hash_file(cache_root / s / rel) for rel in rels}
            if already_captured(state, s, key):
                _log(f'{s}: identical content already captured -- skipped')
                continue
            ctime = _ctime(cache_root / s)
            if dry_run:
                rows.append([s, rels, ctime])
                continue
            if not made_branch:
                _git('switch', '-c', branch, cwd=wt)
                made_branch = True
            for rel in rels:
                dest = wt / s / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(_read_bytes_long(cache_root / s / rel))
            paths = [f'{s}/{rel}' for rel in rels]
            _git('add', '--', *paths, cwd=wt)
            with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False,
                                             encoding='utf-8') as f:
                f.write(commit_message(s, rels, dict(per), ctime))
                msg = f.name
            try:
                _git('-c', f'core.hooksPath={no_hooks.as_posix()}', 'commit', '-F', msg,
                     '--', *paths, cwd=wt)
            finally:
                os.unlink(msg)
            record_capture(state, s, key, branch, _now())
            rows.append([s, rels, ctime])
            _log(f'{s}: captured {", ".join(rels)}')
    except Exception:
        # Commits already made live on the local branch; queue them for push so a
        # failure part-way through never strands captured content untracked.
        if made_branch and rows and not dry_run:
            state['pending_push'].append({'branch': branch, 'rows': rows, 'stamp': stamp})
            save_state(state)
        raise
    finally:
        _git('worktree', 'remove', '--force', str(wt), check=False)
        shutil.rmtree(no_hooks, ignore_errors=True)

    if dry_run:
        for s, rels, ctime in rows:
            _log(f'(dry-run) would capture {s}: {", ".join(rels)} [cache dir {ctime}]')
        _log(f'(dry-run) {len(rows)} skill(s) would be captured; nothing written')
        return rc

    state['fingerprints'].update(fps)
    if rows:
        entry = {'branch': branch, 'rows': rows, 'stamp': stamp}
        state['pending_push'].append(entry)
        save_state(state)          # persisted before the push, so a crash is retried
        try:
            url = push_and_pr(entry)
            state['pending_push'].remove(entry)
            _log(f'captured {len(rows)} skill(s) -> {url}')
        except Exception as e:  # noqa: BLE001
            _log(f'ERROR push/PR for {branch} (commits kept locally, retried next run): {e}')
            rc = 1
    save_state(state)
    return rc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--full', action='store_true', help='check every installed skill')
    ap.add_argument('--dry-run', action='store_true', help='report only; write nothing')
    a = ap.parse_args(argv)
    if not acquire_lock():
        _log('another capture run holds the lock -- exiting')
        return 0
    try:
        return run(a.full, a.dry_run)
    except Exception as e:  # noqa: BLE001 -- unattended: log, surface via exit code
        _log(f'ERROR {type(e).__name__}: {e}')
        return 1
    finally:
        release_lock()


if __name__ == '__main__':
    sys.exit(main())
