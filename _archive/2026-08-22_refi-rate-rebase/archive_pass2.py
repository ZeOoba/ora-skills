import io, os, re
SK = r"C:\Users\Owner\ora-skills\acquisition-underwriting\SKILL.md"
OLD = r"C:\Users\Owner\ora-skills\acquisition-underwriting\versions\CHANGELOG-v3.2-v4.9.md"
NEW = r"C:\Users\Owner\ora-skills\acquisition-underwriting\versions\CHANGELOG-v3.2-v4.11.md"

s = io.open(SK, encoding="utf8", newline="").read().replace("\r\n", "\n")

def take(tag):
    m = re.search(r"^\*\*" + re.escape(tag) + r" \(\d{4}-\d{2}-\d{2}\):\*\*.*?$", s, re.M)
    assert m, "anchor missing: " + tag
    return m.group(0)

v411, v410 = take("v4.11"), take("v4.10")
for para in (v411, v410):
    before = s
    s = s.replace(para + "\n\n", "", 1)
    assert s != before, "removal failed"

arch = io.open(OLD, encoding="utf8", newline="").read().replace("\r\n", "\n")
assert "**v4.10 (2026-08-05):**" not in arch
arch = arch.replace("(v3.2 through v4.9)", "(v3.2 through v4.11)", 1)
arch = arch.rstrip("\n") + (
    "\n\n**v4.10 and v4.11 appended 2026-08-22**, same pass as v4.8/v4.9 — completing the restoration "
    "of the four-most-recent-inline policy rather than stopping half way. Verbatim.\n\n"
    + v411 + "\n\n" + v410 + "\n")
io.open(NEW, "w", encoding="utf8", newline="\n").write(arch)

a = "Revision history through v4.9 is archived at `versions/CHANGELOG-v3.2-v4.9.md`"
assert a in s
s = s.replace(a, "Revision history through v4.11 is archived at `versions/CHANGELOG-v3.2-v4.11.md`", 1)

m = re.search(r"^\*\*Earlier revisions v4\.6–v4\.9 archived\*\*.*?$", s, re.M)
assert m
s = s.replace(m.group(0),
  "**Earlier revisions v4.6–v4.11 archived** to `versions/CHANGELOG-v3.2-v4.11.md` "
  "(v4.6–v4.7 on 2026-08-13; v4.8–v4.11 on 2026-08-22, restoring this file's own "
  "\"four most recent stay inline\" policy) — provenance only, every operative number/rule "
  "independently restated in its own section below.", 1)

a = ("**(1) Inline changelog restored to policy** — v4.8 and v4.9 moved verbatim to "
     "`versions/CHANGELOG-v3.2-v4.9.md` (renamed from `-v4.7`). The inline block had reached seven "
     "revisions against the \"four most recent stay inline\" rule this file set for itself at v4.9, "
     "and the excess was being paid on every single invocation.")
assert a in s, "v4.15 entry text not found"
s = s.replace(a,
  "**(1) Inline changelog restored to policy** — v4.8 through v4.11 moved verbatim to "
  "`versions/CHANGELOG-v3.2-v4.11.md` (renamed from `-v4.7`), leaving v4.12–v4.15 inline. The block had "
  "reached seven revisions against the \"four most recent stay inline\" rule this file set for itself at "
  "v4.9, and the excess was being paid on every single invocation.", 1)

io.open(SK, "w", encoding="utf8", newline="\n").write(s)
print("inline revisions now:", re.findall(r"^\*\*(v4\.\d+) \(", s, re.M))
