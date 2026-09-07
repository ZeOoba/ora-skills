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

# `description: >` / `description: |` plus the indented block that follows it.
BLOCK = re.compile(r"^description:[ \t]*([>|])[-+0-9]*[ \t]*\n((?:[ \t]+.*\n?|\n)*)", re.M)
INLINE = re.compile(r'^description:\s*"?(.*?)"?\s*$', re.M | re.S)


def extract_description(body):
    """Return the description exactly as YAML would materialize it, or None.

    Handles the inline form AND both block-scalar forms. This used to be a single
    inline regex, which matched `description: >` with an effectively empty capture
    and reported **1 character** -- a silent false PASS for every block-scalar skill.
    Found 2026-09-06 (Automation Audit R23-6): 3 skills use block style, one of them
    (`county-parcel-screen`) was 1,306 chars, i.e. 282 over the importer's hard cap,
    and this gate had been reporting it as `ok` with 1,023 chars of headroom.

    Folded (`>`) joins lines with spaces; literal (`|`) preserves newlines -- the
    distinction matters because the importer measures the materialized string.

    NOTE: this is NOT the number that gates packaging -- see packager_description()
    below and read() for why the larger of the two is what's reported.
    """
    m = BLOCK.search(body)
    if m:
        style = m.group(1)
        kept = []
        for line in m.group(2).splitlines():
            if not line.strip():
                kept.append("")
            elif line[:1] in " \t":
                kept.append(line.strip())
            else:
                break  # dedented out of the block; a sibling key started
        if style == "|":
            return "\n".join(kept).strip()
        return " ".join(x for x in kept if x)
    m = INLINE.search(body)
    return m.group(1) if m else None


def packager_description(body):
    """Return the description exactly as `package_skills.py` measures it.

    The packager (package_skills.py:181, :275) uses a DIFFERENT regex from this module:
    `^description:\\s*(.*?)(?=\\n[a-zA-Z_-]+:|\\Z)` captures the raw block INCLUDING the
    `>` marker, the newlines and every line's leading indentation. For a block-scalar
    description that runs ~28 chars higher than the YAML-folded string the importer
    actually receives (measured 2026-09-07: county-parcel-screen 974 folded vs 1002 raw;
    county-sales-monitor 936 vs 964 -- +28 on both, ~14 lines x 2 chars of overhead).

    Both numbers are kept and the LARGER one gates, because the two answer different
    questions and only one of them can block you today:
      - folded  = what the platform importer materializes; semantically correct.
      - raw     = what package_skills.py enforces; it refuses to build over 1024.
    Reporting only the folded count would let this tool clear a skill the packager then
    rejects -- and this skill's own doctrine is that "a fallback checker that disagrees
    with the real packager is worse than no fallback checker" (v1.27, on the inverse bug).
    So: gate conservatively, show both when they differ, never under-report.
    """
    m = re.search(r"^description:\s*(.*?)(?=\n[a-zA-Z_-]+:|\Z)", body, re.S | re.M)
    return m.group(1) if m else None


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
    desc = extract_description(body)
    if desc is None:
        return (nm.group(1) if nm else None), 0, "no description key"
    # Gate on the LARGER of the two measurements -- see packager_description().
    # The folded count is semantically right; the packager's raw count is what
    # actually refuses to build. Reporting only the folded one would clear a skill
    # the packager then rejects, which is the exact failure mode v1.27 recorded in
    # the opposite direction. Never under-report against the tool that can block you.
    raw = packager_description(body)
    if raw is not None and len(raw) > len(desc):
        return (nm.group(1).strip("'\"") if nm else None), len(raw), None
    # strip surrounding quotes exactly as package_skills.validate_skill_frontmatter does
    # (line 179: nm.group(1).strip("'\"") != skill). A quoted `name: "debt-management"` is
    # valid YAML and installs fine; a checker that does not strip reports a false FAIL --
    # which is precisely the bug in package-and-stage-skill v1.26's step-2a snippet.
    return (nm.group(1).strip("'\"") if nm else None), len(desc), None


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
