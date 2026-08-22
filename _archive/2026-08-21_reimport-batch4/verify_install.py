import os
import zipfile
import datetime
from pathlib import Path

APPDATA = Path(os.environ["APPDATA"])
CACHE_ROOT = APPDATA / "Claude" / "local-agent-mode-sessions" / "skills-plugin"
STAGING = Path(r"C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch4")

BASELINES = {
    "isolated-commit": None,  # no prior cache dir -- first install
    "lease-addendum": "2026-08-14 18:30:37",
    "loi-generation": "2026-08-18 15:05:16",
}

def norm(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").rstrip()

for skill, baseline in BASELINES.items():
    print(f"=== {skill} ===")
    hits = [h for h in CACHE_ROOT.rglob(skill) if h.is_dir() and h.name == skill]
    if not hits:
        print("  NO CACHE DIRECTORY FOUND")
        if baseline is None:
            print("  (expected a NEW cache dir for first install -- NOT FOUND means click did not register)")
        continue
    h = hits[0]
    ctime_str = datetime.datetime.fromtimestamp(os.stat(h).st_ctime).strftime("%Y-%m-%d %H:%M:%S")
    if baseline is None:
        print(f"  cache dir: {h}")
        print(f"  CreationTime: {ctime_str}  (no prior baseline -- existence itself is the install signal) FIRST-INSTALL=True")
    else:
        moved = ctime_str != baseline
        print(f"  cache dir: {h}")
        print(f"  CreationTime now: {ctime_str}  (baseline: {baseline})  MOVED={moved}")

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
