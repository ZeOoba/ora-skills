"""Remove purged ("old") history from a local checkout, then prove it at object level (SKILL.md Step 6).

  python -I local_cleanup.py changed <purged.git> <backup.git> [<backup2.git> ...] --out <old-commits.txt>
  python -I local_cleanup.py plan <repo> <old-commits.txt> --out <plan.json> [--min-age-hours 24] [--include-locked]
  python -I local_cleanup.py archive <repo> <plan.json> <archive-dir> [--include-locked]
  python -I local_cleanup.py gc <repo> <old-commits.txt> [--prune-floor 1.hour.ago]
  python -I local_cleanup.py overlap <repo> <old-commits.txt>

Every path argument is resolved against the current directory before use.

"Old history" = reaches a commit the purge CHANGED or DROPPED: every commit reachable from any ref of
any backup, minus every commit reachable from any ref of the purged copy. A clean first commit keeps
its SHA through filter-repo, so branches sharing only that root are NOT old; an orphan branch is not
old either. Several backups: a second one is made when someone pushed after the first (never fetch
into an existing backup); `changed` takes their union.

changed  writes the sorted old set; exit 1 if it is empty (refuse to guess). Also writes
         <out>.objects: the changed/dropped NON-commit objects (blobs, trees, tag objects reachable
         from the backups minus those reachable from the purged copy); plan and overlap read it when
         it sits next to the old-commits file.
plan     (read-only) every ref in every namespace (annotated tags peeled; a ref whose object or
         peeled object is in <old>.objects counts as old), every stash entry, every linked
         worktree. Linked worktrees on old history are skipped (with their branch) when locked
         (unless --include-locked), missing/prunable, or dirty with a change newer than
         --min-age-hours. A main worktree on old history is a BLOCKER (re-point it first, Step 6.2).
         Records each planned ref's reflog length. Exit 0 if every old item is planned and there
         is no blocker, else 1.
archive  re-checks every item (ref SHA, worktree HEAD, dirty set, each dirty file's mtime; branches
         checked out in any other worktree; anything changed is skipped), bundles every ref to
         remove plus temp refs (refs/purge-archive/...) for stash entries, detached worktree HEADs
         and each archived worktree's local refs (refs/worktree, refs/bisect, refs/rewritten,
         ORIG_HEAD/FETCH_HEAD/... and HEAD-reflog entries not reachable otherwise), verifies the
         bundle and its heads. Then per worktree: `git worktree lock`, re-check against LIVE state
         (HEAD, branch, dirty set, mtimes, local refs), save staged-only content (index differs from
         both HEAD and the file), unlock, move the folder intact (ignored files included) to
         <archive>/dirs/. Prunes, re-reads the live worktree list and each ref's tip and reflog
         (anything now checked out or moved is skipped), and removes the refs in ONE leased
         update-ref transaction. Nothing is deleted. Exit 0 all archived, 1 something skipped,
         2 refused before anything was moved or removed.
gc       deletes ONLY the reflog entries (every reflog: each ref incl. refs/stash, every worktree's
         HEAD and per-worktree refs) whose SHA reaches an old commit or is a listed old object,
         highest index first (`reflog delete --rewrite`, so kept entries no longer point at a
         deleted one); every other session's reflog and stash entry is kept. Then
         gc --prune=<floor>. The floor (default 1.hour.ago, never now by default) protects objects
         other sessions are creating.
overlap  objects in the object store that are in the old set (commits) or, when <old>.objects
         exists, in that set (blobs, trees, tags): exit 0 when 0, else 1.

Prints counts and ref names only, never file contents.
Exit codes: 0 ok, 1 work left/found, 2 bad input (nothing changed).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

SHA_RE = re.compile(r"^[0-9a-f]{40}([0-9a-f]{24})?$")
TEMP_NS = "refs/purge-archive/"


class Refuse(Exception):
    """Bad input: exit 2, nothing changed."""


def git(repo, *args, check=True, binary=False, stdin=None):
    r = subprocess.run(["git", "-C", repo, "-c", "core.quotepath=false"] + list(args), capture_output=True,
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


def rev_list_all(repo):
    return set(out(repo, "rev-list", "--all").split())


def objects_all(repo):
    """Every object (commit, tree, blob, tag) reachable from any ref."""
    return {l.split(" ", 1)[0] for l in out(repo, "rev-list", "--objects", "--all").splitlines() if l}


def read_old(path):
    if not os.path.isfile(path):
        raise Refuse("old-commits file not found: %s" % path)
    with open(path, encoding="ascii", errors="replace") as fh:
        shas = [l.strip() for l in fh if l.strip()]
    bad = [s for s in shas if not SHA_RE.match(s)]
    if bad or not shas:
        raise Refuse("old-commits file is empty or has %d malformed line(s)" % len(bad))
    return set(shas)


def read_old_objects(old_path):
    """<old-commits>.objects (changed/dropped blobs, trees, tags) or an empty set when absent."""
    path = old_path + ".objects"
    if not os.path.isfile(path):
        return set()
    with open(path, encoding="ascii", errors="replace") as fh:
        shas = [l.strip() for l in fh if l.strip()]
    bad = [s for s in shas if not SHA_RE.match(s)]
    if bad:
        raise Refuse("old-objects file has %d malformed line(s)" % len(bad))
    return set(shas)


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


def reflog_names(repo):
    """Names that have a reflog (`git reflog list`), or None when this git cannot list them."""
    r = git(repo, "reflog", "list", check=False)
    return {l for l in r.stdout.splitlines() if l} if r.returncode == 0 else None


def reflog_entries(repo, name):
    """[(index, sha)] newest first, as `git reflog delete` addresses them; [] when there is none."""
    r = git(repo, "reflog", "show", "--format=%gD %H", name, "--", check=False)
    rows = []
    if r.returncode != 0:
        return rows
    for line in r.stdout.splitlines():
        m = re.match(r"^(.*)@\{(\d+)\} ([0-9a-f]+)$", line)
        if m:
            rows.append((int(m.group(2)), m.group(3)))
    return rows


def reflog_len(repo, name, have=None):
    if have is not None and name not in have:
        return 0
    return len(reflog_entries(repo, name))


def checked_out(repo):
    """branch ref -> worktree path, for every worktree (main included) as git lists them NOW."""
    return {w["branch"]: w["path"] for w in list_worktrees(repo) if w["branch"]}


def stash_entries(repo):
    if git(repo, "rev-parse", "--verify", "-q", "refs/stash", check=False).returncode != 0:
        return []
    return out(repo, "reflog", "show", "--format=%H", "refs/stash").split()


def common_dir(repo):
    d = out(repo, "rev-parse", "--git-common-dir").strip()
    return d if os.path.isabs(d) else os.path.join(repo, d)


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
            cur["locked"], cur["lock_reason"] = True, line[7:]
        elif line.startswith("prunable"):
            cur["prunable"] = True
    ids = worktree_ids(repo)
    for i, w in enumerate(blocks):
        w["main"] = i == 0
        w["id"] = None if i == 0 else ids.get(norm(w["path"]), os.path.basename(w["path"]))
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
        except OSError:
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


WT_LOCAL_NS = ("refs/worktree", "refs/bisect", "refs/rewritten")
WT_PSEUDO = ("ORIG_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_HEAD")


def wt_local_raw(repo, w):
    """Everything only this linked worktree holds: [(label, original name, sha)], in a stable order.
    Its local refs, its pseudo-refs (FETCH_HEAD lines included) and its HEAD reflog entries."""
    path, rows = w["path"], []
    r = git(path, "for-each-ref", "--format=%(refname) %(objectname)", *WT_LOCAL_NS, check=False)
    for line in r.stdout.splitlines():
        name, _, sha = line.rpartition(" ")
        if name and SHA_RE.match(sha):
            rows.append((name[len("refs/"):], name, sha))
    for p in WT_PSEUDO:
        r = git(path, "rev-parse", "--verify", "-q", p, check=False)
        if r.returncode == 0 and SHA_RE.match(r.stdout.strip()):
            rows.append((p, p, r.stdout.strip()))
    fetch = git(path, "rev-parse", "--git-path", "FETCH_HEAD", check=False).stdout.strip()
    if fetch:
        fetch = fetch if os.path.isabs(fetch) else os.path.join(path, fetch)
        try:
            with open(fetch, encoding="utf-8", errors="replace") as fh:
                for i, line in enumerate(fh):
                    sha = line.split("\t", 1)[0].strip()
                    if SHA_RE.match(sha):
                        rows.append(("FETCH_HEAD/%d" % i, "FETCH_HEAD line %d" % i, sha))
        except OSError:
            pass
    for i, sha in reflog_entries(repo, "worktrees/%s/HEAD" % w["id"]):
        rows.append(("reflog/%d" % i, "HEAD@{%d}" % i, sha))
    return rows


def wt_local_refs(repo, w, raw):
    """The subset of wt_local_raw to bundle: every local ref, plus each pseudo-ref / reflog entry whose
    object exists and is NOT reachable from any ref (those are either kept or bundled anyway)."""
    keep, loose = [], {}
    for label, name, sha in raw:
        if name.startswith("refs/"):
            keep.append((label, name, sha))
        else:
            loose.setdefault(sha, (label, name, sha))
    if loose:
        listing = git(repo, "cat-file", "--batch-check=%(objectname) %(objecttype)",
                      stdin="".join(s + "\n" for s in loose), check=False).stdout.split("\n")
        present = {}
        for line in listing:
            parts = line.split()
            if len(parts) == 2 and parts[1] != "missing":
                present[parts[0]] = parts[1]
        commits = [s for s, t in present.items() if t == "commit"]
        unreached = set()
        if commits:
            r = git(repo, "rev-list", "--stdin", "--not", "--all", stdin="".join(s + "\n" for s in commits),
                    check=False)
            unreached = set(r.stdout.split()) if r.returncode == 0 else set(commits)
        for sha, row in loose.items():
            if sha in unreached or (sha in present and present[sha] != "commit"):
                keep.append(row)
    return keep


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
    have = reflog_names(repo)
    for r in plan["refs"]:
        r["reflog"] = reflog_len(repo, r["name"], have)
    return plan


def cmd_plan(a):
    require_repo(a.repo)
    old = read_old(a.old_commits)
    plan = build_plan(a.repo, old, a.min_age_hours, a.include_locked, read_old_objects(a.old_commits))
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


def wt_unchanged(planned, current):
    """current = the live porcelain entry (or None). Compares HEAD, dirty set and each dirty mtime."""
    if current is None or not os.path.isdir(planned["path"]):
        return "worktree no longer registered or its folder is gone"
    if current["head"] != planned["head"] or current["branch"] != planned["branch"]:
        return "HEAD moved since the plan"
    now = dirty_state(planned["path"])
    key = lambda d: (d["status"], d["path"], d["mtime_ns"])
    if sorted(map(key, now)) != sorted(map(key, planned["dirty"])):
        return "files changed since the plan (dirty set or mtime)"
    return None


def live_worktree(repo, path):
    """The linked worktree's porcelain entry as git lists it NOW (None when no longer registered)."""
    for w in list_worktrees(repo)[1:]:
        if norm(w["path"]) == norm(path):
            return w
    return None


LOCK_REASON = "git-history-purge local_cleanup archive in progress"


def cmd_archive(a):
    require_repo(a.repo)
    repo = a.repo
    if os.path.exists(a.archive_dir):
        raise Refuse("archive dir exists (never reused): %s" % a.archive_dir)
    with open(a.plan, encoding="utf-8") as fh:
        plan = json.load(fh)
    if plan.get("blockers"):
        raise Refuse("plan has %d BLOCKER(s): re-point the main worktree, then plan again" % len(plan["blockers"]))
    wts_now = list_worktrees(repo)
    main = wts_now[0]
    if main["head"] != plan.get("main_head"):
        raise Refuse("main worktree HEAD moved since the plan: plan again")
    skipped = []
    live = {name: sha for name, sha, _c, symref, _p in list_refs(repo) if not symref}
    by_path = {norm(w["path"]): w for w in wts_now[1:]}
    planned_paths = {norm(w["path"]) for w in plan["worktrees"]}
    others = {w["branch"]: w["path"] for w in wts_now[1:]
              if w["branch"] and norm(w["path"]) not in planned_paths}

    # re-check worktrees
    wts = []
    skip_branch = {}
    for w in plan["worktrees"]:
        cur = by_path.get(norm(w["path"]))
        why = wt_unchanged(w, cur)
        if why is None and cur["locked"] and not a.include_locked:
            why = "locked; pass --include-locked on its own yes"
        if why:
            skipped.append((w["path"], why))
            if w["branch"]:
                skip_branch[w["branch"]] = why
        else:
            w["locked_now"], w["lock_reason_now"] = cur["locked"], cur["lock_reason"]
            wts.append(w)
    # re-check refs
    refs = []
    for r in plan["refs"]:
        if r["name"] == main["branch"]:
            skipped.append((r["name"], "checked out in the main worktree"))
        elif r["name"] in others:
            skipped.append((r["name"], "checked out in worktree %s (not in the plan)" % others[r["name"]]))
        elif r["name"] in skip_branch:
            skipped.append((r["name"], skip_branch[r["name"]]))
        elif live.get(r["name"]) != r["sha"]:
            skipped.append((r["name"], "ref moved or removed since the plan"))
        else:
            refs.append(r)
    stash = plan["stash"]
    if stash and stash_entries(repo) != [e["sha"] for e in stash]:
        skipped.append(("refs/stash", "stash changed since the plan"))
        stash = []
        refs = [r for r in refs if r["name"] != "refs/stash"]
    names = {r["name"] for r in refs}
    symrefs = [s for s in plan.get("symrefs", []) if s["target"] in names]

    temp = {}
    for e in stash:
        temp["%sstash/%d" % (TEMP_NS, e["index"])] = e["sha"]
    wtrefs = []                      # (temp ref, worktree id, original name, sha): worktree-local state
    for w in wts:
        if w["detached"] or not w["branch"]:
            temp["%swt/%s" % (TEMP_NS, w["id"])] = w["head"]
        w["wtrefs_raw"] = wt_local_raw(repo, w)
        for label, name, sha in wt_local_refs(repo, w, w["wtrefs_raw"]):
            tn = "%swtref/%s/%s" % (TEMP_NS, w["id"], label)
            temp[tn] = sha
            wtrefs.append((tn, w["id"], name, sha))
    expected = dict((r["name"], r["sha"]) for r in refs)
    expected.update(temp)
    if not expected and not wts:
        print("nothing to archive (all %d item(s) skipped)" % len(skipped))
        for item, why in skipped:
            print("  SKIP %s: %s" % (item, why))
        return 1 if skipped else 0

    # temp refs, bundle, verify: any failure -> exit 2 with nothing moved or removed
    os.makedirs(a.archive_dir)
    created = []

    def drop_temp():
        if created:
            txt = "start\n" + "".join("delete %s %s\n" % (n, temp[n]) for n in created) + "commit\n"
            git(repo, "update-ref", "--stdin", stdin=txt, check=False)

    if temp:
        txt = "start\n" + "".join("create %s %s\n" % kv for kv in sorted(temp.items())) + "commit\n"
        r = git(repo, "update-ref", "--stdin", stdin=txt, check=False)
        if r.returncode != 0:
            raise Refuse("could not create temp refs under %s (name taken?); nothing moved" % TEMP_NS)
        created = sorted(temp)
    bundle = os.path.join(a.archive_dir, "refs.bundle")
    try:
        r = git(repo, "bundle", "create", bundle, "--stdin", stdin="".join(n + "\n" for n in sorted(expected)),
                check=False)
        if r.returncode != 0:
            raise Refuse("git bundle create failed; nothing moved")
        if git(repo, "bundle", "verify", bundle, check=False).returncode != 0:
            raise Refuse("git bundle verify failed; nothing moved")
        lacking = missing_heads(expected, out(repo, "bundle", "list-heads", bundle))
        if lacking:
            raise Refuse("bundle lacks %d ref(s) (%s); nothing moved" % (len(lacking), ", ".join(lacking[:5])))
    except Refuse:
        drop_temp()
        raise

    manifest = [("kind", "id", "sha", "ref", "original_path")]
    for e in stash:
        manifest.append(("stash", str(e["index"]), e["sha"], "%sstash/%d" % (TEMP_NS, e["index"]), ""))
    for tn, wid, name, sha in wtrefs:
        manifest.append(("wtref", wid, sha, tn, name))

    # per worktree: lock, re-check against LIVE state, save staged-only content, unlock, move
    moved = []
    for w in wts:
        label = "%s-%s" % (w["id"], os.path.basename(os.path.normpath(w["path"])))
        why, held = None, False
        if not w["locked_now"]:
            if git(repo, "worktree", "lock", "--reason", LOCK_REASON, w["path"], check=False).returncode != 0:
                why = "could not lock it (locked by another session meanwhile?)"
            else:
                held = True
        if why is None:
            why = wt_unchanged(w, live_worktree(repo, w["path"]))       # live HEAD, branch, dirty set, mtimes
        if why is None and wt_local_raw(repo, w) != w["wtrefs_raw"]:
            why = "worktree-local refs or HEAD reflog changed since the bundle"
        if why is None:
            try:
                save_staged(w, os.path.join(a.archive_dir, "staged-index", label))
                for rel in w["index_only"]:
                    manifest.append(("staged", w["id"], "", "", os.path.join(w["path"], rel)))
            except (OSError, ValueError, subprocess.CalledProcessError) as exc:
                why = "could not save staged-only content (%s)" % type(exc).__name__
        if why is None and (held or w["locked_now"]):              # the moved folder keeps no lock
            if git(repo, "worktree", "unlock", w["path"], check=False).returncode != 0:
                why = "could not unlock"
            else:
                held = False
        dest = os.path.join(a.archive_dir, "dirs", label)
        if why is None:
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            try:
                try:
                    os.rename(w["path"], dest)
                except OSError:
                    shutil.move(w["path"], dest)
            except OSError as exc:
                why = "move failed (%s)" % type(exc).__name__
                if w["locked_now"]:
                    git(repo, "worktree", "lock", "--reason", w["lock_reason_now"] or "restored", w["path"],
                        check=False)
        if why:
            if held:
                git(repo, "worktree", "unlock", w["path"], check=False)
            skipped.append((w["path"], why))
            if w["branch"]:
                skipped.append((w["branch"], why))
                refs = [r for r in refs if r["name"] != w["branch"]]
            continue
        moved.append(w)
        manifest.append(("worktree", w["id"], w["head"], w["branch"] or "%swt/%s" % (TEMP_NS, w["id"]), w["path"]))

    git(repo, "worktree", "prune", check=False)                     # result is checked just below
    still = {norm(w["path"]) for w in list_worktrees(repo)}
    for w in moved:
        if norm(w["path"]) in still:
            skipped.append((w["path"], "still registered after prune"))
            if w["branch"]:
                refs = [r for r in refs if r["name"] != w["branch"]]

    # immediately before the transaction: re-read the LIVE worktree list, each tip and each reflog
    co = checked_out(repo)
    live = {name: sha for name, sha, _c, symref, _p in list_refs(repo) if not symref}
    have = reflog_names(repo)
    keep = []
    for r in refs:
        if r["name"] in co:
            skipped.append((r["name"], "checked out in worktree %s (now)" % co[r["name"]]))
        elif live.get(r["name"]) != r["sha"]:
            skipped.append((r["name"], "ref moved or removed since the plan"))
        elif "reflog" in r and reflog_len(repo, r["name"], have) != r["reflog"]:
            skipped.append((r["name"], "reflog changed since the plan (moved and back?)"))
        else:
            keep.append(r)
    refs = keep

    # remove refs in ONE leased transaction (temp refs included: their content is in the bundle)
    names = {r["name"] for r in refs}
    symrefs = [s for s in symrefs if s["target"] in names]
    txt = ["start"]
    for s in symrefs:
        txt += ["option no-deref", "delete %s" % s["name"]]
    for r in refs:
        txt.append("delete %s %s" % (r["name"], r["sha"]))
    for n in created:
        txt.append("delete %s %s" % (n, temp[n]))
    txt.append("commit")
    rc = 0
    r = git(repo, "update-ref", "--stdin", stdin="\n".join(txt) + "\n", check=False)
    if r.returncode != 0:
        print("REF REMOVAL FAILED (no ref removed; a ref moved meanwhile?): run plan again")
        rc = 1
    else:
        for r_ in refs:
            manifest.append(("ref:" + r_["kind"], r_["name"], r_["sha"], r_["name"], ""))
        for s in symrefs:
            manifest.append(("symref", s["name"], "", s["target"], ""))
    with open(os.path.join(a.archive_dir, "manifest.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("".join("\t".join(row) + "\n" for row in manifest))
    print("bundle: %s (%d refs incl. %d temp)" % (bundle, len(expected), len(temp)))
    print("refs removed: %d, symrefs removed: %d, stash entries archived: %d"
          % (len(refs) if rc == 0 else 0, len(symrefs) if rc == 0 else 0, len(stash)))
    print("worktrees moved: %d (staged-only files saved: %d)" % (len(moved), sum(len(w["index_only"]) for w in moved)))
    print("skipped: %d" % len(skipped))
    for item, why in skipped:
        print("  SKIP %s: %s" % (item, why))
    return 1 if skipped or rc else 0


def all_reflogs(repo):
    """Every reflog: the shared ones and the main worktree's (`git reflog list`), plus each linked
    worktree's HEAD and per-worktree refs, addressed from the main repo as worktrees/<id>/<name>."""
    names = reflog_names(repo)
    if names is None:
        raise Refuse("this git cannot list reflogs (`git reflog list` needs git 2.46+); nothing changed")
    sel = sorted(names)
    local = tuple(ns + "/" for ns in WT_LOCAL_NS)
    for w in list_worktrees(repo)[1:]:
        if not w["id"]:
            continue
        per = {"HEAD"}
        base = os.path.join(common_dir(repo), "worktrees", w["id"], "logs")
        for root, _dirs, files in os.walk(base):
            for f in files:
                per.add(os.path.relpath(os.path.join(root, f), base).replace(os.sep, "/"))
        if os.path.isdir(w["path"]):
            r = git(w["path"], "reflog", "list", check=False)
            per |= {n for n in r.stdout.splitlines() if n == "HEAD" or n.startswith(local)}
        sel += ["worktrees/%s/%s" % (w["id"], n) for n in sorted(per)]
    return sel


def cmd_gc(a):
    require_repo(a.repo)
    is_old = OldTest(a.repo, read_old(a.old_commits), read_old_objects(a.old_commits))
    removed = logs = failed = 0
    for name in all_reflogs(a.repo):
        entries = reflog_entries(a.repo, name)
        idx = sorted({i for i, sha in entries if is_old(sha) or is_old.obj(sha)}, reverse=True)
        if not idx:
            continue
        top = entries[0][1] if entries else None
        args = ["reflog", "delete", "--rewrite"] + (["--updateref"] if name == "refs/stash" else [])
        r = git(a.repo, *(args + ["%s@{%d}" % (name, i) for i in idx]), check=False)   # highest index first
        if r.returncode != 0:
            print("reflog delete failed for %s (exit %d)" % (name, r.returncode))
            failed += 1
            continue
        removed, logs = removed + len(idx), logs + 1
        if name == "refs/stash" and len(idx) == len(entries) and top:     # every stash entry was old
            git(a.repo, "update-ref", "-d", "refs/stash", top, check=False)
    print("reflog entries on old history removed: %d (in %d reflogs); every other entry kept" % (removed, logs))
    r = git(a.repo, "gc", "--quiet", "--prune=" + a.prune_floor, check=False)
    print("gc --prune=%s: exit %d" % (a.prune_floor, r.returncode))
    return 0 if r.returncode == 0 and not failed else 1


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
        print("hint: a ref, stash entry or worktree still reaches them (run plan again), or they are younger "
              "than the prune floor (re-run gc after the floor passes)")
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
    c = sub.add_parser("archive")
    c.add_argument("repo")
    c.add_argument("plan")
    c.add_argument("archive_dir")
    c.add_argument("--include-locked", action="store_true")
    c.set_defaults(fn=cmd_archive)
    c = sub.add_parser("gc")
    c.add_argument("repo")
    c.add_argument("old_commits")
    c.add_argument("--prune-floor", default="1.hour.ago")
    c.set_defaults(fn=cmd_gc)
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
    except subprocess.CalledProcessError as exc:
        print("git failed: %s (exit %d)" % (" ".join(exc.cmd), exc.returncode))
        return 2


if __name__ == "__main__":
    sys.exit(main())
