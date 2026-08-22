# -*- coding: utf-8 -*-
"""1023/1024 is not headroom, it is a tripwire. Trim explanatory text (never trigger vocabulary).
Scoped to the FRONTMATTER block only - these phrases also occur in the body."""
import io, re, sys
SK = r"C:\Users\Owner\ora-skills\register-scheduled-task\SKILL.md"
s = io.open(SK, encoding="utf8").read()
m = re.match(r"^(---\n)(.*?)(\n---\n)", s, re.S)
head, fm, tail = m.group(1), m.group(2), m.group(3)
pairs = [
    ("JSON-splice registration is PROHIBITED (proven registered-but-unscheduled 2026-06-09).",
     "JSON-splice registration is PROHIBITED (proven 2026-06-09)."),
    ("a post-registration fire-time sanity check", "a fire-time sanity check"),
    ("ORA routing canon (ggoldberg-only; Daily Brief sole cc-Eric exception)",
     "routing canon (ggoldberg-only; Daily Brief cc-Eric exception)"),
]
for old, new in pairs:
    assert fm.count(old) == 1, "ANCHOR FAIL (%d): %s" % (fm.count(old), old[:40])
    fm = fm.replace(old, new, 1)
s = head + fm + tail + s[m.end():]
d = re.search(r"^description:\s*(.*?)\s*$", fm, re.M | re.S).group(1)
n = re.search(r"^name:\s*(\S+)", fm, re.M).group(1)
if len(d) > 1024 or n != "register-scheduled-task":
    print("FAIL %s %d/1024" % (n, len(d))); sys.exit(1)
io.open(SK, "w", encoding="utf8", newline="\n").write(s)
print("OK name=%s description=%d/1024 (headroom %d)" % (n, len(d), 1024 - len(d)))
