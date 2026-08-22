import os, re, sys
root = r"C:\Users\Owner\ora-skills\register-scheduled-task"
want = os.path.basename(root)
t = open(os.path.join(root, "SKILL.md"), encoding="utf8").read()
fm = re.match(r"^---\n(.*?)\n---\n", t, re.S)
errs, d = [], ""
if not fm:
    errs.append("no YAML frontmatter block")
else:
    b = fm.group(1)
    nm = re.search(r"^name:\s*(\S+)\s*$", b, re.M)
    dm = re.search(r'^description:\s*"?(.*?)"?\s*$', b, re.M | re.S)
    if not nm:
        errs.append("no name:")
    elif nm.group(1) != want:
        errs.append(f"name {nm.group(1)!r} != dir {want!r}")
    if not dm:
        errs.append("no description:")
    else:
        d = dm.group(1)
        if len(d) > 1024:
            errs.append(f"description {len(d)}/1024 - over by {len(d)-1024}")
        if "\n" in d:
            errs.append("description spans multiple lines")
print("\n".join("FAIL: " + e for e in errs) if errs
      else f"OK  name={want}  description={len(d)}/1024")
sys.exit(1 if errs else 0)
