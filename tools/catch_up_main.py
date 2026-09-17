#!/usr/bin/env python
"""Safe automatic forward-merge of origin/main into the long-lived local main.

The problem this exists for
---------------------------
The live ora-skills checkout keeps a local `main` that carries unpushed commits, so
it never simply tracks origin/main. PRs merge on GitHub; local main only learns about
them when someone hand-runs `git merge origin/main`. Until then,
`repo_first_check.py --all` sees skills installed from those merged PRs (the
pre-commit mirror sync installs them at feature-branch commit time) as matching a
commit OFF local main's ancestry and reports them DIVERGENT -- a false alarm. That
happened four times in four days (#55/#56, #57, #58/#59), each fixed by hand.

What this does
--------------
Fetches origin/main and merges it into local main, but ONLY when every one of these
holds -- otherwise it changes nothing and says why:

  1. the checkout is on `main`
  2. `git fetch origin main` succeeds and origin/main has commits local main lacks
  3. the merge is conflict-free (`git merge-tree --write-tree` dry run)
  4. no uncommitted or untracked file overlaps a path the merge brings in
  5. ~/.claude/maintenance/preflight-shared-checkout.py clears for those paths
     (single-writer rule for this shared checkout; absent script = fail closed)
  6. HEAD has not moved since step 1

Fast-forwards when local main has no unpushed commits; otherwise writes a merge
commit in the established `merge origin/main into local main (forward-merge #N, #M)`
form. Never pushes, never resets, never aborts someone else's merge.

Usage
-----
  python tools/catch_up_main.py [--repo PATH]     exit 0 MERGED/NOOP, 3 SKIPPED, 1 ERROR
  python tools/catch_up_main.py --hook [--repo PATH]
      PostToolUse mode: reads the hook payload on stdin, acts only on a Bash
      `gh pr merge` aimed at ZeOoba/ora-skills, reports via additionalContext,
      always exits 0.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PREFLIGHT = Path.home() / '.claude' / 'maintenance' / 'preflight-shared-checkout.py'
REPO_SLUG = 'zeooba/ora-skills'
FETCH_TIMEOUT_S = 90
# Unattended (hook) runs must fail fast on expired credentials, never stall on a
# Git Credential Manager prompt.
NONINTERACTIVE_GIT_ENV = {'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'}


def _git(repo: Path, *args: str, timeout: int = 60):
    """-> (returncode, stdout, stderr). Never raises; a git failure is returncode != 0."""
    try:
        r = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                           text=True, timeout=timeout,
                           env={**os.environ, **NONINTERACTIVE_GIT_ENV})
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, '', str(exc)
    return r.returncode, r.stdout.strip(), r.stderr.strip()


def run_preflight(repo: Path, paths: list[str], since: str):
    """-> (clear, detail). Fail closed: an absent or erroring gate never reads as clear."""
    if not PREFLIGHT.is_file():
        return False, f'preflight gate absent ({PREFLIGHT}) -- fail closed'
    try:
        r = subprocess.run([sys.executable, str(PREFLIGHT), '--repo', str(repo),
                            '--paths', *paths, '--since', since],
                           capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f'preflight gate failed to run ({exc})'
    first = next((ln for ln in r.stdout.splitlines() if ln.strip()), '(no output)')
    return r.returncode == 0, first.strip()


def _pr_numbers(repo: Path) -> list[str]:
    _, out, _ = _git(repo, 'log', '--reverse', '--format=%s', 'HEAD..origin/main')
    nums = []
    for subject in out.splitlines():
        m = re.search(r'\(#(\d+)\)\s*$', subject)
        if m and m.group(1) not in nums:
            nums.append(m.group(1))
    return nums


def catch_up(repo: Path = REPO, preflight=run_preflight):
    """-> (status, detail); status is MERGED, NOOP, SKIPPED or ERROR."""
    rc, branch, _ = _git(repo, 'symbolic-ref', '--short', 'HEAD')
    if rc != 0 or branch != 'main':
        return 'SKIPPED', f'not on main (checkout is on {branch or "a detached HEAD"})'
    _, head, _ = _git(repo, 'rev-parse', 'HEAD')

    rc, _, err = _git(repo, 'fetch', '--quiet', 'origin', 'main', timeout=FETCH_TIMEOUT_S)
    if rc != 0:
        return 'SKIPPED', f'fetch origin main failed ({err.splitlines()[-1] if err else rc})'

    rc, behind, _ = _git(repo, 'rev-list', '--count', 'HEAD..origin/main')
    if rc != 0:
        return 'ERROR', 'could not count commits behind origin/main'
    if behind == '0':
        return 'NOOP', 'local main already contains origin/main'

    rc, incoming, _ = _git(repo, 'diff', '--name-only', 'HEAD...origin/main')
    if rc != 0:
        return 'ERROR', 'could not list incoming paths'
    incoming_paths = [p for p in incoming.splitlines() if p]

    if _git(repo, 'merge-tree', '--write-tree', 'HEAD', 'origin/main')[0] != 0:
        return 'SKIPPED', f'merge would conflict ({behind} commit(s) behind) -- merge by hand'

    _, modified, _ = _git(repo, 'diff', '--name-only', 'HEAD')
    _, untracked, _ = _git(repo, 'ls-files', '--others', '--exclude-standard')
    local = set(modified.splitlines()) | set(untracked.splitlines())
    overlap = sorted(local & set(incoming_paths))
    if overlap:
        return 'SKIPPED', f'uncommitted work overlaps incoming files: {", ".join(overlap[:5])}'

    clear, gate = preflight(repo, incoming_paths, head)
    if not clear:
        return 'SKIPPED', f'shared-checkout preflight not clear: {gate}'

    if _git(repo, 'rev-parse', 'HEAD')[1] != head:
        return 'SKIPPED', 'HEAD moved during the check -- another writer is active'

    nums = _pr_numbers(repo)
    suffix = f' #{", #".join(nums)}' if nums else ''
    message = f'merge origin/main into local main (forward-merge{suffix})'
    rc, _, err = _git(repo, 'merge', '--no-edit', '-m', message, 'origin/main', timeout=120)
    if rc != 0:
        return 'ERROR', f'git merge failed after all checks passed: {err or rc}'
    if _git(repo, 'rev-list', '--count', 'HEAD..origin/main')[1] != '0':
        return 'ERROR', 'merge reported success but origin/main is still not contained'
    label = ', '.join(f'#{n}' for n in nums) or f'{behind} commit(s)'
    return 'MERGED', f'forward-merged {label} into local main'


def _normalize_slug(value: str) -> str:
    value = value.strip('\'"').lower()
    value = re.sub(r'\.git$', '', value.rstrip('/'))
    return '/'.join(value.replace(':', '/').split('/')[-2:])


def is_ora_skills_merge(payload) -> bool:
    """True only for a Bash `gh pr merge` whose target repo is ZeOoba/ora-skills --
    named by -R/--repo when present, else inferred from the session cwd's origin."""
    if not isinstance(payload, dict) or payload.get('tool_name') != 'Bash':
        return False
    command = (payload.get('tool_input') or {}).get('command')
    if not isinstance(command, str) or not re.search(r'\bgh\s+pr\s+merge\b', command):
        return False
    flag = re.search(r'(?:^|\s)(?:-R|--repo)(?:\s+|=)(\S+)', command)
    if flag:
        return _normalize_slug(flag.group(1)) == REPO_SLUG
    cwd = payload.get('cwd')
    if not isinstance(cwd, str) or not cwd:
        return False
    rc, url, _ = _git(Path(cwd), 'remote', 'get-url', 'origin')
    return rc == 0 and _normalize_slug(url) == REPO_SLUG


def _hook(repo: Path) -> int:
    try:
        payload = json.loads(sys.stdin.buffer.read().decode('utf-8') or '{}')
        if not is_ora_skills_merge(payload):
            return 0
        status, detail = catch_up(repo)
        print(json.dumps({'hookSpecificOutput': {
            'hookEventName': 'PostToolUse',
            'additionalContext': f'ora-skills local main catch-up: {status} -- {detail}',
        }}))
    except Exception:                     # a hook must never disrupt the session
        pass
    return 0


def main(argv: list[str]) -> int:
    repo = REPO
    if '--repo' in argv:
        i = argv.index('--repo')
        if i + 1 >= len(argv):
            print('catch_up_main: --repo needs a path', file=sys.stderr)
            return 1
        repo = Path(argv[i + 1])
    if '--hook' in argv:
        return _hook(repo)
    status, detail = catch_up(repo)
    print(f'catch_up_main: {status} -- {detail}')
    return {'MERGED': 0, 'NOOP': 0, 'SKIPPED': 3}.get(status, 1)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
