import subprocess, os

REPO = r"C:\Users\Owner\.claude"
REL = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
SCRATCH = r"C:\Users\Owner\ora-skills\_staging\2026-08-15"

with open(os.path.join(SCRATCH, "head_base.md"), "r", encoding="utf-8") as f:
    head_text = f.read()
with open(os.path.join(SCRATCH, "my_entry.txt"), "r", encoding="utf-8") as f:
    my_entry = f.read()

INTRO_END = "their history accumulates HERE.\n\n"
idx = head_text.index(INTRO_END) + len(INTRO_END)
assert head_text[idx:idx+3] == "## ", head_text[idx:idx+40]

new_text = head_text[:idx] + my_entry + head_text[idx:]

with open(os.path.join(SCRATCH, "head_plus_mine.md"), "w", encoding="utf-8", newline="") as f:
    f.write(new_text)

print("HEAD len", len(head_text), "NEW len", len(new_text), "DELTA", len(new_text)-len(head_text))
print("insertion point context:")
print(repr(head_text[idx-40:idx+40]))
