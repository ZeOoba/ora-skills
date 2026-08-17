STAGE = r"C:\Users\Owner\ora-skills\_staging\2026-08-16"
RELPATH = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"

with open(STAGE + r"\el_isolated_py.patch", "r", encoding="utf-8") as f:
    lines = f.readlines()

out = []
for line in lines:
    if line.startswith("diff --git"):
        out.append(f'diff --git a/{RELPATH} b/{RELPATH}\n')
    elif line.startswith("--- "):
        out.append(f'--- a/{RELPATH}\n')
    elif line.startswith("+++ "):
        out.append(f'+++ b/{RELPATH}\n')
    else:
        out.append(line)

with open(STAGE + r"\el_isolated_retargeted_py.patch", "w", encoding="utf-8", newline="") as f:
    f.writelines(out)

print("done")
