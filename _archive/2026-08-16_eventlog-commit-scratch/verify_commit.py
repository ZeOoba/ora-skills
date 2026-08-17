import subprocess

REPO = r"C:\Users\Owner\.claude"
RELPATH = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"

new_head = subprocess.run(
    ["git", "-C", REPO, "show", "HEAD:" + RELPATH],
    capture_output=True, text=True, encoding="utf-8"
).stdout

count = sum(1 for ln in new_head.splitlines() if ln.startswith("## "))
print("new HEAD entry count:", count)

for title in [
    "## 2026-08-16 -- package-and-stage-skill: market-monitor v1.4 installed (Save-skill click confirmed)",
    "## 2026-08-16 -- package-and-stage-skill: batch reimport triage on 3 ledger-pending skills -- 2 already in sync, 1 genuinely pending",
    "## 2026-08-16 -- package-and-stage-skill: register-scheduled-task v2.9 installed (Save-skill click confirmed)",
    "## 2026-08-16 -- package-and-stage-skill: repo-architecture-review Entry-point-A triage -- already in sync, despite \"first install\" ledger framing",
]:
    print(("FOUND  " if title in new_head else "MISSING"), title[:80])

with open(REPO + "\\" + RELPATH.replace("/", "\\"), "r", encoding="utf-8") as f:
    live = f.read()
live_count = sum(1 for ln in live.splitlines() if ln.startswith("## "))
print("current working-tree entry count:", live_count)
print("working tree still contains all HEAD entries plus other sessions' uncommitted ones:", live.startswith(new_head[:200]))
