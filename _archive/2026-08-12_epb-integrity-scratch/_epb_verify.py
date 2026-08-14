import os, zipfile, hashlib, time
STAGE = r"C:\Users\Owner\ora-skills\_staging\2026-08-12_pending-reimport-batch"
CACHE = r"C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills"
SK = ["tax-appeal", "fleet-advisory-remediation", "daily-brief", "deal-comparison", "market-monitor"]

def norm(b):
    return b.replace(b"\r\n", b"\n").rstrip()

def sha(b):
    return hashlib.sha256(b).hexdigest()

print("CACHE ROOT exists:", os.path.isdir(CACHE))
for s in SK:
    z = zipfile.ZipFile(os.path.join(STAGE, s + ".skill"))
    names = sorted(z.namelist())
    cdir = os.path.join(CACHE, s)
    print("=" * 68)
    print("SKILL", s, "| pkg entries:", len(names))
    if not os.path.isdir(cdir):
        print("  CACHE DIR MISSING ->", cdir)
        continue
    onDisk = sorted(os.listdir(cdir))
    print("  cache dir mtime:", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(cdir))))
    print("  cache files:", onDisk)
    for n in names:
        rel = n.split("/", 1)[1]
        cp = os.path.join(cdir, rel)
        if not os.path.exists(cp):
            print("  %-24s MISSING IN CACHE" % rel)
            continue
        pb = z.read(n)
        cb = open(cp, "rb").read()
        mt = time.strftime("%m-%d %H:%M", time.localtime(os.path.getmtime(cp)))
        if sha(pb) == sha(cb):
            st = "RAW MATCH"
        elif sha(norm(pb)) == sha(norm(cb)):
            st = "EOL-NORM MATCH"
        else:
            st = "*** MISMATCH ***"
        print("  %-24s %-16s cache_mtime=%s size=%d" % (rel, st, mt, len(cb)))
    extra = [f for f in onDisk if f not in [n.split("/", 1)[1] for n in names]]
    print("  extra-in-cache:", extra or "none")
