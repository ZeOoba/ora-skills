import subprocess, os

REPO = r"C:\Users\Owner\.claude"
RELPATH = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
TMPIDX = r"C:\Users\Owner\ora-skills\_staging\2026-08-16\tmpindex_pss"

def run(args, env=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(args, cwd=REPO, capture_output=True, env=e)
    return r.returncode, r.stdout, r.stderr

env = {"GIT_INDEX_FILE": TMPIDX}
msg = (
    "log: package-and-stage-skill v1.19 install entry (isolated append)\n\n"
    "Isolated single-hunk commit of this session's own event_log.md append only\n"
    "(Save-skill-click record for package-and-stage-skill v1.19). Leaves the rest\n"
    "of the concurrent-session backlog untouched per the documented convention.\n"
)
rc, out, err = run(["git", "commit", "-m", msg], env=env)
print("COMMIT rc:", rc)
print(out.decode(errors="replace"))
print(err.decode(errors="replace"))

rc, out, err = run(["git", "log", "-1", "--format=%H %s"])
print("NEW HEAD:", out.decode(errors="replace"))

rc, out, err = run(["git", "diff", "--cached", "--name-only"])
print("REAL INDEX BEFORE REPAIR:", repr(out.decode()))

rc, out, err = run(["git", "reset", "-q", "--", RELPATH])
print("reset rc:", rc, err.decode(errors="replace"))

rc, out, err = run(["git", "diff", "--cached", "--name-only"])
print("REAL INDEX AFTER REPAIR:", repr(out.decode()))
