import re

SCRATCH = r"C:\Users\Owner\ora-skills\_staging\2026-08-16"
RELPATH = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"

with open(SCRATCH + r"\el_isolated.patch", "rb") as f:
    raw = f.read()

if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
    text = raw.decode("utf-16")
elif raw[:3] == b"\xef\xbb\xbf":
    text = raw.decode("utf-8-sig")
else:
    text = raw.decode("utf-8")

lines = text.splitlines(keepends=True)
out = []
for ln in lines:
    if ln.startswith("diff --git"):
        out.append('diff --git a/%s b/%s\n' % (RELPATH, RELPATH))
    elif ln.startswith("--- "):
        out.append('--- a/%s\n' % RELPATH)
    elif ln.startswith("+++ "):
        out.append('+++ b/%s\n' % RELPATH)
    else:
        out.append(ln)

with open(SCRATCH + r"\el_isolated_retargeted.patch", "w", encoding="utf-8", newline="\n") as f:
    f.write("".join(out))

print("done, lines:", len(out))
print("".join(out[:8]))
