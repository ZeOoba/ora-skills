import subprocess, os, sys

REPO = r"C:\Users\Owner\.claude"
RELPATH = "projects/C--Users-Owner-OneDrive---Oxford-Capital-Partners/memory/event_log.md"
TMPIDX = r"C:\Users\Owner\ora-skills\_staging\2026-08-16\tmpindex_rar"

def run(args, env=None, input_bytes=None):
    e = dict(os.environ)
    if env:
        e.update(env)
    r = subprocess.run(args, cwd=REPO, capture_output=True, env=e, input=input_bytes)
    return r.returncode, r.stdout, r.stderr

env = {"GIT_INDEX_FILE": TMPIDX}

msg = (
    "log: repo-architecture-review v1.0 install entry (isolated append)\n\n"
    "Isolated single-hunk commit of this session's own event_log.md append only\n"
    "(package-and-stage-skill Save-skill-click record for repo-architecture-review).\n"
    "Deliberately does not sweep in the other uncommitted entries in this file --\n"
    "those belong to other concurrent sessions per the documented event_log.md\n"
    "backlog convention (reference_event_log_uncommitted_backlog.md): whoever\n"
    "notices commits their own entry, isolated, rather than batching the backlog.\n"
)

rc, out, err = run(["git", "commit", "-m", msg], env=env)
print("COMMIT rc:", rc)
print(out.decode(errors="replace"))
print(err.decode(errors="replace"))

rc, out, err = run(["git", "log", "-1", "--format=%H %ad %s"])
print("NEW HEAD:", out.decode(errors="replace"))
