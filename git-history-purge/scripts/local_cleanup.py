"""Move a checkout with purged ("old") history into the archive and re-clone it from the purged remote (Step 6).

  python -I local_cleanup.py changed <purged.git> <backup.git> [<backup2.git> ...] --out <old-commits.txt>
  python -I local_cleanup.py inventory <repo> <old-commits.txt> --out <inv.json>
  python -I local_cleanup.py rehome <repo> <inv.json> <archive-dir> <clone-url> --exclusive [--quiet-seconds 60]
  python -I local_cleanup.py overlap <repo> <old-commits.txt>

Every path argument is resolved against the current directory before use. Nothing is ever deleted.

"Old history" = reaches a commit the purge CHANGED or DROPPED: every commit reachable from any ref of
any backup, minus every commit reachable from any ref of the purged copy. A clean first commit keeps
its SHA through filter-repo, so branches sharing only that root are NOT old; an orphan branch is not
old either. Several backups: a second one is made when someone pushed after the first (never fetch
into an existing backup); `changed` takes their union.

changed    writes the sorted old set; exit 1 if it is empty (refuse to guess). Also writes
           <out>.objects: the changed/dropped NON-commit objects (blobs, trees, tag objects reachable
           from the backups minus those reachable from the purged copy); inventory and overlap read it
           when it sits next to the old-commits file.
inventory  (read-only) the main checkout and every linked worktree (branch or detached HEAD, locked,
           modified, untracked, staged-only, operation in progress, submodules), every local ref in
           every namespace (per-worktree refs included) and every stash entry, each OLD (reaches an
           old commit, or is/peels to a listed old object) or KEPT; remotes, branch upstreams,
           core.hooksPath and the hooks dir; and a full-state snapshot. Prints a table. Exit 2 with
           a REFUSED list when something cannot be carried across without loss: a KEPT worktree that
           has modified, untracked or staged-only files, an operation in progress, or a submodule
           with unpushed commits or changes; or an operation in progress in ANY worktree (the rehome
           gate refuses it). OLD worktrees may be dirty: they stay intact in the archive.
rehome     EXCLUSIVE MAINTENANCE. Refuses (exit 4) unless --exclusive is passed (every session, IDE
           and scheduled job using the checkout is stopped), no *.lock file exists, nothing is in
           progress, and two snapshots --quiet-seconds apart equal each other and the inventory's.
           Refuses (exit 2) an archive dir that exists, is inside the checkout or a worktree, or is
           on another volume. Then renames every linked worktree outside the main folder to
           <archive>/worktrees/<n>-<name>/ and the main folder to <archive>/repo/, and runs
           `git worktree repair` there (a failed rename, repair or clone renames everything back: exit 3).
           Clones <clone-url> (the PURGED remote) into the main path, re-points the archived submodules'
           .git files at their archived repositories,
           restores remotes, branch upstreams and core.hooksPath (hooks are NOT copied), fetches the
           KEPT refs from the archived repo with an explicit refspec list (branches, tags, notes and
           other namespaces; never remote-tracking or old refs, never --tags), stores the kept stash
           entries oldest first, re-creates each kept worktree at its path (detached if it was,
           re-locked with its reason) with its per-worktree refs, and verifies: overlap 0, every
           carried ref at its SHA, every re-created worktree clean at its HEAD. Writes
           <archive>/REHOME.md (what moved, what came across, how to restore).
overlap    objects in the object store that are in the old set (commits) or, when <old>.objects
           exists, in that set (blobs, trees, tags): exit 0 when 0, else 1.

Prints counts, ref names and paths only, never file contents.
Exit codes: 0 ok, 1 work left/found, 2 bad input or REFUSED (nothing changed), 3 rehome stopped before
the clone and rolled every rename back (original layout confirmed), 4 not exclusive / not quiet / changed
since the inventory (nothing changed), 5 a step after the clone failed (the archive is complete; see
REHOME.md), 6 the rollback itself failed (folders listed where they are now).
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
MAIN = "."                                  # snapshot id of the main worktree (never a worktree admin id)
PSEUDO = ("HEAD", "ORIG_HEAD", "FETCH_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REBASE_HEAD", "REVERT_HEAD",
          "BISECT_HEAD", "AUTO_MERGE")
BUSY = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "BISECT_START",
        "sequencer")
PER_WORKTREE = ("refs/worktree/", "refs/bisect/", "refs/rewritten/")
TMP_NS = "refs/rehome-tmp/"
EXIT_ROLLED_BACK, EXIT_NOT_QUIET, EXIT_AFTER_CLONE, EXIT_ROLLBACK_FAILED = 3, 4, 5, 6


class Refuse(Exception):
    """Bad input: exit 2, nothing changed."""


class NotQuiet(Exception):
    """Not exclusive / not quiet / changed since the inventory: exit 4, nothing changed."""

    def __init__(self, msg, keys=()):
        Exception.__init__(self, msg)
        self.keys = list(keys)


def git(repo, *args, check=True, stdin=None):
    r = subprocess.run(["git", "--no-optional-locks", "-C", repo, "-c", "core.quotepath=false"] + list(args),
                       capture_output=True, input=None if stdin is None else stdin.encode("utf-8", "surrogateescape"))
    r.stdout = r.stdout.decode("utf-8", "surrogateescape")
    r.stderr = r.stderr.decode("utf-8", "replace")
    if check and r.returncode != 0:
        raise subprocess.CalledProcessError(r.returncode, ["git"] + list(args)[:2], r.stdout, r.stderr)
    return r


def out(repo, *args):
    return git(repo, *args).stdout


def norm(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def inside(path, folder):
    return norm(path).startswith(norm(folder) + os.sep)


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


def index_only(xy):
    """Index differs from BOTH HEAD and the work tree (MM, AM, RM, MD, AD ...)."""
    return len(xy) == 2 and xy[0] not in " ?!" and xy[1] != " "


class OldTest:
    """Called with a commit: does it reach an old commit? .obj(sha): is it a listed old non-commit object?"""

    def __init__(self, repo, old, objs=frozenset()):
        self.repo, self.old, self.objs, self.cache = repo, old, objs, {}

    def __call__(self, sha):
        if sha not in self.cache:
            r = git(self.repo, "rev-list", sha, check=False)
            self.cache[sha] = r.returncode == 0 and not self.old.isdisjoint(r.stdout.split())
        return self.cache[sha]

    def ref(self, sha, commit, peeled):
        """A ref (object sha, peeled commit or None, peeled object) is old history."""
        if commit:
            return self(commit) or sha in self.objs
        return sha in self.objs or peeled in self.objs


def ref_kind(name):
    parts = name.split("/")
    if name.startswith(PER_WORKTREE):
        return "worktree"
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
    """[(sha, message)] newest first."""
    if git(repo, "rev-parse", "--verify", "-q", "refs/stash", check=False).returncode != 0:
        return []
    rows = out(repo, "reflog", "show", "--format=%H%x00%gs", "refs/stash", "--").splitlines()
    return [tuple(l.split("\0", 1)) for l in rows if l]


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
            cur = {"path": os.path.normpath(line[9:]), "head": None, "branch": None, "detached": False, "bare": False,
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
    """Deterministic, JSON-able {key: value} of everything another session could change: every ref (all
    namespaces, every worktree's per-worktree refs and pseudo-refs), every reflog (sha256), every index,
    lock files, operations in progress, and every worktree's status (with each listed file's size and mtime)."""
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


# ---------------------------------------------------------------- inventory

def admin_dir(path):
    return out(path, "rev-parse", "--absolute-git-dir").strip()


def submodules(path, prefix=""):
    """[{path, unpushed, dirty}] for every initialised submodule under path (recursive)."""
    found = []
    for entry in filter(None, out(path, "ls-files", "-s", "-z").split("\0")):
        meta, rel = entry.split("\t", 1)
        if not meta.startswith("160000 "):
            continue
        sub = os.path.join(path, rel)
        if not os.path.exists(os.path.join(sub, ".git")):
            continue                                         # not initialised: nothing local to lose
        unpushed = len(out(sub, "rev-list", "--all", "--not", "--remotes").split())
        dirty = len([l for l in out(sub, "status", "--porcelain", "-uall").splitlines() if l])
        found.append({"path": prefix + rel, "unpushed": unpushed, "dirty": dirty})
        found += submodules(sub, prefix + rel + "/")
    return found


def worktree_state(path, nested):
    """modified / untracked / staged-only paths (registered worktrees nested in it are not untracked),
    operations in progress, submodules and the count of ignored entries."""
    st = {"modified": [], "untracked": [], "staged_only": []}
    raw = git(path, "status", "--porcelain=v1", "-uall", "-z").stdout.split("\0")
    i = 0
    while i < len(raw):
        item = raw[i]
        i += 1
        if len(item) < 4:
            continue
        xy, rel = item[:2], item[3:]
        if xy[0] in "RC":
            i += 1                                           # skip the rename/copy source path
        if xy == "??":
            if rel.rstrip("/") not in nested:
                st["untracked"].append(rel)
        elif index_only(xy):
            st["staged_only"].append(rel)
        else:
            st["modified"].append(rel)
    g = admin_dir(path)
    st["busy"] = [n for n in BUSY if os.path.exists(os.path.join(g, n))]
    st["submodules"] = submodules(path)
    ignored = git(path, "ls-files", "-o", "-i", "--exclude-standard", "--directory", "-z").stdout
    st["ignored"] = len([x for x in ignored.split("\0") if x and x.rstrip("/") not in nested])
    return st


FIXES = {
    "modified": "commit it on a kept branch, or `git stash` it",
    "untracked": "commit it, `git stash -u` it, or move the files out of the checkout",
    "staged-only": "commit the staged version, or unstage it",
    "in progress": "finish or abort it (`git <op> --continue` / `--abort`, `git bisect reset`)",
    "unpushed": "push the submodule's commits, or move them onto a branch its remote has",
    "submodule changes": "commit (and push) inside the submodule",
}


def refusals_for(w):
    rows, path = [], w["path"]

    def add(problem, items, key):
        rows.append({"path": path, "problem": "%s (%d): %s" % (problem, len(items), ", ".join(items[:5])),
                     "fix": FIXES[key]})
    if w["busy"]:
        add("operation in progress", w["busy"], "in progress")
    if w["old"]:
        return rows                                          # stays intact in the archive
    if w["modified"]:
        add("modified files", w["modified"], "modified")
    if w["untracked"]:
        add("untracked files", w["untracked"], "untracked")
    if w["staged_only"]:
        add("staged-only content", w["staged_only"], "staged-only")
    for s in w["submodules"]:
        if s["unpushed"]:
            add("submodule %s has unpushed commits" % s["path"], ["%d commit(s)" % s["unpushed"]], "unpushed")
        if s["dirty"]:
            add("submodule %s has changes" % s["path"], ["%d file(s)" % s["dirty"]], "submodule changes")
    return rows


def config_entries(repo, pattern):
    r = git(repo, "config", "-z", "--get-regexp", pattern, check=False)
    return [list(e.split("\n", 1)) if "\n" in e else [e, ""] for e in r.stdout.split("\0") if e]


def build_inventory(repo, old, objs):
    is_old = OldTest(repo, old, objs)
    wts = list_worktrees(repo)
    main = wts[0]
    if norm(common_dir(repo)) != norm(os.path.join(main["path"], ".git")):
        raise Refuse("the git dir is not <repo>/.git (separate git dir): moving the folder would not move it")
    if main["bare"] or norm(main["path"]) != norm(repo):
        raise Refuse("give the main worktree's top folder (%s), not a linked worktree or a subfolder" % main["path"])
    inv = {"repo": os.path.abspath(repo), "created": time.time(), "worktrees": [], "refs": [], "stash": [],
           "refusals": []}
    paths = [w["path"] for w in wts]
    for w in wts:
        if w["prunable"] or not os.path.isdir(w["path"]):
            inv["refusals"].append({"path": w["path"], "problem": "worktree folder missing (prunable)",
                                    "fix": "restore the folder, or `git worktree prune` it yourself first"})
            continue
        containers = [p for p in paths if inside(w["path"], p)]
        if w["main"] and containers:
            raise Refuse("the main checkout is inside worktree %s" % containers[0])
        nested = {os.path.relpath(p, w["path"]).replace(os.sep, "/") for p in paths if inside(p, w["path"])}
        rec = {k: w[k] for k in ("path", "id", "main", "head", "branch", "detached", "locked", "lock_reason")}
        rec["old"] = bool(w["head"]) and is_old(w["head"])
        rec["container"] = max(containers, key=len) if containers else None
        rec.update(worktree_state(w["path"], nested))
        inv["worktrees"].append(rec)
        inv["refusals"] += refusals_for(rec)
        if not w["main"]:
            for name, sha, commit, symref, peeled in list_refs(w["path"]):
                if name.startswith(PER_WORKTREE) and not symref:
                    inv["refs"].append({"name": name, "sha": sha, "kind": "worktree", "worktree": w["id"],
                                        "old": is_old.ref(sha, commit, peeled)})
    for name, sha, commit, symref, peeled in list_refs(repo):
        if symref or name == "refs/stash":
            continue
        inv["refs"].append({"name": name, "sha": sha, "kind": ref_kind(name), "worktree": None,
                            "old": is_old.ref(sha, commit, peeled)})
    for i, (sha, msg) in enumerate(stash_entries(repo)):
        inv["stash"].append({"index": i, "sha": sha, "message": msg, "old": is_old(sha)})
    for r in inv["refs"]:
        r["carry"] = not r["old"] and r["kind"] != "remotes"
    inv["remotes"] = config_entries(repo, r"^remote\.")
    inv["branch_config"] = config_entries(repo, r"^branch\.")
    hp = git(repo, "config", "--get", "core.hooksPath", check=False).stdout.strip()
    inv["hooks_path"] = hp or None
    hooks = os.path.join(common_dir(repo), "hooks")
    inv["hooks"] = sorted(f for f in os.listdir(hooks) if not f.endswith(".sample")) if os.path.isdir(hooks) else []
    return inv


def label(old):
    return "OLD " if old else "KEPT"


def print_inventory(inv):
    print("worktrees:")
    for w in inv["worktrees"]:
        flags = [w["branch"] or "detached@" + (w["head"] or "?")[:12]]
        if w["main"]:
            flags.append("main")
        if w["locked"]:
            flags.append("locked")
        for k in ("modified", "untracked", "staged_only", "busy"):
            if w[k]:
                flags.append("%s %d" % (k, len(w[k])))
        if w["submodules"]:
            flags.append("submodules %d" % len(w["submodules"]))
        if w["ignored"]:
            flags.append("ignored %d (stay in the archive)" % w["ignored"])
        print("  %s  %s  [%s]" % (label(w["old"]), w["path"], ", ".join(flags)))
        if w["old"] and (w["modified"] or w["untracked"] or w["staged_only"]):
            print("        uncommitted changes here stay only in the archive")
    print("refs:")
    for r in inv["refs"]:
        where = "" if r["worktree"] is None else "  (worktree %s)" % r["worktree"]
        how = "" if r["old"] else ("  carried" if r["carry"] else "  fresh from the clone")
        print("  %s  %-8s %s%s%s" % (label(r["old"]), r["kind"], r["name"], where, how))
    for e in inv["stash"]:
        print("  %s  stash    stash@{%d}" % (label(e["old"]), e["index"]))
    print("remotes: %d config entr%s; core.hooksPath: %s; hooks: %s" % (
        len(inv["remotes"]), "y" if len(inv["remotes"]) == 1 else "ies", inv["hooks_path"] or "(default)",
        ", ".join(inv["hooks"]) or "none"))
    print("old refs: %d, kept refs carried: %d, stash entries kept: %d of %d" % (
        sum(r["old"] for r in inv["refs"]), sum(r["carry"] for r in inv["refs"]),
        sum(not e["old"] for e in inv["stash"]), len(inv["stash"])))
    for x in inv["refusals"]:
        print("REFUSED %s: %s -> %s" % (x["path"], x["problem"], x["fix"]))


def cmd_inventory(a):
    require_repo(a.repo)
    old = read_old(a.old_commits)
    before = snapshot(a.repo)
    inv = build_inventory(a.repo, old, read_old_objects(a.old_commits))
    inv["snapshot"] = snapshot(a.repo)
    changed = diff_keys(before, inv["snapshot"])
    if changed:
        raise NotQuiet("the checkout changed during the inventory: something is writing; stop it, then run "
                       "inventory again", changed)
    inv["old_commits"] = os.path.abspath(a.old_commits)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(inv, fh, indent=1)
    print_inventory(inv)
    if inv["refusals"]:
        print("%d case(s) cannot be carried across without loss: resolve each, then run inventory again"
              % len(inv["refusals"]))
        return 2
    return 0


# ---------------------------------------------------------------- rehome

def move_plan(inv, archive):
    """[(original, archived)] renames: linked worktrees not inside another worktree (sorted), then main."""
    moves, n = [], 0
    for w in sorted(inv["worktrees"], key=lambda w: norm(w["path"])):
        if not w["main"] and w["container"] is None:
            moves.append((w["path"], os.path.join(archive, "worktrees", "%d-%s" % (
                n, os.path.basename(os.path.normpath(w["path"]))))))
            n += 1
    main = [w for w in inv["worktrees"] if w["main"]][0]
    return moves + [(main["path"], os.path.join(archive, "repo"))]


def archived_path(path, moves):
    """Where a worktree folder is after the moves (it may be nested in a moved folder)."""
    for src, dst in moves:
        if norm(path) == norm(src):
            return dst
        if inside(path, src):
            return os.path.join(dst, os.path.relpath(path, src))
    return path


def rollback(repo, inv, archive, done, repaired, why):
    """Rename done moves back in reverse; repair; confirm the inventory's snapshot. Returns an exit code."""
    stuck = []
    for src, dst in reversed(done):
        try:
            os.rename(dst, src)
        except OSError as exc:
            stuck.append((src, dst, type(exc).__name__))
    if stuck:
        print("ROLLBACK FAILED after: %s" % why)
        for src, dst, err in stuck:
            print("  %s is now at %s (rename back failed: %s)" % (src, dst, err))
        back = [s for s, _d in done if s not in {x[0] for x in stuck}]
        for src in back:
            print("  %s is back at its original path" % src)
        print("Nothing was deleted. Rename each folder back by hand, then run `git worktree repair` in %s." % repo)
        return EXIT_ROLLBACK_FAILED
    if repaired:
        git(repo, "worktree", "repair", *[w["path"] for w in inv["worktrees"] if not w["main"]], check=False)
    changed = diff_keys(inv["snapshot"], snapshot(repo))
    if changed:
        print("ROLLBACK FAILED after: %s. Every folder is back, but the checkout differs from the inventory:" % why)
        show_keys(changed)
        return EXIT_ROLLBACK_FAILED
    for d in (os.path.join(archive, "worktrees"), archive):
        try:
            os.rmdir(d)                                       # only removes an EMPTY dir this run made
        except OSError:
            pass
    print("STOPPED: %s. Every rename was rolled back; the checkout matches the inventory again." % why)
    return EXIT_ROLLED_BACK


def check_archive_dir(inv, archive, url):
    if os.path.exists(archive):
        raise Refuse("archive dir exists (never reused): %s" % archive)
    for w in inv["worktrees"]:
        if norm(archive) == norm(w["path"]) or inside(archive, w["path"]):
            raise Refuse("the archive dir is inside %s; put it outside every checkout" % w["path"])
        if len({device_of(archive), device_of(w["path"])}) != 1:
            raise Refuse("the archive dir is on another volume than %s: a rename would copy; put it on the "
                         "same volume" % w["path"])
    if os.path.exists(url) and any(norm(url) == norm(w["path"]) or inside(url, w["path"])
                                   for w in inv["worktrees"]):
        raise Refuse("the clone URL is this checkout: clone the purged remote, never the old copy")


def carry(inv, archived_repo, path):
    """Fetch the kept refs (explicit refspecs) and temp refs for stash entries and per-worktree refs."""
    specs = ["+%s:%s" % (r["name"], r["name"]) for r in inv["refs"] if r["carry"] and r["kind"] != "worktree"]
    temp = {}
    for r in inv["refs"]:
        if r["carry"] and r["kind"] == "worktree":
            temp["%sw%d" % (TMP_NS, len(temp))] = r["sha"]
    for e in inv["stash"]:
        if not e["old"]:
            temp["%ss%d" % (TMP_NS, e["index"])] = e["sha"]
    specs += ["+%s:%s" % (sha, name) for name, sha in sorted(temp.items())]
    if specs:
        git(path, "fetch", "--no-tags", "--update-head-ok", "--no-write-fetch-head", "--no-recurse-submodules",
            "--stdin", archived_repo, stdin="".join(s + "\n" for s in specs))
    return temp


def restore_config(inv, path):
    carried = {r["name"][len("refs/heads/"):] for r in inv["refs"] if r["carry"] and r["kind"] == "heads"}
    entries = list(inv["remotes"])
    for key, value in inv["branch_config"]:
        name = key[len("branch."):].rsplit(".", 1)[0]
        if name in carried:
            entries.append([key, value])
    for key in sorted({k for k, _v in entries}):
        git(path, "config", "--unset-all", key, check=False)
    for key, value in entries:
        git(path, "config", "--add", key, value)
    if inv["hooks_path"]:
        git(path, "config", "core.hooksPath", inv["hooks_path"])


def recreate(inv, path, temp):
    """Stash entries (oldest first), main's branch, kept linked worktrees, per-worktree refs; temp refs dropped."""
    by_sha = {sha: name for name, sha in temp.items()}
    for e in reversed(inv["stash"]):
        if not e["old"]:
            git(path, "stash", "store", "-q", "-m", e["message"], e["sha"])
    main = [w for w in inv["worktrees"] if w["main"]][0]
    if not main["old"]:
        if main["branch"]:
            git(path, "checkout", "-q", "-f", main["branch"][len("refs/heads/"):])
        else:
            git(path, "checkout", "-q", "-f", "--detach", main["head"])
    for w in sorted(inv["worktrees"], key=lambda w: len(w["path"])):
        if w["main"] or w["old"]:
            continue
        if w["branch"]:
            git(path, "worktree", "add", "-q", w["path"], w["branch"][len("refs/heads/"):])
        else:
            git(path, "worktree", "add", "-q", "--detach", w["path"], w["head"])
        if w["locked"]:
            git(path, "worktree", "lock", *(["--reason", w["lock_reason"]] if w["lock_reason"] else []), w["path"])
        for r in inv["refs"]:
            if r["carry"] and r["worktree"] == w["id"]:
                git(w["path"], "update-ref", r["name"], r["sha"])
    if temp:
        git(path, "update-ref", "--stdin", stdin="start\n" + "".join(
            "delete %s %s\n" % (by_sha[sha], sha) for sha in by_sha) + "commit\n")


def overlap_counts(repo, old, objs):
    listing = out(repo, "cat-file", "--batch-all-objects", "--batch-check=%(objecttype) %(objectname)")
    commits, others = set(), set()
    for line in listing.splitlines():
        typ, _, sha = line.partition(" ")
        (commits if typ == "commit" else others).add(sha)
    return len(commits & old), len(others & objs)


def verify(inv, path):
    """Problems found in the new clone (empty list = verified)."""
    bad = []
    old_path = inv["old_commits"]
    n_c, n_o = overlap_counts(path, read_old(old_path), read_old_objects(old_path))
    if n_c or n_o:
        bad.append("overlap: %d old commit(s) and %d old blob/tree/tag object(s) in the new clone" % (n_c, n_o))
    wts = {w["id"]: w for w in inv["worktrees"]}
    for r in inv["refs"]:
        if r["carry"]:
            where = path if r["worktree"] is None else wts[r["worktree"]]["path"]
            got = git(where, "rev-parse", "--verify", "-q", r["name"], check=False).stdout.strip()
            if got != r["sha"]:
                bad.append("ref %s is %s, expected %s" % (r["name"], got or "missing", r["sha"]))
    want = [e["sha"] for e in inv["stash"] if not e["old"]]
    have = git(path, "reflog", "show", "--format=%H", "refs/stash", "--", check=False).stdout.split()
    if have != want:
        bad.append("stash list differs from the kept entries")
    paths = [w["path"] for w in inv["worktrees"] if not w["old"]]
    listed = {norm(w["path"]): w for w in list_worktrees(path)}
    for w in inv["worktrees"]:
        if w["old"]:
            continue
        now = listed.get(norm(w["path"]))
        nested = {os.path.relpath(p, w["path"]).replace(os.sep, "/") for p in paths if inside(p, w["path"])}
        if not now or now["head"] != w["head"] or now["branch"] != w["branch"] or \
                (now["locked"], now["lock_reason"]) != (w["locked"], w["lock_reason"]):
            bad.append("worktree %s is not at its recorded HEAD/branch/lock" % w["path"])
            continue
        st = worktree_state(w["path"], nested)
        if st["modified"] or st["untracked"] or st["staged_only"]:
            bad.append("worktree %s is not clean" % w["path"])
    return bad


def repair_submodules(inv, moves):
    """Point each archived submodule's .git file and core.worktree at its archived location: git writes them
    as relative paths, which break when a worktree and its admin dir move to different folders."""
    for w in inv["worktrees"]:
        for sm in w["submodules"]:
            old_sub = os.path.join(w["path"], sm["path"])
            new_sub = archived_path(old_sub, moves)
            gitfile = os.path.join(new_sub, ".git")
            if not os.path.isfile(gitfile):
                continue                                     # a plain .git dir moved with its work tree
            with open(gitfile, "r+", encoding="utf-8", newline="\n") as fh:   # "w" fails on a hidden file
                target = fh.read().strip()[len("gitdir: "):]
                gitdir = archived_path(target if os.path.isabs(target) else os.path.join(old_sub, target), moves)
                fh.seek(0)
                fh.write("gitdir: %s\n" % os.path.relpath(gitdir, new_sub).replace(os.sep, "/"))
                fh.truncate()
            git(os.path.dirname(gitdir), "config", "--file", os.path.join(gitdir, "config"), "core.worktree",
                os.path.relpath(new_sub, gitdir).replace(os.sep, "/"))


def write_rehome_md(inv, archive, moves, url, result):
    carried = [r for r in inv["refs"] if r["carry"]]
    lines = ["# Rehome record", "", "Result: %s" % result, "", "Clone URL (purged remote): %s" % url, "",
             "## What moved where (renames only; nothing was deleted)", ""]
    for w in inv["worktrees"]:
        lines.append("- %s %s -> %s" % (label(w["old"]).strip(), w["path"], archived_path(w["path"], moves)))
    lines += ["", "## Carried into the new clone", ""]
    lines += ["- %s %s" % (r["name"], r["sha"]) + ("" if r["worktree"] is None else " (worktree %s)" % r["worktree"])
              for r in carried]
    lines += ["- stash entry %s" % e["sha"] for e in inv["stash"] if not e["old"]]
    lines += ["- worktree %s" % w["path"] for w in inv["worktrees"] if not w["old"] and not w["main"]]
    lines += ["", "Everything else (old refs, reflogs, unreachable objects, ignored files, hooks, other config, "
              "ORIG_HEAD/FETCH_HEAD, submodule repositories) is only in the archived copy.", "",
              "## How to restore", "",
              "1. Stop every session using %s." % inv["repo"],
              "2. Rename the new clone and its re-created worktrees aside (into this archive dir; never delete).",
              "3. Rename each archived folder above back to its original path.",
              "4. In %s run `git worktree repair` with every linked worktree path." % inv["repo"],
              "5. Submodule `.git` files under the archived worktrees were re-pointed at the archive (relative "
              "paths): after renaming back, point each at its repository under <repo>/.git/ again.", ""]
    with open(os.path.join(archive, "REHOME.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))


def cmd_rehome(a):
    require_repo(a.repo)
    with open(a.inv, encoding="utf-8") as fh:
        inv = json.load(fh)
    if norm(inv.get("repo", "")) != norm(a.repo) or "snapshot" not in inv:
        raise Refuse("the inventory is for another checkout (or incomplete): %s" % inv.get("repo"))
    if inv["refusals"]:
        raise Refuse("the inventory has %d REFUSED case(s): resolve them and run inventory again"
                     % len(inv["refusals"]))
    archive, repo = a.archive_dir, a.repo
    check_archive_dir(inv, archive, a.clone_url)
    changed = diff_keys(inv["snapshot"], quiet_gate(repo, a))
    if changed:
        raise NotQuiet("the checkout changed since the inventory: run inventory again (and find who changed it)",
                       changed)

    moves = move_plan(inv, archive)
    os.makedirs(os.path.join(archive, "worktrees"))
    done = []
    for src, dst in moves:
        try:
            os.rename(src, dst)
        except OSError as exc:
            return rollback(repo, inv, archive, done, False, "rename of %s failed (%s): close whatever holds it "
                            "open (shell, editor, fsmonitor)" % (src, type(exc).__name__))
        done.append((src, dst))
    archived_repo = os.path.join(archive, "repo")
    linked = [archived_path(w["path"], moves) for w in inv["worktrees"] if not w["main"]]
    r = git(archived_repo, "worktree", "repair", *linked, check=False)
    rows = {norm(w["path"]): w for w in list_worktrees(archived_repo)} if r.returncode == 0 else {}
    if r.returncode != 0 or any(norm(p) not in rows or rows[norm(p)]["prunable"] for p in linked):
        return rollback(repo, inv, archive, done, True, "`git worktree repair` in the archive failed")

    parent = os.path.dirname(os.path.abspath(repo))
    r = git(parent, "clone", "-q", "--no-recurse-submodules", a.clone_url, repo, check=False)
    if r.returncode != 0:
        why = "clone failed (exit %d)" % r.returncode
        if os.path.exists(repo):
            try:
                os.rename(repo, os.path.join(archive, "failed-clone"))
                why += "; its leftover is in %s" % os.path.join(archive, "failed-clone")
            except OSError:
                why += "; its leftover at %s could not be moved aside" % repo   # the rollback then lists it
        return rollback(repo, inv, archive, done, True, why)
    try:
        repair_submodules(inv, moves)
        restore_config(inv, repo)
        temp = carry(inv, archived_repo, repo)
        recreate(inv, repo, temp)
        bad = verify(inv, repo)
    except (subprocess.CalledProcessError, OSError) as exc:
        bad = ["%s: %s" % (type(exc).__name__, " ".join(getattr(exc, "cmd", []) or [str(exc)]))]
    write_rehome_md(inv, archive, moves, a.clone_url, "FAILED: " + "; ".join(bad) if bad else "verified")
    print("archived copy: %s (worktrees in %s); record: %s" % (archived_repo, os.path.join(archive, "worktrees"),
                                                             os.path.join(archive, "REHOME.md")))
    if bad:
        print("AFTER THE CLONE (exit 5): the archived copy in %s is complete; the new clone at %s is not "
              "verified:" % (archive, repo))
        for b in bad:
            print("  " + b)
        print("Fix the cause, or restore the archive as REHOME.md says. Never delete the archive.")
        return EXIT_AFTER_CLONE
    print("carried: %d ref(s), %d stash entr%s, %d worktree(s); overlap 0; every carried ref at its SHA" % (
        sum(r["carry"] for r in inv["refs"]), sum(not e["old"] for e in inv["stash"]),
        "y" if sum(not e["old"] for e in inv["stash"]) == 1 else "ies",
        sum(1 for w in inv["worktrees"] if not w["old"] and not w["main"])))
    print("hooks were NOT copied: run the repo's hook installer once on the new clone (a v1.0 old_history_guard "
          "is no longer needed there; the archived copy keeps its own hooks)")
    return 0


def cmd_overlap(a):
    require_repo(a.repo)
    objs = read_old_objects(a.old_commits)
    n_c, n_o = overlap_counts(a.repo, read_old(a.old_commits), objs)
    print("old commits still in the object store: %d" % n_c)
    if objs:
        print("changed/dropped blobs, trees and tags still in the object store: %d" % n_o)
    if n_c or n_o:
        print("hint: this copy still holds old history: rehome it (inventory, then rehome --exclusive)")
    return 0 if n_c + n_o == 0 else 1


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


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = p.add_subparsers(dest="mode", required=True)
    c = sub.add_parser("changed")
    c.add_argument("purged")
    c.add_argument("backups", nargs="+")
    c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_changed)
    c = sub.add_parser("inventory")
    c.add_argument("repo")
    c.add_argument("old_commits")
    c.add_argument("--out", required=True)
    c.set_defaults(fn=cmd_inventory)
    c = sub.add_parser("rehome")
    c.add_argument("repo")
    c.add_argument("inv")
    c.add_argument("archive_dir")
    c.add_argument("clone_url", help="the PURGED remote (never the archive or this checkout)")
    c.add_argument("--exclusive", action="store_true",
                   help="every session, IDE and scheduled job using this checkout and its worktrees is stopped")
    c.add_argument("--quiet-seconds", type=float, default=60.0,
                   help="gap between the two snapshots that must be identical (default 60)")
    c.set_defaults(fn=cmd_rehome)
    c = sub.add_parser("overlap")
    c.add_argument("repo")
    c.add_argument("old_commits")
    c.set_defaults(fn=cmd_overlap)
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    for attr in ("purged", "repo", "out", "inv", "archive_dir", "old_commits"):   # never resolved against -C
        if getattr(a, attr, None):
            setattr(a, attr, os.path.abspath(getattr(a, attr)))
    if getattr(a, "backups", None):
        a.backups = [os.path.abspath(b) for b in a.backups]
    if getattr(a, "clone_url", None) and os.path.exists(a.clone_url):
        a.clone_url = os.path.abspath(a.clone_url)
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
