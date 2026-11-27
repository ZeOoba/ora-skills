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

v2.4.1 (round-8 fixes): the scripts run WITHOUT -X utf8 (a pipe, as SKILL.md runs them). The first 6.3 line
re-checks a digest of worktrees, refs, stash entries and uncommitted files (`check-unchanged`). The undo is
printed per stage: Undo A (stopped in 6.3) moves back only folders that are in the archive and absent from
their place; Undo B (git clone ran) first confirms the new clone by its pushurl marker and `check-new-clone`.
Each stop point is followed by its undo and the checkout is compared byte for byte.
"""
import hashlib
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
BEGIN, END = "# --- Step 6 commands (printed, not run) ---", "# --- end ---"
UNDO_A = "# --- Undo A: you stopped in 6.3 (git clone has not run) ---"
UNDO_B = "# --- Undo B: git clone has run (6.4 started); only before anyone works in the new clone ---"
MARK = "DISABLED-history-purge-new-clone"                   # the new clone's pushurl, set by its git clone line
PY = "%s -I %s" % (shlex.quote(sys.executable), shlex.quote(SCRIPT))
MSG_A = "Undo A refused: git clone has run (the archive and the checkout path both exist); run Undo B"
MSG_B1 = "Undo B refused: the archived checkout is missing"
MSG_B2 = "Undo B refused: the checkout path is not the new clone (remote.origin.pushurl is not %s)" % MARK


def git(repo, *args, check=True):
    return subprocess.run(["git", "-C", repo, "-c", "core.autocrlf=false", "-c", "protocol.file.allow=always",
                           "-c", "core.quotepath=false"]
                          + list(args), capture_output=True, encoding="utf-8", errors="surrogateescape",
                          check=check, env=ENV).stdout.strip()


def run(*args, cwd=None):
    """The script as SKILL.md runs it: python -I, no -X utf8, stdout a pipe; its output must be strict UTF-8."""
    return subprocess.run([sys.executable, "-I", SCRIPT] + list(args), capture_output=True,
                          encoding="utf-8", errors="strict", env=ENV, cwd=cwd)


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
    """inventory --archive <d>/arch --clone-url <purged>, then follow the printed Step 6 commands.
    undo = {"A": Undo A lines, "B": Undo B lines}."""
    arch = os.path.join(d, "arch")
    r, inv = inventory(live, os.path.join(d, "inv.json"), None, "--archive", arch, "--clone-url", url or S.purged)
    if r.returncode != 0:
        raise AssertionError("inventory exit %d\n%s%s" % (r.returncode, r.stdout, r.stderr))
    cmds = block(r.stdout, BEGIN, UNDO_A)
    undo = {"A": block(r.stdout, UNDO_A, UNDO_B), "B": block(r.stdout, UNDO_B, END)}
    if follow_it:
        follow(cmds)
    return arch, r, inv, cmds, undo


def snapshot(roots):
    """{(root index, relative path): sha256 of the bytes, or 'dir'} for every file and folder under each root."""
    snap = {}
    for i, root in enumerate(roots):
        for dirpath, _dirs, files in os.walk(root):
            rel = os.path.relpath(dirpath, root)
            snap[(i, rel)] = "dir"
            for f in files:
                snap[(i, os.path.join(rel, f))] = hashlib.sha256(read(os.path.join(dirpath, f))).hexdigest()
    return snap


def snapshot_diff(a, b):
    return sorted(k for k in set(a) | set(b) if a.get(k) != b.get(k))[:10]


def run_fix(cmd, cwd, **subst):
    """Run one printed fix command with its <placeholders> filled in; a destructive command is never run."""
    for k, v in subst.items():
        cmd = cmd.replace("<%s>" % k, v)
    assert not re.match(r"\s*(rm|del|rmdir)\b", cmd) and "reset --hard" not in cmd, "destructive fix: " + cmd
    return sh(cmd, cwd=cwd)


def find_archived(arch, marker):
    """The archived worktree folder under <arch>/worktrees whose name ends with marker."""
    base = os.path.join(arch, "worktrees")
    hits = [os.path.join(base, n) for n in os.listdir(base) if n.endswith(marker)]
    assert len(hits) == 1, (marker, os.listdir(base))
    return hits[0]


def printed_fix(stdout, path, word=""):
    """The backticked commands of the (first) REFUSED line for path whose problem holds word, in order."""
    for line in stdout.splitlines():
        if line.startswith("REFUSED %s: " % path) and word in line.split(" -> ", 1)[0]:
            return re.findall(r"`([^`]+)`", line.split(" -> ", 1)[1])
    raise AssertionError("no REFUSED line for %s (%s):\n%s" % (path, word, stdout))


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
        cls.ra = run("inventory", live, S.old, "--out", os.path.join(d, "inv-a.json"), "--archive",
                     os.path.join(d, "arch"), "--clone-url", S.purged)
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

    def test_refused_with_archive_prints_no_step_6_command(self):              # N24
        self.assertEqual(self.ra.returncode, 2, self.ra.stdout)
        self.assertIn("REFUSED", self.ra.stdout)
        for marker in (BEGIN, UNDO_A, UNDO_B, END, "check-unchanged", "git clone", "mv "):
            self.assertNotIn(marker, self.ra.stdout)

    def test_unchanged_skip_worktree_file_not_refused(self):                   # N43
        d = fresh("skip-unchanged")
        live = S.live(os.path.join(d, "live"))
        git(live, "update-index", "--skip-worktree", "g.txt")
        git(live, "update-index", "--assume-unchanged", "README.md")
        r, inv = inventory(live, os.path.join(d, "inv.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertEqual(inv["refusals"], [])

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

        B = os.path.join(d, "B")                                                # verify.git = the purged
        subprocess.run(["git", "clone", "-q", "--bare", S.purged, os.path.join(B, "verify.git")], check=True, env=ENV)
        subprocess.run(["git", "clone", "-q", "--mirror", S.backup, os.path.join(B, "mirror.git")], check=True,
                       env=ENV)                                                 # the backup sits next to it

        def recipe():                                                           # SKILL.md Step 6 item 0b, literally
            with open(SKILL_MD, encoding="utf-8") as fh:
                item = [l for l in fh.read().splitlines() if l.startswith("0b. ")][0]
            steps = [c for c in re.findall(r"`([^`]+)`", item) if "<branch>" in c]
            self.assertEqual(len(steps), 3, steps)
            script = "\n".join(c.replace("<branch>", "old-feature").replace("<B>", B.replace(os.sep, "/"))
                               for c in steps)
            res = sh(script, cwd=live)
            self.assertEqual(res.returncode, 0, script + res.stdout + res.stderr)
        refs_ = self.refused_then_fixed(d, live, "SKILL.md Step 6 item 0b", recipe, "purged")
        self.assertTrue(refs_["refs/heads/old-feature"]["carry"])
        self.assertEqual(refs_["refs/heads/old-feature"]["sha"], git(S.purged, "rev-parse", "refs/heads/old-feature"))
        self.assertIn(wrong, reflog(live, "refs/heads/old-feature"))           # the pinned old tip, in the reflog


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

    def test_long_sha_line_refused(self):                                       # N73
        for n, extra in ((41, "a" * 41), (64, "b" * 63 + "z"), (65, "c" * 65)):
            bad = os.path.join(self.d, "long%d.txt" % n)
            write(bad, read(S.old).decode() + extra + "\n")
            r, _ = inventory(self.live, os.path.join(self.d, "inv-long.json"), bad)
            self.assertEqual(r.returncode, 2, (n, r.stdout))
            self.assertIn("1 malformed line(s)", r.stdout)
        ok = os.path.join(self.d, "sha256.txt")                                 # a SHA-256 line is well formed
        write(ok, read(S.old).decode() + "d" * 64 + "\n")
        r, _ = inventory(self.live, os.path.join(self.d, "inv-256.json"), ok)
        self.assertEqual(r.returncode, 0, r.stdout)

    def test_relative_origin_url_resolved_against_the_checkout(self):          # R7-06 (correctness F4)
        d = fresh("rel-origin")
        live = S.live(os.path.join(d, "deep", "er", "live"))
        rel = os.path.relpath(S.purged, live).replace(os.sep, "/")
        git(live, "remote", "set-url", "origin", rel)
        arch = os.path.join(d, "arch")
        r = run("inventory", live, S.old, "--out", os.path.join(d, "inv.json"), "--archive", arch, cwd=d)
        self.assertEqual(r.returncode, 0, r.stdout)
        clone = [l for l in block(r.stdout, BEGIN, UNDO_A) if l.startswith("git clone")]
        self.assertEqual(clone, ["git clone --no-local --no-checkout --config remote.origin.pushurl=%s %s %s"
                                 % (MARK, shlex.quote(os.path.normpath(S.purged)), shlex.quote(live))])
        follow(block(r.stdout, BEGIN, UNDO_A))
        self.assertEqual(git(live, "rev-parse", "main"), S.new_main)

    def test_relative_clone_url_resolved_against_the_working_directory(self):  # R7-06, N25
        d = fresh("rel-clone-url")
        live = S.live(os.path.join(d, "live"))
        rel = os.path.relpath(S.purged, d)
        r = run("inventory", live, S.old, "--out", os.path.join(d, "inv.json"), "--archive",
                os.path.join(d, "arch"), "--clone-url", rel, cwd=d)
        self.assertEqual(r.returncode, 0, r.stdout)
        cmds = block(r.stdout, BEGIN, UNDO_A)
        self.assertIn(shlex.quote(os.path.normpath(S.purged)), [l for l in cmds if l.startswith("git clone")][0])
        follow(cmds)                                                            # run from the test's own folder
        self.assertEqual(git(live, "rev-parse", "main"), S.new_main)

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
        self.assertEqual(fix, ["git update-index --no-skip-worktree <file>",
                               "git update-index --no-assume-unchanged <file>", "git stash"])
        for f in ("g.txt", "README.md"):
            for cmd in fix[:2]:
                res = run_fix(cmd, live, file=f)
                self.assertEqual(res.returncode, 0, cmd + res.stderr)
        self.assertEqual(run_fix(fix[2], live).returncode, 0)                  # the printed `git stash`
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

    # ---- R7-07 (N34-N38, N41): every printed fix is run as printed, then inventory passes
    def fixed_by_printed(self, name, build, word, apply):
        """build(live, d) -> path of the refused worktree; apply(fix, path, live) runs the printed fix."""
        d = fresh(name)
        live = S.live(os.path.join(d, "live"))
        path = build(live, d)
        r, _inv = inventory(live, os.path.join(d, "inv1.json"))
        self.assertEqual(r.returncode, 2, r.stdout)
        fix = printed_fix(r.stdout, path, word)
        self.assertTrue(fix, "no command printed for %s" % word)
        apply(fix, path, live)
        r, inv = inventory(live, os.path.join(d, "inv2.json"))
        self.assertEqual(r.returncode, 0, r.stdout)
        return live, inv

    def ok(self, res):
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_missing_worktree_folder_then_printed_prune(self):                 # N34
        def build(live, d):
            wt = os.path.join(d, "gone")
            git(live, "worktree", "add", "-q", "--detach", wt, S.new_main)
            os.rename(wt, wt + "-moved")
            return wt
        self.fixed_by_printed("fix-missing", build, "missing",
                              lambda fix, wt, live: [self.ok(run_fix(c, live)) for c in fix])

    def test_bisect_in_progress_then_printed_reset(self):                      # N35
        def build(live, d):
            wt = os.path.join(d, "bi")
            git(live, "worktree", "add", "-q", "--detach", wt, S.new_main)
            git(wt, "bisect", "start")
            return wt

        def apply(fix, wt, live):
            self.assertIn("git bisect reset", fix)
            self.ok(run_fix("git bisect reset", wt))
        self.fixed_by_printed("fix-bisect", build, "in progress", apply)

    def test_rebase_in_progress_refused_then_printed_abort(self):              # N41, N35
        def build(live, d):
            wt = os.path.join(d, "rb")
            git(live, "worktree", "add", "-q", "-b", "rb-br", wt, S.new_main)
            write(os.path.join(wt, "README.md"), "mine\n")
            git(wt, "commit", "-q", "-am", "mine")
            other = os.path.join(d, "other")                                    # a commit that edits README too
            git(live, "worktree", "add", "-q", "-b", "edit-br", other, S.new_main)
            write(os.path.join(other, "README.md"), "theirs\n")
            git(other, "commit", "-q", "-am", "theirs")
            res = subprocess.run(["git", "-C", wt, "rebase", "edit-br"], capture_output=True, env=ENV)
            self.assertNotEqual(res.returncode, 0)                              # stopped on the conflict
            self.assertTrue(os.path.isdir(git(wt, "rev-parse", "--path-format=absolute", "--git-path",
                                              "rebase-merge")))
            return wt

        def apply(fix, wt, live):
            self.assertIn("git <op> --abort", fix)
            self.ok(run_fix("git <op> --abort", wt, op="rebase"))
        self.fixed_by_printed("fix-rebase", build, "in progress", apply)

    def test_kept_submodule_then_printed_deinit(self):                         # N36
        def build(live, d):
            k = os.path.join(d, "k")
            git(live, "worktree", "add", "-q", "-b", "k-br", k, S.new_main)
            add_submodule(k)
            return k

        def apply(fix, k, live):
            self.assertIn("git submodule deinit <sub>", fix)
            sub = os.path.join(k, "sub")
            write(os.path.join(sub, "l.txt"), "uncommitted lib edit\n")      # the printed deinit refuses it
            self.assertNotEqual(run_fix("git submodule deinit <sub>", k, sub="sub").returncode, 0)
            self.assertEqual(read(os.path.join(sub, "l.txt")), b"uncommitted lib edit\n")
            git(sub, "checkout", "-q", "--", "l.txt")                           # the change dropped, as printed
            for c in fix:
                if "deinit" in c:
                    self.ok(run_fix(c, k, sub="sub"))
        _live, _inv = self.fixed_by_printed("fix-sub", build, "submodule", apply)

    def test_modified_and_untracked_then_printed_stash(self):                  # N38
        def build(live, d):
            wt = os.path.join(d, "m")
            git(live, "worktree", "add", "-q", "-b", "m-br", wt, S.new_main)
            write(os.path.join(wt, "README.md"), "edited\n")
            return wt

        def apply(fix, wt, live):
            self.assertEqual(fix, ["git stash"])
            self.ok(run_fix(fix[0], wt))
        live, _inv = self.fixed_by_printed("fix-mod", build, "modified", apply)
        self.assertIn(b"edited", subprocess.run(["git", "-C", live, "show", "stash@{0}:README.md"],
                                                capture_output=True, env=ENV).stdout)

        def build_u(live, d):
            wt = os.path.join(d, "u")
            git(live, "worktree", "add", "-q", "-b", "u-br", wt, S.new_main)
            write(os.path.join(wt, "new.txt"), "untracked\n")
            return wt

        def apply_u(fix, wt, live):
            self.assertIn("git stash -u", fix)
            self.ok(run_fix("git stash -u", wt))
        self.fixed_by_printed("fix-untr", build_u, "untracked", apply_u)

    def test_per_worktree_hooks_path_refused_then_printed_unset(self):          # R7-05 (Blast B7-01)
        d = fresh("fix-wt-hooks")
        live = S.live(os.path.join(d, "live"))
        hooks = os.path.join(live, ".git", "ora-hooks")
        write(os.path.join(hooks, "pre-push"), "#!/bin/sh\nexit 1\n")
        git(live, "config", "core.hooksPath", hooks.replace(os.sep, "/"))
        git(live, "config", "extensions.worktreeConfig", "true")
        kw, ow = os.path.join(d, "kw"), os.path.join(d, "ow")
        git(live, "worktree", "add", "-q", "-b", "kw-br", kw, S.new_main)
        git(live, "worktree", "add", "-q", "-b", "ow-br", ow, S.c[2])          # OLD: archived, still runs hooks
        nk = os.path.join(d, "nk")
        git(live, "worktree", "add", "-q", "--detach", nk, S.new_main)          # no override: not refused
        for wt in (kw, ow, live):
            git(wt, "config", "--worktree", "core.hooksPath", hooks.replace(os.sep, "/"))
        r, inv = inventory(live, os.path.join(d, "inv1.json"))
        self.assertEqual(r.returncode, 2, r.stdout)
        self.assertEqual(sorted(norm(x["path"]) for x in inv["refusals"]), sorted(norm(p) for p in (kw, ow, live)))
        for wt in (kw, ow, live):
            fix = printed_fix(r.stdout, wt, "per-worktree core.hooksPath")
            self.assertEqual(fix, ["git config --worktree --unset core.hooksPath"])
            self.ok(run_fix(fix[0], wt))
        arch, _r, _inv, _cmds, _u = step6(live, d)
        for name in ("kw", "ow", "nk"):
            archived = find_archived(arch, name)
            got = git(archived, "rev-parse", "--path-format=absolute", "--git-path", "hooks")
            self.assertEqual(norm(got), norm(os.path.join(arch, "repo", ".git", "ora-hooks")), name)


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
        cls.cmds = block(cls.inv_run.stdout, BEGIN, UNDO_A)
        cls.undo = {"A": block(cls.inv_run.stdout, UNDO_A, UNDO_B), "B": block(cls.inv_run.stdout, UNDO_B, END)}
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
                "%s check-unchanged %s %s" % (PY, q(live), self.inv["digest"]),
                "mkdir -p %s" % q(os.path.join(A, "worktrees"))]
        want += ["mv %s %s" % (q(s), q(t)) for s, t in moved]
        want += ["mv %s %s" % (q(live), q(arepo)),
                 "git -C %s worktree repair %s" % (q(arepo), " ".join(q(t) for _s, t in moved)),
                 "git -C %s config core.hooksPath %s" % (q(arepo), q(os.path.join(arepo, ".git", "ora-hooks"))),
                 "# 6.4 clone the purged remote, freeze its pushes, bring the kept work across",
                 "git clone --no-local --no-checkout --config remote.origin.pushurl=%s %s %s"
                 % (MARK, q(S.purged), q(live)),
                 g + "remote add fork https://example.invalid/fork.git",
                 g + "config --replace-all remote.origin.pushurl " + MARK,
                 g + "config --replace-all remote.fork.pushurl " + MARK]
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
        back = ["if [ -e %s ] && [ ! -e %s ]; then mv %s %s; fi" % (q(t), q(s), q(t), q(s))
                for s, t in [(live, arepo)] + moved]
        back += [g + "worktree repair %s" % " ".join(q(s) for s, _t in moved),
                 g + "config core.hooksPath %s" % q(self.hooks.replace(os.sep, "/"))]
        undo_a = ["# moves back only a folder that is in the archive and absent from its original place",
                  "if [ -e %s ] && [ -e %s ]; then echo %s >&2; exit 1; fi" % (q(arepo), q(live), q(MSG_A))] + back
        self.assertEqual(self.undo["A"], undo_a)
        aside = os.path.join(A, "new-clone-aside")
        aw = [(self.det, os.path.join(aside, "worktrees", "0-det")),
              (self.out, os.path.join(aside, "worktrees", "1-out ü"))]
        undo_b = ["# sets the new clone aside only once it is confirmed as the new clone, untouched; "
                  "then moves the archived folders back",
                  "if [ ! -e %s ]; then echo %s >&2; exit 1; fi" % (q(arepo), q(MSG_B1)),
                  'if [ "$(git -C %s config --get remote.origin.pushurl)" != %s ]; then echo %s >&2; exit 1; fi'
                  % (q(live), MARK, q(MSG_B2)),
                  "%s check-new-clone %s %s %s" % (PY, q(live), q(os.path.join(self.d, "inv.json")),
                                                   self.inv["new_clone_digest"]),
                  "mkdir -p %s" % q(os.path.join(aside, "worktrees"))]
        undo_b += ["if [ -e %s ]; then mv %s %s; fi" % (q(s), q(s), q(t)) for s, t in aw]
        undo_b.append("mv %s %s" % (q(live), q(os.path.join(aside, "repo"))))
        undo_b += ["if [ -e %s ]; then git -C %s worktree repair %s; fi" % (q(t), q(os.path.join(aside, "repo")), q(t))
                   for _s, t in aw]
        self.assertEqual(self.undo["B"], undo_b + back)

    def test_new_clone_expectation_recorded(self):                              # what check-new-clone compares
        exp = self.inv["new_clone"]
        self.assertEqual(exp["refs"], {n: self.refs_before[n] for n in self.CARRIED})
        kept2, _old, kept1 = self.stash_before
        self.assertEqual(exp["stash"], [kept1, kept2])
        self.assertEqual(sorted(norm(p) for p in exp["worktrees"]), sorted([norm(self.out), norm(self.det)]))

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
        for repo, value in ((self.live, MARK), (self.archived_repo, "DISABLED-history-purge-x")):
            for r in ("origin", "fork"):
                self.assertEqual(git(repo, "config", "--get-all", "remote.%s.pushurl" % r), value, (repo, r))
            pushes = [l for l in git(repo, "remote", "-v").splitlines() if l.endswith("(push)")]
            self.assertEqual(len(pushes), 2)
            self.assertTrue(all("DISABLED" in l for l in pushes), pushes)
        res = subprocess.run(["git", "-C", self.live, "push", "origin", "HEAD:refs/heads/x"], capture_output=True,
                             env=ENV)
        self.assertNotEqual(res.returncode, 0)
        self.assertNotIn("refs/heads/x", refs(S.purged))


def undo_fixture(d, name="live"):
    """A checkout for the undo tests: absolute hooksPath inside .git, a kept locked worktree on a branch, a kept
    detached worktree in a folder named outside cp1252, an old dirty worktree, a kept stash entry, a frozen
    second remote. Returns (live, roots: the main folder and every linked worktree folder)."""
    live = S.live(os.path.join(d, name))
    git(live, "config", "remote.origin.pushurl", "DISABLED-history-purge-2026-11-27")   # the Step 0 freeze
    hooks = os.path.join(live, ".git", "ora-hooks")
    write(os.path.join(hooks, "pre-push"), "#!/bin/sh\nexit 1\n")
    git(live, "config", "core.hooksPath", hooks.replace(os.sep, "/"))
    a, b, c = (os.path.join(d, "wts", n) for n in ("a", "b-old", "c-Проект"))
    git(live, "worktree", "add", "-q", "-b", "a-br", a, commit_on(live, S.new_main, "a work"))
    git(live, "worktree", "lock", "--reason", "keep me", a)
    git(live, "worktree", "add", "-q", "-b", "b-br", b, S.c[2])
    write(os.path.join(b, "dirty.txt"), "old dirty\n")
    git(live, "worktree", "add", "-q", "--detach", c, S.new_main)
    write(os.path.join(live, "README.md"), "kept stash\n")
    git(live, "stash", "-q")
    return live, [live, a, b, c]


def git_state(live):
    return (refs(live), wt_list(live), reflog(live, "refs/stash"), git(live, "config", "--list", "--local"))


class Step6UndoTest(unittest.TestCase):
    """R7-01: the printed commands are stopped at EVERY line; the undo for that stage is run as printed; the
    checkout is back byte for byte (every file of the main folder, .git included, and of every worktree), and
    no folder of the original set is left aside or in the archive."""

    def stop_and_undo(self, k, name):
        d = fresh(name)
        live, roots = undo_fixture(d)
        before, state = snapshot(roots), git_state(live)
        arch, _r, _inv, cmds, undo = step6(live, d, follow_it=False)
        lines = [l for l in cmds if not l.startswith("#")]
        clone_at = [i for i, l in enumerate(lines) if l.startswith("git clone")][0]
        follow(lines[:k])
        stage = "B" if k > clone_at else "A"
        follow(undo[stage])
        self.assertEqual(snapshot_diff(before, snapshot(roots)), [], (k, lines[k - 1] if k else None))
        self.assertEqual(git_state(live), state)
        self.assertFalse(os.path.exists(os.path.join(arch, "repo")))
        self.assertEqual(os.listdir(os.path.join(arch, "worktrees")) if os.path.isdir(
            os.path.join(arch, "worktrees")) else [], [])
        aside = os.path.join(arch, "new-clone-aside")
        if stage == "B":                                                        # only the new clone is aside
            self.assertEqual(git(os.path.join(aside, "repo"), "config", "remote.origin.pushurl"), MARK)
            for n in os.listdir(os.path.join(aside, "worktrees")):
                self.assertIn(n, ("0-a", "1-c-Проект"))
                self.assertEqual(norm(git(os.path.join(aside, "worktrees", n), "rev-parse", "--git-common-dir")),
                                 norm(os.path.join(aside, "repo", ".git")))
        else:
            self.assertFalse(os.path.exists(aside))
        return len(lines)

    def test_every_stop_point_then_its_undo_restores_the_checkout_byte_for_byte(self):
        n = self.stop_and_undo(0, "undo-0")
        for k in range(1, n + 1):
            with self.subTest(stop_after=k):
                self.stop_and_undo(k, "undo-%d" % k)

    def test_undo_a_refuses_once_git_clone_has_run(self):
        d = fresh("undo-a-late")
        live, roots = undo_fixture(d)
        arch, _r, _inv, cmds, undo = step6(live, d)
        after = snapshot([live, os.path.join(arch, "repo")])
        guard = [l for l in undo["A"] if not l.startswith("#")][0]
        res = sh(guard)
        self.assertEqual(res.returncode, 1)
        self.assertIn(MSG_A, res.stderr)
        self.assertEqual(snapshot([live, os.path.join(arch, "repo")]), after)

    def test_undo_b_refuses_before_git_clone_and_on_the_original(self):
        d = fresh("undo-b-early")
        live, roots = undo_fixture(d)
        arch, _r, _inv, cmds, undo = step6(live, d, follow_it=False)
        guards = [l for l in undo["B"] if not l.startswith("#")][:2]
        res = sh(guards[0])                                                     # nothing archived yet
        self.assertEqual((res.returncode, res.stderr.strip()), (1, MSG_B1))
        os.makedirs(os.path.join(arch, "repo"))                                 # pretend 6.3 ran, original in place
        res = sh(guards[1])                                                     # Step 0's DISABLED-...-<date> marker
        self.assertEqual((res.returncode, res.stderr.strip()), (1, MSG_B2))
        os.rmdir(os.path.join(arch, "repo"))


class NewCloneGuardTest(unittest.TestCase):
    """R7-01 / race probe 1: Undo B sets the new clone aside only when nobody has worked in it."""

    def worked_in(self, name, work):
        d = fresh(name)
        live, roots = undo_fixture(d)
        arch, _r, inv, cmds, undo = step6(live, d)
        work(live, d)
        lines = [l for l in undo["B"] if not l.startswith("#")]
        check = lines[2]
        self.assertTrue(check.startswith(PY + " check-new-clone "), check)
        follow(lines[:2])                                                       # identity guards pass
        res = sh(check)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("CHANGED", res.stdout)
        self.assertTrue(os.path.isdir(live) and not os.path.exists(os.path.join(arch, "new-clone-aside")))
        return res.stdout

    def test_untouched_new_clone_passes(self):
        d = fresh("ncg-ok")
        live, roots = undo_fixture(d)
        arch, _r, _inv, cmds, undo = step6(live, d)
        res = sh([l for l in undo["B"] if not l.startswith("#")][2])
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        git(live, "fetch", "-q", "origin")                                      # remote-tracking refs may move
        self.assertEqual(sh([l for l in undo["B"] if not l.startswith("#")][2]).returncode, 0)

    def test_tags_the_clone_brought_pass_a_new_tag_refused(self):              # remote tags are not "new work"
        d = fresh("ncg-tags")
        remote = os.path.join(d, "remote.git")
        subprocess.run(["git", "clone", "-q", "--mirror", "--no-local", S.purged, remote], check=True, env=ENV)
        git(remote, "tag", "-a", "v-remote", S.new_main, "-m", "remote release")
        git(remote, "tag", "lt-remote", S.new_main)
        live, roots = undo_fixture(d)
        arch, _r, _inv, cmds, undo = step6(live, d, url=remote)
        self.assertEqual(git(live, "cat-file", "-t", "refs/tags/v-remote"), "tag")
        check = [l for l in undo["B"] if not l.startswith("#")][2]
        res = sh(check)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        git(live, "tag", "session-tag", S.new_main)
        res = sh(check)
        self.assertEqual(res.returncode, 1, res.stdout)
        self.assertIn("refs/tags/session-tag", res.stdout)

    def test_session_worktree_with_a_commit_refused(self):                      # race probe 1 (A)
        def work(live, d):
            x = os.path.join(live, ".claude", "worktrees", "x")
            git(live, "worktree", "add", "-q", "-b", "sess-x", x, "main")
            write(os.path.join(x, "s.txt"), "session work\n")
            git(x, "add", "s.txt")
            git(x, "commit", "-q", "-m", "session work")
        out = self.worked_in("ncg-wt", work)
        self.assertIn("refs/heads/sess-x", out)

    def test_worktree_added_without_a_new_ref_refused(self):                    # only the worktree list shows it
        def work(live, d):
            git(live, "worktree", "add", "-q", "--detach", os.path.join(d, "session-wt"), S.new_main)
        out = self.worked_in("ncg-wt-noref", work)
        self.assertIn("was added", out)

    def test_recreated_worktree_moved_to_another_carried_commit_refused(self):  # clean, no new ref
        def work(live, d):
            c = os.path.join(d, "wts", "c-Проект")
            git(c, "checkout", "-q", "--detach", git(live, "rev-parse", "refs/heads/a-br"))
            self.assertEqual(git(c, "status", "--porcelain"), "")
        out = self.worked_in("ncg-wt-moved", work)
        self.assertIn("is not at", out)

    def test_commit_on_a_carried_branch_refused(self):
        self.worked_in("ncg-commit", lambda live, d: git(live, "commit", "-q", "--allow-empty", "-m", "new work"))

    def test_commit_in_a_recreated_worktree_refused(self):
        def work(live, d):
            a = os.path.join(d, "wts", "a")
            git(a, "commit", "-q", "--allow-empty", "-m", "work in a")
        self.worked_in("ncg-wt-commit", work)

    def test_new_stash_entry_refused(self):
        def work(live, d):
            write(os.path.join(live, "README.md"), "new stash\n")
            git(live, "stash", "-q")
        self.worked_in("ncg-stash", work)

    def test_uncommitted_edit_refused(self):
        self.worked_in("ncg-edit", lambda live, d: write(os.path.join(d, "wts", "c-Проект", "README.md"), "x\n"))

    def test_detached_commit_in_the_main_worktree_refused(self):
        def work(live, d):
            git(live, "checkout", "-q", "--detach")
            git(live, "commit", "-q", "--allow-empty", "-m", "detached work")
        self.worked_in("ncg-detached", work)

    def test_inv_json_from_another_run_refused(self):
        d = fresh("ncg-other-inv")
        live, roots = undo_fixture(d)
        arch, _r, inv, cmds, undo = step6(live, d)
        check = [l for l in undo["B"] if not l.startswith("#")][2]
        inv["new_clone"]["refs"]["refs/heads/zzz"] = S.new_main                 # a later inventory rewrote it
        with open(os.path.join(d, "inv.json"), "w", encoding="utf-8") as fh:
            json.dump(inv, fh)
        res = sh(check)
        self.assertEqual(res.returncode, 2, res.stdout)
        self.assertIn("inv.json", res.stdout)


class CheckUnchangedTest(unittest.TestCase):
    """R7-04 (race 1): the first 6.3 line re-checks the digest inventory printed; any change to worktrees, refs,
    stash entries or uncommitted files since then stops the procedure before anything moves."""

    def changed_after_inventory(self, name, change):
        d = fresh(name)
        live, roots = undo_fixture(d)
        arch, r, inv, cmds, undo = step6(live, d, follow_it=False)
        first = [l for l in cmds if not l.startswith("#")][0]
        self.assertEqual(cmds[0][:6], "# 6.3 ")
        self.assertEqual(first, "%s check-unchanged %s %s" % (PY, shlex.quote(live), inv["digest"]))
        self.assertEqual(sh(first).returncode, 0, sh(first).stdout)
        self.assertEqual(run("check-unchanged", live, inv["digest"]).returncode, 0)
        change(live, d)
        res = sh(first)
        self.assertEqual(res.returncode, 1, res.stdout + res.stderr)
        self.assertIn("CHANGED since inventory", res.stdout)
        with self.assertRaises(AssertionError):                                 # following stops at line 1
            follow(cmds)
        self.assertTrue(os.path.isdir(live) and not os.path.exists(os.path.join(arch, "repo")))

    def test_capture_run_branch_after_inventory(self):                          # race1_capture_after_inventory
        def capture(live, d):
            wt = os.path.join(d, "cap")
            git(live, "worktree", "add", "-q", "--detach", wt, S.new_main)
            git(wt, "switch", "-q", "-c", "capture/runtime-cache-1")
            git(wt, "commit", "-q", "--allow-empty", "-m", "capture")
            git(live, "worktree", "remove", "--force", wt)
        self.changed_after_inventory("cu-capture", capture)

    def test_commit_in_a_linked_worktree(self):
        self.changed_after_inventory("cu-commit", lambda live, d: git(
            os.path.join(d, "wts", "a"), "commit", "-q", "--allow-empty", "-m", "x"))

    def test_new_stash_entry(self):
        def stash(live, d):
            write(os.path.join(live, "README.md"), "y\n")
            git(live, "stash", "-q")
        self.changed_after_inventory("cu-stash", stash)

    def test_older_stash_entry_dropped(self):                                   # refs/stash itself does not move
        d = fresh("cu-stash-drop")
        live, roots = undo_fixture(d)
        write(os.path.join(live, "README.md"), "second\n")
        git(live, "stash", "-q")
        top = git(live, "rev-parse", "refs/stash")
        _arch, _r, inv, cmds, _u = step6(live, d, follow_it=False)
        git(live, "stash", "drop", "-q", "stash@{1}")
        self.assertEqual(git(live, "rev-parse", "refs/stash"), top)
        res = run("check-unchanged", live, inv["digest"])
        self.assertEqual(res.returncode, 1, res.stdout)

    def test_edit_in_a_kept_worktree(self):
        self.changed_after_inventory("cu-edit", lambda live, d: write(
            os.path.join(d, "wts", "c-Проект", "README.md"), "edited\n"))

    def test_per_worktree_ref_in_a_linked_worktree(self):
        self.changed_after_inventory("cu-perwt", lambda live, d: git(
            os.path.join(d, "wts", "a"), "update-ref", "refs/bisect/bad", S.new_main))

    def test_lock_added_to_a_worktree(self):
        self.changed_after_inventory("cu-lock", lambda live, d: git(
            live, "worktree", "lock", os.path.join(d, "wts", "c-Проект")))

    def test_bad_digest_or_repo_exit_2(self):
        d = fresh("cu-bad")
        live = S.live(os.path.join(d, "live"))
        self.assertEqual(run("check-unchanged", os.path.join(d, "nope"), "0" * 20).returncode, 2)
        self.assertEqual(run("check-unchanged", live, "not-a-digest").returncode, 2)


class EncodingTest(unittest.TestCase):
    """R7-02: inventory runs WITHOUT -X utf8, under python -I, its stdout a pipe (`| tee`, as SKILL.md item 2),
    with Cyrillic and CJK folder names, branch names and stash messages; the tee'd file is UTF-8 and every printed
    command, run from it, reproduces the names exactly."""

    def test_non_cp1252_names_through_tee_then_followed(self):
        d = fresh("enc Отчёт 日本")
        live = S.live(os.path.join(d, "live Проект"))
        kept = commit_on(live, S.new_main, "kept")
        git(live, "update-ref", "refs/heads/feature/отчёт-日本", kept)
        git(live, "tag", "-a", "релиз-版本", kept, "-m", "tag")
        wt = os.path.join(d, "wts", "дерево 木")
        git(live, "worktree", "add", "-q", "-b", "ветка/枝", wt, kept)
        git(live, "worktree", "lock", "--reason", "сессия 会话", wt)
        write(os.path.join(live, "README.md"), "s\n")
        git(live, "stash", "push", "-q", "-m", "Отчёт 日本 it's")
        stash_msgs = git(live, "log", "-g", "--format=%gs", "refs/stash", "--")
        arch, txt = os.path.join(d, "архив 档案"), os.path.join(d, "inventory-1.txt")
        cmd = "%s %s inventory %s %s --out %s --archive %s --clone-url %s | tee %s" % tuple(
            shlex.quote(x) for x in (sys.executable, SCRIPT, live, S.old, os.path.join(d, "inv.json"), arch,
                                     S.purged, txt))
        cmd = cmd.replace(shlex.quote(sys.executable) + " ", shlex.quote(sys.executable) + " -I ", 1)
        self.assertNotIn("-X", cmd)
        res = subprocess.run([SH, "-c", "set -o pipefail; " + cmd], capture_output=True, env=ENV)
        self.assertEqual(res.returncode, 0, res.stdout.decode("utf-8", "replace") + res.stderr.decode("utf-8", "replace"))
        text = read(txt).decode("utf-8")                                        # strict: the file is UTF-8
        self.assertNotIn(chr(13), text)                                           # LF only: bash can run it as a file
        self.assertNotIn("\\u", text)
        self.assertNotIn("\\x", text)
        for name in ("feature/отчёт-日本", "релиз-版本", "дерево 木", "ветка/枝", "Отчёт 日本 it", "сессия 会话"):
            self.assertIn(name, text)
        follow(block(text, BEGIN, UNDO_A))
        self.assertEqual(git(live, "rev-parse", "refs/heads/feature/отчёт-日本"), kept)
        self.assertEqual(git(live, "rev-parse", "refs/tags/релиз-版本^{}"), kept)
        self.assertEqual(git(live, "log", "-g", "--format=%gs", "refs/stash", "--"), stash_msgs)
        rows = {w["path"]: w for w in wt_list(live)}
        self.assertEqual(rows[norm(wt)]["branch"], "refs/heads/ветка/枝")
        self.assertEqual(rows[norm(wt)]["locked"], "сессия 会话")

    def test_a_name_that_is_not_utf8_is_refused_not_mangled(self):
        mod = load_module()
        mod.check_writable(["ascii", "Отчёт 日本"])
        with self.assertRaises(mod.Refuse):
            mod.check_writable(["ok", "refs/heads/caf\udce9"])                  # a Latin-1 byte, surrogate-escaped


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
            git(k, "submodule", "deinit", "-q", "sub")                          # the printed fix
            return k
        _live, _arch, k, _r, _inv, _c = self.follow_layout("submodule-after", build)
        git(k, "submodule", "update", "-q", "--init")                           # the step after Step 6
        self.assertEqual(read(os.path.join(k, "sub", "l.txt")), b"lib\n")

    def test_hooks_path_outside_the_checkout_left_as_it_is(self):              # N06
        hooks = []

        def build(live, d):
            hooks.append(os.path.join(d, "machine-hooks"))
            write(os.path.join(hooks[0], "pre-push"), "#!/bin/sh\nexit 1\n")
            git(live, "config", "core.hooksPath", hooks[0].replace(os.sep, "/"))
        live, arch, _i, _r, _inv, cmds = self.follow_layout("hooks-outside", build)
        self.assertEqual([c for c in cmds if "hooksPath" in c], [])
        self.assertEqual(norm(git(os.path.join(arch, "repo"), "config", "core.hooksPath")), norm(hooks[0]))

    def test_dotted_branch_upstream_carried(self):                              # N14
        def build(live, d):
            git(live, "branch", "rel.1", S.new_main)
            git(live, "config", "branch.rel.1.remote", "origin")
            git(live, "config", "branch.rel.1.merge", "refs/heads/rel.1")
        live, _arch, _i, _r, _inv, _c = self.follow_layout("dotted", build)
        self.assertEqual(git(live, "config", "--get", "branch.rel.1.merge"), "refs/heads/rel.1")
        self.assertEqual(git(live, "config", "--get", "branch.rel.1.remote"), "origin")

    def test_worktree_locked_without_a_reason_relocked(self):                   # N17
        def build(live, d):
            wt = os.path.join(d, "wt")
            git(live, "worktree", "add", "-q", "-b", "wt-br", wt, S.new_main)
            git(live, "worktree", "lock", wt)
            return wt
        live, _arch, wt, _r, _inv, _c = self.follow_layout("lock-no-reason", build)
        self.assertEqual({w["path"]: w["locked"] for w in wt_list(live)}[norm(wt)], "")

    def test_lock_reason_with_tab_quote_and_backslash_carried_exactly(self):   # git C-quotes it in porcelain
        reason = 'tab\there "quoted" back\\slash сессия'

        def build(live, d):
            wt = os.path.join(d, "wt")
            git(live, "worktree", "add", "-q", "-b", "wt-br", wt, S.new_main)
            git(live, "worktree", "lock", "--reason", reason, wt)
            return wt
        live, _arch, wt, _r, inv, _c = self.follow_layout("lock-quoted", build)
        self.assertEqual([w["lock_reason"] for w in inv["worktrees"] if w["locked"]], [reason])
        locked = git(wt, "rev-parse", "--path-format=absolute", "--git-path", "locked")
        self.assertEqual(read(locked).decode("utf-8"), reason + "\n")          # as `git worktree lock` writes it

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
        self.assertIn("git clone --no-local --no-checkout --config remote.origin.pushurl=%s %s %s"
                      % (MARK, shlex.quote(S.src), shlex.quote(self.live)),
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
        self.assertIn("{changed,inventory,overlap,check-unchanged,check-new-clone}", top)
        self.assertIn("digest", run("check-unchanged", "--help").stdout)
        self.assertIn("inv", run("check-new-clone", "--help").stdout)


# ==================================================================== SKILL.md freeze / unfreeze recipe

def skill_blocks():
    """The ```bash blocks of SKILL.md."""
    with open(SKILL_MD, encoding="utf-8") as fh:
        return re.findall(r"```bash\n(.*?)```", fh.read(), re.S)


class FreezeRecipeTest(unittest.TestCase):
    """R6-02: SKILL.md Step 0 freeze and Step 6 unfreeze, run as written, on a plain remote, one with one
    custom pushurl and one with two pushurls."""

    FILE = "pushurls-before-<clone>.txt"

    def recipes(self):
        freeze = [b for b in skill_blocks() if self.FILE in b and "--replace-all" in b]
        unfreeze = [b for b in skill_blocks() if self.FILE in b and "--unset-all" in b]
        self.assertEqual((len(freeze), len(unfreeze)), (1, 1), skill_blocks())
        return freeze[0], unfreeze[0]

    def test_each_clone_gets_back_its_own_push_urls(self):                     # R7-06 (scope F1)
        freeze, unfreeze = self.recipes()
        d = fresh("freeze-two")
        B = d.replace(os.sep, "/")
        up = os.path.join(d, "up.git")
        subprocess.run(["git", "init", "-q", "--bare", up], check=True, env=ENV)
        clones = {}
        for name, pushurls in (("live", [os.path.join(d, "mirror.git"), up]), ("second", [])):
            c = clones[name] = os.path.join(d, name)
            subprocess.run(["git", "init", "-q", "-b", "main", c], check=True, env=ENV)
            git(c, "remote", "add", "origin", up)
            for p in pushurls:
                git(c, "config", "--add", "remote.origin.pushurl", p)
        git(clones["live"], "remote", "add", "fork", up)
        before = {n: git(c, "config", "--get-regexp", r"^remote\..*\.pushurl$", check=False) for n, c in clones.items()}
        for n, c in clones.items():
            res = sh(freeze.replace("<B>", B).replace("<clone>", n).replace("<date>", "2026-11-27"), cwd=c)
            self.assertEqual(res.stdout.strip().splitlines()[-1], "every push URL is frozen", res.stdout + res.stderr)
        for n, c in clones.items():                                             # each re-cloned in Step 6.4
            git(c, "config", "--replace-all", "remote.origin.pushurl", MARK)
        for n, c in clones.items():
            res = sh(unfreeze.replace("<B>", B).replace("<clone>", n), cwd=c)
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(git(c, "config", "--get-regexp", r"^remote\..*\.pushurl$", check=False), before[n], n)

    def test_freeze_then_unfreeze_on_three_remote_shapes(self):
        freeze, unfreeze = self.recipes()
        freeze, unfreeze = [freeze.replace("<clone>", "live")], [unfreeze.replace("<clone>", "live")]
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


class TagRenameRecipeTest(unittest.TestCase):
    """R7-07 (D12/D14/D15): SKILL.md Step 3's tag-rename block, run as written."""

    def test_tag_rename_block_leaves_no_old_tag_object(self):
        blocks = [b for b in skill_blocks() if "tag -a <new>" in b]
        self.assertEqual(len(blocks), 1, skill_blocks())
        d = fresh("tag-rename")
        src = os.path.join(d, "src")
        subprocess.run(["git", "init", "-q", "-b", "main", src], check=True, env=ENV)
        git(src, "commit", "-q", "--allow-empty", "-m", "c0")
        git(src, "tag", "-a", "v-123457", "-m", "release notes\n\nsecond line")
        work = os.path.join(d, "work.git")
        subprocess.run(["git", "clone", "-q", "--mirror", src, work], check=True, env=ENV)
        old_obj, peeled = git(work, "rev-parse", "v-123457"), git(work, "rev-parse", "v-123457^{}")
        msg = git(work, "tag", "-l", "--format=%(contents)", "v-123457")
        script = blocks[0].replace("<B>", d.replace(os.sep, "/")).replace("<old>", "v-123457").replace("<new>", "v-x")
        res = sh(script)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertFalse(exists(work, old_obj))                                 # the old tag object is gone
        self.assertEqual(git(work, "cat-file", "-t", "v-x"), "tag")             # annotated, not lightweight
        self.assertEqual(git(work, "rev-parse", "v-x^{}"), peeled)
        self.assertEqual(git(work, "tag", "-l", "--format=%(contents)", "v-x"), msg)
        self.assertEqual(git(work, "tag", "-l"), "v-x")


class UnitTest(unittest.TestCase):
    def test_index_only_status_codes(self):
        mod = load_module()
        self.assertTrue(all(mod.index_only(x) for x in ("MM", "AM", "RM", "MD", "AD")))
        self.assertFalse(any(mod.index_only(x) for x in (" M", "M ", "A ", "??", " D")))


if __name__ == "__main__":
    unittest.main()
