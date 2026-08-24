import os, datetime, zipfile

STAGING = r"C:\Users\Owner\ora-skills\_staging\2026-08-22_doctrine-patch-v01"
CACHE_BASE = r"C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills"

baselines = {
    "acquisition-underwriting": "2026-08-22 17:50:08",
    "acquisition-proposal-generation": "2026-08-21 16:46:25",
    "market-monitor": "2026-08-16 15:57:44",
    "loi-generation": "2026-08-21 18:09:42",
}

for name, base in baselines.items():
    print("="*20, name, "="*20)
    zpath = os.path.join(STAGING, name + ".skill")
    with zipfile.ZipFile(zpath) as z:
        want_files = set(e.split("/", 1)[1] for e in z.namelist())
    cache_dir = os.path.join(CACHE_BASE, name)
    have_files = set()
    for root, dirs, files in os.walk(cache_dir):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), cache_dir).replace("\\", "/")
            have_files.add(rel)
    missing = want_files - have_files
    extra = have_files - want_files
    print("want:", sorted(want_files))
    print("have:", sorted(have_files))
    print("MISSING:", sorted(missing))
    print("extra (ok, e.g. old versions dir):", sorted(extra))
    st = os.stat(cache_dir)
    ct = datetime.datetime.fromtimestamp(st.st_ctime)
    print("current cache CreationTime:", ct, " baseline was:", base, " MOVED:", str(ct) != base and ct.strftime("%Y-%m-%d %H:%M:%S") != base)
