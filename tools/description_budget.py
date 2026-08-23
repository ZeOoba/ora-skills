#!/usr/bin/env python3
"""description_budget.py -- report frontmatter description headroom BEFORE you edit.

The platform importer rejects a .skill whose frontmatter `description` exceeds 1024
characters, or whose `name` differs from its directory -- with NO error text anywhere.
The Save-skill click is simply a no-op (package-and-stage-skill v1.21).

package_skills.py already catches both, but only at PACKAGE time -- after the edit is
written, committed, and staged. That is the wrong moment to learn you have 9 characters
of headroom. This reports it BEFORE, so an edit can be sized to fit.

Motivating incident (2026-08-22): two separate description overflows in one session --
package-and-stage-skill hit 1052/1024 and then 1064/1024 on consecutive edits, each
caught only by the pre-package gate, each costing an edit-trim-recheck cycle.

Usage:
  python tools/description_budget.py                 # every skill, tightest first
  python tools/description_budget.py <skill> [...]   # named skills
  python tools/description_budget.py --budget 40 <skill>
        # exit 1 unless <skill> has >= 40 chars of headroom -- use before a planned edit

Exit: 0 = all named skills fit (and clear --budget if given), 1 = at least one does not.
"""
import os, re, sys

LIMIT = 1024
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FM = re.compile(r"^---\n(.*?)\n---\n", re.S)


def read(skill):
    """Return (name, description_len, error)."""
    p = os.path.join(ROOT, skill, "SKILL.md")
    if not os.path.isfile(p):
        return None, 0, "no SKILL.md"
    try:
        m = FM.match(open(p, encoding="utf8").read())
    except Exception as e:
        return None, 0, f"{type(e).__name__}: {e}"[:80]
    if not m:
        return None, 0, "no frontmatter block"
    body = m.group(1)
    nm = re.search(r"^name:\s*(\S+)\s*$", body, re.M)
    d = re.search(r'^description:\s*"?(.*?)"?\s*$', body, re.M | re.S)
    if not d:
        return (nm.group(1) if nm else None), 0, "no description key"
    # strip surrounding quotes exactly as package_skills.validate_skill_frontmatter does
    # (line 179: nm.group(1).strip("'\"") != skill). A quoted `name: "debt-management"` is
    # valid YAML and installs fine; a checker that does not strip reports a false FAIL --
    # which is precisely the bug in package-and-stage-skill v1.26's step-2a snippet.
    return (nm.group(1).strip("'\"") if nm else None), len(d.group(1)), None


def skills():
    for e in sorted(os.listdir(ROOT)):
        if e.startswith((".", "_")) or e in ("tools", "plugins", "versions"):
            continue
        if os.path.isfile(os.path.join(ROOT, e, "SKILL.md")):
            yield e


def main(argv):
    want = 0
    args = argv[1:]
    if "--budget" in args:
        i = args.index("--budget")
        try:
            want = int(args[i + 1])
        except (IndexError, ValueError):
            print("--budget needs an integer"); return 1
        del args[i:i + 2]

    targets = args or list(skills())
    rows, bad = [], False
    for s in targets:
        nm, n, err = read(s)
        head = LIMIT - n
        if err:
            verdict = f"ERROR {err}"; bad = True
        elif nm != s:
            verdict = f"NAME MISMATCH name={nm!r} dir={s!r} (silent import rejection)"; bad = True
        elif n > LIMIT:
            verdict = f"OVER by {-head}  (silent import rejection)"; bad = True
        elif want and head < want:
            verdict = f"TOO TIGHT for a +{want} edit"; bad = True
        elif head < 40:
            verdict = "fits, but TIGHT"
        else:
            verdict = "ok"
        rows.append((head, s, n, verdict))

    for head, s, n, verdict in sorted(rows):
        print(f"{s:34} {n:>5}/{LIMIT}  headroom {head:>5}   {verdict}")
    if want:
        print(f"\n(--budget {want}: an edit adding more than the headroom shown will be "
              f"rejected at package time, silently at import time)")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
