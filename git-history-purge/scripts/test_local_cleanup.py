"""Tests for local_cleanup.py (stdlib unittest; gated by tools/run_skill_suites.sh).

Real git in temp dirs. The purge is a real `git filter-repo --replace-text` run on a mirror clone
of the backup (SKILL.md Step 3). The FIRST commit holds nothing private, so the purge keeps its SHA
and new branches share it: such branches must NOT count as old history (finding R3-01).
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


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false"] + list(args), capture_output=True,
                          text=True, check=True, env=ENV).stdout.strip()


def run(*args, cwd=None, env=None):
    return subprocess.run([sys.executable, "-I", SCRIPT] + list(args), capture_output=True, text=True,
                          env=dict(ENV, **(env or {})), cwd=cwd)


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


def inproc(argv, before=None, replace=None):
    """Run local_cleanup.main in-process with a seam around its git() calls.
    before(repo, args, kw) runs just before the real call; replace(real, repo, args, kw) may return a result
    instead of calling git. Returns (rc, stdout, [(repo, args, stdin)])."""
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


def fake_result(rc=0, stdout=""):
    return subprocess.CompletedProcess(["git"], rc, stdout, "")


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
        cls.stash_before = git(live, "reflog", "show", "--format=%H", "refs/stash").split()
        # Step 6 sequence
        cls.overlap_before = run("overlap", live, s.old)
        cls.plan_path = os.path.join(t, "plan.json")
        cls.plan_run = run("plan", live, s.old, "--out", cls.plan_path)
        with open(cls.plan_path, encoding="utf-8") as fh:
            cls.plan = json.load(fh)
        cls.arch = os.path.join(t, "arch1")
        cls.archive_run = run("archive", live, cls.plan_path, cls.arch)
        cls.refs_after1 = refs(live)
        cls.plan2_path = os.path.join(t, "plan2.json")
        cls.plan2_run = run("plan", live, s.old, "--out", cls.plan2_path, "--include-locked",
                            "--min-age-hours", "0")
        cls.arch2 = os.path.join(t, "arch2")
        cls.archive2_run = run("archive", live, cls.plan2_path, cls.arch2, "--include-locked")
        cls.gc_default = run("gc", live, s.old)
        cls.overlap_floor = run("overlap", live, s.old)
        cls.gc_now = run("gc", live, s.old, "--prune-floor", "now")
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

    def test_changed_unions_several_backups(self):
        t = self.tmp.name
        late_src = os.path.join(t, "late-src")
        subprocess.run(["git", "clone", "-q", self.s.src, late_src], check=True, env=ENV)
        git(late_src, "commit", "-q", "--allow-empty", "-m", "late push")
        backup2 = os.path.join(t, "backup2.git")
        subprocess.run(["git", "clone", "-q", "--mirror", late_src, backup2], check=True, env=ENV)
        out = os.path.join(t, "old2.txt")
        r = run("changed", self.s.purged, self.s.backup, backup2, "--out", out)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        both = read(out).decode().split()
        self.assertIn(git(late_src, "rev-parse", "HEAD"), both)
        self.assertEqual(set(both) - set(read(self.s.old).decode().split()), {git(late_src, "rev-parse", "HEAD")})

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

    def test_bundle_restores_every_removed_ref_and_stash_entry(self):
        restore = os.path.join(self.tmp.name, "restore")
        subprocess.run(["git", "init", "-q", restore], check=True, env=ENV)
        for arch in (self.arch, self.arch2):
            git(restore, "fetch", "-q", os.path.join(arch, "refs.bundle"), "refs/*:refs/*")
        got = refs(restore)
        for name in self.plan_ref_names():
            self.assertEqual(got.get(name), self.refs_before[name], name)
        stash_shas = {v for k, v in got.items() if k.startswith("refs/purge-archive/stash/")}
        self.assertEqual(stash_shas, set(self.stash_before))
        self.assertIn(self.s.c[1], {v for k, v in got.items() if k.startswith("refs/purge-archive/wt/")})
        for name in ("refs/heads/wt-locked-br", "refs/heads/wt-recent-br"):
            self.assertEqual(got.get(name), self.refs_before[name])

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
    """Per-test live checkout for archive edge cases (fresh state each test)."""

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
        self.plan = os.path.join(t, "plan.json")
        self.plan_run = run("plan", live, self.s.old, "--out", self.plan, "--include-locked")
        self.before = refs(live)

    def test_plan_ok_and_main_untouched(self):
        self.assertEqual(self.plan_run.returncode, 0, self.plan_run.stdout + self.plan_run.stderr)

    def test_anything_changed_after_plan_is_skipped_not_acted_on(self):
        write(os.path.join(self.wt["wa"], "f.txt"), "changed after plan\n", OLD_AGE + 60)
        git(self.live, "branch", "-f", "mv-br", self.s.c[2])
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        now = refs(self.live)
        self.assertTrue(os.path.isdir(self.wt["wa"]))
        self.assertEqual(read(os.path.join(self.wt["wa"], "f.txt")), b"changed after plan\n")
        self.assertIn("refs/heads/wa-br", now)
        self.assertEqual(now.get("refs/heads/mv-br"), self.s.c[2])
        self.assertFalse(os.path.exists(self.wt["wb"]))                 # unchanged items still archived
        self.assertNotIn("refs/heads/wb-br", now)
        self.assertFalse(os.path.exists(self.wt["wl"]))                 # --include-locked
        self.assertNotIn("refs/heads/wl-br", now)

    def test_mtime_only_change_is_skipped(self):
        os.utime(os.path.join(self.wt["wa"], "f.txt"), (OLD_AGE + 5, OLD_AGE + 5))
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(os.path.isdir(self.wt["wa"]))
        self.assertIn("refs/heads/wa-br", refs(self.live))

    def test_locked_without_flag_is_skipped_at_archive(self):
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"))
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertTrue(os.path.isdir(self.wt["wl"]))
        self.assertIn("refs/heads/wl-br", refs(self.live))

    def test_existing_archive_dir_refused(self):
        arch = os.path.join(self.t, "arch")
        os.makedirs(arch)
        r = run("archive", self.live, self.plan, arch, "--include-locked")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(refs(self.live), self.before)
        self.assertTrue(all(os.path.isdir(p) for p in self.wt.values()))

    def test_failure_before_bundle_moves_nothing(self):
        wd_id = [w["id"] for w in json.load(open(self.plan, encoding="utf-8"))["worktrees"]
                 if norm(w["path"]) == norm(self.wt["wd"])][0]
        git(self.live, "update-ref", "refs/purge-archive/wt/" + wd_id, "newmain")   # temp ref name taken
        before = refs(self.live)
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(refs(self.live), before)
        self.assertTrue(all(os.path.isdir(p) for p in self.wt.values()))
        self.assertEqual(len(wt_paths(self.live)), 5)

    def test_bundle_lacking_a_head_aborts_with_nothing_moved(self):
        # in-process run with `git bundle list-heads` answering nothing: the heads check must refuse
        mod = load_module()
        real = mod.git

        def fake(repo, *args, **kw):
            r = real(repo, *args, **kw)
            if args[:2] == ("bundle", "list-heads"):
                r.stdout = ""
            return r

        mod.git = fake
        old_env = dict(os.environ)
        os.environ.update(ENV)
        try:
            rc = mod.main(["archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked"])
        finally:
            os.environ.clear()
            os.environ.update(old_env)
        self.assertEqual(rc, 2)
        self.assertEqual(refs(self.live), self.before)                  # temp refs dropped again too
        self.assertTrue(all(os.path.isdir(p) for p in self.wt.values()))
        self.assertEqual(len(wt_paths(self.live)), 5)

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
        a = run("archive", live, out, os.path.join(self.t, "arch-blocked"))
        self.assertEqual(a.returncode, 2, a.stdout + a.stderr)
        self.assertEqual(refs(live), before)


    # ---- round-1 merge-gate fixes (PR 297)
    def locked_paths(self):
        out, cur, locked = git(self.live, "worktree", "list", "--porcelain"), None, set()
        for line in out.splitlines():
            if line.startswith("worktree "):
                cur = norm(line[9:])
            elif line.startswith("locked"):
                locked.add(cur)
        return locked

    def archive_inproc(self, before=None, replace=None, plan=None):
        return inproc(["archive", self.live, plan or self.plan, os.path.join(self.t, "arch"), "--include-locked"],
                      before=before, replace=replace)

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

    def test_branch_checked_out_in_new_worktree_after_plan_is_kept(self):       # G1-01 (race probe2)
        sha = self.before["refs/heads/mv-br"]
        git(self.live, "worktree", "add", "-q", os.path.join(self.t, "wnew"), "mv-br")
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(refs(self.live).get("refs/heads/mv-br"), sha)
        self.assertRegex(r.stdout, r"SKIP refs/heads/mv-br: .*checked out")
        self.assertNotIn("refs/heads/wb-br", refs(self.live))                  # the rest still archived

    def test_branch_checked_out_just_before_removal_is_kept(self):              # G1-01 (live re-read)
        sha = self.before["refs/heads/mv-br"]
        wnew = os.path.join(self.t, "wnew")

        def replace(real, repo, args, kw):
            if args[:2] == ("worktree", "prune"):
                r = real(repo, *args, **kw)
                git(self.live, "worktree", "add", "-q", wnew, "mv-br")      # another session, after the prune
                return r
            return None

        rc, stdout, _ = self.archive_inproc(replace=replace)
        self.assertEqual(rc, 1, stdout)
        self.assertEqual(refs(self.live).get("refs/heads/mv-br"), sha)
        self.assertRegex(stdout, r"SKIP refs/heads/mv-br: .*checked out")
        self.assertNotIn("REF REMOVAL FAILED", stdout)
        self.assertNotIn("refs/heads/wb-br", refs(self.live))

    def test_branch_whose_reflog_moved_is_kept(self):                            # G1-01 (reflog moved, tip same)
        sha = self.before["refs/heads/mv-br"]
        git(self.live, "update-ref", "-m", "elsewhere", "refs/heads/mv-br", self.s.c[2])
        git(self.live, "update-ref", "-m", "back", "refs/heads/mv-br", sha)
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(refs(self.live).get("refs/heads/mv-br"), sha)
        self.assertRegex(r.stdout, r"SKIP refs/heads/mv-br: reflog")

    def test_detached_worktree_with_new_commit_after_plan_is_skipped(self):     # G1-02 (testvalidity L19)
        write(os.path.join(self.wt["wd"], "work.txt"), "new work after the plan\n")
        git(self.wt["wd"], "add", "work.txt")
        git(self.wt["wd"], "commit", "-q", "-m", "new work")
        new = git(self.wt["wd"], "rev-parse", "HEAD")
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("HEAD moved", r.stdout)
        self.assertTrue(os.path.isdir(self.wt["wd"]))
        self.assertIn(norm(self.wt["wd"]), wt_paths(self.live))
        run("gc", self.live, self.s.old, "--prune-floor", "now")
        self.assertEqual(git(self.wt["wd"], "rev-parse", "HEAD"), new)

    def test_commit_between_recheck_and_move_is_not_lost(self):                 # G1-02 (race probe1, L35)
        hook = os.path.join(self.live, ".git", "hooks", "reference-transaction")
        mark, done = os.path.join(self.t, "b-mark"), os.path.join(self.t, "b-commit")
        with open(hook, "w", encoding="utf-8", newline="\n") as fh:
            fh.write('#!/bin/sh\n[ "$1" = committed ] || exit 0\ngrep -q "refs/purge-archive/wt/" || exit 0\n'
                     '[ -e "$B_MARK" ] && exit 0\n: > "$B_MARK"\n'
                     'cd "$B_WT" && unset GIT_DIR GIT_INDEX_FILE GIT_WORK_TREE GIT_PREFIX && echo b > b-new.txt '
                     '&& git add b-new.txt && git commit -q -m "B work" && git rev-parse HEAD > "$B_OUT"\nexit 0\n')
        os.chmod(hook, 0o755)
        fwd = lambda p: p.replace("\\", "/")
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked",
                env={"B_MARK": fwd(mark), "B_WT": fwd(self.wt["wd"]), "B_OUT": fwd(done)})
        os.remove(hook)
        self.assertTrue(os.path.isfile(done), "seam did not fire: " + r.stdout + r.stderr)
        b_commit = read(done).decode().strip()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("HEAD moved", r.stdout)
        self.assertTrue(os.path.isdir(self.wt["wd"]))
        self.assertIn(norm(self.wt["wd"]), wt_paths(self.live))
        self.assertNotIn(norm(self.wt["wd"]), self.locked_paths())             # our lock released on skip
        run("gc", self.live, self.s.old, "--prune-floor", "now")
        self.assertEqual(git(self.wt["wd"], "rev-parse", "HEAD"), b_commit)
        self.assertFalse(os.path.exists(self.wt["wb"]))                      # unchanged ones still moved

    def test_each_worktree_is_locked_across_its_recheck_and_move(self):         # G1-02 (lock)
        rc, stdout, calls = self.archive_inproc()
        self.assertEqual(rc, 0, stdout)
        for name in ("wa", "wb", "wd"):
            p = norm(self.wt[name])
            seq = [(norm(repo), args) for repo, args, _ in calls]
            lock = [i for i, (_r, a) in enumerate(seq) if a[:2] == ("worktree", "lock") and norm(a[-1]) == p]
            unlock = [i for i, (_r, a) in enumerate(seq) if a[:2] == ("worktree", "unlock") and norm(a[-1]) == p]
            self.assertTrue(lock and unlock, name + ": " + stdout)
            status = [i for i, (r, a) in enumerate(seq) if r == p and a[:1] == ("status",)]
            self.assertTrue([i for i in status if lock[-1] < i < unlock[-1]], name + ": no live re-check while locked")
        self.assertFalse(self.locked_paths())

    def test_gc_keeps_other_sessions_stash_and_reflog_recovery(self):           # G1-03 (race probe3, pgc)
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
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
        stash = git(live, "reflog", "show", "--format=%H", "refs/stash").split()
        self.assertEqual(len(stash), 2)
        g = run("gc", live, self.s.old, "--prune-floor", "now")
        self.assertEqual(g.returncode, 0, g.stdout + g.stderr)
        self.assertEqual(git(live, "reflog", "show", "--format=%H", "refs/stash").split(), stash)
        self.assertEqual(git(live, "cat-file", "-t", y), "commit")
        self.assertIn(y, git(live, "reflog", "show", "--format=%H", "refs/heads/b-work").split())
        o = run("overlap", live, self.s.old)
        self.assertEqual(o.returncode, 0, o.stdout + o.stderr)

    def test_commit_landing_on_a_planned_branch_before_removal_fails_leased(self):   # G1-04 (L38)
        c1, state = self.s.c[1], {}

        def before(repo, args, kw):
            if args[:2] == ("update-ref", "--stdin") and "delete refs/heads/mv-br" in (kw.get("stdin") or "") \
                    and not state:
                n = git(self.live, "commit-tree", c1 + "^{tree}", "-p", c1, "-m", "concurrent work")
                git(self.live, "update-ref", "refs/heads/mv-br", n, c1)
                state["new"] = n

        rc, stdout, _ = self.archive_inproc(before=before)
        self.assertTrue(state, "seam did not fire")
        self.assertEqual(rc, 1, stdout)
        self.assertIn("REF REMOVAL FAILED", stdout)
        self.assertEqual(refs(self.live).get("refs/heads/mv-br"), state["new"])
        run("gc", self.live, self.s.old, "--prune-floor", "now")
        self.assertEqual(git(self.live, "cat-file", "-t", state["new"]), "commit")

    def test_worktree_local_refs_and_head_reflog_are_bundled(self):              # G1-10 (pwt)
        wb, wd = self.wt["wb"], self.wt["wd"]
        keep = git(wb, "commit-tree", self.s.c[0] + "^{tree}", "-m", "saved on a per-worktree ref")
        git(wb, "update-ref", "refs/worktree/keep", keep)
        orig = git(wb, "commit-tree", self.s.c[0] + "^{tree}", "-m", "only in ORIG_HEAD")
        git(wb, "update-ref", "ORIG_HEAD", orig)
        git(wd, "commit", "-q", "--allow-empty", "-m", "visited then left")
        visited = git(wd, "rev-parse", "HEAD")
        git(wd, "checkout", "-q", "--detach", self.s.c[1])                     # HEAD back where the plan saw it
        arch = os.path.join(self.t, "arch")
        r = run("archive", self.live, self.plan, arch, "--include-locked")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse([n for n in refs(self.live) if n.startswith("refs/purge-archive/")])
        restore = os.path.join(self.t, "restore")
        subprocess.run(["git", "init", "-q", restore], check=True, env=ENV)
        git(restore, "fetch", "-q", os.path.join(arch, "refs.bundle"), "refs/*:refs/*")
        got = set(refs(restore).values())
        for sha in (keep, orig, visited):
            self.assertIn(sha, got)
            self.assertEqual(git(restore, "cat-file", "-t", sha), "commit")
        manifest = read(os.path.join(arch, "manifest.tsv")).decode()
        self.assertIn("refs/worktree/keep", manifest)
        self.assertIn("ORIG_HEAD", manifest)

    def test_stash_changed_after_plan_is_skipped_rest_archived(self):            # G1-16 L22
        write(os.path.join(self.wt["wb"], "f.txt"), "old stash\n")
        git(self.wt["wb"], "stash", "-q")
        out = os.path.join(self.t, "plan-stash.json")
        run("plan", self.live, self.s.old, "--out", out, "--include-locked")
        self.assertTrue(json.load(open(out, encoding="utf-8"))["stash"])
        write(os.path.join(self.live, "README.md"), "new stash\n")
        git(self.live, "stash", "-q")
        stash = git(self.live, "reflog", "show", "--format=%H", "refs/stash").split()
        arch = os.path.join(self.t, "arch")
        r = run("archive", self.live, out, arch, "--include-locked")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("stash changed since the plan", r.stdout)
        self.assertNotIn("REF REMOVAL FAILED", r.stdout)
        self.assertEqual(git(self.live, "reflog", "show", "--format=%H", "refs/stash").split(), stash)
        self.assertNotIn("refs/heads/wb-br", refs(self.live))
        self.assertNotIn("\nstash\t", "\n" + read(os.path.join(arch, "manifest.tsv")).decode())

    def test_main_head_moved_after_plan_refuses(self):                           # G1-16 L23
        git(self.live, "commit", "-q", "--allow-empty", "-m", "main moved")
        before = refs(self.live)
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("main worktree HEAD moved", r.stdout)
        self.assertEqual(refs(self.live), before)
        self.assertTrue(all(os.path.isdir(p) for p in self.wt.values()))

    def test_planned_branch_now_checked_out_in_main_is_skipped(self):           # G1-16 L26
        head = git(self.live, "rev-parse", "HEAD")
        git(self.live, "update-ref", "refs/heads/mv-br", head)
        git(self.live, "symbolic-ref", "HEAD", "refs/heads/mv-br")             # main HEAD (sha) unchanged
        r = run("archive", self.live, self.plan, os.path.join(self.t, "arch"), "--include-locked")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("SKIP refs/heads/mv-br: checked out in the main worktree", r.stdout)
        self.assertEqual(refs(self.live).get("refs/heads/mv-br"), head)

    def test_bundle_verify_failure_aborts_with_nothing_moved(self):              # G1-16 L29
        def replace(real, repo, args, kw):
            return fake_result(1) if args[:2] == ("bundle", "verify") else None

        rc, stdout, _ = self.archive_inproc(replace=replace)
        self.assertEqual(rc, 2, stdout)
        self.assertIn("bundle verify failed", stdout)
        self.assertEqual(refs(self.live), self.before)
        self.assertTrue(all(os.path.isdir(p) for p in self.wt.values()))
        self.assertEqual(len(wt_paths(self.live)), 5)

    def test_worktree_still_registered_after_prune_is_reported(self):           # G1-16 L37
        def replace(real, repo, args, kw):
            return fake_result(0) if args[:2] == ("worktree", "prune") else None

        rc, stdout, _ = self.archive_inproc(replace=replace)
        self.assertEqual(rc, 1, stdout)
        self.assertRegex(stdout, r"SKIP .*wd: still registered after prune")

    def test_relative_paths_are_resolved_against_the_working_directory(self):   # G1-18
        r = run("archive", "live", "plan.json", "arch-rel", "--include-locked", cwd=self.t)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isfile(os.path.join(self.t, "arch-rel", "refs.bundle")))
        self.assertFalse(os.path.exists(os.path.join(self.live, "arch-rel")))


class ChangedTagOnlyTest(unittest.TestCase):
    def test_changed_includes_a_commit_reachable_only_from_a_tag(self):         # G1-05 (L04)
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as t:
            src = os.path.join(t, "src")
            subprocess.run(["git", "init", "-q", "-b", "main", src], check=True, env=ENV)
            write(os.path.join(src, "r.md"), "r\n")
            git(src, "add", "-A")
            git(src, "commit", "-q", "-m", "c0")
            git(src, "checkout", "-q", "--detach")
            write(os.path.join(src, "rel.txt"), "secret in release\n")
            git(src, "add", "-A")
            git(src, "commit", "-q", "-m", "release")
            rel = git(src, "rev-parse", "HEAD")
            git(src, "tag", "-a", "v1", "-m", "release")
            git(src, "checkout", "-q", "main")
            backup, purged = os.path.join(t, "backup.git"), os.path.join(t, "purged.git")
            subprocess.run(["git", "clone", "-q", "--mirror", src, backup], check=True, env=ENV)
            subprocess.run(["git", "clone", "-q", "--mirror", "--no-local", backup, purged], check=True, env=ENV)
            write(os.path.join(t, "rules.txt"), "secret==>[private]\n")
            git(purged, "filter-repo", "--force", "--replace-text", os.path.join(t, "rules.txt"))
            out = os.path.join(t, "old.txt")
            r = run("changed", purged, backup, "--out", out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn(rel, read(out).decode().split())


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


if __name__ == "__main__":
    unittest.main()
