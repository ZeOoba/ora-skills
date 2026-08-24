import os, sys, zipfile, hashlib, datetime

REPO = r"C:\Users\Owner\ora-skills"
STAGING = r"C:\Users\Owner\ora-skills\_staging\2026-08-22_doctrine-patch-v01"
CACHE_BASE = r"C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills"

skills = ["acquisition-underwriting","acquisition-proposal-generation","market-monitor","loi-generation"]

sys.path.insert(0, os.path.join(REPO, "tools"))
import package_skills as ps

def norm(b):
    return b.replace(b"\r\n", b"\n").rstrip()

for name in skills:
    print("="*20, name, "="*20)
    try:
        po = ps.plugin_of(name)
    except Exception as e:
        po = f"ERROR: {e}"
    print("plugin_of:", po)
    zpath = os.path.join(STAGING, name + ".skill")
    with zipfile.ZipFile(zpath) as z:
        entries = z.namelist()
        print("entries (%d):" % len(entries))
        for e in entries:
            print("   ", e)
        skmd_name = [e for e in entries if e.endswith("SKILL.md")][0]
        with z.open(skmd_name) as f:
            zdata = f.read()

    repo_skmd = os.path.join(REPO, name, "SKILL.md")
    with open(repo_skmd, "rb") as f:
        rdata = f.read()
    print("SKILL.md raw match:", zdata == rdata, " norm match:", norm(zdata) == norm(rdata))

    shared = getattr(ps, "SHARED_ROOT_DEPS", {})
    if name in shared:
        dep = shared[name]
        dep_names = dep if isinstance(dep, (list, tuple)) else [dep]
        for depname in dep_names:
            zentry = [e for e in entries if e.endswith(depname)]
            if not zentry:
                print("  SHARED DEP", depname, "NOT FOUND IN ZIP")
                continue
            with zipfile.ZipFile(zpath) as z, z.open(zentry[0]) as f:
                zdep = f.read()
            repo_dep = os.path.join(REPO, depname)
            with open(repo_dep, "rb") as f:
                rdep = f.read()
            print("  shared dep", depname, "raw match:", zdep == rdep, " norm match:", norm(zdep) == norm(rdep))

    cache_dir = os.path.join(CACHE_BASE, name)
    exists = os.path.isdir(cache_dir)
    print("cache_dir exists:", exists, cache_dir)
    if exists:
        st = os.stat(cache_dir)
        print("cache dir ctime (creation):", datetime.datetime.fromtimestamp(st.st_ctime))
        for f in sorted(os.listdir(cache_dir)):
            print("   cache file:", f)
