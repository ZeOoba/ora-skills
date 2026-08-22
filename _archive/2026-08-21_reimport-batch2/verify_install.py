import hashlib
import os
import zipfile
from pathlib import Path

APPDATA = Path(os.environ["APPDATA"])
CACHE_ROOT = APPDATA / "Claude" / "local-agent-mode-sessions" / "skills-plugin"
STAGING = Path(r"C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch2")

BASELINES = {
    "insurance-renewal-review": "2026-08-21 17:19:31",
    "package-and-stage-skill": "2026-08-21 16:56:54",
    "dirty-tree-triage": "2026-08-13 20:08:25",
}

def norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").rstrip()

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

for skill in ["insurance-renewal-review", "package-and-stage-skill", "dirty-tree-triage"]:
    print(f"=== {skill} ===")
    hits = list(CACHE_ROOT.rglob(skill))
    hits = [h for h in hits if h.is_dir() and h.name == skill]
    if not hits:
        print("  NO CACHE DIRECTORY FOUND")
        continue
    for h in hits:
        ctime = os.stat(h).st_ctime
        import datetime
        ctime_str = datetime.datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M:%S")
        moved = ctime_str != BASELINES[skill]
        print(f"  cache dir: {h}")
        print(f"  CreationTime now: {ctime_str}  (baseline: {BASELINES[skill]})  MOVED={moved}")

    zpath = STAGING / f"{skill}.skill"
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        print(f"  packaged entries ({len(names)}):")
        all_match = True
        for name in names:
            # entries look like "<skill>/relative/path"
            rel = name.split("/", 1)[1] if "/" in name else name
            packaged_bytes = z.read(name)
            cache_file = hits[0] / rel
            if not cache_file.exists():
                print(f"    MISSING in cache: {rel}")
                all_match = False
                continue
            cache_bytes = cache_file.read_bytes()
            raw_match = packaged_bytes == cache_bytes
            norm_match = norm(packaged_bytes) == norm(cache_bytes)
            status = "RAW-MATCH" if raw_match else ("NORMALIZED-MATCH" if norm_match else "MISMATCH")
            print(f"    {rel}: {status}")
            if not (raw_match or norm_match):
                all_match = False
        print(f"  ALL FILES MATCH: {all_match}")
