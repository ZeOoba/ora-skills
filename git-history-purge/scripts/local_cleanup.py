"""Remove purged ("old") history from a local checkout, then prove it at object level (SKILL.md Step 6).

  python -I local_cleanup.py changed <purged.git> <backup.git> [<backup2.git> ...] --out <old-commits.txt>
  python -I local_cleanup.py plan <repo> <old-commits.txt> --out <plan.json> [--min-age-hours 24] [--include-locked]
  python -I local_cleanup.py archive <repo> <plan.json> <archive-dir> --exclusive [--quiet-seconds 60]
                                     [--include-locked]
  python -I local_cleanup.py gc <repo> <old-commits.txt> <archive-dir> --exclusive [--quiet-seconds 60]
                                [--prune-floor 1.hour.ago]
  python -I local_cleanup.py overlap <repo> <old-commits.txt>

Every path argument is resolved against the current directory before use.

archive and gc are EXCLUSIVE MAINTENANCE: they do not try to be safe against other writers. They refuse
unless --exclusive is passed (the operator's statement that every session, IDE and scheduled job using
this checkout and its worktrees is stopped), no *.lock file exists in the common dir or any worktree git
dir, no rebase/merge/cherry-pick/revert/bisect is in progress, and two full-state snapshots taken
--quiet-seconds apart are identical. A snapshot covers every ref (all namespaces, every worktree's
per-worktree refs and HEAD/ORIG_HEAD/FETCH_HEAD/MERGE_HEAD/... files), every reflog file (sha256),
every index (size + sha256), every worktree's `git status --porcelain=v2` (with each listed file's
size and mtime) and the worktree list. Every change they make is checked against a snapshot afterwards;
anything they did not make is reported loudly with the safety bundle to recover from.

"Old history" = reaches a commit the purge CHANGED or DROPPED: every commit reachable from any ref of
any backup, minus every commit reachable from any ref of the purged copy. A clean first commit keeps
its SHA through filter-repo, so branches sharing only that root are NOT old; an orphan branch is not
old either. Several backups: a second one is made when someone pushed after the first (never fetch
into an existing backup); `changed` takes their union.

changed  writes the sorted old set; exit 1 if it is empty (refuse to guess). Also writes
         <out>.objects: the changed/dropped NON-commit objects (blobs, trees, tag objects reachable
         from the backups minus those reachable from the purged copy); plan, gc and overlap read it
         when it sits next to the old-commits file.
plan     (read-only) every ref in every namespace (annotated tags peeled; a ref whose object or
         peeled object is in <old>.objects counts as old), every stash entry, every linked
         worktree. Linked worktrees on old history are skipped (with their branch) when locked
         (unless --include-locked), missing/prunable, or dirty with a change newer than
         --min-age-hours. A main worktree on old history is a BLOCKER (re-point it first, Step 6.2).
         Records the full-state snapshot. Exit 0 if every old item is planned and there is no
         blocker, 1 if not, 4 if the checkout changed while planning.
archive  quiet gate, then refuses (exit 4) unless the live snapshot equals the plan's. Writes the
         SAFETY BUNDLE <archive>/safety.bundle: every ref, plus temp refs (refs/purge-archive/obj/<sha>)
         for every object named by any reflog entry (old and new values, every reflog of every
         worktree), every worktree's per-worktree refs and HEAD/ORIG_HEAD/FETCH_HEAD/... files; then
         verifies it and its heads. Saves each planned worktree's staged-only content (index differs
         from both HEAD and the file). Moves each planned worktree folder intact (ignored files
         included) to <archive>/dirs/ with os.rename only (the archive dir must be on the same volume;
         refused up front otherwise), prunes, and removes the planned refs in ONE leased update-ref
         transaction. A snapshot check runs before the first move, after the moves, after the prune
         and at the end. Nothing is deleted.
gc       quiet gate; needs the archive's safety bundle (`git bundle verify` must pass, and every
         entry of each reflog it edits must be in the bundle). Deletes ONLY the reflog entries (every
         reflog of every worktree, refs/stash included) whose new value reaches an old commit or is a
         listed old object, or whose previous value still would after the edit; highest index first
         (`reflog delete --rewrite`); every other entry is kept. Pins every linked worktree's
         per-worktree refs with temp refs (refs/purge-keep/<n>), runs gc --prune=<floor> (reflog
         expiry and worktree pruning off), removes the pins, then checks that every ref still
         resolves and nothing else changed. The floor (default 1.hour.ago) protects fresh objects.
overlap  objects in the object store that are in the old set (commits) or, when <old>.objects
         exists, in that set (blobs, trees, tags): exit 0 when 0, else 1. Names each reflog that
         still holds old entries (including entries whose previous value is old).

Prints counts and ref names only, never file contents.
Exit codes: 0 ok, 1 work left/found (or gc's git step failed), 2 bad input (nothing changed),
3 archive stopped at a failed move (nothing else moved, no ref removed), 4 not quiet / changed since
the plan or the archive (nothing changed), 5 a change this run did not make was found after it started
(recover from the safety bundle it names).
"""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
NULL_RE = re.compile(r"^0+$")
TEMP_NS = "refs/purge-archive/"
PIN_NS = "refs/purge-keep/"
MAIN = "."                                  # snapshot id of the main worktree (never a worktree admin id)
PSEUDO = ("HEAD", "ORIG_HEAD", "FETCH_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REBASE_HEAD", "REVERT_HEAD",
          "BISECT_HEAD", "AUTO_MERGE")
BUSY = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "sequencer")
EXIT_PARTIAL, EXIT_NOT_QUIET, EXIT_UNPLANNED = 3, 4, 5


class Refuse(Exception):
    """Bad input: exit 2, nothing changed."""


class NotQuiet(Exception):
    """Not exclusive / not quiet / changed since the plan: exit 4, nothing changed."""

    def __init__(self, msg, keys=()):
        Exception.__init__(self, msg)
        self.keys = list(keys)


def git(repo, *args, check=True, binary=False, stdin=None):
    r = subprocess.run(["git", "--no-optional-locks", "-C", repo, "-c", "core.quotepath=false"] + list(args),
                       capture_output=True,
                       input=stdin if binary or stdin is None else stdin.encode("utf-8", "surrogateescape"))
    if check and r.returncode != 0:
        raise subprocess.CalledProcessError(r.returncode, ["git"] + list(args)[:2], r.stdout,
                                            r.stderr.decode("utf-8", "replace"))
    if binary:
        return r
    r.stdout = r.stdout.decode("utf-8", "surrogateescape")
    r.stderr = r.stderr.decode("utf-8", "replace")
    return r


def out(repo, *args):
    return git(repo, *args).stdout


def norm(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def require_repo(path):
    if not os.path.isdir(path) or git(path, "rev-parse", "--git-dir", check=False).returncode != 0:
        raise Refuse("not a git repository: %s" % path)
    r = git(path, "config", "--get", "extensions.refstorage", check=False)
    if r.stdout.strip().lower() == "reftable":
        raise Refuse("reftable ref storage is not supported (the snapshot reads ref and reflog files)")


def rev_list_all(repo):
    return set(out(repo, "rev-list", "--all").split())


def objects_all(repo):
    """Every object (commit, tree, blob, tag) reachable from any ref."""
    return {l.split(" ", 1)[0] for l in out(repo, "rev-list", "--objects", "--all").splitlines() if l}


def read_shas(path, what, allow_empty):
    with open(path, encoding="ascii", errors="replace") as fh:
        shas = [l.strip() for l in fh if l.strip()]
    bad = [s for s in shas if not SHA_RE.match(s)]
    if bad or (not shas and not allow_empty):
        raise Refuse("%s file is empty or has %d malformed line(s)" % (what, len(bad)))
    return set(shas)


def read_old(path):
    if not os.path.isfile(path):
        raise Refuse("old-commits file not found: %s" % path)
    return read_shas(path, "old-commits", False)


def read_old_objects(old_path):
    """<old-commits>.objects (changed/dropped blobs, trees, tags) or an empty set when absent."""
    path = old_path + ".objects"
    return read_shas(path, "old-objects", True) if os.path.isfile(path) else set()


def wait_quiet(seconds):
    """The quiet window between the two gate snapshots (a seam for tests)."""
    time.sleep(seconds)


def device_of(path):
    """Volume of path, or of its nearest existing ancestor (a seam for tests)."""
    path = os.path.abspath(path)
    while not os.path.exists(path) and os.path.dirname(path) != path:
        path = os.path.dirname(path)
    return os.stat(path).st_dev


# ---------------------------------------------------------------- helpers shared by plan / archive

def index_only(xy):
    """Index differs from BOTH HEAD and the work tree (MM, AM, RM, MD, AD ...)."""
    return len(xy) == 2 and xy[0] not in " ?!" and xy[1] != " "


def missing_heads(expected, listed_text):
    """Refs in `expected` (name -> sha) that `git bundle list-heads` output lacks or lists at another SHA."""
    listed = {}
    for line in listed_text.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            listed[parts[1].strip()] = parts[0]
    return sorted(n for n, sha in expected.items() if listed.get(n) != sha)


class OldTest:
    """Called with a commit: does it reach an old commit? .obj(sha): is it a listed old non-commit object?"""

    def __init__(self, repo, old, objs=frozenset()):
        self.repo, self.old, self.objs, self.cache = repo, old, objs, {}

    def __call__(self, sha):
        if sha not in self.cache:
            r = git(self.repo, "rev-list", sha, check=False)
            self.cache[sha] = r.returncode == 0 and not self.old.isdisjoint(r.stdout.split())
        return self.cache[sha]

    def obj(self, sha):
        return sha in self.objs

    def any(self, sha):
        """A reflog value: reaches an old commit or is a listed old object (never the null id)."""
        return bool(sha) and not NULL_RE.match(sha) and (self.obj(sha) or self(sha))

    def ref(self, sha, commit, peeled):
        """A ref (object sha, peeled commit or None, peeled object) is old history."""
        if commit:
            return self(commit) or self.obj(sha)
        return self.obj(sha) or self.obj(peeled)


def ref_kind(name):
    if name == "refs/stash":
        return "stash"
    parts = name.split("/")
    if len(parts) >= 3 and parts[1] in ("heads", "remotes", "tags", "notes", "original"):
        return parts[1]
    return "other"


def list_refs(repo):
    """[(name, object sha, peeled commit or None, symref target or '', peeled object sha)]."""
    fmt = "%(refname)%00%(objectname)%00%(objecttype)%00%(symref)%00%(*objectname)"
    rows = []
    for line in out(repo, "for-each-ref", "--format=" + fmt).splitlines():
        if not line:
            continue
        name, sha, typ, symref, peeled = line.split("\0")
        commit, peeled = (sha if typ == "commit" else None), (peeled or sha)
        if typ == "tag":
            r = git(repo, "rev-parse", "--verify", "-q", sha + "^{}", check=False)
            peeled = r.stdout.strip() if r.returncode == 0 else peeled
            r = git(repo, "rev-parse", "--verify", "-q", sha + "^{commit}", check=False)
            commit = r.stdout.strip() if r.returncode == 0 else None
        rows.append((name, sha, commit, symref, peeled))
    return rows


def stash_entries(repo):
    if git(repo, "rev-parse", "--verify", "-q", "refs/stash", check=False).returncode != 0:
        return []
    return out(repo, "reflog", "show", "--format=%H", "refs/stash").split()


def common_dir(repo):
    d = out(repo, "rev-parse", "--git-common-dir").strip()
    return os.path.abspath(d if os.path.isabs(d) else os.path.join(repo, d))


def worktree_ids(repo):
    """norm(worktree path) -> admin id under <common>/worktrees/."""
    base = os.path.join(common_dir(repo), "worktrees")
    ids = {}
    if os.path.isdir(base):
        for wid in os.listdir(base):
            try:
                with open(os.path.join(base, wid, "gitdir"), encoding="utf-8") as fh:
                    ids[norm(os.path.dirname(fh.read().strip()))] = wid
            except OSError:
                continue
    return ids


def list_worktrees(repo):
    blocks, cur = [], None
    for line in out(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            cur = {"path": line[9:], "head": None, "branch": None, "detached": False, "bare": False,
                   "locked": False, "lock_reason": "", "prunable": False, "raw": []}
            blocks.append(cur)
        elif cur is None or not line:
            continue
        elif line.startswith("HEAD "):
            cur["head"] = line[5:]
        elif line.startswith("branch "):
            cur["branch"] = line[7:]
        elif line == "detached":
            cur["detached"] = True
        elif line == "bare":
            cur["bare"] = True
        elif line.startswith("locked"):
            cur["locked"], cur["lock_reason"] = True, line[7:]
        elif line.startswith("prunable"):
            cur["prunable"] = True
        if cur is not None and line:
            cur["raw"].append(line)
    ids = worktree_ids(repo)
    for i, w in enumerate(blocks):
        w["main"] = i == 0
        w["id"] = None if i == 0 else ids.get(norm(w["path"]), os.path.basename(w["path"]))
        w["raw"] = "\n".join(w["raw"])
    return blocks


def dirty_state(path):
    """[{status, path, mtime_ns or None}] from git status (untracked included, ignored excluded)."""
    raw = git(path, "status", "--porcelain=v1", "-uall", "-z").stdout.split("\0")
    entries, i = [], 0
    while i < len(raw):
        item = raw[i]
        i += 1
        if len(item) < 4:
            continue
        xy, rel = item[:2], item[3:]
        if xy[0] in "RC":
            i += 1                                       # skip the rename/copy source path
        full = os.path.join(path, rel)
        try:
            mtime = os.lstat(full).st_mtime_ns
        except (OSError, ValueError):
            mtime = None
        entries.append({"status": xy, "path": rel, "mtime_ns": mtime})
    return entries


def wt_snapshot(w):
    dirty = dirty_state(w["path"])
    times = [d["mtime_ns"] for d in dirty if d["mtime_ns"] is not None]
    return {"id": w["id"], "path": w["path"], "head": w["head"], "branch": w["branch"],
            "detached": w["detached"], "locked": w["locked"], "lock_reason": w["lock_reason"],
            "dirty_count": len(dirty), "dirty": dirty,
            "index_only": [d["path"] for d in dirty if index_only(d["status"])],
            "newest_change": max(times) / 1e9 if times else None}


# ---------------------------------------------------------------- full-state snapshot

def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def walk_files(base, skip_top=()):
    """Relative '/'-separated paths of every file under base (sorted)."""
    found = []
    for root, dirs, files in os.walk(base):
        if root == base:
            dirs[:] = [d for d in dirs if d not in skip_top]
        for f in files:
            found.append(os.path.relpath(os.path.join(root, f), base).replace(os.sep, "/"))
    return sorted(found)


def git_dirs(repo):
    """[(snapshot id, git dir, worktree folder or None)]: the main worktree first, then every admin dir."""
    common = common_dir(repo)
    wts = list_worktrees(repo)
    dirs = [(MAIN, common, None if wts[0]["bare"] else wts[0]["path"])]
    base = os.path.join(common, "worktrees")
    if os.path.isdir(base):
        for wid in sorted(os.listdir(base)):
            g = os.path.join(base, wid)
            path = None
            try:
                with open(os.path.join(g, "gitdir"), encoding="utf-8") as fh:
                    path = os.path.dirname(fh.read().strip())
            except OSError:
                pass
            dirs.append((wid, g, path))
    return dirs


def status_files(path):
    """{relpath: status record (without the path) + size + mtime} from porcelain v2, untracked included."""
    r = git(path, "status", "--porcelain=v2", "-z", "--untracked-files=all", check=False)
    if r.returncode != 0:
        return {"": "status failed (exit %d)" % r.returncode}
    parts, res, i = r.stdout.split("\0"), {}, 0
    while i < len(parts):
        rec = parts[i]
        i += 1
        n = {"1": 8, "2": 9, "u": 10, "?": 1, "!": 1}.get(rec[:1])
        fields = rec.split(" ", n) if n else []
        if len(fields) <= (n or 0):
            continue
        rel, meta = fields[n], " ".join(fields[:n])
        if rec[0] == "2" and i < len(parts):
            meta += " from " + parts[i]
            i += 1
        try:
            st = os.lstat(os.path.join(path, rel))
            meta += " size=%d mtime=%d" % (st.st_size, st.st_mtime_ns)
        except (OSError, ValueError):
            meta += " absent"
        res[rel] = meta
    return res


def pseudo_value(path):
    with open(path, "rb") as fh:
        data = fh.read()
    text = data.decode("utf-8", "replace").strip()
    return text if len(text) <= 120 and "\n" not in text else "sha256:" + hashlib.sha256(data).hexdigest()


def snapshot(repo):
    """Deterministic, JSON-able {key: value} of everything another session could change. See module doc."""
    s = {}
    for w in list_worktrees(repo):
        s["wtlist|" + norm(w["path"])] = w["raw"]
    for line in out(repo, "for-each-ref", "--format=%(refname)%00%(objectname)%00%(symref)").splitlines():
        if line:
            name, sha, sym = line.split("\0")
            s["ref|" + name] = sha + (" -> " + sym if sym else "")
    for wid, g, path in git_dirs(repo):
        p = "wt|%s|" % wid
        if wid == MAIN:
            s[p + "path"] = path or ""
        else:                                               # the main worktree's own refs are listed above
            for rel in walk_files(os.path.join(g, "refs")):
                try:
                    s[p + "ref|refs/" + rel] = pseudo_value(os.path.join(g, "refs", rel))
                except OSError:
                    s[p + "ref|refs/" + rel] = "unreadable"
        for name in PSEUDO:
            f = os.path.join(g, name)
            if os.path.isfile(f):
                s[p + "pseudo|" + name] = pseudo_value(f)
        for rel in walk_files(os.path.join(g, "logs")):
            s[p + "reflog|" + rel] = sha256_file(os.path.join(g, "logs", rel))
        idx = os.path.join(g, "index")
        if os.path.isfile(idx):
            s[p + "index"] = "%d %s" % (os.path.getsize(idx), sha256_file(idx))
        for rel in walk_files(g, skip_top=("worktrees",) if wid == MAIN else ()):
            if rel.endswith(".lock"):
                s[p + "lock|" + rel] = "present"
        for name in BUSY:
            if os.path.exists(os.path.join(g, name)):
                s[p + "busy|" + name] = "present"
        if path is None:
            continue
        if not os.path.isdir(path):
            s[p + "folder"] = "missing"
            continue
        s[p + "folder"] = "present"
        for rel, meta in status_files(path).items():
            s[p + "file|" + rel] = meta
    return s


def diff_keys(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))


def key_kind(k):
    """'ref', 'wtlist', or for 'wt|<id>|<kind>|...' keys the <kind> (ref, pseudo, reflog, index, lock ...)."""
    parts = k.split("|", 3)
    return parts[2] if parts[0] == "wt" and len(parts) > 2 else parts[0]


def show_keys(keys, limit=20):
    for k in keys[:limit]:
        print("  changed: %s" % k)
    if len(keys) > limit:
        print("  ... and %d more" % (len(keys) - limit))


def quiet_gate(repo, a):
    """--exclusive, no lock file, nothing in progress, two snapshots --quiet-seconds apart identical."""
    if not a.exclusive:
        raise NotQuiet("--exclusive not given: stop every session, IDE and scheduled job that uses this "
                       "checkout and its worktrees, then pass --exclusive")
    first = snapshot(repo)
    locks = [k for k in first if key_kind(k) == "lock"]
    if locks:
        raise NotQuiet("lock file(s) present: a git command is running (or crashed); find it", locks)
    busy = [k for k in first if key_kind(k) == "busy"]
    if busy:
        raise NotQuiet("a rebase, merge, cherry-pick, revert or bisect is in progress: finish or abort it", busy)
    wait_quiet(a.quiet_seconds)
    second = snapshot(repo)
    changed = diff_keys(first, second)
    if changed:
        raise NotQuiet("the checkout changed during the %g s quiet window: something is still writing; "
                       "find and stop it" % a.quiet_seconds, changed)
    return second


def unexpected(before, after, temp_ok=False, moved=(), moved_gone=False, removed=frozenset()):
    """Keys that differ between two snapshots in a way this run did not make.
    temp_ok: our temp refs may exist. moved: snapshot ids + paths of worktrees whose folder we moved
    (moved_gone: and whose admin dir was pruned). removed: keys we deleted on purpose."""
    ids = tuple("wt|%s|" % wid for wid, _p in moved)
    listed = {"wtlist|" + norm(p) for _w, p in moved}
    inside = tuple(norm(p) + os.sep for _w, p in moved)
    main_dir = before.get("wt|%s|path" % MAIN, "")
    bad = []
    for k in diff_keys(before, after):
        if temp_ok and k not in before and (k.startswith("ref|" + TEMP_NS) or
                                            k.startswith("wt|%s|reflog|%s" % (MAIN, TEMP_NS))):
            continue
        if inside and main_dir and k.startswith("wt|%s|file|" % MAIN) and k not in after and \
                (norm(os.path.join(main_dir, k.split("|", 3)[3])) + os.sep).startswith(inside):
            continue                                        # a moved worktree nested in the main folder
        if k.startswith(ids) or k in listed:
            if moved_gone and k not in after:
                continue
            rest = k.split("|", 2)[2] if k.startswith(ids) else ""
            if not moved_gone and (k in listed or rest == "folder" or rest.startswith("file|")):
                continue                                    # folder gone, lock released, now prunable
        if k in removed and k not in after:
            continue
        bad.append(k)
    return bad


def loud(stage, keys, bundle, extra=""):
    print("UNPLANNED CHANGE %s: %d item(s) changed that this run did not change. %s" % (stage, len(keys), extra))
    show_keys(keys)
    print("Recover from the safety bundle: %s  (git fetch <bundle> 'refs/*:refs/restored/*')" % bundle)
    return EXIT_UNPLANNED


# ---------------------------------------------------------------- reflogs

def reflog_files(repo):
    """[(name as `git reflog` addresses it from the main worktree, file path)] for every reflog."""
    common = common_dir(repo)
    rows = [(rel, os.path.join(common, "logs", rel)) for rel in walk_files(os.path.join(common, "logs"))]
    base = os.path.join(common, "worktrees")
    if os.path.isdir(base):
        for wid in sorted(os.listdir(base)):
            logs = os.path.join(base, wid, "logs")
            rows += [("worktrees/%s/%s" % (wid, rel), os.path.join(logs, rel)) for rel in walk_files(logs)]
    return rows


def read_reflog(path):
    """[(old, new)] newest first, so position i is what `git reflog delete <name>@{i}` addresses."""
    rows = []
    try:
        with open(path, "rb") as fh:
            for line in fh:
                parts = line.split(b" ", 2)
                if len(parts) == 3:
                    o, n = parts[0].decode("ascii", "replace"), parts[1].decode("ascii", "replace")
                    if SHA_RE.match(o) and SHA_RE.match(n):
                        rows.append((o, n))
    except OSError:
        return []
    return rows[::-1]


def reflog_deletions(entries, bad):
    """Indexes to delete, highest first: entries whose new value is bad, plus entries whose previous value
    is still bad once `--rewrite` has relinked the kept ones (R2-14). With no deletion there is no rewrite,
    so an entry whose recorded previous value is bad is deleted itself."""
    drop = {i for i, (_o, n) in enumerate(entries) if bad(n)}
    while True:
        kept = [i for i in range(len(entries)) if i not in drop]
        more = set()
        for j, i in enumerate(kept):
            if drop:
                prev = entries[kept[j + 1]][1] if j + 1 < len(kept) else None
            else:
                prev = entries[i][0]
            if prev and bad(prev):
                more.add(i)
        if not more:
            return sorted(drop, reverse=True)
        drop |= more


# ---------------------------------------------------------------- modes

def cmd_changed(a):
    require_repo(a.purged)
    for b in a.backups:
        require_repo(b)
    backup = set()
    for b in a.backups:
        backup |= rev_list_all(b)
    old = sorted(backup - rev_list_all(a.purged))
    backup_objs = set()
    for b in a.backups:
        backup_objs |= objects_all(b)
    objs = sorted(backup_objs - objects_all(a.purged) - backup)
    with open(a.out, "w", encoding="ascii", newline="\n") as fh:
        fh.write("".join(s + "\n" for s in old))
    with open(a.out + ".objects", "w", encoding="ascii", newline="\n") as fh:
        fh.write("".join(s + "\n" for s in objs))
    print("changed or dropped commits: %d (backups: %d)" % (len(old), len(a.backups)))
    print("changed or dropped blobs/trees/tags: %d (%s.objects)" % (len(objs), os.path.basename(a.out)))
    if not old:
        print("EMPTY: no commit differs; wrong purged copy or backup? refusing to guess")
        return 1
    return 0


def build_plan(repo, old, min_age_hours, include_locked, objs=frozenset()):
    is_old = OldTest(repo, old, objs)
    plan = {"repo": os.path.abspath(repo), "created": time.time(), "refs": [], "symrefs": [], "stash": [],
            "worktrees": [], "skipped": [], "blockers": [], "main_head": None, "main_branch": None}
    skip_branches = {}
    cutoff = time.time() - min_age_hours * 3600
    for w in list_worktrees(repo):
        if w["main"]:
            plan["main_head"], plan["main_branch"] = w["head"], w["branch"]
            if not w["bare"] and w["head"] and is_old(w["head"]):
                plan["blockers"].append({"item": w["path"], "reason": "main worktree HEAD is on old history: "
                                         "re-point it first (SKILL.md Step 6 item 2)"})
                if w["branch"]:
                    skip_branches[w["branch"]] = "checked out in the main worktree (BLOCKER)"
            continue
        if not w["head"] or not is_old(w["head"]):
            continue
        reason = None
        if w["prunable"] or not os.path.isdir(w["path"]):
            reason = "prunable or missing directory"
        elif w["locked"] and not include_locked:
            reason = "locked (%s); pass --include-locked on its own yes" % (w["lock_reason"] or "no reason")
        snap = None
        if reason is None:
            snap = wt_snapshot(w)
            if snap["dirty_count"] and snap["newest_change"] and snap["newest_change"] > cutoff:
                reason = "dirty with a recent change (newer than %g h): someone may be using it" % min_age_hours
        if reason:
            plan["skipped"].append({"item": w["path"], "reason": reason})
            if w["branch"]:
                skip_branches[w["branch"]] = reason
            continue
        plan["worktrees"].append(snap)
    by_name = {}
    rows = list_refs(repo)
    for name, sha, commit, symref, peeled in rows:
        if symref:
            continue
        by_name[name] = sha
        if not is_old.ref(sha, commit, peeled):
            continue
        if name in skip_branches:
            plan["skipped"].append({"item": name, "reason": skip_branches[name]})
            continue
        plan["refs"].append({"name": name, "sha": sha, "commit": commit, "kind": ref_kind(name)})
    planned = {r["name"] for r in plan["refs"]}
    for name, sha, commit, symref, _p in rows:
        if symref and symref in planned:
            plan["symrefs"].append({"name": name, "target": symref})
    entries = stash_entries(repo)
    if any(is_old(s) for s in entries):
        plan["stash"] = [{"index": i, "sha": s, "old": is_old(s)} for i, s in enumerate(entries)]
        if "refs/stash" not in planned and "refs/stash" in by_name:
            plan["refs"].append({"name": "refs/stash", "sha": by_name["refs/stash"],
                                 "commit": by_name["refs/stash"], "kind": "stash"})
    return plan


def cmd_plan(a):
    require_repo(a.repo)
    old = read_old(a.old_commits)
    before = snapshot(a.repo)
    plan = build_plan(a.repo, old, a.min_age_hours, a.include_locked, read_old_objects(a.old_commits))
    plan["snapshot"] = snapshot(a.repo)
    changed = diff_keys(before, plan["snapshot"])
    if changed:
        raise NotQuiet("the checkout changed while planning: something is writing; stop it, then plan again",
                       changed)
    plan["old_commits"] = os.path.abspath(a.old_commits)
    plan["include_locked"] = a.include_locked
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(plan, fh, indent=1)
    kinds = {}
    for r in plan["refs"]:
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print("refs to archive: %d (%s)" % (len(plan["refs"]), ", ".join("%s %d" % kv for kv in sorted(kinds.items()))))
    print("stash entries: %d (%d on old history)" % (len(plan["stash"]), sum(e["old"] for e in plan["stash"])))
    print("symrefs to remove with their target: %d" % len(plan["symrefs"]))
    print("worktrees to archive: %d (dirty %d, with staged-only files %d)" % (
        len(plan["worktrees"]), sum(1 for w in plan["worktrees"] if w["dirty_count"]),
        sum(1 for w in plan["worktrees"] if w["index_only"])))
    print("skipped: %d" % len(plan["skipped"]))
    for s in plan["skipped"]:
        print("  SKIP %s: %s" % (s["item"], s["reason"]))
    for b in plan["blockers"]:
        print("BLOCKER %s: %s" % (b["item"], b["reason"]))
    return 1 if plan["skipped"] or plan["blockers"] else 0


def safe_join(base, rel):
    full = os.path.normpath(os.path.join(base, rel))
    if os.path.commonpath([os.path.abspath(base), os.path.abspath(full)]) != os.path.abspath(base):
        raise ValueError("path escapes the archive: %s" % rel)
    return full


def save_staged(wt, dest):
    """Write each index-only path's staged blob(s) under dest. Returns the count of files written."""
    n = 0
    for rel in wt["index_only"]:
        listing = git(wt["path"], "ls-files", "-s", "-z", "--", rel).stdout.split("\0")
        for entry in filter(None, listing):
            meta, path = entry.split("\t", 1)
            mode, sha, stage = meta.split()
            if mode == "160000":
                continue                                    # submodule: a commit, not content
            target = safe_join(dest, path if stage == "0" else "%s.stage%s" % (path, stage))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            data = git(wt["path"], "cat-file", "blob", sha, binary=True).stdout
            with open(target, "wb") as fh:
                fh.write(data)
            n += 1
    return n


def safety_sources(repo):
    """sha -> [where it is named] for everything only reflogs, per-worktree refs or pseudo-refs hold."""
    src = {}
    for name, path in reflog_files(repo):
        for i, (o, n) in enumerate(read_reflog(path)):
            for sha in (o, n):
                if not NULL_RE.match(sha):
                    src.setdefault(sha, []).append("%s@{%d}" % (name, i))
    for wid, g, _path in git_dirs(repo):
        if wid != MAIN:
            for rel in walk_files(os.path.join(g, "refs")):
                try:
                    sha = pseudo_value(os.path.join(g, "refs", rel))
                except OSError:
                    continue
                if SHA_RE.match(sha):
                    src.setdefault(sha, []).append("worktree %s refs/%s" % (wid, rel))
        for name in PSEUDO:
            try:
                with open(os.path.join(g, name), encoding="utf-8", errors="replace") as fh:
                    for k, line in enumerate(fh):
                        sha = line.split("\t", 1)[0].strip()
                        if SHA_RE.match(sha):
                            src.setdefault(sha, []).append("worktree %s %s line %d" % (wid, name, k))
            except OSError:
                continue
    return src


def object_types(repo, shas):
    if not shas:
        return {}
    listing = git(repo, "cat-file", "--batch-check=%(objectname) %(objecttype)",
                  stdin="".join(s + "\n" for s in shas), check=False).stdout.split("\n")
    types = {}
    for line in listing:
        parts = line.split()
        if len(parts) == 2 and parts[1] != "missing":
            types[parts[0]] = parts[1]
    return types


def live_refs(repo):
    return {name: sha for name, sha, _c, symref, _p in list_refs(repo) if not symref}


def write_safety_bundle(repo, archive_dir):
    """Temp refs + bundle of every ref; returns (bundle path, temp {name: sha}, manifest rows).
    Raises Refuse with every temp ref dropped again on any failure."""
    held = set(live_refs(repo).values())
    src = safety_sources(repo)
    types = object_types(repo, sorted(s for s in src if s not in held))
    temp = {"%sobj/%s" % (TEMP_NS, sha): sha for sha in sorted(types)}
    rows = [("keep", name, sha, "", "; ".join(src[sha][:3]) + (" (+%d)" % (len(src[sha]) - 3)
                                                              if len(src[sha]) > 3 else ""))
            for name, sha in sorted(temp.items())]
    if temp:
        txt = "start\n" + "".join("create %s %s\n" % kv for kv in sorted(temp.items())) + "commit\n"
        if git(repo, "update-ref", "--stdin", stdin=txt, check=False).returncode != 0:
            raise Refuse("could not create temp refs under %s (name taken?); nothing changed" % TEMP_NS)
    bundle = os.path.join(archive_dir, "safety.bundle")
    try:
        expected = live_refs(repo)
        r = git(repo, "bundle", "create", bundle, "--stdin", stdin="".join(n + "\n" for n in sorted(expected)),
                check=False)
        if r.returncode != 0:
            raise Refuse("git bundle create failed; nothing changed")
        if git(repo, "bundle", "verify", bundle, check=False).returncode != 0:
            raise Refuse("git bundle verify failed; nothing changed")
        lacking = missing_heads(expected, out(repo, "bundle", "list-heads", bundle))
        if lacking:
            raise Refuse("bundle lacks %d ref(s) (%s); nothing changed" % (len(lacking), ", ".join(lacking[:5])))
    except Refuse:
        drop_refs(repo, temp)
        raise
    return bundle, temp, expected, rows


def drop_refs(repo, refs):
    if refs:
        txt = "start\n" + "".join("delete %s %s\n" % kv for kv in sorted(refs.items())) + "commit\n"
        return git(repo, "update-ref", "--stdin", stdin=txt, check=False).returncode == 0
    return True


def write_manifest(archive_dir, rows):
    with open(os.path.join(archive_dir, "manifest.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join("\t".join(row) + "\n" for row in rows))


def manifest_bundle(archive_dir):
    path = os.path.join(archive_dir, "manifest.tsv")
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split("\t")
                if parts[0] == "bundle" and len(parts) == 5:
                    return parts[4]
    except OSError:
        pass
    raise Refuse("no safety bundle recorded in %s: run archive first" % path)


def cmd_archive(a):
    require_repo(a.repo)
    repo = a.repo
    if not a.exclusive:
        quiet_gate(repo, a)                                          # raises with the --exclusive message
    if os.path.exists(a.archive_dir):
        raise Refuse("archive dir exists (never reused): %s" % a.archive_dir)
    with open(a.plan, encoding="utf-8") as fh:
        plan = json.load(fh)
    if "snapshot" not in plan:
        raise Refuse("the plan has no snapshot (made by an older local_cleanup.py): plan again")
    if norm(plan.get("repo", "")) != norm(repo):
        raise Refuse("the plan is for another checkout: %s" % plan.get("repo"))
    if plan.get("blockers"):
        raise Refuse("plan has %d BLOCKER(s): re-point the main worktree, then plan again" % len(plan["blockers"]))
    wts = plan["worktrees"]
    locked = [w["path"] for w in wts if w["locked"]]
    if locked and not a.include_locked:
        raise Refuse("the plan includes %d locked worktree(s) (%s); pass --include-locked on its own yes"
                     % (len(locked), ", ".join(locked[:3])))
    planned_paths = {norm(w["path"]) for w in wts}
    for w in list_worktrees(repo):
        if norm(a.archive_dir).startswith(norm(w["path"]) + os.sep):
            raise Refuse("the archive dir is inside worktree %s; put it outside every checkout" % w["path"])
        if w["prunable"] and norm(w["path"]) not in planned_paths:
            raise Refuse("worktree %s is prunable and not in the plan: restore its folder or prune it "
                         "yourself first" % w["path"])
    if wts and len({device_of(a.archive_dir)} | {device_of(w["path"]) for w in wts}) != 1:
        raise Refuse("the archive dir is on another volume than a planned worktree: a move would copy; "
                     "put the archive dir on the same volume")
    snap = quiet_gate(repo, a)
    changed = diff_keys(plan["snapshot"], snap)
    if changed:
        raise NotQuiet("the checkout changed since the plan: plan again (and find who changed it)", changed)

    os.makedirs(a.archive_dir)
    bundle, temp, expected, keep_rows = write_safety_bundle(repo, a.archive_dir)
    manifest = [("kind", "id", "sha", "ref", "original_path"), ("bundle", "safety", "", "", bundle)] + keep_rows
    write_manifest(a.archive_dir, manifest)
    try:
        for w in wts:
            label = "%s-%s" % (w["id"], os.path.basename(os.path.normpath(w["path"])))
            save_staged(w, os.path.join(a.archive_dir, "staged-index", label))
            for rel in w["index_only"]:
                manifest.append(("staged", w["id"], "", "", os.path.join(w["path"], rel)))
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        drop_refs(repo, temp)
        raise Refuse("could not save staged-only content (%s); nothing moved" % type(exc).__name__)
    changed = unexpected(snap, snapshot(repo), temp_ok=True)
    if changed:
        drop_refs(repo, temp)
        raise NotQuiet("the checkout changed while the bundle was written: nothing moved; find the writer", changed)

    # move each planned worktree folder intact (os.rename only); stop at the first failure
    moved, failed = [], None
    for w in wts:
        label = "%s-%s" % (w["id"], os.path.basename(os.path.normpath(w["path"])))
        dest = os.path.join(a.archive_dir, "dirs", label)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if w["locked"] and git(repo, "worktree", "unlock", w["path"], check=False).returncode != 0:
            failed = (w, "could not unlock it")
            break
        try:
            os.rename(w["path"], dest)
        except OSError as exc:
            if w["locked"]:
                git(repo, "worktree", "lock", "--reason", w["lock_reason"] or "restored", w["path"], check=False)
            failed = (w, "move failed (%s)" % type(exc).__name__)
            break
        moved.append((w["id"], w["path"]))
        manifest.append(("worktree", w["id"], w["head"], w["branch"] or "(detached)", w["path"]))
    write_manifest(a.archive_dir, manifest)
    changed = unexpected(snap, snapshot(repo), temp_ok=True, moved=moved)
    if changed:
        return loud("after moving %d worktree folder(s)" % len(moved), changed, bundle,
                    "Nothing was pruned or removed; the moved folders are in %s (move them back to restore)."
                    % os.path.join(a.archive_dir, "dirs"))
    if moved:
        git(repo, "worktree", "prune", check=False)                   # result is checked just below
    changed = unexpected(snap, snapshot(repo), temp_ok=True, moved=moved, moved_gone=True)
    if changed:
        return loud("after the prune", changed, bundle, "No ref was removed.")

    removed = set()
    if failed:
        drop_refs(repo, temp)
        w, why = failed
        print("STOPPED: %s: %s. That worktree and its admin dir are untouched; no ref was removed; "
              "%d worktree(s) before it were moved and pruned. Fix the cause, then plan again."
              % (w["path"], why, len(moved)))
        rc = EXIT_PARTIAL
    else:
        txt = ["start"]
        for s in plan["symrefs"]:
            txt += ["option no-deref", "delete %s" % s["name"]]
        for r in plan["refs"]:
            txt.append("delete %s %s" % (r["name"], r["sha"]))
        for n in sorted(temp):
            txt.append("delete %s %s" % (n, temp[n]))
        txt.append("commit")
        if git(repo, "update-ref", "--stdin", stdin="\n".join(txt) + "\n", check=False).returncode != 0:
            write_manifest(a.archive_dir, manifest)
            return loud("at ref removal", ["REF REMOVAL FAILED: a planned ref moved during the run; no ref "
                                           "was removed"], bundle)
        for r in plan["refs"]:
            manifest.append(("ref:" + r["kind"], r["name"], r["sha"], r["name"], ""))
            removed |= {"ref|" + r["name"], "wt|%s|reflog|%s" % (MAIN, r["name"])}
        for s in plan["symrefs"]:
            manifest.append(("symref", s["name"], "", s["target"], ""))
            removed |= {"ref|" + s["name"], "wt|%s|reflog|%s" % (MAIN, s["name"])}
        rc = 0
    write_manifest(a.archive_dir, manifest)
    changed = unexpected(snap, snapshot(repo), moved=moved, moved_gone=True, removed=removed)
    if changed:
        return loud("after the run", changed, bundle)
    print("safety bundle: %s (%d refs incl. %d temp)" % (bundle, len(expected), len(temp)))
    print("refs removed: %d, symrefs removed: %d, stash entries archived: %d" % (
        0 if failed else len(plan["refs"]), 0 if failed else len(plan["symrefs"]),
        0 if failed else len(plan["stash"])))
    print("worktrees moved: %d (staged-only files saved: %d)" % (
        len(moved), sum(len(w["index_only"]) for w in wts)))
    print("verified: nothing changed except what this run did")
    return rc


def uncovered(repo, bundle, shas):
    """Objects among shas (present in the repo) that the bundle does not hold."""
    heads = {l.split(" ", 1)[0] for l in out(repo, "bundle", "list-heads", bundle).splitlines() if l}
    types = object_types(repo, sorted(s for s in shas if s not in heads))
    lost = [s for s, t in types.items() if t != "commit"]
    commits = [s for s, t in types.items() if t == "commit"]
    if commits:
        head_types = object_types(repo, sorted(heads))
        neg = [h for h, t in head_types.items() if t in ("commit", "tag")]
        r = git(repo, "rev-list", "--ignore-missing", "--stdin",
                stdin="".join(s + "\n" for s in commits) + "--not\n" + "".join(h + "\n" for h in neg), check=False)
        lost += r.stdout.split() if r.returncode == 0 else commits
    return sorted(set(lost))


def cmd_gc(a):
    require_repo(a.repo)
    repo = a.repo
    if not a.exclusive:
        quiet_gate(repo, a)
    is_old = OldTest(repo, read_old(a.old_commits), read_old_objects(a.old_commits))
    bundle = manifest_bundle(a.archive_dir)
    if not os.path.isfile(bundle) or git(repo, "bundle", "verify", bundle, check=False).returncode != 0:
        raise Refuse("the safety bundle is missing or fails `git bundle verify`: %s" % bundle)
    snap = quiet_gate(repo, a)

    work = []                                               # (name, path, entries, indexes to delete)
    for name, path in reflog_files(repo):
        entries = read_reflog(path)
        idx = reflog_deletions(entries, is_old.any)
        if idx:
            work.append((name, path, entries, idx))
    lost = uncovered(repo, bundle, {s for _n, _p, e, _i in work for pair in e for s in pair
                                    if not NULL_RE.match(s)})
    if lost:
        raise NotQuiet("%d object(s) in the reflogs gc would edit are not in the safety bundle (changed since "
                       "the archive): plan and archive again for a fresh bundle" % len(lost))
    pins, n = {}, 0
    for k, v in sorted(snap.items()):
        if k.startswith("wt|") and not k.startswith("wt|%s|" % MAIN) and key_kind(k) == "ref" and SHA_RE.match(v):
            pins["%s%d" % (PIN_NS, n)] = v
            n += 1
    if pins:
        txt = "start\n" + "".join("create %s %s\n" % kv for kv in sorted(pins.items())) + "commit\n"
        if git(repo, "update-ref", "--stdin", stdin=txt, check=False).returncode != 0:
            raise Refuse("could not create pin refs under %s (name taken?); nothing changed" % PIN_NS)

    removed = failed = 0
    expect, gone, moved_to = {}, set(), {}
    for name, path, entries, idx in work:
        args = ["reflog", "delete", "--rewrite"] + (["--updateref"] if name == "refs/stash" else [])
        r = git(repo, *(args + ["%s@{%d}" % (name, i) for i in idx]), check=False)   # highest index first
        rel = name.split("/", 2)
        key = ("wt|%s|reflog|%s" % (rel[1], rel[2]) if name.startswith("worktrees/") else
               "wt|%s|reflog|%s" % (MAIN, name))
        if r.returncode != 0:
            print("reflog delete failed for %s (exit %d)" % (name, r.returncode))
            failed += 1
            continue
        removed += len(idx)
        expect[key] = (path, [n_ for i, (_o, n_) in enumerate(entries) if i not in idx])
        if name == "refs/stash" and len(idx) == len(entries):              # every stash entry was old
            git(repo, "update-ref", "-d", "refs/stash", entries[0][1], check=False)
            gone |= {"ref|refs/stash", key}
        elif name == "refs/stash" and 0 in idx:                            # --updateref moved it down
            moved_to["ref|refs/stash"] = expect[key][1][0]
    print("reflog entries on old history removed: %d (in %d reflogs); every other entry kept" % (removed, len(expect)))
    r = git(repo, "-c", "gc.reflogExpire=never", "-c", "gc.reflogExpireUnreachable=never",
            "-c", "gc.worktreePruneExpire=never", "gc", "--quiet", "--prune=" + a.prune_floor, check=False)
    print("gc --prune=%s: exit %d" % (a.prune_floor, r.returncode))
    gc_rc = r.returncode
    if not drop_refs(repo, pins):
        print("could not remove the pin refs under %s" % PIN_NS)
        failed += 1

    after = snapshot(repo)
    values = set()
    for k, v in after.items():                     # every ref of every worktree, and each worktree's HEAD
        if key_kind(k) == "ref" or (key_kind(k) == "pseudo" and k.endswith("|HEAD")):
            sha = v.split(" -> ")[0]
            if SHA_RE.match(sha):
                values.add(sha)
    present = object_types(repo, sorted(values))
    dangling = sorted(s for s in values if s not in present)
    if dangling:
        return loud("after gc", ["a ref or HEAD names a missing object %s" % s for s in dangling], bundle)
    bad = []
    for k in diff_keys(snap, after):
        if k in gone and k not in after:
            continue
        if k in moved_to and after.get(k) == moved_to[k]:
            continue
        if k in expect:
            path, want = expect[k]
            got = read_reflog(path)
            if [n_ for _o, n_ in got] == want and not any(is_old.any(o) for o, _n in got):
                continue
        bad.append(k)
    if bad:
        return loud("after gc", bad, bundle)
    return 0 if gc_rc == 0 and not failed else 1


def cmd_overlap(a):
    require_repo(a.repo)
    old = read_old(a.old_commits)
    objs = read_old_objects(a.old_commits)
    listing = out(a.repo, "cat-file", "--batch-all-objects", "--batch-check=%(objecttype) %(objectname)")
    commits, others = set(), set()
    for line in listing.splitlines():
        typ, _, sha = line.partition(" ")
        (commits if typ == "commit" else others).add(sha)
    n = len(commits & old) + len(others & objs)
    print("old commits still in the object store: %d" % len(commits & old))
    if objs:
        print("changed/dropped blobs, trees and tags still in the object store: %d" % len(others & objs))
    if n:
        is_old = OldTest(a.repo, old, objs)
        for name, path in reflog_files(a.repo):
            entries = read_reflog(path)
            new = sum(1 for _o, s in entries if is_old.any(s))
            prev = sum(1 for o, s in entries if not is_old.any(s) and is_old.any(o))
            if new:
                print("reflog %s: %d entr%s on old history; `gc` removes them" % (name, new, "y" if new == 1 else "ies"))
            if prev:
                print("reflog %s: %d entr%s whose previous value is old history (held only through the reflog); "
                      "`gc` removes them" % (name, prev, "y" if prev == 1 else "ies"))
        print("hint: a ref, stash entry or worktree still reaches them (run plan again), a reflog holds them "
              "(run gc), or they are younger than the prune floor (re-run gc after the floor passes)")
    return 0 if n == 0 else 1


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="mode", required=True)
    c = sub.add_parser("changed")
    c.add_argument("purged")
    c.add_argument("backups", nargs="+")
    c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_changed)
    c = sub.add_parser("plan")
    c.add_argument("repo")
    c.add_argument("old_commits")
    c.add_argument("--out", required=True)
    c.add_argument("--min-age-hours", type=float, default=24.0)
    c.add_argument("--include-locked", action="store_true")
    c.set_defaults(fn=cmd_plan)
    for mode, fn in (("archive", cmd_archive), ("gc", cmd_gc)):
        c = sub.add_parser(mode)
        c.add_argument("repo")
        if mode == "archive":
            c.add_argument("plan")
        else:
            c.add_argument("old_commits")
        c.add_argument("archive_dir")
        c.add_argument("--exclusive", action="store_true",
                       help="every session, IDE and scheduled job using this checkout and its worktrees is stopped")
        c.add_argument("--quiet-seconds", type=float, default=60.0,
                       help="gap between the two snapshots that must be identical (default 60)")
        if mode == "archive":
            c.add_argument("--include-locked", action="store_true")
        else:
            c.add_argument("--prune-floor", default="1.hour.ago")
        c.set_defaults(fn=fn)
    c = sub.add_parser("overlap")
    c.add_argument("repo")
    c.add_argument("old_commits")
    c.set_defaults(fn=cmd_overlap)
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    for attr in ("purged", "repo", "out", "plan", "archive_dir", "old_commits"):   # never resolved against -C
        if getattr(a, attr, None):
            setattr(a, attr, os.path.abspath(getattr(a, attr)))
    if getattr(a, "backups", None):
        a.backups = [os.path.abspath(b) for b in a.backups]
    try:
        return a.fn(a)
    except Refuse as exc:
        print("REFUSED: %s" % exc)
        return 2
    except NotQuiet as exc:
        print("NOT QUIET (nothing changed): %s" % exc)
        show_keys(exc.keys)
        return EXIT_NOT_QUIET
    except subprocess.CalledProcessError as exc:
        print("git failed: %s (exit %d)" % (" ".join(exc.cmd), exc.returncode))
        return 2


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(errors="backslashreplace")       # non-ASCII ref names never crash a print
    sys.exit(main())
