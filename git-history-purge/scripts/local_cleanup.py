"""Move a checkout with purged ("old") history into the archive and re-clone it from the purged remote (Step 6).

  python -I local_cleanup.py changed <purged.git> <backup.git> [<backup2.git> ...] --out <old-commits.txt>
  python -I local_cleanup.py inventory <repo> <old-commits.txt> --out <inv.json>
  python -I local_cleanup.py rehome <repo> <inv.json> <archive-dir> <clone-url> --exclusive [--quiet-seconds 60]
  python -I local_cleanup.py overlap <repo> <old-commits.txt>
  python -I local_cleanup.py restore <archive-dir> --exclusive

Paths are resolved against the current directory. Nothing is deleted (except a run's own <repo>.rehome.lock,
and its own rehome.json after a complete rollback).

"Old history" = reaches a commit the purge CHANGED or DROPPED (in any backup, not in the purged copy). A clean
first commit keeps its SHA, so branches sharing only that root are NOT old; neither is an orphan branch.

changed    writes the sorted old set (exit 1 if empty: the file then holds only a "0 commits" marker, the one
           empty form accepted; an empty or malformed file is refused, exit 2) and <out>.objects, the
           changed/dropped blobs, trees and tag objects, read by inventory and overlap.
inventory  (read-only) classifies every worktree, ref and stash entry OLD or KEPT, names each worktree's
           ignored paths exactly as git reports them, records remotes, upstreams, core.hooksPath and a
           full-state snapshot, and prints a table. rehome carries ONE layout: the main worktree and linked
           worktrees that are direct folders (none inside another), each on a branch with commits or detached
           at a commit a carried ref reaches; kept ones clean, with no initialised submodule and no
           per-worktree ref; kept branches, tags, notes, other refs and stash entries. The main checkout may
           be OLD. Everything else is REFUSED (exit 2), each with what to do by hand. OLD worktrees may be
           dirty: they stay in the archive.
rehome     EXCLUSIVE MAINTENANCE. Exit 4 (nothing changed) without --exclusive, while <repo>.rehome.lock
           exists, with a *.lock file or an operation in progress, or when two snapshots --quiet-seconds apart
           (and a third before the first rename) differ from each other or the inventory. Exit 2 for an
           archive dir that exists, is inside a worktree or on another volume. Writes <archive>/rehome.json,
           renames every linked worktree to <archive>/worktrees/<n>-<name>/ and the main folder to
           <archive>/repo/, runs `git worktree repair` there, and clones the purged remote into
           <archive>/new-clone (a failure rolls every rename back: exit 3; an interrupt rolls back, then is
           raised again). Then re-points gitfiles and submodule core.worktree in the archive, restores
           remotes, upstreams and core.hooksPath (a clone without hooks gets <archive>/hooks-stub, whose
           pre-push refuses every push), fetches the kept refs (explicit refspecs) and stash entries, checks
           the main worktree out clean, renames the clone into place (exit 5 if the path was recreated),
           re-creates the kept worktrees and verifies: overlap 0, every carried ref at its SHA, stash order,
           every worktree clean at its HEAD, reflogs unchanged. Writes <archive>/REHOME.md.
restore    EXCLUSIVE MAINTENANCE, the reverse: moves the new clone (if any) and its worktrees aside to
           <archive>/restored-aside-<n>/, renames back every folder the rehome moved, repairs links and
           compares with the inventory's snapshot: exit 0 identical, 1 differs.
overlap    old commits (and listed old objects) in the object store: exit 0 when 0, else 1.

Prints counts, ref names and paths only, never file contents.
Exit codes: 0 ok, 1 work left/found, 2 bad input or REFUSED (nothing changed), 3 stopped and rolled back,
4 not exclusive / locked / not quiet (nothing changed), 5 a step after the clone failed (the archive is
complete; see REHOME.md), 6 the rollback itself failed (folders listed where they are now).
"""
import argparse
import contextlib
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
ZERO_MARK = "# local_cleanup changed: 0 commits"     # the only empty old-commits file inventory accepts
LOCK_SUFFIX = ".rehome.lock"
STAGING = "new-clone"
RECORD = "rehome.json"
STUB = "hooks-stub"
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


def objects_of(repo, shas):
    """Every object reachable from the given objects."""
    stdin = "".join(sha + "\n" for sha in shas)
    listing = git(repo, "rev-list", "--objects", "--stdin", stdin=stdin).stdout if shas else ""
    return {l.split(" ", 1)[0] for l in listing.splitlines() if l}


def read_shas(path, what, allow_empty):
    with open(path, encoding="ascii", errors="replace") as fh:
        lines = [l.strip() for l in fh if l.strip()]
    shas = [l for l in lines if l != ZERO_MARK]
    bad = [s for s in shas if not SHA_RE.match(s)]
    if bad or (not shas and not allow_empty and ZERO_MARK not in lines):
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
    """Called with a commit: does it reach an old commit? .ref(...): is a ref old history?"""

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
    for i, w in enumerate(blocks):
        w["main"] = i == 0
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

def submodules(path):
    """Paths of the initialised submodules (gitlinks whose folder holds a .git) in the worktree at path."""
    found = []
    for entry in filter(None, out(path, "ls-files", "-s", "-z").split("\0")):
        meta, rel = entry.split("\t", 1)
        if meta.startswith("160000 ") and os.path.exists(os.path.join(path, rel, ".git")):
            found.append(rel)
    return found


def hidden_changes(path):
    """Tracked files marked skip-worktree or assume-unchanged whose work-tree file differs from the index
    (git status hides them; a sparse checkout's absent files are not changes)."""
    rows = []
    for entry in filter(None, out(path, "ls-files", "-v", "-s", "-z").split("\0")):
        meta, rel = entry.split("\t", 1)
        tag, mode, sha = meta.split(" ")[:3]
        if (tag == "S" or tag.islower()) and mode != "160000" and os.path.isfile(os.path.join(path, rel)):
            rows.append((rel, sha))
    if not rows:
        return []
    hashed = git(path, "hash-object", "--stdin-paths", stdin="".join(rel + "\n" for rel, _s in rows)).stdout.split()
    return [rel for (rel, sha), h in zip(rows, hashed) if h != sha]


def ignored_names(path, worktrees):
    """Ignored paths exactly as git reports them ('dir/' or 'file'), never one that is or holds a worktree."""
    names = []
    for x in git(path, "ls-files", "-o", "-i", "--exclude-standard", "--directory", "-z").stdout.split("\0"):
        full = os.path.join(path, x.rstrip("/"))
        if x and not any(norm(w) == norm(full) or inside(w, full) for w in worktrees):
            names.append(x)
    return names


def worktree_state(path, worktrees=()):
    """modified / untracked / staged-only / hidden (skip-worktree, assume-unchanged) paths, operations in
    progress, initialised submodules and ignored paths."""
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
        if xy == "??":                                       # a nested worktree is refused as such, not here
            st["untracked"] += [] if any(norm(w) == norm(os.path.join(path, rel)) for w in worktrees) else [rel]
        elif index_only(xy):
            st["staged_only"].append(rel)
        else:
            st["modified"].append(rel)
    g = out(path, "rev-parse", "--absolute-git-dir").strip()
    st["busy"] = [n for n in BUSY if os.path.exists(os.path.join(g, n))]
    st["submodules"] = submodules(path)
    st["own_refs"] = out(path, "for-each-ref", "--format=%(refname)", *[p.rstrip("/") for p in PER_WORKTREE]).split()
    st["hidden"] = hidden_changes(path)
    st["ignored"] = ignored_names(path, worktrees)
    return st


FIXES = {
    "modified": "commit it on a kept branch, or `git stash` it",
    "hidden": "`git update-index --no-skip-worktree --no-assume-unchanged <file>`, then commit or stash it",
    "untracked": "commit it, `git stash -u` it, or move the files out of the checkout",
    "staged-only": "commit the staged version, or unstage it",
    "in progress": "finish or abort it (`git <op> --continue` / `--abort`, `git bisect reset`)",
    "missing": "restore the folder, or `git worktree prune` it yourself first",
    "unborn": "commit on it there (`git commit --allow-empty -m start`), or switch to a branch with commits",
    "nested": "`git worktree move <path> <new path outside every worktree>` (unlock it first if locked)",
    "submodule": "in each, push every commit and commit or drop every change, then `git submodule deinit -f <sub>` "
                 "(its repository moves to the archive); after rehome, `git submodule update --init`",
    "per-worktree": "in that worktree, `git branch <name> <ref>`, then `git update-ref -d <ref>`",
    "unreached": "name it: `git branch <name>` in that worktree",
    "purged": "re-point it onto its rewritten counterpart (SKILL.md Step 6 item 2), or rebuild it without that "
              "content (`git update-ref <ref> <new> <old>`); the old tip stays in its reflog in the archive",
}


def refusal(path, problem, key):
    return {"path": path, "problem": problem, "fix": FIXES[key]}


def refusals_for(w):
    rows, path = [], w["path"]

    def add(problem, items, key):
        rows.append(refusal(path, "%s (%d): %s" % (problem, len(items), ", ".join(items[:5])), key))
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
    if w["hidden"]:
        add("local changes hidden by skip-worktree / assume-unchanged", w["hidden"], "hidden")
    if w["submodules"]:
        add("initialised submodule(s)", w["submodules"], "submodule")
    if w["own_refs"]:
        add("per-worktree ref(s)", w["own_refs"], "per-worktree")
    return rows


def config_entries(repo, pattern):
    r = git(repo, "config", "-z", "--get-regexp", pattern, check=False)
    return [list(e.split("\n", 1)) if "\n" in e else [e, ""] for e in r.stdout.split("\0") if e]


def unborn(w):
    return not w["head"] or set(w["head"]) == {"0"}


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
            inv["refusals"].append(refusal(w["path"], "worktree folder missing (prunable)", "missing"))
            continue
        containers = [p for p in paths if inside(w["path"], p)]
        if w["main"] and containers:
            raise Refuse("the main checkout is inside worktree %s" % containers[0])
        rec = {k: w[k] for k in ("path", "main", "head", "branch", "detached", "locked", "lock_reason")}
        rec["old"] = not unborn(w) and is_old(w["head"])
        rec.update(worktree_state(w["path"], paths))
        inv["worktrees"].append(rec)
        if containers:
            inv["refusals"].append(refusal(w["path"], "worktree nested inside %s" % max(containers, key=len),
                                           "nested"))
        if unborn(w):
            inv["refusals"].append(refusal(w["path"], "branch %s is unborn (no commit yet)" % w["branch"], "unborn"))
        inv["refusals"] += refusals_for(rec)
    for name, sha, commit, symref, peeled in list_refs(repo):         # the main worktree's own refs included
        if symref or name == "refs/stash":
            continue
        inv["refs"].append({"name": name, "sha": sha, "kind": ref_kind(name), "old": is_old.ref(sha, commit, peeled)})
    for r in inv["refs"]:
        r["carry"] = not r["old"] and r["kind"] not in ("remotes", "worktree")
    carried = [r for r in inv["refs"] if r["carry"]]
    for i, (sha, msg) in enumerate(stash_entries(repo)):
        old_entry = is_old(sha) or bool(objs and not objs.isdisjoint(objects_of(repo, [sha])))
        inv["stash"].append({"index": i, "sha": sha, "message": msg, "old": old_entry})
    inv["refusals"] += layout_refusals(repo, inv, carried, objs)
    inv["remotes"] = config_entries(repo, r"^remote\.")
    inv["branch_config"] = config_entries(repo, r"^branch\.")
    hp = git(repo, "config", "--get", "core.hooksPath", check=False).stdout.strip()
    inv["hooks_path"] = hp or None
    hooks = os.path.join(common_dir(repo), "hooks")
    inv["hooks"] = sorted(f for f in os.listdir(hooks) if not f.endswith(".sample")) if os.path.isdir(hooks) else []
    return inv


def layout_refusals(repo, inv, carried, objs):
    """Kept worktrees detached at a commit no carried ref reaches; carried refs that reach a listed old
    (purged) object."""
    rows, names = [], {r["name"] for r in carried}
    for w in inv["worktrees"]:
        if not w["old"] and w["detached"]:
            reach = out(repo, "for-each-ref", "--contains", w["head"], "--format=%(refname)").split()
            if names.isdisjoint(reach):
                rows.append(refusal(w["path"], "detached at %s, which no carried ref reaches" % w["head"],
                                    "unreached"))
    if objs and not objs.isdisjoint(objects_of(repo, [r["sha"] for r in carried])):
        for r in carried:
            n = len(objs & objects_of(repo, [r["sha"]]))
            if n:
                rows.append(refusal(repo, "ref %s reaches %d purged blob/tree/tag object(s)" % (r["name"], n),
                                    "purged"))
    return rows


def label(old):
    return "OLD " if old else "KEPT"


def print_inventory(inv):
    print("worktrees:")
    for w in inv["worktrees"]:
        flags = [w["branch"] or "detached@" + (w["head"] or "?")[:12]] + [k for k in ("main", "locked") if w[k]]
        flags += ["%s %d" % (k, len(w[k])) for k in ("modified", "untracked", "staged_only", "hidden", "busy",
                                                     "submodules", "own_refs") if w[k]]
        print("  %s  %s  [%s]" % (label(w["old"]), w["path"], ", ".join(flags)))
        if w["old"] and (w["modified"] or w["untracked"] or w["staged_only"]):
            print("        uncommitted changes here stay only in the archive")
        if w["ignored"]:
            print("        ignored, NOT carried (stays in the archive): %s" % ", ".join(w["ignored"]))
    print("refs:")
    for r in inv["refs"]:
        how = "" if r["old"] else "  carried" if r["carry"] else "  fresh from the clone"
        print("  %s  %-8s %s%s" % (label(r["old"]), r["kind"], r["name"], how))
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
        print("%d case(s) outside the supported layout: do what each REFUSED line says, then run inventory again"
              % len(inv["refusals"]))
        return 2
    return 0


# ---------------------------------------------------------------- rehome

def load_json(path, what, keys):
    """A JSON object holding every key, else Refuse (exit 2, never a traceback)."""
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise Refuse("%s is missing or not valid JSON: %s (%s)" % (what, path, type(exc).__name__))
    if not isinstance(data, dict) or any(k not in data for k in keys):
        raise Refuse("%s is incomplete (make it again): %s" % (what, path))
    return data


INV_KEYS = ("repo", "snapshot", "worktrees", "refs", "stash", "refusals", "remotes", "branch_config", "hooks_path",
            "old_commits")


@contextlib.contextmanager
def run_lock(repo):
    """<repo>.rehome.lock next to the checkout, created O_EXCL and held for the whole run: one rehome or
    restore at a time. An existing lock (another run, or a crashed one) is exit 4 and is never removed."""
    path = os.path.abspath(repo) + LOCK_SUFFIX
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise NotQuiet("%s exists: another rehome or restore is running on this checkout (or one crashed). "
                       "Make sure none is running, then move that file aside" % path)
    except OSError as exc:
        raise Refuse("cannot create the run lock %s (%s)" % (path, type(exc).__name__))
    try:
        os.write(fd, ("pid %d\n" % os.getpid()).encode("ascii"))
        os.close(fd)
        yield path
    finally:
        try:
            os.remove(path)                                   # this run's own lock file only
        except OSError:
            pass


def move_plan(inv, archive):
    """[(original, archived)] renames: every linked worktree (sorted), then main."""
    moves = []
    for w in sorted(inv["worktrees"], key=lambda w: norm(w["path"])):
        if not w["main"]:
            moves.append((w["path"], os.path.join(archive, "worktrees", "%d-%s" % (
                len(moves), os.path.basename(os.path.normpath(w["path"]))))))
    main = [w for w in inv["worktrees"] if w["main"]][0]
    return moves + [(main["path"], os.path.join(archive, "repo"))]


def archived_path(path, moves):
    """Where a path is after the moves [(was, now)] (it may be inside a moved folder)."""
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
        for src in [s for s, _d in done if s not in {x[0] for x in stuck}]:
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
    with contextlib.suppress(OSError):
        os.remove(os.path.join(archive, RECORD))              # this run's own record: nothing moved any more
    remove_empty_archive(archive)
    print("STOPPED: %s. Every rename was rolled back; the checkout matches the inventory again." % why)
    return EXIT_ROLLED_BACK


def remove_empty_archive(archive):
    for d in (os.path.join(archive, "worktrees"), archive):
        with contextlib.suppress(OSError):
            os.rmdir(d)                                       # only removes an EMPTY dir this run made


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


def resolve(base, target):
    return os.path.normpath(target if os.path.isabs(target) else os.path.join(base, target))


GITDIR_SKIP = {"objects", "refs", "logs", "hooks", "info", "lfs"}


def relink(pairs, here):
    """After the folders in pairs [(was, now)] moved, re-point every gitfile under them and core.worktree of
    every submodule repository under a git dir's modules/ (at any depth) at where its target now is: git writes
    relative paths, which break when a work tree and its repository moved apart. Returns the number rewritten."""
    back = [(b, a) for a, b in pairs]
    fixed, gitdirs = 0, []
    for _a, top in pairs:
        for root, dirs, files in os.walk(top):
            if ".git" in dirs:
                gitdirs.append(os.path.join(root, ".git"))
                dirs.remove(".git")
            if ".git" not in files:
                continue
            gitfile = os.path.join(root, ".git")
            with open(gitfile, encoding="utf-8", errors="surrogateescape") as fh:
                text = fh.read().strip()
            if not text.startswith("gitdir: "):
                continue
            target = text[len("gitdir: "):]
            want = archived_path(resolve(archived_path(root, back), target), pairs)
            if norm(resolve(root, target)) != norm(want):
                with open(gitfile, "r+", encoding="utf-8", newline="\n") as fh:   # "w" fails on a hidden file
                    fh.write("gitdir: %s\n" % os.path.relpath(want, root).replace(os.sep, "/"))
                    fh.truncate()
                fixed += 1
    for g in gitdirs:
        for root, dirs, files in os.walk(g):
            dirs[:] = [d for d in dirs if d not in GITDIR_SKIP]
            rel = os.path.relpath(root, g).replace(os.sep, "/").split("/")
            if "modules" not in rel or "HEAD" not in files or "config" not in files:
                continue
            cfg = os.path.join(root, "config")
            cw = git(here, "config", "--file", cfg, "--get", "core.worktree", check=False).stdout.strip()
            if not cw:
                continue
            want = archived_path(resolve(archived_path(root, back), cw), pairs)
            if norm(resolve(root, cw)) != norm(want):
                git(here, "config", "--file", cfg, "core.worktree", os.path.relpath(want, root).replace(os.sep, "/"))
                fixed += 1
    return fixed


def restore_config(inv, path):
    """Remotes, carried branches' config and core.hooksPath from the inventory."""
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


def hook_stub(path, archive):
    """When the checked-out new clone has no hooks: core.hooksPath -> <archive>/hooks-stub, whose pre-push
    refuses every push until the repo's hook installer runs. Returns the stub path, or None (hooks present)."""
    hooks = resolve(path, out(path, "rev-parse", "--git-path", "hooks").strip())
    if os.path.isdir(hooks) and any(not f.endswith(".sample") for f in os.listdir(hooks)):
        return None
    stub = os.path.join(archive, STUB)
    os.makedirs(stub)
    with open(os.path.join(stub, "pre-push"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("#!/bin/sh\necho \"local_cleanup rehome: this clone has no hooks yet; run the repo's hook installer "
                 "first (see %s)\" >&2\nexit 1\n" % os.path.join(archive, "REHOME.md").replace(os.sep, "/"))
    os.chmod(os.path.join(stub, "pre-push"), 0o755)
    git(path, "config", "core.hooksPath", stub)
    return stub


def prepare_clone(inv, archived_repo, path):
    """In the staging clone: fetch the kept refs (explicit refspecs) and the kept stash entries through temp
    refs, store the stash entries (oldest first), check the main worktree out clean, delete the temp refs."""
    specs = ["+%s:%s" % (r["name"], r["name"]) for r in inv["refs"] if r["carry"]]
    temp = [("%s%d" % (TMP_NS, i), e["sha"]) for i, e in enumerate(inv["stash"]) if not e["old"]]
    specs += ["+%s:%s" % (sha, name) for name, sha in temp]
    if specs:
        git(path, "fetch", "--no-tags", "--update-head-ok", "--no-write-fetch-head", "--no-recurse-submodules",
            "--stdin", archived_repo, stdin="".join(s + "\n" for s in specs))
    for e in reversed(inv["stash"]):
        if not e["old"]:
            git(path, "stash", "store", "-q", "-m", e["message"], e["sha"])
    main = [w for w in inv["worktrees"] if w["main"]][0]
    if main["old"]:                       # never on a branch a kept worktree may need; HEAD after the fetch
        git(path, "checkout", "-q", "-f", "--detach", "HEAD")
    elif main["branch"]:
        git(path, "checkout", "-q", "-f", main["branch"][len("refs/heads/"):])
    else:
        git(path, "checkout", "-q", "-f", "--detach", main["head"])
    if temp:
        git(path, "update-ref", "--stdin", stdin="start\n" + "".join(
            "delete %s %s\n" % (name, sha) for name, sha in temp) + "commit\n")


def add_worktrees(inv, path):
    """Kept linked worktrees at their paths, re-locked with their reason."""
    for w in inv["worktrees"]:
        if w["main"] or w["old"]:
            continue
        if w["branch"]:
            git(path, "worktree", "add", "-q", w["path"], w["branch"][len("refs/heads/"):])
        else:
            git(path, "worktree", "add", "-q", "--detach", w["path"], w["head"])
        if w["locked"]:
            git(path, "worktree", "lock", *(["--reason", w["lock_reason"]] if w["lock_reason"] else []), w["path"])


def reflogs(path):
    """{relpath: sha256} of every reflog of the new clone's main worktree and its shared refs."""
    base = os.path.join(path, ".git", "logs")
    return {rel: sha256_file(os.path.join(base, rel)) for rel in walk_files(base)}


def overlap_counts(repo, old, objs):
    listing = out(repo, "cat-file", "--batch-all-objects", "--batch-check=%(objecttype) %(objectname)")
    commits, others = set(), set()
    for line in listing.splitlines():
        typ, _, sha = line.partition(" ")
        (commits if typ == "commit" else others).add(sha)
    return len(commits & old), len(others & objs)


def verify(inv, path, logs):
    """Problems found in the new clone (empty list = verified)."""
    bad = []
    old_path = inv["old_commits"]
    n_c, n_o = overlap_counts(path, read_old(old_path), read_old_objects(old_path))
    if n_c or n_o:
        bad.append("overlap: %d old commit(s) and %d old blob/tree/tag object(s) in the new clone" % (n_c, n_o))
    for r in inv["refs"]:
        if r["carry"]:
            got = git(path, "rev-parse", "--verify", "-q", r["name"], check=False).stdout.strip()
            if got != r["sha"]:
                bad.append("ref %s is %s, expected %s" % (r["name"], got or "missing", r["sha"]))
    want = [e["sha"] for e in inv["stash"] if not e["old"]]
    have = git(path, "reflog", "show", "--format=%H", "refs/stash", "--", check=False).stdout.split()
    if have != want:
        bad.append("stash list differs from the kept entries")
    listed = {norm(w["path"]): w for w in list_worktrees(path)}
    for w in inv["worktrees"]:
        if w["old"] and not w["main"]:
            continue
        now = listed.get(norm(w["path"]))
        if not now or (not w["old"] and (now["head"] != w["head"] or now["branch"] != w["branch"] or
                                         (now["locked"], now["lock_reason"]) != (w["locked"], w["lock_reason"]))):
            bad.append("worktree %s is not at its recorded HEAD/branch/lock" % w["path"])
            continue
        st = worktree_state(w["path"])
        if st["modified"] or st["untracked"] or st["staged_only"]:
            bad.append("worktree %s is not clean" % w["path"])
    changed = diff_keys(logs, reflogs(path))
    if changed:
        bad.append("the new clone's reflogs changed after it was moved into place (a session is using it): %s"
                   % ", ".join(changed[:5]))
    return bad


def at(base, rel):
    """An ignored path rel ('dir/' or 'file', '/'-separated) under base, a folder keeping its trailing separator."""
    return os.path.join(base, os.path.normpath(rel)) + (os.sep if rel.endswith("/") else "")


def write_rehome_md(inv, archive, moves, url, result, stub):
    carried = [r for r in inv["refs"] if r["carry"]]
    lines = ["# Rehome record", "", "Result: %s" % result, "", "Clone URL (purged remote): %s" % url, "",
             "## What moved where (renames only; nothing was deleted)", ""]
    for w in inv["worktrees"]:
        lines.append("- %s %s -> %s" % (label(w["old"]).strip(), w["path"], archived_path(w["path"], moves)))
    lines += ["", "## Carried into the new clone", ""]
    lines += ["- %s %s" % (r["name"], r["sha"]) for r in carried]
    lines += ["- stash entry %s" % e["sha"] for e in inv["stash"] if not e["old"]]
    lines += ["- worktree %s" % w["path"] for w in inv["worktrees"] if not w["old"] and not w["main"]]
    main = [w for w in inv["worktrees"] if w["main"]][0]
    if main["old"]:
        lines += ["", "The main checkout was on old history: the new clone's main worktree is detached at the "
                  "clone's HEAD; `git switch <branch>` there."]
    lines += ["", "## Hooks", "", "The new clone has no hooks, so core.hooksPath points at %s, whose pre-push "
              "refuses every push. Run the repo's hook installer once on the new clone; when the installer does not "
              "set core.hooksPath itself, then run `git config --unset core.hooksPath` there." % stub if stub else
              "core.hooksPath (%s) holds hooks in the new clone." % inv["hooks_path"],
              "The checkout's core.hooksPath was: %s. Its hooks stay in the archived copy." % (
                  inv["hooks_path"] or "(unset)")]
    lines += ["", "## Ignored files left in the archive (NOT in the new clone)", ""]
    ign = [at(archived_path(w["path"], moves), n) for w in inv["worktrees"] for n in w["ignored"]]
    lines += ["- %s" % p for p in ign] or ["- none"]
    lines += ["", "Copy back only the files the repo's tools need, one named path at a time, before resuming "
              "sessions or scheduled jobs (ora-skills: `_staging/` and `tools/real-identifiers.local.json`).",
              "Never copy a `.git` file or a whole worktree folder back: the new clone's worktree would then "
              "point at the archive.", "",
              "Everything else (old refs, reflogs, unreachable objects, hooks, other config, ORIG_HEAD/FETCH_HEAD, "
              "submodule repositories, per-worktree refs of old worktrees) is only in the archived copy.", "",
              "## How to restore", "",
              "Stop every session using %s, then run `python -I local_cleanup.py restore %s --exclusive`. It "
              "moves the new clone and its re-created worktrees aside into this archive dir, renames every "
              "archived folder back, runs `git worktree repair`, re-points every gitfile and submodule "
              "`core.worktree`, and compares the result with the inventory (exit 0 = identical)." % (
                  inv["repo"], archive), "",
              "By hand, the same steps:", "",
              "1. Stop every session using %s." % inv["repo"],
              "2. Rename the new clone and its re-created worktrees aside (into this archive dir; never delete).",
              "3. Rename each archived folder above back to its original path.",
              "4. In %s run `git worktree repair` with every linked worktree path." % inv["repo"],
              "5. Submodule `.git` files and each submodule repository's `core.worktree` (in its config under "
              "`.git/modules/` or `.git/worktrees/<id>/modules/`) were re-pointed at the archive (relative "
              "paths): after renaming back, point each `.git` file at its repository and each `core.worktree` "
              "at its submodule folder again.", ""]
    with open(os.path.join(archive, "REHOME.md"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))


def cmd_rehome(a):
    require_repo(a.repo)
    inv = load_json(a.inv, "the inventory", INV_KEYS)
    if norm(inv["repo"]) != norm(a.repo):
        raise Refuse("the inventory is for another checkout: %s" % inv["repo"])
    if inv["refusals"]:
        raise Refuse("the inventory has %d REFUSED case(s): resolve them and run inventory again"
                     % len(inv["refusals"]))
    check_archive_dir(inv, a.archive_dir, a.clone_url)
    if not a.exclusive:
        raise NotQuiet("--exclusive not given: stop every session, IDE and scheduled job that uses this "
                       "checkout and its worktrees, then pass --exclusive")
    with run_lock(a.repo):
        return rehome_locked(a, inv)


def move_and_clone(a, inv, moves, staging):
    """Renames, repair, clone. Returns None when the clone is in staging, else the rollback's exit code. Any
    exception (Ctrl+C included) rolls every rename back first, then is raised again."""
    archive, repo, done, repaired, why = a.archive_dir, a.repo, [], False, None
    try:
        for src, dst in moves:
            try:
                os.rename(src, dst)
            except OSError as exc:
                why = "rename of %s failed (%s): close whatever holds it open (shell, editor, fsmonitor)" % (
                    src, type(exc).__name__)
                break
            done.append((src, dst))
        if why is None:
            archived_repo = os.path.join(archive, "repo")
            linked = [archived_path(w["path"], moves) for w in inv["worktrees"] if not w["main"]]
            repaired = True
            r = git(archived_repo, "worktree", "repair", *linked, check=False)
            rows = {norm(w["path"]): w for w in list_worktrees(archived_repo)} if r.returncode == 0 else {}
            if r.returncode != 0 or not all(norm(p) in rows and not rows[norm(p)]["prunable"] for p in linked):
                why = "`git worktree repair` in the archive failed"
        if why is None:
            rc = git(archive, "clone", "-q", "--no-recurse-submodules", a.clone_url, staging, check=False).returncode
            if rc != 0:
                why = "clone failed (exit %d)%s" % (rc, set_leftover_aside(archive, staging))
    except BaseException as exc:
        rollback(repo, inv, archive, done, repaired, "%s%s" % (type(exc).__name__, set_leftover_aside(archive,
                                                                                                   staging)))
        raise
    return None if why is None else rollback(repo, inv, archive, done, repaired, why)


def set_leftover_aside(archive, staging):
    """Move a partial clone to <archive>/failed-clone (never deleted). Returns a note for the message."""
    if os.path.exists(staging):
        with contextlib.suppress(OSError):
            os.rename(staging, os.path.join(archive, "failed-clone"))
    left = [p for p in (staging, os.path.join(archive, "failed-clone")) if os.path.exists(p)]
    return "; its leftover is in %s" % left[0] if left else ""


def rehome_locked(a, inv):
    archive, repo = a.archive_dir, a.repo
    changed = diff_keys(inv["snapshot"], quiet_gate(repo, a))
    if changed:
        raise NotQuiet("the checkout changed since the inventory: run inventory again (and find who changed it)",
                       changed)
    moves = move_plan(inv, archive)
    os.makedirs(os.path.join(archive, "worktrees"))
    changed = diff_keys(inv["snapshot"], snapshot(repo))
    if changed:
        remove_empty_archive(archive)
        raise NotQuiet("the checkout changed after the quiet window, right before the first rename: something "
                       "is still writing; find and stop it", changed)
    with open(os.path.join(archive, RECORD), "w", encoding="utf-8", newline="\n") as fh:   # before any rename
        json.dump({"repo": repo, "moves": moves, "clone_url": a.clone_url, "inv": inv}, fh, indent=1)
    staging = os.path.join(archive, STAGING)
    rc = move_and_clone(a, inv, moves, staging)
    if rc is not None:
        return rc
    archived_repo = os.path.join(archive, "repo")
    where, bad, stub = staging, [], None
    try:
        relink(moves, archive)
        restore_config(inv, staging)
        prepare_clone(inv, archived_repo, staging)
        stub = hook_stub(staging, archive)
        logs = reflogs(staging)
        if os.path.lexists(repo):
            raise FileExistsError(repo)
        os.rename(staging, repo)                             # fails if anything recreated the path meanwhile
        where = repo
        add_worktrees(inv, repo)
        bad = verify(inv, repo, logs)
    except (subprocess.CalledProcessError, OSError) as exc:
        if where == staging and os.path.lexists(repo):
            bad = ["%s was recreated while the new clone was prepared (something is still using it); nothing "
                   "there was touched; the new clone is in %s" % (repo, staging)]
        else:
            bad = ["%s: %s" % (type(exc).__name__, " ".join(getattr(exc, "cmd", []) or [str(exc)]))]
    write_rehome_md(inv, archive, moves, a.clone_url, "FAILED: " + "; ".join(bad) if bad else "verified", stub)
    print("archived copy: %s (worktrees in %s); record: %s" % (archived_repo, os.path.join(archive, "worktrees"),
                                                             os.path.join(archive, "REHOME.md")))
    if bad:
        print("AFTER THE CLONE (exit 5): the archived copy in %s is complete; the new clone at %s is not "
              "verified:" % (archive, where))
        for b in bad:
            print("  " + b)
        print("Fix the cause, or restore the archive (local_cleanup.py restore %s --exclusive). Never delete the "
              "archive." % archive)
        return EXIT_AFTER_CLONE
    print("carried: %d ref(s), %d stash entr%s, %d worktree(s); overlap 0; every carried ref at its SHA" % (
        sum(r["carry"] for r in inv["refs"]), sum(not e["old"] for e in inv["stash"]),
        "y" if sum(not e["old"] for e in inv["stash"]) == 1 else "ies",
        sum(1 for w in inv["worktrees"] if not w["old"] and not w["main"])))
    ign = sum(len(w["ignored"]) for w in inv["worktrees"])
    if ign:
        print("ignored paths NOT carried: %d (listed in REHOME.md); copy back only the named files the repo's tools "
              "need, never a `.git` file or a worktree folder" % ign)
    print("hooks were NOT copied: core.hooksPath now points at %s, whose pre-push refuses every push; run the repo's "
          "hook installer once on the new clone (see REHOME.md)" % stub if stub else "hooks were NOT copied: "
          "core.hooksPath (%s) holds hooks in the new clone" % inv["hooks_path"])
    return 0


# ---------------------------------------------------------------- restore

def cmd_restore(a):
    archive = a.archive_dir
    rec = load_json(os.path.join(archive, RECORD), "the rehome record", ("repo", "moves", "inv"))
    inv = rec["inv"]
    if not isinstance(inv, dict) or any(k not in inv for k in INV_KEYS):
        raise Refuse("the rehome record is incomplete: %s" % os.path.join(archive, RECORD))
    if not a.exclusive:
        raise NotQuiet("--exclusive not given: stop every session, IDE and scheduled job that uses the new clone "
                       "and its worktrees, then pass --exclusive")
    with run_lock(rec["repo"]):
        return restore_locked(archive, rec["repo"], [tuple(m) for m in rec["moves"]], inv)


def restore_locked(archive, repo, moves, inv):
    moved = [(s, d) for s, d in moves if os.path.isdir(d)]
    missing = [d for s, d in moves if not os.path.isdir(d) and not os.path.isdir(s)]
    if missing:
        raise Refuse("archived folder(s) missing: %s" % ", ".join(missing))
    aside_src = []
    if len(moved) == len(moves):                              # every rename was done: a new clone may exist
        aside_src = [w["path"] for w in inv["worktrees"] if not w["old"] and not w["main"] and
                     os.path.lexists(w["path"])] + ([repo] if os.path.lexists(repo) else [])
    blocked = [s for s, _d in moved if os.path.lexists(s) and norm(s) not in {norm(x) for x in aside_src}]
    if blocked:
        raise Refuse("in the way, and not the new clone or one of its worktrees (move it aside yourself): %s"
                     % ", ".join(blocked))
    n = 0
    while os.path.exists(os.path.join(archive, "restored-aside-%d" % n)):
        n += 1
    aside = os.path.join(archive, "restored-aside-%d" % n)
    os.makedirs(os.path.join(aside, "worktrees"))
    aside_wts = [(p, os.path.join(aside, "worktrees", "%d-%s" % (i, os.path.basename(os.path.normpath(p)))))
                 for i, p in enumerate(aside_src) if norm(p) != norm(repo)]
    plan = aside_wts + ([(repo, os.path.join(aside, "repo"))] if repo in aside_src else [])
    plan += [(dst, src) for src, dst in reversed(moved)]
    done = []
    for src, dst in plan:
        try:
            os.rename(src, dst)
        except OSError as exc:
            stuck = []
            for s, d in reversed(done):
                try:
                    os.rename(d, s)
                except OSError:
                    stuck.append((s, d))
            print("STOPPED: rename of %s failed (%s): close whatever holds it open." % (src, type(exc).__name__))
            if stuck:
                for s, d in stuck:
                    print("  %s is now at %s (rename back failed)" % (s, d))
                return EXIT_ROLLBACK_FAILED
            print("Every rename of this restore was undone.")
            return EXIT_ROLLED_BACK
        done.append((src, dst))
    if os.path.isdir(os.path.join(aside, "repo")):           # keep the set-aside clone usable too
        git(os.path.join(aside, "repo"), "worktree", "repair", *[d for _s, d in aside_wts], check=False)
    git(repo, "worktree", "repair", *[w["path"] for w in inv["worktrees"] if not w["main"]], check=False)
    relink([(dst, src) for src, dst in moved], archive)
    print("restored %s and %d linked worktree folder(s); the new clone (if any) is in %s" % (
        repo, sum(1 for s, _d in moved if norm(s) != norm(repo)), aside))
    changed = diff_keys(inv["snapshot"], snapshot(repo))
    if changed:
        print("the restored checkout differs from the inventory:")
        show_keys(changed)
        return 1
    print("the restored checkout matches the inventory")
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
        fh.write("".join(s + "\n" for s in old) if old else ZERO_MARK + "\n")
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
    c = sub.add_parser("restore")
    c.add_argument("archive_dir", help="the archive dir a rehome wrote (holds rehome.json)")
    c.add_argument("--exclusive", action="store_true",
                   help="every session, IDE and scheduled job using the new clone and its worktrees is stopped")
    c.set_defaults(fn=cmd_restore)
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
