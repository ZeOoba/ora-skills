#!/usr/bin/env python3
"""
Regression tests for scan_dirty_trees.discover_clones_by_remote()'s role
classification.

Stdlib only -- run with `python dirty-tree-triage/tests/test_scan_dirty_trees.py`.
No pytest, matching lease-form-qc/tests and tools/test_*.py.

WHY THIS FILE EXISTS
--------------------
The 2026-09-16 run mislabeled two classes of checkout:
1. Every registered `git worktree` (a `.git` FILE, listed by
   `git -C <primary> worktree list`) came out `stray`, because the classifier
   only knew "first found" vs "everything else".
2. `primary` was simply the first child in sort order, so a linked worktree of
   the canonical site repo (wc-seo-fixes) was labeled primary and the canonical
   checkout itself was labeled stray.

Fixtures are real git repos (a bare "remote", clones of it, and linked
worktrees) under a temp root, so the tests exercise the same git plumbing the
live scan uses rather than a mocked subprocess.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import scan_dirty_trees as sdt  # noqa: E402


class GitFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="scan_dirty_trees_test_")).resolve()
        # Keep any global/ORA git hooks (commit-provenance etc.) out of fixture commits.
        self.nohooks = self.tmp / "nohooks"
        self.nohooks.mkdir()
        self.root = self.tmp / "root"
        self.root.mkdir()
        self.remote = self.tmp / "remote.git"
        self._git(self.tmp, "init", "-q", "--bare", "-b", "main", str(self.remote))
        seed = self.tmp / "seed"
        self._git(self.tmp, "clone", "-q", str(self.remote), str(seed))
        self._git(seed, "checkout", "-q", "-b", "main")
        (seed / "README.md").write_text("seed\n", encoding="utf-8")
        self._git(seed, "add", "README.md")
        self._git(seed, "commit", "-q", "-m", "seed")
        self._git(seed, "push", "-q", "origin", "main")

    def tearDown(self):
        def _onerror(func, path, _exc):
            os.chmod(path, 0o700)
            func(path)
        shutil.rmtree(self.tmp, onerror=_onerror)

    def _git(self, cwd, *args):
        proc = subprocess.run(
            ["git", "-c", f"core.hooksPath={self.nohooks}",
             "-c", "user.name=test", "-c", "user.email=test@example.invalid",
             *args],
            cwd=str(cwd), capture_output=True, text=True, check=False,
        )
        if proc.returncode != 0:
            self.fail(f"git {' '.join(args)} failed: {proc.stderr}")
        return proc.stdout

    def _clone(self, name):
        dest = self.root / name
        self._git(self.tmp, "clone", "-q", str(self.remote), str(dest))
        return dest

    def _worktree(self, main, name, branch):
        dest = self.root / name
        self._git(main, "worktree", "add", "-q", "-b", branch, str(dest))
        return dest

    def _roles(self, roster=None):
        # roster=None -> an empty roster, so the live DEFAULT_REPOS never leak into a fixture.
        result = sdt.discover_clones_by_remote(root=str(self.root), roster=list(roster or []))
        self.assertNotIn("error", result)
        groups = result["remote_groups_with_duplicates"]
        self.assertEqual(len(groups), 1, groups)
        return {Path(c["path"]).name: c for c in groups[0]["clones"]}


class LinkedWorktreesAreNotStray(GitFixture):
    def test_registered_worktree_gets_worktree_role(self):
        canon = self._clone("canon")
        self._worktree(canon, "canon-wt-feature", "feat/x")

        roles = self._roles()

        self.assertEqual(roles["canon"]["role"], "primary")
        self.assertEqual(roles["canon-wt-feature"]["role"], "worktree")

    def test_worktree_reports_branch_and_main_worktree(self):
        canon = self._clone("canon")
        self._worktree(canon, "canon-wt-feature", "feat/x")

        wt = self._roles()["canon-wt-feature"]

        self.assertEqual(wt["branch"], "feat/x")
        self.assertEqual(Path(wt["main_worktree"]).resolve(), canon.resolve())

    def test_worktree_at_default_branch_tip_is_merged(self):
        canon = self._clone("canon")
        self._worktree(canon, "canon-wt-feature", "feat/x")

        self.assertIs(self._roles()["canon-wt-feature"]["merged"], True)

    def test_worktree_with_unmerged_commit_is_not_merged(self):
        canon = self._clone("canon")
        wt = self._worktree(canon, "canon-wt-feature", "feat/y")
        (wt / "new.txt").write_text("wip\n", encoding="utf-8")
        self._git(wt, "add", "new.txt")
        self._git(wt, "commit", "-q", "-m", "wip")

        self.assertIs(self._roles()["canon-wt-feature"]["merged"], False)

    def test_worktree_whose_upstream_branch_was_deleted_reports_upstream_gone(self):
        # Squash-merged PR branches never become ancestors of main; a deleted
        # upstream is the observable signal that the PR landed.
        canon = self._clone("canon")
        wt = self._worktree(canon, "canon-wt-feature", "feat/z")
        (wt / "z.txt").write_text("z\n", encoding="utf-8")
        self._git(wt, "add", "z.txt")
        self._git(wt, "commit", "-q", "-m", "z")
        self._git(wt, "push", "-q", "-u", "origin", "feat/z")
        self._git(canon, "push", "-q", "origin", "--delete", "feat/z")

        wt_entry = self._roles()["canon-wt-feature"]

        self.assertIs(wt_entry["merged"], False)
        self.assertIs(wt_entry["upstream_gone"], True)

    def test_managed_build_root_worktree_keeps_managed_role(self):
        canon = self._clone("canon")
        self._worktree(canon, "canon-deploy-build", "deploy")

        self.assertEqual(self._roles()["canon-deploy-build"]["role"], "managed-build-root")


class PrimaryIsNotFirstFound(GitFixture):
    def test_main_worktree_is_primary_even_when_a_linked_worktree_sorts_first(self):
        # The wc-seo-fixes / website-canonical shape: the linked worktree's
        # name sorts ahead of the checkout that owns it.
        canon = self._clone("website")
        self._worktree(canon, "aaa-seo-fixes", "fix/seo")

        roles = self._roles()

        self.assertEqual(roles["website"]["role"], "primary")
        self.assertEqual(roles["aaa-seo-fixes"]["role"], "worktree")

    def test_roster_repo_is_primary_over_an_earlier_sorting_independent_clone(self):
        self._clone("aaa-reclone")
        canon = self._clone("zzz-canonical")

        roles = self._roles(roster=[str(canon)])

        self.assertEqual(roles["zzz-canonical"]["role"], "primary")
        self.assertEqual(roles["aaa-reclone"]["role"], "stray")

    def test_roster_match_is_case_and_separator_insensitive(self):
        self._clone("aaa-reclone")
        canon = self._clone("zzz-canonical")
        roster_spelling = str(canon).upper().replace("\\", "/") if os.name == "nt" else str(canon)

        self.assertEqual(self._roles(roster=[roster_spelling])["zzz-canonical"]["role"], "primary")

    def test_independent_reclone_without_roster_is_still_stray(self):
        # The original OI-200 case (oxford-command-center-1) must keep flagging.
        self._clone("occ")
        self._clone("occ-1")

        roles = self._roles()

        self.assertEqual(roles["occ"]["role"], "primary")
        self.assertEqual(roles["occ-1"]["role"], "stray")

    def test_independent_reclone_is_stray_alongside_worktrees(self):
        canon = self._clone("occ")
        self._worktree(canon, "occ-wt-a", "feat/a")
        self._clone("occ-1")

        roles = self._roles(roster=[str(canon)])

        self.assertEqual(roles["occ"]["role"], "primary")
        self.assertEqual(roles["occ-wt-a"]["role"], "worktree")
        self.assertEqual(roles["occ-1"]["role"], "stray")


if __name__ == "__main__":
    unittest.main(verbosity=2)
