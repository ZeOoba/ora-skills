#!/usr/bin/env python3
"""Read what the PLATFORM actually holds: the installed SKILL.md in the runtime cache.

Why this exists (2026-08-24): the platform's skill listing is NOT a per-skill
diagnostic. It truncates -- a long alphabetical tail renders name-only with no
description at all, and which skills fall in that tail changes between renders.
On 2026-08-24 loi-generation and listing-agreement-qc showed full descriptions
early in a session and name-only later, unchanged. Never read name-only as a
defect, and never confirm an install from the listing alone.

repo_first_check.py answers "does the cache match the repo". This answers the
different question "what does the installed file actually say" -- which is what
you need when the repo copy itself was the thing in doubt, or when confirming a
frontmatter repair really reached the platform.

    python tools/verify_installed_cache.py                  # every installed skill
    python tools/verify_installed_cache.py a-skill b-skill  # named skills only

Reports, per installed copy: whether the description scalar is balanced, whether
an orphaned quote sits in the head of the body, and the description's leading
text. Exit 0 = all inspected copies look sane, 1 = a problem or nothing found.
"""
import glob
import io
import os
import sys
from pathlib import Path

CACHE_GLOB = os.path.join(
    os.environ.get('APPDATA', ''), 'Claude', 'local-agent-mode-sessions',
    'skills-plugin', '*', '*', 'skills')


def installed_paths(names=None):
    for skills_root in sorted(glob.glob(CACHE_GLOB)):
        for d in sorted(Path(skills_root).iterdir()):
            if not (d / 'SKILL.md').exists():
                continue
            if names and d.name not in names:
                continue
            yield d.name, d / 'SKILL.md'


def inspect(path):
    lines = io.open(path, encoding='utf-8').read().split('\n')
    d = next((i for i, l in enumerate(lines) if l.startswith('description:')), None)
    if d is None:
        return False, 0, '(no description line)'
    val = lines[d][len('description:'):].strip()
    quoted = val[:1] in ('"', "'")
    balanced = (not quoted) or (len(val) > 1 and val[-1] == val[0])
    fence = next((i for i, l in enumerate(lines) if l.strip() == '---' and i > d), d)
    stray = sum(1 for l in lines[fence + 1:fence + 19]
                if l.rstrip().endswith(('"', "'"))
                and (l.count('"') % 2 == 1 or l.count("'") % 2 == 1))
    return balanced, stray, val


def main(argv):
    names = set(a for a in argv if not a.startswith('-')) or None
    seen = bad = 0
    for name, path in installed_paths(names):
        seen += 1
        balanced, stray, val = inspect(path)
        flag = '' if (balanced and stray == 0) else '   <-- CHECK'
        if flag:
            bad += 1
        print('%-30s balanced=%-5s stray_body_quotes=%d  %s...%s'
              % (name, balanced, stray, val[:52], flag))
    if not seen:
        print('no installed skills found under %s' % CACHE_GLOB)
        return 1
    print('--- %d installed copy(ies) inspected; %d need attention ---' % (seen, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
