import subprocess, sys, os

REPO = r"C:\Users\Owner\.claude"
RELPATH = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
STAGE = r"C:\Users\Owner\ora-skills\_staging\2026-08-16"

def run(args, **kw):
    r = subprocess.run(args, cwd=REPO, capture_output=True, **kw)
    return r

# 1. Get HEAD content as bytes (avoid shell redirection encoding mangling)
r = run(["git", "show", f"HEAD:{RELPATH}"])
if r.returncode != 0:
    print("GIT SHOW FAILED:", r.stderr.decode(errors="replace"))
    sys.exit(1)
base_bytes = r.stdout

base_path = os.path.join(STAGE, "el_base_py.md")
with open(base_path, "wb") as f:
    f.write(base_bytes)

base_text = base_bytes.decode("utf-8")

ANCHOR = "Renamed/expanded 2026-06-03 from reference_optimization_log.md. Living docs (firm/projects/tech/etc.) hold current state; their history accumulates HERE.\n\n"
assert ANCHOR in base_text, "anchor not found"

MY_ENTRY = """## 2026-08-16 -- repo-architecture-review v1.0 installed (Save-skill click)

- Skill: repo-architecture-review -- first install; no AppData cache mirror existed prior to this session (verified via a repo-vs-cache sweep run before packaging, which returned no match).
- Source: C:\\Users\\Owner\\ora-skills\\repo-architecture-review\\SKILL.md, single-file skill. Repo git-clean; commit f2fc1cf5f1 "Add repo-architecture-review skill (first install)".
- plugin_of('repo-architecture-review') = None -- standalone install path, not a plugin bundle member.
- Packaged via tools\\package_skills.py (never Compress-Archive): description 1004/1024 chars OK, 1 entries OK, forward-slash path repo-architecture-review/SKILL.md.
- Staged to Cowork session outputs via Desktop Commander bridge + device_stage_files from _staging\\2026-08-16\\repo-architecture-review.skill.
- Gabriel confirmed the Save-skill click in-session (2026-08-16).
- Post-install verify: AppData cache mirror at skills-plugin\\583f08bc-0123-4111-8158-8fe3d927e350\\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\\skills\\repo-architecture-review\\SKILL.md now present, single file, modified 08/16/2026 16:14:13, SHA256 BBBC5D21E8DFBE24E07A96300039FC4644DA5C98510CD025AFE16D9E94DF2879, byte-identical to the repo copy.
- pending_reimport.py list: none pending -- no ledger entry required clearing (first install never enters the reimport ledger).
- Note: two earlier draft log-entry files were found pre-staged in _staging\\2026-08-16\\ (event_log_entry_repo-architecture-review.md, event_log_entry_rar.md) with mutually contradictory narratives -- one roughly matching this session's real sequence, the other claiming the skill was already installed by a concurrent session before packaging ran here. That second claim contradicts this session's own pre-packaging cache sweep (empty) and is uncorroborated -- disregarded. This entry supersedes both drafts and is the one actually appended.

"""

spliced = base_text.replace(ANCHOR, ANCHOR + MY_ENTRY, 1)

# also bump the modified: timestamp line (this append's own timestamp) -- attributable to this session's append-event-log.py run
spliced = spliced.replace(
    "  modified: 2026-08-16T19:20:01.670Z\n",
    "  modified: 2026-08-16T20:15:29.895Z\n",
    1,
)

mine_path = os.path.join(STAGE, "el_base_plus_mine_py.md")
with open(mine_path, "w", encoding="utf-8", newline="") as f:
    f.write(spliced)

print("WROTE base:", base_path, len(base_bytes), "bytes")
print("WROTE spliced:", mine_path, len(spliced.encode("utf-8")), "bytes")
