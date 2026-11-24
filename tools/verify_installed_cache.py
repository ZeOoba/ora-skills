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
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_reimport as pr  # noqa: E402


def installed_paths(names=None, cache_root=None, rpm_root=None):
    """(skill, SKILL.md) for every installed copy in effect: the legacy skills-plugin
    cache AND the rpm store-plugin root, each skill resolved the way every drift reader
    resolves it (pending_reimport.installed_skill_dirs; R34-6 follow-up -- a legacy-only
    glob found none of the ~100 rpm-installed ORA skills)."""
    for name, d in pr.installed_skill_dirs(cache_root, rpm_root).items():
        if names and name not in names:
            continue
        if (d / 'SKILL.md').exists():
            yield name, d / 'SKILL.md'


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


def main(argv, cache_root=None, rpm_root=None):
    names = set(a for a in argv if not a.startswith('-')) or None
    unreachable = pr.unreachable_cache_roots(cache_root, rpm_root)
    if unreachable:
        # Fail closed: a partial read would omit every skill under the unreadable root.
        print('install root unreadable: %s -- nothing inspected'
              % ', '.join(str(r) for r in unreachable))
        return 1
    seen = bad = 0
    for name, path in installed_paths(names, cache_root, rpm_root):
        seen += 1
        balanced, stray, val = inspect(path)
        flag = '' if (balanced and stray == 0) else '   <-- CHECK'
        if flag:
            bad += 1
        print('%-30s balanced=%-5s stray_body_quotes=%d  %s...%s'
              % (name, balanced, stray, val[:52], flag))
    if not seen:
        print('no installed skills found under %s or %s'
              % (cache_root or pr.CACHE_ROOT, rpm_root or pr.RPM_ROOT))
        return 1
    print('--- %d installed copy(ies) inspected; %d need attention ---' % (seen, bad))
    return 1 if bad else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
