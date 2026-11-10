import sys, pathlib, yaml
sys.path.insert(0, r"C:\Users\Owner\ora-skills\tools")
from pending_reimport import CACHE_ROOT
wt = pathlib.Path(sys.argv[1])
target = wt / "merge-ready" / "SKILL.md"
cache_line = (pathlib.Path(CACHE_ROOT) / "merge-ready/SKILL.md").read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")[2]
assert cache_line.startswith('description: "') and cache_line.endswith('"'), cache_line[:60]
with open(target, encoding="utf-8", newline="") as f:
    raw = f.read()
eol = "\r\n" if "\r\n" in raw else "\n"
lines = raw.split(eol)
assert lines[2].startswith("description: ") and not lines[2].startswith('description: "'), lines[2][:40]
old_val, new_val = lines[2], cache_line
# the new line must decode to EXACTLY the text the old line was meant to carry
assert yaml.safe_load(new_val)["description"] == old_val[len("description: "):], "value changed!"
lines[2] = new_val
with open(target, "w", encoding="utf-8", newline="") as f:
    f.write(eol.join(lines))
fm = yaml.safe_load(eol.join(lines).replace("\r\n", "\n").split("---", 2)[1])
print("strict YAML OK; name =", fm["name"], "| description", len(fm["description"]), "chars | value unchanged")
