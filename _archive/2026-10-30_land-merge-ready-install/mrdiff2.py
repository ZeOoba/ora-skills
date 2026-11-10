import sys, difflib, pathlib, yaml
sys.path.insert(0, r"C:\Users\Owner\ora-skills\tools")
from pending_reimport import CACHE_ROOT
R = pathlib.Path(r"C:\Users\Owner\ora-skills")
repo = (R / "merge-ready/SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
cache = (pathlib.Path(CACHE_ROOT) / "merge-ready/SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n")
diff = list(difflib.unified_diff(repo.splitlines(), cache.splitlines(), "repo", "cache", n=0, lineterm=""))
print("raw diff lines:", len(diff))
for l in diff:
    print("  ", (l[:110] + " ... " + l[-60:]) if len(l) > 180 else l)
cf = yaml.safe_load(cache.split("---", 2)[1])
print("cache frontmatter parses; keys:", sorted(cf))
bad = []
for p in sorted(R.glob("*/SKILL.md")):
    t = p.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n")
    if not t.startswith("---"):
        continue
    try:
        yaml.safe_load(t.split("---", 2)[1])
    except yaml.YAMLError as e:
        bad.append((p.parent.name, str(e).splitlines()[0]))
print(f"strict-YAML frontmatter failures across repo: {len(bad)}")
for n, e in bad:
    print("   ", n, "::", e)
