import os, sys, hashlib, zipfile, json, subprocess

REPO = r"C:\Users\Owner\ora-skills"
STAGE = r"C:\Users\Owner\ora-skills\_staging\2026-07-21_index-unregistered-batch"

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def norm(b):
    try:
        s = b.decode("utf-8")
    except UnicodeDecodeError:
        return None
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in s.split("\n")]
    return "\n".join(lines).encode("utf-8")

print("=== ACQUISITION-UNDERWRITING.SKILL ===")
skill_zip = os.path.join(STAGE, "acquisition-underwriting.skill")
print("exists:", os.path.isfile(skill_zip))
with zipfile.ZipFile(skill_zip) as z:
    names = z.namelist()
    print("n_entries:", len(names))
    for n in names:
        print(" entry:", n, "backslash" if "\\" in n else "")
    skill_md_name = [n for n in names if n.endswith("SKILL.md")][0]
    skill_md = z.read(skill_md_name)
    tm_in_zip = None
    for n in names:
        if n.endswith("target-markets.json"):
            tm_in_zip = z.read(n)
            tm_in_zip_name = n

repo_skill_md_path = os.path.join(REPO, "acquisition-underwriting", "SKILL.md")
with open(repo_skill_md_path, "rb") as f:
    repo_skill_md = f.read()

raw_match = skill_md == repo_skill_md
norm_match = norm(skill_md) == norm(repo_skill_md)
print("SKILL.md raw sha zip:", sha256_bytes(skill_md))
print("SKILL.md raw sha repo:", sha256_bytes(repo_skill_md))
print("SKILL.md raw_match:", raw_match, "norm_match:", norm_match)

repo_tm_path = os.path.join(REPO, "target-markets.json")
with open(repo_tm_path, "rb") as f:
    repo_tm = f.read()

if tm_in_zip is not None:
    print("target-markets.json entry name in zip:", tm_in_zip_name)
    tm_raw_match = tm_in_zip == repo_tm
    tm_norm_match = norm(tm_in_zip) == norm(repo_tm)
    print("target-markets.json sha zip:", sha256_bytes(tm_in_zip))
    print("target-markets.json sha repo-root:", sha256_bytes(repo_tm))
    print("target-markets.json raw_match:", tm_raw_match, "norm_match:", tm_norm_match)
else:
    print("target-markets.json NOT FOUND IN ZIP")

print()
print("=== ORA-OPERATIONS-EXTENSIONS.PLUGIN ===")
plugin_zip = os.path.join(STAGE, "ora-operations-extensions.plugin")
print("exists:", os.path.isfile(plugin_zip))
with zipfile.ZipFile(plugin_zip) as z:
    pnames = z.namelist()
    print("n_entries:", len(pnames))
    for n in pnames:
        print(" entry:", n, "backslash" if "\\" in n else "")
    dr_entry = [n for n in pnames if n.endswith("deal-retirement/SKILL.md")]
    print("deal-retirement SKILL.md entries found:", dr_entry)
    pb_entry = [n for n in pnames if n.endswith("plugin-build.json") or n.endswith(".claude-plugin/plugin.json") or n.endswith("plugin.json")]
    print("plugin manifest-like entries:", pb_entry)
    if dr_entry:
        dr_in_zip = z.read(dr_entry[0])

repo_dr_path = os.path.join(REPO, "deal-retirement", "SKILL.md")
with open(repo_dr_path, "rb") as f:
    repo_dr = f.read()

if dr_entry:
    dr_raw_match = dr_in_zip == repo_dr
    dr_norm_match = norm(dr_in_zip) == norm(repo_dr)
    print("deal-retirement SKILL.md sha zip:", sha256_bytes(dr_in_zip))
    print("deal-retirement SKILL.md sha repo top-level:", sha256_bytes(repo_dr))
    print("deal-retirement raw_match:", dr_raw_match, "norm_match:", dr_norm_match)

print()
print("=== PENDING REIMPORT LEDGER ===")
r = subprocess.run(["python", "tools/pending_reimport.py", "list"], cwd=REPO, capture_output=True, text=True)
print(r.stdout)
print(r.stderr)
