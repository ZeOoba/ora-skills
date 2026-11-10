import sys, hashlib, zipfile, pathlib
sys.path.insert(0, r"C:\Users\Owner\ora-skills\tools")
from pending_reimport import CACHE_ROOT
H = pathlib.Path(r"C:\Users\Owner\ora-skills\_staging\handoff\2026-10-30_land-merge-ready")
norm = lambda b: b.replace(b"\r\n", b"\n")
ok = True
for skill in ("land", "merge-ready"):
    dirs = [p for p in [pathlib.Path(CACHE_ROOT) / skill] if p.is_dir()]
    if len(dirs) != 1:
        print(f"{skill}: expected 1 cache dir, found {len(dirs)}: {dirs}"); ok = False; continue
    d = dirs[0]
    with zipfile.ZipFile(H / f"{skill}.skill") as z:
        for n in z.namelist():
            rel = n.split("/", 1)[1]
            f = d / rel
            if not f.exists():
                print(f"{skill}: MISSING {rel}"); ok = False; continue
            same = norm(f.read_bytes()) == norm(z.read(n))
            print(f"{skill}: {'OK  ' if same else 'DIFF'} {rel}")
            ok &= same
print("ALL PACKAGED FILES PRESENT AND IDENTICAL" if ok else "INSTALL INCOMPLETE")
sys.exit(0 if ok else 1)
