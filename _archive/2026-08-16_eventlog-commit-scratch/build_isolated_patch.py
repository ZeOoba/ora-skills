import re, subprocess, sys, os

REPO = r"C:\Users\Owner\.claude"
RELPATH = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
LIVE_PATH = os.path.join(REPO, RELPATH.replace("/", os.sep))
SCRATCH = r"C:\Users\Owner\ora-skills\_staging\2026-08-16"

MY_TITLES = [
    "## 2026-08-16 -- package-and-stage-skill: market-monitor v1.4 installed (Save-skill click confirmed)",
    "## 2026-08-16 -- package-and-stage-skill: batch reimport triage on 3 ledger-pending skills -- 2 already in sync, 1 genuinely pending",
    "## 2026-08-16 -- package-and-stage-skill: register-scheduled-task v2.9 installed (Save-skill click confirmed)",
    "## 2026-08-16 -- package-and-stage-skill: repo-architecture-review Entry-point-A triage -- already in sync, despite \"first install\" ledger framing",
]

def split_entries(text):
    lines = text.splitlines(keepends=True)
    # find header/intro = everything before first line starting with "## "
    first_idx = None
    for i, ln in enumerate(lines):
        if ln.startswith("## "):
            first_idx = i
            break
    if first_idx is None:
        return "".join(lines), []
    header = "".join(lines[:first_idx])
    body_lines = lines[first_idx:]
    # split body into entries at each "## " boundary
    entries = []
    cur = []
    for ln in body_lines:
        if ln.startswith("## ") and cur:
            entries.append("".join(cur))
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        entries.append("".join(cur))
    return header, entries

# 1. HEAD content
head_content = subprocess.run(
    ["git", "-C", REPO, "show", "HEAD:" + RELPATH],
    capture_output=True, text=True, encoding="utf-8"
).stdout

# 2. current working tree content
with open(LIVE_PATH, "r", encoding="utf-8") as f:
    live_content = f.read()

head_header, head_entries = split_entries(head_content)
live_header, live_entries = split_entries(live_content)

print("HEAD entries count:", len(head_entries))
print("LIVE entries count:", len(live_entries))

# 3. find my 4 entries in live_entries by title prefix match
my_blocks = {}
for title in MY_TITLES:
    found = None
    for e in live_entries:
        if e.startswith(title):
            found = e
            break
    if found is None:
        print("MISSING TITLE:", title)
    my_blocks[title] = found

missing = [t for t, v in my_blocks.items() if v is None]
if missing:
    print("ABORT: missing entries:", missing)
    sys.exit(1)

# order: most-recently-appended first (repo-architecture-review, register-scheduled-task, batch3, market-monitor)
ordered_titles = [MY_TITLES[3], MY_TITLES[2], MY_TITLES[1], MY_TITLES[0]]
mine_concat = "".join(my_blocks[t] for t in ordered_titles)

# 4. build new content = HEAD header + my 4 blocks + HEAD original entries unchanged
new_content = head_header + mine_concat + "".join(head_entries)

base_path = os.path.join(SCRATCH, "el_base.md")
plus_path = os.path.join(SCRATCH, "el_base_plus_mine.md")
with open(base_path, "w", encoding="utf-8", newline="") as f:
    f.write(head_content)
with open(plus_path, "w", encoding="utf-8", newline="") as f:
    f.write(new_content)

print("Wrote base:", base_path, len(head_content), "chars")
print("Wrote base_plus_mine:", plus_path, len(new_content), "chars")
print("OK")
