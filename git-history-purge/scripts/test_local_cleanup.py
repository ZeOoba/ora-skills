"""Tests for local_cleanup.py (stdlib unittest; gated by tools/run_skill_suites.sh).

Real git in temp dirs. The purge is a real `git filter-repo --replace-text` run on a mirror clone
of the backup (SKILL.md Step 3). The FIRST commit holds nothing private, so the purge keeps its SHA
and new branches share it: such branches must NOT count as old history.

v2.4 (round-7 cut, Gabriel: "Cut rehome/restore (Recommended)"): Step 6 is a manual procedure.
`inventory` stays read-only: it classifies, refuses every unsupported layout with a manual fix, and with
--archive prints the Step 6 commands. Every test here that checks the procedure FOLLOWS the printed
commands literally (each line through `sh -c`) and then checks the new clone and the archive; each
refusal's printed fix is applied as printed and inventory then passes. SKILL.md's freeze/unfreeze recipe
is run as written on three remote shapes.
"""
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "local_cleanup.py")
SKILL_MD = os.path.join(os.path.dirname(HERE), "SKILL.md")
ENV = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="t",
           GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com",
           GIT_ALLOW_PROTOCOL="file")
SH = shutil.which("sh") or shutil.which("bash")
BEGIN, UNDO, END = "# --- Step 6 commands (printed, not run) ---", "# --- Undo ---", "# --- end ---"


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false", "-c", "protocol.file.allow=always"]
                          + list(args), capture_output=True, encoding="utf-8", errors="surrogateescape",
                          check=check, env=ENV).stdout.strip()


def run(*args, cwd=None):
    return subprocess.run([sys.executable, "-I", "-X", "utf8", SCRIPT] + list(args), capture_output=True,
                          encoding="utf-8", errors="replace", env=ENV, cwd=cwd)          # exact non-ASCII lines


def sh(script, cwd=None):
    """Run shell text exactly as printed or documented (POSIX sh)."""
    return subprocess.run([SH, "-c", script], capture_output=True, encoding="utf-8", errors="replace", env=ENV,
                          cwd=cwd)


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


def inventory(live, out, old=None, *extra):
    r = run("inventory", live, old or S.old, "--out", out, *extra)
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


def block(stdout, first, last):
    """The printed lines strictly between the marker lines first and last."""
    lines = stdout.splitlines()
    assert first in lines and last in lines, stdout
    return lines[lines.index(first) + 1:lines.index(last)]


def follow(lines):
    """Run every non-comment line exactly as printed; each must exit 0. Returns the outputs."""
    outs = []
    for line in lines:
        if line.startswith("#"):
            continue
        r = sh(line)
        if r.returncode != 0:
            raise AssertionError("exit %d: %s\n%s%s" % (r.returncode, line, r.stdout, r.stderr))
        outs.append(r.stdout)
    return outs


def step6(live, d, follow_it=True, url=None):
    """inventory --archive <d>/arch --clone-url <purged>, then follow the printed Step 6 commands."""
    arch = os.path.join(d, "arch")
    r, inv = inventory(live, os.path.join(d, "inv.json"), None, "--archive", arch, "--clone-url", url or S.purged)
    if r.returncode != 0:
        raise AssertionError("inventory exit %d\n%s%s" % (r.returncode, r.stdout, r.stderr))
    cmds, undo = block(r.stdout, BEGIN, UNDO), block(r.stdout, UNDO, END)
    if follow_it:
        follow(cmds)
    return arch, r, inv, cmds, undo


def find_archived(arch, marker):
    """The archived worktree folder under <arch>/worktrees whose name ends with marker."""
    base = os.path.join(arch, "worktrees")
    hits = [os.path.join(base, n) for n in os.listdir(base) if n.endswith(marker)]
    assert len(hits) == 1, (marker, os.listdir(base))
    return hits[0]


def printed_fix(stdout, path):
    """The backticked commands of the REFUSED line for path, in order."""
    for line in stdout.splitlines():
        if line.startswith("REFUSED %s: " % path):
            return re.findall(r"`([^`]+)`", line.split(" -> ", 1)[1])
    raise AssertionError("no REFUSED line for %s:\n%s" % (path, stdout))


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
        git(late_src, "switch", "-q", "--orphan", "late")                       # empty index: holds no old blob
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
        git(ow, "update-ref", "refs/worktree/keep", nm)                       # per-worktree refs of an OLD
        git(ow, "update-ref", "refs/bisect/bad", c[1])                         # worktree stay in the archive
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

    def test_old_worktrees_own_refs_neither_refused_nor_carried(self):        # v2.3: they stay in the archive
        names = {x["name"] for x in self.inv1["refs"]}
        self.assertFalse(names & {"refs/worktree/keep", "refs/bisect/bad"})
        ow = [w for w in self.inv1["worktrees"] if norm(w["path"]) == norm(self.ow)][0]
        self.assertEqual(sorted(ow["own_refs"]), ["refs/bisect/bad", "refs/worktree/keep"])
        self.assertEqual(self.inv1["refusals"], [])

    def test_worktrees_classified(self):
        old = {norm(w["path"]): w["old"] for w in self.inv1["worktrees"]}
        self.assertEqual(old, {norm(self.live): False, norm(self.ow): True, norm(self.kw): False})

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
        # v2.3 refusals: layouts outside the supported set
        nested = cls.wt["k-nested"] = os.path.join(live, ".wt", "k-nested")     # inside the main folder
        git(live, "worktree", "add", "-q", "--detach", nested, nm)
        host = add("o-host", c[2], "-b", "o-host-br")                           # OLD, holding a KEPT one
        inner = cls.wt["k-in-old"] = os.path.join(host, "inner")
        git(live, "worktree", "add", "-q", "-b", "inner-br", inner, nm)
        git(live, "worktree", "add", "-q", "--orphan", "-b", "fresh", os.path.join(d, "k-unborn"))
        cls.wt["k-unborn"] = os.path.join(d, "k-unborn")
        pw = add("k-perwt", nm, "--detach")
        git(pw, "update-ref", "refs/worktree/keep", nm)
        add("k-lost", commit_on(live, nm, "no ref reaches this"), "--detach")
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

    def test_kept_initialised_submodule_refused(self):                         # v2.3: never carried
        self.assert_refused("k-sub", "initialised submodule")

    def test_worktree_nested_in_the_main_folder_refused(self):                 # R5-02
        self.assert_refused("k-nested", "nested inside %s" % self.live)

    def test_kept_worktree_nested_in_an_old_worktree_refused(self):            # R5-08 (correctness F6)
        self.assert_refused("k-in-old", "nested inside %s" % self.wt["o-host"])

    def test_unborn_branch_refused(self):                                       # R5-03
        self.assert_refused("k-unborn", "unborn")

    def test_per_worktree_ref_in_a_kept_worktree_refused(self):
        self.assert_refused("k-perwt", "per-worktree ref")

    def test_kept_detached_head_no_carried_ref_reaches_refused(self):
        self.assert_refused("k-lost", "no carried ref reaches")

    def test_operation_in_progress_in_an_old_worktree_refused(self):           # a session is mid-operation there
        self.assert_refused("o-busy", "in progress")

    def test_missing_worktree_folder_refused(self):
        self.assert_refused("k-gone", "missing")

    def test_dirty_old_worktree_allowed(self):
        self.assertNotIn(norm(self.wt["o-dirty"]), self.problems)

    def test_each_refusal_names_what_to_do(self):
        self.assertTrue(all(x["fix"] for x in self.inv["refusals"]))
        self.assertIn("REFUSED", self.r.stdout)

class RefusalInstructionTest(unittest.TestCase):
    """v2.3: each refusal prints a manual instruction; applied exactly as printed, inventory then passes."""

    def live(self, name):
        d = fresh(name)
        return d, S.live(os.path.join(d, "live"))

    def refused_then_fixed(self, d, live, instruction, fix, word, paths=None):
        r, inv = inventory(live, os.path.join(d, "inv1.json"))
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertTrue(inv["refusals"] and all(word in x["problem"] for x in inv["refusals"]), inv["refusals"])
        if paths:                                                               # every case named, by its worktree
            self.assertEqual(sorted(norm(x["path"]) for x in inv["refusals"]), sorted(norm(p) for p in paths))
        self.assertIn(instruction, r.stdout)
        fix()
        r, inv = inventory(live, os.path.join(d, "inv2.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        return {x["name"]: x for x in inv["refs"]}

    def test_unborn_branch_in_a_linked_worktree_then_commit(self):            # R5-03 (C)
        d, live = self.live("fix-unborn-wt")
        wt = os.path.join(d, "wt")
        git(live, "worktree", "add", "-q", "--orphan", "-b", "fresh", wt)
        refs_ = self.refused_then_fixed(d, live, "`git commit --allow-empty -m start`",
                                        lambda: git(wt, "commit", "-q", "--allow-empty", "-m", "start"), "unborn")
        self.assertTrue(refs_["refs/heads/fresh"]["carry"])

    def test_unborn_branch_in_the_main_worktree_then_commit(self):             # R5-03 (B)
        d, live = self.live("fix-unborn-main")
        git(live, "switch", "-q", "--orphan", "fresh")
        refs_ = self.refused_then_fixed(d, live, "`git commit --allow-empty -m start`",
                                        lambda: git(live, "commit", "-q", "--allow-empty", "-m", "start"), "unborn")
        self.assertTrue(refs_["refs/heads/fresh"]["carry"])

    def test_nested_worktree_then_worktree_move(self):                          # R5-02
        d, live = self.live("fix-nested")
        inner = os.path.join(live, ".wt", "inner")
        git(live, "worktree", "add", "-q", "-b", "inner-br", inner, S.new_main)
        self.refused_then_fixed(d, live, "`git worktree move -f -f <path> <new path outside every worktree>`",
                                lambda: git(live, "worktree", "move", inner, os.path.join(d, "inner")), "nested")

    def test_per_worktree_refs_then_branch_and_delete(self):
        d, live = self.live("fix-perwt")
        wt = os.path.join(d, "wt")
        git(live, "worktree", "add", "-q", "-b", "wt-br", wt, S.new_main)
        git(wt, "update-ref", "refs/worktree/keep", S.new_main)
        git(live, "update-ref", "refs/bisect/good", S.new_main)                 # the main worktree's own

        def fix():
            for where, ref, name in ((wt, "refs/worktree/keep", "keep-wt"), (live, "refs/bisect/good", "good-main")):
                git(where, "branch", name, ref)
                git(where, "update-ref", "-d", ref)
        refs_ = self.refused_then_fixed(d, live, "`git branch <name> <ref>`, then `git update-ref -d <ref>`", fix,
                                        "per-worktree ref", paths=[wt, live])
        self.assertTrue(refs_["refs/heads/keep-wt"]["carry"] and refs_["refs/heads/good-main"]["carry"])

    def test_detached_head_no_carried_ref_reaches_then_branch(self):           # was R4-04's detached main
        d, live = self.live("fix-unreached")
        wt = os.path.join(d, "wt")
        git(live, "worktree", "add", "-q", "--detach", wt, commit_on(live, S.new_main, "only HEAD reaches it"))
        git(live, "checkout", "-q", "--detach", commit_on(live, S.new_main, "main detached here"))
        wt2, remote_only = os.path.join(d, "wt2"), commit_on(live, S.new_main, "only a remote-tracking ref")
        git(live, "update-ref", "refs/remotes/other/x", remote_only)              # never carried
        git(live, "worktree", "add", "-q", "--detach", wt2, remote_only)
        refs_ = self.refused_then_fixed(d, live, "`git branch <name>` in that worktree", lambda: (
            git(wt, "branch", "saved-wt"), git(live, "branch", "saved-main"), git(wt2, "branch", "saved-wt2")),
            "no carried ref reaches", paths=[wt, live, wt2])
        self.assertTrue(refs_["refs/heads/saved-wt"]["carry"])

    def test_carried_ref_holding_a_purged_blob_then_rebuild(self):             # R5-04 (inventory check)
        d, live = self.live("fix-purged-blob")
        blob = git(live, "rev-parse", S.c[1] + ":f.txt")
        tree = subprocess.run(["git", "-C", live, "mktree"], input="100644 blob %s\tf.txt\n" % blob,
                              capture_output=True, encoding="utf-8", env=ENV, check=True).stdout.strip()
        old_tip = git(live, "commit-tree", tree, "-p", S.new_main, "-m", "re-add")
        git(live, "update-ref", "refs/heads/readd", old_tip)
        refs_ = self.refused_then_fixed(d, live, "rebuild it without that content", lambda: git(
            live, "update-ref", "refs/heads/readd", commit_on(live, S.new_main, "rebuilt"), old_tip), "purged")
        self.assertTrue(refs_["refs/heads/readd"]["carry"])
        self.assertIn(old_tip, reflog(live, "refs/heads/readd"))                 # the old tip stays in the reflog

    def test_step_6_2_recipe_keeps_no_purged_object(self):                      # R5-04 (SKILL.md recipe)
        d, live = self.live("fix-recipe")
        git(live, "branch", "old-feature", "origin/old-feature")
        old_tip = git(live, "rev-parse", "refs/heads/old-feature")
        wrong = git(live, "commit-tree", old_tip + "^{tree}", "-p", S.new_main, "-m", "v2.2.1 recipe")
        git(live, "update-ref", "refs/heads/old-feature", wrong, old_tip)       # the round-5 recipe: refused

        def recipe():                                                           # SKILL.md Step 6 item 2 (v2.3)
            cur = git(live, "rev-parse", "refs/heads/old-feature")
            git(live, "fetch", "-q", S.purged, "refs/heads/old-feature")
            git(live, "update-ref", "refs/heads/old-feature", git(live, "rev-parse", "FETCH_HEAD"), cur)
        refs_ = self.refused_then_fixed(d, live, "SKILL.md Step 6 item 2", recipe, "purged")
        self.assertTrue(refs_["refs/heads/old-feature"]["carry"])
        self.assertEqual(refs_["refs/heads/old-feature"]["sha"], git(S.purged, "rev-parse", "refs/heads/old-feature"))


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
    def test_missing_old_commits_file_refused(self):                             # R5-06 (I01)
        nope = os.path.join(self.d, "no-such-old-commits.txt")
        r, _ = inventory(self.live, os.path.join(self.d, "inv-nope.json"), nope)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("REFUSED: old-commits file not found: %s" % nope, r.stdout.splitlines())
        r = run("overlap", self.live, nope)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

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
        self.assertTrue(any("initialised submodule" in x["problem"] for x in inv["refusals"]), inv["refusals"])

    def test_uninitialised_submodule_not_inspected(self):                       # T04
        d = fresh("uninit")
        live = S.live(os.path.join(d, "live"))
        k = os.path.join(d, "wts", "k")
        git(live, "worktree", "add", "-q", "-b", "k-br", k, S.new_main)
        add_submodule(k)
        git(k, "submodule", "deinit", "-q", "-f", "sub")                         # v2.3: an initialised one is refused
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




class RefusalPrintedFixTest(unittest.TestCase):
    """v2.4: the printed fix (its backticked commands, in order) is run exactly as printed; inventory then passes."""

    def test_hidden_changes_then_the_two_printed_commands_then_stash(self):    # R6-03
        d = fresh("fix-hidden")
        live = S.live(os.path.join(d, "live"))
        write(os.path.join(live, "g.txt"), "LOCAL EDIT never committed\n")
        git(live, "update-index", "--skip-worktree", "g.txt")
        write(os.path.join(live, "README.md"), "hidden edit\n")
        git(live, "update-index", "--assume-unchanged", "README.md")
        r, _inv = inventory(live, os.path.join(d, "inv1.json"))
        self.assertEqual(r.returncode, 2, r.stdout)
        fix = printed_fix(r.stdout, live)
        self.assertEqual(fix[:2], ["git update-index --no-skip-worktree <file>",
                                   "git update-index --no-assume-unchanged <file>"])
        for f in ("g.txt", "README.md"):
            for cmd in fix[:2]:
                res = sh(cmd.replace("<file>", f), cwd=live)
                self.assertEqual(res.returncode, 0, cmd + res.stderr)
        self.assertEqual(sh("git stash", cwd=live).returncode, 0)
        r, _inv = inventory(live, os.path.join(d, "inv2.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn(b"LOCAL EDIT never committed", subprocess.run(
            ["git", "-C", live, "show", "stash@{0}:g.txt"], capture_output=True, env=ENV).stdout)
        self.assertIn(b"hidden edit", subprocess.run(
            ["git", "-C", live, "show", "stash@{0}:README.md"], capture_output=True, env=ENV).stdout)

    def test_locked_nested_worktree_then_printed_move_keeps_the_lock(self):    # correctness F4
        d = fresh("fix-nested-locked")
        live = S.live(os.path.join(d, "live"))
        inner, new = os.path.join(live, ".wt", "inner"), os.path.join(d, "inner")
        git(live, "worktree", "add", "-q", "-b", "inner-br", inner, S.new_main)
        git(live, "worktree", "lock", "--reason", "on a USB stick", inner)
        r, _inv = inventory(live, os.path.join(d, "inv1.json"))
        self.assertEqual(r.returncode, 2, r.stdout)
        fix = printed_fix(r.stdout, inner)
        self.assertEqual(len(fix), 1, fix)
        res = sh(fix[0].replace("<path>", shlex.quote(inner)).replace(
            "<new path outside every worktree>", shlex.quote(new)), cwd=live)
        self.assertEqual(res.returncode, 0, res.stderr)
        r, _inv = inventory(live, os.path.join(d, "inv2.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        rows = {w["path"]: w for w in wt_list(live)}
        self.assertEqual(rows[norm(new)]["locked"], "on a USB stick")

    def test_main_inside_a_linked_worktree_then_printed_fix(self):             # T037
        d = fresh("fix-main-in-wt")
        live = S.live(os.path.join(d, "live"))
        host = os.path.join(d, "host")
        git(live, "worktree", "add", "-q", "-b", "host-br", host, S.new_main)
        main = os.path.join(host, "inner-main")
        os.rename(live, main)
        git(main, "worktree", "repair")
        r, inv = inventory(main, os.path.join(d, "inv1.json"))
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertTrue(any("the main checkout is inside worktree %s" % host in x["problem"]
                            for x in inv["refusals"]), inv["refusals"])
        fix = printed_fix(r.stdout, main)
        moved = os.path.join(d, "main2")
        res = sh(fix[0].replace("<main>", shlex.quote(main)).replace(
            "<new path outside every worktree>", shlex.quote(moved)), cwd=d)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(fix[1], "git worktree repair")
        self.assertEqual(sh(fix[1], cwd=moved).returncode, 0)
        r, _inv = inventory(moved, os.path.join(d, "inv2.json"))
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_carried_tag_and_notes_holding_a_purged_blob_refused_then_rebuild(self):   # T016
        d = fresh("fix-purged-tag")
        live = S.live(os.path.join(d, "live"))
        blob = git(live, "rev-parse", S.c[1] + ":f.txt")
        tree = subprocess.run(["git", "-C", live, "mktree"], input="100644 blob %s\tf.txt\n" % blob,
                              capture_output=True, encoding="utf-8", env=ENV, check=True).stdout.strip()
        tip = git(live, "commit-tree", tree, "-p", S.new_main, "-m", "re-add on new history")
        git(live, "tag", "release-readd", tip)
        git(live, "update-ref", "refs/notes/readd", tip)
        r, inv = inventory(live, os.path.join(d, "inv1.json"))
        self.assertEqual(r.returncode, 2, r.stdout)
        problems = sorted(x["problem"] for x in inv["refusals"])
        self.assertEqual(problems, ["ref refs/notes/readd reaches 1 purged blob/tree/tag object(s)",
                                    "ref refs/tags/release-readd reaches 1 purged blob/tree/tag object(s)"])
        for ref in ("refs/tags/release-readd", "refs/notes/readd"):
            git(live, "update-ref", ref, commit_on(live, S.new_main, "rebuilt"), tip)
        r, _inv = inventory(live, os.path.join(d, "inv2.json"))
        self.assertEqual(r.returncode, 0, r.stdout)


# ==================================================================== Step 6 procedure, followed literally

class Step6ProcedureTest(unittest.TestCase):
    """Main checkout (kept, on a non-ASCII branch), kept linked worktrees (one locked, one detached), an old
    dirty worktree, kept and old stash entries, a kept unpushed branch, kept tags and notes, a second remote,
    frozen pushurls and an absolute core.hooksPath inside .git (as install_hooks.py sets it). inventory
    --archive prints the commands; every one is run as printed."""

    @classmethod
    def setUpClass(cls):
        d = cls.d = fresh("happy ü")
        c, nm = S.c, S.new_main
        live = cls.live = S.live(os.path.join(d, "live ü x"))
        git(live, "config", "remote.origin.pushurl", "DISABLED-history-purge-x")          # the Step 0 freeze
        git(live, "remote", "add", "fork", "https://example.invalid/fork.git")
        git(live, "config", "remote.fork.pushurl", "DISABLED-history-purge-x")
        hooks = cls.hooks = os.path.join(live, ".git", "ora-hooks")
        write(os.path.join(hooks, "pre-push"), "#!/bin/sh\nexit 1\n")
        git(live, "config", "core.hooksPath", hooks.replace(os.sep, "/"))
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
        out = cls.out = os.path.join(d, "wts", "out ü")
        git(live, "worktree", "add", "-q", "-b", "out-br", out, kept)
        git(live, "worktree", "lock", "--reason", "busy reason", out)
        git(live, "config", "branch.out-br.remote", "origin")
        git(live, "config", "branch.out-br.merge", "refs/heads/out-br")
        git(live, "config", "branch.old-wt.remote", "origin")                  # an OLD branch's upstream
        det = cls.det = os.path.join(d, "wts", "det")
        git(live, "worktree", "add", "-q", "--detach", det, nm)              # not the main checkout's HEAD
        cls.branch_cfg = [l.split(" ", 1) for l in git(live, "config", "--get-regexp", r"^branch\.").splitlines()]
        cls.refs_before = refs(live)
        cls.stash_before = reflog(live, "refs/stash")
        cls.stash_msgs = git(live, "log", "-g", "--format=%gs", "refs/stash", "--").splitlines()
        cls.overlap_before = run("overlap", live, S.old)
        cls.arch = os.path.join(d, "arch ü")
        cls.inv_run, cls.inv = inventory(live, os.path.join(d, "inv.json"), None, "--archive", cls.arch,
                                         "--clone-url", S.purged)
        cls.cmds, cls.undo = block(cls.inv_run.stdout, BEGIN, UNDO), block(cls.inv_run.stdout, UNDO, END)
        cls.results = [(l, sh(l)) for l in cls.cmds if not l.startswith("#")]
        cls.overlap_after = run("overlap", live, S.old)
        cls.archived_repo = os.path.join(cls.arch, "repo")

    CARRIED = ("refs/heads/kept/ü-1", "refs/heads/main", "refs/heads/newmain", "refs/heads/out-br",
               "refs/notes/commits", "refs/tags/kept-tag", "refs/tags/lt-kept")

    def test_inventory_exit_0(self):
        self.assertEqual(self.inv_run.returncode, 0, self.inv_run.stdout + self.inv_run.stderr)

    def test_printed_commands_exact(self):
        q, live, A = shlex.quote, self.live, self.arch
        arepo, g = os.path.join(A, "repo"), "git -C %s " % shlex.quote(live)
        moved = [(self.det, os.path.join(A, "worktrees", "0-det")),
                 (self.ow, os.path.join(A, "worktrees", "1-old wt")),
                 (self.out, os.path.join(A, "worktrees", "2-out ü"))]
        kept2, _old, kept1 = self.stash_before
        want = ["# 6.3 move every worktree folder and the main checkout into the archive (never delete)",
                "mkdir -p %s" % q(os.path.join(A, "worktrees"))]
        want += ["mv %s %s" % (q(s), q(t)) for s, t in moved]
        want += ["mv %s %s" % (q(live), q(arepo)),
                 "git -C %s worktree repair %s" % (q(arepo), " ".join(q(t) for _s, t in moved)),
                 "git -C %s config core.hooksPath %s" % (q(arepo), q(os.path.join(arepo, ".git", "ora-hooks"))),
                 "# 6.4 clone the purged remote, freeze its pushes, bring the kept work across",
                 "git clone --no-local --no-checkout %s %s" % (q(S.purged), q(live)),
                 g + "remote add fork https://example.invalid/fork.git",
                 g + "config --replace-all remote.origin.pushurl DISABLED-history-purge",
                 g + "config --replace-all remote.fork.pushurl DISABLED-history-purge"]
        want += [g + "fetch --no-tags --update-head-ok %s %s" % (q(arepo), q("+%s:%s" % (n, n))) for n in self.CARRIED]
        for sha, msg in ((kept1, self.stash_msgs[2]), (kept2, self.stash_msgs[0])):
            want += [g + "fetch --no-tags %s %s" % (q(arepo), sha), g + "stash store -m %s %s" % (q(msg), sha)]
        want.append(g + "checkout -f %s" % q("kept/ü-1"))
        want += [g + "config %s %s" % (q(k), q(v)) for k, v in self.branch_cfg
                 if k.split(".")[1] in ("main", "out-br")]
        want += [g + "worktree add --detach %s %s" % (q(self.det), S.new_main),
                 g + "worktree add %s out-br" % q(self.out),
                 g + "worktree lock --reason %s %s" % (q("busy reason"), q(self.out))]
        self.assertEqual(self.cmds, want)
        aside = os.path.join(A, "new-clone-aside")
        undo = ["# only before anyone works in the new clone: set it aside, move the archived folders back",
                "mkdir -p %s" % q(os.path.join(aside, "worktrees")),
                "mv %s %s" % (q(self.det), q(os.path.join(aside, "worktrees", "0-det"))),
                "mv %s %s" % (q(self.out), q(os.path.join(aside, "worktrees", "1-out ü"))),
                "mv %s %s" % (q(live), q(os.path.join(aside, "repo")))]
        undo += ["mv %s %s" % (q(t), q(s)) for s, t in moved]
        undo += ["mv %s %s" % (q(arepo), q(live)),
                 g + "worktree repair %s" % " ".join(q(s) for s, _t in moved),
                 g + "config core.hooksPath %s" % q(self.hooks.replace(os.sep, "/"))]
        self.assertEqual(self.undo, undo)

    def test_every_printed_command_exit_0(self):
        for line, res in self.results:
            self.assertEqual(res.returncode, 0, "%s\n%s%s" % (line, res.stdout, res.stderr))

    def test_overlap_zero_on_the_new_clone(self):
        self.assertEqual(self.overlap_before.returncode, 1)
        self.assertEqual(self.overlap_after.returncode, 0, self.overlap_after.stdout)

    def test_new_clone_is_a_clone_of_the_purged_remote(self):
        self.assertEqual(git(self.live, "rev-parse", "refs/remotes/origin/main"), S.new_main)
        self.assertEqual(norm(git(self.live, "config", "remote.origin.url")), norm(S.purged))

    def test_kept_refs_carried_at_the_same_sha(self):
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
        self.assertEqual(git(self.live, "symbolic-ref", "HEAD"), "refs/heads/kept/ü-1")
        self.assertEqual(git(self.live, "status", "--porcelain"), "")

    def test_kept_worktrees_recreated_at_their_paths_and_relocked(self):
        rows = {w["path"]: w for w in wt_list(self.live)}
        self.assertEqual(set(rows), {norm(self.live), norm(self.out), norm(self.det)})
        self.assertEqual(rows[norm(self.out)]["branch"], "refs/heads/out-br")
        self.assertEqual(rows[norm(self.out)]["locked"], "busy reason")
        self.assertTrue(rows[norm(self.det)]["detached"])
        self.assertEqual(rows[norm(self.det)]["head"], S.new_main)
        self.assertIsNone(rows[norm(self.det)]["locked"])
        for p in (self.out, self.det):
            self.assertEqual(git(p, "status", "--porcelain"), "", p)

    def test_branch_upstream_config_carried_old_one_not(self):
        self.assertEqual(git(self.live, "config", "branch.out-br.merge"), "refs/heads/out-br")
        self.assertEqual(git(self.live, "config", "--get-all", "branch.old-wt.remote", check=False), "")

    def test_old_branch_and_worktree_only_in_the_archive(self):
        self.assertNotIn("refs/heads/old-wt", refs(self.live))
        self.assertFalse(os.path.exists(self.ow))
        moved = find_archived(self.arch, "old wt")
        self.assertEqual(read(os.path.join(moved, "f.txt")), b"dirty old\n")
        self.assertEqual(read(os.path.join(moved, "new ü.txt")), b"untracked old\n")
        self.assertEqual(git(moved, "rev-parse", "HEAD"), S.c[2])

    def test_archived_repo_opens_with_every_ref_worktree_and_stash(self):
        self.assertEqual(refs(self.archived_repo), self.refs_before)
        self.assertEqual(reflog(self.archived_repo, "refs/stash"), self.stash_before)
        self.assertIn(S.c[1], git(self.archived_repo, "log", "--format=%H", "old-wt").split())
        rows = wt_list(self.archived_repo)
        self.assertEqual(len(rows), 4)
        for w in rows:
            self.assertTrue(w["path"].startswith(norm(self.arch) + os.sep), w["path"])
            self.assertFalse(w["prunable"], w["path"])
        self.assertEqual({w["locked"] for w in rows}, {None, "busy reason"})

    def test_archive_hooks_path_points_at_its_own_hooks(self):                   # Blast B6-01
        hp = git(self.archived_repo, "config", "core.hooksPath")
        self.assertEqual(norm(hp), norm(os.path.join(self.archived_repo, ".git", "ora-hooks")))
        self.assertTrue(os.path.isfile(os.path.join(hp, "pre-push")))
        self.assertEqual(git(self.live, "config", "--get-all", "core.hooksPath", check=False), "")

    def test_pushes_stay_frozen_in_the_new_clone_and_the_archive(self):        # R6-02
        for repo, value in ((self.live, "DISABLED-history-purge"), (self.archived_repo, "DISABLED-history-purge-x")):
            for r in ("origin", "fork"):
                self.assertEqual(git(repo, "config", "--get-all", "remote.%s.pushurl" % r), value, (repo, r))
            pushes = [l for l in git(repo, "remote", "-v").splitlines() if l.endswith("(push)")]
            self.assertEqual(len(pushes), 2)
            self.assertTrue(all("DISABLED" in l for l in pushes), pushes)
        res = subprocess.run(["git", "-C", self.live, "push", "origin", "HEAD:refs/heads/x"], capture_output=True,
                             env=ENV)
        self.assertNotEqual(res.returncode, 0)
        self.assertNotIn("refs/heads/x", refs(S.purged))


class Step6UndoTest(unittest.TestCase):
    """The printed commands, then the printed undo: the original checkout is back, identical."""

    @classmethod
    def setUpClass(cls):
        d = cls.d = fresh("undo")
        live = cls.live = S.live(os.path.join(d, "live"))
        hooks = os.path.join(live, ".git", "ora-hooks")
        write(os.path.join(hooks, "pre-push"), "#!/bin/sh\nexit 1\n")
        cls.hp = hooks.replace(os.sep, "/")
        git(live, "config", "core.hooksPath", cls.hp)
        cls.a, cls.b = os.path.join(d, "wts", "a"), os.path.join(d, "wts", "b")
        git(live, "worktree", "add", "-q", "-b", "a-br", cls.a, commit_on(live, S.new_main, "a work"))
        git(live, "worktree", "lock", "--reason", "keep me", cls.a)
        git(live, "worktree", "add", "-q", "-b", "b-br", cls.b, S.c[2])
        write(os.path.join(cls.b, "dirty.txt"), "old dirty\n")
        write(os.path.join(live, "README.md"), "kept stash\n")
        git(live, "stash", "-q")
        cls.refs, cls.wts = refs(live), wt_list(live)
        cls.stash = reflog(live, "refs/stash")
        cls.arch, _r, _inv, cls.cmds, cls.undo = step6(live, d, follow_it=False)

    def test_commands_then_undo_restore_the_original_checkout(self):
        follow(self.cmds)
        self.assertEqual(run("overlap", self.live, S.old).returncode, 0)
        follow(self.undo)
        self.assertEqual(refs(self.live), self.refs)
        self.assertEqual(wt_list(self.live), self.wts)                            # paths, HEADs, locks, none prunable
        self.assertEqual(reflog(self.live, "refs/stash"), self.stash)
        self.assertEqual(read(os.path.join(self.b, "dirty.txt")), b"old dirty\n")
        self.assertEqual(git(self.live, "config", "core.hooksPath"), self.hp)
        self.assertEqual(norm(git(self.live, "config", "remote.origin.url")), norm(S.src))   # not the new clone
        self.assertEqual(run("overlap", self.live, S.old).returncode, 1)          # the old history is back
        aside = os.path.join(self.arch, "new-clone-aside")
        self.assertEqual(git(os.path.join(aside, "repo"), "rev-parse", "refs/remotes/origin/main"), S.new_main)
        self.assertEqual(sorted(os.listdir(os.path.join(aside, "worktrees"))), ["0-a"])
        self.assertEqual(os.listdir(os.path.join(self.arch, "worktrees")), [])


class Step6LayoutTest(unittest.TestCase):
    """Each layout inventory accepts, followed through the printed commands."""

    def follow_layout(self, name, build):
        d = fresh(name)
        live = S.live(os.path.join(d, "live"))
        info = build(live, d)
        arch, r, inv, cmds, _undo = step6(live, d)
        self.assertEqual(run("overlap", live, S.old).returncode, 0)
        self.assertEqual(git(live, "status", "--porcelain"), "")
        return live, arch, info, r, inv, cmds

    def test_old_main_checkout_with_kept_local_main_ahead(self):                # R4-01, T019
        def build(live, d):
            write(os.path.join(live, "local.txt"), "local kept work\n")
            git(live, "add", "-A")
            git(live, "commit", "-q", "-m", "local kept")
            kept = git(live, "rev-parse", "main")
            git(live, "checkout", "-q", "old-feature")
            git(live, "update-ref", "refs/worktree/mark", S.new_main)           # the OLD main's own ref
            return kept
        live, arch, kept, _r, inv, cmds = self.follow_layout("old-main-ahead", build)
        self.assertEqual(git(live, "rev-parse", "refs/heads/main"), kept)
        self.assertEqual(git(live, "rev-parse", "HEAD"), kept)
        self.assertEqual(git(live, "symbolic-ref", "-q", "HEAD", check=False), "")
        self.assertEqual(read(os.path.join(live, "local.txt")), b"local kept work\n")
        self.assertFalse([c for c in cmds if "refs/worktree" in c], cmds)
        self.assertEqual(git(live, "for-each-ref", "refs/worktree"), "")
        self.assertEqual(git(os.path.join(arch, "repo"), "rev-parse", "refs/worktree/mark"), S.new_main)

    def test_detached_main_at_a_local_commit_a_branch_reaches(self):           # R4-04
        def build(live, d):
            git(live, "checkout", "-q", "--detach")
            write(os.path.join(live, "w.txt"), "detached work\n")
            git(live, "add", "-A")
            git(live, "commit", "-q", "-m", "detached work")
            git(live, "branch", "saved")
            return git(live, "rev-parse", "HEAD")
        live, _arch, head, _r, _inv, _c = self.follow_layout("detached-main", build)
        self.assertEqual(git(live, "rev-parse", "HEAD"), head)
        self.assertEqual(git(live, "symbolic-ref", "-q", "HEAD", check=False), "")

    def test_worktree_detached_at_an_ancestor_of_a_carried_branch(self):       # T013
        def build(live, d):
            wt = os.path.join(d, "wt-mid")
            git(live, "worktree", "add", "-q", "--detach", wt, S.new_main + "~1")
            return wt
        live, _arch, wt, _r, _inv, _c = self.follow_layout("detached-ancestor", build)
        rows = {w["path"]: w for w in wt_list(live)}
        self.assertEqual(rows[norm(wt)]["head"], git(S.purged, "rev-parse", "main~1"))
        self.assertTrue(rows[norm(wt)]["detached"])

    def test_old_main_checkout_and_a_kept_worktree_on_main(self):              # R4-04
        def build(live, d):
            git(live, "checkout", "-q", "old-feature")
            wt = os.path.join(d, "wt-main")
            git(live, "worktree", "add", "-q", wt, "main")
            return wt
        live, _arch, wt, _r, _inv, _c = self.follow_layout("old-main-wt-main", build)
        rows = {w["path"]: w for w in wt_list(live)}
        self.assertEqual(rows[norm(wt)]["branch"], "refs/heads/main")
        self.assertTrue(rows[norm(live)]["detached"])

    def test_per_worktree_ref_of_an_old_worktree_stays_in_the_archive(self):  # R4-04 (E)
        def build(live, d):
            wt = os.path.join(d, "wt-old")
            git(live, "worktree", "add", "-q", wt, "old-feature")
            git(wt, "update-ref", "refs/worktree/mark", S.new_main)
        live, arch, _i, _r, inv, _c = self.follow_layout("perwt-old", build)
        self.assertNotIn("refs/worktree/mark", {r["name"] for r in inv["refs"]})
        self.assertEqual(git(live, "for-each-ref", "refs/worktree"), "")
        self.assertEqual(git(find_archived(arch, "wt-old"), "rev-parse", "refs/worktree/mark"), S.new_main)

    def test_purged_remote_on_a_local_path_with_old_objects_left_unreachable(self):   # e2e finding (round 7)
        d = fresh("local-remote")
        remote = os.path.join(d, "remote.git")
        subprocess.run(["git", "clone", "-q", "--mirror", "--no-local", S.purged, remote], check=True, env=ENV)
        git(remote, "fetch", "-q", S.backup, "+refs/heads/*:refs/old/*")
        for ref in git(remote, "for-each-ref", "--format=%(refname)", "refs/old").split():
            git(remote, "update-ref", "-d", ref)                                # old objects stay, unreachable
        self.assertTrue(exists(remote, S.c[1]))
        live = S.live(os.path.join(d, "live"))
        step6(live, d, url=remote)
        self.assertEqual(run("overlap", live, S.old).returncode, 0)

    def test_duplicate_stash_shas_all_stored(self):                           # R4-12 (F5)
        def build(live, d):
            write(os.path.join(live, "README.md"), "x\n")
            git(live, "stash", "-q")
            first = git(live, "rev-parse", "refs/stash")
            write(os.path.join(live, "README.md"), "y\n")
            git(live, "stash", "-q")
            git(live, "stash", "store", "-q", "-m", "dup", first)               # the same SHA twice
            return reflog(live, "refs/stash")
        live, _arch, before, _r, _inv, _c = self.follow_layout("dup-sha", build)
        self.assertEqual(reflog(live, "refs/stash"), before)

    def test_linked_worktrees_with_the_same_folder_name(self):                 # R4-12 (T16)
        def build(live, d):
            for i in (1, 2):
                git(live, "worktree", "add", "-q", "-b", "app%d" % i, os.path.join(d, "wts%d" % i, "app"), S.new_main)
        _live, arch, _i, _r, _inv, _c = self.follow_layout("same-name", build)
        self.assertEqual(sorted(os.listdir(os.path.join(arch, "worktrees"))), ["0-app", "1-app"])

    def test_ignored_paths_named_exactly_and_left_in_the_archive(self):       # R4-03, R5-01
        def build(live, d):
            write(os.path.join(live, ".claude", "keep.txt"), "tracked\n")
            write(os.path.join(live, "tools", "t.py"), "tracked\n")
            git(live, "add", "-A")
            git(live, "commit", "-q", "-m", "tracked folders")
            write(os.path.join(live, ".git", "info", "exclude"), "_staging/\n__pycache__/\n*.local.json\n")
            write(os.path.join(live, "_staging", "PENDING_REIMPORT.md"), "# pending\n")
            write(os.path.join(live, "debug.log"), "x\n")                       # *.log is ignored
            write(os.path.join(live, ".claude", "prefs.local.json"), "{}\n")
            write(os.path.join(live, "tools", "__pycache__", "t.pyc"), "x\n")
            write(os.path.join(live, "tools", "real-identifiers.local.json"), "{}\n")
            wt = os.path.join(d, "wt")
            git(live, "worktree", "add", "-q", "-b", "wt-br", wt, "main")
            write(os.path.join(wt, "notes.local.json"), "{}\n")
            return wt
        live, arch, wt, r, inv, _c = self.follow_layout("ignored", build)
        ign = {norm(w["path"]): w["ignored"] for w in inv["worktrees"]}
        main_ign = [".claude/prefs.local.json", "_staging/", "debug.log", "tools/__pycache__/",
                    "tools/real-identifiers.local.json"]
        self.assertEqual(ign[norm(live)], main_ign)                              # never collapsed to `tools/`
        self.assertEqual(ign[norm(wt)], ["notes.local.json"])
        self.assertIn("        ignored, NOT carried (stays in the archive): " + ", ".join(main_ign),
                      r.stdout.splitlines())
        self.assertFalse(os.path.exists(os.path.join(live, "_staging")))
        self.assertTrue(os.path.isfile(os.path.join(arch, "repo", "_staging", "PENDING_REIMPORT.md")))
        self.assertTrue(os.path.isfile(os.path.join(live, "tools", "t.py")))

    def test_ignored_folder_holding_a_worktree_never_listed(self):            # R5-01 (Blast F1), E01
        d = fresh("ignored-holds-wt")
        live = S.live(os.path.join(d, "live"))
        write(os.path.join(live, ".git", "info", "exclude"), ".claude/worktrees/\n*.local.json\n")
        write(os.path.join(live, ".claude", "prefs.local.json"), "{}\n")
        git(live, "worktree", "add", "-q", "-b", "wt1", os.path.join(live, ".claude", "worktrees", "wt1"),
            S.new_main)
        r, inv = inventory(live, os.path.join(d, "inv.json"))
        self.assertEqual(r.returncode, 2, r.stdout)                              # the nested worktree is refused
        main = [w for w in inv["worktrees"] if w["main"]][0]
        self.assertEqual(main["ignored"], [".claude/prefs.local.json"])

    def test_kept_submodule_deinit_then_init_after_step_6(self):
        def build(live, d):
            k = os.path.join(d, "k")
            git(live, "worktree", "add", "-q", "-b", "k-br", k, S.new_main)
            add_submodule(k)
            git(k, "submodule", "deinit", "-q", "-f", "sub")                    # the printed fix
            return k
        _live, _arch, k, _r, _inv, _c = self.follow_layout("submodule-after", build)
        git(k, "submodule", "update", "-q", "--init")                           # the step after Step 6
        self.assertEqual(read(os.path.join(k, "sub", "l.txt")), b"lib\n")

    def test_stash_entry_holding_a_purged_blob_stays_in_the_archive(self):
        def build(live, d):
            write(os.path.join(live, "f.txt"), "secret v1\n")                   # the very blob the purge dropped
            git(live, "add", "f.txt")
            git(live, "stash", "-q")
        live, arch, _i, _r, inv, _c = self.follow_layout("stash-purged-blob", build)
        self.assertEqual([e["old"] for e in inv["stash"]], [True])
        self.assertEqual(git(live, "stash", "list"), "")
        self.assertEqual(len(reflog(os.path.join(arch, "repo"), "refs/stash")), 1)


class Step6KeepsEverythingTest(unittest.TestCase):
    """Data that in-place cleanup lost in rounds 1-3 is still in the archive after the procedure."""

    def test_round_3_cases_stay_in_the_archive(self):
        d = fresh("keeps")
        c, nm = S.c, S.new_main
        live = S.live(os.path.join(d, "live"))
        sm = os.path.join(d, "wts", "sm")                                   # R3-02: old worktree, submodule
        git(live, "worktree", "add", "-q", "-b", "sm-br", sm, c[2])
        sub_commit = unpushed_submodule_commit(add_submodule(sm))
        write(os.path.join(live, "README.md"), "kept stash\n")              # R3-01: stash entries
        git(live, "stash", "-q")
        write(os.path.join(sm, "f.txt"), "another session's stash\n")
        git(sm, "stash", "-q")
        stash_before = reflog(live, "refs/stash")
        write(os.path.join(live, "README.md"), "to drop\n")                 # R3-03: a dropped stash
        git(live, "stash", "-q")
        dropped = git(live, "rev-parse", "refs/stash")
        git(live, "stash", "drop", "-q")
        r = commit_on(live, nm, "reflog only")                               # a reflog-only commit
        git(live, "update-ref", "-m", "away", "refs/heads/main", r)
        git(live, "update-ref", "-m", "back", "refs/heads/main", nm)
        bw = os.path.join(d, "wts", "bw")                                    # refs/bisect, refs/worktree
        git(live, "worktree", "add", "-q", "--detach", bw, c[1])
        git(bw, "update-ref", "refs/bisect/bad", c[1])
        git(bw, "update-ref", "refs/worktree/x", c[2])
        arch, _r, _inv, _cmds, _u = step6(live, d)
        repo = os.path.join(arch, "repo")
        self.assertEqual(run("overlap", live, S.old).returncode, 0)
        self.assertEqual(reflog(repo, "refs/stash"), stash_before)
        self.assertTrue(exists(repo, dropped))
        self.assertIn(r, reflog(repo, "refs/heads/main"))
        archived_bw = find_archived(arch, "bw")
        self.assertEqual(git(archived_bw, "rev-parse", "refs/bisect/bad"), c[1])
        self.assertEqual(git(archived_bw, "rev-parse", "refs/worktree/x"), c[2])
        modules = os.path.join(repo, ".git", "worktrees", "sm", "modules", "sub")   # its repository moved whole
        found = subprocess.run(["git", "--git-dir", modules, "--work-tree", modules, "cat-file", "-e", sub_commit],
                               env=ENV, capture_output=True)                    # its core.worktree is relative
        self.assertEqual(found.returncode, 0, found.stderr)


class Step6InputTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = cls.d = fresh("step6-input")
        cls.live = S.live(os.path.join(d, "live"))
        cls.wt = os.path.join(d, "wt")
        git(cls.live, "worktree", "add", "-q", "--detach", cls.wt, S.new_main)

    def inv(self, *extra):
        return run("inventory", self.live, S.old, "--out", os.path.join(self.d, "inv-x.json"), *extra)

    def assert_refused(self, r, text):
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("REFUSED: " + text, r.stdout.splitlines())
        self.assertNotIn(BEGIN, r.stdout)

    def test_without_archive_no_commands_printed(self):
        r = self.inv()
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertNotIn(BEGIN, r.stdout)
        self.assertIn("pass --archive <B>/rehome-<n> to print the Step 6 commands", r.stdout.splitlines())

    def test_existing_archive_dir_refused(self):
        arch = os.path.join(self.d, "exists")
        os.makedirs(arch)
        self.assert_refused(self.inv("--archive", arch, "--clone-url", S.purged),
                            "archive dir exists (never reused): %s" % arch)

    def test_archive_inside_the_repo_or_a_worktree_refused(self):
        for base in (self.live, self.wt):
            self.assert_refused(self.inv("--archive", os.path.join(base, "arch"), "--clone-url", S.purged),
                                "the archive dir is inside %s; put it outside every checkout" % base)

    def test_clone_url_naming_the_checkout_refused(self):
        self.assert_refused(self.inv("--archive", os.path.join(self.d, "a1"), "--clone-url", self.live),
                            "the clone URL is this checkout: clone the purged remote, never the old copy")

    def test_clone_url_defaults_to_origin_and_refused_without_one(self):
        r = self.inv("--archive", os.path.join(self.d, "a2"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("git clone --no-local --no-checkout %s %s" % (shlex.quote(S.src), shlex.quote(self.live)),
                      r.stdout.splitlines())
        d = fresh("no-origin")
        live = S.live(os.path.join(d, "live"))
        git(live, "remote", "remove", "origin")
        r = run("inventory", live, S.old, "--out", os.path.join(d, "inv.json"), "--archive", os.path.join(d, "a"))
        self.assert_refused(r, "no remote.origin.url: pass --clone-url <the purged remote>")

    def test_relative_paths_resolved_against_the_working_directory(self):     # G1-18
        r = run("inventory", "live", S.old, "--out", "inv-rel.json", "--archive", "arch-rel", "--clone-url",
                S.purged, cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("mv %s %s" % (shlex.quote(self.live), shlex.quote(os.path.join(self.d, "arch-rel", "repo"))),
                      r.stdout.splitlines())

    def test_help_names_every_option_the_skill_uses(self):
        r = run("inventory", "--help")
        for opt in ("--out", "--archive", "--clone-url"):
            self.assertIn(opt, r.stdout)
        top = run("--help").stdout
        self.assertIn("{changed,inventory,overlap}", top)


# ==================================================================== SKILL.md freeze / unfreeze recipe

def skill_blocks():
    """The ```bash blocks of SKILL.md."""
    with open(SKILL_MD, encoding="utf-8") as fh:
        return re.findall(r"```bash\n(.*?)```", fh.read(), re.S)


class FreezeRecipeTest(unittest.TestCase):
    """R6-02: SKILL.md Step 0 freeze and Step 6 unfreeze, run as written, on a plain remote, one with one
    custom pushurl and one with two pushurls."""

    def test_freeze_then_unfreeze_on_three_remote_shapes(self):
        freeze = [b for b in skill_blocks() if "pushurls-before.txt" in b and "--replace-all" in b]
        unfreeze = [b for b in skill_blocks() if "pushurls-before.txt" in b and "--unset-all" in b]
        self.assertEqual((len(freeze), len(unfreeze)), (1, 1), skill_blocks())
        d = fresh("freeze")
        B = d.replace(os.sep, "/")
        ups = {}
        for n in ("up", "a2", "b2", "c2"):
            ups[n] = os.path.join(d, n + ".git")
            subprocess.run(["git", "init", "-q", "--bare", ups[n]], check=True, env=ENV)
        live = os.path.join(d, "live")
        subprocess.run(["git", "init", "-q", "-b", "main", live], check=True, env=ENV)
        git(live, "commit", "-q", "--allow-empty", "-m", "init")
        git(live, "remote", "add", "a", ups["up"])                               # plain
        git(live, "remote", "add", "b", ups["up"])                               # one custom pushurl
        git(live, "config", "remote.b.pushurl", ups["a2"])
        git(live, "remote", "add", "c", ups["up"])                               # two pushurls
        git(live, "config", "--add", "remote.c.pushurl", ups["b2"])
        git(live, "config", "--add", "remote.c.pushurl", ups["c2"])
        before = git(live, "config", "--get-regexp", r"^remote\..*\.pushurl$")
        check = [l.strip() for l in freeze[0].splitlines() if "grep -v DISABLED" in l]
        self.assertEqual(len(check), 1, freeze[0])
        res = sh(check[0], cwd=live)                                            # before the freeze: all live
        self.assertNotIn("every push URL is frozen", res.stdout)
        self.assertEqual(len([l for l in res.stdout.splitlines() if l.endswith("(push)")]), 4, res.stdout)
        res = sh(freeze[0].replace("<B>", B).replace("<date>", "2026-11-27"), cwd=live)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(res.stdout.strip().splitlines()[-1], "every push URL is frozen", res.stdout)
        pushes = [l for l in git(live, "remote", "-v").splitlines() if l.endswith("(push)")]
        self.assertEqual(len(pushes), 3, pushes)
        self.assertTrue(all("DISABLED-history-purge-2026-11-27" in l for l in pushes), pushes)
        for r in ("a", "b", "c"):
            self.assertNotEqual(subprocess.run(["git", "-C", live, "push", "-q", r, "main"], capture_output=True,
                                               env=ENV).returncode, 0, r)
        for n in ups:
            self.assertEqual(git(ups[n], "for-each-ref"), "", n)                 # nothing landed anywhere
        res = sh(unfreeze[0].replace("<B>", B), cwd=live)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(git(live, "config", "--get-regexp", r"^remote\..*\.pushurl$"), before)
        for r in ("a", "b", "c"):
            self.assertEqual(subprocess.run(["git", "-C", live, "push", "-q", r, "main"], capture_output=True,
                                            env=ENV).returncode, 0, r)
        landed = {n for n in ups if git(ups[n], "for-each-ref")}
        self.assertEqual(landed, {"up", "a2", "b2", "c2"})


class UnitTest(unittest.TestCase):
    def test_index_only_status_codes(self):
        mod = load_module()
        self.assertTrue(all(mod.index_only(x) for x in ("MM", "AM", "RM", "MD", "AD")))
        self.assertFalse(any(mod.index_only(x) for x in (" M", "M ", "A ", "??", " D")))


if __name__ == "__main__":
    unittest.main()
