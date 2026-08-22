import zipfile, re, os, subprocess

SKILL_PATH = r"C:\Users\Owner\ora-skills\_staging\2026-08-22_reimport-batch5\register-scheduled-task.skill"
REPO_DIR = r"C:\Users\Owner\ora-skills\register-scheduled-task"

zf = zipfile.ZipFile(SKILL_PATH)
skill_md_bytes = zf.read("register-scheduled-task/SKILL.md")
skill_md_text = skill_md_bytes.decode("utf8")

print("=== ITEM 2a: FRONTMATTER GATE (CRLF-tolerant) ===")
m = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n", skill_md_text, re.S)
if not m:
    print("FAIL: could not locate frontmatter block even with CRLF tolerance")
else:
    b = m.group(1)
    nm = re.search(r"^name:\s*(\S+)\s*$", b, re.M).group(1)
    dmatch = re.search(r'^description:\s*"?(.*?)"?\s*$', b, re.M | re.S)
    d = dmatch.group(1)
    want = "register-scheduled-task"
    bad = []
    if nm != want:
        bad.append(f"name {nm!r} != dir {want!r}")
    if len(d) > 1024:
        bad.append(f"description {len(d)}/1024")
    print("name:", nm)
    print("description length:", len(d), "/1024")
    print("FAIL:" if bad else "OK:", "; ".join(bad) if bad else f"name={want} description={len(d)}/1024")

print("\n=== ITEM 3: FRESHNESS vs REPO ===")
repo_skill_md = os.path.join(REPO_DIR, "SKILL.md")
with open(repo_skill_md, "rb") as f:
    repo_bytes = f.read()

def norm(bb):
    return bb.replace(b"\r\n", b"\n").rstrip()

raw_match = (skill_md_bytes == repo_bytes)
norm_match = (norm(skill_md_bytes) == norm(repo_bytes))
print("SKILL.md raw byte match packaged vs repo:", raw_match)
print("SKILL.md EOL-normalized match packaged vs repo:", norm_match)

repo_ref = os.path.join(REPO_DIR, "references", "incident-history.md")
if os.path.isfile(repo_ref):
    with open(repo_ref, "rb") as f:
        repo_ref_bytes = f.read()
    pkg_ref_bytes = zf.read("register-scheduled-task/references/incident-history.md")
    print("incident-history.md raw match:", pkg_ref_bytes == repo_ref_bytes)
    print("incident-history.md normalized match:", norm(pkg_ref_bytes) == norm(repo_ref_bytes))
else:
    print("repo references/incident-history.md not found at", repo_ref)

print("\n=== GIT STATUS (repo-clean check) ===")
r = subprocess.run(["git", "status", "--short", "--", "register-scheduled-task/"],
                    cwd=r"C:\Users\Owner\ora-skills", capture_output=True, text=True)
print("git status --short output:", repr(r.stdout), r.stderr)

r2 = subprocess.run(["git", "log", "-1", "--format=%H %ci", "--", "register-scheduled-task/"],
                     cwd=r"C:\Users\Owner\ora-skills", capture_output=True, text=True)
print("git log -1:", r2.stdout.strip(), r2.stderr)

r3 = subprocess.run(["git", "log", "-1", "--format=%H"], cwd=r"C:\Users\Owner\ora-skills",
                     capture_output=True, text=True)
print("current HEAD:", r3.stdout.strip())

zf.close()
