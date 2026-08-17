import subprocess, os, sys

REPO = r"C:\Users\Owner\.claude"
RELPATH = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
TMPIDX = r"C:\Users\Owner\ora-skills\_staging\2026-08-16\tmpindex_pss"

def run(args, env=None, input_bytes=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(args, cwd=REPO, capture_output=True, env=e, input=input_bytes)
    return r.returncode, r.stdout, r.stderr

rc, out, err = run(["git", "diff", "--cached", "--name-only"])
print("PRE-EXISTING REAL INDEX (should be empty):", repr(out.decode()))
if out.strip():
    print("ABORT: real index not empty")
    sys.exit(2)

rc, out, err = run(["git", "rev-parse", "HEAD"])
head = out.decode().strip()
print("HEAD:", head)

rc, out, err = run(["git", "show", f"HEAD:{RELPATH}"])
if rc != 0:
    print("git show failed:", err.decode(errors="replace")); sys.exit(1)
base_bytes = out
base_text = base_bytes.decode("utf-8")

ANCHOR = "Renamed/expanded 2026-06-03 from reference_optimization_log.md. Living docs (firm/projects/tech/etc.) hold current state; their history accumulates HERE.\r\n\r\n"
if base_text.count(ANCHOR) != 1:
    print("ANCHOR not found or not unique -- aborting, need manual re-check")
    sys.exit(1)

MY_ENTRY_LF = """## 2026-08-16 -- package-and-stage-skill v1.19 installed (Save-skill click)

- Skill: package-and-stage-skill v1.19 -- doctrine update, commit 0661c8a "never trust pre-staged _staging drafts + archive-on-clear", authored this session after finding two mutually contradictory pre-staged event_log_entry drafts for an unrelated repo-architecture-review install earlier in the day.
- plugin_of('package-and-stage-skill') = None -- standalone install path.
- Frontmatter description trimmed to 1005/1024 chars (first draft edit landed at 1186, over budget; shortened "Oxford Realty Advisors" to "ORA" and cut the redundant archive-on-clear clause from the description, keeping the full rule in the body + changelog).
- Packaged via tools\\package_skills.py (never Compress-Archive): description 1005/1024 chars OK, 1 entries OK, forward-slash path package-and-stage-skill/SKILL.md.
- Staged to Cowork session outputs via Desktop Commander bridge + device_stage_files from _staging\\2026-08-16\\package-and-stage-skill.skill.
- Gabriel confirmed the Save-skill click in-session (2026-08-16).
- Post-install verify: AppData cache mirror at skills-plugin\\583f08bc-0123-4111-8158-8fe3d927e350\\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\\skills\\package-and-stage-skill\\SKILL.md present, single file, modified 08/16/2026 16:41:11, SHA256 D66CC2009B24F235C2906D1B196C5AF44CD1D12C1E988C2DD62E9CB6BFAA65D8, byte-identical to the repo copy.
- `pending_reimport.py clear package-and-stage-skill` run in this same pass, immediately following this append's confirmed exit 0.

"""
MY_ENTRY = MY_ENTRY_LF.replace("\r\n", "\n").replace("\n", "\r\n")

spliced_text = base_text.replace(ANCHOR, ANCHOR + MY_ENTRY, 1)
spliced_bytes = spliced_text.encode("utf-8")

rc, out, err = run(["git", "hash-object", "-w", "--no-filters", "--stdin"], input_bytes=spliced_bytes)
if rc != 0:
    print("hash-object failed:", err.decode(errors="replace")); sys.exit(1)
new_blob = out.decode().strip()
print("NEW BLOB:", new_blob)

if os.path.exists(TMPIDX):
    os.remove(TMPIDX)
env = {"GIT_INDEX_FILE": TMPIDX}
rc, out, err = run(["git", "read-tree", "HEAD"], env=env)
if rc != 0:
    print("read-tree failed:", err.decode(errors="replace")); sys.exit(1)

rc, out, err = run(["git", "update-index", "--cacheinfo", f"100644,{new_blob},{RELPATH}"], env=env)
if rc != 0:
    print("update-index failed:", err.decode(errors="replace")); sys.exit(1)

rc, out, err = run(["git", "diff", "HEAD", "--cached", "--numstat"], env=env)
print("TEMP INDEX NUMSTAT (expect one line, small insert/delete):\n", out.decode(errors="replace"))
