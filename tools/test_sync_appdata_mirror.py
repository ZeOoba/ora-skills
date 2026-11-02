#!/usr/bin/env python3
"""Regression tests for sync_appdata_mirror.py -- automates the dual-write
discipline the README previously documented as manual-only. Verifies: mirror
discovery is glob-based (not a hardcoded uuid pair), a skill with no
installed mirror is reported informationally rather than erroring, sync is
additive-only (a pre-existing untracked file in the mirror survives), and
check_staged() never propagates a copy failure into a non-zero exit (a
mirror-sync hiccup must never block a commit).

Stdlib only — run with `python tools/test_sync_appdata_mirror.py`.
"""
import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sync_appdata_mirror import check_staged, discover_mirror_dirs, sync_changed_range, sync_skill


def _rmtree(path) -> None:
    """git writes object files read-only, which rmtree cannot unlink on Windows --
    with ignore_errors=True every git-backed fixture here leaked silently into %TEMP%.
    Clear the bit and retry; still best-effort, so a locked file never fails a test.
    (Same helper as PR #79 adds to tools/test_pending_reimport.py.)"""
    def _retry(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:  # onexc can also hand over os.open/os.close
            pass
    shutil.rmtree(path, onexc=_retry)


class DiscoverMirrorDirsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(_rmtree, self.tmp)

    def test_no_appdata_root_returns_empty(self):
        self.assertEqual(discover_mirror_dirs('some-skill', appdata=None), [])

    def test_missing_skills_plugin_dir_returns_empty(self):
        # self.tmp exists but has no Claude/local-agent-mode-sessions/skills-plugin subtree.
        self.assertEqual(discover_mirror_dirs('some-skill', appdata=self.tmp), [])

    def test_finds_skill_under_any_uuid_pair_not_a_hardcoded_one(self):
        base = self.tmp / 'Claude' / 'local-agent-mode-sessions' / 'skills-plugin'
        mirror1 = base / 'uuid-a' / 'uuid-1' / 'skills' / 'my-skill'
        mirror2 = base / 'uuid-b' / 'uuid-2' / 'skills' / 'my-skill'
        mirror1.mkdir(parents=True)
        mirror2.mkdir(parents=True)
        (base / 'uuid-a' / 'uuid-1' / 'skills' / 'other-skill').mkdir(parents=True)

        found = discover_mirror_dirs('my-skill', appdata=self.tmp)
        self.assertEqual(found, sorted([mirror1, mirror2]))

    def test_skill_not_installed_anywhere_returns_empty(self):
        base = self.tmp / 'Claude' / 'local-agent-mode-sessions' / 'skills-plugin'
        (base / 'uuid-a' / 'uuid-1' / 'skills' / 'other-skill').mkdir(parents=True)
        self.assertEqual(discover_mirror_dirs('my-skill', appdata=self.tmp), [])


class SyncSkillTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(_rmtree, self.tmp)
        self.repo_root = self.tmp / 'repo'
        self.skill_dir = self.repo_root / 'my-skill'
        (self.skill_dir / 'references').mkdir(parents=True)
        (self.skill_dir / 'SKILL.md').write_text('---\nname: my-skill\ndescription: x\n---\nbody v1', encoding='utf-8')
        (self.skill_dir / 'references' / 'notes.md').write_text('note v1', encoding='utf-8')
        self.appdata = self.tmp / 'appdata'
        # Fixture repos are not git repos; direction is exercised in WriteGateTests.
        p = patch('sync_appdata_mirror.cache_verdict', return_value='REPO-AHEAD')
        p.start()
        self.addCleanup(p.stop)

    def test_no_installed_mirror_reports_informational_line_only(self):
        lines = sync_skill(self.skill_dir, appdata=self.appdata)
        self.assertEqual(len(lines), 1)
        self.assertIn('no local AppData mirror installed yet', lines[0])

    def test_syncs_into_an_existing_mirror(self):
        mirror_root = self.appdata / 'Claude' / 'local-agent-mode-sessions' / 'skills-plugin' / 'u1' / 'u2' / 'skills' / 'my-skill'
        mirror_root.mkdir(parents=True)

        lines = sync_skill(self.skill_dir, appdata=self.appdata)

        self.assertEqual(len(lines), 1)
        self.assertIn('synced 2 file(s)', lines[0])
        self.assertEqual(
            (mirror_root / 'SKILL.md').read_text(encoding='utf-8'),
            '---\nname: my-skill\ndescription: x\n---\nbody v1',
        )
        self.assertEqual((mirror_root / 'references' / 'notes.md').read_text(encoding='utf-8'), 'note v1')

    def test_sync_overwrites_stale_content_in_the_mirror(self):
        mirror_root = self.appdata / 'Claude' / 'local-agent-mode-sessions' / 'skills-plugin' / 'u1' / 'u2' / 'skills' / 'my-skill'
        mirror_root.mkdir(parents=True)
        (mirror_root / 'SKILL.md').write_text('STALE body from a prior install', encoding='utf-8')

        sync_skill(self.skill_dir, appdata=self.appdata)

        self.assertEqual(
            (mirror_root / 'SKILL.md').read_text(encoding='utf-8'),
            '---\nname: my-skill\ndescription: x\n---\nbody v1',
        )

    def test_sync_is_additive_only_leaves_untracked_mirror_files_alone(self):
        mirror_root = self.appdata / 'Claude' / 'local-agent-mode-sessions' / 'skills-plugin' / 'u1' / 'u2' / 'skills' / 'my-skill'
        mirror_root.mkdir(parents=True)
        # Simulates installer-owned metadata this module has no visibility into.
        (mirror_root / '.install-manifest.json').write_text('{"installed": true}', encoding='utf-8')

        sync_skill(self.skill_dir, appdata=self.appdata)

        self.assertTrue((mirror_root / '.install-manifest.json').exists())
        self.assertEqual(
            (mirror_root / '.install-manifest.json').read_text(encoding='utf-8'),
            '{"installed": true}',
        )

    def test_syncs_into_every_installed_mirror_when_more_than_one_exists(self):
        base = self.appdata / 'Claude' / 'local-agent-mode-sessions' / 'skills-plugin'
        mirror1 = base / 'u1' / 'u2' / 'skills' / 'my-skill'
        mirror2 = base / 'u3' / 'u4' / 'skills' / 'my-skill'
        mirror1.mkdir(parents=True)
        mirror2.mkdir(parents=True)

        lines = sync_skill(self.skill_dir, appdata=self.appdata)

        expected = '---\nname: my-skill\ndescription: x\n---\nbody v1'
        self.assertEqual(len(lines), 2)
        self.assertEqual((mirror1 / 'SKILL.md').read_text(encoding='utf-8'), expected)
        self.assertEqual((mirror2 / 'SKILL.md').read_text(encoding='utf-8'), expected)


class CheckStagedNeverBlocksTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(_rmtree, self.tmp)
        self.skill_dir = self.tmp / 'my-skill'
        self.skill_dir.mkdir()
        (self.skill_dir / 'SKILL.md').write_text('---\nname: my-skill\ndescription: x\n---\nbody', encoding='utf-8')

    def test_a_copy_failure_is_reported_but_never_raises_or_blocks(self):
        with patch('sync_appdata_mirror.staged_skill_dirs', return_value=[self.skill_dir]):
            with patch('sync_appdata_mirror.sync_skill', side_effect=OSError('disk full')):
                code = check_staged(files=[])
        self.assertEqual(code, 0)

    def test_no_staged_skill_dirs_is_a_clean_noop(self):
        with patch('sync_appdata_mirror.staged_skill_dirs', return_value=[]):
            code = check_staged(files=[])
        self.assertEqual(code, 0)


class WriteGateTests(unittest.TestCase):
    """2026-09-23: Check 4 wrote the runtime cache Cowork loads from ANY branch in
    ANY worktree. A feature-branch commit (register-scheduled-task v2.29, pre-review)
    overwrote a just-installed v2.28 for 11 minutes; on 09-22 a main commit clobbered
    a platform-side pma-qc v1.3 that existed only in the cache. Writes are now gated
    on (a) the primary checkout on main and (b) the cache not being ahead of or
    divergent from the repo."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(_rmtree, self.tmp)
        self.skill_dir = self.tmp / 'repo' / 'my-skill'
        self.skill_dir.mkdir(parents=True)
        (self.skill_dir / 'SKILL.md').write_text('repo body', encoding='utf-8')
        self.appdata = self.tmp / 'appdata'
        self.mirror = self.appdata / 'Claude' / 'local-agent-mode-sessions' / 'skills-plugin' / 'u1' / 'u2' / 'skills' / 'my-skill'
        self.mirror.mkdir(parents=True)
        (self.mirror / 'SKILL.md').write_text('cache body', encoding='utf-8')

    def _sync(self, verdict):
        with patch('sync_appdata_mirror.cache_verdict', return_value=verdict):
            return sync_skill(self.skill_dir, appdata=self.appdata)

    def test_repo_ahead_cache_is_written(self):
        lines = self._sync('REPO-AHEAD')
        self.assertEqual((self.mirror / 'SKILL.md').read_text(encoding='utf-8'), 'repo body')
        self.assertIn('synced', lines[0])

    def test_in_sync_cache_is_written(self):
        self._sync('IN-SYNC')
        self.assertEqual((self.mirror / 'SKILL.md').read_text(encoding='utf-8'), 'repo body')

    def test_unsafe_directions_never_overwrite_the_cache(self):
        for verdict in ('CACHE-AHEAD', 'DIVERGENT', 'REPO-MISSING', 'MAIN-BEHIND-ORIGIN', 'UNKNOWN'):
            with self.subTest(verdict=verdict):
                (self.mirror / 'SKILL.md').write_text('cache body', encoding='utf-8')
                lines = self._sync(verdict)
                self.assertEqual((self.mirror / 'SKILL.md').read_text(encoding='utf-8'), 'cache body')
                self.assertIn(verdict, lines[0])
                self.assertIn('NOT written', lines[0])

    def test_classifier_error_fails_closed(self):
        with patch('sync_appdata_mirror.cache_verdict', side_effect=RuntimeError('git gone')):
            lines = sync_skill(self.skill_dir, appdata=self.appdata)
        self.assertEqual((self.mirror / 'SKILL.md').read_text(encoding='utf-8'), 'cache body')
        self.assertIn('NOT written', lines[0])


class CanonicalCheckoutGateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(_rmtree, self.tmp)
        self.skill_dir = self.tmp / 'my-skill'
        self.skill_dir.mkdir()

    def _check_staged(self, canonical):
        with patch('sync_appdata_mirror.staged_skill_dirs', return_value=[self.skill_dir]), \
             patch('sync_appdata_mirror.is_canonical_checkout', return_value=canonical), \
             patch('sync_appdata_mirror.sync_skill', return_value=['x: synced']) as sync:
            code = check_staged(files=[])
        return code, sync

    def test_feature_branch_or_linked_worktree_defers_the_write(self):
        code, sync = self._check_staged(canonical=False)
        sync.assert_not_called()
        self.assertEqual(code, 0)

    def test_primary_checkout_on_main_writes(self):
        code, sync = self._check_staged(canonical=True)
        sync.assert_called_once()
        self.assertEqual(code, 0)

    def test_changed_range_syncs_skills_a_merge_brought_in(self):
        # A fast-forward/merge on main runs no pre-commit hook; post-merge covers it.
        with patch('sync_appdata_mirror.is_canonical_checkout', return_value=True), \
             patch('sync_appdata_mirror.skills_changed_between', return_value=[self.skill_dir]), \
             patch('sync_appdata_mirror.sync_skill', return_value=['x: synced']) as sync:
            code = sync_changed_range('ORIG_HEAD', 'HEAD')
        sync.assert_called_once_with(self.skill_dir)
        self.assertEqual(code, 0)

    def test_changed_range_off_main_is_a_noop(self):
        with patch('sync_appdata_mirror.is_canonical_checkout', return_value=False), \
             patch('sync_appdata_mirror.skills_changed_between') as changed, \
             patch('sync_appdata_mirror.sync_skill') as sync:
            sync_changed_range('ORIG_HEAD', 'HEAD')
        sync.assert_not_called()
        changed.assert_not_called()


class RealClassifierIntegrationTests(unittest.TestCase):
    """End-to-end through the REAL repo_first_check.classify_skill on a throwaway git
    repo (review finding 2026-09-23: patched verdicts hid a skill-level REPO-MISSING
    that permanently disabled syncing after any shipped-file deletion)."""

    def setUp(self):
        import subprocess
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(_rmtree, self.tmp)
        self.repo = self.tmp / 'repo'
        self.skill = self.repo / 'my-skill'
        (self.skill / 'scripts').mkdir(parents=True)
        self.git = lambda *a: subprocess.run(['git', '-C', str(self.repo), *a], check=True,
                                             capture_output=True)
        self.git('init', '-q')
        for k, v in (('user.email', 't@t.invalid'), ('user.name', 't'), ('core.autocrlf', 'false')):
            self.git('config', k, v)
        (self.skill / 'SKILL.md').write_text('---\nname: my-skill\ndescription: x\n---\nv1\n', encoding='utf-8')
        (self.skill / 'scripts' / 'old.py').write_text('print(1)\n', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'v1')
        self.appdata = self.tmp / 'appdata'
        self.mirror = self.appdata / 'Claude' / 'local-agent-mode-sessions' / 'skills-plugin' / 'u1' / 'u2' / 'skills' / 'my-skill'
        shutil.copytree(self.skill, self.mirror)  # cache == HEAD

    def _mirror_skill_md(self):
        return (self.mirror / 'SKILL.md').read_text(encoding='utf-8')

    def test_ordinary_edit_is_written(self):
        (self.skill / 'SKILL.md').write_text('---\nname: my-skill\ndescription: x\n---\nv2\n', encoding='utf-8')
        lines = sync_skill(self.skill, appdata=self.appdata)
        self.assertIn('synced', lines[0], lines)
        self.assertIn('v2', self._mirror_skill_md())

    def test_deleted_shipped_file_does_not_disable_future_syncs(self):
        (self.skill / 'scripts' / 'old.py').unlink()
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'drop old.py')
        (self.skill / 'SKILL.md').write_text('---\nname: my-skill\ndescription: x\n---\nv3\n', encoding='utf-8')
        lines = sync_skill(self.skill, appdata=self.appdata)
        self.assertIn('synced', lines[0], lines)
        self.assertIn('v3', self._mirror_skill_md())
        self.assertTrue((self.mirror / 'scripts' / 'old.py').exists())  # additive: never deleted

    def test_platform_edit_to_a_script_blocks_even_beside_a_cache_only_file(self):
        (self.mirror / 'scripts' / 'old.py').write_text('print("platform")\n', encoding='utf-8')
        (self.mirror / 'scripts' / 'junk.py').write_text('cache only\n', encoding='utf-8')
        (self.skill / 'SKILL.md').write_text('---\nname: my-skill\ndescription: x\n---\nv2\n', encoding='utf-8')
        lines = sync_skill(self.skill, appdata=self.appdata)
        self.assertIn('CACHE-AHEAD', lines[0], lines)
        self.assertNotIn('v2', self._mirror_skill_md())
        self.assertIn('platform', (self.mirror / 'scripts' / 'old.py').read_text(encoding='utf-8'))

    def test_runtime_state_in_mirror_does_not_disable_syncs(self):
        # merge-gate PR #196: run state that exists ONLY in the mirror must never
        # block the sync. The sync is additive and is_bundled() excludes runs/ and
        # .pytest_cache/, so mirror-only run state is neither compared nor removed.
        (self.repo / '.gitignore').write_text('.pytest_cache/\nmy-skill/runs/\n', encoding='utf-8')
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'ignore run state')
        (self.mirror / '.pytest_cache').mkdir()
        (self.mirror / '.pytest_cache' / 'README.md').write_text('x\n', encoding='utf-8')
        (self.mirror / 'runs').mkdir()
        (self.mirror / 'runs' / 'x.json').write_text('{}\n', encoding='utf-8')
        (self.skill / 'SKILL.md').write_text('---\nname: my-skill\ndescription: x\n---\nv2\n', encoding='utf-8')
        lines = sync_skill(self.skill, appdata=self.appdata)
        self.assertIn('synced', lines[0], lines)
        self.assertIn('v2', self._mirror_skill_md())
        self.assertTrue((self.mirror / 'runs' / 'x.json').exists())  # additive: run state kept

    def test_repo_run_state_is_never_copied_into_the_mirror(self):
        # root cause (merge-gate round 2): the sync and the packager shipped the
        # working tree's runs/ and .pytest_cache/ into the installed copy.
        (self.skill / 'runs').mkdir()
        (self.skill / 'runs' / 'x.json').write_text('{}\n', encoding='utf-8')
        (self.skill / '.pytest_cache').mkdir()
        (self.skill / '.pytest_cache' / 'README.md').write_text('x\n', encoding='utf-8')
        (self.skill / 'SKILL.md').write_text('---\nname: my-skill\ndescription: x\n---\nv2\n', encoding='utf-8')
        lines = sync_skill(self.skill, appdata=self.appdata)
        self.assertIn('synced', lines[0], lines)
        self.assertIn('v2', self._mirror_skill_md())
        self.assertFalse((self.mirror / 'runs').exists())
        self.assertFalse((self.mirror / '.pytest_cache').exists())

    def test_uncommitted_platform_edit_is_not_overwritten(self):
        (self.mirror / 'SKILL.md').write_text('---\nname: my-skill\ndescription: x\n---\nPLATFORM EDIT\n', encoding='utf-8')
        (self.skill / 'SKILL.md').write_text('---\nname: my-skill\ndescription: x\n---\nv2\n', encoding='utf-8')
        lines = sync_skill(self.skill, appdata=self.appdata)
        self.assertIn('NOT written', lines[0], lines)
        self.assertIn('PLATFORM EDIT', self._mirror_skill_md())


class FixtureCleanupRemovesGitRepos(unittest.TestCase):
    """git writes object files read-only; rmtree(ignore_errors=True) skipped them on
    Windows and every RealClassifierIntegrationTests fixture leaked into %TEMP%."""

    def test_cleanup_removes_the_committed_fixture_repo(self):
        fx = RealClassifierIntegrationTests('test_ordinary_edit_is_written')
        fx.setUp()
        fx.doCleanups()

        self.assertFalse(fx.tmp.exists())


if __name__ == '__main__':
    unittest.main()
