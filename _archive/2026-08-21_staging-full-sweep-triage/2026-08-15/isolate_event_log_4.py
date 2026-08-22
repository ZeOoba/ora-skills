import subprocess, os

REPO = r"C:\Users\Owner\.claude"
REL = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
SCRATCH = r"C:\Users\Owner\ora-skills\_staging\2026-08-15"

with open(os.path.join(SCRATCH, "head_base.md"), "rb") as f:
    head_bytes = f.read()
with open(os.path.join(SCRATCH, "my_entry.txt"), "rb") as f:
    entry_bytes = f.read()

head_text = head_bytes.decode("utf-8")
assert "\r" not in head_text
entry_text = entry_bytes.decode("utf-8").replace("\r", "")
assert "\r" not in entry_text

INTRO_END = "their history accumulates HERE.\n\n"
idx = head_text.index(INTRO_END) + len(INTRO_END)
assert head_text[idx:idx+3] == "## ", head_text[idx:idx+40]

new_text = head_text[:idx] + entry_text + head_text[idx:]
assert "\r" not in new_text

with open(os.path.join(SCRATCH, "head_plus_mine.md"), "wb") as f:
    f.write(new_text.encode("utf-8"))

print("HEAD len", len(head_text), "NEW len", len(new_text), "DELTA", len(new_text)-len(head_text))
print(repr(entry_text[:120]))
