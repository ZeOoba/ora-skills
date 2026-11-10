import sys, pathlib, subprocess
sys.path.insert(0, r"C:\Users\Owner\ora-skills\tools")
from pending_reimport import CACHE_ROOT
wt = pathlib.Path(r"C:\Users\Owner\.claude-wt\mr-yaml-fix")
n = lambda p: p.read_bytes().replace(b"\r\n", b"\n")
fixed, cache = n(wt / "merge-ready/SKILL.md"), n(pathlib.Path(CACHE_ROOT) / "merge-ready/SKILL.md")
print("worktree SKILL.md == installed cache copy (EOL-normalized):", fixed == cache)
out = subprocess.run(["git", "-C", str(wt), "diff", "--numstat"], capture_output=True, text=True).stdout.strip()
print("numstat:", out)
fl = fixed.decode().split("\n")[:4]
print("frontmatter lines 1/2/4:", fl[0], "|", fl[1], "|", fl[3])
sys.exit(0 if fixed == cache and out == "1\t1\tmerge-ready/SKILL.md" else 1)
