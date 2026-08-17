import subprocess, os, sys

REPO = r"C:\Users\Owner\.claude"
RELPATH = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
SPLICED = r"C:\Users\Owner\ora-skills\_staging\2026-08-16\el_base_plus_mine_py.md"
TMPIDX = r"C:\Users\Owner\ora-skills\_staging\2026-08-16\tmpindex_rar"

def run(args, env=None, input_bytes=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(args, cwd=REPO, capture_output=True, env=e, input=input_bytes)
    return r.returncode, r.stdout, r.stderr

# sanity: HEAD unchanged from what we based off
rc, out, err = run(["git", "rev-parse", "HEAD"])
head = out.decode().strip()
print("HEAD:", head)

# 0. immediate pre-commit foreign-index check
rc, out, err = run(["git", "diff", "--cached", "--name-only"])
print("PRE-EXISTING REAL INDEX (should be empty):", repr(out.decode()))
if out.strip():
    print("ABORT: real index not empty, refusing to proceed")
    sys.exit(2)

# 1. write the spliced content as a new blob, raw bytes, no filters
with open(SPLICED, "rb") as f:
    spliced_bytes = f.read()
rc, out, err = run(["git", "hash-object", "-w", "--no-filters", "--stdin"], input_bytes=spliced_bytes)
if rc != 0:
    print("hash-object failed:", err.decode(errors="replace")); sys.exit(1)
new_blob = out.decode().strip()
print("NEW BLOB:", new_blob)

# 2. temp index = HEAD tree
if os.path.exists(TMPIDX):
    os.remove(TMPIDX)
env = {"GIT_INDEX_FILE": TMPIDX}
rc, out, err = run(["git", "read-tree", "HEAD"], env=env)
if rc != 0:
    print("read-tree failed:", err.decode(errors="replace")); sys.exit(1)

# 3. point path at new blob in temp index
rc, out, err = run(["git", "update-index", "--cacheinfo", f"100644,{new_blob},{RELPATH}"], env=env)
if rc != 0:
    print("update-index failed:", err.decode(errors="replace")); sys.exit(1)

# 4. verify only this file differs from HEAD in temp index
rc, out, err = run(["git", "diff", "HEAD", "--cached", "--stat"], env=env)
print("TEMP INDEX DIFF STAT vs HEAD:\n", out.decode(errors="replace"))

rc, out, err = run(["git", "diff", "HEAD", "--cached", "--numstat"], env=env)
print("TEMP INDEX NUMSTAT:\n", out.decode(errors="replace"))
