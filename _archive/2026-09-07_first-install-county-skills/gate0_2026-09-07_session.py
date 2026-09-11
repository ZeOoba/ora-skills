import os, re, sys
os.chdir(r"C:\Users\Owner\ora-skills"); sys.path.insert(0, "tools")
from package_skills import plugin_of
for s in ("county-parcel-screen", "county-sales-monitor"):
    print(f"{s}: plugin_of={plugin_of(s)!r}")
    txt = open(os.path.join(s, "SKILL.md"), encoding="utf8").read()
    b = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", txt, re.S).group(1)
    nm = re.search(r"^name:\s*(\S+)\s*$", b, re.M).group(1).strip("'\"")
    d = re.search(r'^description:\s*"?(.*?)"?\s*$', b, re.M | re.S).group(1)
    v = re.findall(r"v(\d+\.\d+)", d)
    print(f"  name={nm} dir_match={nm==s} description={len(d)}/1024 version_tokens={v}")
