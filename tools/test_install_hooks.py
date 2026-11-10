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

    def _add_real_gate(self, cwd=None):
        with open(os.path.join(TRACKED_HOOKS, "pre-push"), encoding="utf-8") as f:
            self.sb.write("tools/hooks/pre-push", f.read(), cwd)
        with open(SCAN, encoding="utf-8") as f:
            self.sb.write("tools/prepush_confidential_scan.py", f.read(), cwd)
        self.sb.git(cwd or self.sb.work, "add", "-A")
        self.sb.git(cwd or self.sb.work, "commit", "-q", "--no-verify", "-m", "add gate")

    def test_uncommitted_noop_edit_to_tracked_pre_push_is_still_blocked(self):
        # REFUTE E1: the worktree's tracked hook is a live, editable file; the pinned scan
        # beside the shim must still run.
        self.installed()
        wt = os.path.join(self.sb.root, "wt feat")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "feat", wt, "main")
        self._add_real_gate(wt)
        self.sb.write("tools/hooks/pre-push", "#!/bin/sh\nexit 0\n", wt)
        self.sb.write("tools/prepush_confidential_scan.py", "import sys; sys.exit(0)\n", wt)
        self.sb.write("deal.md", "%s\n" % TERM, wt)
        self.sb.git(wt, "add", "deal.md")
        self.sb.git(wt, "commit", "-q", "--no-verify", "-m", "x")
        self.assertBlocked(*self.sb.push("feat", cwd=wt))

    def test_committed_noop_tracked_pre_push_is_still_blocked(self):
        self.installed()
        self.sb.commit("tools/hooks/pre-push", "#!/bin/sh\nexit 0\n")
        self.sb.commit("deal.md", "%s\n" % TERM)
        self.assertBlocked(*self.sb.push())

    def test_no_python_blocks(self):
        self.installed()
        fake = os.path.join(self.sb.root, "fakebin")
        os.makedirs(fake)
        for n in ("python", "python3", "py"):
            p = os.path.join(fake, n)
            with open(p, "w", newline="\n") as f:
                f.write("#!/bin/sh\nexit 9\n")
            os.chmod(p, 0o755)
        self.sb.env["PATH"] = fake + os.pathsep + self.sb.env["PATH"]
        self.sb.commit("notes.md", "nothing confidential\n")
        rc, err = self.sb.push()
        self.assertNotEqual(rc, 0, err)
        self.assertIn("pre-push BLOCKED", err)
        self.assertIn("Python", err)

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
        self.assertFalse(os.path.exists(self.sb.hooks_dir()), "refusal must write nothing")
        self.assertEqual(self.sb.git(self.sb.work, "config", "--local", "--get", "core.hooksPath",
                                     check=False).stdout, b"")

    def test_inherited_old_shared_hookspath_is_not_an_override(self):
        # Regression 2026-11-10: with extensions.worktreeConfig on and NO config.worktree
        # value, a linked worktree merely INHERITS the old shared core.hooksPath. That is not
        # an override (the install replaces the shared value), so it must not block install.
        wt = os.path.join(self.sb.root, "wt")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "side", wt, "main")
        self.sb.git(self.sb.work, "config", "extensions.worktreeConfig", "true")
        self.sb.git(self.sb.work, "config", "core.hooksPath",
                    os.path.join(self.sb.work, "tools", "hooks"))
        self.installed()
        for d in (self.sb.work, wt):
            val = self.sb.git(d, "config", "--get", "core.hooksPath").stdout.decode().strip()
            self.assertEqual(os.path.normcase(os.path.normpath(val)), self.sb.hooks_dir(), d)
        rc, out = self.sb.install(None, "--check")
        self.assertEqual(rc, 0, out)

    def test_worktree_override_equal_to_hooks_dir_is_allowed(self):
        # A config.worktree value that already names the install dir does not win against it.
        wt = os.path.join(self.sb.root, "wt")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "side", wt, "main")
        self.sb.git(self.sb.work, "config", "extensions.worktreeConfig", "true")
        self.sb.git(wt, "config", "--worktree", "core.hooksPath", self.sb.hooks_dir())
        self.installed()

    def test_main_worktree_scoped_override_is_refused(self):
        # config.worktree of the MAIN worktree would also beat the shared --local value.
        self.sb.git(self.sb.work, "config", "extensions.worktreeConfig", "true")
        self.sb.git(self.sb.work, "config", "--worktree", "core.hooksPath",
                    os.path.join(self.sb.work, "tools", "hooks"))
        rc, out = self.sb.install()
        self.assertNotEqual(rc, 0, out)
        self.assertFalse(os.path.exists(self.sb.hooks_dir()), "refusal must write nothing")

    # REFUTE 2026-11-10 (cases A/B/C/F): overrides a worktree-scope-only read would miss.
    def _side_worktree(self, wt_config=True):
        wt = os.path.join(self.sb.root, "wt")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "side", wt, "main")
        if wt_config:
            self.sb.git(self.sb.work, "config", "extensions.worktreeConfig", "true")
        return wt

    def _evil_include(self):
        path = os.path.join(self.sb.root, "evil.cfg")
        with open(path, "w") as f:
            f.write("[core]\n\thooksPath = %s\n" % os.path.join(self.sb.root, "evil").replace("\\", "/"))
        return path

    def _assert_refused_then_caught_after_install(self, add_override):
        add_override()
        rc, out = self.sb.install()
        self.assertEqual(rc, 2, out)
        self.assertFalse(os.path.exists(self.sb.hooks_dir()), "refusal must write nothing")
        rc, out = self.sb.install(None, "--check")
        self.assertEqual(rc, 1, out)

    def test_include_in_config_worktree_is_refused(self):           # case A
        wt = self._side_worktree()
        self._assert_refused_then_caught_after_install(
            lambda: self.sb.git(wt, "config", "--worktree", "include.path", self._evil_include()))

    def test_empty_config_worktree_value_is_refused(self):          # case B
        wt = self._side_worktree()
        self._assert_refused_then_caught_after_install(
            lambda: self.sb.git(wt, "config", "--worktree", "core.hooksPath", ""))

    def test_shared_includeif_onbranch_is_refused(self):            # case F
        self._side_worktree()
        self._assert_refused_then_caught_after_install(
            lambda: self.sb.git(self.sb.work, "config", "--local", "includeIf.onbranch:side.path",
                                self._evil_include()))

    def test_shared_includeif_onbranch_refused_without_worktree_config(self):
        self._side_worktree(wt_config=False)
        self._assert_refused_then_caught_after_install(
            lambda: self.sb.git(self.sb.work, "config", "--local", "includeIf.onbranch:side.path",
                                self._evil_include()))

    def test_override_added_after_install_fails_check(self):
        wt = self._side_worktree()
        self.installed()
        self.sb.git(self.sb.work, "config", "--local", "includeIf.onbranch:side.path",
                    self._evil_include())
        rc, out = self.sb.install(None, "--check")
        self.assertEqual(rc, 1, out)
        self.assertIn("wt", out)

    # REFUTE round 2 (H1/H2/H4): judge the override by its SOURCE, not its value.
    def _includeif_for_side(self, value):
        path = os.path.join(self.sb.root, "same.cfg")
        with open(path, "w") as f:
            f.write("[core]\n\thooksPath = %s\n" % value.replace("\\", "/"))
        self.sb.git(self.sb.work, "config", "--local", "includeIf.onbranch:side.path", path)

    def test_includeif_repeating_global_value_is_refused(self):     # H1
        self._side_worktree(wt_config=False)
        g = os.path.join(self.sb.root, "globalhooks")
        self.sb.git(self.sb.work, "config", "--global", "core.hooksPath", g)
        self._assert_refused_then_caught_after_install(lambda: self._includeif_for_side(g))

    def test_includeif_added_after_install_repeating_global_fails_check(self):   # H1p
        wt = self._side_worktree(wt_config=False)
        g = os.path.join(self.sb.root, "globalhooks")
        self.sb.git(self.sb.work, "config", "--global", "core.hooksPath", g)
        self.installed()
        self._includeif_for_side(g)
        rc, out = self.sb.install(None, "--check")
        self.assertEqual(rc, 1, out)

    def test_includeif_repeating_shared_local_value_is_refused(self):   # H2
        self._side_worktree()
        x = os.path.join(self.sb.root, "oldhooks")
        self.sb.git(self.sb.work, "config", "--local", "core.hooksPath", x)
        self._assert_refused_then_caught_after_install(lambda: self._includeif_for_side(x))

    def test_global_includeif_hookspath_does_not_block_install(self):   # H4 (legitimate)
        wt = self._side_worktree(wt_config=False)
        path = os.path.join(self.sb.root, "mgr.cfg")
        with open(path, "w") as f:
            f.write("[core]\n\thooksPath = %s\n" % os.path.join(self.sb.root, "mgr").replace("\\", "/"))
        self.sb.git(self.sb.work, "config", "--global",
                    "includeIf.gitdir:%s/**.path" % self.sb.root.replace("\\", "/"), path)
        self.installed()
        val = self.sb.git(wt, "config", "--get", "core.hooksPath").stdout.decode().strip()
        self.assertEqual(os.path.normcase(os.path.normpath(val)), self.sb.hooks_dir())

    def test_plain_global_hookspath_does_not_block_install(self):       # H6 (legitimate)
        self._side_worktree()
        self.sb.git(self.sb.work, "config", "--global", "core.hooksPath",
                    os.path.join(self.sb.root, "g"))
        self.installed()

    def test_non_ascii_worktree_override_is_refused(self):           # REFUTE round 3
        # worktreeConfig OFF so the refusal can only come from actually reading this worktree
        # (an includeIf scoped to its branch), not from a blanket refusal.
        wt = os.path.join(self.sb.root, "wté")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "side", wt, "main")
        self._assert_refused_then_caught_after_install(
            lambda: self.sb.git(self.sb.work, "config", "--local", "includeIf.onbranch:side.path",
                                self._evil_include()))

    # Follow-up to #234: a poisoned checker environment must not redirect what is read.
    def _install_env(self, extra_env, *args, repo=None):
        env = dict(self.sb.env)
        env.update(extra_env)
        p = subprocess.run([sys.executable, INSTALLER, "--repo", repo or self.sb.work] + list(args),
                           capture_output=True, text=True, env=env)
        return p.returncode, p.stdout + p.stderr

    def test_legacy_git_config_env_does_not_mask_override(self):
        wt = self._side_worktree()
        self.installed()
        self.sb.git(wt, "config", "--worktree", "core.hooksPath", os.path.join(self.sb.root, "evil"))
        fake = os.path.join(self.sb.root, "fake.cfg")
        with open(fake, "w") as f:
            f.write("[core]\n\thooksPath = %s\n" % self.sb.hooks_dir().replace("\\", "/"))
        rc, out = self._install_env({"GIT_CONFIG": fake}, "--check")
        self.assertEqual(rc, 1, out)

    def test_env_config_equal_to_hooks_dir_does_not_mask_override(self):   # REFUTE C7
        wt = self._side_worktree()
        self.installed()
        self.sb.git(wt, "config", "--worktree", "core.hooksPath", os.path.join(self.sb.root, "evil"))
        hd = self.sb.hooks_dir()
        for env in ({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
                     "GIT_CONFIG_VALUE_0": hd},
                    {"GIT_CONFIG_PARAMETERS": "'core.hookspath'='%s'" % hd.replace("\\", "/")}):
            rc, out = self._install_env(env, "--check")
            self.assertEqual(rc, 1, (env, out))
            rc, out = self._install_env(env)          # re-install must not report success
            self.assertEqual(rc, 2, (env, out))

    def test_env_config_equal_to_hooks_dir_alone_is_fine(self):   # H5a still installs
        self._side_worktree()
        hd = self.sb.hooks_dir()
        env = {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.hooksPath",
               "GIT_CONFIG_VALUE_0": hd}
        rc, out = self._install_env(env)
        self.assertEqual(rc, 0, out)
        rc, out = self._install_env(env, "--check")
        self.assertEqual(rc, 0, out)

    def test_git_dir_env_does_not_redirect_target(self):
        other = os.path.join(self.sb.root, "other")
        self.sb.git(self.sb.root, "init", "-q", other)
        rc, out = self._install_env({"GIT_DIR": os.path.join(other, ".git")})
        self.assertEqual(rc, 0, out)
        self.assertTrue(os.path.isdir(self.sb.hooks_dir()), out)       # --repo's clone
        self.assertFalse(os.path.exists(os.path.join(other, ".git", "ora-hooks")), out)

    def test_c_unquote(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "ih", os.path.join(os.path.dirname(os.path.abspath(__file__)), "install_hooks.py"))
        ih = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ih)
        self.assertEqual(ih._c_unquote('"C:\\\\a b\\\\.git/config"'), "C:\\a b\\.git/config")
        self.assertEqual(ih._c_unquote('"C:/n\\303\\266n/config"'), "C:/n\u00f6n/config")
        self.assertEqual(ih._c_unquote("C:/plain/config"), "C:/plain/config")

    def test_non_ascii_clone_installs_and_checks(self):
        # Whole clone under a non-ASCII dir: quoted origin must still match the local file.
        nroot = os.path.join(self.sb.root, "n\u00f6n")
        os.makedirs(nroot)
        clone = os.path.join(nroot, "c")
        self.sb.git(self.sb.root, "clone", "-q", self.sb.work, clone)
        self.sb.git(clone, "config", "core.hooksPath", os.path.join(clone, "tools", "hooks"))
        rc, out = self.sb.install(clone)
        self.assertEqual(rc, 0, out)
        rc, out = self.sb.install(clone, "--check")
        self.assertEqual(rc, 0, out)

    def _moved_override(self, lock):
        wt = self._side_worktree()
        if lock:
            self.sb.git(self.sb.work, "worktree", "lock", wt)
        self.sb.git(wt, "config", "--worktree", "core.hooksPath",
                    os.path.join(self.sb.root, "evil"))
        moved = os.path.join(self.sb.root, "moved")
        shutil.move(wt, moved)                 # by hand: git still records the old path
        hooks = self.sb.git(moved, "rev-parse", "--git-path", "hooks").stdout.decode().strip()
        self.assertIn("evil", hooks)           # the moved worktree really bypasses the gate
        return moved

    def test_moved_locked_worktree_override_is_refused(self):       # REFUTE round 4
        self._moved_override(lock=True)
        rc, out = self.sb.install()
        self.assertEqual(rc, 2, out)
        self.assertFalse(os.path.exists(self.sb.hooks_dir()), "refusal must write nothing")

    def test_moved_unlocked_worktree_override_is_refused(self):     # REFUTE round 4
        self._moved_override(lock=False)
        rc, out = self.sb.install()
        self.assertEqual(rc, 2, out)

    def test_locked_missing_worktree_is_checked_not_skipped(self):
        # Its admin dir is still here, so it is verified (clean -> installs and passes).
        wt = os.path.join(self.sb.root, "away")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "away", wt, "main")
        self.sb.git(self.sb.work, "worktree", "lock", wt)
        shutil.rmtree(wt)
        self.installed()
        rc, out = self.sb.install(None, "--check")
        self.assertEqual(rc, 0, out)

    def test_non_ascii_worktree_clean_installs(self):
        wt = os.path.join(self.sb.root, "wté")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "side", wt, "main")
        self.installed()
        rc, out = self.sb.install(None, "--check")
        self.assertEqual(rc, 0, out)

    def test_pruned_worktree_is_skipped(self):
        wt = os.path.join(self.sb.root, "gone")
        self.sb.git(self.sb.work, "worktree", "add", "-q", "-b", "side", wt, "main")
        shutil.rmtree(wt)
        self.installed()
        rc, out = self.sb.install(None, "--check")
        self.assertEqual(rc, 0, out)

    def test_failed_reinstall_never_leaves_shim_missing(self):
        # REFUTE E2: a failure while swapping files must not leave git with no pre-push.
        import importlib.util
        spec = importlib.util.spec_from_file_location("install_hooks_mod", INSTALLER)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.installed()
        hd = self.sb.hooks_dir()
        with open(os.path.join(hd, "pre-push"), "a", newline="\n") as f:
            f.write("# drifted\n")
        real_replace = mod.os.replace

        def boom(src, dst):
            raise OSError(28, "No space left on device (simulated)")
        mod.os.replace = boom
        try:
            with self.assertRaises(OSError):
                mod.install(self.sb.work, lambda _m: None)
        finally:
            mod.os.replace = real_replace
        with open(os.path.join(hd, "pre-push"), encoding="utf-8") as f:
            self.assertIn("ORA-HOOKS-SHIM", f.read(), "live pre-push shim must survive")
        self.sb.commit("deal.md", "%s\n" % TERM)
        self.assertBlocked(*self.sb.push())

    def test_oserror_exits_2_without_traceback(self):
        hd = self.sb.hooks_dir()
        os.makedirs(os.path.dirname(hd), exist_ok=True)
        with open(hd, "w") as f:      # a FILE where the hooks dir should be
            f.write("x")
        rc, out = self.sb.install()
        self.assertEqual(rc, 2, out)
        self.assertNotIn("Traceback", out)

    def test_not_a_git_repo_fails(self):
        d = os.path.join(self.sb.root, "plain")
        os.makedirs(d)
        rc, out = self.sb.install(d)
        self.assertNotEqual(rc, 0, out)


if __name__ == "__main__":
    unittest.main()
