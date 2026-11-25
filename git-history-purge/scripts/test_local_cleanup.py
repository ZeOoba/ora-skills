"""Tests for local_cleanup.py (stdlib unittest; gated by tools/run_skill_suites.sh).

Real git in temp dirs. The purge is a real `git filter-repo --replace-text` run on a mirror clone
of the backup (SKILL.md Step 3). The FIRST commit holds nothing private, so the purge keeps its SHA
and new branches share it: such branches must NOT count as old history.

v2.2 (round-4 redesign): Step 6 deletes nothing. `inventory` records the checkout and refuses what it
cannot carry across; `rehome` moves the whole checkout (every worktree) into the archive with renames,
re-clones the purged remote in its place and brings kept work across from the archived copy. The
"remote" of every rehome here is the purged bare mirror. Failures are injected through seams
(os.rename, git(), device_of, wait_quiet) instead of racing real processes.
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "local_cleanup.py")
ENV = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="t",
           GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com",
           GIT_ALLOW_PROTOCOL="file")
Q = ("--exclusive", "--quiet-seconds", "0")


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false", "-c", "protocol.file.allow=always"]
                          + list(args), capture_output=True, encoding="utf-8", errors="surrogateescape",
                          check=check, env=ENV).stdout.strip()


def run(*args, cwd=None):
    return subprocess.run([sys.executable, "-I", SCRIPT] + list(args), capture_output=True, encoding="utf-8",
                          errors="replace", env=ENV, cwd=cwd)


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode())


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def refs(repo):
    out = git(repo, "for-each-ref", "--format=%(objectname) %(refname)")
    return dict(reversed(l.split(" ", 1)) for l in out.splitlines() if l)


def norm(p):
    return os.path.normcase(os.path.normpath(p))


def wt_list(repo):
    """[{path, head, branch, detached, locked, prunable}] from `git worktree list --porcelain`."""
    rows = []
    for line in git(repo, "worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            rows.append({"path": norm(line[9:]), "locked": None, "detached": False, "prunable": False,
                         "branch": None, "head": None})
        elif line.startswith("HEAD "):
            rows[-1]["head"] = line[5:]
        elif line.startswith("branch "):
            rows[-1]["branch"] = line[7:]
        elif line == "detached":
            rows[-1]["detached"] = True
        elif line.startswith("locked"):
            rows[-1]["locked"] = line[7:]
        elif line.startswith("prunable"):
            rows[-1]["prunable"] = True
    return rows


def wt_paths(repo):
    return sorted(w["path"] for w in wt_list(repo))


def reflog(repo, name):
    return git(repo, "reflog", "show", "--format=%H", name, "--").split()


def exists(repo, sha):
    return subprocess.run(["git", "-C", repo, "cat-file", "-e", sha], env=ENV,
                          capture_output=True).returncode == 0


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
        self.lib = os.path.join(root, "lib")                      # a submodule's upstream
        subprocess.run(["git", "init", "-q", "-b", "main", self.lib], check=True, env=ENV)
        write(os.path.join(self.lib, "l.txt"), "lib\n")
        git(self.lib, "add", "-A")
        git(self.lib, "commit", "-q", "-m", "lib")

    def live(self, path):
        """A clone of src, main re-pointed onto the purged main (so the main checkout is kept history)."""
        subprocess.run(["git", "clone", "-q", self.src, path], check=True, env=ENV)
        git(path, "fetch", "-q", self.purged, "refs/heads/main:refs/heads/newmain")
        git(path, "checkout", "-q", "-B", "main", "newmain")
        return path


S = None
TMP = None


def setUpModule():
    global S, TMP
    TMP = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    S = Source(TMP.name)


def tearDownModule():
    TMP.cleanup()


def fresh(name):
    d = os.path.join(TMP.name, name)
    os.makedirs(d)
    return d


def commit_on(repo, parent, msg):
    """A new commit with parent's tree (new history when parent is new history)."""
    return git(repo, "commit-tree", parent + "^{tree}", "-p", parent, "-m", msg)


def add_submodule(wt, name="sub"):
    """Add S.lib as submodule <name> in worktree wt and commit; return the submodule's folder."""
    git(wt, "submodule", "add", "-q", S.lib, name)
    git(wt, "commit", "-q", "-m", "add " + name)
    return os.path.join(wt, name)


def unpushed_submodule_commit(sub):
    """A commit on a new branch in the submodule, then back to the recorded commit (superproject stays clean)."""
    rec = git(sub, "rev-parse", "HEAD")
    git(sub, "switch", "-q", "-c", "wip")
    write(os.path.join(sub, "w.txt"), "unpushed lib work\n")
    git(sub, "add", "w.txt")
    git(sub, "commit", "-q", "-m", "unpushed lib work")
    sha = git(sub, "rev-parse", "HEAD")
    git(sub, "switch", "-q", "--detach", rec)
    return sha


def inventory(live, out, old=None):
    r = run("inventory", live, old or S.old, "--out", out)
    data = None
    if os.path.isfile(out):
        with open(out, encoding="utf-8") as fh:
            data = json.load(fh)
    return r, data


def load_module():
    spec = importlib.util.spec_from_file_location("local_cleanup", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def inproc(argv, replace=None, setup=None):
    """Run local_cleanup.main in-process. replace(real, repo, args, kw) may return a result instead of calling
    git; setup(mod) may patch module functions first. Returns (rc, stdout)."""
    mod = load_module()
    real = mod.git

    def fake(repo, *args, **kw):
        if replace:
            r = replace(real, repo, args, kw)
            if r is not None:
                return r
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
    return rc, buf.getvalue()


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


def find_archived(arch, marker):
    """The archived worktree folder under <arch>/worktrees whose name ends with marker."""
    base = os.path.join(arch, "worktrees")
    hits = [os.path.join(base, n) for n in os.listdir(base) if n.endswith(marker)]
    assert len(hits) == 1, (marker, os.listdir(base))
    return hits[0]


# ==================================================================== changed / overlap (unchanged)

class ChangedTest(unittest.TestCase):
    def test_changed_excludes_unchanged_root_and_includes_changed(self):
        old = read(S.old).decode().split()
        self.assertEqual(old, sorted(old))
        self.assertNotIn(S.c[0], old)
        for sha in S.c[1:]:
            self.assertIn(sha, old)

    def test_changed_writes_dropped_blobs_and_trees(self):                      # G1-15
        listed = set(read(S.old + ".objects").decode().split())
        self.assertIn(git(S.src, "rev-parse", S.c[1] + ":f.txt"), listed)
        self.assertIn(git(S.src, "rev-parse", S.c[1] + "^{tree}"), listed)
        self.assertNotIn(git(S.src, "rev-parse", S.c[0] + ":README.md"), listed)   # unchanged blob
        self.assertFalse(listed & set(S.c))                                          # commits: own file

    def test_changed_refuses_empty_set_and_bad_path(self):
        d = fresh("changed-refuse")
        out = os.path.join(d, "empty.txt")
        self.assertEqual(run("changed", S.purged, S.purged, "--out", out).returncode, 1)
        self.assertEqual(run("changed", S.purged, os.path.join(d, "nope"), "--out", out).returncode, 2)

    def test_overlap_counts_a_dropped_blob(self):                                # G1-15
        bare = os.path.join(fresh("blob-only"), "b.git")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True, env=ENV)
        subprocess.run(["git", "-C", bare, "hash-object", "-w", "--stdin"], input=b"secret v1\n", check=True,
                       env=ENV, capture_output=True)
        r = run("overlap", bare, S.old)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertEqual(run("overlap", S.purged, S.old).returncode, 0)


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
    def test_annotated_tag_with_a_rewritten_message_on_a_kept_commit_is_old(self):   # L06b
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
            _r, inv = inventory(live, os.path.join(t, "inv.json"), old)
            self.assertTrue({x["name"]: x["old"] for x in inv["refs"]}["refs/tags/v0"])


# ==================================================================== inventory: classification

class InventoryClassifyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = cls.d = fresh("classify")
        c, nm = S.c, S.new_main
        live = cls.live = S.live(os.path.join(d, "live"))
        git(live, "branch", "shares-root", commit_on(live, c[0], "x"))            # unchanged root: NOT old
        empty = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"                          # the empty tree
        git(live, "update-ref", "refs/heads/heartbeat", git(live, "commit-tree", empty, "-m", "hb"))  # orphan
        m = git(live, "commit-tree", nm + "^{tree}", "-p", nm, "-p", c[1], "-m", "merge")
        git(live, "update-ref", "refs/heads/merged-old", m)                         # old via 2nd parent
        git(live, "tag", "lt-old", c[1])
        git(live, "tag", "-a", "at-old", c[2], "-m", "old release")
        git(live, "tag", "-a", "at-new", nm, "-m", "new release")
        git(live, "tag", "-a", "blobtag", "-m", "saved file", c[1] + ":f.txt")      # tag-only dropped blob
        git(live, "tag", "treetag", git(live, "rev-parse", c[1] + "^{tree}"))
        git(live, "tag", "oktag", git(live, "rev-parse", c[0] + ":README.md"))
        git(live, "update-ref", "refs/custom/x", c[1])
        git(live, "update-ref", "refs/original/refs/heads/main", c[3])
        git(live, "branch", "--track", "old-feature", "origin/old-feature")
        git(live, "notes", "add", "-m", "note", nm)                                 # kept notes
        git(live, "notes", "--ref", "oldnotes", "add", "-m", "n", c[1])
        oldnotes = git(live, "rev-parse", "refs/notes/oldnotes")                    # notes commit with an old parent
        git(live, "update-ref", "refs/notes/oldnotes",
            git(live, "commit-tree", oldnotes + "^{tree}", "-p", oldnotes, "-p", c[1], "-m", "n2"))
        # a second backup: an orphan commit pushed after the first backup holds the secret
        late_src = os.path.join(d, "late-src")
        subprocess.run(["git", "clone", "-q", S.src, late_src], check=True, env=ENV)
        git(late_src, "checkout", "-q", "--orphan", "late")
        write(os.path.join(late_src, "late.txt"), "secret pushed late\n")
        git(late_src, "add", "late.txt")
        git(late_src, "commit", "-q", "-m", "late push")
        cls.late = git(late_src, "rev-parse", "HEAD")
        backup2 = os.path.join(d, "backup2.git")
        subprocess.run(["git", "clone", "-q", "--mirror", late_src, backup2], check=True, env=ENV)
        cls.old2 = os.path.join(d, "old2.txt")
        cls.changed2 = run("changed", S.purged, S.backup, backup2, "--out", cls.old2)
        git(live, "fetch", "-q", late_src, "refs/heads/late:refs/heads/late")
        # stash: kept (main), old (old worktree), kept (main); per-worktree refs
        write(os.path.join(live, "README.md"), "s1\n")
        git(live, "stash", "-q")
        ow = cls.ow = os.path.join(d, "ow")
        git(live, "worktree", "add", "-q", "-b", "ow-br", ow, c[2])
        write(os.path.join(ow, "f.txt"), "old stash\n")
        git(ow, "stash", "-q")
        write(os.path.join(live, "README.md"), "s2\n")
        git(live, "stash", "-q")
        cls.stash = reflog(live, "refs/stash")
        kw = cls.kw = os.path.join(d, "kw")
        git(live, "worktree", "add", "-q", "--detach", kw, nm)
        git(kw, "update-ref", "refs/worktree/keep", nm)
        git(kw, "update-ref", "refs/bisect/bad", c[1])
        cls.r1, cls.inv1 = inventory(live, os.path.join(d, "inv1.json"))
        cls.r2, cls.inv2 = inventory(live, os.path.join(d, "inv2.json"), cls.old2)

    def old_flags(self, inv):
        return {(x["name"], x.get("worktree")): x["old"] for x in inv["refs"]}

    def test_inventory_exit_0(self):
        self.assertEqual(self.r1.returncode, 0, self.r1.stdout + self.r1.stderr)

    def test_old_and_kept_refs_in_every_namespace(self):
        flags = {n: o for (n, w), o in self.old_flags(self.inv1).items() if w is None}
        for name in ("refs/heads/old-feature", "refs/heads/merged-old", "refs/heads/ow-br",
                     "refs/remotes/origin/main", "refs/tags/lt-old", "refs/tags/at-old", "refs/custom/x",
                     "refs/original/refs/heads/main", "refs/notes/oldnotes"):
            self.assertTrue(flags[name], name)
        for name in ("refs/heads/main", "refs/heads/newmain", "refs/heads/shares-root", "refs/heads/heartbeat",
                     "refs/tags/at-new", "refs/tags/oktag", "refs/notes/commits", "refs/heads/late"):
            self.assertFalse(flags[name], name)

    def test_tag_only_blob_and_tree_are_old(self):                              # G1-15
        flags = self.old_flags(self.inv1)
        self.assertTrue(flags[("refs/tags/blobtag", None)])
        self.assertTrue(flags[("refs/tags/treetag", None)])

    def test_second_backup_makes_its_commit_old(self):                          # union of backups
        self.assertEqual(self.changed2.returncode, 0, self.changed2.stdout + self.changed2.stderr)
        self.assertIn(self.late, read(self.old2).decode().split())
        self.assertTrue(self.old_flags(self.inv2)[("refs/heads/late", None)])

    def test_stash_entries_classified_each(self):
        self.assertEqual([e["sha"] for e in self.inv1["stash"]], self.stash)
        self.assertEqual([e["old"] for e in self.inv1["stash"]], [False, True, False])
        self.assertNotIn("refs/stash", {x["name"] for x in self.inv1["refs"]})

    def test_worktree_local_refs_recorded_per_worktree(self):
        kw_id = [w["id"] for w in self.inv1["worktrees"] if norm(w["path"]) == norm(self.kw)][0]
        flags = self.old_flags(self.inv1)
        self.assertFalse(flags[("refs/worktree/keep", kw_id)])
        self.assertTrue(flags[("refs/bisect/bad", kw_id)])

    def test_worktrees_classified(self):
        old = {norm(w["path"]): w["old"] for w in self.inv1["worktrees"]}
        self.assertEqual(old, {norm(self.live): False, norm(self.ow): True, norm(self.kw): False})

    def test_snapshot_recorded(self):
        snap = self.inv1["snapshot"]
        self.assertIn("ref|refs/heads/main", snap)
        self.assertTrue(any(k.startswith("wt|.|reflog|") for k in snap))

    def test_table_printed(self):
        out = self.r1.stdout
        self.assertIn("OLD", out)
        self.assertIn("KEPT", out)
        self.assertIn("refs/heads/old-feature", out)


# ==================================================================== inventory: refusals

class InventoryRefusalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = fresh("refuse")
        c, nm = S.c, S.new_main
        live = cls.live = S.live(os.path.join(d, "live"))
        cls.wt = {}

        def add(name, start, *flags):
            path = cls.wt[name] = os.path.join(d, name)
            git(live, "worktree", "add", "-q", *flags, path, start)
            return path

        write(os.path.join(add("k-mod", nm, "--detach"), "README.md"), "edited\n")
        write(os.path.join(add("k-untr", nm, "--detach"), "notes ü.txt"), "untracked\n")
        st = add("k-staged", nm, "--detach")
        write(os.path.join(st, "README.md"), "staged version\n")
        git(st, "add", "README.md")
        write(os.path.join(st, "README.md"), "work tree version\n")
        bi = add("k-busy", nm, "--detach")
        git(bi, "bisect", "start")
        sm = add("k-sub", nm, "-b", "k-sub-br")
        cls.sub_commit = unpushed_submodule_commit(add_submodule(sm))
        od = add("o-dirty", c[2], "-b", "o-dirty-br")
        write(os.path.join(od, "f.txt"), "dirty old\n")
        write(os.path.join(od, "u.txt"), "untracked old\n")
        ob = add("o-busy", c[2], "-b", "o-busy-br")
        git(ob, "bisect", "start")
        gone = add("k-gone", nm, "--detach")
        os.rename(gone, gone + "-moved")
        cls.r, cls.inv = inventory(live, os.path.join(d, "inv.json"))
        cls.problems = {}
        for x in cls.inv["refusals"]:
            cls.problems.setdefault(norm(x["path"]), []).append(x["problem"])

    def assert_refused(self, name, word):
        self.assertEqual(self.r.returncode, 2, self.r.stdout + self.r.stderr)
        found = self.problems.get(norm(self.wt[name]), [])
        self.assertTrue(any(word in p for p in found), (name, found))
        self.assertIn(self.wt[name], self.r.stdout)

    def test_kept_dirty_worktree_refused(self):
        self.assert_refused("k-mod", "modified")

    def test_kept_untracked_files_refused(self):
        self.assert_refused("k-untr", "untracked")

    def test_kept_staged_only_content_refused(self):
        self.assert_refused("k-staged", "staged-only")

    def test_kept_operation_in_progress_refused(self):
        self.assert_refused("k-busy", "in progress")

    def test_kept_submodule_with_unpushed_commit_refused(self):
        self.assert_refused("k-sub", "unpushed")

    def test_operation_in_progress_in_an_old_worktree_refused(self):           # the rehome gate would refuse it
        self.assert_refused("o-busy", "in progress")

    def test_missing_worktree_folder_refused(self):
        self.assert_refused("k-gone", "missing")

    def test_dirty_old_worktree_allowed(self):
        self.assertNotIn(norm(self.wt["o-dirty"]), self.problems)

    def test_each_refusal_names_what_to_do(self):
        self.assertTrue(all(x["fix"] for x in self.inv["refusals"]))
        self.assertIn("REFUSED", self.r.stdout)

    def test_rehome_refuses_an_inventory_with_refusals(self):
        arch = os.path.join(TMP.name, "refuse", "arch")
        r = run("rehome", self.live, os.path.join(TMP.name, "refuse", "inv.json"), arch, S.purged, *Q)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertFalse(os.path.exists(arch))


# ==================================================================== rehome: happy path

class RehomeHappyTest(unittest.TestCase):
    """Main checkout (kept) with a worktree inside it, kept worktrees outside (one locked, one detached),
    an old dirty worktree, kept and old stash entries, a kept unpushed branch, kept tags and notes.
    Non-ASCII and space-containing paths and branch names throughout."""

    @classmethod
    def setUpClass(cls):
        d = cls.d = fresh("happy ü")
        c, nm = S.c, S.new_main
        live = cls.live = S.live(os.path.join(d, "live ü x"))
        git(live, "config", "remote.origin.pushurl", "DISABLED-history-purge-x")
        git(live, "config", "core.hooksPath", "my hooks")
        write(os.path.join(live, ".git", "hooks", "pre-push"), "#!/bin/sh\nexit 1\n")
        kept = cls.kept = commit_on(live, nm, "kept work")
        git(live, "update-ref", "refs/heads/kept/ü-1", kept)
        git(live, "checkout", "-q", "kept/ü-1")
        git(live, "update-ref", "refs/heads/main", commit_on(live, nm, "local main work"))   # ahead of origin
        git(live, "update-ref", "refs/remotes/other/x", nm)                 # kept, but remote-tracking
        git(live, "tag", "old-tag", c[1])
        git(live, "tag", "-a", "kept-tag", kept, "-m", "kept release")
        git(live, "tag", "lt-kept", kept)
        git(live, "notes", "add", "-m", "note", nm)
        write(os.path.join(live, "README.md"), "s1\n")
        git(live, "stash", "-q")
        ow = cls.ow = os.path.join(d, "wts", "old wt")
        git(live, "worktree", "add", "-q", "-b", "old-wt", ow, c[2])
        write(os.path.join(ow, "f.txt"), "old stash\n")
        git(ow, "stash", "-q")
        write(os.path.join(live, "README.md"), "s2\n")
        git(live, "stash", "-q")
        write(os.path.join(ow, "f.txt"), "dirty old\n")
        write(os.path.join(ow, "new ü.txt"), "untracked old\n")
        cls.inside = os.path.join(live, ".wt", "inside")
        git(live, "worktree", "add", "-q", "-b", "in-br", cls.inside, nm)
        out = cls.out = os.path.join(d, "wts", "out ü")
        git(live, "worktree", "add", "-q", "-b", "out-br", out, kept)
        git(live, "worktree", "lock", "--reason", "busy reason", out)
        git(live, "config", "branch.out-br.remote", "origin")
        git(live, "config", "branch.out-br.merge", "refs/heads/out-br")
        git(out, "update-ref", "refs/worktree/keep", nm)
        det = cls.det = os.path.join(d, "wts", "det")
        git(live, "worktree", "add", "-q", "--detach", det, nm)              # not the main checkout's HEAD
        cls.refs_before = refs(live)
        cls.stash_before = reflog(live, "refs/stash")
        cls.stash_msgs = git(live, "log", "-g", "--format=%gs", "refs/stash", "--").splitlines()
        cls.overlap_before = run("overlap", live, S.old)
        cls.inv_path = os.path.join(d, "inv.json")
        cls.inv_run, cls.inv = inventory(live, cls.inv_path)
        cls.arch = os.path.join(d, "arch ü")
        cls.rh = run("rehome", live, cls.inv_path, cls.arch, S.purged, *Q)
        cls.overlap_after = run("overlap", live, S.old)
        cls.archived_repo = os.path.join(cls.arch, "repo")

    CARRIED = ("refs/heads/main", "refs/heads/newmain", "refs/heads/kept/ü-1", "refs/heads/in-br",
               "refs/heads/out-br", "refs/tags/kept-tag", "refs/tags/lt-kept", "refs/notes/commits")

    def assert_new_clone(self):
        """live is now a clone of the purged remote and the old checkout is in the archive."""
        self.assertEqual(git(self.live, "rev-parse", "refs/remotes/origin/main"), S.new_main)
        self.assertTrue(os.path.isdir(os.path.join(self.archived_repo, ".git")))

    def test_inventory_allows_this_checkout(self):
        self.assertEqual(self.inv_run.returncode, 0, self.inv_run.stdout + self.inv_run.stderr)

    def test_rehome_exit_0(self):
        self.assertEqual(self.rh.returncode, 0, self.rh.stdout + self.rh.stderr)

    def test_overlap_zero_on_the_new_clone(self):
        self.assertEqual(self.overlap_before.returncode, 1)
        self.assertEqual(self.overlap_after.returncode, 0, self.overlap_after.stdout)

    def test_new_clone_is_a_clone_of_the_purged_remote(self):
        self.assertEqual(git(self.live, "rev-parse", "refs/remotes/origin/main"), S.new_main)
        self.assertEqual(refs(self.live)["refs/remotes/origin/old-feature"],
                         git(S.purged, "rev-parse", "refs/heads/old-feature"))

    def test_kept_refs_carried_at_the_same_sha(self):
        self.assert_new_clone()
        now = refs(self.live)
        for name in self.CARRIED:
            self.assertEqual(now.get(name), self.refs_before[name], name)

    def test_no_other_refs_come_across(self):
        local = {k for k in refs(self.live) if not k.startswith("refs/remotes/")}
        self.assertEqual(local, set(self.CARRIED) | {"refs/stash"})
        self.assertNotIn("refs/remotes/other/x", refs(self.live))

    def test_kept_stash_entries_in_order_old_entry_not_carried(self):
        kept2, _old, kept1 = self.stash_before
        self.assertEqual(reflog(self.live, "refs/stash"), [kept2, kept1])
        msgs = git(self.live, "log", "-g", "--format=%gs", "refs/stash", "--").splitlines()
        self.assertEqual(msgs, [self.stash_msgs[0], self.stash_msgs[2]])

    def test_main_checkout_on_its_branch_and_clean(self):
        self.assert_new_clone()
        self.assertEqual(git(self.live, "symbolic-ref", "HEAD"), "refs/heads/kept/ü-1")
        self.assertEqual(git(self.live, "status", "--porcelain", "--untracked-files=no"), "")

    def test_kept_worktrees_recreated_at_their_paths(self):
        rows = {w["path"]: w for w in wt_list(self.live)}
        self.assertEqual(set(rows), {norm(self.live), norm(self.inside), norm(self.out), norm(self.det)})
        self.assertEqual(rows[norm(self.inside)]["branch"], "refs/heads/in-br")
        self.assertEqual(rows[norm(self.out)]["branch"], "refs/heads/out-br")
        self.assertTrue(rows[norm(self.det)]["detached"])
        self.assertEqual(rows[norm(self.det)]["head"], S.new_main)
        for p in (self.inside, self.out, self.det):
            self.assertEqual(git(p, "status", "--porcelain"), "", p)

    def test_locked_worktree_relocked_with_its_reason(self):
        self.assert_new_clone()
        rows = {w["path"]: w for w in wt_list(self.live)}
        self.assertEqual(rows[norm(self.out)]["locked"], "busy reason")
        self.assertIsNone(rows[norm(self.det)]["locked"])

    def test_worktree_local_ref_carried(self):
        self.assert_new_clone()
        self.assertEqual(git(self.out, "rev-parse", "refs/worktree/keep"), S.new_main)

    def test_branch_upstream_config_carried(self):
        self.assert_new_clone()
        self.assertEqual(git(self.live, "config", "branch.out-br.merge"), "refs/heads/out-br")

    def test_old_branch_and_worktree_only_in_the_archive(self):
        self.assertNotIn("refs/heads/old-wt", refs(self.live))
        self.assertFalse(os.path.exists(self.ow))
        moved = find_archived(self.arch, "old wt")
        self.assertEqual(read(os.path.join(moved, "f.txt")), b"dirty old\n")
        self.assertEqual(read(os.path.join(moved, "new ü.txt")), b"untracked old\n")
        self.assertEqual(git(moved, "rev-parse", "HEAD"), S.c[2])

    def test_archived_repo_opens_with_every_ref_and_the_old_log(self):
        self.assertEqual(refs(self.archived_repo), self.refs_before)
        self.assertEqual(reflog(self.archived_repo, "refs/stash"), self.stash_before)
        self.assertIn(S.c[1], git(self.archived_repo, "log", "--format=%H", "old-wt").split())
        rows = wt_list(self.archived_repo)
        self.assertEqual(len(rows), 5)
        for w in rows:
            self.assertTrue(w["path"].startswith(norm(self.arch) + os.sep), w["path"])
            self.assertFalse(w["prunable"], w["path"])

    def test_remotes_and_hooks_path_restored_hooks_not_copied(self):
        self.assertEqual(norm(git(self.live, "config", "remote.origin.url")), norm(S.src))
        self.assertEqual(git(self.live, "config", "remote.origin.pushurl"), "DISABLED-history-purge-x")
        self.assertEqual(git(self.live, "config", "core.hooksPath"), "my hooks")
        self.assertFalse(os.path.exists(os.path.join(self.live, ".git", "hooks", "pre-push")))
        self.assertTrue(os.path.isfile(os.path.join(self.archived_repo, ".git", "hooks", "pre-push")))
        self.assertIn("hook installer", self.rh.stdout)

    def test_rehome_md_says_what_moved_and_how_to_restore(self):
        text = read(os.path.join(self.arch, "REHOME.md")).decode("utf-8")
        self.assertIn(self.live, text)
        self.assertIn(self.ow, text)
        self.assertIn("worktree repair", text)
        self.assertIn("refs/heads/kept/ü-1", text)
        self.assertIn("Result: verified", text)

    def test_rehome_md_names_where_each_folder_now_is(self):                    # R4-09 (T24)
        text = read(os.path.join(self.arch, "REHOME.md")).decode("utf-8")
        self.assertIn("- OLD %s -> %s" % (self.ow, find_archived(self.arch, "old wt")), text)
        self.assertIn("- KEPT %s -> %s" % (self.out, find_archived(self.arch, "out ü")), text)
        self.assertIn("- KEPT %s -> %s" % (self.live, self.archived_repo), text)

    def test_rehome_md_lists_kept_stash_entries_and_worktrees(self):            # R4-09 (T26, T27)
        lines = read(os.path.join(self.arch, "REHOME.md")).decode("utf-8").splitlines()
        kept2, old, kept1 = self.stash_before
        self.assertIn("- stash entry %s" % kept1, lines)
        self.assertIn("- stash entry %s" % kept2, lines)
        self.assertNotIn("- stash entry %s" % old, lines)
        for p in (self.inside, self.out, self.det):
            self.assertIn("- worktree %s" % p, lines)
        self.assertNotIn("- worktree %s" % self.ow, lines)

    def test_restore_command_named_in_rehome_md(self):                          # R4-06
        text = read(os.path.join(self.arch, "REHOME.md")).decode("utf-8")
        self.assertIn("local_cleanup.py restore", text)
        self.assertIn("core.worktree", text)

    def test_relative_paths_resolved_against_the_working_directory(self):     # G1-18
        d = fresh("relative")
        live = S.live(os.path.join(d, "live"))
        r, _inv = inventory(live, os.path.join(d, "inv.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        r = run("rehome", "live", "inv.json", "arch", S.purged, *Q, cwd=d)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertTrue(os.path.isdir(os.path.join(d, "arch", "repo", ".git")))


# ==================================================================== rehome: round-3 data-loss cases

class RehomeKeepsEverythingTest(unittest.TestCase):
    """Data that in-place cleanup lost in rounds 1-3 is still readable in the archive after rehome."""

    @classmethod
    def setUpClass(cls):
        d = fresh("keeps")
        c, nm = S.c, S.new_main
        live = cls.live = S.live(os.path.join(d, "live"))
        sm = os.path.join(d, "wts", "sm")                                   # R3-02: old worktree, submodule
        git(live, "worktree", "add", "-q", "-b", "sm-br", sm, c[2])
        cls.sub_commit = unpushed_submodule_commit(add_submodule(sm))
        write(os.path.join(live, "README.md"), "kept stash\n")              # R3-01: stash entries
        git(live, "stash", "-q")
        write(os.path.join(sm, "f.txt"), "another session's stash\n")
        git(sm, "stash", "-q")
        cls.stash_before = reflog(live, "refs/stash")
        write(os.path.join(live, "README.md"), "to drop\n")                 # R3-03: a dropped stash
        git(live, "stash", "-q")
        cls.dropped = git(live, "rev-parse", "refs/stash")
        git(live, "stash", "drop", "-q")
        r = cls.reflog_only = commit_on(live, nm, "reflog only")            # a reflog-only commit
        git(live, "update-ref", "-m", "away", "refs/heads/main", r)
        git(live, "update-ref", "-m", "back", "refs/heads/main", nm)
        write(os.path.join(live, "local.txt"), "local main work\n")
        git(live, "add", "local.txt")
        git(live, "commit", "-q", "-m", "local main work")
        bw = os.path.join(d, "wts", "bw")                                    # refs/bisect, refs/worktree
        git(live, "worktree", "add", "-q", "--detach", bw, c[1])
        git(bw, "update-ref", "refs/bisect/bad", c[1])
        git(bw, "update-ref", "refs/worktree/x", c[2])
        cls.inv_path = os.path.join(d, "inv.json")
        cls.inv_run, _ = inventory(live, cls.inv_path)
        cls.arch = os.path.join(d, "arch")
        cls.rh = run("rehome", live, cls.inv_path, cls.arch, S.purged, *Q)
        cls.repo = os.path.join(cls.arch, "repo")
        cls.sm, cls.bw = find_archived(cls.arch, "sm"), find_archived(cls.arch, "bw")

    def test_rehome_exit_0_and_overlap_zero(self):
        self.assertEqual(self.inv_run.returncode, 0, self.inv_run.stdout)
        self.assertEqual(self.rh.returncode, 0, self.rh.stdout + self.rh.stderr)
        self.assertEqual(run("overlap", self.live, S.old).returncode, 0)

    def test_main_checkout_at_its_local_commit_and_clean(self):
        self.assertEqual(read(os.path.join(self.live, "local.txt")), b"local main work\n")
        self.assertEqual(git(self.live, "status", "--porcelain"), "")

    def test_submodule_repo_under_an_admin_dir_kept(self):                       # R3-02
        sub = os.path.join(self.sm, "sub")
        self.assertTrue(exists(sub, self.sub_commit))
        self.assertEqual(git(sub, "rev-parse", "refs/heads/wip"), self.sub_commit)

    def test_other_sessions_stash_entries_kept(self):                            # R3-01
        self.assertEqual(reflog(self.repo, "refs/stash"), self.stash_before)

    def test_dropped_stash_object_kept(self):                                    # R3-03
        self.assertTrue(exists(self.repo, self.dropped))

    def test_reflog_only_commit_kept(self):
        self.assertTrue(exists(self.repo, self.reflog_only))
        self.assertIn(self.reflog_only, reflog(self.repo, "refs/heads/main"))

    def test_bisect_and_worktree_refs_kept(self):
        self.assertEqual(git(self.bw, "rev-parse", "refs/bisect/bad"), S.c[1])
        self.assertEqual(git(self.bw, "rev-parse", "refs/worktree/x"), S.c[2])


# ==================================================================== rehome: failures

class RehomeFailureTest(unittest.TestCase):
    """Per test: live (kept main) + wts/a (kept, branch a-br) + wts/b (old, dirty), inventoried."""

    n = 0

    def setUp(self):
        RehomeFailureTest.n += 1
        d = self.d = fresh("fail%d" % self.n)
        live = self.live = S.live(os.path.join(d, "live"))
        self.a, self.b = os.path.join(d, "wts", "a"), os.path.join(d, "wts", "b")
        git(live, "worktree", "add", "-q", "-b", "a-br", self.a, commit_on(live, S.new_main, "a work"))
        git(live, "worktree", "add", "-q", "-b", "b-br", self.b, S.c[2])
        self.cw = os.path.join(d, "wts", "c")                               # kept, detached
        git(live, "worktree", "add", "-q", "--detach", self.cw, S.new_main)
        write(os.path.join(self.b, "dirty.txt"), "old dirty\n")
        write(os.path.join(live, "README.md"), "kept stash\n")
        git(live, "stash", "-q")
        self.inv = os.path.join(d, "inv.json")
        r, _ = inventory(live, self.inv)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.arch = os.path.join(d, "arch")
        self.refs, self.wts = refs(live), wt_paths(live)
        self.heads = {p: git(p, "rev-parse", "HEAD") for p in (live, self.a, self.b, self.cw)}

    def rehome(self, *extra, replace=None, setup=None, argv=None):
        return inproc(argv or ["rehome", self.live, self.inv, self.arch, S.purged] + list(Q) + list(extra),
                      replace=replace, setup=setup)

    def assert_original_layout(self):
        self.assertEqual(refs(self.live), self.refs)
        self.assertEqual(wt_paths(self.live), self.wts)
        for p, h in self.heads.items():
            self.assertEqual(git(p, "rev-parse", "HEAD"), h, p)
        self.assertEqual(read(os.path.join(self.b, "dirty.txt")), b"old dirty\n")
        self.assertEqual(norm(git(self.live, "config", "remote.origin.url")), norm(S.src))   # not a new clone
        self.assertFalse(os.path.exists(os.path.join(self.arch, "repo")))
        self.assertFalse(any(w["prunable"] for w in wt_list(self.live)))

    def fail_rename_of(self, target, also=None):
        state = {"fired": False}

        def fn(real, src, dst):
            if not state["fired"] and norm(src) == norm(target):
                state["fired"] = True
                raise PermissionError(13, "held open by another process")
            if also and also(src):
                raise PermissionError(13, "held open (rollback)")
            return real(src, dst)
        return fn

    # ---- rename failures roll back to the original layout
    def test_rename_failure_first_worktree_rolls_back_exit_3(self):
        with patched_rename(self.fail_rename_of(self.a)):
            rc, out = self.rehome()
        self.assertEqual(rc, 3, out)
        self.assert_original_layout()

    def test_rename_failure_later_worktree_rolls_back_exit_3(self):
        with patched_rename(self.fail_rename_of(self.b)):
            rc, out = self.rehome()
        self.assertEqual(rc, 3, out)
        self.assert_original_layout()

    def test_rename_failure_main_checkout_rolls_back_exit_3(self):
        with patched_rename(self.fail_rename_of(self.live)):
            rc, out = self.rehome()
        self.assertEqual(rc, 3, out)
        self.assertIn("rolled back", out)
        self.assert_original_layout()

    def test_rollback_failure_exit_6_lists_where_each_folder_is(self):
        arch = norm(self.arch)
        with patched_rename(self.fail_rename_of(self.live, also=lambda src: norm(src).startswith(arch))):
            rc, out = self.rehome()
        self.assertEqual(rc, 6, out)
        self.assertIn("ROLLBACK FAILED", out)
        for name in ("a", "b"):
            now = find_archived(self.arch, name)
            self.assertIn(now, out)
            self.assertIn(os.path.join(self.d, "wts", name), out)
        self.assertTrue(os.path.isdir(self.live))

    def test_rollback_that_does_not_restore_the_inventory_state_exit_6(self):
        def fn(real, src, dst):
            if norm(src) == norm(self.live) and not os.path.exists(os.path.join(self.arch, "repo")):
                git(self.live, "branch", "written-meanwhile", S.new_main)     # another writer during the move
                raise PermissionError(13, "held open")
            return real(src, dst)
        with patched_rename(fn):
            rc, out = self.rehome()
        self.assertEqual(rc, 6, out)
        self.assertIn("differs from the inventory", out)
        self.assertIn("refs/heads/written-meanwhile", out)

    def test_repair_failure_rolls_back_exit_3(self):
        def replace(real, repo, args, kw):
            if args[:2] == ("worktree", "repair") and norm(repo).startswith(norm(self.arch)):
                return fake_result(1)
        rc, out = self.rehome(replace=replace)
        self.assertEqual(rc, 3, out)
        self.assert_original_layout()

    # ---- clone failure: the move is rolled back (documented choice)
    def test_clone_failure_rolls_back_exit_3(self):
        rc, out = self.rehome(replace=lambda real, repo, args, kw: fake_result(128) if "clone" in args else None)
        self.assertEqual(rc, 3, out)
        self.assertIn("clone failed", out)
        self.assert_original_layout()

    def test_clone_failure_leftover_is_moved_into_the_archive_not_deleted(self):
        def replace(real, repo, args, kw):
            if "clone" in args:
                write(os.path.join(args[-1], "partial.txt"), "partial clone\n")
                return fake_result(128)
        rc, out = self.rehome(replace=replace)
        self.assertEqual(rc, 3, out)
        self.assert_original_layout()
        self.assertEqual(read(os.path.join(self.arch, "failed-clone", "partial.txt")), b"partial clone\n")

    # ---- refused before any change
    def assert_refused_before_change(self, rc, out, code=2):
        self.assertEqual(rc, code, out)
        self.assert_original_layout()

    def test_archive_dir_on_another_volume_refused(self):
        arch = norm(self.arch)
        rc, out = self.rehome(setup=lambda mod: setattr(
            mod, "device_of", lambda p: 2 if norm(p).startswith(arch) else 1))
        self.assert_refused_before_change(rc, out)
        self.assertIn("volume", out)
        self.assertFalse(os.path.exists(self.arch))

    def test_existing_archive_dir_refused(self):
        os.makedirs(self.arch)
        rc, out = self.rehome()
        self.assert_refused_before_change(rc, out)
        self.assertEqual(os.listdir(self.arch), [])

    def test_archive_dir_inside_the_repo_refused(self):
        arch = os.path.join(self.live, "arch")
        rc, out = self.rehome(argv=["rehome", self.live, self.inv, arch, S.purged] + list(Q))
        self.assert_refused_before_change(rc, out)
        self.assertFalse(os.path.exists(arch))

    def test_archive_dir_inside_a_worktree_refused(self):
        arch = os.path.join(self.b, "arch")
        rc, out = self.rehome(argv=["rehome", self.live, self.inv, arch, S.purged] + list(Q))
        self.assert_refused_before_change(rc, out)
        self.assertFalse(os.path.exists(arch))

    def test_clone_url_naming_the_checkout_refused(self):
        rc, out = self.rehome(argv=["rehome", self.live, self.inv, self.arch, self.live] + list(Q))
        self.assert_refused_before_change(rc, out)
        self.assertFalse(os.path.exists(self.arch))

    def test_missing_exclusive_exit_4(self):
        rc, out = self.rehome(argv=["rehome", self.live, self.inv, self.arch, S.purged, "--quiet-seconds", "0"])
        self.assert_refused_before_change(rc, out, 4)
        self.assertIn("--exclusive", out)

    def test_snapshot_not_matching_the_inventory_exit_4(self):
        git(self.live, "branch", "late", S.new_main)
        self.refs = refs(self.live)
        rc, out = self.rehome()
        self.assert_refused_before_change(rc, out, 4)
        self.assertIn("since the inventory", out)

    def test_lock_file_exit_4(self):
        lock = os.path.join(self.live, ".git", "index.lock")
        write(lock, b"")
        try:
            rc, out = self.rehome()
        finally:
            os.remove(lock)
        self.assert_refused_before_change(rc, out, 4)
        self.assertIn("lock file", out)

    def test_change_in_the_quiet_window_exit_4(self):
        rc, out = self.rehome(setup=lambda mod: setattr(
            mod, "wait_quiet", lambda s: git(self.live, "branch", "late", S.new_main)))
        self.refs = refs(self.live)
        self.assert_refused_before_change(rc, out, 4)
        self.assertIn("quiet window", out)

    # ---- after the clone: exit 5, the archive is complete
    def test_overlap_after_the_clone_exit_5_archive_intact(self):
        blob = git(self.live, "rev-parse", S.c[1] + ":f.txt")                # old content re-added on new history
        tree = subprocess.run(["git", "-C", self.live, "mktree"], input="100644 blob %s\tf.txt\n" % blob,
                              capture_output=True, encoding="utf-8", env=ENV, check=True).stdout.strip()
        readd = git(self.live, "commit-tree", tree, "-p", S.new_main, "-m", "re-add")
        git(self.live, "update-ref", "refs/heads/readd", readd)
        r, _ = inventory(self.live, self.inv)
        self.assertEqual(r.returncode, 0, r.stdout)
        refs_before = refs(self.live)
        rc, out = self.rehome()
        self.assertEqual(rc, 5, out)
        self.assertIn(self.arch, out)
        self.assertEqual(refs(os.path.join(self.arch, "repo")), refs_before)
        self.assertTrue(os.path.isfile(os.path.join(self.arch, "REHOME.md")))

    def test_failure_bringing_work_across_exit_5_archive_intact(self):
        rc, out = self.rehome(replace=lambda real, repo, args, kw: fake_result(128) if args[:1] == ("fetch",)
                              else None)
        self.assertEqual(rc, 5, out)
        self.assertIn(self.arch, out)
        self.assertEqual(refs(os.path.join(self.arch, "repo")), self.refs)
        self.assertEqual(read(os.path.join(find_archived(self.arch, "b"), "dirty.txt")), b"old dirty\n")
        result = [l for l in read(os.path.join(self.arch, "REHOME.md")).decode("utf-8").splitlines()
                  if l.startswith("Result:")]
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].startswith("Result: FAILED"), result)            # R4-09 (T25)


    # ---- verification catches what did not come across (faults injected after the clone)
    def test_carried_ref_missing_after_the_clone_exit_5(self):
        def replace(real, repo, args, kw):
            if args[:1] == ("fetch",):
                kw = dict(kw, stdin="".join(l + "\n" for l in kw["stdin"].splitlines() if "newmain" not in l))
                return real(repo, *args, **kw)
        rc, out = self.rehome(replace=replace)
        self.assertEqual(rc, 5, out)
        self.assertIn("refs/heads/newmain", out)

    def test_stash_entry_missing_after_the_clone_exit_5(self):
        rc, out = self.rehome(replace=lambda real, repo, args, kw: fake_result(0) if args[:2] == ("stash", "store")
                              else None)
        self.assertEqual(rc, 5, out)
        self.assertIn("stash", out)

    def test_recreated_worktree_not_clean_exit_5(self):
        def replace(real, repo, args, kw):
            if args[:2] == ("worktree", "add"):
                r = real(repo, *args, **kw)
                write(os.path.join(self.a, "stray.txt"), "x\n")
                return r
        rc, out = self.rehome(replace=replace)
        self.assertEqual(rc, 5, out)
        self.assertIn("not clean", out)

    def test_recreated_worktree_at_another_head_exit_5(self):
        def replace(real, repo, args, kw):
            if args[:2] == ("worktree", "add") and "--detach" in args:     # same (no) branch, another HEAD
                return real(repo, "worktree", "add", "-q", "--detach", self.cw, S.c[0])
        rc, out = self.rehome(replace=replace)
        self.assertEqual(rc, 5, out)
        self.assertIn("recorded HEAD", out)

    def test_recreated_worktree_on_another_branch_exit_5(self):                 # R4-12 (T22)
        def replace(real, repo, args, kw):
            if args[:2] == ("worktree", "add") and args[-1] == "a-br":
                return real(repo, "worktree", "add", "-q", "-b", "not-a-br", args[-2], "a-br")
        rc, out = self.rehome(replace=replace)
        self.assertEqual(rc, 5, out)
        self.assertIn("recorded HEAD/branch/lock", out)

    def test_relock_skipped_exit_5(self):                                       # R4-12 (T23)
        git(self.live, "worktree", "lock", "--reason", "held", self.a)
        r, _ = inventory(self.live, self.inv)
        self.assertEqual(r.returncode, 0, r.stdout)
        rc, out = self.rehome(replace=lambda real, repo, args, kw: fake_result(0) if args[:2] == ("worktree", "lock")
                              else None)
        self.assertEqual(rc, 5, out)
        self.assertIn("recorded HEAD/branch/lock", out)

    # ---- the quiet window really waits, 60 s by default (R4-08: T14, T15)
    def fake_clock(self, slept):
        import types

        def sleep(seconds):
            slept.append(seconds)
            git(self.live, "branch", "late", S.new_main)                     # a writer inside the window
        return lambda mod: setattr(mod, "time", types.SimpleNamespace(sleep=sleep, time=mod.time.time))

    def test_quiet_window_sleeps_and_sees_a_writer_exit_4(self):
        slept = []
        rc, out = self.rehome(setup=self.fake_clock(slept))
        self.refs = refs(self.live)
        self.assertEqual(slept, [0.0])
        self.assert_refused_before_change(rc, out, 4)
        self.assertIn("quiet window", out)

    def test_quiet_window_default_is_60_seconds(self):
        slept = []
        rc, out = self.rehome(setup=self.fake_clock(slept),
                              argv=["rehome", self.live, self.inv, self.arch, S.purged, "--exclusive"])
        self.refs = refs(self.live)
        self.assertEqual(slept, [60.0])
        self.assert_refused_before_change(rc, out, 4)

    # ---- the snapshot sees each kind of change (R4-12: LC04, LC06, LC10, LC12, LC13)
    def assert_change_detected(self, key_part):
        rc, out = self.rehome()
        self.assert_refused_before_change(rc, out, 4)
        self.assertIn(key_part, out)

    def test_pseudo_ref_written_after_inventory_exit_4(self):                  # LC04
        write(os.path.join(self.live, ".git", "ORIG_HEAD"), S.c[0] + "\n")     # `git stash` left new_main there
        self.assert_change_detected("pseudo|ORIG_HEAD")

    def test_long_pseudo_ref_rewritten_after_inventory_exit_4(self):           # LC13
        fh = os.path.join(self.live, ".git", "FETCH_HEAD")
        write(fh, "%s\t\tbranch 'a' of x\n%s\t\tbranch 'b' of x\n" % (S.new_main, S.c[0]))
        r, _ = inventory(self.live, self.inv)
        self.assertEqual(r.returncode, 0, r.stdout)
        write(fh, "%s\t\tbranch 'a' of x\n%s\t\tbranch 'b' of x\n" % (S.c[0], S.new_main))
        self.assert_change_detected("pseudo|FETCH_HEAD")

    def test_reflog_rewritten_in_place_same_size_exit_4(self):                 # LC06
        log = os.path.join(self.live, ".git", "logs", "HEAD")
        data = bytearray(read(log))
        data[-2] = ord("X") if data[-2] != ord("X") else ord("Y")             # last message character
        write(log, bytes(data))
        self.assert_change_detected("reflog|HEAD")

    def test_untracked_file_added_after_inventory_exit_4(self):                # LC10
        write(os.path.join(self.b, "late.txt"), "written after the inventory\n")
        self.assert_change_detected("late.txt")

    def test_status_failure_counts_as_a_change_exit_4(self):                   # LC12
        clean = norm(self.a)                                                    # a CLEAN worktree: no file keys
        rc, out = self.rehome(replace=lambda real, repo, args, kw: fake_result(128) if args[:1] == ("status",)
                              and "--porcelain=v2" in args and norm(repo) == clean else None)
        self.assert_refused_before_change(rc, out, 4)
        self.assertIn("|file|", out)

    # ---- one run at a time; a change after the gate is still caught (R4-10)
    def test_second_rehome_during_the_first_exit_4(self):
        arch2, state = os.path.join(self.d, "arch2"), {}

        def fn(real, src, dst):
            if not state:
                state["b"] = run("rehome", self.live, self.inv, arch2, S.purged, *Q)
            return real(src, dst)
        with patched_rename(fn):
            rc, out = self.rehome()
        self.assertEqual(state["b"].returncode, 4, state["b"].stdout + state["b"].stderr)
        self.assertIn("rehome.lock", state["b"].stdout)
        self.assertFalse(os.path.exists(arch2))
        self.assertEqual(rc, 0, out)
        self.assertFalse(os.path.exists(self.live + ".rehome.lock"))          # released at the end

    def test_existing_lock_file_exit_4(self):
        lock = self.live + ".rehome.lock"
        write(lock, "pid 1\n")
        rc, out = self.rehome()
        self.assert_refused_before_change(rc, out, 4)
        self.assertTrue(os.path.isfile(lock))                                  # never removed: not ours
        self.assertFalse(os.path.exists(self.arch))

    def test_change_after_the_quiet_gate_exit_4(self):
        def setup(mod):
            real = mod.quiet_gate

            def gate(repo, a):
                snap = real(repo, a)
                git(self.live, "branch", "after-gate", S.new_main)
                return snap
            mod.quiet_gate = gate
        rc, out = self.rehome(setup=setup)
        self.refs = refs(self.live)
        self.assert_refused_before_change(rc, out, 4)
        self.assertIn("refs/heads/after-gate", out)
        self.assertFalse(os.path.exists(self.arch))

    # ---- rollback details (R4-12: T18, T19, T32)
    def test_repair_that_ran_then_failed_is_repaired_back_exit_3(self):
        def replace(real, repo, args, kw):
            if args[:2] == ("worktree", "repair") and norm(repo).startswith(norm(self.arch)):
                real(repo, *args, **kw)                                       # links now point into the archive
                return fake_result(1)
        rc, out = self.rehome(replace=replace)
        self.assertEqual(rc, 3, out)
        self.assert_original_layout()

    def test_rollback_leaves_no_archive_dir_so_a_retry_works(self):
        with patched_rename(self.fail_rename_of(self.live)):
            rc, out = self.rehome()
        self.assertEqual(rc, 3, out)
        self.assertFalse(os.path.exists(self.arch))
        rc, out = self.rehome()
        self.assertEqual(rc, 0, out)

    def test_clone_url_inside_the_checkout_refused(self):
        rc, out = self.rehome(argv=["rehome", self.live, self.inv, self.arch, os.path.join(self.live, ".git")]
                              + list(Q))
        self.assert_refused_before_change(rc, out)
        self.assertFalse(os.path.exists(self.arch))

    # ---- the new clone is prepared aside; nothing written at the path meanwhile is lost (R4-02)
    def test_path_recreated_while_the_clone_is_prepared_exit_5_nothing_lost(self):
        state = {}

        def replace(real, repo, args, kw):
            if args[:1] == ("clone",) and not state:
                res = real(repo, *args, **kw)
                state["x"] = 1
                write(os.path.join(self.live, "README.md"), "B: written at the path after the clone\n")
                return res
        rc, out = self.rehome(replace=replace)
        self.assertEqual(rc, 5, out)
        self.assertEqual(read(os.path.join(self.live, "README.md")), b"B: written at the path after the clone\n")
        self.assertEqual(os.listdir(self.live), ["README.md"])
        self.assertTrue(os.path.isdir(os.path.join(self.arch, "new-clone", ".git")))
        self.assertIn("new-clone", out)

    def test_commit_in_the_new_clone_during_worktree_add_exit_5(self):
        state = {}

        def replace(real, repo, args, kw):
            if args[:2] == ("worktree", "add") and not state:
                write(os.path.join(self.live, "README.md"), "B committed\n")
                git(self.live, "commit", "-q", "-am", "B: commit in the new clone")
                state["b"] = git(self.live, "rev-parse", "HEAD")
        rc, out = self.rehome(replace=replace)
        self.assertEqual(rc, 5, out)
        self.assertIn("reflog", out)
        self.assertEqual(git(self.live, "rev-parse", "HEAD"), state["b"])      # the commit is kept

    def test_new_clone_main_not_clean_when_main_was_old_exit_5(self):           # R4-01 verify
        git(self.live, "checkout", "-q", "--detach", S.c[2])                  # the main checkout is OLD
        r, _ = inventory(self.live, self.inv)
        self.assertEqual(r.returncode, 0, r.stdout)

        def replace(real, repo, args, kw):
            if args[:2] == ("worktree", "add"):
                write(os.path.join(self.live, "README.md"), "edited in the new clone\n")
        rc, out = self.rehome(replace=replace)
        self.assertEqual(rc, 5, out)
        self.assertIn("worktree %s is not clean" % self.live, out)


class InventoryInputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = cls.d = fresh("input")
        cls.live = S.live(os.path.join(d, "live"))
        cls.wt = os.path.join(d, "wt")
        git(cls.live, "worktree", "add", "-q", "--detach", cls.wt, S.new_main)
        os.makedirs(os.path.join(cls.live, "sub"))

    def test_linked_worktree_or_subfolder_as_repo_refused(self):
        for repo in (self.wt, os.path.join(self.live, "sub")):
            r, _ = inventory(repo, os.path.join(self.d, "inv-x.json"))
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("main worktree", r.stdout)

    def test_separate_git_dir_refused(self):
        sep = os.path.join(self.d, "sep")
        subprocess.run(["git", "clone", "-q", "--separate-git-dir", os.path.join(self.d, "sep.git"), S.purged, sep],
                       check=True, env=ENV, capture_output=True)
        r, _ = inventory(sep, os.path.join(self.d, "inv-sep.json"))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("separate git dir", r.stdout)

    # ---- the old-commits file (R4-08: T10, T11)
    def test_empty_old_commits_file_refused(self):
        empty = os.path.join(self.d, "empty.txt")
        write(empty, "")
        r, _ = inventory(self.live, os.path.join(self.d, "inv-empty.json"), empty)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("empty", r.stdout)

    def test_zero_commit_file_written_by_changed_accepted(self):
        zero = os.path.join(self.d, "zero.txt")
        self.assertEqual(run("changed", S.purged, S.purged, "--out", zero).returncode, 1)
        r, _ = inventory(self.live, os.path.join(self.d, "inv-zero.json"), zero)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_malformed_old_commits_line_refused(self):
        bad = os.path.join(self.d, "bad.txt")
        write(bad, "".join(s + "\n" for s in read(S.old).decode().split()[:-1]) + S.c[1][:20] + "\n")
        r, _ = inventory(self.live, os.path.join(self.d, "inv-bad.json"), bad)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("malformed", r.stdout)

    def test_change_during_inventory_exit_4(self):                              # R4-08 (T09)
        out = os.path.join(self.d, "inv-during.json")

        def setup(mod):
            real = mod.build_inventory

            def wrapped(*a, **kw):
                inv = real(*a, **kw)
                git(self.live, "branch", "written-during-inventory", S.new_main)
                return inv
            mod.build_inventory = wrapped
        try:
            rc, text = inproc(["inventory", self.live, S.old, "--out", out], setup=setup)
        finally:
            git(self.live, "branch", "-D", "written-during-inventory")
        self.assertEqual(rc, 4, text)
        self.assertIn("refs/heads/written-during-inventory", text)
        self.assertFalse(os.path.exists(out))

    # ---- a missing or broken inventory / record (R4-12 F7)
    def test_missing_or_invalid_inventory_exit_2(self):
        bad = os.path.join(self.d, "broken.json")
        write(bad, "{not json")
        half = os.path.join(self.d, "half.json")
        write(half, json.dumps({"repo": self.live}))
        for inv in (os.path.join(self.d, "nope.json"), bad, half):
            r = run("rehome", self.live, inv, os.path.join(self.d, "arch-x"), S.purged, *Q)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("REFUSED", r.stdout)
            self.assertNotIn("Traceback", r.stderr)
        r = run("restore", os.path.join(self.d, "no-archive"), "--exclusive")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("Traceback", r.stderr)


class InventoryMoreRefusalTest(unittest.TestCase):
    """Cases a re-clone cannot carry, and one it can (R4-12: T02, T04, F6)."""

    def test_kept_submodule_dirty_with_ignore_dirty_refused(self):             # T02
        d = fresh("dirty-sub-ign")
        live = S.live(os.path.join(d, "live"))
        k = os.path.join(d, "wts", "k")
        git(live, "worktree", "add", "-q", "-b", "k-br", k, S.new_main)
        sub = add_submodule(k)
        git(live, "config", "submodule.sub.ignore", "dirty")                   # superproject status stays quiet
        write(os.path.join(sub, "l.txt"), "uncommitted lib edit\n")
        self.assertEqual(git(k, "status", "--porcelain"), "")
        r, inv = inventory(live, os.path.join(d, "inv.json"))
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertTrue(any("submodule sub has changes" in x["problem"] for x in inv["refusals"]), inv["refusals"])

    def test_uninitialised_submodule_not_inspected(self):                       # T04
        d = fresh("uninit")
        live = S.live(os.path.join(d, "live"))
        k = os.path.join(d, "wts", "k")
        git(live, "worktree", "add", "-q", "-b", "k-br", k, S.new_main)
        add_submodule(k)
        git(k, "update-ref", "refs/heads/k-local", commit_on(k, git(k, "rev-parse", "HEAD"), "local work"))
        k2 = os.path.join(d, "wts", "k2")
        git(live, "worktree", "add", "-q", "--detach", k2, "k-br")              # same commit, submodule NOT initialised
        os.makedirs(os.path.join(k2, "sub"), exist_ok=True)
        r, inv = inventory(live, os.path.join(d, "inv.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual([w["submodules"] for w in inv["worktrees"] if norm(w["path"]) == norm(k2)], [[]])

    def test_skip_worktree_file_with_local_changes_refused(self):              # F6
        d = fresh("skipwt")
        live = S.live(os.path.join(d, "live"))
        write(os.path.join(live, "g.txt"), "LOCAL EDIT never committed\n")
        git(live, "update-index", "--skip-worktree", "g.txt")
        write(os.path.join(live, "README.md"), "hidden edit\n")
        git(live, "update-index", "--assume-unchanged", "README.md")
        self.assertEqual(git(live, "status", "--porcelain"), "")
        sp = os.path.join(d, "wt-sparse")                                       # sparse: skip-worktree, absent: fine
        git(live, "worktree", "add", "-q", "-b", "sp", sp, "main")
        git(sp, "sparse-checkout", "set", "--no-cone", "/README.md")
        r, inv = inventory(live, os.path.join(d, "inv.json"))
        self.assertEqual(r.returncode, 2, r.stdout)
        problems = [x["problem"] for x in inv["refusals"]]
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("g.txt", problems[0])
        self.assertIn("README.md", problems[0])
        self.assertIn("skip-worktree", problems[0])


def layout(name, build, rehome_it=True):
    """live = S.live(...); build(live, d) -> info; inventory; rehome. Returns a namespace."""
    import types
    d = fresh(name)
    live = S.live(os.path.join(d, "live"))
    info = build(live, d)
    ns = types.SimpleNamespace(d=d, live=live, info=info, inv_path=os.path.join(d, "inv.json"),
                               arch=os.path.join(d, "arch"))
    ns.inv_run, ns.inv = inventory(live, ns.inv_path)
    if rehome_it and ns.inv_run.returncode == 0:
        ns.rh = run("rehome", live, ns.inv_path, ns.arch, S.purged, *Q)
    return ns


class RehomeLayoutTest(unittest.TestCase):
    """Layouts inventory accepts must rehome to exit 0 (R4-01, R4-04, R4-12)."""

    def assert_ok(self, ns):
        self.assertEqual(ns.inv_run.returncode, 0, ns.inv_run.stdout)
        self.assertEqual(ns.rh.returncode, 0, ns.rh.stdout + ns.rh.stderr)
        self.assertEqual(git(ns.live, "status", "--porcelain"), "")
        self.assertEqual(git(ns.live, "for-each-ref", "refs/rehome-tmp/"), "")

    def test_old_main_checkout_with_kept_local_main_ahead(self):                # R4-01
        def build(live, d):
            write(os.path.join(live, "local.txt"), "local kept work\n")
            git(live, "add", "-A")
            git(live, "commit", "-q", "-m", "local kept")
            kept = git(live, "rev-parse", "main")
            git(live, "checkout", "-q", "old-feature")
            return kept
        ns = layout("old-main-ahead", build)
        self.assert_ok(ns)
        self.assertEqual(git(ns.live, "rev-parse", "refs/heads/main"), ns.info)
        self.assertEqual(git(ns.live, "rev-parse", "HEAD"), ns.info)
        self.assertEqual(git(ns.live, "diff", "--cached", "--stat"), "")
        self.assertEqual(read(os.path.join(ns.live, "local.txt")), b"local kept work\n")

    def test_detached_main_at_a_local_only_commit(self):                        # R4-04
        def build(live, d):
            git(live, "checkout", "-q", "--detach")
            write(os.path.join(live, "w.txt"), "detached work\n")
            git(live, "add", "-A")
            git(live, "commit", "-q", "-m", "detached work")
            return git(live, "rev-parse", "HEAD")
        ns = layout("detached-main", build)
        self.assert_ok(ns)
        self.assertEqual(git(ns.live, "rev-parse", "HEAD"), ns.info)
        self.assertEqual(git(ns.live, "symbolic-ref", "-q", "HEAD", check=False), "")

    def test_old_main_checkout_and_a_kept_worktree_on_main(self):              # R4-04
        def build(live, d):
            git(live, "checkout", "-q", "old-feature")
            wt = os.path.join(d, "wt-main")
            git(live, "worktree", "add", "-q", wt, "main")
            return wt
        ns = layout("old-main-wt-main", build)
        self.assert_ok(ns)
        rows = {w["path"]: w for w in wt_list(ns.live)}
        self.assertEqual(rows[norm(ns.info)]["branch"], "refs/heads/main")
        self.assertTrue(rows[norm(ns.live)]["detached"])

    def test_main_per_worktree_ref_carried(self):                               # R4-04 (D)
        ns = layout("perwt-main", lambda live, d: git(live, "update-ref", "refs/worktree/mark", "HEAD"))
        self.assert_ok(ns)
        self.assertEqual(git(ns.live, "rev-parse", "refs/worktree/mark"), git(ns.live, "rev-parse", "HEAD"))

    def test_per_worktree_ref_of_an_old_worktree_not_carried(self):            # R4-04 (E)
        def build(live, d):
            wt = os.path.join(d, "wt-old")
            git(live, "worktree", "add", "-q", wt, "old-feature")
            git(wt, "update-ref", "refs/worktree/mark", S.new_main)
            return wt
        ns = layout("perwt-old", build)
        self.assert_ok(ns)
        row = [r for r in ns.inv["refs"] if r["name"] == "refs/worktree/mark"]
        self.assertEqual([(r["old"], r["carry"]) for r in row], [(False, False)])
        self.assertIn("stays in the archive", ns.inv_run.stdout)
        moved = find_archived(ns.arch, "wt-old")
        self.assertEqual(git(moved, "rev-parse", "refs/worktree/mark"), S.new_main)

    def test_duplicate_shas_every_temp_ref_deleted(self):                      # R4-12 (F5)
        def build(live, d):
            wt = os.path.join(d, "wt-k")
            git(live, "worktree", "add", "-q", "-b", "k", wt, "main")
            git(wt, "update-ref", "refs/worktree/a", "HEAD")
            git(wt, "update-ref", "refs/worktree/b", "HEAD")
            write(os.path.join(live, "README.md"), "x\n")
            git(live, "stash", "-q")
            first = git(live, "rev-parse", "refs/stash")
            write(os.path.join(live, "README.md"), "y\n")
            git(live, "stash", "-q")
            git(live, "stash", "store", "-q", "-m", "dup", first)               # the same SHA twice
            return wt
        ns = layout("dup-sha", build)
        self.assert_ok(ns)
        self.assertEqual(len(reflog(ns.live, "refs/stash")), 3)
        self.assertEqual(git(ns.info, "rev-parse", "refs/worktree/b"), git(ns.info, "rev-parse", "HEAD"))

    def test_linked_worktrees_with_the_same_folder_name(self):                 # R4-12 (T16)
        def build(live, d):
            for i in (1, 2):
                git(live, "worktree", "add", "-q", "-b", "app%d" % i, os.path.join(d, "wts%d" % i, "app"), S.new_main)
        ns = layout("same-name", build)
        self.assert_ok(ns)
        self.assertEqual(sorted(os.listdir(os.path.join(ns.arch, "worktrees"))), ["0-app", "1-app"])

    def test_kept_worktree_nested_in_a_kept_linked_worktree(self):            # R4-12 (T21)
        def build(live, d):
            outer = os.path.join(d, "wts", "outer")
            git(live, "worktree", "add", "-q", "-b", "outer-br", outer, S.new_main)
            git(live, "worktree", "add", "-q", "-b", "inner-br", os.path.join(outer, ".wt", "inner"), S.new_main)
            return outer
        ns = layout("nested-kept", build)
        self.assert_ok(ns)
        self.assertEqual(len(wt_list(ns.live)), 3)

    def test_ignored_paths_named_in_the_inventory_and_rehome_md(self):        # R4-03
        def build(live, d):
            write(os.path.join(live, "_staging", "PENDING_REIMPORT.md"), "# pending\n")
            write(os.path.join(live, "debug.log"), "x\n")                       # *.log is ignored
            write(os.path.join(live, ".git", "info", "exclude"), "_staging/\n")
        ns = layout("ignored", build)
        self.assert_ok(ns)
        self.assertIn("_staging/", ns.inv_run.stdout)
        self.assertIn("debug.log", ns.inv_run.stdout)
        main = [w for w in ns.inv["worktrees"] if w["main"]][0]
        self.assertEqual(main["ignored"], ["_staging/", "debug.log"])
        text = read(os.path.join(ns.arch, "REHOME.md")).decode("utf-8")
        self.assertIn(os.path.join(ns.arch, "repo", "_staging/"), text)
        self.assertFalse(os.path.exists(os.path.join(ns.live, "_staging")))

    def test_old_worktree_submodule_outside_its_index_usable_in_the_archive(self):   # R4-05
        def build(live, d):
            git(live, "submodule", "add", "-q", S.lib, "lib")
            git(live, "commit", "-q", "-m", "lib")
            git(live, "branch", "k")
            wk = os.path.join(d, "wk")
            git(live, "worktree", "add", "-q", wk, "k")
            git(wk, "submodule", "update", "-q", "--init")
            sub = os.path.join(wk, "lib")
            git(sub, "checkout", "-q", "-b", "x")
            write(os.path.join(sub, "u.txt"), "u\n")
            git(sub, "add", "-A")
            git(sub, "commit", "-q", "-m", "unpushed")
            up = git(sub, "rev-parse", "HEAD")
            git(wk, "checkout", "-q", "-f", "old-feature")                     # lib/ is no longer in its index
            return up
        ns = layout("sub-outside-index", build)
        self.assertEqual(ns.inv_run.returncode, 0, ns.inv_run.stdout)
        self.assertEqual(ns.rh.returncode, 0, ns.rh.stdout + ns.rh.stderr)
        sub = os.path.join(find_archived(ns.arch, "wk"), "lib")
        self.assertEqual(git(sub, "rev-parse", "refs/heads/x"), ns.info)
        self.assertEqual(norm(git(sub, "rev-parse", "--show-toplevel")), norm(sub))
        self.assertEqual(git(sub, "status", "--porcelain"), "")


class RestoreTest(unittest.TestCase):
    """rehome, then `restore`: the archived checkout is back at its paths and equals the inventory (R4-06)."""

    @classmethod
    def setUpClass(cls):
        d = cls.d = fresh("restore")
        live = cls.live = S.live(os.path.join(d, "live"))
        git(live, "submodule", "add", "-q", S.lib, "lib")
        git(live, "commit", "-q", "-m", "add lib")
        git(live, "branch", "k")
        wk = cls.wk = os.path.join(d, "wt-kept")
        git(live, "worktree", "add", "-q", wk, "k")
        git(wk, "submodule", "update", "-q", "--init")                         # repo under .git/worktrees/<id>/modules
        wo = cls.wo = os.path.join(d, "wt-old")
        git(live, "worktree", "add", "-q", wo, "old-feature")
        git(wo, "submodule", "add", "-q", S.lib, "lib")
        git(wo, "commit", "-q", "-m", "lib on old")
        write(os.path.join(wo, "lib", "u.txt"), "unpushed\n")
        git(os.path.join(wo, "lib"), "add", "-A")
        git(os.path.join(wo, "lib"), "commit", "-q", "-m", "unpushed sub commit")
        cls.unpushed = git(os.path.join(wo, "lib"), "rev-parse", "HEAD")
        git(live, "worktree", "add", "-q", os.path.join(live, "nested"), "-b", "nest", "main")
        write(os.path.join(live, ".gitignore"), "*.log\n.env\nnested/\n")
        git(live, "commit", "-q", "-am", "ignore")
        write(os.path.join(live, ".env"), "TOKEN=fake\n")
        write(os.path.join(live, "README.md"), "stashed\n")
        git(live, "stash", "-q")
        cls.refs_before, cls.wts_before = refs(live), wt_paths(live)
        cls.inv_run, _ = inventory(live, os.path.join(d, "inv.json"))
        cls.arch = os.path.join(d, "arch")
        cls.rh = run("rehome", live, os.path.join(d, "inv.json"), cls.arch, S.purged, *Q)
        cls.rs = run("restore", cls.arch, "--exclusive")

    def test_rehome_then_restore_exit_0(self):
        self.assertEqual(self.inv_run.returncode, 0, self.inv_run.stdout)
        self.assertEqual(self.rh.returncode, 0, self.rh.stdout + self.rh.stderr)
        self.assertEqual(self.rs.returncode, 0, self.rs.stdout + self.rs.stderr)
        self.assertIn("matches the inventory", self.rs.stdout)

    def test_original_layout_back(self):
        self.assertEqual(refs(self.live), self.refs_before)
        self.assertEqual(wt_paths(self.live), self.wts_before)
        self.assertEqual(read(os.path.join(self.live, ".env")), b"TOKEN=fake\n")
        self.assertFalse(os.path.exists(os.path.join(self.arch, "repo")))

    def test_submodules_usable_at_their_original_paths(self):
        for wt in (self.wk, self.wo):
            sub = os.path.join(wt, "lib")
            self.assertEqual(norm(git(sub, "rev-parse", "--show-toplevel")), norm(sub))
            self.assertEqual(git(sub, "status", "--porcelain"), "")
        self.assertTrue(exists(os.path.join(self.wo, "lib"), self.unpushed))

    def test_new_clone_kept_aside_in_the_archive(self):
        aside = [n for n in os.listdir(self.arch) if n.startswith("restored-aside")]
        self.assertEqual(len(aside), 1, os.listdir(self.arch))
        self.assertEqual(git(os.path.join(self.arch, aside[0], "repo"), "rev-parse", "refs/remotes/origin/main"),
                         S.new_main)

    def test_restore_needs_exclusive(self):
        r = run("restore", self.arch)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)

    def test_archived_submodules_usable_before_the_restore(self):              # R4-05 (core.worktree)
        d = fresh("restore-sub-archived")
        live = S.live(os.path.join(d, "live"))
        git(live, "submodule", "add", "-q", S.lib, "lib")
        git(live, "commit", "-q", "-m", "add lib")
        wk = os.path.join(d, "wt-kept")
        git(live, "worktree", "add", "-q", "-b", "k", wk, "main")
        git(wk, "submodule", "update", "-q", "--init")
        r, _ = inventory(live, os.path.join(d, "inv.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        arch = os.path.join(d, "arch")
        rh = run("rehome", live, os.path.join(d, "inv.json"), arch, S.purged, *Q)
        self.assertEqual(rh.returncode, 0, rh.stdout + rh.stderr)
        archived = find_archived(arch, "wt-kept")
        self.assertEqual(git(archived, "status", "--porcelain"), "")          # recurses into lib/
        sub = os.path.join(archived, "lib")
        self.assertEqual(norm(git(sub, "rev-parse", "--show-toplevel")), norm(sub))

    def test_restore_reports_a_difference_from_the_inventory_exit_1(self):
        d = fresh("restore-differs")
        live = S.live(os.path.join(d, "live"))
        r, _ = inventory(live, os.path.join(d, "inv.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        arch = os.path.join(d, "arch")
        rh = run("rehome", live, os.path.join(d, "inv.json"), arch, S.purged, *Q)
        self.assertEqual(rh.returncode, 0, rh.stdout + rh.stderr)
        git(os.path.join(arch, "repo"), "branch", "added-in-the-archive", S.new_main)
        rs = run("restore", arch, "--exclusive")
        self.assertEqual(rs.returncode, 1, rs.stdout + rs.stderr)
        self.assertIn("refs/heads/added-in-the-archive", rs.stdout)
        self.assertEqual(git(live, "rev-parse", "refs/heads/added-in-the-archive"), S.new_main)   # restored


class UnitTest(unittest.TestCase):
    def test_index_only_status_codes(self):
        mod = load_module()
        self.assertTrue(all(mod.index_only(x) for x in ("MM", "AM", "RM", "MD", "AD")))
        self.assertFalse(any(mod.index_only(x) for x in (" M", "M ", "A ", "??", " D")))


if __name__ == "__main__":
    unittest.main()
