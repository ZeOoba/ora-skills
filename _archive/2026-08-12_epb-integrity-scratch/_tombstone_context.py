import os
R = r"C:\Users\Owner\ora-skills"
TARGETS = {
    "tax-appeal/SKILL.md": [79, 205, 206],
    "deal-execution/SKILL.md": [442],
    "loi-generation/SKILL.md": [483],
    "acquisition-underwriting/SKILL.md": [166, 257, 408, 436],
    "capex-budgeting/SKILL.md": [21, 31, 70],
    "submarket-spatial-analysis/SKILL.md": [84, 92, 98],
    "lease-abstraction-pipeline/SKILL.md": [152],
    "parcel-data-recovery/SKILL.md": [32],
}
for f, lns in TARGETS.items():
    p = os.path.join(R, f.replace("/", "\\"))
    if not os.path.exists(p):
        print("MISSING", f)
        continue
    L = open(p, encoding="utf-8", errors="replace").read().splitlines()
    print("#" * 72)
    print("FILE", f, "(%d lines)" % len(L))
    for n in lns:
        print("  --- line %d ---" % n)
        for i in range(max(0, n - 2), min(len(L), n + 1)):
            print("  %5d| %s" % (i + 1, L[i][:300].encode("ascii", "replace").decode()))
