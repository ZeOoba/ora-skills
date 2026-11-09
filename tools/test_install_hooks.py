#!/usr/bin/env python3
"""Tests for tools/install_hooks.py: the per-clone, untracked git hooks directory.

The gap this closes: `core.hooksPath` used to point at the MAIN checkout's tracked tools/hooks,
so whenever that checkout sat on a branch cut before tools/hooks/pre-push existed, git ran no
pre-push hook at all and the Invariant 3 confidentiality gate was silently off. The installer
writes shims into <git-common-dir>/ora-hooks (never tracked, never switched by a checkout) and
points core.hooksPath there. Each shim runs the tracked hook from the tree being committed or
pushed when it exists; pre-push otherwise runs a fallback scanner copy, or blocks.

End-to-end cases build a throwaway bare remote + clone (path deliberately contains a space),
point HOME/USERPROFILE at a temp home holding a synthetic roster, and run real git commands.
Roster terms are invented. Stdlib only.

    python tools/test_install_hooks.py
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
INSTALLER = os.path.join(HERE, "install_hooks.py")
SCAN = os.path.join(HERE, "prepush_confidential_scan.py")
TRACKED_HOOKS = os.path.join(HERE, "hooks")

TERM = "Zyxwv Quillborne"   # invented
ROSTER = {
    "_meta": {"note": "synthetic test roster"},
    "deal_a": {"active": True, "always": [TERM]},
}
HOOK_NAMES = ("pre-commit", "post-commit", "post-merge", "post-rewrite", "pre-push")


def _rmtree(path):
    def onerr(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=onerr)


def _snapshot(d):
    snap = {}
    for n in os.listdir(d):
        with open(os.path.join(d, n), "rb") as f:
            snap[n] = (os.stat(os.path.join(d, n)).st_mtime_ns, f.read())
    return snap


class Sandbox:
    """Temp home + roster, bare remote, and a clone whose main has NO tools/ at all
    (i.e. its checked-out branch predates every tracked hook, including pre-push)."""

    def __init__(self):
        self.root = tempfile.mkdtemp(prefix="ora hooks ")   # space on purpose: shim quoting
        self.home = os.path.join(self.root, "home")
        os.makedirs(os.path.join(self.home, ".claude", "hooks"))
        with open(os.path.join(self.home, ".claude", "hooks", "confidential-terms.json"),
                  "w", encoding="utf-8") as f:
            json.dump(ROSTER, f)
        gcfg = os.path.join(self.root, "gitconfig")
        open(gcfg, "w").close()
        self.env = dict(os.environ)
        self.env.update({
            "HOME": self.home, "USERPROFILE": self.home,
            "GIT_CONFIG_GLOBAL": gcfg, "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        })
        self.env.pop("ORA_PREPUSH_REQUIRE_REFS", None)
        self.remote = os.path.join(self.root, "remote.git")
        self.work = os.path.join(self.root, "work")
        self.git(self.root, "init", "-q", "--bare", "-b", "main", self.remote)
        self.git(self.root, "init", "-q", "-b", "main", self.work)
        self.git(self.work, "remote", "add", "origin", self.remote)
        self.commit("README.md", "seed\n", "seed")
        self.git(self.work, "push", "-q", "--no-verify", "origin", "main")
        self.git(self.work, "fetch", "-q", "origin")

    # -- helpers --------------------------------------------------------------------------
    def git(self, cwd, *args, check=True, stdin=None):
        p = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True, env=self.env,
                           input=stdin)
        if check and p.returncode != 0:
            raise AssertionError("git %s failed: %s" % (args, p.stderr.decode(errors="replace")))
        return p

    def install(self, repo=None, *extra):
        p = subprocess.run([sys.executable, INSTALLER, "--repo", repo or self.work] + list(extra),
                           capture_output=True, text=True, env=self.env)
        return p.returncode, p.stdout + p.stderr

    def hooks_dir(self, repo=None):
        out = self.git(repo or self.work, "rev-parse", "--path-format=absolute",
                       "--git-common-dir").stdout.decode().strip()
        return os.path.normcase(os.path.normpath(os.path.join(out, "ora-hooks")))

    def write(self, name, content, cwd=None):
        path = os.path.join(cwd or self.work, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)

    def commit(self, name, content, msg="change", cwd=None, verify=False):
        self.write(name, content, cwd)
        self.git(cwd or self.work, "add", "-A")
        args = ["commit", "-q", "-m", msg] + ([] if verify else ["--no-verify"])
        return self.git(cwd or self.work, *args, check=not verify)

    def push(self, *refspec, cwd=None):
        p = self.git(cwd or self.work, "push", "origin", *(refspec or ("HEAD",)), check=False)
        return p.returncode, p.stderr.decode("utf-8", "replace")

    def close(self):
        _rmtree(self.root)


class Base(unittest.TestCase):
    def setUp(self):
        self.sb = Sandbox()

    def tearDown(self):
        self.sb.close()

    def assertBlocked(self, rc, err):
        self.assertNotEqual(rc, 0, "push should have been blocked:\n" + err)
        self.assertIn("pre-push BLOCKED", err)
        self.assertNotIn(TERM.lower(), err.lower(), "a roster term was echoed")

    def assertAllowed(self, rc, err):
        self.assertEqual(rc, 0, "push should have been allowed:\n" + err)
        self.assertNotIn("pre-push BLOCKED", err)

    def installed(self):
        rc, out = self.sb.install()
        self.assertEqual(rc, 0, out)
        return out


class EndToEnd(Base):
    # --- the TDD anchor: the gap the adversarial review proved with a real push ----------
    def test_term_push_blocked_when_checked_out_branch_predates_hook(self):
        self.installed()
        self.assertFalse(os.path.exists(os.path.join(self.sb.work, "tools")),
                         "precondition: the checked-out branch has no tracked hooks")
        self.sb.commit("notes.md", "LOI for %s\n" % TERM)
        self.assertBlocked(*self.sb.push())
        self.assertEqual(self.sb.git(self.sb.remote, "rev-parse", "main").stdout,
                         self.sb.git(self.sb.work, "rev-parse", "origin/main").stdout,
                         "remote main moved despite the block")

    def test_clean_push_allowed_when_branch_predates_hook(self):
        self.installed()
        self.sb.commit("notes.md", "nothing confidential\n")
        self.assertAllowed(*self.sb.push())

    def test_without_installer_the_gap_is_real(self):
        # Control: same clone, core.hooksPath at a tracked dir the branch lacks -> no gate.
        self.sb.git(self.sb.work, "config", "core.hooksPath",
                    os.path.join(self.sb.work, "tools", "hooks"))
        self.sb.commit("notes.md", "LOI for %s\n" % TERM)
        rc, err = self.sb.push()
        self.assertEqual(rc, 0, "control expected the old layout to let this through:\n" + err)

    def test_linked_worktree_on_old_branch_is_blocked(self):
        self.installed()
        wt = os.path.join(self.sb.root, "wt two")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "old", wt, "main")
        self.sb.commit("x.md", "re %s\n" % TERM, cwd=wt)
        self.assertBlocked(*self.sb.push("old", cwd=wt))

    def test_install_from_linked_worktree_targets_common_dir(self):
        wt = os.path.join(self.sb.root, "wt")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "side", wt, "main")
        rc, out = self.sb.install(wt)
        self.assertEqual(rc, 0, out)
        self.assertTrue(os.path.isdir(self.sb.hooks_dir()))
        self.sb.commit("y.md", "re %s\n" % TERM)            # push from the MAIN checkout
        self.assertBlocked(*self.sb.push())

    def test_missing_fallback_scanner_blocks(self):
        self.installed()
        os.remove(os.path.join(self.sb.hooks_dir(), "prepush_confidential_scan.py"))
        self.sb.commit("notes.md", "nothing confidential\n")
        rc, err = self.sb.push()
        self.assertNotEqual(rc, 0, "push must be blocked when no scanner is reachable:\n" + err)
        self.assertIn("pre-push BLOCKED", err)

    def test_tracked_pre_push_preferred_and_gets_stdin(self):
        self.installed()
        self.sb.commit("tools/hooks/pre-push",
                       "#!/bin/sh\ncat > \"$(git rev-parse --git-common-dir)/stdin.txt\"\n"
                       "echo TRACKED-PRE-PUSH-RAN >&2\nexit 3\n")
        rc, err = self.sb.push()
        self.assertNotEqual(rc, 0, err)
        self.assertIn("TRACKED-PRE-PUSH-RAN", err)
        common = self.sb.git(self.sb.work, "rev-parse", "--git-common-dir").stdout.decode().strip()
        with open(os.path.join(self.sb.work, common, "stdin.txt"), encoding="utf-8") as f:
            self.assertIn("refs/heads/main", f.read(), "ref lines must reach the tracked hook")

    def test_repo_tracked_hooks_run_through_shim(self):
        # The real tracked pre-push from this repo, run via the shim, blocks a term push.
        self.installed()
        for name in ("pre-push",):
            with open(os.path.join(TRACKED_HOOKS, name), encoding="utf-8") as f:
                self.sb.write("tools/hooks/" + name, f.read())
        with open(SCAN, encoding="utf-8") as f:
            self.sb.write("tools/prepush_confidential_scan.py", f.read())
        self.sb.git(self.sb.work, "add", "-A")
        self.sb.git(self.sb.work, "commit", "-q", "--no-verify", "-m", "add gate")
        self.assertAllowed(*self.sb.push())
        self.sb.commit("deal.md", "%s\n" % TERM)
        self.assertBlocked(*self.sb.push())


class OtherHooks(Base):
    def test_pre_commit_absent_in_tree_allows_commit(self):
        self.installed()
        p = self.sb.commit("a.md", "a\n", verify=True)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_tracked_pre_commit_runs_and_can_block(self):
        self.installed()
        self.sb.commit("tools/hooks/pre-commit", "#!/bin/sh\necho TRACKED-PRE-COMMIT >&2\nexit 1\n")
        p = self.sb.commit("b.md", "b\n", verify=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("TRACKED-PRE-COMMIT", p.stderr.decode())

    def test_tracked_post_hooks_run_with_args_and_stdin(self):
        self.installed()
        common = self.sb.git(self.sb.work, "rev-parse", "--path-format=absolute",
                             "--git-common-dir").stdout.decode().strip()
        marker = os.path.join(common, "post.log").replace("\\", "/")
        body = ("#!/bin/sh\necho \"$(basename \"$0\") $*\" >> '%s'\n"
                "[ \"$(basename \"$0\")\" = post-rewrite ] && cat >> '%s'\nexit 0\n" % (marker, marker))
        for name in ("post-commit", "post-merge", "post-rewrite"):
            self.sb.write("tools/hooks/" + name, body)
        self.sb.git(self.sb.work, "add", "-A")
        self.sb.git(self.sb.work, "commit", "-q", "-m", "hooks")            # post-commit
        self.sb.git(self.sb.work, "commit", "-q", "--amend", "-m", "hooks2")  # post-rewrite amend
        self.sb.git(self.sb.work, "branch", "other", "HEAD~1")
        self.sb.git(self.sb.work, "checkout", "-q", "other")
        self.sb.commit("o.md", "o\n")
        self.sb.git(self.sb.work, "checkout", "-q", "main")
        self.sb.git(self.sb.work, "merge", "-q", "--no-edit", "other")        # post-merge
        with open(marker, encoding="utf-8") as f:
            log = f.read()
        self.assertIn("post-commit", log)
        self.assertIn("post-rewrite amend", log)
        self.assertIn("post-merge 0", log)

    def test_post_hooks_absent_are_noops(self):
        self.installed()
        p = self.sb.commit("c.md", "c\n", verify=True)
        self.assertEqual(p.returncode, 0, p.stderr)


class Installer(Base):
    def test_hooks_dir_is_untracked_and_outside_worktree(self):
        self.installed()
        hd = self.sb.hooks_dir()
        val = self.sb.git(self.sb.work, "config", "--get", "core.hooksPath").stdout.decode().strip()
        self.assertEqual(os.path.normcase(os.path.normpath(val)), hd)
        work = os.path.normcase(os.path.normpath(self.sb.work)) + os.sep
        common = os.path.normcase(os.path.normpath(os.path.join(self.sb.work, ".git"))) + os.sep
        self.assertTrue(hd.startswith(common), hd)
        self.assertEqual(self.sb.git(self.sb.work, "status", "--porcelain").stdout, b"")
        self.assertTrue(hd.startswith(work))  # inside .git, so inside the dir but never tracked
        for name in HOOK_NAMES:
            self.assertTrue(os.path.isfile(os.path.join(hd, name)), name)
        self.assertTrue(os.path.isfile(os.path.join(hd, "prepush_confidential_scan.py")))

    def test_fallback_scanner_is_byte_identical_copy(self):
        self.installed()
        with open(SCAN, "rb") as a, open(os.path.join(self.sb.hooks_dir(),
                                                      "prepush_confidential_scan.py"), "rb") as b:
            self.assertEqual(a.read(), b.read())

    def test_idempotent(self):
        self.installed()
        hd = self.sb.hooks_dir()
        before = _snapshot(hd)
        out = self.installed()
        after = _snapshot(hd)
        self.assertEqual(before, after)
        self.assertIn("up to date", out.lower())

    def test_never_deletes_existing_files(self):
        hd = self.sb.hooks_dir()
        os.makedirs(hd)
        with open(os.path.join(hd, "pre-push"), "w") as f:
            f.write("#!/bin/sh\n# someone's own hook\nexit 0\n")
        with open(os.path.join(hd, "unrelated.txt"), "w") as f:
            f.write("keep me\n")
        self.installed()
        names = os.listdir(hd)
        backups = [n for n in names if n.startswith("pre-push.bak-")]
        self.assertEqual(len(backups), 1, names)
        with open(os.path.join(hd, backups[0])) as f:
            self.assertIn("someone's own hook", f.read())
        with open(os.path.join(hd, "unrelated.txt")) as f:
            self.assertEqual(f.read(), "keep me\n")
        self.installed()   # a second run must not create another backup
        self.assertEqual(len([n for n in os.listdir(hd) if n.startswith("pre-push.bak-")]), 1)

    def test_previous_hookspath_reported_and_replaced(self):
        old = os.path.join(self.sb.work, "tools", "hooks")
        self.sb.git(self.sb.work, "config", "core.hooksPath", old)
        out = self.installed()
        self.assertIn("core.hooksPath", out)
        self.assertIn("tools", out)
        val = self.sb.git(self.sb.work, "config", "--get", "core.hooksPath").stdout.decode().strip()
        self.assertEqual(os.path.normcase(os.path.normpath(val)), self.sb.hooks_dir())

    def test_check_mode(self):
        rc, out = self.sb.install(None, "--check")
        self.assertEqual(rc, 1, out)
        self.assertFalse(os.path.exists(self.sb.hooks_dir()), "--check must not write")
        self.installed()
        rc, out = self.sb.install(None, "--check")
        self.assertEqual(rc, 0, out)
        with open(os.path.join(self.sb.hooks_dir(), "prepush_confidential_scan.py"), "a") as f:
            f.write("# stale\n")
        rc, out = self.sb.install(None, "--check")
        self.assertEqual(rc, 1, out)

    def test_worktree_scoped_hookspath_override_is_refused(self):
        # A per-worktree core.hooksPath would silently win over the shared one.
        wt = os.path.join(self.sb.root, "wt")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "side", wt, "main")
        self.sb.git(self.sb.work, "config", "extensions.worktreeConfig", "true")
        self.sb.git(wt, "config", "--worktree", "core.hooksPath",
                    os.path.join(wt, "tools", "hooks"))
        rc, out = self.sb.install()
        self.assertNotEqual(rc, 0, out)
        self.assertIn("worktree", out.lower())

    def test_not_a_git_repo_fails(self):
        d = os.path.join(self.sb.root, "plain")
        os.makedirs(d)
        rc, out = self.sb.install(d)
        self.assertNotEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main()
