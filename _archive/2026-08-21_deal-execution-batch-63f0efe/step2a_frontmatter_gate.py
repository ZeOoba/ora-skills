import os, re, sys

skills = ["deal-execution","document-assembly","estoppel-request-generation",
          "lease-abstraction-pipeline","legal-intelligence","package-and-stage-skill"]

repo = r"C:\Users\Owner\ora-skills"
overall_ok = True
for skill in skills:
    root = os.path.join(repo, skill)
    want = os.path.basename(root)
    try:
        text = open(os.path.join(root, "SKILL.md"), encoding="utf8").read()
        b = re.match(r"^---\n(.*?)\n---\n", text, re.S).group(1)
        nm = re.search(r"^name:\s*(\S+)\s*$", b, re.M).group(1)
        d = re.search(r'^description:\s*"?(.*?)"?\s*$', b, re.M | re.S).group(1)
        bad = ([f"name {nm!r} != dir {want!r}"] if nm != want else []) + \
              ([f"description {len(d)}/1024"] if len(d) > 1024 else [])
        if bad:
            overall_ok = False
            print(f"{skill}: FAIL: " + "; ".join(bad))
        else:
            print(f"{skill}: OK name={want} description={len(d)}/1024")
    except Exception as e:
        overall_ok = False
        print(f"{skill}: ERROR {e}")

print()
print("OVERALL:", "OK" if overall_ok else "FAIL")
sys.exit(0 if overall_ok else 1)
