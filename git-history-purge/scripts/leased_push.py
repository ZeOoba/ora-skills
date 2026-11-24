"""Force-push a history rewrite, checking the whole chain backup -> copy -> rewrite -> remote first.

  python -I leased_push.py prepare <backup.git> <work.git>
  python -I leased_push.py <backup.git> <work.git> <remote-url> [--batch N] [--dry-run]
                          [--delete-removed] [--main-ref refs/heads/<default>]

prepare  makes the copy filter-repo runs on: refuses (exit 2) if <work.git> exists, then
         `git init --bare` + `git fetch --no-tags` of the backup's refs/heads/* and refs/tags/*
         ONLY (no refs/pull/* or other namespaces, nor objects reachable only from them), and
         <work.git>/purge-backup-refs.txt = "# backup <abs path>" plus the backup's heads and tags
         ("<sha> <ref>") at copy time. A backup that changes during the copy is refused (exit 2).
         Run filter-repo on <work.git> afterwards (it leaves filter-repo/ref-map: old SHA,
         new SHA, ref; a second filter-repo pass on the same copy keeps the original "old" SHAs).

Push mode checks every link before anything is pushed:
  copy     - purge-backup-refs.txt must exist (else exit 2: make the copy with `prepare`) and
             name this backup. If the backup's heads/tags now differ from it in any way (ref
             added, removed or moved) -> exit 2 STALE: the backup changed after the copy.
  rewrite  - every ref in ref-map must have been rewritten FROM the snapshot's SHA, else exit 2.
  default  - the default branch is the remote's HEAD (`ls-remote --symref`). --main-ref, if
             given, must equal it; if the remote reports no HEAD, --main-ref is required. It
             must exist in <work.git>. Any of these failing -> exit 2.
  remote   - each ref is classified against `git ls-remote`:
               done   remote already has the rewritten SHA (an earlier run pushed it): skipped
               push   remote still has the backup's SHA (or neither has the ref)
               moved  anything else: someone pushed after the backup; also any branch or tag
                      on the remote that the backup does not have (created after it)
             Any moved ref -> nothing pushed, exit 3. The freeze leaked: find who. Never fetch
             into the existing backup (it is the record of the old commits); make a NEW backup
             directory from the remote, redo the copy and rewrite from it, and pass both backups
             to local_cleanup.py changed.
  deleted  - refs in the snapshot that are not in <work.git> (every commit on them was purged;
             never inferred from the live backup) still hold the old data on the remote.
             Without --delete-removed: exit 4, nothing pushed. With it: each is deleted, leased
             against the snapshot's SHA.

  after    - once the last push is done, `ls-remote` again: a branch or tag on the remote that is
             neither in <work.git> nor deleted by the rewrite (created during the push), or a
             pushed ref whose remote value is not the pushed SHA -> exit 3 MOVED (same recovery).

Every lease is against the backup's SHA (as snapshotted), never against what the remote shows
at push time. Refspecs carry NO "+": a "+" forces past its own lease. All refs except the
default branch go in batches of --batch (default 40; hundreds of lease arguments exceed the
Windows command-line limit); the default branch is pushed ALONE, last, and only if nothing
else was rejected.

Exit: 0 everything pushed or already done; 1 a rejection or the default branch held (rerun
after fixing: finished refs are skipped); 2 bad arguments, unreadable repo, failed ls-remote,
missing or stale snapshot or ref-map, default-branch problem, existing prepare target;
3 remote moved since backup (before the push, or found by the re-check after it); 4 refs deleted
by the rewrite (see above).

Every git call decodes as UTF-8 (surrogateescape), so non-ASCII ref names round-trip under
`python -I` on Windows, where the default would be the ANSI code page.
"""
import argparse
import os
import subprocess
import sys

ZERO = "0" * 40
SNAPSHOT = "purge-backup-refs.txt"
MOVED_RECOVERY = ("Someone pushed after the backup: find who (the freeze leaked). "
                  "Never fetch into the existing backup (it is the record of the old commits). "
                  "Make a NEW backup directory from the remote (Step 1), redo Steps 2-3 from it, "
                  "and pass both backups to local_cleanup.py changed.")
MOVED_HELP = "nothing pushed. " + MOVED_RECOVERY
MOVED_AFTER_HELP = ("the remote moved DURING the push (the refs pushed above stand). " + MOVED_RECOVERY)


def sh(args):
    # UTF-8 explicitly: under `python -I` on Windows text=True would decode as the ANSI code page
    # and a non-ASCII ref name would never match (G1-07).
    return subprocess.run(args, capture_output=True, encoding="utf-8", errors="surrogateescape")


def local_refs(repo):
    r = sh(["git", "-C", repo, "for-each-ref", "--format=%(objectname) %(refname)", "refs/heads", "refs/tags"])
    if r.returncode:
        return None
    return {ref: sha for sha, ref in (l.split(" ", 1) for l in r.stdout.splitlines() if l)}


def read_ref_map(work):
    path = os.path.join(work, "filter-repo", "ref-map")
    try:
        with open(path, encoding="utf-8", errors="surrogateescape") as fh:
            rows = [l.split() for l in fh.read().splitlines()[1:] if l.strip()]
    except OSError:
        return None
    return {ref: (old, new) for old, new, ref in rows}


def prepare(argv):
    ap = argparse.ArgumentParser(prog="leased_push.py prepare")
    ap.add_argument("backup")
    ap.add_argument("work")
    a = ap.parse_args(argv)
    if os.path.lexists(a.work):
        print("%s already exists: never reuse a copy; pick a new directory" % a.work)
        return 2
    backup = local_refs(a.backup)
    if not backup:
        print("cannot read refs from %s" % a.backup)
        return 2
    # Heads and tags ONLY (G1-11): a GitHub --mirror backup also holds refs/pull/*, which scan
    # never reads and which are never pushed; objects reachable only from them stay out of the copy.
    r = sh(["git", "init", "-q", "--bare", a.work])
    if not r.returncode:
        r = sh(["git", "-C", a.work, "fetch", "-q", "--no-tags", os.path.abspath(a.backup),
                "+refs/heads/*:refs/heads/*", "+refs/tags/*:refs/tags/*"])
    if r.returncode:
        print("copy failed: %s" % r.stderr.strip()[-300:])
        return 2
    head = sh(["git", "-C", a.backup, "symbolic-ref", "-q", "HEAD"]).stdout.strip()
    if head.startswith("refs/heads/"):
        sh(["git", "-C", a.work, "symbolic-ref", "HEAD", head])
    snap = local_refs(a.backup)      # refs at copy time; a change during the copy is refused here
    if snap != backup or local_refs(a.work) != snap:
        print("the backup changed while it was being copied: move %s aside and run prepare again" % a.work)
        return 2
    with open(os.path.join(a.work, SNAPSHOT), "w", encoding="utf-8", errors="surrogateescape", newline="\n") as fh:
        fh.write("# backup %s\n" % os.path.abspath(a.backup))
        fh.writelines("%s %s\n" % (sha, ref) for ref, sha in sorted(snap.items()))
    print("copy made: %d refs recorded in %s" % (len(snap), SNAPSHOT))
    return 0


def push(work, url, refs, leases, dry_run, flags, rejected, label, accepted):
    """One `git push` of refs (each "src:dst" with a lease); tallies porcelain flags and records
    each ref the remote accepted in accepted {dst: flag}."""
    print("%s: %s" % (label, " ".join(dst for _, dst in refs)))
    args = ["git", "-C", work, "push", "--porcelain", "--no-verify"]
    if dry_run:
        args.append("--dry-run")
    args.append(url)
    args += ["--force-with-lease=%s:%s" % (dst, leases[dst]) for _, dst in refs]
    args += ["%s:%s" % (src, dst) for src, dst in refs]
    p = sh(args)
    seen = False
    for l in p.stdout.splitlines():
        if "\t" in l and l[:1] in "+-*= !":
            seen = True
            f = l.split("\t")[0].strip() or " "
            flags[f] = flags.get(f, 0) + 1
            if f == "!":
                rejected.append(l)
            else:
                accepted[l.split("\t")[1].rsplit(":", 1)[-1]] = f
    if p.returncode and not seen:
        rejected.append("%s failed: %s" % (label, p.stderr.strip()[-300:]))


def read_snapshot(work):
    """purge-backup-refs.txt written by `prepare`: (backup path, {ref: sha}) or None."""
    try:
        with open(os.path.join(work, SNAPSHOT), encoding="utf-8", errors="surrogateescape") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None
    if not lines or not lines[0].startswith("# backup "):
        return None
    refs = {}
    for l in lines[1:]:
        if l.strip():
            sha, ref = l.split(" ", 1)
            refs[ref] = sha
    return lines[0][len("# backup "):], refs


def same_path(a, b):
    return os.path.normcase(os.path.realpath(a)) == os.path.normcase(os.path.realpath(b))


def remote_refs(url):
    """{ref: sha} of the remote's heads and tags (peeled ^{} lines dropped), None if ls-remote failed."""
    r = sh(["git", "ls-remote", url, "refs/heads/*", "refs/tags/*"])
    if r.returncode:
        print("ls-remote failed: %s" % r.stderr.strip()[-300:])
        return None
    return {ref: sha for sha, ref in (l.split("\t", 1) for l in r.stdout.splitlines()
                                      if l and not l.endswith("^{}"))}


def remote_head(url):
    """The ref the remote's HEAD points at, "" if it reports none, None if ls-remote failed."""
    r = sh(["git", "ls-remote", "--symref", url, "HEAD"])
    if r.returncode:
        return None
    for l in r.stdout.splitlines():
        if l.startswith("ref: ") and l.endswith("	HEAD"):
            return l[len("ref: "):-len("	HEAD")]
    return ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mirror")
    ap.add_argument("work")
    ap.add_argument("url")
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--delete-removed", action="store_true")
    ap.add_argument("--main-ref", default=None,
                    help="the default branch (default: the remote's HEAD; must match it): pushed alone, "
                         "last, only if nothing else was rejected")
    a = ap.parse_args()

    backup, work = local_refs(a.mirror), local_refs(a.work)
    if not backup or work is None:
        print("cannot read refs from %s" % (a.mirror if not backup else a.work))
        return 2
    snapshot = read_snapshot(a.work)
    if snapshot is None:
        print("no %s in %s: make the copy with `prepare` (leased_push.py prepare <backup.git> <work.git>)"
              % (SNAPSHOT, a.work))
        return 2
    snap_path, snap = snapshot
    if not same_path(snap_path, a.mirror):
        print("this copy was made from another backup (%s), not %s" % (snap_path, a.mirror))
        return 2
    stale = sorted(ref for ref in set(snap) | set(backup) if snap.get(ref) != backup.get(ref))
    if stale:
        for ref in stale:
            print("STALE " + ref)
        print("the backup changed after the copy was made: nothing pushed. Never fetch into the backup; "
              "make a NEW backup from the remote (Step 1) and redo Steps 2-3 from it")
        return 2
    ref_map = read_ref_map(a.work)
    if ref_map is None:
        print("no filter-repo/ref-map in %s: it must be a filter-repo run on a copy made with `prepare`" % a.work)
        return 2
    stale = sorted(ref for ref, (old, _) in ref_map.items() if ref in snap and old != snap[ref])
    if stale:
        for ref in stale:
            print("STALE " + ref)
        print("the rewrite was not made from this backup: move work.git aside, run prepare again, re-run filter-repo")
        return 2

    remote = remote_refs(a.url)
    if remote is None:
        return 2
    head = remote_head(a.url)
    if head is None:
        print("ls-remote --symref HEAD failed")
        return 2
    if a.main_ref and head and a.main_ref != head:
        print("--main-ref %s differs from the remote's default branch %s" % (a.main_ref, head))
        return 2
    if not (a.main_ref or head):
        print("the remote reports no default branch (HEAD): pass --main-ref <refs/heads/...>")
        return 2
    main_ref = a.main_ref or head
    if main_ref not in work:
        print("default branch %s is not in the rewritten copy %s" % (main_ref, a.work))
        return 2
    print("default branch: %s" % main_ref)

    done, todo, moved = [], [], []
    for ref, new in work.items():
        cur, old = remote.get(ref), snap.get(ref)
        if cur == new:
            done.append(ref)
        elif cur == old:
            todo.append(ref)
        else:
            moved.append(ref)
    # R4-01: "deleted by the rewrite" comes from the snapshot taken when the copy was made,
    # never from the live backup (a ref added there later would look deleted).
    removed = sorted(ref for ref in snap if ref not in work)
    to_delete = [ref for ref in removed if remote.get(ref) == snap[ref]]
    moved += [ref for ref in removed if remote.get(ref) not in (None, snap[ref])]
    # The backup is a mirror: a branch or tag on the remote that it does not have was
    # created after the backup, and may carry pre-purge history. Treat it as moved.
    moved += sorted(set(remote) - set(work) - set(snap))
    print("refs: %d to push, %d already done, %d moved since backup, %d deleted by the rewrite "
          "(%d still on remote)" % (len(todo), len(done), len(moved), len(removed), len(to_delete)))
    if moved:
        for ref in sorted(moved):
            print("MOVED " + ref)
        print(MOVED_HELP)
        return 3
    if to_delete and not a.delete_removed:
        for ref in to_delete:
            print("DELETED-BY-REWRITE " + ref)
        print("nothing pushed: these remote refs still hold purged data; re-run with --delete-removed")
        return 4

    hook = os.environ.get("LEASED_PUSH_TEST_BEFORE_PUSH")   # test seam: a Python script run between check and push
    if hook:
        subprocess.run([sys.executable, "-I", hook], check=True)

    leases = {ref: snap.get(ref, "") for ref in todo}
    leases.update({ref: snap[ref] for ref in to_delete})
    others = [(ref, ref) for ref in todo if ref != main_ref] + [("", ref) for ref in to_delete]
    flags, rejected, held, accepted = {}, [], [], {}
    for i in range(0, len(others), a.batch):
        push(a.work, a.url, others[i:i + a.batch], leases, a.dry_run, flags, rejected,
             "batch %d" % (i // a.batch + 1), accepted)
    if main_ref in todo:
        if rejected:
            held.append(main_ref)
        else:
            push(a.work, a.url, [(main_ref, main_ref)], leases, a.dry_run, flags, rejected, "main", accepted)
    print("flags: %s" % " ".join("%s=%d" % kv for kv in sorted(flags.items())))
    for l in rejected:
        print("REJECTED " + l)
    for ref in held:
        print("HELD %s (pushed only when every other ref succeeded)" % ref)
    print("rejected: %d; held: %d; deleted: %d" % (len(rejected), len(held), flags.get("-", 0)))
    if not a.dry_run:
        # G1-14: the pre-push check cannot see a push that lands while ours run. Look again.
        after = remote_refs(a.url)
        if after is None:                      # the re-check could not run: never report success
            return 1 if (rejected or held) else 2
        # created during the push: not in the copy, and not a deletion of ours the remote rejected
        late = set(after) - set(work) - (set(to_delete) - set(accepted))
        late |= {ref for ref, f in accepted.items()
                 if after.get(ref) != (None if f == "-" else work.get(ref))}   # overwritten after ours
        if late:
            for ref in sorted(late):
                print("MOVED " + ref)
            print(MOVED_AFTER_HELP)
            return 3
    return 1 if (rejected or held) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="backslashreplace")
    sys.exit(prepare(sys.argv[2:]) if sys.argv[1:2] == ["prepare"] else main())
