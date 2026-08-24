import os, re, sys
root = sys.argv[1].rstrip("/\\"); want = os.path.basename(root)
b = re.match(r"^---\n(.*?)\n---\n",
             open(os.path.join(root, "SKILL.md"), encoding="utf8").read(), re.S).group(1)
nm = re.search(r"^name:\s*(\S+)\s*$", b, re.M).group(1)
d  = re.search(r'^description:\s*"?(.*?)"?\s*$', b, re.M | re.S).group(1)
bad = ([f"name {nm!r} != dir {want!r}"] if nm != want else []) + \
      ([f"description {len(d)}/1024"] if len(d) > 1024 else [])
print(("FAIL: " + "; ".join(bad)) if bad else f"OK name={want} description={len(d)}/1024")
sys.exit(1 if bad else 0)
