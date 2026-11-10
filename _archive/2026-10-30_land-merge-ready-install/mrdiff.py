import sys, difflib, pathlib, yaml
sys.path.insert(0, r"C:\Users\Owner\ora-skills\tools")
from pending_reimport import CACHE_ROOT
repo = pathlib.Path(r"C:\Users\Owner\ora-skills\merge-ready\SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
cache = (pathlib.Path(CACHE_ROOT) / "merge-ready" / "SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
def split(t):
    _, fm, body = t.split("---", 2)
    return yaml.safe_load(fm), body
rf, rb = split(repo); cf, cb = split(cache)
print("frontmatter values identical:", rf == cf)
for k in sorted(set(rf) | set(cf)):
    if rf.get(k) != cf.get(k):
        print(f"  key {k!r}: repo={str(rf.get(k))[:80]!r} cache={str(cf.get(k))[:80]!r}")
print("body identical:", rb == cb)
diff = [l for l in difflib.unified_diff(repo.splitlines(), cache.splitlines(), "repo", "cache", n=0, lineterm="")]
print("raw diff lines:", len(diff))
for l in diff[:12]:
    print("  ", l[:160])
