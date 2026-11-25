"""Tests for local_cleanup.py (stdlib unittest; gated by tools/run_skill_suites.sh).

Real git in temp dirs. The purge is a real `git filter-repo --replace-text` run on a mirror clone
of the backup (SKILL.md Step 3). The FIRST commit holds nothing private, so the purge keeps its SHA
and new branches share it: such branches must NOT count as old history (finding R3-01).

archive and gc are exclusive maintenance (round-3 redesign): tests pass --exclusive --quiet-seconds 0
and inject "other sessions" through seams (wait_quiet, os.rename, git()) instead of racing real ones.
"""
import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "local_cleanup.py")
ENV = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="t",
           GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")
OLD_AGE = time.time() - 48 * 3600
Q = ("--exclusive", "--quiet-seconds", "0")


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false"] + list(args), capture_output=True,
                          encoding="utf-8", errors="surrogateescape", check=check, env=ENV).stdout.strip()


def run(*args, cwd=None, env=None):
    return subprocess.run([sys.executable, "-I", SCRIPT] + list(args), capture_output=True, encoding="utf-8",
                          errors="replace", env=dict(ENV, **(env or {})), cwd=cwd)


def write(path, data, age=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode())
    if age is not None:
        os.utime(path, (age, age))


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def refs(repo):
    out = git(repo, "for-each-ref", "--format=%(objectname) %(refname)")
    return dict(reversed(l.split(" ", 1)) for l in out.splitlines() if l)


def wt_paths(repo):
    return [os.path.normcase(os.path.normpath(l[9:])) for l in
            git(repo, "worktree", "list", "--porcelain").splitlines() if l.startswith("worktree ")]


def norm(p):
    return os.path.normcase(os.path.normpath(p))


def reflog(repo, name):
    return git(repo, "reflog", "show", "--format=%H", name, "--").split()


def exists(repo, sha):
    return subprocess.run(["git", "-C", repo, "cat-file", "-e", sha], env=ENV).returncode == 0


class Source:
    """src history: c0 clean root (kept by the purge), c1/c2 hold 'secret', c3 clean; branch old-feature at c2."""

    def __init__(self, root):
        self.root = root
        src = self.src = os.path.join(root, "src")
        subprocess.run(["git", "init", "-q", "-b", "main", src], check=True, env=ENV)
        write(os.path.join(src, "README.md"), "readme\n")
        write(os.path.join(src, ".gitignore"), "*.log\n")
        git(src, "add", "-A")
        git(src, "commit", "-q", "-m", "c0")
        self.c = [git(src, "rev-parse", "HEAD")]
        for i, (name, text) in enumerate([("f.txt", "secret v1\n"), ("f.txt", "secret v2\n"),
                                          ("g.txt", "ok\n")], 1):
            write(os.path.join(src, name), text)
            git(src, "add", "-A")
            git(src, "commit", "-q", "-m", "c%d" % i)
            self.c.append(git(src, "rev-parse", "HEAD"))
            if i == 2:
                git(src, "branch", "old-feature")
        self.backup = os.path.join(root, "backup.git")
        subprocess.run(["git", "clone", "-q", "--mirror", src, self.backup], check=True, env=ENV)
        self.purged = os.path.join(root, "purged.git")
        subprocess.run(["git", "clone", "-q", "--mirror", "--no-local", self.backup, self.purged], check=True,
                       env=ENV)
        rules = os.path.join(root, "rules.txt")
        write(rules, "secret==>[private]\n")
        git(self.purged, "filter-repo", "--force", "--replace-text", rules, "--replace-message", rules)
        self.new_main = git(self.purged, "rev-parse", "refs/heads/main")
        self.old = os.path.join(root, "old-commits.txt")
        r = run("changed", self.purged, self.backup, "--out", self.old)
        assert r.returncode == 0, r.stdout + r.stderr

    def live(self, name, repoint=True):
        """A clone of src (main on old history); repoint=True does SKILL.md Step 6 item 2."""
        live = os.path.join(self.root, name)
        subprocess.run(["git", "clone", "-q", self.src, live], check=True, env=ENV)
        git(live, "fetch", "-q", self.purged, "refs/heads/main:refs/heads/newmain")
        if repoint:
            git(live, "checkout", "-q", "-B", "main", "newmain")
        return live


def load_module():
    spec = importlib.util.spec_from_file_location("local_cleanup", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def inproc(argv, before=None, replace=None, setup=None):
    """Run local_cleanup.main in-process with a seam around its git() calls.
    before(repo, args, kw) runs just before the real call; replace(real, repo, args, kw) may return a result
    instead of calling git; setup(mod) may patch module functions first. Returns (rc, stdout, calls)."""
    mod = load_module()
    real, calls = mod.git, []

    def fake(repo, *args, **kw):
        calls.append((repo, args, kw.get("stdin")))
        if replace:
            r = replace(real, repo, args, kw)
            if r is not None:
                return r
        if before:
            before(repo, args, kw)
        return real(repo, *args, **kw)

    mod.git = fake
    if setup:
        setup(mod)
    old_env = dict(os.environ)
    os.environ.update(ENV)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            rc = mod.main(argv)
    finally:
        os.environ.clear()
        os.environ.update(old_env)
    return rc, buf.getvalue(), calls


@contextlib.contextmanager
def patched_rename(fn):
    """Replace os.rename (process-wide) with fn(real, src, dst) for the duration."""
    real = os.rename
    os.rename = lambda src, dst: fn(real, src, dst)
    try:
        yield
    finally:
        os.rename = real


def fake_result(rc=0, stdout=""):
    return subprocess.CompletedProcess(["git"], rc, stdout, "")


def restore_bundle(root, bundle):
    restore = os.path.join(root, "restore-%d" % len(os.listdir(root)))
    subprocess.run(["git", "init", "-q", restore], check=True, env=ENV)
    git(restore, "fetch", "-q", bundle, "refs/*:refs/*")
    return restore


class FullCleanupTest(unittest.TestCase):
    """One live checkout with every kind of old and new item; the whole Step 6 sequence runs once."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        t = cls.tmp.name
        s = cls.s = Source(t)
        c = s.c
        live = cls.live = s.live("live")
        wts = os.path.join(t, "wts")
        # refs in every namespace
        git(live, "branch", "new-branch", "newmain")
        git(live, "commit", "-q", "--allow-empty", "-m", "new work")    # on main (new history)
        git(live, "branch", "shares-root", c[0])                          # R3-01: unchanged root, NOT old
        git(live, "update-ref", "refs/heads/shares-root",
            git(live, "commit-tree", c[0] + "^{tree}", "-p", c[0], "-m", "x"))
        empty = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"                 # the empty tree
        git(live, "update-ref", "refs/heads/heartbeat", git(live, "commit-tree", empty, "-m", "hb"))  # orphan
        git(live, "tag", "lt-old", c[1])
        git(live, "tag", "-a", "at-old", c[2], "-m", "old release")
        git(live, "tag", "-a", "at-new", "newmain", "-m", "new release")
        git(live, "update-ref", "refs/original/refs/heads/main", c[3])
        git(live, "update-ref", "refs/custom/x", c[1])
        git(live, "notes", "add", "-m", "note", c[1])                     # notes commit does not reach c1
        git(live, "branch", "--track", "old-feature", "origin/old-feature")
        # linked worktrees
        cls.wt = {}

        def add(name, *spec):
            path = os.path.join(wts, name)
            git(live, "worktree", "add", "-q", *spec[:-1], path, spec[-1])
            cls.wt[name] = path
            return path

        clean = add("wt-clean", "-b", "wt-clean-br", c[2])
        write(os.path.join(clean, "run.log"), "ignored state\n")
        for i in range(2):                                                 # two stash entries on old
            write(os.path.join(clean, "f.txt"), "stash %d\n" % i)
            git(clean, "stash", "-q")
        write(os.path.join(live, "README.md"), "main stash\n")             # newest stash: new history
        git(live, "stash", "-q")
        dirty = add("wt-dirty", "-b", "wt-dirty-br", c[2])
        write(os.path.join(dirty, "f.txt"), "edited\n", OLD_AGE)
        write(os.path.join(dirty, "untracked.txt"), "u\n", OLD_AGE)
        write(os.path.join(dirty, "cache.log"), "ignored, holds runtime state\n")
        mm = add("wt-mm", "-b", "wt-mm-br", c[2])
        cls.staged = {"f.txt": b"staged f\n", "new.txt": b"staged new\n", "bin.dat": b"\x00\x01\r\n\xff staged"}
        for name, data in cls.staged.items():
            write(os.path.join(mm, name), data)
            git(mm, "add", name)
            write(os.path.join(mm, name), b"work tree " + name.encode() + b"\n", OLD_AGE)
        write(os.path.join(mm, "README.md"), "plain unstaged\n", OLD_AGE)   # " M": not index-only
        locked = add("wt-locked", "-b", "wt-locked-br", c[1])
        git(live, "worktree", "lock", "--reason", "in use", locked)
        add("wt-detached", "--detach", c[1])
        recent = add("wt-recent", "-b", "wt-recent-br", c[2])
        write(os.path.join(recent, "f.txt"), "being edited now\n")
        add("wt-new", "-b", "wt-new-br", "newmain")
        cls.new_refs = {k: v for k, v in refs(live).items() if k in (
            "refs/heads/main", "refs/heads/newmain", "refs/heads/new-branch", "refs/heads/shares-root",
            "refs/heads/heartbeat", "refs/tags/at-new", "refs/notes/commits", "refs/heads/wt-new-br")}
        cls.refs_before = refs(live)
        cls.stash_before = reflog(live, "refs/stash")
        # Step 6 sequence
        cls.overlap_before = run("overlap", live, s.old)
        cls.plan_path = os.path.join(t, "plan.json")
        cls.plan_run = run("plan", live, s.old, "--out", cls.plan_path)
        with open(cls.plan_path, encoding="utf-8") as fh:
            cls.plan = json.load(fh)
        cls.arch = os.path.join(t, "arch1")
        cls.archive_run = run("archive", live, cls.plan_path, cls.arch, *Q)
        cls.refs_after1 = refs(live)
        cls.plan2_path = os.path.join(t, "plan2.json")
        cls.plan2_run = run("plan", live, s.old, "--out", cls.plan2_path, "--include-locked",
                            "--min-age-hours", "0")
        cls.arch2 = os.path.join(t, "arch2")
        cls.archive2_run = run("archive", live, cls.plan2_path, cls.arch2, "--include-locked", *Q)
        cls.gc_default = run("gc", live, s.old, cls.arch2, *Q)
        cls.overlap_floor = run("overlap", live, s.old)
        cls.gc_now = run("gc", live, s.old, cls.arch2, "--prune-floor", "now", *Q)
        cls.overlap_after = run("overlap", live, s.old)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def plan_ref_names(self, plan=None):
        return {r["name"] for r in (plan or self.plan)["refs"]}

    def plan_wt(self, name, plan=None):
        return [w for w in (plan or self.plan)["worktrees"] if norm(w["path"]) == norm(self.wt[name])]

    # changed
    def test_changed_excludes_unchanged_root_and_includes_changed(self):
        old = read(self.s.old).decode().split()
        self.assertEqual(old, sorted(old))
        self.assertNotIn(self.s.c[0], old)
        for sha in self.s.c[1:]:
            self.assertIn(sha, old)

    def test_changed_unions_several_backups(self):                           # also L01b (objects)
        t = self.tmp.name
        late_src = os.path.join(t, "late-src")
        subprocess.run(["git", "clone", "-q", self.s.src, late_src], check=True, env=ENV)
        write(os.path.join(late_src, "late.txt"), "secret pushed late\n")
        git(late_src, "add", "late.txt")
        git(late_src, "commit", "-q", "-m", "late push")
        late_blob = git(late_src, "rev-parse", "HEAD:late.txt")
        backup2 = os.path.join(t, "backup2.git")
        subprocess.run(["git", "clone", "-q", "--mirror", late_src, backup2], check=True, env=ENV)
        out = os.path.join(t, "old2.txt")
        r = run("changed", self.s.purged, self.s.backup, backup2, "--out", out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        both = read(out).decode().split()
        self.assertIn(git(late_src, "rev-parse", "HEAD"), both)
        self.assertEqual(set(both) - set(read(self.s.old).decode().split()), {git(late_src, "rev-parse", "HEAD")})
        self.assertIn(late_blob, read(out + ".objects").decode().split())    # a blob only in the 2nd backup

    def test_changed_refuses_empty_set_and_bad_path(self):
        out = os.path.join(self.tmp.name, "empty.txt")
        self.assertEqual(run("changed", self.s.purged, self.s.purged, "--out", out).returncode, 1)
        self.assertEqual(run("changed", self.s.purged, os.path.join(self.tmp.name, "nope"),
                             "--out", out).returncode, 2)

    # plan
    def test_plan_lists_old_refs_in_every_namespace_only(self):
        self.assertEqual(self.plan_run.returncode, 1, self.plan_run.stdout + self.plan_run.stderr)  # skips exist
        self.assertEqual(self.plan_ref_names(), {
            "refs/heads/old-feature", "refs/heads/wt-clean-br", "refs/heads/wt-dirty-br", "refs/heads/wt-mm-br",
            "refs/remotes/origin/main", "refs/remotes/origin/old-feature", "refs/tags/lt-old",
            "refs/tags/at-old", "refs/original/refs/heads/main", "refs/custom/x", "refs/stash"})
        kinds = {r["name"]: r["kind"] for r in self.plan["refs"]}
        self.assertEqual(kinds["refs/remotes/origin/main"], "remotes")
        self.assertEqual(kinds["refs/tags/at-old"], "tags")
        self.assertEqual(kinds["refs/original/refs/heads/main"], "original")
        at_old = [r for r in self.plan["refs"] if r["name"] == "refs/tags/at-old"][0]
        self.assertEqual(at_old["sha"], self.refs_before["refs/tags/at-old"])   # tag object, leased as-is
        self.assertEqual(at_old["commit"], self.s.c[2])                          # peeled

    def test_plan_never_marks_new_history_old(self):
        names = self.plan_ref_names() | {s["item"] for s in self.plan["skipped"]}
        for ref in self.new_refs:
            self.assertNotIn(ref, names)
        self.assertEqual(self.plan_wt("wt-new"), [])

    def test_plan_lists_every_stash_entry(self):
        self.assertEqual([e["sha"] for e in self.plan["stash"]], self.stash_before)
        self.assertEqual([e["index"] for e in self.plan["stash"]], [0, 1, 2])
        self.assertEqual([e["old"] for e in self.plan["stash"]], [False, True, True])

    def test_plan_worktree_classification(self):
        for name in ("wt-clean", "wt-dirty", "wt-mm", "wt-detached"):
            self.assertEqual(len(self.plan_wt(name)), 1, name)
        self.assertIsNone(self.plan_wt("wt-detached")[0]["branch"])
        self.assertEqual(self.plan_wt("wt-clean")[0]["dirty_count"], 0)
        self.assertEqual(self.plan_wt("wt-dirty")[0]["dirty_count"], 2)    # modified + untracked, not ignored
        self.assertEqual(self.plan_wt("wt-dirty")[0]["index_only"], [])
        self.assertEqual(sorted(self.plan_wt("wt-mm")[0]["index_only"]), sorted(self.staged))

    def test_plan_skips_locked_and_recent_with_their_branches(self):
        reasons = {s["item"]: s["reason"] for s in self.plan["skipped"]}
        locked = [r for i, r in reasons.items() if norm(i) == norm(self.wt["wt-locked"])]
        recent = [r for i, r in reasons.items() if norm(i) == norm(self.wt["wt-recent"])]
        self.assertTrue(locked and "locked" in locked[0], reasons)
        self.assertTrue(recent and "recent" in recent[0], reasons)
        self.assertIn("locked", reasons["refs/heads/wt-locked-br"])
        self.assertIn("recent", reasons["refs/heads/wt-recent-br"])
        self.assertEqual(self.plan["blockers"], [])

    def test_plan_records_a_full_snapshot(self):
        snap = self.plan["snapshot"]
        self.assertEqual(snap["ref|refs/heads/main"], self.refs_before["refs/heads/main"])
        wid = self.plan_wt("wt-mm")[0]["id"]
        self.assertIn("wt|%s|index" % wid, snap)
        self.assertIn("wt|%s|file|f.txt" % wid, snap)
        self.assertIn("wt|.|reflog|refs/stash", snap)
        self.assertIn("wtlist|" + norm(self.wt["wt-new"]), snap)

    # archive
    def test_archive_round_one_succeeds_and_removes_planned_refs_only(self):
        self.assertEqual(self.archive_run.returncode, 0, self.archive_run.stdout + self.archive_run.stderr)
        for name in self.plan_ref_names():
            self.assertNotIn(name, self.refs_after1)
        for name in ("refs/heads/wt-locked-br", "refs/heads/wt-recent-br"):
            self.assertIn(name, self.refs_after1)
        for name, sha in self.new_refs.items():
            self.assertEqual(self.refs_after1.get(name), sha, name)
        self.assertFalse([r for r in self.refs_after1 if r.startswith("refs/purge-archive/")])
        self.assertIn("refs/remotes/origin/main", {s["target"] for s in self.plan["symrefs"]})
        r = subprocess.run(["git", "-C", self.live, "symbolic-ref", "-q", "refs/remotes/origin/HEAD"],
                           capture_output=True, text=True, env=ENV)
        self.assertNotEqual(r.returncode, 0, "origin/HEAD left dangling: " + r.stdout)

    def test_safety_bundle_restores_every_ref_and_stash_entry(self):
        restore = restore_bundle(self.tmp.name, os.path.join(self.arch, "safety.bundle"))
        got = refs(restore)
        for name, sha in self.refs_before.items():                       # EVERY ref, not only removed ones
            if name != "refs/remotes/origin/HEAD":
                self.assertEqual(got.get(name), sha, name)
        self.assertTrue(set(self.stash_before) <= set(got.values()))
        self.assertIn(self.s.c[1], set(got.values()))
        restore2 = restore_bundle(self.tmp.name, os.path.join(self.arch2, "safety.bundle"))
        for name in ("refs/heads/wt-locked-br", "refs/heads/wt-recent-br"):
            self.assertEqual(refs(restore2).get(name), self.refs_before[name])

    def test_staged_only_content_saved_byte_exact(self):
        mm = self.plan_wt("wt-mm")[0]
        base = os.path.join(self.arch, "staged-index", "%s-wt-mm" % mm["id"])
        for name, data in self.staged.items():
            self.assertEqual(read(os.path.join(base, name)), data, name)
        self.assertFalse(os.path.exists(os.path.join(base, "README.md")))

    def test_worktree_folders_moved_intact_nothing_deleted(self):
        dirs = os.path.join(self.arch, "dirs")
        by_base = {}
        for d in os.listdir(dirs):
            for name in ("wt-clean", "wt-dirty", "wt-mm", "wt-detached"):
                if d.endswith("-" + name):
                    by_base[name] = os.path.join(dirs, d)
        self.assertEqual(set(by_base), {"wt-clean", "wt-dirty", "wt-mm", "wt-detached"})
        self.assertEqual(read(os.path.join(by_base["wt-clean"], "run.log")), b"ignored state\n")
        self.assertEqual(read(os.path.join(by_base["wt-dirty"], "cache.log")), b"ignored, holds runtime state\n")
        self.assertEqual(read(os.path.join(by_base["wt-dirty"], "f.txt")), b"edited\n")
        self.assertEqual(read(os.path.join(by_base["wt-dirty"], "untracked.txt")), b"u\n")
        self.assertEqual(read(os.path.join(by_base["wt-mm"], "f.txt")), b"work tree f.txt\n")
        for name in by_base:
            self.assertFalse(os.path.exists(self.wt[name]), name)
        manifest = read(os.path.join(self.arch, "manifest.tsv")).decode()
        self.assertIn("worktree", manifest)
        self.assertIn("refs/stash", manifest)
        self.assertIn("bundle\tsafety\t", manifest)

    def test_round_two_takes_locked_and_recent_then_gc_and_overlap(self):
        self.assertEqual(self.plan2_run.returncode, 0, self.plan2_run.stdout + self.plan2_run.stderr)
        self.assertEqual(self.archive2_run.returncode, 0, self.archive2_run.stdout + self.archive2_run.stderr)
        live_wts = wt_paths(self.live)
        self.assertNotIn(norm(self.wt["wt-locked"]), live_wts)
        self.assertNotIn(norm(self.wt["wt-recent"]), live_wts)
        self.assertIn(norm(self.wt["wt-new"]), live_wts)
        self.assertTrue(os.path.isdir(self.wt["wt-new"]))
        self.assertEqual(self.gc_default.returncode, 0, self.gc_default.stdout + self.gc_default.stderr)
        self.assertEqual(self.gc_now.returncode, 0, self.gc_now.stdout + self.gc_now.stderr)

    def test_overlap_before_cleanup_is_nonzero(self):
        self.assertEqual(self.overlap_before.returncode, 1, self.overlap_before.stdout)

    def test_default_prune_floor_keeps_fresh_objects(self):
        # objects made seconds ago are younger than the 1-hour floor, so the default gc must keep them
        self.assertEqual(self.overlap_floor.returncode, 1, self.overlap_floor.stdout)

    def test_overlap_zero_after_cleanup_and_gc(self):
        self.assertEqual(self.overlap_after.returncode, 0, self.overlap_after.stdout + self.overlap_after.stderr)
        self.assertRegex(self.overlap_after.stdout, r"\b0\b")
        for name, sha in self.new_refs.items():
            self.assertEqual(refs(self.live).get(name), sha, name)
        self.assertEqual(git(self.live, "cat-file", "-t", self.s.c[0]), "commit")  # shared root survives


class SmallFixture(unittest.TestCase):
    """Per-test live checkout: wa (dirty, c2), wb (c2), wl (locked, c1), wd (detached, c1), branch mv-br at c1."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        cls.s = Source(cls.tmp.name)
        cls.n = 0

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        SmallFixture.n += 1
        t = self.t = os.path.join(self.tmp.name, "case%d" % self.n)
        os.makedirs(t)
        c = self.s.c
        live = self.live = self.s.live(os.path.join(t, "live"))
        self.wt = {}
        for name, start in (("wa", c[2]), ("wb", c[2]), ("wl", c[1])):
            path = os.path.join(t, name)
            git(live, "worktree", "add", "-q", "-b", name + "-br", path, start)
            self.wt[name] = path
        write(os.path.join(self.wt["wa"], "f.txt"), "dirty\n", OLD_AGE)
        git(live, "worktree", "lock", self.wt["wl"])
        path = self.wt["wd"] = os.path.join(t, "wd")
        git(live, "worktree", "add", "-q", "--detach", path, c[1])
        git(live, "branch", "mv-br", c[1])
        self.arch = os.path.join(t, "arch")
        self.replan()

    def replan(self, name="plan.json"):
        self.plan = os.path.join(self.t, name)
        self.plan_run = run("plan", self.live, self.s.old, "--out", self.plan, "--include-locked")
        self.before = refs(self.live)
        return self.plan_run

    def plan_json(self):
        with open(self.plan, encoding="utf-8") as fh:
            return json.load(fh)

    def wt_id(self, name):
        return [w["id"] for w in self.plan_json()["worktrees"] if norm(w["path"]) == norm(self.wt[name])][0]

    def archive(self, *extra):
        return run("archive", self.live, self.plan, self.arch, "--include-locked", *(Q + extra))

    def archive_inproc(self, before=None, replace=None, setup=None):
        return inproc(["archive", self.live, self.plan, self.arch, "--include-locked"] + list(Q),
                      before=before, replace=replace, setup=setup)

    def gc(self, *extra):
        return run("gc", self.live, self.s.old, self.arch, "--prune-floor", "now", *(Q + extra))

    def assert_nothing_changed(self, before_refs=None):
        self.assertEqual(refs(self.live), before_refs or self.before)
        self.assertTrue(all(os.path.isdir(p) for p in self.wt.values()))
        self.assertEqual(len(wt_paths(self.live)), 5)

    def new_commit(self, msg, repo=None):
        return git(repo or self.live, "commit-tree", "newmain^{tree}", "-p", "newmain", "-m", msg)

    def add_kept_worktree(self, name="wn", start="newmain"):
        path = self.wt[name] = os.path.join(self.t, name)
        git(self.live, "worktree", "add", "-q", "--detach", path, start)
        return path

    def test_plan_ok_and_main_untouched(self):
        self.assertEqual(self.plan_run.returncode, 0, self.plan_run.stdout + self.plan_run.stderr)

    # ---- quiet gate (round-3 redesign)
    def test_archive_and_gc_refuse_without_exclusive(self):
        r = run("archive", self.live, self.plan, self.arch, "--include-locked", "--quiet-seconds", "0")
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("--exclusive", r.stdout)
        self.assertFalse(os.path.exists(self.arch))
        self.assert_nothing_changed()
        g = run("gc", self.live, self.s.old, self.arch, "--quiet-seconds", "0")
        self.assertEqual(g.returncode, 4, g.stdout + g.stderr)
        self.assertIn("--exclusive", g.stdout)

    def test_gate_refuses_on_a_lock_file(self):
        lock = os.path.join(self.live, ".git", "worktrees", self.wt_id("wb"), "index.lock")
        write(lock, b"")
        self.replan()                                     # the plan sees the lock too: only the gate refuses
        r = self.archive()
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("lock file", r.stdout)
        self.assert_nothing_changed()

    def test_gate_refuses_on_a_rebase_in_progress(self):
        wr = self.add_kept_worktree("wr")
        git(wr, "checkout", "-q", "-b", "r1")
        write(os.path.join(wr, "README.md"), "one\n")
        git(wr, "commit", "-q", "-am", "r1")
        git(wr, "checkout", "-q", "-b", "r2", "newmain")
        write(os.path.join(wr, "README.md"), "two\n")
        git(wr, "commit", "-q", "-am", "r2")
        subprocess.run(["git", "-C", wr, "rebase", "r1"], capture_output=True, env=ENV)   # stops on the conflict
        self.replan()
        r = self.archive()
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("in progress", r.stdout)
        self.assertIn(norm(self.wt["wb"]), wt_paths(self.live))

    def gate_window(self, change):
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        before = refs(self.live)
        rc, stdout, _ = inproc(["gc", self.live, self.s.old, self.arch, "--prune-floor", "now"] + list(Q),
                               setup=lambda mod: setattr(mod, "wait_quiet", lambda s: change()))
        self.assertEqual(rc, 4, stdout)
        self.assertIn("quiet window", stdout)
        return before, stdout

    def test_gate_refuses_when_a_ref_changes_in_the_quiet_window(self):
        before, _ = self.gate_window(lambda: git(self.live, "branch", "late", "newmain"))
        self.assertEqual(refs(self.live), dict(before, **{"refs/heads/late": before["refs/heads/newmain"]}))

    def test_gate_refuses_when_only_a_reflog_changes_in_the_quiet_window(self):
        def change():
            sha = git(self.live, "rev-parse", "newmain")
            git(self.live, "update-ref", "-m", "away", "refs/heads/newmain", self.s.c[0])
            git(self.live, "update-ref", "-m", "back", "refs/heads/newmain", sha)
        self.gate_window(change)

    def test_gate_refuses_when_only_an_index_changes_in_the_quiet_window(self):
        def change():
            os.utime(os.path.join(self.live, "README.md"), (OLD_AGE, OLD_AGE))
            git(self.live, "update-index", "--refresh")
        self.gate_window(change)

    # ---- the live state must equal the plan's
    def assert_refused_since_plan(self):
        before = refs(self.live)
        r = self.archive()
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("since the plan", r.stdout)
        self.assertFalse(os.path.exists(self.arch))
        self.assertEqual(refs(self.live), before)
        self.assertTrue(all(os.path.isdir(p) for p in self.wt.values()))
        return r

    def test_commit_in_a_planned_worktree_after_plan_refuses(self):
        git(self.wt["wb"], "commit", "-q", "--allow-empty", "-m", "work after the plan")
        self.assert_refused_since_plan()

    def test_planned_branch_checked_out_in_a_new_worktree_after_plan_refuses(self):    # G1-01 / R2-12
        git(self.live, "worktree", "add", "-q", os.path.join(self.t, "wnew"), "mv-br")
        self.assert_refused_since_plan()

    def test_stash_push_after_plan_refuses(self):
        write(os.path.join(self.live, "README.md"), "new stash\n")
        git(self.live, "stash", "-q")
        self.assert_refused_since_plan()

    def test_late_worktree_local_ref_after_plan_refuses(self):                      # W08
        git(self.wt["wd"], "update-ref", "refs/worktree/late", self.new_commit("late"))
        self.assert_refused_since_plan()

    def test_dirty_file_edited_again_after_plan_refuses(self):                      # mtime only
        os.utime(os.path.join(self.wt["wa"], "f.txt"), (OLD_AGE + 5, OLD_AGE + 5))
        self.assert_refused_since_plan()

    def test_main_head_moved_after_plan_refuses(self):                              # G1-16 L23
        git(self.live, "commit", "-q", "--allow-empty", "-m", "main moved")
        self.assert_refused_since_plan()

    def test_branch_moved_and_back_after_plan_refuses(self):                        # G1-01 (reflog only)
        sha = self.before["refs/heads/mv-br"]
        git(self.live, "update-ref", "-m", "elsewhere", "refs/heads/mv-br", self.s.c[2])
        git(self.live, "update-ref", "-m", "back", "refs/heads/mv-br", sha)
        self.assert_refused_since_plan()

    # ---- changes this run did not make, found after it started
    def test_change_while_the_bundle_is_written_moves_nothing(self):                # G1-02 (race probe1, L35)
        git(self.live, "commit", "-q", "--allow-empty", "-m", "reset away: needs a temp ref")
        git(self.live, "reset", "-q", "--hard", "HEAD~1")
        self.replan()
        hook =os.path.join(self.live, ".git", "hooks", "reference-transaction")
        mark, done = os.path.join(self.t, "b-mark"), os.path.join(self.t, "b-commit")
        with open(hook, "w", encoding="utf-8", newline="\n") as fh:
            fh.write('#!/bin/sh\n[ "$1" = committed ] || exit 0\ngrep -q "refs/purge-archive/" || exit 0\n'
                     '[ -e "$B_MARK" ] && exit 0\n: > "$B_MARK"\n'
                     'cd "$B_WT" && unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX && echo b > b-new.txt '
                     '&& git add b-new.txt && git commit -q -m "B work" && git rev-parse HEAD > "$B_OUT"\nexit 0\n')
        os.chmod(hook, 0o755)
        fwd = lambda p: p.replace("\\", "/")
        r = run("archive", self.live, self.plan, self.arch, "--include-locked", *Q,
                env={"B_MARK": fwd(mark), "B_WT": fwd(self.wt["wd"]), "B_OUT": fwd(done)})
        os.remove(hook)
        self.assertTrue(os.path.isfile(done), "seam did not fire: " + r.stdout + r.stderr)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("while the bundle was written", r.stdout)
        self.assertTrue(all(os.path.isdir(p) for p in self.wt.values()))
        self.assertFalse([n for n in refs(self.live) if n.startswith("refs/purge-archive/")])
        self.assertEqual(git(self.wt["wd"], "rev-parse", "HEAD"), read(done).decode().strip())
        self.assertIn("refs/heads/wb-br", refs(self.live))

    def test_unplanned_change_at_the_move_step_is_caught_and_names_the_bundle(self):
        state = {}

        def rename(real, src, dst):
            if not state:
                state["late"] = self.new_commit("another session")
                git(self.live, "update-ref", "refs/heads/late-work", state["late"])
            return real(src, dst)

        with patched_rename(rename):
            rc, stdout, _ = self.archive_inproc()
        self.assertTrue(state, "seam did not fire")
        self.assertEqual(rc, 5, stdout)
        self.assertIn("UNPLANNED CHANGE", stdout)
        self.assertIn("ref|refs/heads/late-work", stdout)
        self.assertIn(os.path.join(self.arch, "safety.bundle"), stdout)
        now = refs(self.live)
        for name in ("refs/heads/wa-br", "refs/heads/wb-br", "refs/heads/mv-br"):
            self.assertIn(name, now)                                        # no planned ref removed
        self.assertIn(norm(self.wt["wa"]), wt_paths(self.live))            # nothing pruned
        restore = restore_bundle(self.t, os.path.join(self.arch, "safety.bundle"))
        self.assertEqual(refs(restore).get("refs/heads/wb-br"), self.before["refs/heads/wb-br"])

    def test_commit_in_a_planned_worktree_at_the_move_step_is_not_lost(self):       # R2-01
        wd_id, state = self.wt_id("wd"), {}

        def rename(real, src, dst):
            if norm(src) == norm(self.wt["wd"]) and not state:
                git(self.wt["wd"], "commit", "-q", "--allow-empty", "-m", "B work at the move")
                state["b"] = git(self.wt["wd"], "rev-parse", "HEAD")
            return real(src, dst)

        with patched_rename(rename):
            rc, stdout, _ = self.archive_inproc()
        self.assertTrue(state, "seam did not fire")
        self.assertEqual(rc, 5, stdout)
        self.assertIn("UNPLANNED CHANGE", stdout)
        self.assertEqual(git(self.live, "rev-parse", "worktrees/%s/HEAD" % wd_id), state["b"])   # not pruned
        self.assertIn("refs/heads/mv-br", refs(self.live))

    def test_rename_failure_leaves_the_worktree_intact_and_removes_no_ref(self):   # R2-03
        wb_id = self.wt_id("wb")

        def rename(real, src, dst):
            if norm(src) == norm(self.wt["wb"]):
                raise PermissionError(13, "in use", src)
            return real(src, dst)

        with patched_rename(rename):
            rc, stdout, _ = self.archive_inproc()
        self.assertEqual(rc, 3, stdout)
        self.assertIn("STOPPED", stdout)
        self.assertEqual(read(os.path.join(self.wt["wb"], "f.txt")), b"secret v2\n")
        self.assertTrue(os.path.isdir(os.path.join(self.live, ".git", "worktrees", wb_id)))
        self.assertIn(norm(self.wt["wb"]), wt_paths(self.live))
        self.assertEqual(refs(self.live), self.before)                       # no ref removed, no temp ref left
        for name in ("wl", "wd"):                                            # nothing after it moved
            self.assertTrue(os.path.isdir(self.wt[name]), name)

    def test_archive_dir_on_another_volume_is_refused_before_any_change(self):
        arch = self.arch
        rc, stdout, _ = self.archive_inproc(
            setup=lambda mod: setattr(mod, "device_of", lambda p: 2 if norm(p) == norm(arch) else 1))
        self.assertEqual(rc, 2, stdout)
        self.assertIn("another volume", stdout)
        self.assertFalse(os.path.exists(arch))
        self.assert_nothing_changed()

    def test_branch_checked_out_just_before_removal_is_kept(self):                  # R2-12 / G1-01
        sha, wnew = self.before["refs/heads/mv-br"], os.path.join(self.t, "wnew")

        def replace(real, repo, args, kw):
            if args[:2] == ("worktree", "prune"):
                r = real(repo, *args, **kw)
                git(self.live, "worktree", "add", "-q", wnew, "mv-br")      # another session, after the prune
                return r
            return None

        rc, stdout, _ = self.archive_inproc(replace=replace)
        self.assertEqual(rc, 5, stdout)
        self.assertIn("after the prune", stdout)
        self.assertEqual(refs(self.live).get("refs/heads/mv-br"), sha)
        self.assertEqual(git(wnew, "rev-parse", "HEAD"), sha)

    def test_worktree_still_registered_after_prune_is_caught(self):                 # G1-16 L37
        def replace(real, repo, args, kw):
            return fake_result(0) if args[:2] == ("worktree", "prune") else None

        rc, stdout, _ = self.archive_inproc(replace=replace)
        self.assertEqual(rc, 5, stdout)
        self.assertIn("after the prune", stdout)
        self.assertIn("refs/heads/wb-br", refs(self.live))

    def test_ref_moving_at_removal_fails_leased_and_is_caught(self):                # G1-04 (L38)
        c1, state = self.s.c[1], {}

        def before(repo, args, kw):
            if args[:2] == ("update-ref", "--stdin") and "delete refs/heads/mv-br" in (kw.get("stdin") or "") \
                    and not state:
                n = git(self.live, "commit-tree", c1 + "^{tree}", "-p", c1, "-m", "concurrent work")
                git(self.live, "update-ref", "refs/heads/mv-br", n, c1)
                state["new"] = n

        rc, stdout, _ = self.archive_inproc(before=before)
        self.assertTrue(state, "seam did not fire")
        self.assertEqual(rc, 5, stdout)
        self.assertIn("REF REMOVAL FAILED", stdout)
        self.assertEqual(refs(self.live).get("refs/heads/mv-br"), state["new"])
        self.assertIn("refs/heads/wb-br", refs(self.live))

    # ---- refusals before anything changes
    def test_locked_worktree_in_plan_needs_the_flag_at_archive(self):
        r = run("archive", self.live, self.plan, self.arch, *Q)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--include-locked", r.stdout)
        self.assert_nothing_changed()

    def test_existing_archive_dir_refused(self):
        os.makedirs(self.arch)
        r = self.archive()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assert_nothing_changed()

    def test_failure_before_bundle_moves_nothing(self):
        git(self.live, "commit", "-q", "--allow-empty", "-m", "reset away")
        gone = git(self.live, "rev-parse", "HEAD")
        git(self.live, "reset", "-q", "--hard", "HEAD~1")                  # gone: reflog-only, needs a temp ref
        git(self.live, "update-ref", "refs/purge-archive/obj/" + gone, "newmain")   # temp ref name taken
        self.replan()
        r = self.archive()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assert_nothing_changed()

    def test_bundle_lacking_a_head_aborts_with_nothing_moved(self):
        def replace(real, repo, args, kw):
            if args[:2] == ("bundle", "list-heads"):
                r = real(repo, *args, **kw)
                r.stdout = ""
                return r
            return None

        rc, stdout, _ = self.archive_inproc(replace=replace)
        self.assertEqual(rc, 2, stdout)
        self.assert_nothing_changed()                                       # temp refs dropped again too

    def test_bundle_verify_failure_aborts_with_nothing_moved(self):              # G1-16 L29
        def replace(real, repo, args, kw):
            return fake_result(1) if args[:2] == ("bundle", "verify") else None

        rc, stdout, _ = self.archive_inproc(replace=replace)
        self.assertEqual(rc, 2, stdout)
        self.assertIn("bundle verify failed", stdout)
        self.assert_nothing_changed()

    def test_missing_worktree_dir_is_skipped_with_branch(self):
        gone = self.wt["wb"]
        shutil.move(gone, gone + "-elsewhere")
        out = os.path.join(self.t, "plan-missing.json")
        r = run("plan", self.live, self.s.old, "--out", out, "--include-locked")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        plan = json.load(open(out, encoding="utf-8"))
        reasons = {s["item"]: s["reason"] for s in plan["skipped"]}
        self.assertIn("refs/heads/wb-br", reasons)
        self.assertNotIn("refs/heads/wb-br", {x["name"] for x in plan["refs"]})

    def test_main_worktree_on_old_history_is_blocker(self):
        live = self.s.live(os.path.join(self.t, "live-old"), repoint=False)
        out = os.path.join(self.t, "plan-blocked.json")
        r = run("plan", live, self.s.old, "--out", out)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        plan = json.load(open(out, encoding="utf-8"))
        self.assertTrue(plan["blockers"])
        self.assertIn("BLOCKER", r.stdout)
        self.assertNotIn("refs/heads/main", {x["name"] for x in plan["refs"]})
        before = refs(live)
        a = run("archive", live, out, os.path.join(self.t, "arch-blocked"), *Q)
        self.assertEqual(a.returncode, 2, a.stdout + a.stderr)
        self.assertEqual(refs(live), before)

    # ---- the safety bundle (R2-04, W06, W07)
    def test_safety_bundle_holds_reflog_only_and_worktree_local_commits(self):
        live, wd = self.live, self.wt["wd"]
        git(live, "checkout", "-q", "--detach", self.s.c[2])
        git(live, "commit", "-q", "--allow-empty", "-m", "user: unpushed work on old history")
        work = {"reflog-only commit in main (R2-04)": git(live, "rev-parse", "HEAD")}
        git(live, "checkout", "-q", "main")
        wdc = lambda m: git(wd, "commit-tree", "newmain^{tree}", "-p", "newmain", "-m", m)
        for ref in ("refs/bisect/bad", "refs/rewritten/onto"):                   # W07
            work[ref] = wdc(ref)
            git(wd, "update-ref", ref, work[ref])
        work["FETCH_HEAD only (W06)"] = wdc("fetched")
        fetch = git(wd, "rev-parse", "--git-path", "FETCH_HEAD")
        fetch = fetch if os.path.isabs(fetch) else os.path.join(wd, fetch)
        write(fetch, "%s\t\tbranch 'x' of ../elsewhere\n" % work["FETCH_HEAD only (W06)"])
        orig = wdc("only in ORIG_HEAD")
        git(wd, "update-ref", "ORIG_HEAD", orig)
        work["ORIG_HEAD"] = orig
        wn = self.add_kept_worktree()
        work["refs/worktree/keep in a kept worktree"] = self.new_commit("kept worktree's own ref")
        git(wn, "update-ref", "refs/worktree/keep", work["refs/worktree/keep in a kept worktree"])
        self.replan()
        r = self.archive()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse([n for n in refs(live) if n.startswith("refs/purge-archive/")])
        restore = restore_bundle(self.t, os.path.join(self.arch, "safety.bundle"))
        for label, sha in work.items():
            self.assertTrue(exists(restore, sha), label)
        manifest = read(os.path.join(self.arch, "manifest.tsv")).decode()
        self.assertIn("refs/bisect/bad", manifest)
        self.assertIn("FETCH_HEAD", manifest)

    # ---- gc
    def test_gc_needs_the_archive_safety_bundle(self):
        r = self.gc()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("run archive first", r.stdout)
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        write(os.path.join(self.arch, "safety.bundle"), b"not a bundle\n")
        r = self.gc()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("bundle", r.stdout)

    def test_gc_refuses_when_a_reflog_it_edits_changed_since_the_archive(self):
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        git(self.live, "commit", "-q", "--allow-empty", "-m", "made after the archive")
        late = git(self.live, "rev-parse", "HEAD")
        git(self.live, "reset", "-q", "--hard", "HEAD~1")                  # late: only in reflogs gc edits
        head = reflog(self.live, "HEAD")
        r = self.gc()
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("not in the safety bundle", r.stdout)
        self.assertEqual(reflog(self.live, "HEAD"), head)
        self.assertTrue(exists(self.live, late))

    def test_gc_keeps_other_sessions_stash_and_reflog_recovery(self):           # G1-03 (race probe3, pgc)
        live = self.live
        git(live, "checkout", "-q", "-b", "b-work")
        for name in ("s1.txt", "s2.txt"):
            write(os.path.join(live, name), name + "\n")
            git(live, "add", name)
            git(live, "stash", "-q")
        write(os.path.join(live, "y.txt"), "yesterday\n")
        git(live, "add", "y.txt")
        git(live, "commit", "-q", "-m", "work later reset away")
        y = git(live, "rev-parse", "HEAD")
        git(live, "reset", "-q", "--hard", "HEAD~1")
        stash = reflog(live, "refs/stash")
        self.assertEqual(len(stash), 2)
        self.replan()
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        g = self.gc()
        self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        self.assertEqual(reflog(live, "refs/stash"), stash)
        self.assertEqual(git(live, "cat-file", "-t", y), "commit")
        self.assertIn(y, reflog(live, "refs/heads/b-work"))
        o = run("overlap", live, self.s.old)
        self.assertEqual(o.returncode, 0, o.stdout + o.stderr)

    def test_gc_deletes_interleaved_old_entries_and_keeps_the_rest(self):       # G02 (R2-05)
        c = self.s.c
        m, n, p = (self.new_commit(x) for x in ("M", "N", "P: another session's recovery point"))
        for sha in (p, c[1], n, c[2], m):
            git(self.live, "update-ref", "-m", "move", "refs/heads/x", sha)
        self.assertEqual(reflog(self.live, "refs/heads/x"), [m, c[2], n, c[1], p])
        self.replan()
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        g = self.gc()
        self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        self.assertEqual(reflog(self.live, "refs/heads/x"), [m, n, p])
        self.assertTrue(exists(self.live, p))

    def keep_stash_in_plan(self):
        plan = self.plan_json()
        plan["refs"] = [r for r in plan["refs"] if r["name"] != "refs/stash"]
        plan["stash"] = []
        with open(self.plan, "w", encoding="utf-8") as fh:
            json.dump(plan, fh)

    def stash_on(self, path, text):
        write(os.path.join(path, "f.txt" if path != self.live else "README.md"), text)
        git(path, "stash", "-q")
        return git(self.live, "rev-parse", "refs/stash")

    def test_gc_old_stash_entry_on_top_leaves_the_stash_on_the_new_one(self):   # G04
        new = self.stash_on(self.live, "new stash\n")
        self.stash_on(self.wt["wb"], "old stash\n")
        self.replan()
        self.keep_stash_in_plan()                    # as if archive had left the stash (seam: edited plan)
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        g = self.gc()
        self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        self.assertEqual(git(self.live, "rev-parse", "refs/stash"), new)
        self.assertEqual(reflog(self.live, "refs/stash"), [new])

    def test_gc_stash_with_every_entry_old_is_removed(self):                     # G05
        self.stash_on(self.wt["wb"], "old stash 1\n")
        self.stash_on(self.wt["wb"], "old stash 2\n")
        self.replan()
        self.keep_stash_in_plan()
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        g = self.gc()
        self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        self.assertNotIn("refs/stash", refs(self.live))

    def test_gc_stash_pushed_during_gc_is_caught(self):                          # R2-02
        self.stash_on(self.live, "new stash\n")
        self.stash_on(self.wt["wb"], "old stash\n")
        self.replan()
        self.keep_stash_in_plan()
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        state = {}

        def before(repo, args, kw):
            if args[:2] == ("reflog", "delete") and any(x.startswith("refs/stash@") for x in args) and not state:
                state["c"] = self.stash_on(self.live, "session C stash\n")

        rc, stdout, _ = inproc(["gc", self.live, self.s.old, self.arch, "--prune-floor", "now"] + list(Q),
                               before=before)
        self.assertTrue(state, "seam did not fire")
        self.assertEqual(rc, 5, stdout)
        self.assertIn("UNPLANNED CHANGE", stdout)
        self.assertIn("safety.bundle", stdout)

    def test_gc_removes_a_linked_worktree_head_reflog_entry(self):              # G06
        wn = self.add_kept_worktree("wn", self.s.c[2])
        git(wn, "checkout", "-q", "--detach", "newmain")
        self.replan()
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        wn_id = os.path.basename(git(wn, "rev-parse", "--git-dir"))
        self.assertIn(self.s.c[2], reflog(self.live, "worktrees/%s/HEAD" % wn_id))
        g = self.gc()
        self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        self.assertNotIn(self.s.c[2], reflog(self.live, "worktrees/%s/HEAD" % wn_id))
        o = run("overlap", self.live, self.s.old)
        self.assertEqual(o.returncode, 0, o.stdout + o.stderr)

    def test_gc_failure_is_nonzero(self):                                       # G07
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)

        def replace(real, repo, args, kw):
            return fake_result(1) if "gc" in args and any(x.startswith("--prune=") for x in args) else None

        rc, stdout, _ = inproc(["gc", self.live, self.s.old, self.arch] + list(Q), replace=replace)
        self.assertEqual(rc, 1, stdout)
        self.assertIn("exit 1", stdout)

    def test_gc_keeps_commits_held_only_by_another_worktrees_local_refs(self):  # R2-11
        wn = self.add_kept_worktree()
        keep, bad = self.new_commit("refs/worktree/keep"), self.new_commit("refs/bisect/bad")
        git(wn, "update-ref", "refs/worktree/keep", keep)
        git(wn, "update-ref", "refs/bisect/bad", bad)
        self.replan()
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        g = self.gc()
        self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        self.assertTrue(exists(self.live, keep), "refs/worktree/keep commit pruned")
        self.assertTrue(exists(self.live, bad), "refs/bisect/bad commit pruned")
        self.assertFalse([n for n in refs(self.live) if n.startswith("refs/purge-keep/")])

    def test_gc_removes_an_entry_whose_previous_value_is_old(self):            # R2-14
        git(self.live, "branch", "feature", self.s.c[2])
        git(self.live, "reflog", "expire", "--expire=now", "refs/heads/feature")   # aged out (auto-gc)
        git(self.live, "update-ref", "refs/heads/feature", "newmain")              # moved onto new history
        self.replan()
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        o = run("overlap", self.live, self.s.old)
        self.assertIn("reflog refs/heads/feature: 1 entry whose previous value is old history", o.stdout)
        g = self.gc()
        self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        o = run("overlap", self.live, self.s.old)
        self.assertEqual(o.returncode, 0, o.stdout + o.stderr)
        self.assertEqual(git(self.live, "rev-parse", "refs/heads/feature"), git(self.live, "rev-parse", "newmain"))

    def test_non_ascii_branch_through_plan_archive_gc_overlap(self):           # U01
        name = "refs/heads/feat/ünï"
        git(self.live, "update-ref", name, self.s.c[1])
        self.replan()
        self.assertIn(name, {r["name"] for r in self.plan_json()["refs"]})
        a = self.archive()
        self.assertEqual(a.returncode, 0, a.stdout + a.stderr)
        self.assertNotIn(name, refs(self.live))
        restore = restore_bundle(self.t, os.path.join(self.arch, "safety.bundle"))
        self.assertEqual(refs(restore).get(name), self.s.c[1])
        g = self.gc()
        self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        o = run("overlap", self.live, self.s.old)
        self.assertEqual(o.returncode, 0, o.stdout + o.stderr)

    # ---- changed / plan (round-1 merge-gate fixes, PR 297)
    def test_changed_writes_dropped_blobs_and_trees(self):                      # G1-15
        objs = self.s.old + ".objects"
        self.assertTrue(os.path.isfile(objs))
        listed = set(read(objs).decode().split())
        self.assertIn(git(self.live, "rev-parse", self.s.c[1] + ":f.txt"), listed)
        self.assertIn(git(self.live, "rev-parse", self.s.c[1] + "^{tree}"), listed)
        self.assertNotIn(git(self.live, "rev-parse", self.s.c[0] + ":README.md"), listed)   # unchanged blob
        self.assertFalse(listed & set(self.s.c))                                             # commits: own file

    def test_tag_on_dropped_blob_or_tree_is_planned(self):                       # G1-15
        git(self.live, "tag", "-a", "blobtag", "-m", "saved file",
            git(self.live, "rev-parse", self.s.c[1] + ":f.txt"))
        git(self.live, "tag", "treetag", git(self.live, "rev-parse", self.s.c[1] + "^{tree}"))
        git(self.live, "tag", "oktag", git(self.live, "rev-parse", self.s.c[0] + ":README.md"))
        out = os.path.join(self.t, "plan-blob.json")
        run("plan", self.live, self.s.old, "--out", out, "--include-locked")
        names = {x["name"] for x in json.load(open(out, encoding="utf-8"))["refs"]}
        self.assertIn("refs/tags/blobtag", names)
        self.assertIn("refs/tags/treetag", names)
        self.assertNotIn("refs/tags/oktag", names)

    def test_overlap_counts_a_dropped_blob(self):                                # G1-15
        bare = os.path.join(self.t, "blob-only.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True, env=ENV)
        subprocess.run(["git", "-C", bare, "hash-object", "-w", "--stdin"], input=b"secret v1\n", check=True,
                       env=ENV, capture_output=True)
        r = run("overlap", bare, self.s.old)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)

    def test_branch_reaching_old_only_through_second_parent_is_planned(self):   # G1-13 (L06)
        m = git(self.live, "commit-tree", "newmain^{tree}", "-p", "newmain", "-p", self.s.c[1], "-m", "merge")
        git(self.live, "update-ref", "refs/heads/merged-old", m)
        out = os.path.join(self.t, "plan-merge.json")
        run("plan", self.live, self.s.old, "--out", out, "--include-locked")
        self.assertIn("refs/heads/merged-old", {x["name"] for x in json.load(open(out, encoding="utf-8"))["refs"]})

    def test_relative_paths_are_resolved_against_the_working_directory(self):   # G1-18
        r = run("archive", "live", "plan.json", "arch-rel", "--include-locked", *Q, cwd=self.t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.t, "arch-rel", "safety.bundle")))
        self.assertFalse(os.path.exists(os.path.join(self.live, "arch-rel")))


def purge_fixture(t, build):
    """src built by build(src) -> backup mirror, purged mirror (secret -> [private], messages too), old file."""
    src = os.path.join(t, "src")
    subprocess.run(["git", "init", "-q", "-b", "main", src], check=True, env=ENV)
    info = build(src)
    backup, purged = os.path.join(t, "backup.git"), os.path.join(t, "purged.git")
    subprocess.run(["git", "clone", "-q", "--mirror", src, backup], check=True, env=ENV)
    subprocess.run(["git", "clone", "-q", "--mirror", "--no-local", backup, purged], check=True, env=ENV)
    rules = os.path.join(t, "rules.txt")
    write(rules, "secret==>[private]\n")
    git(purged, "filter-repo", "--force", "--replace-text", rules, "--replace-message", rules)
    out = os.path.join(t, "old.txt")
    r = run("changed", purged, backup, "--out", out)
    return src, backup, purged, out, r, info


class ChangedTagOnlyTest(unittest.TestCase):
    def test_changed_includes_a_commit_and_blob_reachable_only_from_a_tag(self):   # G1-05 (L04), L04b
        def build(src):
            write(os.path.join(src, "r.md"), "r\n")
            git(src, "add", "-A")
            git(src, "commit", "-q", "-m", "c0")
            git(src, "checkout", "-q", "--detach")
            write(os.path.join(src, "rel.txt"), "secret in release\n")
            git(src, "add", "-A")
            git(src, "commit", "-q", "-m", "release")
            info = (git(src, "rev-parse", "HEAD"), git(src, "rev-parse", "HEAD:rel.txt"))
            git(src, "tag", "-a", "v1", "-m", "release")
            git(src, "checkout", "-q", "main")
            return info

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            _src, _b, _p, out, r, (rel, blob) = purge_fixture(t, build)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn(rel, read(out).decode().split())
            self.assertIn(blob, read(out + ".objects").decode().split())


class TagMessageTest(unittest.TestCase):
    def test_annotated_tag_with_a_rewritten_message_on_a_kept_commit_is_planned(self):   # L06b
        def build(src):
            write(os.path.join(src, "r.md"), "r\n")
            git(src, "add", "-A")
            git(src, "commit", "-q", "-m", "c0")
            git(src, "tag", "-a", "v0", "-m", "closing price secret 123457")
            write(os.path.join(src, "f.txt"), "secret\n")
            git(src, "add", "-A")
            git(src, "commit", "-q", "-m", "c1")
            return git(src, "rev-parse", "refs/tags/v0")

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            src, _b, purged, old, r, tagobj = purge_fixture(t, build)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn(tagobj, read(old + ".objects").decode().split())
            live = os.path.join(t, "live")
            subprocess.run(["git", "clone", "-q", src, live], check=True, env=ENV)
            git(live, "fetch", "-q", purged, "refs/heads/main:refs/heads/newmain")
            git(live, "checkout", "-q", "-B", "main", "newmain")
            plan = os.path.join(t, "plan.json")
            run("plan", live, old, "--out", plan)
            with open(plan, encoding="utf-8") as fh:
                self.assertIn("refs/tags/v0", {x["name"] for x in json.load(fh)["refs"]})


class UnitTest(unittest.TestCase):
    def test_bundle_heads_check_reports_missing_and_moved(self):
        mod = load_module()
        a, b = "a" * 40, "b" * 40
        listed = "%s refs/heads/x\n%s refs/heads/y\n" % (a, a)
        self.assertEqual(mod.missing_heads({"refs/heads/x": a, "refs/heads/y": a}, listed), [])
        self.assertEqual(mod.missing_heads({"refs/heads/x": a, "refs/heads/y": b, "refs/heads/z": a}, listed),
                         ["refs/heads/y", "refs/heads/z"])

    def test_index_only_status_codes(self):
        mod = load_module()
        self.assertTrue(all(mod.index_only(x) for x in ("MM", "AM", "RM", "MD", "AD")))
        self.assertFalse(any(mod.index_only(x) for x in (" M", "M ", "A ", "??", " D")))

    def test_reflog_deletions_follow_the_rewrite(self):
        mod = load_module()
        z = "0" * 40
        bad = lambda s: s.startswith("o")
        e = [("o2", "M"), ("N", "o2"), ("o1", "N"), ("P", "o1"), (z, "P")]          # newest first
        self.assertEqual(mod.reflog_deletions(e, bad), [3, 1])
        self.assertEqual(mod.reflog_deletions([("o1", "X")], bad), [0])            # R2-14: no rewrite otherwise
        self.assertEqual(mod.reflog_deletions([("A", "B"), (z, "A")], bad), [])


if __name__ == "__main__":
    unittest.main()
