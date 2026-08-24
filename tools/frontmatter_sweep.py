#!/usr/bin/env python3
"""Run validate_skill_frontmatter() across EVERY skill dir in the repo.

Why this exists (2026-08-24): the per-skill gates fire only on what you happen to
be packaging or committing. Five skills had shipped a broken description for
almost a month -- the 2026-07-29 Phase-4 description lint left an unterminated
quoted scalar whose closing quote sat in the body, so the platform listed each
file's changelog heading as its description and none of their trigger vocabulary
was routing. Two of the five (monthly-close, portfolio-reporting) were invisible
in the platform's own skill listing, which truncates. Only a repo-wide sweep
found them.

Run it after ANY bulk description operation, and as part of a session close-out
alongside repo_first_check.py.

    python tools/frontmatter_sweep.py            # sweep every skill dir
    python tools/frontmatter_sweep.py a-skill b-skill   # sweep named skills only
    python tools/frontmatter_sweep.py --quiet    # findings only, no OK lines

Exit 0 = clean, 1 = findings (suitable for CI / a pre-flight gate).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_skills import validate_skill_frontmatter, is_skill_dir  # noqa: E402

REPO = Path(__file__).resolve().parent.parent


def skill_dirs(names=None):
    if names:
        for n in names:
            d = REPO / n
            if not (d / 'SKILL.md').exists():
                print('%-34s NOT A SKILL DIR' % n)
                continue
            yield d
        return
    for d in sorted(REPO.iterdir()):
        if (d.is_dir() and not d.name.startswith(('.', '_'))
                and is_skill_dir(d.name) and (d / 'SKILL.md').exists()):
            yield d


def main(argv):
    quiet = '--quiet' in argv
    names = [a for a in argv if not a.startswith('-')]
    swept = findings = 0
    for d in skill_dirs(names or None):
        swept += 1
        errs = validate_skill_frontmatter(d)
        if errs:
            findings += len(errs)
            for e in errs:
                print('FAIL %s' % e)
        elif not quiet:
            print('ok   %s' % d.name)
    print('--- swept %d skill dir(s); %d finding(s) ---' % (swept, findings))
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
