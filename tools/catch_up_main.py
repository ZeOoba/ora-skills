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

Hook matching (is_ora_skills_merge)
-----------------------------------
A real fetch+merge into the shared checkout must never fire on text that merely
MENTIONS the command, so the match is structural, not a substring search: the command
is split into shell segments on `;` `&&` `||` `|` `&`, newlines, and the `(`..`)` of a
command group or `$( )` substitution (a `(` mid-argument, as in `echo x (gh pr merge)`,
is plain text; an array literal `A=( ... )` is skipped whole; quoted
text, `#` comment lines and heredoc bodies are never a command position; a heredoc
ends only on a line exactly equal to its delimiter, as in bash, and a malformed `<<`
voids the whole command, which bash would reject), and a
segment counts only if its words are `gh pr merge ...` after optional `VAR=val`
assignments, with no -h/--help/--dry-run. The target repo must normalize to exactly
zeooba/ora-skills: every -R/--repo value and PR-URL argument the command names must
match; only when it names none is the payload cwd's origin used. A non-github.com
host, an explicit port, or a malformed spec never matches. A `cd elsewhere &&` prefix
is not followed -- the payload cwd's origin is used. Known misses, all in the safe
direction (no write): anything that hides the command from the scanner -- `bash -c
"gh pr merge ..."`, backticks / `$(...)` inside quotes or an unquoted heredoc body, a
shell fed by a heredoc, a wrapper or keyword in command position (`time`, `sudo`,
`env`, `command`, `exec`, `eval`, `!`, `nohup`, `xargs`, `then`, `do`, `{`, a function
body), a process substitution `<(...)`/`>(...)`, a `case` pattern arm, and an unquoted
PR URL given as another flag's value -- plus `gh pr -R x merge`. Stray or unbalanced
parentheses (`echo a(b); ...`, `echo x) ; ...`, `((...))`) are not modelled: bash
rejects or does not run those, but the scanner still matches a `gh pr merge` after
them. It is a
static scan, so control flow is not modelled either: `false && gh pr merge ...` matches
though bash would not run it (the gated fetch+merge is still what the operator wanted
whenever the merge did run).

Time budget
-----------
The hook is registered with `timeout: 360` in ~/.claude/settings.json. The per-call
git timeouts alone could sum past that (before the budget existed: fetch 90 +
preflight 120 + merge 120 + ten default-60s local reads = ~930s worst case), and a hook killed mid-`git merge` could
leave the shared checkout half-merged. catch_up() therefore runs under a total
deadline (TOTAL_BUDGET_S = 280): each pre-merge git call is clamped to the time
remaining, and the preflight and the merge are only STARTED when their full timeout
still fits -- otherwise the run is SKIPPED with nothing changed (an exhausted budget
is reported as such, never as a conflict). The post-merge verification read gets its
own 30s timeout: catch_up() is bounded by ~310s (merge starts by t=160, +120 merge,
+30 read) and the hook process by ~330s (HOOK_OVERHEAD_S = 20 covers the 10s
cwd-origin read and interpreter startup), under the 360s kill. HOOK_TIMEOUT_S mirrors the settings.json value; the tests fail
if the budget arithmetic stops fitting under it.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PREFLIGHT = Path.home() / '.claude' / 'maintenance' / 'preflight-shared-checkout.py'
REPO_SLUG = 'zeooba/ora-skills'
FETCH_TIMEOUT_S = 90
PREFLIGHT_TIMEOUT_S = 120
MERGE_TIMEOUT_S = 120
POST_MERGE_READ_TIMEOUT_S = 30
TOTAL_BUDGET_S = 280
HOOK_TIMEOUT_S = 360          # mirrors the hook `timeout` in ~/.claude/settings.json
HOOK_OVERHEAD_S = 20          # interpreter startup + the 10s cwd-origin read in the hook
# Unattended (hook) runs must fail fast on expired credentials, never stall on a
# Git Credential Manager prompt.
NONINTERACTIVE_GIT_ENV = {'GIT_TERMINAL_PROMPT': '0', 'GCM_INTERACTIVE': 'never'}


class _BudgetExhausted(Exception):
    """The total time budget ran out before a pre-merge check could run."""


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
                           capture_output=True, text=True, timeout=PREFLIGHT_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return False, f'preflight gate failed to run ({exc})'
    first = next((ln for ln in r.stdout.splitlines() if ln.strip()), '(no output)')
    return r.returncode == 0, first.strip()


def _pr_numbers(log: str) -> list[str]:
    nums = []
    for subject in log.splitlines():
        m = re.search(r'\(#(\d+)\)\s*$', subject)
        if m and m.group(1) not in nums:
            nums.append(m.group(1))
    return nums


def catch_up(repo: Path = REPO, preflight=run_preflight, budget_s: float = TOTAL_BUDGET_S,
             clock=time.monotonic):
    """-> (status, detail); status is MERGED, NOOP, SKIPPED or ERROR. Bounded by
    `budget_s` (see "Time budget" in the module docstring)."""
    end = clock() + budget_s

    def remaining() -> float:
        return end - clock()

    def git(*args: str, timeout: int = 60):
        left = remaining()
        if left < 1:
            raise _BudgetExhausted
        return _git(repo, *args, timeout=min(timeout, int(left)))

    try:
        return _catch_up(repo, preflight, git, remaining)
    except _BudgetExhausted:
        return 'SKIPPED', 'time budget exhausted before the checks finished -- nothing changed'


def _catch_up(repo: Path, preflight, git, remaining):
    rc, branch, _ = git('symbolic-ref', '--short', 'HEAD')
    if rc != 0 or branch != 'main':
        return 'SKIPPED', f'not on main (checkout is on {branch or "a detached HEAD"})'
    rc, head, _ = git('rev-parse', 'HEAD')
    if rc != 0:
        return 'SKIPPED', 'could not read HEAD'

    rc, _, err = git('fetch', '--quiet', 'origin', 'main', timeout=FETCH_TIMEOUT_S)
    if rc != 0:
        return 'SKIPPED', f'fetch origin main failed ({err.splitlines()[-1] if err else rc})'

    rc, behind, _ = git('rev-list', '--count', 'HEAD..origin/main')
    if rc != 0:
        return 'ERROR', 'could not count commits behind origin/main'
    if behind == '0':
        return 'NOOP', 'local main already contains origin/main'

    rc, incoming, _ = git('diff', '--name-only', 'HEAD...origin/main')
    if rc != 0:
        return 'ERROR', 'could not list incoming paths'
    incoming_paths = [p for p in incoming.splitlines() if p]

    if git('merge-tree', '--write-tree', 'HEAD', 'origin/main')[0] != 0:
        return 'SKIPPED', f'merge would conflict ({behind} commit(s) behind) -- merge by hand'

    rc_mod, modified, _ = git('diff', '--name-only', 'HEAD')
    rc_untracked, untracked, _ = git('ls-files', '--others', '--exclude-standard')
    if rc_mod != 0 or rc_untracked != 0:
        return 'SKIPPED', 'could not list uncommitted files -- cannot rule out an overlap'
    local = set(modified.splitlines()) | set(untracked.splitlines())
    overlap = sorted(local & set(incoming_paths))
    if overlap:
        return 'SKIPPED', f'uncommitted work overlaps incoming files: {", ".join(overlap[:5])}'

    if remaining() < PREFLIGHT_TIMEOUT_S:
        return 'SKIPPED', 'time budget too low to run the shared-checkout preflight'
    clear, gate = preflight(repo, incoming_paths, head)
    if not clear:
        return 'SKIPPED', f'shared-checkout preflight not clear: {gate}'

    rc, now_head, _ = git('rev-parse', 'HEAD')
    if rc != 0:
        return 'SKIPPED', 'could not re-read HEAD before merging'
    if now_head != head:
        return 'SKIPPED', 'HEAD moved during the check -- another writer is active'

    _, log, _ = git('log', '--reverse', '--format=%s', 'HEAD..origin/main')
    nums = _pr_numbers(log)
    suffix = f' #{", #".join(nums)}' if nums else ''
    message = f'merge origin/main into local main (forward-merge{suffix})'
    # Never start a merge that the deadline could kill half-way through.
    if remaining() < MERGE_TIMEOUT_S:
        return 'SKIPPED', 'time budget too low to start the merge'
    rc, _, err = _git(repo, 'merge', '--no-edit', '-m', message, 'origin/main',
                      timeout=MERGE_TIMEOUT_S)
    if rc != 0:
        return 'ERROR', f'git merge failed after all checks passed: {err or rc}'
    label = ', '.join(f'#{n}' for n in nums) or f'{behind} commit(s)'
    rc, left_behind, _ = _git(repo, 'rev-list', '--count', 'HEAD..origin/main',
                              timeout=POST_MERGE_READ_TIMEOUT_S)
    if rc != 0:                       # the merge itself succeeded; only the re-check failed
        return 'MERGED', f'forward-merged {label} into local main (post-merge check unread -- verify)'
    if left_behind != '0':
        return 'ERROR', 'merge reported success but origin/main is still not contained'
    return 'MERGED', f'forward-merged {label} into local main'


_REPO_SPEC = re.compile(
    r'(?:(?:https?|ssh|git)://(?:[^@/\s]+@)?|[^@/\s]+@)?'   # scheme:// and/or user@
    r'(?:([^/:\s]+)[/:])?'                                   # optional host
    r'([^/:\s]+)/([^/:\s]+?)(?:\.git)?/?')                   # owner/repo
_PR_URL = re.compile(r'https?://[^/\s]+/[^/\s]+/[^/\s]+/pull/\d+\S*')
_ASSIGNMENT = re.compile(r'[A-Za-z_][A-Za-z0-9_]*=')
_NON_MERGING_FLAGS = {'-h', '--help', '--dry-run'}
_ARRAY_OPENER = re.compile(r'[A-Za-z_][A-Za-z0-9_]*\+?=')


def _array_literal_end(command: str, start: int) -> int:
    """Index of the `)` closing the `(` at `start` (quote- and nesting-aware), or the
    last index when unterminated -- the whole `NAME=( ... )` literal is data."""
    depth, quote, j, n = 0, None, start, len(command)
    while j < n:
        ch = command[j]
        if quote:
            if ch == quote:
                quote = None
            elif ch == '\\' and quote == '"':
                j += 1
        elif ch in '\'"':
            quote = ch
        elif ch == '\\':
            j += 1
        elif ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                return j
        j += 1
    return n - 1


def _normalize_slug(value: str):
    """'owner/repo' (lowercased) for OWNER/REPO, [github.com/]OWNER/REPO, or an
    https/ssh/scp-style GitHub remote URL; None for any other host or shape."""
    m = _REPO_SPEC.fullmatch(value.strip('\'"').lower())
    if not m or m.group(1) not in (None, 'github.com'):
        return None
    return f'{m.group(2)}/{m.group(3)}'


def _shell_segments(command: str) -> list[list[str]]:
    """Split a shell command line into simple commands, each a list of unquoted words.
    Separators (`;` `&&` `||` `|` `&` `(` `)` newline) start a new command; quoted
    text stays inside one word, `#` at a word start comments out the rest of the
    line, and heredoc bodies are skipped -- so text that merely mentions a command
    never lands in command position."""
    segments: list[list[str]] = []
    words: list[str] = []
    word: list[str] = []
    in_word = False
    quote = None
    heredocs: list[tuple[str, bool]] = []          # (delimiter, `<<-` strips leading tabs)
    depth = 0                                      # open `(` groups / `$(` substitutions
    i, n = 0, len(command)

    def end_word():
        nonlocal in_word
        if in_word:
            words.append(''.join(word))
            word.clear()
            in_word = False

    def end_segment():
        end_word()
        if words:
            segments.append(words[:])
            words.clear()

    while i < n:
        c = command[i]
        if quote:
            if c == quote:
                quote = None
            elif quote == '"' and c == '\\' and i + 1 < n and command[i + 1] in '"\\$`':
                i += 1
                word.append(command[i])
            else:
                word.append(c)
        elif c in '\'"':
            quote, in_word = c, True
        elif c == '\\' and i + 1 < n:
            if command[i + 1] != '\n':             # backslash-newline = continuation
                word.append(command[i + 1])
                in_word = True
            i += 1
        elif c == '#' and not in_word:
            while i + 1 < n and command[i + 1] != '\n':
                i += 1
        elif c == '\n':
            end_segment()
            for delim, dash in heredocs:           # skip each pending heredoc body
                i += 1
                while i < n:
                    eol = command.find('\n', i)
                    eol = n if eol < 0 else eol
                    line = command[i:eol].rstrip('\r')
                    i = eol
                    if (line.lstrip('\t') if dash else line) == delim:
                        break
                    i += 1
            heredocs.clear()
        elif c == '(' and word and _ARRAY_OPENER.fullmatch(''.join(word)):
            i = _array_literal_end(command, i)     # `A=( ... )` is data; a command it
                                                   # prefixes still runs and still matches
        elif c == '(' and ((not in_word and not words) or (word and word[-1] == '$')):
            depth += 1                             # a group or `$(` substitution starts a command
            end_segment()
        elif c == ')' and depth:
            depth -= 1
            end_segment()
        elif c in ';&|':
            end_segment()
        elif c.isspace():
            end_word()
        elif command.startswith('<<', i) and not command.startswith('<<<', i):
            end_word()
            i += 2
            dash = i < n and command[i] == '-'
            if dash:
                i += 1
            while i < n and command[i] in ' \t':
                i += 1
            delim = []
            while i < n and not command[i].isspace() and command[i] not in ';&|()<>':
                if command[i] not in '\'"\\':
                    delim.append(command[i])
                i += 1
            if not delim:
                return []                          # malformed: bash rejects the whole command
            heredocs.append((''.join(delim), dash))
            continue
        else:
            word.append(c)
            in_word = True
        i += 1
    end_segment()
    return segments


def _merge_repo_specs(words: list[str]):
    """For a segment that is a real `gh pr merge` (not help/dry-run) -> the repo specs
    it names (-R/--repo values, PR-URL arguments; [] when none). None otherwise."""
    words = list(words)
    while words and _ASSIGNMENT.match(words[0]):
        words.pop(0)
    if (len(words) < 3 or re.split(r'[\\/]', words[0])[-1].lower() not in ('gh', 'gh.exe')
            or words[1] != 'pr' or words[2] != 'merge'):
        return None
    args = words[3:]
    if _NON_MERGING_FLAGS & set(args):
        return None
    specs: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ('-R', '--repo'):
            if i + 1 >= len(args):
                return None                        # malformed: gh would refuse it too
            specs.append(args[i + 1])
            i += 1
        elif arg.startswith('--repo='):
            specs.append(arg[len('--repo='):])
        elif arg.startswith('-R') and not arg.startswith('--'):
            specs.append(arg[2:].lstrip('='))      # -RSLUG and -R=SLUG (pflag takes both)
        elif _PR_URL.fullmatch(arg):
            specs.append(re.sub(r'/pull/.*$', '', arg))
        i += 1
    return specs


def is_ora_skills_merge(payload) -> bool:
    """True only for a Bash command whose command position holds `gh pr merge` aimed
    at ZeOoba/ora-skills -- named by -R/--repo or a PR URL when present (every named
    repo must match), else inferred from the session cwd's origin. Text that merely
    mentions the command (echo, commit messages, comments, heredocs, --help) is not
    a merge; see "Hook matching" in the module docstring."""
    if not isinstance(payload, dict) or payload.get('tool_name') != 'Bash':
        return False
    command = (payload.get('tool_input') or {}).get('command')
    if not isinstance(command, str) or 'merge' not in command:
        return False
    cwd_matches = None                             # resolved lazily, once
    for words in _shell_segments(command):
        specs = _merge_repo_specs(words)
        if specs is None:
            continue
        if specs:
            if all(_normalize_slug(spec) == REPO_SLUG for spec in specs):
                return True
            continue
        if cwd_matches is None:
            cwd = payload.get('cwd')
            rc, url, _ = (_git(Path(cwd), 'remote', 'get-url', 'origin', timeout=10)
                          if isinstance(cwd, str) and cwd else (1, '', ''))
            cwd_matches = rc == 0 and _normalize_slug(url) == REPO_SLUG
        if cwd_matches:
            return True
    return False


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
