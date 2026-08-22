import hashlib
import os
import zipfile
import datetime
from pathlib import Path

APPDATA = Path(os.environ["APPDATA"])
CACHE_ROOT = APPDATA / "Claude" / "local-agent-mode-sessions" / "skills-plugin"
STAGING = Path(r"C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch3")

BASELINES = {
    "deal-execution": "2026-08-21 17:21:59",
    "debt-management": "2026-08-17 17:34:25",
    "document-assembly": "2026-08-14 18:00:44",
    "estoppel-request-generation": "2026-08-21 17:22:05",
    "lease-abstraction-pipeline": "2026-08-21 17:21:51",
    "legal-intelligence": "2026-08-03 14:51:09",
}

def norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").rstrip()

for skill in BASELINES:
    print(f"=== {skill} ===")
    hits = [h for h in CACHE_ROOT.rglob(skill) if h.is_dir() and h.name == skill]
    if not hits:
        print("  NO CACHE DIRECTORY FOUND")
        continue
    h = hits[0]
    ctime_str = datetime.datetime.fromtimestamp(os.stat(h).st_ctime).strftime("%Y-%m-%d %H:%M:%S")
    moved = ctime_str != BASELINES[skill]
    print(f"  cache dir: {h}")
    print(f"  CreationTime now: {ctime_str}  (baseline: {BASELINES[skill]})  MOVED={moved}")

    zpath = STAGING / f"{skill}.skill"
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        all_match = True
        for name in names:
            rel = name.split("/", 1)[1] if "/" in name else name
            packaged_bytes = z.read(name)
            cache_file = h / rel
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
