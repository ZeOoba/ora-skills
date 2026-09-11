import zipfile, hashlib, os, sys
STAGE = r"C:\Users\Owner\ora-skills\_staging\2026-09-07"
REPO = r"C:\Users\Owner\ora-skills"
EXPECT = {"county-parcel-screen": 16, "county-sales-monitor": 1}

def sha(b): return hashlib.sha256(b).hexdigest()
def norm(b): return b.replace(b"\r\n", b"\n")

overall_ok = True
for skill, n_expect in EXPECT.items():
    print(f"=== {skill} ===")
    z = zipfile.ZipFile(os.path.join(STAGE, skill + ".skill"))
    infos = z.infolist()
    names = [i.filename for i in infos]
    dir_recs = [n for n in names if n.endswith("/")]
    backslash = [n for n in names if "\\" in n]
    print(f"entries={len(names)} expected={n_expect} dir_records={len(dir_recs)} backslash={len(backslash)}")
    if len(names) != n_expect or dir_recs or backslash:
        overall_ok = False; print("ENTRY CHECK: FAIL")
    else:
        print("ENTRY CHECK: OK")
    real_mismatch = 0; raw_only = 0; missing_in_repo = 0
    for n in names:
        rel = n.split("/", 1)[1] if n.startswith(skill + "/") else n
        rp = os.path.join(REPO, skill, rel.replace("/", os.sep))
        pk = z.read(n)
        if not os.path.exists(rp):
            missing_in_repo += 1; print(f"  {n}: REPO FILE MISSING {rp}"); continue
        rb = open(rp, "rb").read()
        if sha(pk) == sha(rb):
            tag = "MATCH"
        elif sha(norm(pk)) == sha(norm(rb)):
            tag = "MATCH-EOL-NORMALIZED"; raw_only += 1
        else:
            tag = "MISMATCH"; real_mismatch += 1
        print(f"  {n}  {sha(pk)[:12]}  {tag}")
    # repo-side files not in package
    extra = []
    for root, _, files in os.walk(os.path.join(REPO, skill)):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), os.path.join(REPO, skill)).replace(os.sep, "/")
            if f"{skill}/{rel}" not in names and rel not in names:
                extra.append(rel)
    print(f"repo-only files (not packaged): {extra}")
    verdict = "FRESH" if (real_mismatch == 0 and missing_in_repo == 0) else "STALE"
    if verdict != "FRESH": overall_ok = False
    print(f"FRESHNESS: {verdict} real_mismatch={real_mismatch} raw_only_eol={raw_only} missing_in_repo={missing_in_repo}")
print("OVERALL:", "OK" if overall_ok else "REJECT")
sys.exit(0 if overall_ok else 1)
