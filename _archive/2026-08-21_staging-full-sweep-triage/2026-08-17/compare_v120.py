import re
p = r"C:\Users\Owner\ora-skills\package-and-stage-skill\SKILL.md"
t = open(p, "rb").read().replace(b"\r\n", b"\n").decode("utf8")
fm = re.match(r"^---\n(.*?)\n---\n", t, re.S).group(1)
d = re.search(r"^description:\s*(.*)$", fm, re.M).group(1)
print("REPO description chars:", len(d), "/1024")
print("REPO description tail:", repr(d[-190:]))
print()
i = t.find("## Changelog")
entries = [ln for ln in t[i:].split("\n") if ln.startswith("- v")]
for e in entries[:3]:
    print("*", e[:340])
    print()
print("has step 2a:", "2a. **Pre-flight" in t)
print("total chars:", len(t))
