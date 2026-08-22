# -*- coding: utf-8 -*-
"""Trim one redundant description fragment to make room. Run BEFORE patch_v212.py."""
import io, re, sys
SK = r"C:\Users\Owner\ora-skills\register-scheduled-task\SKILL.md"
s = io.open(SK, encoding="utf8").read()
old = "register scheduled task, register this as a scheduled task, schedule this to run,"
new = "register scheduled task, schedule this to run,"
assert s.count(old) == 1, "ANCHOR FAIL (%d)" % s.count(old)
s = s.replace(old, new)
b = re.match(r"^---\n(.*?)\n---\n", s, re.S).group(1)
d = re.search(r"^description:\s*(.*?)\s*$", b, re.M | re.S).group(1)
io.open(SK, "w", encoding="utf8", newline="\n").write(s)
print("OK description now %d/1024" % len(d))
