import subprocess, os

REPO = r"C:\Users\Owner\.claude"
REL = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
SCRATCH = r"C:\Users\Owner\ora-skills\_staging\2026-08-15"

base = os.path.join(SCRATCH, "head_base.md")
mine = os.path.join(SCRATCH, "head_plus_mine.md")

p = subprocess.run(["git", "diff", "--no-index", "--", base, mine],
                    cwd=REPO, capture_output=True)
patch = p.stdout.decode("utf-8")
print("diff exit", p.returncode, "len", len(patch))

lines = patch.splitlines(keepends=True)
out = []
for ln in lines:
    if ln.startswith("diff --git"):
        out.append(f"diff --git a/{REL} b/{REL}\n")
    elif ln.startswith("--- "):
        out.append(f"--- a/{REL}\n")
    elif ln.startswith("+++ "):
        out.append(f"+++ b/{REL}\n")
    else:
        out.append(ln)
patch2 = "".join(out)

out_path = os.path.join(SCRATCH, "isolated_event_log.patch")
with open(out_path, "wb") as f:
    f.write(patch2.encode("utf-8"))

print("wrote", out_path)
print(patch2[:600])
print("...")
print(patch2[-400:])
