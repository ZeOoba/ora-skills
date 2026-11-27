"""Find local copies that still hold purged ("old") history and print the manual Step 6 commands for them.

  python -I local_cleanup.py changed <purged.git> <backup.git> [<backup2.git> ...] --out <old-commits.txt>
  python -I local_cleanup.py inventory <repo> <old-commits.txt> --out <inv.json> [--archive <dir>] [--clone-url <url>]
  python -I local_cleanup.py overlap <repo> <old-commits.txt>
  python -I local_cleanup.py check-unchanged <repo> <digest>
  python -I local_cleanup.py check-new-clone <repo> <inv.json> <digest>

Paths are resolved against the current directory (a relative local remote.origin.url against <repo>, as git
does). Nothing here moves, deletes or writes into a checkout. Output is UTF-8 whatever the console code page.

"Old history" = reaches a commit the purge CHANGED or DROPPED (in any backup, not in the purged copy). A clean
first commit keeps its SHA, so branches sharing only that root are NOT old; neither is an orphan branch.

changed    writes the sorted old set (exit 1 if empty: the file then holds only a "0 commits" marker, the one
           empty form accepted; an empty or malformed file is refused, exit 2) and <out>.objects, the
           changed/dropped blobs, trees and tag objects, read by inventory and overlap.
inventory  READ-ONLY. Classifies every worktree, ref and stash entry OLD or KEPT, names each worktree's ignored
           paths exactly as git reports them, and refuses (exit 2, a REFUSED line each with the manual fix)
           every layout the Step 6 procedure does not cover. With --archive (an absent folder outside every
           worktree, on the same volume) it also prints the Step 6 commands built from this inventory: the
           digest re-check, the moves into the archive, `git clone`, the push-URL freeze, one fetch per kept
           ref, the kept stash entries, the kept worktrees, then Undo A (stopped in 6.3) and Undo B (git clone
           ran). It runs none of them. --clone-url defaults to remote.origin.url and must be the PURGED remote.
overlap    old commits (and listed old objects) in the object store: exit 0 when 0, else 1.
check-unchanged  READ-ONLY. Exit 0 when the checkout's worktrees, refs, stash entries and uncommitted files
           still match the digest inventory printed, else 1 (the first 6.3 line).
check-new-clone  READ-ONLY. Exit 0 when <repo> is the new clone as the 6.4 lines leave it (any stop point): only
           carried refs, kept stash entries and kept worktrees, nothing committed, added or edited; else 1.
           Undo B runs it before setting the new clone aside. Exit 2 when <inv.json> is not the one the undo
           was printed with.

Prints counts, ref names and paths only, never file contents.
Exit codes: 0 ok, 1 work left/found, 2 bad input or REFUSED.
"""
import argparse
import codecs
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import time

SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
DIGEST_RE = re.compile(r"^[0-9a-f]{20}$")
BUSY = ("rebase-merge", "rebase-apply", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "BISECT_START",
        "sequencer")
PER_WORKTREE = ("refs/worktree/", "refs/bisect/", "refs/rewritten/")
ZERO_MARK = "# local_cleanup changed: 0 commits"     # the only empty old-commits file inventory accepts
FROZEN = "DISABLED-history-purge-new-clone"          # the new clone's pushurl (its clone line sets it): its identity
BEGIN, END = "# --- Step 6 commands (printed, not run) ---", "# --- end ---"
UNDO_A = "# --- Undo A: you stopped in 6.3 (git clone has not run) ---"
UNDO_B = "# --- Undo B: git clone has run (6.4 started); only before anyone works in the new clone ---"
MSG_A = "Undo A refused: git clone has run (the archive and the checkout path both exist); run Undo B"
MSG_B1 = "Undo B refused: the archived checkout is missing"
MSG_B2 = "Undo B refused: the checkout path is not the new clone (remote.origin.pushurl is not %s)" % FROZEN


class Refuse(Exception):
    """Bad input: exit 2, nothing changed."""


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


def unquote_c(text):
    """git C-quotes a porcelain value holding a tab, newline, quote or backslash ("a\\tb"); return it as stored."""
    if len(text) < 2 or text[0] != '"' or text[-1] != '"':
        return text
    raw = codecs.escape_decode(text[1:-1].encode("utf-8", "surrogateescape"))[0]
    return raw.decode("utf-8", "surrogateescape")


def list_worktrees(repo):
    blocks, cur = [], None
    for line in out(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            cur = {"path": os.path.normpath(line[9:]), "head": None, "branch": None, "detached": False, "bare": False,
                   "locked": False, "lock_reason": "", "prunable": False}
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
            cur["locked"], cur["lock_reason"] = True, unquote_c(line[7:])
        elif line.startswith("prunable"):
            cur["prunable"] = True
    for i, w in enumerate(blocks):
        w["main"] = i == 0
    return blocks


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
    "hidden": "`git update-index --no-skip-worktree <file>`, then `git update-index --no-assume-unchanged <file>`, "
              "then commit or `git stash` it",
    "untracked": "commit it, `git stash -u` it, or move the files out of the checkout",
    "staged-only": "commit the staged version, or unstage it",
    "in progress": "finish or abort it there: `git <op> --continue` or `git <op> --abort` (<op> = rebase, merge, "
                   "cherry-pick or revert), or `git bisect reset`",
    "missing": "restore the folder, or `git worktree prune` it yourself first",
    "unborn": "commit on it there (`git commit --allow-empty -m start`), or switch to a branch with commits",
    "nested": "`git worktree move -f -f <path> <new path outside every worktree>` (keeps a lock and its reason)",
    "main nested": "move the main folder out of it (`mv <main> <new path outside every worktree>`), run "
                   "`git worktree repair` in the moved folder, then run inventory on the new path",
    "submodule": "in each, push every commit and commit or drop every change, then `git submodule deinit <sub>` "
                 "(it refuses while the submodule has changes; its repository moves to the archive); after Step 6, "
                 "`git submodule update --init`",
    "per-worktree": "in that worktree, `git branch <name> <ref>`, then `git update-ref -d <ref>`",
    "unreached": "name it: `git branch <name>` in that worktree",
    "purged": "re-point it onto its rewritten counterpart (SKILL.md Step 6 item 0b), or rebuild it without that "
              "content (`git update-ref <ref> <new> <old>`); the old tip stays in its reflog in the archive",
    "worktree hooks": "in that worktree, `git config --worktree --unset core.hooksPath` (the shared core.hooksPath "
                      "then applies there, as install_hooks.py requires; after the move it names the archive's hooks)",
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


def worktree_hooks_path(repo, path):
    """The worktree's own core.hooksPath (config.worktree, read only when extensions.worktreeConfig is on: it
    then beats the shared value, which Step 6.3 re-points at the archive's hooks), or None."""
    on = git(repo, "config", "--type=bool", "--get", "extensions.worktreeConfig", check=False).stdout.strip()
    if on != "true":
        return None
    r = git(path, "config", "--worktree", "--get-all", "core.hooksPath", check=False)
    return r.stdout.strip() if r.returncode == 0 else None


def state_text(repo):
    """What Step 6 must find unchanged since inventory: every worktree (path, HEAD, branch, lock), every ref
    (each worktree's own refs included), every stash entry, and each worktree's uncommitted files."""
    parts = ["worktrees\0" + out(repo, "worktree", "list", "--porcelain"),
             "refs\0" + out(repo, "for-each-ref", "--format=%(objectname) %(refname) %(symref)"),
             "stash\0" + "\0".join("%s %s" % e for e in stash_entries(repo))]
    for w in list_worktrees(repo):
        if os.path.isdir(w["path"]):
            own = out(w["path"], "for-each-ref", "--format=%(objectname) %(refname)",
                      *[p.rstrip("/") for p in PER_WORKTREE])
            status = git(w["path"], "status", "--porcelain=v1", "-uall", "-z").stdout
            parts.append("worktree %s\0%s\0%s" % (w["path"], own, status))
    return "\0\0".join(parts)


def state_digest(repo):
    return hashlib.sha256(state_text(repo).encode("utf-8", "surrogateescape")).hexdigest()[:20]


def check_main(repo):
    """<repo> is the main worktree's top folder and holds its git dir; returns the worktree list."""
    wts = list_worktrees(repo)
    main = wts[0]
    if norm(common_dir(repo)) != norm(os.path.join(main["path"], ".git")):
        raise Refuse("the git dir is not <repo>/.git (separate git dir): moving the folder would not move it")
    if main["bare"] or norm(main["path"]) != norm(repo):
        raise Refuse("give the main worktree's top folder (%s), not a linked worktree or a subfolder" % main["path"])
    return wts


def build_inventory(repo, old, objs):
    is_old = OldTest(repo, old, objs)
    wts = check_main(repo)
    inv = {"repo": os.path.abspath(repo), "created": time.time(), "worktrees": [], "refs": [], "stash": [],
           "refusals": []}
    paths = [w["path"] for w in wts]
    for w in wts:
        if w["prunable"] or not os.path.isdir(w["path"]):
            inv["refusals"].append(refusal(w["path"], "worktree folder missing (prunable)", "missing"))
            continue
        containers = [p for p in paths if inside(w["path"], p)]
        rec = {k: w[k] for k in ("path", "main", "head", "branch", "detached", "locked", "lock_reason")}
        rec["old"] = not unborn(w) and is_old(w["head"])
        rec.update(worktree_state(w["path"], paths))
        inv["worktrees"].append(rec)
        if containers and w["main"]:
            inv["refusals"].append(refusal(w["path"], "the main checkout is inside worktree %s"
                                           % max(containers, key=len), "main nested"))
        elif containers:
            inv["refusals"].append(refusal(w["path"], "worktree nested inside %s" % max(containers, key=len),
                                           "nested"))
        if unborn(w):
            inv["refusals"].append(refusal(w["path"], "branch %s is unborn (no commit yet)" % w["branch"], "unborn"))
        own_hp = worktree_hooks_path(repo, w["path"])
        if own_hp is not None:                               # old or kept: an archived worktree runs hooks too
            inv["refusals"].append(refusal(w["path"], "per-worktree core.hooksPath %s (config.worktree)"
                                           % (own_hp or '""'), "worktree hooks"))
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


def inventory_lines(inv):
    lines = ["worktrees:"]
    for w in inv["worktrees"]:
        flags = [w["branch"] or "detached@" + (w["head"] or "?")[:12]] + [k for k in ("main", "locked") if w[k]]
        flags += ["%s %d" % (k, len(w[k])) for k in ("modified", "untracked", "staged_only", "hidden", "busy",
                                                     "submodules", "own_refs") if w[k]]
        lines.append("  %s  %s  [%s]" % (label(w["old"]), w["path"], ", ".join(flags)))
        if w["old"] and (w["modified"] or w["untracked"] or w["staged_only"]):
            lines.append("        uncommitted changes here stay only in the archive")
        if w["ignored"]:
            lines.append("        ignored, NOT carried (stays in the archive): %s" % ", ".join(w["ignored"]))
    lines.append("refs:")
    for r in inv["refs"]:
        how = "" if r["old"] else "  carried" if r["carry"] else "  fresh from the clone"
        lines.append("  %s  %-8s %s%s" % (label(r["old"]), r["kind"], r["name"], how))
    for e in inv["stash"]:
        lines.append("  %s  stash    stash@{%d}" % (label(e["old"]), e["index"]))
    lines.append("remotes: %d config entr%s; core.hooksPath: %s" % (
        len(inv["remotes"]), "y" if len(inv["remotes"]) == 1 else "ies", inv["hooks_path"] or "(default)"))
    lines.append("old refs: %d, kept refs carried: %d, stash entries kept: %d of %d" % (
        sum(r["old"] for r in inv["refs"]), sum(r["carry"] for r in inv["refs"]),
        sum(not e["old"] for e in inv["stash"]), len(inv["stash"])))
    lines.append("state digest (the first 6.3 line re-checks it): %s" % inv["digest"])
    for x in inv["refusals"]:
        lines.append("REFUSED %s: %s -> %s" % (x["path"], x["problem"], x["fix"]))
    return lines


def check_writable(lines):
    """Every printed line must be written exactly as UTF-8. A name git gave as bytes that are not UTF-8 (kept
    as surrogates) cannot be, and a printed command holding a mangled name would act on another path or ref."""
    for n, line in enumerate(lines, 1):
        try:
            line.encode("utf-8", "strict")
        except UnicodeEncodeError:
            raise Refuse("output line %d holds a path, ref name or stash message that is not valid UTF-8 and "
                         "cannot be printed exactly: rename it, then run inventory again" % n)


# ---------------------------------------------------------------- Step 6 commands (printed, never run)

def q(s):
    return shlex.quote(s)


def remote_names(inv):
    """Remote names in config order (from remote.<name>.url entries)."""
    names = []
    for key, _v in inv["remotes"]:
        if key.endswith(".url") and key[len("remote."):-len(".url")] not in names:
            names.append(key[len("remote."):-len(".url")])
    return names


def archived_hooks_path(inv, archive):
    """The archive's own core.hooksPath when the checkout's is an absolute path inside it (install_hooks.py sets
    <repo>/.git/ora-hooks): after the move it would name the NEW clone's hooks. Else None."""
    hp = inv["hooks_path"]
    if not hp or not os.path.isabs(hp) or not (norm(hp) == norm(inv["repo"]) or inside(hp, inv["repo"])):
        return None
    return os.path.join(archive, "repo", os.path.relpath(os.path.abspath(hp), inv["repo"]))


def self_command():
    """How the printed lines call this script: this interpreter, isolated mode, this file (absolute)."""
    return "%s -I %s" % (q(sys.executable), q(os.path.abspath(__file__)))


def new_clone_expected(inv):
    """What the 6.4 lines create in the new clone; check-new-clone accepts any stop point within them."""
    main = [w for w in inv["worktrees"] if w["main"]][0]
    return {"repo": inv["repo"],
            "refs": {r["name"]: r["sha"] for r in inv["refs"] if r["carry"]},
            "stash": [e["sha"] for e in reversed(inv["stash"]) if not e["old"]],          # oldest first
            "worktrees": {w["path"]: {"branch": w["branch"], "head": w["head"]}
                          for w in inv["worktrees"] if not w["main"] and not w["old"]},
            "main_head": main["head"] if not main["old"] and not main["branch"] else None}


def expected_digest(exp):
    return hashlib.sha256(json.dumps(exp, sort_keys=True).encode("utf-8", "surrogateescape")).hexdigest()[:20]


def step6_commands(inv, archive, url, inv_path):
    """(commands, Undo A, Undo B) as shell lines; '#' lines are comments. Every undo line is guarded so it is safe
    at the point where the operator stopped: a folder moves back only from the archive and only to an empty place;
    the new clone is set aside only once its pushurl marker and check-new-clone confirm it, untouched."""
    repo, A = inv["repo"], archive
    main = [w for w in inv["worktrees"] if w["main"]][0]
    linked = sorted((w for w in inv["worktrees"] if not w["main"]), key=lambda w: norm(w["path"]))
    moved = [(w, os.path.join(A, "worktrees", "%d-%s" % (i, os.path.basename(os.path.normpath(w["path"])))))
             for i, w in enumerate(linked)]
    arepo, g = os.path.join(A, "repo"), "git -C %s " % q(repo)
    cmds = ["# 6.3 move every worktree folder and the main checkout into the archive (never delete)",
            "%s check-unchanged %s %s" % (self_command(), q(repo), inv["digest"]),
            "mkdir -p %s" % q(os.path.join(A, "worktrees"))]
    cmds += ["mv %s %s" % (q(w["path"]), q(dst)) for w, dst in moved]
    cmds.append("mv %s %s" % (q(repo), q(arepo)))
    if moved:
        cmds.append("git -C %s worktree repair %s" % (q(arepo), " ".join(q(d) for _w, d in moved)))
    ahp = archived_hooks_path(inv, A)
    if ahp:
        cmds.append("git -C %s config core.hooksPath %s" % (q(arepo), q(ahp)))
    cmds += ["# 6.4 clone the purged remote, freeze its pushes, bring the kept work across",
             "git clone --no-local --no-checkout --config %s %s %s" % (
                 q("remote.origin.pushurl=" + FROZEN), q(url), q(repo))]
    urls = {k: v for k, v in inv["remotes"]}
    for name in remote_names(inv):
        if name != "origin":
            cmds.append(g + "remote add %s %s" % (q(name), q(urls["remote.%s.url" % name])))
    for name in ["origin"] + [n for n in remote_names(inv) if n != "origin"]:
        cmds.append(g + "config --replace-all %s %s" % (q("remote.%s.pushurl" % name), FROZEN))
    for r in inv["refs"]:
        if r["carry"]:
            cmds.append(g + "fetch --no-tags --update-head-ok %s %s" % (q(arepo), q("+%s:%s" % (r["name"], r["name"]))))
    for e in reversed(inv["stash"]):                       # oldest first: the newest ends up as stash@{0}
        if not e["old"]:
            cmds.append(g + "fetch --no-tags %s %s" % (q(arepo), e["sha"]))
            cmds.append(g + "stash store -m %s %s" % (q(e["message"]), e["sha"]))
    if main["old"]:
        cmds.append(g + "checkout -f --detach")
    elif main["branch"]:
        cmds.append(g + "checkout -f %s" % q(main["branch"][len("refs/heads/"):]))
    else:
        cmds.append(g + "checkout -f --detach %s" % main["head"])
    carried = {r["name"][len("refs/heads/"):] for r in inv["refs"] if r["carry"] and r["kind"] == "heads"}
    for key, value in inv["branch_config"]:
        b, _dot, field = key[len("branch."):].rpartition(".")
        if b in carried and field in ("remote", "merge"):
            cmds.append(g + "config %s %s" % (q(key), q(value)))
    for w, _dst in moved:
        if w["old"]:
            continue
        if w["branch"]:
            cmds.append(g + "worktree add %s %s" % (q(w["path"]), q(w["branch"][len("refs/heads/"):])))
        else:
            cmds.append(g + "worktree add --detach %s %s" % (q(w["path"]), w["head"]))
        if w["locked"]:
            cmds.append(g + "worktree lock %s%s" % ("--reason %s " % q(w["lock_reason"]) if w["lock_reason"] else "",
                                                   q(w["path"])))
    # moving back: only a folder that is in the archive AND absent from its original place
    back = ["if [ -e %s ] && [ ! -e %s ]; then mv %s %s; fi" % (q(src), q(dst), q(src), q(dst))
            for dst, src in [(repo, arepo)] + [(w["path"], d) for w, d in moved]]
    if moved:
        back.append(g + "worktree repair %s" % " ".join(q(w["path"]) for w, _d in moved))
    if ahp:
        back.append(g + "config core.hooksPath %s" % q(inv["hooks_path"]))
    undo_a = ["# moves back only a folder that is in the archive and absent from its original place",
              "if [ -e %s ] && [ -e %s ]; then echo %s >&2; exit 1; fi" % (q(arepo), q(repo), q(MSG_A))] + back
    aside = os.path.join(A, "new-clone-aside")
    kept = [w for w, _d in moved if not w["old"]]
    kept_aside = [(w, os.path.join(aside, "worktrees", "%d-%s" % (i, os.path.basename(os.path.normpath(w["path"])))))
                  for i, w in enumerate(kept)]
    undo_b = ["# sets the new clone aside only once it is confirmed as the new clone, untouched; "
              "then moves the archived folders back",
              "if [ ! -e %s ]; then echo %s >&2; exit 1; fi" % (q(arepo), q(MSG_B1)),
              'if [ "$(git -C %s config --get remote.origin.pushurl)" != %s ]; then echo %s >&2; exit 1; fi'
              % (q(repo), FROZEN, q(MSG_B2)),
              "%s check-new-clone %s %s %s" % (self_command(), q(repo), q(inv_path),
                                               expected_digest(new_clone_expected(inv))),
              "mkdir -p %s" % q(os.path.join(aside, "worktrees"))]
    undo_b += ["if [ -e %s ]; then mv %s %s; fi" % (q(w["path"]), q(w["path"]), q(d)) for w, d in kept_aside]
    undo_b.append("mv %s %s" % (q(repo), q(os.path.join(aside, "repo"))))
    undo_b += ["if [ -e %s ]; then git -C %s worktree repair %s; fi" % (q(d), q(os.path.join(aside, "repo")), q(d))
               for _w, d in kept_aside]
    return cmds, undo_a, undo_b + back


def check_archive(inv, archive, url):
    if os.path.lexists(archive):
        raise Refuse("archive dir exists (never reused): %s" % archive)
    for w in inv["worktrees"]:
        if norm(archive) == norm(w["path"]) or inside(archive, w["path"]):
            raise Refuse("the archive dir is inside %s; put it outside every checkout" % w["path"])
    if os.path.exists(url) and any(norm(url) == norm(w["path"]) or inside(url, w["path"]) for w in inv["worktrees"]):
        raise Refuse("the clone URL is this checkout: clone the purged remote, never the old copy")


def local_url(url, base):
    """A clone URL that names a folder (relative to base, or absolute) as an absolute path; anything else as is."""
    return os.path.abspath(os.path.join(base, url)) if os.path.exists(os.path.join(base, url)) else url


def cmd_inventory(a):
    require_repo(a.repo)
    old = read_old(a.old_commits)
    check_main(a.repo)
    first = state_digest(a.repo)
    inv = build_inventory(a.repo, old, read_old_objects(a.old_commits))
    inv["digest"] = state_digest(a.repo)
    if inv["digest"] != first:
        raise Refuse("the checkout changed while inventory ran: stop every session, IDE and scheduled job that "
                     "uses it (SKILL.md Step 6 item 1), then run inventory again")
    inv["old_commits"] = os.path.abspath(a.old_commits)
    if a.clone_url:
        url = local_url(a.clone_url, os.getcwd())
    else:                                                  # git reads a relative remote URL against the checkout
        url = dict(inv["remotes"]).get("remote.origin.url")
        url = url and local_url(url, inv["repo"])
    lines = inventory_lines(inv)
    if a.archive:
        if not url:
            raise Refuse("no remote.origin.url: pass --clone-url <the purged remote>")
        check_archive(inv, a.archive, url)
    if inv["refusals"]:
        lines.append("%d case(s) outside the supported layout: do what each REFUSED line says, then run inventory "
                     "again" % len(inv["refusals"]))
    elif a.archive:
        cmds, undo_a, undo_b = step6_commands(inv, a.archive, url, a.out)
        inv["new_clone"] = new_clone_expected(inv)
        inv["new_clone_digest"] = expected_digest(inv["new_clone"])
        lines += [BEGIN] + cmds + [UNDO_A] + undo_a + [UNDO_B] + undo_b + [END]
    else:
        lines.append("pass --archive <B>/rehome-<n> to print the Step 6 commands")
    check_writable(lines)
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(inv, fh, indent=1)
    print("\n".join(lines))
    return 2 if inv["refusals"] else 0


def cmd_check_unchanged(a):
    require_repo(a.repo)
    if not DIGEST_RE.match(a.digest):
        raise Refuse("not a digest printed by inventory: %s" % a.digest)
    now = state_digest(a.repo)
    if now != a.digest:
        print("CHANGED since inventory (%s, now %s): a worktree, ref, stash entry or uncommitted file changed. "
              "Stop: nothing has moved. Find and stop the writer (SKILL.md Step 6 item 1), then run inventory "
              "again with a new --archive" % (a.digest, now))
        return 1
    print("unchanged since inventory: %s" % now)
    return 0


def new_clone_problems(repo, exp):
    """Differences between the new clone and any stop point of the printed 6.4 lines."""
    problems = []
    rows = [l.split("\0") for l in out(repo, "for-each-ref", "--format=%(refname)%00%(objectname)").splitlines() if l]
    remote = {n: s for n, s in rows if n.startswith("refs/remotes/")}
    served = None
    for name, sha in rows:
        if name.startswith("refs/remotes/") or name == "refs/stash" or exp["refs"].get(name) == sha:
            continue
        if name.startswith("refs/heads/") and remote.get("refs/remotes/origin/" + name[len("refs/heads/"):]) == sha:
            continue                                       # the branch git clone itself created, untouched
        if name.startswith("refs/tags/"):                  # git clone also brought the remote's tags
            if served is None:
                r = git(repo, "ls-remote", "--tags", "origin", check=False)
                served = dict(reversed(l.split("\t", 1)) for l in r.stdout.splitlines() if "\t" in l)
                if r.returncode:
                    problems.append("cannot read origin's tags to tell them from new ones (git ls-remote exit %d)"
                                    % r.returncode)
            if served.get(name) == sha:
                continue
        problems.append("ref %s at %s is not what 6.4 put there" % (name, sha))
    stash = [s for s, _m in reversed(stash_entries(repo))]
    if stash != exp["stash"][:len(stash)]:
        problems.append("stash entries differ from the kept ones (%d now)" % len(stash))
    wts = list_worktrees(repo)
    if norm(wts[0]["path"]) != norm(exp["repo"]):
        problems.append("main worktree is %s" % wts[0]["path"])
    want = {norm(p): (p, w) for p, w in exp["worktrees"].items()}
    for w in wts[1:]:
        e = want.get(norm(w["path"]))
        if not e:
            problems.append("worktree %s was added" % w["path"])
        elif w["prunable"] or (w["branch"], w["head"]) != (e[1]["branch"], e[1]["head"]):
            problems.append("worktree %s is not at %s" % (w["path"], e[1]["branch"] or e[1]["head"]))
        elif git(w["path"], "status", "--porcelain=v1", "-uall", "-z").stdout:
            problems.append("worktree %s has uncommitted files" % w["path"])
    listed = {norm(w["path"]) for w in wts}
    problems += ["%s exists but is not a worktree of the new clone" % p
                 for k, (p, _w) in want.items() if os.path.lexists(p) and k not in listed]
    for w in wts:
        if os.path.isdir(w["path"]):
            own = out(w["path"], "for-each-ref", "--format=%(refname)", *[p.rstrip("/") for p in PER_WORKTREE])
            problems += ["per-worktree ref %s in %s" % (r, w["path"]) for r in own.split()]
    raw = git(repo, "status", "--porcelain=v1", "-uall", "-z").stdout.split("\0")   # before checkout: all "D "
    if any(item and item[:2] != "D " for item in raw if len(item) > 3 and item[2] == " "):
        problems.append("uncommitted files in %s" % repo)
    head = git(repo, "rev-parse", "--verify", "-q", "HEAD", check=False).stdout.strip()
    if head and head not in set(exp["refs"].values()) | set(remote.values()) | {exp["main_head"]}:
        problems.append("HEAD is at %s, which 6.4 never checked out" % head)
    return problems


def cmd_check_new_clone(a):
    require_repo(a.repo)
    try:
        with open(a.inv, encoding="utf-8") as fh:
            exp = json.load(fh).get("new_clone")
    except (OSError, ValueError):
        exp = None
    if not exp or expected_digest(exp) != a.digest or norm(exp["repo"]) != norm(a.repo):
        raise Refuse("%s is not the inv.json these Undo B lines were printed with (digest %s)" % (a.inv, a.digest))
    problems = new_clone_problems(a.repo, exp)
    if problems:
        print("CHANGED: someone worked in the new clone, so Undo B would set their work aside. Nothing moved. "
              "%s" % "; ".join(problems[:10]))
        return 1
    print("the new clone is untouched: %d carried refs, %d kept stash entries, %d kept worktrees expected"
          % (len(exp["refs"]), len(exp["stash"]), len(exp["worktrees"])))
    return 0


def cmd_overlap(a):
    require_repo(a.repo)
    objs = read_old_objects(a.old_commits)
    n_c, n_o = overlap_counts(a.repo, read_old(a.old_commits), objs)
    print("old commits still in the object store: %d" % n_c)
    if objs:
        print("changed/dropped blobs, trees and tags still in the object store: %d" % n_o)
    if n_c or n_o:
        print("hint: this copy still holds old history: run Step 6 on it (inventory --archive, then its commands)")
    return 0 if n_c + n_o == 0 else 1


def overlap_counts(repo, old, objs):
    listing = out(repo, "cat-file", "--batch-all-objects", "--batch-check=%(objecttype) %(objectname)")
    commits, others = set(), set()
    for line in listing.splitlines():
        typ, _, sha = line.partition(" ")
        (commits if typ == "commit" else others).add(sha)
    return len(commits & old), len(others & objs)


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
    c.add_argument("--archive", help="absent folder outside every worktree (<B>/rehome-<n>): print the Step 6 "
                                     "commands that move the checkout there")
    c.add_argument("--clone-url", help="the PURGED remote (default: remote.origin.url)")
    c.set_defaults(fn=cmd_inventory)
    c = sub.add_parser("overlap")
    c.add_argument("repo")
    c.add_argument("old_commits")
    c.set_defaults(fn=cmd_overlap)
    c = sub.add_parser("check-unchanged", help="the first 6.3 line: exit 1 if the checkout changed since inventory")
    c.add_argument("repo")
    c.add_argument("digest", help="the state digest inventory printed")
    c.set_defaults(fn=cmd_check_unchanged)
    c = sub.add_parser("check-new-clone", help="Undo B: exit 1 if anyone worked in the new clone")
    c.add_argument("repo")
    c.add_argument("inv", help="the inv.json inventory wrote with these lines")
    c.add_argument("digest", help="the digest printed on the Undo B line")
    c.set_defaults(fn=cmd_check_new_clone)
    try:
        a = p.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0
    for attr in ("purged", "repo", "out", "archive", "old_commits", "inv"):   # never resolved against -C
        if getattr(a, attr, None):
            setattr(a, attr, os.path.abspath(getattr(a, attr)))
    if getattr(a, "backups", None):
        a.backups = [os.path.abspath(b) for b in a.backups]
    try:
        return a.fn(a)
    except Refuse as exc:
        print("REFUSED: %s" % exc)
        return 2
    except subprocess.CalledProcessError as exc:
        print("git failed: %s (exit %d)" % (" ".join(exc.cmd), exc.returncode))
        return 2


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):    # UTF-8 whatever the console code page: printed names stay exact;
        if hasattr(_stream, "reconfigure"):     # a name that cannot be written is refused (check_writable)
            _stream.reconfigure(encoding="utf-8", errors="strict", newline="\n")   # LF: bash runs a tee'd file
    sys.exit(main())
