"""Regression tests for reimport_correlate.py's ABSENT-baseline handling.

Stdlib only — run with `python tools/test_reimport_correlate.py` (no pytest).

Covers the 2026-09-11 fix (ORA Setup Audit R25 remediation, vendor-management's
first-ever publish): `baseline` previously SKIPPED a skill with no cache dir
yet (first install), silently leaving `verify` with NO-BASELINE later and
forcing a manual `--baseline "YYYY-MM-DD HH:MM:SS"` override for exactly the
case -- a brand-new publish -- this tool exists to make routine. These tests
build synthetic cache/log fixture trees (never the real AppData runtime cache
or main.log) so they're deterministic regardless of live install state.
"""
import importlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_reimport as pr  # noqa: E402
import reimport_correlate as rc  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='')


def _git(repo: Path, *args: str) -> None:
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)


def _rmtree(path: Path) -> None:
    """git writes object files read-only; on Windows rmtree cannot unlink them and
    ignore_errors=True leaks the whole fixture silently. Clear the bit and retry;
    still best-effort, so a locked file never fails a test."""
    def _retry(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:  # onexc can also hand over os.open/os.close
            pass
    shutil.rmtree(pr._win_long(path), onexc=_retry)


class FixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='reimport_correlate_test_'))
        self.cache = self.tmp / 'cache'
        self.baselines = self.tmp / 'baselines'
        self.local_log = self.tmp / 'local_main.log'
        self.roaming_log = self.tmp / 'roaming_main.log'
        self.cache.mkdir()
        self.patches = [
            unittest.mock.patch.object(rc, 'CACHE_ROOT', self.cache),
            unittest.mock.patch.object(rc, 'BASELINE_DIR', self.baselines),
            unittest.mock.patch.object(rc, 'LOCAL_LOG', self.local_log),
            unittest.mock.patch.object(rc, 'ROAMING_LOG', self.roaming_log),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        _rmtree(self.tmp)

    def _run(self, func, *args):
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc_result = func(*args)
        return rc_result, buf.getvalue()


class BaselineAbsentCache(FixtureTestCase):
    """cmd_baseline against a skill with no cache dir -- the first-install case."""

    def test_records_absent_baseline_instead_of_skipping(self):
        code, out = self._run(rc.cmd_baseline, ['never-installed-skill'])

        self.assertEqual(code, 0)
        path = self.baselines / 'never-installed-skill.json'
        self.assertTrue(path.is_file(), 'baseline file must be written even when absent')
        data = json.loads(path.read_text())
        self.assertIsNone(data['creation_time'])
        self.assertIn('ABSENT', out)

    def test_normal_skill_still_baselines_its_creation_time(self):
        (self.cache / 'installed-skill').mkdir()

        code, out = self._run(rc.cmd_baseline, ['installed-skill'])

        self.assertEqual(code, 0)
        data = json.loads((self.baselines / 'installed-skill.json').read_text())
        self.assertIsNotNone(data['creation_time'])
        self.assertNotIn('ABSENT', out)


class VerifyAbsentBaseline(FixtureTestCase):
    """cmd_verify's handling of an ABSENT baseline -- both the still-absent
    (nothing happened) and now-present (first install just happened) cases."""

    def test_still_absent_reads_no_change_not_no_cache(self):
        _write(self.baselines / 'never-installed-skill.json',
               json.dumps({'skill': 'never-installed-skill', 'creation_time': None}))

        code, out = self._run(rc.cmd_verify, ['never-installed-skill'], None)

        self.assertEqual(code, 0, 'a resolved ABSENT baseline must not count as a failure')
        self.assertIn('NO-CHANGE', out)
        self.assertNotIn('NO-BASELINE', out)
        self.assertNotIn('NO-CACHE', out)

    def test_no_baseline_file_at_all_is_still_no_baseline(self):
        # Distinguish "baseline never taken" from "baseline taken and recorded
        # ABSENT" -- both currently have no cache dir, but only the latter
        # should read as a resolved, non-failing NO-CHANGE.
        code, out = self._run(rc.cmd_verify, ['untouched-skill'], None)

        self.assertEqual(code, 1)
        self.assertIn('NO-CACHE', out)

    def test_first_install_confirmed_via_exact_second_log_match(self):
        _write(self.baselines / 'vendor-management.json',
               json.dumps({'skill': 'vendor-management', 'creation_time': None}))
        (self.cache / 'vendor-management').mkdir()
        # Backdate the just-created dir's ctime is not portable across platforms,
        # so instead pin the correlation window via an explicit --baseline
        # override path is exercised separately below; here we only need the
        # log line to land within TOLERANCE of the dir's real (just-now) ctime.
        ctime = rc._creation_time('vendor-management')
        ts = ctime.strftime('%Y-%m-%d %H:%M:%S')
        _write(self.local_log,
               f'{ts} [info] [SkillsPlugin] Delta: 3 to download\n'
               f'{ts} [info] [SkillsPlugin] Sync complete: 3 downloaded, 0 failed\n')

        code, out = self._run(rc.cmd_verify, ['vendor-management'], None)

        self.assertEqual(code, 0)
        self.assertIn('CONFIRMED', out)
        self.assertIn('(first install)', out)

    def test_first_install_with_no_log_match_is_moved_only(self):
        _write(self.baselines / 'vendor-management.json',
               json.dumps({'skill': 'vendor-management', 'creation_time': None}))
        (self.cache / 'vendor-management').mkdir()
        # No log files written at all -- nothing to corroborate with.

        code, out = self._run(rc.cmd_verify, ['vendor-management'], None)

        self.assertEqual(code, 0)
        self.assertIn('MOVED-ONLY', out)
        self.assertIn('(first install)', out)

    def test_explicit_baseline_override_still_works_for_first_install(self):
        # No baseline file at all -- an ad hoc --baseline covering a skill that
        # has never had a cache dir until just now.
        (self.cache / 'vendor-management').mkdir()

        code, out = self._run(rc.cmd_verify, ['vendor-management'], '2020-01-01 00:00:00')

        self.assertEqual(code, 0)
        self.assertIn('MOVED-ONLY', out)
        self.assertNotIn('(first install)', out, '--baseline path is not the ABSENT path')


class VerifyOrdinaryMoveUnaffected(FixtureTestCase):
    """Regression guard: a skill that already had a cache dir at baseline time
    must keep going through the ordinary (non-ABSENT) branch unchanged."""

    def test_unchanged_creation_time_is_no_change(self):
        (self.cache / 'daily-brief').mkdir()
        ct = rc._creation_time('daily-brief')
        _write(self.baselines / 'daily-brief.json',
               json.dumps({'skill': 'daily-brief', 'creation_time': ct.isoformat()}))

        code, out = self._run(rc.cmd_verify, ['daily-brief'], None)

        self.assertEqual(code, 0)
        self.assertIn('NO-CHANGE', out)
        self.assertNotIn('(first install)', out)

    def test_cache_dir_removed_after_a_real_baseline_is_no_cache_not_no_change(self):
        _write(self.baselines / 'daily-brief.json',
               json.dumps({'skill': 'daily-brief',
                           'creation_time': '2026-01-01T00:00:00'}))
        # cache dir never created this time -- simulates an uninstall/cache-root move.

        code, out = self._run(rc.cmd_verify, ['daily-brief'], None)

        self.assertEqual(code, 1)
        self.assertIn('NO-CACHE', out)
        self.assertNotIn('NO-CHANGE', out)


class BaselineDirResolvesToPrimaryCheckout(unittest.TestCase):
    """A baseline is taken in the packaging pre-check and read back by `verify`
    after the Save-skill reimport -- often after the packaging worktree has been
    removed. Resolved against that worktree, BASELINE_DIR dies with
    `git worktree remove` and `verify` degrades to NO-BASELINE. The module is
    reloaded with REPO pointed at a real fixture worktree, so a revert to a
    REPO-relative path fails whether the suite runs from a worktree or the primary."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='reimport_correlate_test_'))
        self.addCleanup(_rmtree, self.tmp)
        self.repo, self.wt, self.cache = self.tmp / 'repo', self.tmp / 'wt', self.tmp / 'cache'
        self.repo.mkdir()
        self.cache.mkdir()
        _git(self.repo, 'init', '-q')
        _git(self.repo, '-c', 'user.name=t', '-c', 'user.email=t@t',
             'commit', '-q', '--allow-empty', '-m', 'init')
        _git(self.repo, 'worktree', 'add', '-q', str(self.wt))
        self.addCleanup(importlib.reload, rc)
        with unittest.mock.patch.object(pr, 'REPO', self.wt):
            importlib.reload(rc)

    def test_baseline_survives_worktree_remove(self):
        with unittest.mock.patch.object(rc, 'CACHE_ROOT', self.cache), redirect_stdout(io.StringIO()):
            rc.cmd_baseline(['demo-skill'])
        _git(self.repo, 'worktree', 'remove', '--force', str(self.wt))

        saved = self.repo / '_staging' / 'reimport-baselines' / 'demo-skill.json'
        self.assertEqual(json.loads(saved.read_text(encoding='utf-8'))['skill'], 'demo-skill')

    def test_repo_stays_the_checkouts_own_root(self):
        self.assertEqual(rc.REPO, self.wt)


if __name__ == '__main__':
    unittest.main()
