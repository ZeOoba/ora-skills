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

# retarget a/ and b/ headers to the real repo path
base_fwd = base.replace("\\", "/")
mine_fwd = mine.replace("\\", "/")
patch2 = patch.replace(f"a/{base_fwd}", f"a/{REL}").replace(f"b/{mine_fwd}", f"b/{REL}")
patch2 = patch2.replace(f"--- {base_fwd}", f"--- a/{REL}").replace(f"+++ {mine_fwd}", f"+++ b/{REL}")
patch2 = patch2.replace(f"diff --git {base_fwd} {mine_fwd}", f"diff --git a/{REL} b/{REL}")

out_path = os.path.join(SCRATCH, "isolated_event_log.patch")
with open(out_path, "w", encoding="utf-8", newline="\n") as f:
    f.write(patch2)

print("wrote", out_path)
print(patch2[:800])
