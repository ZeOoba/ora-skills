import os, sys, zipfile, hashlib
REPO = r"C:\Users\Owner\ora-skills"
STAGE = os.path.join(REPO, "_staging", "2026-08-12_pending-reimport-batch")
SK = ["tax-appeal", "fleet-advisory-remediation", "daily-brief", "deal-comparison", "market-monitor"]
DEPS = {"daily-brief": ["target-markets.json"], "deal-comparison": ["target-markets.json"], "market-monitor": ["target-markets.json"]}

def norm(b):
    return b.replace(b"\r\n", b"\n").rstrip()

def sha(b):
    return hashlib.sha256(b).hexdigest()

for s in SK:
    p = os.path.join(STAGE, s + ".skill")
    print("=" * 70)
    print("PKG", s)
    if not os.path.exists(p):
        print("  1 EXISTS: FAIL - not found")
        continue
    print("  1 EXISTS: OK  %d bytes" % os.path.getsize(p))
    z = zipfile.ZipFile(p)
    names = z.namelist()
    bad = [n for n in names if "\\" in n]
    print("  2 ENTRIES: %d entries; backslash=%s" % (len(names), bad or "none"))
    for n in sorted(names):
        print("      -", n, z.getinfo(n).file_size)
    ok = True
    for n in sorted(names):
        rel = n.split("/", 1)[1] if "/" in n else n
        base = os.path.basename(n)
        if base in DEPS.get(s, []):
            src = os.path.join(REPO, base)
            label = "REPO-ROOT dep"
        else:
            src = os.path.join(REPO, s, rel)
            label = "repo skill dir"
        if not os.path.exists(src):
            print("  3 FRESH: %-28s SOURCE MISSING (%s) %s" % (base, label, src))
            ok = False
            continue
        pb = z.read(n)
        rb = open(src, "rb").read()
        if sha(pb) == sha(rb):
            print("  3 FRESH: %-28s RAW MATCH   (%s)" % (base, label))
        elif sha(norm(pb)) == sha(norm(rb)):
            print("  3 FRESH: %-28s EOL-NORM MATCH (raw differs) (%s)" % (base, label))
        else:
            print("  3 FRESH: %-28s *** REAL MISMATCH *** (%s)" % (base, label))
            print("           pkg %s / repo %s" % (sha(norm(pb))[:16], sha(norm(rb))[:16]))
            ok = False
    # coverage: repo files not in package
    repodir = os.path.join(REPO, s)
    have = set(os.path.basename(n) for n in names)
    missing = []
    for root, dirs, files in os.walk(repodir):
        for f in files:
            if f in ("PACKAGING-NOTE.md",) or f.startswith("."):
                continue
            if f not in have:
                missing.append(os.path.relpath(os.path.join(root, f), repodir))
    print("  4 COVERAGE: repo files absent from pkg: %s" % (missing or "none"))
    print("  VERDICT:", "PASS" if ok and not missing else "REVIEW")
