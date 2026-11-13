#!/usr/bin/env python3
"""Warn after a merge/rebase that leaves this clone's hook pins stale.

tools/install_hooks.py writes a PINNED copy of tools/prepush_confidential_scan.py and one
shim per hook into <common-dir>/ora-hooks/. Nothing re-pins them when a merge changes the
scanner or the hooks, so the drift surfaced only at the next push (2026-11-13: after #257
changed the scanner, the pre-push note "the pinned scanner ... differs" appeared hours
later). Run from tools/hooks/post-merge and post-rewrite:

    python tools/hook_pin_check.py --range ORIG_HEAD HEAD

When the range touches a pinned input -- or the range cannot be read (no ORIG_HEAD), in
which case it checks anyway -- it runs `install_hooks.py --check` and, on drift, prints a
WARNING with the exact re-pin command. It never re-pins by itself (re-pinning rewrites the
fallback scanner every push relies on, so a human runs it) and it ALWAYS exits 0: a hook
helper must never fail a merge.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
# Inputs install_hooks.py copies or derives its shims from.
PINNED_INPUTS = ('tools/prepush_confidential_scan.py', 'tools/hooks', 'tools/install_hooks.py')


def changed_pinned_inputs(repo: Path, a: str, b: str):
    """Pinned inputs changed between `a` and `b`, or None when the range cannot be read."""
    p = subprocess.run(['git', '-C', str(repo), 'diff', '--name-only', a, b, '--', *PINNED_INPUTS],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    if p.returncode != 0:
        return None
    return [ln for ln in p.stdout.splitlines() if ln.strip()]


def run_install_check(repo: Path) -> tuple[int, str]:
    p = subprocess.run([sys.executable, str(repo / 'tools' / 'install_hooks.py'),
                        '--repo', str(repo), '--check'],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    return p.returncode, (p.stdout + p.stderr).strip()


def check(repo: Path, a: str, b: str, changed=changed_pinned_inputs, run=run_install_check) -> str:
    """'skip' (no pinned input changed), 'ok' or 'stale'. Prints the warning for 'stale'."""
    files = changed(repo, a, b)
    if files == []:
        return 'skip'
    rc, out = run(repo)
    if rc == 0:
        return 'ok'
    what = ', '.join(files) if files else 'unknown range (no ORIG_HEAD)'
    print('WARNING: ora-skills hook pins are stale after this update '
          f'({what}). Pushes run the OLD pinned scanner until you re-pin:', file=sys.stderr)
    print(f'  python tools/install_hooks.py --repo "{repo}"', file=sys.stderr)
    if out:
        print('  ' + out.replace('\n', '\n  '), file=sys.stderr)
    return 'stale'


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    a, b = 'ORIG_HEAD', 'HEAD'
    if argv[:1] == ['--range'] and len(argv) >= 3:
        a, b = argv[1], argv[2]
    try:
        check(REPO, a, b)
    except Exception as exc:  # never fail the merge
        print(f'hook_pin_check: skipped ({type(exc).__name__}: {exc})', file=sys.stderr)
    return 0


if __name__ == '__main__':
    sys.exit(main())
