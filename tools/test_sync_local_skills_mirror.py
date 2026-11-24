#!/usr/bin/env python3
"""Regression tests for sync_local_skills_mirror.py.

Stdlib only — run with `python tools/test_sync_local_skills_mirror.py` (no pytest).

Covers the 2026-08-16 fix for Automation Audit R13-2: ora-setup-audit's local
Code-surface mirror (~/.claude/skills/<skill>) had silently diverged from the
canonical repo copy, and nothing kept the two in sync. These tests build
synthetic repo/mirror fixture trees (never the real ora-skills repo or the
real ~/.claude/skills) so they're deterministic regardless of live drift state.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sync_local_skills_mirror as slm  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='')


class FixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='sync_local_skills_mirror_test_'))
        self.repo = self.tmp / 'repo'
        self.mirror = self.tmp / 'mirror'
        self.repo.mkdir()
        self.mirror.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class SyncSkill(FixtureTestCase):
    def test_no_local_mirror_is_skipped_not_created(self):
        _write(self.repo / 'some-skill' / 'SKILL.md', 'name: some-skill\ncontent\n')
        # No mirror dir created — sync must not auto-create one.

        result = slm.sync_skill('some-skill', repo_root=self.repo, mirror_root=self.mirror)

        self.assertIn('no local mirror, skipped', result)
        self.assertFalse((self.mirror / 'some-skill').exists())

    def test_diverged_mirror_is_repaired(self):
        _write(self.repo / 'drifted-skill' / 'SKILL.md', 'name: drifted-skill\nv2 content\n')
        _write(self.mirror / 'drifted-skill' / 'SKILL.md', 'name: drifted-skill\nv1 STALE content\n')

        result = slm.sync_skill('drifted-skill', repo_root=self.repo, mirror_root=self.mirror)

        self.assertIn('synced', result)
        self.assertEqual(
            (self.mirror / 'drifted-skill' / 'SKILL.md').read_text(encoding='utf-8'),
            'name: drifted-skill\nv2 content\n',
        )

    def test_already_synced_mirror_is_a_noop(self):
        _write(self.repo / 'synced-skill' / 'SKILL.md', 'name: synced-skill\ncontent\n')
        _write(self.mirror / 'synced-skill' / 'SKILL.md', 'name: synced-skill\ncontent\n')

        result = slm.sync_skill('synced-skill', repo_root=self.repo, mirror_root=self.mirror)

        self.assertIn('already in sync', result)

    def test_multi_file_skill_syncs_new_and_changed_files(self):
        _write(self.repo / 'multi-skill' / 'SKILL.md', 'name: multi-skill\ncontent\n')
        _write(self.repo / 'multi-skill' / 'references' / 'notes.md', 'notes v2\n')
        _write(self.mirror / 'multi-skill' / 'SKILL.md', 'name: multi-skill\ncontent\n')
        # references/notes.md doesn't exist in the mirror yet — a new bundled file.

        result = slm.sync_skill('multi-skill', repo_root=self.repo, mirror_root=self.mirror)

        self.assertIn('synced', result)
        self.assertEqual(
            (self.mirror / 'multi-skill' / 'references' / 'notes.md').read_text(encoding='utf-8'),
            'notes v2\n',
        )

    def test_non_bundled_files_are_not_copied(self):
        # PACKAGING-NOTE.md and versions/ are excluded from every bundle
        # (package_skills.is_bundled) — the mirror sync must respect the same
        # rule as the packager, not ship repo-reader-only or archival content.
        _write(self.repo / 'noted-skill' / 'SKILL.md', 'name: noted-skill\ncontent\n')
        _write(self.repo / 'noted-skill' / 'PACKAGING-NOTE.md', 'internal note\n')
        _write(self.repo / 'noted-skill' / 'versions' / 'old.md', 'archived\n')
        _write(self.mirror / 'noted-skill' / 'SKILL.md', 'name: noted-skill\ncontent\n')

        slm.sync_skill('noted-skill', repo_root=self.repo, mirror_root=self.mirror)

        self.assertFalse((self.mirror / 'noted-skill' / 'PACKAGING-NOTE.md').exists())
        self.assertFalse((self.mirror / 'noted-skill' / 'versions').exists())


class SweepAll(FixtureTestCase):
    """2026-09-22: main advances by merge/pull/rebase far more often than by a
    plain commit, and git runs post-merge/post-rewrite for those -- never
    post-commit. 16 local mirrors sat stale behind merged branches (e.g.
    acquisition-underwriting v4.20 vs repo v4.22). sweep_all() is the
    history-independent repair: compare every existing mirror to the repo."""

    def setUp(self):
        super().setUp()
        self.backup = self.tmp / 'backup'

    def _sweep(self, check=False):
        return slm.sweep_all(repo_root=self.repo, mirror_root=self.mirror,
                             backup_root=self.backup, check=check)

    def test_repairs_every_drifted_mirror_and_skips_unmirrored(self):
        _write(self.repo / 'a-skill' / 'SKILL.md', 'a v2\n')
        _write(self.mirror / 'a-skill' / 'SKILL.md', 'a v1\n')
        _write(self.repo / 'b-skill' / 'SKILL.md', 'b\n')
        _write(self.mirror / 'b-skill' / 'SKILL.md', 'b\n')
        _write(self.repo / 'c-skill' / 'SKILL.md', 'c\n')  # never mirrored

        drifted = self._sweep()

        self.assertEqual(drifted, ['a-skill'])
        self.assertEqual((self.mirror / 'a-skill' / 'SKILL.md').read_text(encoding='utf-8'), 'a v2\n')
        self.assertFalse((self.mirror / 'c-skill').exists())

    def test_check_mode_reports_without_writing(self):
        _write(self.repo / 'a-skill' / 'SKILL.md', 'a v2\n')
        _write(self.mirror / 'a-skill' / 'SKILL.md', 'a v1\n')

        drifted = self._sweep(check=True)

        self.assertEqual(drifted, ['a-skill'])
        self.assertEqual((self.mirror / 'a-skill' / 'SKILL.md').read_text(encoding='utf-8'), 'a v1\n')
        self.assertFalse(self.backup.exists())

    def test_overwritten_mirror_file_is_backed_up_first(self):
        # A mirror edited in place (a REPO-FIRST violation) must never be lost.
        _write(self.repo / 'a-skill' / 'SKILL.md', 'repo\n')
        _write(self.mirror / 'a-skill' / 'SKILL.md', 'hand-edited mirror\n')

        self._sweep()

        backups = list(self.backup.rglob('SKILL.md'))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_text(encoding='utf-8'), 'hand-edited mirror\n')

    def test_crlf_only_difference_is_not_drift(self):
        _write(self.repo / 'a-skill' / 'SKILL.md', 'line\n')
        _write(self.mirror / 'a-skill' / 'SKILL.md', 'line\r\n')

        self.assertEqual(self._sweep(check=True), [])


class SweepSafety(FixtureTestCase):
    def test_mirror_dirs_without_repo_counterpart_are_untouched(self):
        # ~/.claude/skills holds synced/ and _archive_* trees that are not skills.
        _write(self.mirror / 'synced' / 'x' / 'SKILL.md', 'platform copy\n')
        _write(self.mirror / '_archive_2026' / 'old' / 'SKILL.md', 'retired\n')
        self.assertEqual(slm.sweep_all(repo_root=self.repo, mirror_root=self.mirror,
                                       backup_root=self.tmp / 'b'), [])
        self.assertEqual((self.mirror / 'synced' / 'x' / 'SKILL.md').read_text(encoding='utf-8'),
                         'platform copy\n')

    def test_skill_with_uncommitted_changes_is_skipped(self):
        # A pull on a dirty main must not push unreviewed WIP into the live mirror.
        _write(self.repo / 'a-skill' / 'SKILL.md', 'wip\n')
        _write(self.mirror / 'a-skill' / 'SKILL.md', 'committed\n')
        with unittest.mock.patch.object(slm, 'dirty_skills', return_value={'a-skill'}):
            drifted = slm.sweep_all(repo_root=self.repo, mirror_root=self.mirror,
                                    backup_root=self.tmp / 'b')
        self.assertEqual(drifted, [])
        self.assertEqual((self.mirror / 'a-skill' / 'SKILL.md').read_text(encoding='utf-8'),
                         'committed\n')


class MainBranchGuard(unittest.TestCase):
    def test_sweep_refuses_detached_head(self):
        # post-rewrite can fire mid-rebase, when HEAD is detached.
        with unittest.mock.patch.object(slm, 'current_branch', return_value='HEAD'), \
             unittest.mock.patch.object(slm, 'sweep_all') as sweep:
            slm.main(['--all'])
        sweep.assert_not_called()

    def test_sweep_refuses_off_main(self):
        # A stale feature worktree must never roll live mirrors back.
        with unittest.mock.patch.object(slm, 'current_branch', return_value='fix/old'), \
             unittest.mock.patch.object(slm, 'sweep_all') as sweep:
            rc = slm.main(['--all'])
        sweep.assert_not_called()
        self.assertEqual(rc, 0)

    def test_check_runs_on_any_branch(self):
        with unittest.mock.patch.object(slm, 'current_branch', return_value='fix/old'), \
             unittest.mock.patch.object(slm, 'sweep_all', return_value=['x']) as sweep:
            rc = slm.main(['--all', '--check'])
        sweep.assert_called_once()
        self.assertEqual(rc, 1)


class PerCommitGuard(unittest.TestCase):
    """Cross-repo audit 2026-11-23 (HIGH): the post-commit hook ran the per-commit sync on
    EVERY branch and worktree, so unreviewed feature-branch (or uncommitted) skill content
    became the live Code-surface skill. Only the canonical checkout on main may write, and a
    skill with uncommitted changes is skipped (same rules as the --all sweep)."""

    def _main(self, canonical, dirty=frozenset()):
        with unittest.mock.patch.object(slm, 'is_canonical_checkout', return_value=canonical), \
             unittest.mock.patch.object(slm, 'dirty_skills', return_value=set(dirty)), \
             unittest.mock.patch.object(slm, 'changed_files', return_value=['a-skill/SKILL.md', 'b-skill/SKILL.md']), \
             unittest.mock.patch.object(slm, 'affected_skills', return_value={'a-skill', 'b-skill'}), \
             unittest.mock.patch.object(slm, 'sync_skill', return_value='synced') as sync:
            rc = slm.main(['HEAD'])
        return rc, sorted(c.args[0] for c in sync.call_args_list)

    def test_feature_branch_or_worktree_commit_does_not_touch_live_mirrors(self):
        rc, synced = self._main(canonical=False)
        self.assertEqual(rc, 0)
        self.assertEqual(synced, [])

    def test_canonical_main_commit_still_syncs(self):
        rc, synced = self._main(canonical=True)
        self.assertEqual((rc, synced), (0, ['a-skill', 'b-skill']))

    def test_skill_with_uncommitted_changes_is_skipped_per_commit(self):
        rc, synced = self._main(canonical=True, dirty={'a-skill'})
        self.assertEqual((rc, synced), (0, ['b-skill']))

    def test_all_sweep_runs_on_the_canonical_checkout_on_main(self):
        # Review 2026-11-23 (M6): a regression that silently skips every post-merge sweep must fail.
        with unittest.mock.patch.object(slm, 'is_canonical_checkout', return_value=True), \
             unittest.mock.patch.object(slm, 'current_branch', return_value='main'), \
             unittest.mock.patch.object(slm, 'sweep_all', return_value=[]) as sweep:
            self.assertEqual(slm.main(['--all']), 0)
        sweep.assert_called_once()

    def test_all_sweep_also_requires_the_canonical_checkout(self):
        with unittest.mock.patch.object(slm, 'is_canonical_checkout', return_value=False), \
             unittest.mock.patch.object(slm, 'current_branch', return_value='main'), \
             unittest.mock.patch.object(slm, 'sweep_all') as sweep:
            self.assertEqual(slm.main(['--all']), 0)
        sweep.assert_not_called()


class CanonicalCheckout(unittest.TestCase):
    """is_canonical_checkout against REAL repos: primary on main -> True; a linked worktree, or
    the primary on another branch -> False; not a repo -> False (fail closed)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='slm-canon-'))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.repo = self.tmp / 'repo'
        self.repo.mkdir()
        for args in (['init', '-q', '-b', 'main'], ['config', 'user.email', 't@t'],
                     ['config', 'user.name', 't'], ['commit', '-q', '--allow-empty', '-m', 'x']):
            subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)

    def test_primary_on_main_is_canonical(self):
        self.assertTrue(slm.is_canonical_checkout(self.repo))

    def test_linked_worktree_is_not_canonical(self):
        wt = self.tmp / 'wt'
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-q', '-b', 'feat', str(wt)],
                       check=True, capture_output=True)
        self.assertFalse(slm.is_canonical_checkout(wt))

    def test_primary_on_another_branch_is_not_canonical(self):
        subprocess.run(['git', '-C', str(self.repo), 'checkout', '-q', '-b', 'feat'],
                       check=True, capture_output=True)
        self.assertFalse(slm.is_canonical_checkout(self.repo))

    def test_linked_worktree_on_main_is_not_canonical(self):
        # Review 2026-11-23 (M3): pins the git-dir == common-dir half of the rule; the branch
        # check alone would call this worktree canonical.
        subprocess.run(['git', '-C', str(self.repo), 'checkout', '-q', '-b', 'feat2'],
                       check=True, capture_output=True)
        wt = self.tmp / 'wt-main'
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-q', str(wt), 'main'],
                       check=True, capture_output=True)
        self.assertFalse(slm.is_canonical_checkout(wt))

    def test_not_a_repo_is_not_canonical(self):
        plain = self.tmp / 'plain'
        plain.mkdir()
        with unittest.mock.patch.dict('os.environ', {'GIT_CEILING_DIRECTORIES': str(self.tmp)}):
            self.assertFalse(slm.is_canonical_checkout(plain))


class DirtySkills(unittest.TestCase):
    """dirty_skills against a REAL repo (review 2026-11-23, C2: two leaks)."""

    def setUp(self):
        self.repo = Path(tempfile.mkdtemp(prefix='slm-dirty-'))
        self.addCleanup(shutil.rmtree, self.repo, True)
        _write(self.repo / 'other' / 'leak.md', 'x\n')
        _write(self.repo / 'daily-brief' / 'SKILL.md', 'v1\n')
        _write(self.repo / 'target-markets.json', '{"v": 1}\n')
        _write(self.repo / 'my skill' / 'SKILL.md', 'v1\n')
        for args in (['init', '-q', '-b', 'main'], ['config', 'user.email', 't@t'],
                     ['config', 'user.name', 't'], ['add', '-A'], ['commit', '-q', '-m', 'base']):
            subprocess.run(['git', '-C', str(self.repo), *args], check=True, capture_output=True)

    def test_clean_repo_has_no_dirty_skills(self):
        self.assertEqual(slm.dirty_skills(self.repo), set())

    def test_staged_rename_marks_the_DESTINATION_skill_dirty(self):
        subprocess.run(['git', '-C', str(self.repo), 'mv', 'other/leak.md', 'daily-brief/leak.md'],
                       check=True, capture_output=True)
        dirty = slm.dirty_skills(self.repo)
        self.assertIn('daily-brief', dirty)
        self.assertIn('other', dirty)

    def test_dirty_shared_dependency_marks_every_consumer_dirty(self):
        _write(self.repo / 'target-markets.json', '{"v": "UNCOMMITTED"}\n')
        dirty = slm.dirty_skills(self.repo)
        for consumer in ('daily-brief', 'deal-comparison', 'market-monitor', 'acquisition-underwriting'):
            self.assertIn(consumer, dirty)

    def test_path_with_spaces_is_parsed(self):
        _write(self.repo / 'my skill' / 'SKILL.md', 'v2\n')
        self.assertIn('my skill', slm.dirty_skills(self.repo))


class Main(unittest.TestCase):
    def test_no_affected_skills_does_not_raise(self):
        # A commit touching nothing skill-shaped (empty affected_skills()) must
        # be a silent no-op, matching pending_reimport's own non-blocking design.
        with unittest.mock.patch.object(slm, 'changed_files', return_value=['README.md']):
            slm.main()  # must not raise


if __name__ == '__main__':
    unittest.main()
