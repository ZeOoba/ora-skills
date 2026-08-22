import subprocess, os

REPO = r"C:\Users\Owner\.claude"
REL = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
SCRATCH = r"C:\Users\Owner\ora-skills\_staging\2026-08-15"

def run(args, cwd=REPO):
    p = subprocess.run(args, cwd=cwd, capture_output=True)
    return p.returncode, p.stdout, p.stderr

rc, head_bytes, err = run(["git", "show", f"HEAD:{REL}"])
assert rc == 0, err
head_text = head_bytes.decode("utf-8")

with open(os.path.join(REPO, REL), "rb") as f:
    work_text = f.read().decode("utf-8")

MY_START = "## 2026-08-15 -- 12 skills installed via Save-skill click (Entry point B, skill-text-audit remediation batch)"
NEXT_MARK = "## 2026-08-15 \u2014 ora-setup-audit v1.4 installed via confirmed Save-skill click"

s = work_text.index(MY_START)
e = work_text.index(NEXT_MARK, s)
my_entry = work_text[s:e]
print("ENTRY LENGTH", len(my_entry))
print("ENTRY LINES", my_entry.count("\n"))
print("---START---")
print(my_entry[:200])
print("---END---")
print(my_entry[-200:])

with open(os.path.join(SCRATCH, "my_entry.txt"), "w", encoding="utf-8") as f:
    f.write(my_entry)
with open(os.path.join(SCRATCH, "head_base.md"), "w", encoding="utf-8", newline="") as f:
    f.write(head_text)
