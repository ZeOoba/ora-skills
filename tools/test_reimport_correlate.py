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
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_reimport as pr  # noqa: E402
import reimport_correlate as rc  # noqa: E402
import reimport_cycle as cyc  # noqa: E402


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
        path = rc._baseline_path('never-installed-skill')
        self.assertTrue(path.is_file(), 'baseline file must be written even when absent')
        data = json.loads(path.read_text())
        self.assertIsNone(data['creation_time'])
        self.assertIn('ABSENT', out)

    def test_normal_skill_still_baselines_its_creation_time(self):
        (self.cache / 'installed-skill').mkdir()

        code, out = self._run(rc.cmd_baseline, ['installed-skill'])

        self.assertEqual(code, 0)
        data = json.loads((rc._baseline_path('installed-skill')).read_text())
        self.assertIsNotNone(data['creation_time'])
        self.assertNotIn('ABSENT', out)


class VerifyAbsentBaseline(FixtureTestCase):
    """cmd_verify's handling of an ABSENT baseline -- both the still-absent
    (nothing happened) and now-present (first install just happened) cases."""

    def test_still_absent_reads_no_change_not_no_cache(self):
        _write(rc._baseline_path('never-installed-skill'),
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
        _write(rc._baseline_path('vendor-management'),
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
        _write(rc._baseline_path('vendor-management'),
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
        _write(rc._baseline_path('daily-brief'),
               json.dumps({'skill': 'daily-brief', 'creation_time': ct.isoformat()}))

        code, out = self._run(rc.cmd_verify, ['daily-brief'], None)

        self.assertEqual(code, 0)
        self.assertIn('NO-CHANGE', out)
        self.assertNotIn('(first install)', out)

    def test_cache_dir_removed_after_a_real_baseline_is_no_cache_not_no_change(self):
        _write(rc._baseline_path('daily-brief'),
               json.dumps({'skill': 'daily-brief',
                           'creation_time': '2026-01-01T00:00:00'}))
        # cache dir never created this time -- simulates an uninstall/cache-root move.

        code, out = self._run(rc.cmd_verify, ['daily-brief'], None)

        self.assertEqual(code, 1)
        self.assertIn('NO-CACHE', out)
        self.assertNotIn('NO-CHANGE', out)


def _make_pkg(path: Path, skill: str, entries: dict[str, bytes]) -> None:
    import zipfile
    with zipfile.ZipFile(path, 'w') as z:
        for name, data in entries.items():
            z.writestr(zipfile.ZipInfo(name), data)


class PrecheckTests(FixtureTestCase):
    """cmd_precheck against a synthetic repo (rc.REPO patched to a temp tree)."""

    SKILL_MD = '---\nname: demo-skill\ndescription: A demo skill.\n---\nbody\n'

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / 'repo'
        (self.repo / 'demo-skill' / 'references').mkdir(parents=True)
        _write(self.repo / 'demo-skill' / 'SKILL.md', self.SKILL_MD)
        _write(self.repo / 'demo-skill' / 'references' / 'a.md', 'ref a\n')
        _write(self.repo / 'shared.json', '{"k": 1}\n')
        for p in (unittest.mock.patch.object(rc, 'REPO', self.repo),
                  unittest.mock.patch.object(rc, '_plugin_of', lambda s: None)):
            p.start()
            self.addCleanup(p.stop)
        self.pkg = self.tmp / 'demo-skill.skill'

    def _good_entries(self):
        return {'demo-skill/SKILL.md': self.SKILL_MD.encode(),
                'demo-skill/references/a.md': b'ref a\n',
                'demo-skill/shared.json': b'{"k": 1}\n'}

    def test_good_package_passes_and_captures_baseline(self):
        _make_pkg(self.pkg, 'demo-skill', self._good_entries())
        code, out = self._run(rc.cmd_precheck, [str(self.pkg)])
        self.assertEqual(code, 0, out)
        self.assertIn('PRECHECK OK', out)
        self.assertIn('1 shared root dep', out)
        self.assertIn('baseline CAPTURED', out)
        self.assertTrue((rc._baseline_path('demo-skill')).is_file())

    def test_existing_baseline_is_never_overwritten(self):
        _write(rc._baseline_path('demo-skill'),
               json.dumps({'skill': 'demo-skill', 'creation_time': '2026-01-01T00:00:00'}))
        _make_pkg(self.pkg, 'demo-skill', self._good_entries())
        code, out = self._run(rc.cmd_precheck, [str(self.pkg)])
        self.assertEqual(code, 0, out)
        self.assertIn('baseline kept (2026-01-01T00:00:00)', out)
        self.assertEqual(json.loads((rc._baseline_path('demo-skill')).read_text())['creation_time'],
                         '2026-01-01T00:00:00')

    def test_precheck_recaptures_a_baseline_an_install_has_made_stale(self):
        # Through cmd_precheck itself, not the helper: unwiring precheck from the
        # refresh must fail a test (merge-gate round 4, test-validity F3).
        _write(rc._baseline_path('demo-skill'),
               json.dumps({'skill': 'demo-skill', 'creation_time': '2026-01-01T00:00:00'}))
        _make_pkg(self.pkg, 'demo-skill', self._good_entries())

        with unittest.mock.patch.object(rc, '_creation_time',
                                        lambda s: datetime(2026, 9, 23, 12, 5, 0)):
            code, out = self._run(rc.cmd_precheck, [str(self.pkg)])

        self.assertEqual(code, 0, out)
        self.assertIn('baseline was stale', out)
        self.assertEqual(json.loads(rc._baseline_path('demo-skill').read_text())['creation_time'],
                         '2026-09-23T12:05:00')

    def test_missing_package_is_reported_missing_not_stale(self):
        code, out = self._run(rc.cmd_precheck, [str(self.tmp / 'ghost.skill')])
        self.assertEqual(code, 1)
        self.assertIn('MISSING', out)

    def test_stale_content_fails(self):
        e = self._good_entries()
        e['demo-skill/references/a.md'] = b'OLD ref a\n'
        _make_pkg(self.pkg, 'demo-skill', e)
        code, out = self._run(rc.cmd_precheck, [str(self.pkg)])
        self.assertEqual(code, 1)
        self.assertIn('MISMATCH', out)

    def test_crlf_only_difference_is_not_drift(self):
        e = self._good_entries()
        e['demo-skill/references/a.md'] = b'ref a\r\n'
        _make_pkg(self.pkg, 'demo-skill', e)
        code, out = self._run(rc.cmd_precheck, [str(self.pkg)])
        self.assertEqual(code, 0, out)

    def test_backslash_entry_fails(self):
        e = self._good_entries()
        e['demo-skill/references/b.md'] = b'x'
        _make_pkg(self.pkg, 'demo-skill', e)
        # zipfile normalizes '\\' -> '/' on Windows at write AND read time, so
        # forge the raw same-length name bytes (local header + central dir).
        data = self.pkg.read_bytes()
        self.pkg.write_bytes(data.replace(b'demo-skill/references/b.md',
                                          b'demo-skill\\references\\b.md'))
        code, out = self._run(rc.cmd_precheck, [str(self.pkg)])
        self.assertEqual(code, 1)
        self.assertIn('backslash', out)

    def test_name_dir_mismatch_and_long_description_fail(self):
        bad = '---\nname: other\ndescription: ' + 'x' * 1030 + '\n---\nb\n'
        e = self._good_entries()
        e['demo-skill/SKILL.md'] = bad.encode()
        _write(self.repo / 'demo-skill' / 'SKILL.md', bad)
        _make_pkg(self.pkg, 'demo-skill', e)
        code, out = self._run(rc.cmd_precheck, [str(self.pkg)])
        self.assertEqual(code, 1)
        self.assertIn("name 'other'", out)
        self.assertIn('/1024', out)

    def test_repo_file_missing_from_package_warns_only(self):
        _write(self.repo / 'demo-skill' / 'references' / 'extra.md', 'x\n')
        _make_pkg(self.pkg, 'demo-skill', self._good_entries())
        code, out = self._run(rc.cmd_precheck, [str(self.pkg)])
        self.assertEqual(code, 0, out)
        self.assertIn('WARN references/extra.md', out)


class PostclickTests(FixtureTestCase):
    """cmd_postclick: append happens ONLY on CONFIRMED, and only exit 0 clears."""

    def setUp(self):
        super().setUp()
        self.repo = self.tmp / 'repo'
        (self.repo / '_staging').mkdir(parents=True)
        self.calls = self.tmp / 'append_calls.txt'
        self.fake_append = self.tmp / 'fake_append.py'
        self.fake_append.write_text(
            'import sys\n'
            f'open({str(self.calls)!r}, "a").write(open(sys.argv[2]).read())\n'
            'sys.exit(int(__import__("os").environ.get("FAKE_APPEND_RC", "0")))\n')
        # PENDING is the script `--clear-ledger` runs: never let a regression reach the real one.
        self.pending_calls = self.tmp / 'pending_calls.txt'
        self.fake_pending = self.tmp / 'fake_pending.py'
        self.fake_pending.write_text(
            'import sys\n'
            f'open({str(self.pending_calls)!r}, "a").write(" ".join(sys.argv[1:]))\n')
        for p in (unittest.mock.patch.object(rc, 'REPO', self.repo),
                  unittest.mock.patch.object(rc, 'APPEND_LOG', self.fake_append),
                  unittest.mock.patch.object(rc, 'PENDING', self.fake_pending)):
            p.start()
            self.addCleanup(p.stop)

    def _confirmable(self):
        (self.cache / 'demo-skill').mkdir()
        ct = rc._creation_time('demo-skill')
        _write(rc._baseline_path('demo-skill'),
               json.dumps({'skill': 'demo-skill', 'creation_time': '2020-01-01T00:00:00'}))
        ts = ct.strftime('%Y-%m-%d %H:%M:%S')
        _write(self.local_log,
               f'{ts} [info] [SkillsPlugin] Delta: 1 to download\n'
               f'{ts} [info] [SkillsPlugin] Sync complete: 1 downloaded, 0 failed\n')

    def test_confirmed_appends_dated_entry_with_version(self):
        self._confirmable()
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.23', False, False)
        self.assertEqual(code, 0, out)
        text = self.calls.read_text()
        self.assertRegex(text, r'^## \d{4}-\d{2}-\d{2} -- demo-skill v4\.23 reimport confirmed')
        self.assertIn('demo-skill v4.23 reimported via Cowork Save-skill; reimport_correlate CONFIRMED.', text)

    def test_no_change_stops_and_appends_nothing(self):
        (self.cache / 'demo-skill').mkdir()
        ct = rc._creation_time('demo-skill')
        _write(rc._baseline_path('demo-skill'),
               json.dumps({'skill': 'demo-skill', 'creation_time': ct.isoformat()}))
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.23', False, False)
        self.assertEqual(code, 1)
        self.assertIn('STOP', out)
        self.assertFalse(self.calls.exists())

    def test_moved_only_stops_and_appends_nothing(self):
        (self.cache / 'demo-skill').mkdir()
        _write(rc._baseline_path('demo-skill'),
               json.dumps({'skill': 'demo-skill', 'creation_time': '2020-01-01T00:00:00'}))
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.23', False, False)
        self.assertEqual(code, 1)
        self.assertIn('MOVED-ONLY', out)
        self.assertFalse(self.calls.exists())

    def test_no_append_flag_verifies_only(self):
        self._confirmable()
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, True, False)
        self.assertEqual(code, 0)
        self.assertFalse(self.calls.exists())

    def test_failed_append_returns_1_and_skips_ledger_clear(self):
        self._confirmable()
        with unittest.mock.patch.dict('os.environ', {'FAKE_APPEND_RC': '1'}):
            with unittest.mock.patch.object(rc.subprocess, 'run', wraps=rc.subprocess.run) as run:
                code, out = self._run(rc.cmd_postclick, 'demo-skill', '1.0', False, True)
        self.assertEqual(code, 1)
        self.assertIn('ledger NOT cleared', out)
        self.assertFalse(any('clear' in [str(a) for a in c.args[0]] for c in run.call_args_list))


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

        saved = (self.repo / '_staging' / 'reimport-baselines' / 'demo-skill'
                 / f'{rc._session_key()}.json')
        self.assertEqual(json.loads(saved.read_text(encoding='utf-8'))['skill'], 'demo-skill')

    def test_repo_stays_the_checkouts_own_root(self):
        self.assertEqual(rc.REPO, self.wt)


class _SessionFixture(FixtureTestCase):
    """Controlled CreationTime + fake append + per-session runner. No tests of its own."""

    def setUp(self):
        super().setUp()
        self.ct = {'demo-skill': datetime(2026, 9, 23, 12, 0, 0)}
        p = unittest.mock.patch.object(rc, '_creation_time', lambda s: self.ct.get(s))
        p.start()
        self.addCleanup(p.stop)
        self.repo = self.tmp / 'repo'
        (self.repo / '_staging').mkdir(parents=True)
        self.calls = self.tmp / 'append_calls.txt'
        self.fake_append = self.tmp / 'fake_append.py'
        self.fake_append.write_text(
            'import sys\n'
            f'open({str(self.calls)!r}, "a").write(open(sys.argv[2]).read())\n'
            'sys.exit(int(__import__("os").environ.get("FAKE_APPEND_RC", "0")))\n')
        for p in (unittest.mock.patch.object(rc, 'REPO', self.repo),
                  unittest.mock.patch.object(rc, 'APPEND_LOG', self.fake_append)):
            p.start()
            self.addCleanup(p.stop)

    def _as(self, session, func, *args):
        with unittest.mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': session}):
            return self._run(func, *args)

    def _install(self, when):
        self.ct['demo-skill'] = when
        ts = when.strftime('%Y-%m-%d %H:%M:%S')
        with open(self.local_log, 'a', encoding='utf-8') as f:
            f.write(f'{ts} [info] [SkillsPlugin] Delta: 1 to download\n'
                    f'{ts} [info] [SkillsPlugin] Sync complete: 1 downloaded, 0 failed\n')


class SessionScopedBaselines(_SessionFixture):
    """Since #79 every checkout shares ONE baseline dir (the primary's). A baseline
    must therefore belong to the session that took it and be used up once its
    install is recorded -- otherwise a session reads another session's install (or
    its own previous run's) as its own CONFIRMED, and postclick logs an install that
    never happened (merge-gate race finding F1)."""

    def test_another_sessions_install_is_not_confirmed_for_this_session(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))       # A's package clicked

        _, out = self._as('sess-B', rc.cmd_verify, ['demo-skill'], None)

        self.assertNotIn('CONFIRMED', out)
        self.assertIn('NO-BASELINE', out)

    def test_another_sessions_baseline_does_not_clobber_this_ones(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))       # A's package clicked
        self._as('sess-B', rc.cmd_baseline, ['demo-skill'])  # B's pre-check, after A's click

        _, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)

        self.assertIn('demo-skill: CONFIRMED', out)

    def test_recorded_install_uses_the_baseline_up(self):
        # Without this a later reimport of the same skill in the same session keeps
        # (precheck never overwrites) the old baseline and CONFIRMs the OLD install.
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        code, out = self._as('sess-A', rc.cmd_postclick, 'demo-skill', '1.0', False, False)
        self.assertEqual(code, 0, out)

        _, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)

        self.assertIn('NO-BASELINE', out)

    def test_no_append_and_failed_append_keep_the_baseline(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        self._as('sess-A', rc.cmd_postclick, 'demo-skill', None, True, False)
        with unittest.mock.patch.dict(os.environ, {'FAKE_APPEND_RC': '1'}):
            self._as('sess-A', rc.cmd_postclick, 'demo-skill', '1.0', False, False)

        _, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)

        self.assertIn('demo-skill: CONFIRMED', out)

    def test_failed_baseline_write_leaves_the_previous_one_intact(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        with unittest.mock.patch.object(pr.os, 'replace',
                                        side_effect=PermissionError(13, 'locked')), \
                unittest.mock.patch.object(pr.time, 'sleep'), \
                self.assertRaises(PermissionError):
            self._as('sess-A', rc.cmd_baseline, ['demo-skill'])

        _, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)

        self.assertIn('demo-skill: CONFIRMED', out)
        self.assertEqual([p for p in self.baselines.rglob('*') if p.name.endswith('.tmp')], [])

    def test_transient_lock_on_a_baseline_read_is_retried(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        real_read = Path.read_text
        failed = []

        def locked_once(path, *a, **kw):
            if self.baselines in path.parents and not failed:
                failed.append(path)
                raise PermissionError(13, 'being used by another process')
            return real_read(path, *a, **kw)

        with unittest.mock.patch.object(Path, 'read_text', locked_once), \
                unittest.mock.patch.object(pr.time, 'sleep'):
            _, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)

        self.assertTrue(failed)
        self.assertIn('demo-skill: CONFIRMED', out)


class PostclickRoundTwoGateFindings(_SessionFixture):
    """Merge-gate round 2: postclick from a worktree with no _staging/ of its own,
    --baseline across sessions, and the hint for a legacy flat baseline."""

    def test_postclick_works_where_the_checkout_has_no_staging_dir(self):
        # Baselines now live in the primary, so nothing creates a worktree's own
        # _staging/ any more -- postclick's entry file must not assume it exists.
        bare = self.tmp / 'fresh-worktree'
        bare.mkdir()
        with unittest.mock.patch.object(rc, 'REPO', bare):
            self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
            self._install(datetime(2026, 9, 23, 12, 5, 0))
            code, out = self._as('sess-A', rc.cmd_postclick, 'demo-skill', '1.0', False, False)

        self.assertEqual(code, 0, out)
        self.assertIn('event log appended', out)

    def test_postclick_honours_baseline_across_sessions(self):
        # e.g. baseline taken in Code (real session id), click verified via the
        # Desktop Commander bridge (no session id) -- the documented escape hatch.
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))

        code, out = self._as('sess-B', rc.cmd_postclick, 'demo-skill', '1.0', True, False,
                             '2026-09-23 12:00:00')

        self.assertEqual(code, 0, out)
        self.assertIn('demo-skill: CONFIRMED', out)

    def test_no_baseline_points_at_a_legacy_flat_baseline(self):
        _write(self.baselines / 'demo-skill.json',
               json.dumps({'skill': 'demo-skill', 'creation_time': '2026-09-23T11:57:00'}))

        _, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)

        self.assertIn('NO-BASELINE', out)
        self.assertIn('pre-#79', out)
        self.assertIn('--baseline "2026-09-23 11:57:00"', out)


class ConsumeRaceFindings(_SessionFixture):
    """Merge-gate round 2, race F1/F3/F4: a baseline that vanishes mid-read, a
    consume that fails, and a consume that would delete a baseline captured after
    the verify it is meant to follow."""

    def test_a_baseline_that_vanishes_before_the_read_is_no_baseline(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        real_read = Path.read_text

        def vanished(path, *a, **kw):
            if self.baselines in path.parents:
                raise FileNotFoundError(2, 'No such file or directory', str(path))
            return real_read(path, *a, **kw)

        with unittest.mock.patch.object(Path, 'read_text', vanished):
            code, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)

        self.assertEqual(code, 1)
        self.assertIn('NO-BASELINE', out)

    def test_a_baseline_captured_after_the_install_is_kept(self):
        # Subagents share the parent's session id: one can re-capture while the
        # parent's postclick is still appending. That baseline records the NEW
        # CreationTime, so it can still tell the next install from this one.
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])       # the re-capture

        self._as('sess-A', rc.cmd_consume, ['demo-skill'])

        with unittest.mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': 'sess-A'}):
            kept = json.loads(rc._baseline_path('demo-skill').read_text(encoding='utf-8'))
        self.assertEqual(kept['creation_time'], '2026-09-23T12:05:00')

    def test_a_recorded_install_uses_up_every_sessions_older_baseline(self):
        # Merge-gate round 3 MEDIUM: the documented --baseline path (e.g. verify via
        # the DC bridge, which has no session id) used up only ITS session's baseline;
        # session A's pre-install one survived and CONFIRMed A's next reimport of the
        # skill with no click at all.
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._as('sess-B', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        code, out = self._as('no-session', rc.cmd_postclick, 'demo-skill', '1.0', False, False,
                             '2026-09-23 12:00:00')
        self.assertEqual(code, 0, out)

        for session in ('sess-A', 'sess-B'):
            _, out = self._as(session, rc.cmd_verify, ['demo-skill'], None)
            self.assertIn('NO-BASELINE', out, session)
            self.assertNotIn('CONFIRMED', out, session)

    def test_consume_leaves_no_claim_files_behind(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._as('sess-B', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        self._as('sess-B', rc.cmd_baseline, ['demo-skill'])       # post-install: kept

        self._as('sess-A', rc.cmd_consume, ['demo-skill'])

        self.assertEqual(sorted(p.name for p in (self.baselines / 'demo-skill').iterdir()),
                         ['sess-B.json'])

    def test_postclick_reports_a_consume_that_failed(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))

        with unittest.mock.patch.object(rc, 'consume_baseline',
                                        side_effect=PermissionError(32, 'in use')):
            code, out = self._as('sess-A', rc.cmd_postclick, 'demo-skill', '1.0', False, False)

        self.assertEqual(code, 1)
        self.assertIn('event log appended', out)
        self.assertIn('baseline NOT used up', out)

    def test_consume_cli_reports_a_failure(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        with unittest.mock.patch.object(rc, 'consume_baseline',
                                        side_effect=PermissionError(32, 'in use')):
            code, out = self._as('sess-A', rc.cmd_consume, ['demo-skill'])

        self.assertEqual(code, 1)
        self.assertIn('NOT used up', out)

    def test_postclick_with_clear_ledger_still_reports_a_consume_that_failed(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        ok = self.tmp / 'ok.py'
        ok.write_text('import sys\nsys.exit(0)\n')

        with unittest.mock.patch.object(rc, 'PENDING', ok), \
                unittest.mock.patch.object(rc, 'consume_baseline',
                                           side_effect=PermissionError(32, 'in use')):
            code, out = self._as('sess-A', rc.cmd_postclick, 'demo-skill', '1.0', False, True)

        self.assertEqual(code, 1)
        self.assertIn('baseline NOT used up', out)


class RoundThreeGateFindings(_SessionFixture):
    """Merge-gate round 3: legacy-hint robustness, the ABSENT hint, stale baselines
    kept by precheck, and the CLI plumbing for the new flags."""

    def test_a_malformed_legacy_baseline_never_crashes_verify(self):
        for i, bad in enumerate(('[1, 2]', '{"creation_time": "yesterday"}',
                                 '{"creation_time": 123}', 'not json')):
            skill = f'bad-{i}'
            _write(self.baselines / f'{skill}.json', bad)
            self.ct[skill] = datetime(2026, 9, 23, 12, 0, 0)

        code, out = self._as('sess-A', rc.cmd_verify, ['bad-0', 'bad-1', 'bad-2', 'bad-3'], None)

        self.assertEqual(code, 1)
        self.assertEqual(out.count('NO-BASELINE'), 4)

    def test_an_absent_legacy_baseline_gets_its_own_hint(self):
        _write(self.baselines / 'demo-skill.json',
               json.dumps({'skill': 'demo-skill', 'creation_time': None}))

        _, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)

        self.assertIn('pre-#79 unscoped ABSENT baseline', out)
        self.assertIn('--baseline "2000-01-01 00:00:00"', out)

    def test_precheck_recaptures_a_baseline_an_install_has_made_stale(self):
        # A kept baseline that no longer matches the cache predates an install; kept,
        # it would CONFIRM that install again as the next one.
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        with unittest.mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': 'sess-A'}):
            rc._refresh_stale_baseline('demo-skill')
            kept = json.loads(rc._baseline_path('demo-skill').read_text(encoding='utf-8'))

        self.assertEqual(kept['creation_time'], '2026-09-23T12:05:00')

    def _main(self, session, *argv):
        with unittest.mock.patch.object(sys, 'argv', ['reimport_correlate.py', *argv]):
            return self._as(session, rc.main)

    def test_cli_postclick_honours_baseline(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))

        # Override mode has no checkout fallback, so a plain baseline needs --version.
        code, out = self._main('sess-B', 'postclick', 'demo-skill', '--no-append',
                               '--baseline', '2026-09-23 12:00:00', '--version', '1.0')

        self.assertEqual(code, 0, out)
        self.assertIn('demo-skill: CONFIRMED', out)

    def test_cli_consume_uses_up_a_stale_baseline(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))

        code, out = self._main('sess-A', 'consume', 'demo-skill')

        self.assertEqual(code, 0, out)
        _, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)
        self.assertIn('NO-BASELINE', out)

    def test_cycle_main_passes_baseline_to_close(self):
        seen = {}
        with unittest.mock.patch.object(cyc, 'cmd_close',
                                        lambda *a: seen.setdefault('args', a) and 0):
            cyc.main(['close', 'demo-skill', '--baseline', '2026-09-23 12:00:00',
                      '--version', '4.32'])

        self.assertEqual(seen['args'][-2:], ('2026-09-23 12:00:00', '4.32'))


class RoundFourGateFindings(_SessionFixture):
    """Merge-gate round 4: the 1-second "predates" boundary and the first-install
    case pinned, foreign baseline files, and a claim rename that is not exclusive."""

    def _names(self):
        return sorted(p.name for p in (self.baselines / 'demo-skill').iterdir())

    def test_a_baseline_taken_seconds_before_the_install_is_used_up(self):
        # Every other test puts 5 minutes between baseline and install, so a rule that
        # only used up baselines a minute old would pass them -- and CONFIRM a click
        # taken 30 seconds after the baseline again with no click at all.
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 0, 30))
        code, out = self._as('sess-A', rc.cmd_postclick, 'demo-skill', '1.0', False, False)
        self.assertEqual(code, 0, out)

        _, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)

        self.assertIn('NO-BASELINE', out)

    def test_predates_is_one_second_either_way_and_absent_always_predates(self):
        installed = datetime(2026, 9, 23, 12, 5, 0)
        self.assertTrue(rc._predates(datetime(2026, 9, 23, 12, 4, 59), installed))
        self.assertFalse(rc._predates(datetime(2026, 9, 23, 12, 4, 59, 500000), installed))
        self.assertFalse(rc._predates(installed, installed))
        self.assertTrue(rc._predates(None, installed))

    def test_a_first_install_uses_up_the_absent_baseline(self):
        self.ct['demo-skill'] = None
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        code, out = self._as('sess-A', rc.cmd_postclick, 'demo-skill', '1.0', False, False)
        self.assertEqual(code, 0, out)

        _, out = self._as('sess-A', rc.cmd_verify, ['demo-skill'], None)

        self.assertIn('NO-BASELINE', out)

    def test_foreign_baseline_files_are_used_up_and_never_stop_the_sweep(self):
        # Correctness F1: a hand-written tz-aware or UTF-16 file raised out of the loop,
        # leaving every older baseline sorted after it to CONFIRM the next reimport.
        skill_dir = self.baselines / 'demo-skill'
        skill_dir.mkdir(parents=True)
        (skill_dir / '0-aware.json').write_text(
            json.dumps({'skill': 'demo-skill', 'creation_time': '2026-09-01T09:00:00+00:00'}),
            encoding='utf-8')
        (skill_dir / '1-utf16.json').write_text(
            json.dumps({'skill': 'demo-skill', 'creation_time': '2026-09-01T09:00:00'}),
            encoding='utf-16')
        self._as('sess-B', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))

        code, out = self._as('sess-B', rc.cmd_consume, ['demo-skill'])

        self.assertEqual(code, 0, out)
        self.assertEqual(self._names(), [])

    def test_precheck_recaptures_a_tz_aware_baseline_instead_of_crashing(self):
        with unittest.mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': 'sess-A'}):
            _write(rc._baseline_path('demo-skill'),
                   json.dumps({'skill': 'demo-skill',
                               'creation_time': '2026-09-23T12:00:00+00:00'}))
            note = rc._refresh_stale_baseline('demo-skill')

        self.assertIn('stale', note)

    def test_a_claim_another_consumer_moved_on_is_theirs_not_a_failure(self):
        # Race F2: a rename is not exclusive on Windows -- two can both "succeed", the
        # second moving the first's claim. The loser must skip it, not exit 1.
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        real_rename = os.rename

        def stolen_after_claim(src, dst):
            real_rename(src, dst)
            if Path(dst).name.startswith('.'):              # our claim, taken by B
                Path(dst).unlink()

        with unittest.mock.patch.object(rc.os, 'rename', stolen_after_claim):
            code, out = self._as('sess-A', rc.cmd_consume, ['demo-skill'])

        self.assertEqual(code, 0, out)
        self.assertNotIn('NOT used up', out)

    def test_a_claim_rename_that_finds_the_file_gone_is_skipped(self):
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))

        with unittest.mock.patch.object(rc.os, 'rename',
                                        side_effect=FileNotFoundError(2, 'gone')):
            code, out = self._as('sess-A', rc.cmd_consume, ['demo-skill'])

        self.assertEqual(code, 0, out)

    def _put_back(self, on_put_back):
        """Consume a post-install (kept) baseline with the put-back rename replaced."""
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])
        real_rename = os.rename

        def rename(src, dst):
            if Path(src).name.startswith('.'):              # claim -> path: the put-back
                on_put_back(Path(src), Path(dst))
            else:
                real_rename(src, dst)

        with unittest.mock.patch.object(rc.os, 'rename', rename):
            return self._as('sess-A', rc.cmd_consume, ['demo-skill'])

    def test_a_newer_baseline_that_lands_before_the_put_back_wins(self):
        def newer_lands(src, dst):
            dst.write_text('{"skill": "demo-skill", "creation_time": "NEWER"}',
                           encoding='utf-8')
            raise FileExistsError(17, 'exists', str(dst))

        code, out = self._put_back(newer_lands)

        self.assertEqual(code, 0, out)
        self.assertEqual(self._names(), ['sess-A.json'])
        self.assertIn('NEWER', (self.baselines / 'demo-skill' / 'sess-A.json')
                      .read_text(encoding='utf-8'))

    def test_a_claim_taken_before_the_put_back_is_theirs_not_a_failure(self):
        def taken(src, dst):
            src.unlink()
            raise FileNotFoundError(2, 'gone', str(src))

        code, out = self._put_back(taken)

        self.assertEqual(code, 0, out)
        self.assertNotIn('NOT used up', out)


class RoundFiveGateFindings(_SessionFixture):
    """Merge-gate round 5 MEDIUM: the put-back of a kept baseline was the one rename
    in consume_baseline with no retry, so a brief lock (an indexer or AV handle)
    stranded it as a hidden claim file -- and the message said the opposite."""

    def _names(self):
        return sorted(p.name for p in (self.baselines / 'demo-skill').iterdir())

    def _locked_put_back(self, failures):
        """Patch os.rename so the put-back (claim -> path) hits `failures` locks."""
        real_rename = os.rename
        left = [failures]

        def rename(src, dst):
            if Path(src).name.startswith('.') and left[0] > 0:
                left[0] -= 1
                raise PermissionError(32, 'in use by another process', str(src))
            real_rename(src, dst)
        return unittest.mock.patch.object(rc.os, 'rename', rename)

    def _kept_and_predating(self):
        self._as('sess-B', rc.cmd_baseline, ['demo-skill'])          # predates: used up
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        self._as('sess-A', rc.cmd_baseline, ['demo-skill'])          # post-install: kept

    def test_a_brief_lock_on_the_put_back_is_retried(self):
        self._kept_and_predating()

        with self._locked_put_back(2):
            code, out = self._as('sess-A', rc.cmd_consume, ['demo-skill'])

        self.assertEqual(code, 0, out)
        self.assertEqual(self._names(), ['sess-A.json'])

    def test_a_put_back_that_stays_locked_says_the_kept_baseline_is_stranded(self):
        self._kept_and_predating()

        with self._locked_put_back(99):
            code, out = self._as('sess-A', rc.cmd_consume, ['demo-skill'])

        self.assertEqual(code, 1, out)
        self.assertIn('could not be put back', out)
        self.assertNotIn('CONFIRM this install again', out)
        names = self._names()
        self.assertNotIn('sess-B.json', names)                       # the sweep went on
        stranded = [n for n in names if n.startswith('.sess-A.json.claim-')]
        self.assertEqual(len(stranded), 1, names)
        self.assertIn(stranded[0], out)

    def test_postclick_reports_a_stranded_baseline_not_an_unused_one(self):
        self._as('sess-B', rc.cmd_baseline, ['demo-skill'])
        self._install(datetime(2026, 9, 23, 12, 5, 0))
        self._as('sess-C', rc.cmd_baseline, ['demo-skill'])          # post-install: kept

        with self._locked_put_back(99):
            code, out = self._as('sess-B', rc.cmd_postclick, 'demo-skill', '1.0', False, False)

        self.assertEqual(code, 1, out)
        self.assertIn('could not be put back', out)
        self.assertNotIn('baseline NOT used up', out)


class CycleCloseUsesTheBaselineUp(unittest.TestCase):
    """reimport_cycle close does its own combined event-log append (postclick runs
    with --no-append), so it must use the baselines up itself -- and only once that
    append exited 0."""

    def _close(self, append_rc, baseline=None, consume_rc=0, version=None):
        calls = []

        def fake_run(args, echo=True):
            calls.append([str(a) for a in args])
            if str(args[0]) == str(cyc.APPEND):
                rc_ = append_rc
            elif 'consume' in [str(a) for a in args]:
                rc_ = consume_rc
            else:
                rc_ = 0
            return subprocess.CompletedProcess(args, rc_, stdout='', stderr='')

        with unittest.mock.patch.object(cyc, '_run', fake_run), \
                unittest.mock.patch.object(cyc, 'REPO', Path(tempfile.mkdtemp(
                    prefix='reimport_correlate_test_'))) as repo, redirect_stdout(io.StringIO()):
            self.addCleanup(_rmtree, repo)
            code = cyc.cmd_close(['demo-skill'], None, False, False, baseline, version)
        return code, calls

    def test_consume_after_the_append_needs_no_time_bound(self):
        # What gets used up is decided by each baseline's recorded CreationTime
        # against the install, not by a wall-clock bound (round 3: mtime granularity).
        code, calls = self._close(0)

        consume = next(c for c in calls if 'consume' in c)
        self.assertEqual(code, 0)
        self.assertNotIn('--not-after', consume)

    def test_a_failed_consume_fails_close(self):
        with redirect_stdout(io.StringIO()) as out:
            code, _ = self._close(0, consume_rc=1)

        self.assertEqual(code, 1)

    def test_baseline_is_passed_through_to_postclick(self):
        code, calls = self._close(0, baseline='2026-09-23 12:00:00')

        postclick = next(c for c in calls if 'postclick' in c)
        self.assertEqual(code, 0)
        self.assertEqual(postclick[postclick.index('--baseline') + 1], '2026-09-23 12:00:00')

    def test_version_is_passed_through_to_postclick(self):
        code, calls = self._close(0, version='4.32')

        postclick = next(c for c in calls if 'postclick' in c)
        self.assertEqual(code, 0)
        self.assertEqual(postclick[postclick.index('--version') + 1], '4.32')

    def test_version_with_several_skills_is_refused_before_anything_runs(self):
        with unittest.mock.patch.object(cyc, '_run') as run, redirect_stdout(io.StringIO()):
            code = cyc.cmd_close(['a', 'b'], None, False, False, None, '4.32')

        self.assertEqual(code, 2)
        run.assert_not_called()

    def test_c4_a_blank_version_is_passed_through_so_postclick_refuses_it(self):
        code, calls = self._close(0, version='')

        postclick = next(c for c in calls if 'postclick' in c)
        self.assertEqual(postclick[postclick.index('--version') + 1], '')

    def test_c5_a_blank_baseline_is_passed_through_so_postclick_refuses_it(self):
        code, calls = self._close(0, baseline='')

        postclick = next(c for c in calls if 'postclick' in c)
        self.assertEqual(postclick[postclick.index('--baseline') + 1], '')

    def _close_clearing(self, repo_version, cache_version):
        calls = []

        def fake_run(args, echo=True):
            calls.append([str(a) for a in args])
            return subprocess.CompletedProcess(args, 0, stdout='', stderr='')

        out = io.StringIO()
        with unittest.mock.patch.object(cyc, '_run', fake_run), \
                unittest.mock.patch.object(cyc._rcor, '_repo_expected_version', lambda s: repo_version), \
                unittest.mock.patch.object(cyc._rcor, '_cache_version', lambda s: cache_version), \
                unittest.mock.patch.object(cyc, 'REPO', Path(tempfile.mkdtemp(
                    prefix='reimport_correlate_test_'))) as repo, redirect_stdout(out):
            self.addCleanup(_rmtree, repo)
            code = cyc.cmd_close(['demo-skill'], None, True, False)
        return code, calls, out.getvalue()

    def test_c1_close_keeps_the_ledger_entry_when_the_repo_moved_on(self):
        code, calls, out = self._close_clearing('4.30', '4.29')

        self.assertEqual(code, 0, out)
        self.assertTrue(any(c[0] == str(cyc.APPEND) for c in calls))      # install still logged
        self.assertFalse(any('clear' in c for c in calls), calls)
        self.assertIn('ledger NOT cleared: repo is v4.30', out)

    def test_c1_close_clears_when_the_repo_matches(self):
        code, calls, out = self._close_clearing('4.29', '4.29')

        self.assertEqual(code, 0, out)
        self.assertTrue(any('clear' in c for c in calls), calls)

    def test_c1_close_clears_when_the_repo_declares_no_version(self):
        code, calls, out = self._close_clearing(None, '4.29')

        self.assertTrue(any('clear' in c for c in calls), calls)

    def test_consumes_after_a_successful_append(self):
        code, calls = self._close(0)

        self.assertEqual(code, 0)
        append_at = next(i for i, c in enumerate(calls) if c[0] == str(cyc.APPEND))
        consume_at = next(i for i, c in enumerate(calls) if 'consume' in c)
        self.assertGreater(consume_at, append_at)
        self.assertIn('demo-skill', calls[consume_at])

    def test_does_not_consume_when_the_append_fails(self):
        code, calls = self._close(1)

        self.assertEqual(code, 1)
        self.assertFalse(any('consume' in c for c in calls))


class PostclickVersionGuard(PostclickTests):
    """2026-10-17: postclick logged "v4.28 ... CONFIRMED" while the cache held v4.29,
    because --version was trusted and the installed SKILL.md never read. A version that
    can be read from the cache and disagrees must stop postclick like any non-CONFIRMED
    verdict: nothing appended, baseline kept, ledger untouched."""

    def _skill_md(self, h1='# Demo Skill (v4.29 — Buy Box)', fm=''):
        _write(self.cache / 'demo-skill' / 'SKILL.md',
               f'---\nname: demo-skill\ndescription: d\n{fm}---\n\n{h1}\n')

    def _confirmable_with(self, **kw):
        self._confirmable()
        self._skill_md(**kw)

    def test_h1_mismatch_refuses_and_appends_nothing(self):
        self._confirmable_with()
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.28', False, False)
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)
        self.assertNotIn('demo-skill: CONFIRMED', out)
        self.assertFalse(self.calls.exists())

    def test_mismatch_keeps_the_baseline_for_a_later_correct_install(self):
        self._confirmable_with()
        self._run(rc.cmd_postclick, 'demo-skill', '4.28', False, False)
        self.assertTrue(rc._baseline_path('demo-skill').exists())

    def test_mismatch_never_clears_the_ledger(self):
        self._confirmable_with()
        with unittest.mock.patch.object(rc.subprocess, 'run', wraps=rc.subprocess.run) as run:
            code, _ = self._run(rc.cmd_postclick, 'demo-skill', '4.28', False, True)
        self.assertEqual(code, 1)
        self.assertFalse(any('clear' in [str(a) for a in c.args[0]] for c in run.call_args_list))
        self.assertFalse(self.pending_calls.exists())

    def test_not_confirmed_run_never_reads_the_repo_skill_md(self):
        # An unreadable (non-UTF-8) repo SKILL.md must not turn a plain STOP into a crash.
        (self.cache / 'demo-skill').mkdir()
        _write(rc._baseline_path('demo-skill'),
               json.dumps({'skill': 'demo-skill', 'creation_time': '2020-01-01T00:00:00'}))
        (self.repo / 'demo-skill').mkdir()
        (self.repo / 'demo-skill' / 'SKILL.md').write_bytes(
            b'---\nname: demo-skill\n---\n\xff\xfe bad\n')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, False)
        self.assertEqual(code, 1, out)
        self.assertIn('STOP', out)

    def test_mismatch_also_refuses_under_no_append(self):
        self._confirmable_with()
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.28', True, False)
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)

    def test_matching_h1_version_appends(self):
        self._confirmable_with()
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.29', False, False)
        self.assertEqual(code, 0, out)
        self.assertIn('demo-skill v4.29 reimport confirmed', self.calls.read_text())

    def test_leading_v_on_the_requested_version_is_tolerated(self):
        self._confirmable_with()
        code, out = self._run(rc.cmd_postclick, 'demo-skill', 'v4.29', False, False)
        self.assertEqual(code, 0, out)
        logged = self.calls.read_text()
        self.assertIn('demo-skill v4.29 reimport confirmed', logged)
        self.assertNotIn('vv4.29', logged)

    def test_frontmatter_version_takes_precedence_over_h1(self):
        self._confirmable_with(h1='# Demo (v9.9)', fm='version: 2.1\n')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '9.9', False, False)
        self.assertEqual(code, 1, out)
        self.assertFalse(self.calls.exists())
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '2.1', False, False)
        self.assertEqual(code, 0, out)

    def test_h1_without_parens_uses_trailing_version(self):
        self._confirmable_with(h1='# Solar Lease — v1.3')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '1.3', False, False)
        self.assertEqual(code, 0, out)

    def test_unreadable_cache_version_warns_but_proceeds(self):
        # Existing contract: a cache with no SKILL.md / no version token cannot be checked.
        self._confirmable()
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.23', False, False)
        self.assertEqual(code, 0, out)
        self.assertIn('version not verified', out)
        self.assertTrue(self.calls.exists())


class PostclickRepoDerivedVersion(PostclickVersionGuard):
    """REFUTE round 1 (biggest finding): reimport_cycle.cmd_close runs `postclick
    --no-append` WITHOUT --version, and no skill carries a frontmatter version, so the
    guard was skipped on the standard path. With no --version the expected version now
    comes from the repo checkout's SKILL.md (frontmatter version, else H1)."""

    def _repo_skill(self, h1):
        d = self.repo / 'demo-skill'
        d.mkdir(parents=True, exist_ok=True)
        (d / 'SKILL.md').write_text(f'---\nname: demo-skill\ndescription: d\n---\n\n{h1}\n', encoding='utf-8')

    def test_no_version_flag_still_catches_a_mismatch(self):
        self._confirmable_with(h1='# Demo (v4.29)')
        self._repo_skill('# Demo (v4.28)')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, True, False)  # --no-append, as reimport_cycle
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)
        self.assertFalse(self.calls.exists())

    def test_no_version_flag_matching_repo_confirms(self):
        self._confirmable_with(h1='# Demo (v4.29)')
        self._repo_skill('# Demo (v4.29)')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, False)
        self.assertEqual(code, 0, out)
        self.assertIn('demo-skill v4.29 reimport confirmed', self.calls.read_text())

    def test_explicit_version_still_wins_over_the_repo(self):
        self._confirmable_with(h1='# Demo (v4.29)')
        self._repo_skill('# Demo (v4.28)')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.29', False, False)
        self.assertEqual(code, 0, out)

    def test_repo_without_a_readable_version_stays_unchecked(self):
        self._confirmable_with(h1='# Demo (v4.29)')
        self._repo_skill('# Demo with no version token')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, False)
        self.assertEqual(code, 0, out)

    def test_non_utf8_repo_skill_md_does_not_crash(self):
        self._confirmable_with(h1='# Demo (v4.29)')
        d = self.repo / 'demo-skill'
        d.mkdir(parents=True, exist_ok=True)
        (d / 'SKILL.md').write_bytes(b'---\nname: demo-skill\n---\n\n# Demo (v4.29)\n\xff\xfe\n')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, False)
        self.assertEqual(code, 0, out)


class PostclickNoExpectedVersionWarns(PostclickTests):
    """REFUTE round 2 (low): 12 skills declare no version anywhere, so with no --version the
    guard had nothing to compare and skipped SILENTLY. It must say so."""

    def test_confirmed_with_no_expected_version_warns(self):
        self._confirmable()
        (self.cache / 'demo-skill' / 'SKILL.md').write_text(
            '---\nname: demo-skill\ndescription: d\n---\n\n# Demo with no version\n', encoding='utf-8')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, True, False)
        self.assertEqual(code, 0, out)
        self.assertIn('version not verified', out)
        self.assertIn('no expected version', out)


class PostclickPackageVersion(PostclickTests):
    """Follow-up to #139 (its "Known limitation"): with no --version, the expected version
    followed the checkout running postclick, so v4.32 packaged in a worktree + v4.31
    installed + close run from a primary still on v4.31 logged a false CONFIRMED. `baseline
    --package` records the PACKAGED SKILL.md version; postclick compares the cache to that."""

    def _pkg(self, version_line, name='demo-skill.skill'):
        pkg = self.tmp / name
        fm = f'---\nname: demo-skill\ndescription: d\n{version_line}---\n\n# Demo\n'
        _make_pkg(pkg, 'demo-skill', {'demo-skill/SKILL.md': fm.encode()})
        return pkg

    def _cache_md(self, ver):
        _write(self.cache / 'demo-skill' / 'SKILL.md',
               f'---\nname: demo-skill\ndescription: d\n---\n\n# Demo (v{ver})\n')

    def _repo_md(self, ver):
        _write(self.repo / 'demo-skill' / 'SKILL.md',
               f'---\nname: demo-skill\ndescription: d\n---\n\n# Demo (v{ver})\n')

    def _baseline_json(self):
        return json.loads(rc._baseline_path('demo-skill').read_text())

    def _arm(self, packaged, installed, checkout):
        """A baseline taken from a package, then an install that moves the cache."""
        self._cache_md('0.0')
        code, out = self._run(rc.cmd_baseline, ['demo-skill'], str(self._pkg(f'version: {packaged}\n')))
        self.assertEqual(code, 0, out)
        _write(rc._baseline_path('demo-skill'),
               json.dumps({**self._baseline_json(), 'creation_time': '2020-01-01T00:00:00'}))
        self._cache_md(installed)
        self._repo_md(checkout)
        ts = rc._creation_time('demo-skill').strftime('%Y-%m-%d %H:%M:%S')
        _write(self.local_log,
               f'{ts} [info] [SkillsPlugin] Delta: 1 to download\n'
               f'{ts} [info] [SkillsPlugin] Sync complete: 1 downloaded, 0 failed\n')

    def test_baseline_package_records_the_packaged_version(self):
        (self.cache / 'demo-skill').mkdir()
        code, out = self._run(rc.cmd_baseline, ['demo-skill'], str(self._pkg('version: 4.32\n')))
        self.assertEqual(code, 0, out)
        self.assertEqual(self._baseline_json()['expected_version'], '4.32')

    def test_false_match_v432_packaged_v431_installed_checkout_on_v431(self):
        self._arm(packaged='4.32', installed='4.31', checkout='4.31')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, True, False)
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)
        self.assertNotIn('demo-skill: CONFIRMED', out)
        self.assertFalse(self.calls.exists())
        self.assertTrue(rc._baseline_path('demo-skill').exists())

    def test_package_version_confirms_when_checkout_is_behind(self):
        self._arm(packaged='4.32', installed='4.32', checkout='4.31')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, False)
        self.assertEqual(code, 0, out)
        self.assertIn('demo-skill v4.32 reimport confirmed', self.calls.read_text())

    def test_explicit_version_beats_the_baseline(self):
        self._arm(packaged='4.32', installed='4.31', checkout='4.30')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.31', True, False)
        self.assertEqual(code, 0, out)

    def test_baseline_beats_the_repo_checkout(self):
        self._arm(packaged='4.31', installed='4.31', checkout='4.99')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, True, False)
        self.assertEqual(code, 0, out)

    def test_baseline_without_expected_version_still_falls_back_to_the_repo(self):
        self._confirmable()                      # legacy baseline: no expected_version key
        self._cache_md('4.31')
        self._repo_md('4.32')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, True, False)
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)

    def test_unversioned_package_does_not_fall_back_to_the_repo(self):
        # The package was inspected and declares no version: a versioned checkout must not
        # stand in for it (that is the false match this change removes).
        self._arm(packaged='4.32', installed='4.31', checkout='4.31')
        _write(self.cache / 'demo-skill' / 'SKILL.md',
               '---\nname: demo-skill\ndescription: d\n---\n\n# Demo, no version\n')
        _write(rc._baseline_path('demo-skill'),
               json.dumps({**self._baseline_json(), 'expected_version': None}))
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, True, False)
        self.assertEqual(code, 0, out)
        self.assertIn('version not verified', out)
        self.assertIn('no expected version', out)

    def test_unversioned_package_with_a_versioned_cache_is_a_mismatch(self):
        # A package declaring no version cannot have produced a cache that declares one.
        self._arm(packaged='4.32', installed='4.31', checkout='4.31')
        _write(rc._baseline_path('demo-skill'),
               json.dumps({**self._baseline_json(), 'expected_version': None}))
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, True, False)
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)

    def test_malformed_expected_version_never_confirms_a_versioned_cache(self):
        for bad in (0, False, '', '   ', [4, 32], {'v': 1}):
            with self.subTest(bad=bad):
                self._arm(packaged='4.32', installed='4.31', checkout='4.31')
                _write(rc._baseline_path('demo-skill'),
                       json.dumps({**self._baseline_json(), 'expected_version': bad}))
                code, out = self._run(rc.cmd_postclick, 'demo-skill', None, True, False)
                self.assertEqual(code, 1, out)
                self.assertIn('VERSION-MISMATCH', out)

    def test_record_expected_version_does_not_resurrect_a_consumed_baseline(self):
        (self.cache / 'demo-skill').mkdir()
        rc.cmd_baseline(['demo-skill'])
        path = rc._baseline_path('demo-skill')
        real_read = rc._read_baseline
        calls = []

        def read_then_consume(pth):
            text = real_read(pth)
            calls.append(1)
            if len(calls) == 1:          # a consume claims the file after precheck read it
                path.unlink()
            return text

        with unittest.mock.patch.object(rc, '_read_baseline', read_then_consume):
            rc._record_expected_version('demo-skill', '4.32')
        self.assertFalse(path.exists())

    def test_unreadable_package_writes_no_baseline(self):
        (self.cache / 'demo-skill').mkdir()
        bad = self.tmp / 'bad.skill'
        bad.write_bytes(b'not a zip')
        code, out = self._run(rc.cmd_baseline, ['demo-skill'], str(bad))
        self.assertEqual(code, 1, out)
        self.assertFalse(rc._baseline_path('demo-skill').exists())
        code, out = self._run(rc.cmd_baseline, ['demo-skill'], str(self.tmp / 'ghost.skill'))
        self.assertEqual(code, 1, out)
        self.assertFalse(rc._baseline_path('demo-skill').exists())

    def test_package_without_skill_md_writes_no_baseline(self):
        (self.cache / 'demo-skill').mkdir()
        pkg = self.tmp / 'demo-skill.skill'
        _make_pkg(pkg, 'demo-skill', {'demo-skill/other.md': b'x'})
        code, out = self._run(rc.cmd_baseline, ['demo-skill'], str(pkg))
        self.assertEqual(code, 1, out)
        self.assertFalse(rc._baseline_path('demo-skill').exists())

    def test_package_with_several_skills_is_refused(self):
        code, out = self._run(rc.cmd_baseline, ['demo-skill', 'other'],
                              str(self._pkg('version: 1.0\n')))
        self.assertEqual(code, 2, out)
        self.assertFalse(rc._baseline_path('demo-skill').exists())

    def test_cli_package_flag_reaches_cmd_baseline(self):
        (self.cache / 'demo-skill').mkdir()
        pkg = self._pkg('version: 4.32\n')
        with unittest.mock.patch.object(sys, 'argv',
                                        ['rc', 'baseline', 'demo-skill', '--package', str(pkg)]):
            code, out = self._run(rc.main)
        self.assertEqual(code, 0, out)
        self.assertEqual(self._baseline_json()['expected_version'], '4.32')

    def test_precheck_records_the_package_version_on_capture_and_on_keep(self):
        # Entry point A takes its baseline in precheck, so precheck must record it too.
        pkg = self._pkg('version: 4.32\n')
        _write(self.repo / 'demo-skill' / 'SKILL.md',
               '---\nname: demo-skill\ndescription: d\nversion: 4.32\n---\n\n# Demo\n')
        with unittest.mock.patch.object(rc, '_plugin_of', lambda s: None):
            code, out = self._run(rc.cmd_precheck, [str(pkg)])
            self.assertEqual(code, 0, out)
            self.assertEqual(self._baseline_json()['expected_version'], '4.32')
            _write(rc._baseline_path('demo-skill'),
                   json.dumps({'skill': 'demo-skill', 'creation_time': None}))   # kept, no version
            code, out = self._run(rc.cmd_precheck, [str(pkg)])
        self.assertEqual(code, 0, out)
        self.assertEqual(self._baseline_json()['expected_version'], '4.32')


class PostclickOverrideMode(PostclickPackageVersion):
    """`close --baseline "<time>"` (prep ran in another session). The expected version must
    come from the baseline whose CreationTime IS that override -- any session's -- or from
    --version. Never from this session's unrelated file, never from the repo checkout:
    that is #139's false-match path (REFUTE round 1, high + medium)."""

    OVERRIDE = '2020-01-01 00:00:00'

    def _put(self, session, creation, **extra):
        _write(rc.BASELINE_DIR / 'demo-skill' / f'{session}.json',
               json.dumps({'skill': 'demo-skill', 'creation_time': creation, **extra}))

    def _installed(self, ver, checkout=None):
        self._cache_md(ver)
        if checkout:
            self._repo_md(checkout)
        ts = rc._creation_time('demo-skill').strftime('%Y-%m-%d %H:%M:%S')
        _write(self.local_log,
               f'{ts} [info] [SkillsPlugin] Delta: 1 to download\n'
               f'{ts} [info] [SkillsPlugin] Sync complete: 1 downloaded, 0 failed\n')

    def _close(self, version=None, session='sess-B', override=None):
        with unittest.mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': session}):
            return self._run(rc.cmd_postclick, 'demo-skill', version, True, False,
                             override or self.OVERRIDE)

    def _stopped_clean(self, code, out):
        self.assertEqual(code, 1, out)
        self.assertIn('pass --version', out)
        self.assertNotIn('demo-skill: CONFIRMED', out)
        self.assertFalse(self.calls.exists())
        self.assertFalse(self.pending_calls.exists())

    def test_no_baseline_at_all_stops_instead_of_trusting_the_checkout(self):
        # #139's own scenario: v4.32 packaged elsewhere, v4.31 installed, this checkout on 4.31.
        self._installed('4.31', checkout='4.31')
        self._stopped_clean(*self._close())

    def test_no_match_stops_even_when_the_repo_would_agree(self):
        self._put('sess-B', '2019-06-06T00:00:00', expected_version='4.31')   # unrelated, local
        self._installed('4.31', checkout='4.31')
        self._stopped_clean(*self._close())

    def test_explicit_version_still_works_in_override_mode(self):
        self._installed('4.31', checkout='4.99')
        code, out = self._close(version='4.31')
        self.assertEqual(code, 0, out)
        self.assertNotIn('pass --version', out)

    def test_match_in_another_session_gives_the_packaged_version(self):
        self._put('sess-A', '2020-01-01T00:00:00', expected_version='4.32')
        self._installed('4.31', checkout='4.31')
        code, out = self._close()
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)
        self.assertNotIn('pass --version', out)
        self._installed('4.32', checkout='4.31')
        code, out = self._close()
        self.assertEqual(code, 0, out)

    def test_a_stale_local_baseline_does_not_beat_the_matching_one(self):
        self._put('sess-B', '2019-06-06T00:00:00', expected_version='4.31')   # this session's, stale
        self._put('sess-A', '2020-01-01T00:00:00', expected_version='4.32')
        self._installed('4.31', checkout='4.31')
        code, out = self._close(session='sess-B')
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)

    def test_two_baselines_with_different_creation_times_are_told_apart(self):
        self._put('sess-A', '2020-01-01T00:00:00', expected_version='4.32')
        self._put('sess-C', '2021-03-03T00:00:00', expected_version='4.30')
        self._installed('4.30')
        code, out = self._close(override='2021-03-03 00:00:00')
        self.assertEqual(code, 0, out)
        code, out = self._close(override='2020-01-01 00:00:00')
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)

    def test_matching_baseline_with_no_recorded_version_stops(self):
        self._put('sess-A', '2020-01-01T00:00:00')                 # plain baseline, pre-change
        self._installed('4.31', checkout='4.31')
        self._stopped_clean(*self._close())

    def test_conflicting_matching_baselines_stop(self):
        self._put('sess-A', '2020-01-01T00:00:00', expected_version='4.32')
        self._put('sess-C', '2020-01-01T00:00:00', expected_version='4.31')
        self._installed('4.31')
        self._stopped_clean(*self._close())

    def test_agreeing_matching_baselines_are_fine(self):
        self._put('sess-A', '2020-01-01T00:00:00', expected_version='4.31')
        self._put('sess-C', '2020-01-01T00:00:00', expected_version='4.31')
        self._installed('4.31')
        code, out = self._close()
        self.assertEqual(code, 0, out)

    def test_unreadable_neighbour_baselines_are_ignored(self):
        _write(rc.BASELINE_DIR / 'demo-skill' / 'junk.json', '{not json')
        (rc.BASELINE_DIR / 'demo-skill' / 'bin.json').write_bytes(b'\xff\xfe\x00')
        self._put('sess-A', '2020-01-01T00:00:00', expected_version='4.31')
        self._installed('4.31')
        code, out = self._close()
        self.assertEqual(code, 0, out)

    def test_override_stop_keeps_every_baseline(self):
        self._put('sess-A', '2020-01-01T00:00:00', expected_version='4.32')
        self._installed('4.31')
        self._close()
        self.assertTrue((rc.BASELINE_DIR / 'demo-skill' / 'sess-A.json').exists())

    def test_cli_close_path_reaches_the_same_stop(self):
        self._installed('4.31', checkout='4.31')
        with unittest.mock.patch.object(sys, 'argv', ['rc', 'postclick', 'demo-skill',
                                                      '--no-append', '--baseline', self.OVERRIDE]):
            code, out = self._run(rc.main)
        self.assertEqual(code, 1, out)
        self.assertIn('pass --version', out)


class PlainBaselineWritesNoRecordedVersion(PostclickPackageVersion):
    """REFUTE round 2 (medium): a plain `baseline` that KEPT expected_version while the
    CreationTime was unchanged let a stale package's version survive a repo bump. An
    unchanged CreationTime says nothing was installed, not that the package is current. A
    plain baseline therefore records NO version, and only --package / precheck do."""

    def test_plain_baseline_overwrites_an_earlier_recorded_version(self):
        (self.cache / 'demo-skill').mkdir()
        self._run(rc.cmd_baseline, ['demo-skill'], str(self._pkg('version: 4.31\n')))
        self._run(rc.cmd_baseline, ['demo-skill'])
        self.assertNotIn('expected_version', self._baseline_json())

    def test_absent_baseline_writes_none_either(self):
        self._run(rc.cmd_baseline, ['demo-skill'], str(self._pkg('version: 4.31\n')))
        self._run(rc.cmd_baseline, ['demo-skill'])
        self.assertNotIn('expected_version', self._baseline_json())

    def test_a_new_package_replaces_it(self):
        (self.cache / 'demo-skill').mkdir()
        self._run(rc.cmd_baseline, ['demo-skill'], str(self._pkg('version: 4.32\n')))
        self._run(rc.cmd_baseline, ['demo-skill'], str(self._pkg('version: 4.33\n')))
        self.assertEqual(self._baseline_json()['expected_version'], '4.33')

    def test_stale_package_install_after_a_repo_bump_is_not_confirmed(self):
        # baseline --package 4.31, no click; repo bumps to 4.32; the step-2 plain baseline;
        # then the STALE 4.31 package is installed. Must not be CONFIRMED (c175941 did).
        self._cache_md('0.0')
        self._run(rc.cmd_baseline, ['demo-skill'], str(self._pkg('version: 4.31\n')))
        self._repo_md('4.32')
        self._run(rc.cmd_baseline, ['demo-skill'])
        _write(rc._baseline_path('demo-skill'),
               json.dumps({**self._baseline_json(), 'creation_time': '2020-01-01T00:00:00'}))
        self._cache_md('4.31')
        ts = rc._creation_time('demo-skill').strftime('%Y-%m-%d %H:%M:%S')
        _write(self.local_log,
               f'{ts} [info] [SkillsPlugin] Delta: 1 to download\n'
               f'{ts} [info] [SkillsPlugin] Sync complete: 1 downloaded, 0 failed\n')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, True)
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)
        self.assertFalse(self.calls.exists())
        self.assertFalse(self.pending_calls.exists())


class VersionFlagValueIsValidated(PostclickTests):
    """`postclick demo --version --no-append` swallowed --no-append as the version, and a blank
    --version skipped the check entirely. Both are operator slips; refuse them (exit 2)."""

    def _main(self, *argv):
        with unittest.mock.patch.object(sys, 'argv', ['rc', *argv]):
            return self._run(rc.main)

    def test_flag_like_and_blank_versions_are_refused(self):
        self._confirmable()
        for bad in ('--no-append', '-x', '', '   '):
            with self.subTest(bad=bad):
                code, out = self._main('postclick', 'demo-skill', '--version', bad)
                self.assertEqual(code, 2, out)
                self.assertIn('--version needs a version', out)
                self.assertFalse(self.calls.exists())

    def test_a_real_version_still_passes(self):
        self._confirmable()
        code, out = self._main('postclick', 'demo-skill', '--version', 'v4.23', '--no-append')
        self.assertEqual(code, 0, out)


class ReviewRoundThreeFindings(PostclickPackageVersion):
    """REFUTE round 3 (C1-C5), each a path to a false CONFIRMED or a wrong ledger clear."""

    def _confirmable_install(self, ver):
        self._cache_md(ver)
        ts = rc._creation_time('demo-skill').strftime('%Y-%m-%d %H:%M:%S')
        _write(self.local_log,
               f'{ts} [info] [SkillsPlugin] Delta: 1 to download\n'
               f'{ts} [info] [SkillsPlugin] Sync complete: 1 downloaded, 0 failed\n')

    def _main(self, *argv):
        with unittest.mock.patch.object(sys, 'argv', ['rc', *argv]):
            return self._run(rc.main)

    # C1 ------------------------------------------------------------------
    def test_c1_precheck_failure_does_not_record_the_stale_packages_version(self):
        self._repo_md('4.33')                           # repo moved on; the 4.32 package is stale
        self._cache_md('0.0')
        pkg = self._pkg('version: 4.32\n')
        with unittest.mock.patch.object(rc, '_plugin_of', lambda s: None):
            code, out = self._run(rc.cmd_precheck, [str(pkg)])
        self.assertEqual(code, 1, out)
        self.assertIn('PRECHECK FAIL', out)
        self.assertNotIn('expected_version', self._baseline_json())

    def test_c1_precheck_failure_drops_a_version_an_earlier_run_recorded(self):
        self._repo_md('4.33')
        self._cache_md('0.0')
        self._run(rc.cmd_baseline, ['demo-skill'], str(self._pkg('version: 4.32\n')))
        self.assertEqual(self._baseline_json()['expected_version'], '4.32')
        with unittest.mock.patch.object(rc, '_plugin_of', lambda s: None):
            self._run(rc.cmd_precheck, [str(self._pkg('version: 4.32\n'))])
        self.assertNotIn('expected_version', self._baseline_json())

    def test_c1_stale_install_after_a_failed_precheck_is_a_mismatch(self):
        self._repo_md('4.33')
        self._cache_md('0.0')
        with unittest.mock.patch.object(rc, '_plugin_of', lambda s: None):
            self._run(rc.cmd_precheck, [str(self._pkg('version: 4.32\n'))])
        _write(rc._baseline_path('demo-skill'),
               json.dumps({**self._baseline_json(), 'creation_time': '2020-01-01T00:00:00'}))
        self._confirmable_install('4.32')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, True)
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)
        self.assertFalse(self.calls.exists())
        self.assertFalse(self.pending_calls.exists())

    # C2 ------------------------------------------------------------------
    def test_c2_versions_that_normalize_to_empty_are_refused_by_main(self):
        self._confirmable_install('4.31')
        for bad in ('v', 'V', 'vv', 'vV', ' v '):
            with self.subTest(bad=bad):
                code, out = self._main('postclick', 'demo-skill', '--version', bad, '--clear-ledger')
                self.assertEqual(code, 2, out)
                self.assertFalse(self.calls.exists())
                self.assertFalse(self.pending_calls.exists())

    def test_c2_cmd_postclick_refuses_them_too(self):
        # A direct caller (reimport_cycle passes the value through) is covered, not just main().
        self._confirmable_install('4.31')
        for bad in ('v', 'V', 'vv', '', '   ', '--no-append'):
            with self.subTest(bad=bad):
                code, out = self._run(rc.cmd_postclick, 'demo-skill', bad, False, True)
                self.assertEqual(code, 2, out)
                self.assertFalse(self.calls.exists())
                self.assertFalse(self.pending_calls.exists())

    # C3 ------------------------------------------------------------------
    def test_c3_malformed_expected_version_stops_even_with_an_unversioned_cache(self):
        self._arm(packaged='4.32', installed='4.31', checkout='4.31')
        _write(self.cache / 'demo-skill' / 'SKILL.md',
               '---\nname: demo-skill\ndescription: d\n---\n\n# Demo, no version\n')
        _write(rc._baseline_path('demo-skill'),
               json.dumps({**self._baseline_json(), 'expected_version': 4.32}))
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, True)
        self.assertEqual(code, 1, out)
        self.assertIn('VERSION-MISMATCH', out)
        self.assertFalse(self.calls.exists())
        self.assertFalse(self.pending_calls.exists())

    # C5 ------------------------------------------------------------------
    def test_c5_blank_baseline_is_refused_by_main_and_cmd_postclick(self):
        self._confirmable_install('4.31')
        for bad in ('', '   '):
            with self.subTest(bad=bad):
                code, out = self._main('postclick', 'demo-skill', '--baseline', bad, '--version', '4.31')
                self.assertEqual(code, 2, out)
                code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.31', True, False, bad)
                self.assertEqual(code, 2, out)
        self.assertFalse(self.calls.exists())


class ReviewRoundFourLows(ReviewRoundThreeFindings):
    """REFUTE round 4 lows (C2-C4)."""

    def _recorded_then(self, pkg_path):
        self._cache_md('0.0')
        self._run(rc.cmd_baseline, ['demo-skill'], str(self._pkg('version: 4.28\n')))
        self.assertEqual(self._baseline_json()['expected_version'], '4.28')
        with unittest.mock.patch.object(rc, '_plugin_of', lambda s: None):
            return self._run(rc.cmd_precheck, [str(pkg_path)])

    def test_c2_missing_package_drops_a_recorded_version(self):
        code, out = self._recorded_then(self.tmp / 'elsewhere' / 'demo-skill.skill')
        self.assertEqual(code, 1, out)
        self.assertNotIn('expected_version', self._baseline_json())

    def test_c2_corrupt_package_drops_a_recorded_version(self):
        bad = self.tmp / 'elsewhere' / 'demo-skill.skill'
        bad.parent.mkdir()
        bad.write_bytes(b'not a zip')
        code, out = self._recorded_then(bad)
        self.assertEqual(code, 1, out)
        self.assertIn('FAIL', out)
        self.assertNotIn('expected_version', self._baseline_json())

    def test_c2_package_without_skill_md_drops_a_recorded_version(self):
        pkg = self.tmp / 'elsewhere' / 'demo-skill.skill'
        pkg.parent.mkdir()
        _make_pkg(pkg, 'demo-skill', {'demo-skill/other.md': b'x'})
        code, out = self._recorded_then(pkg)
        self.assertEqual(code, 1, out)
        self.assertNotIn('expected_version', self._baseline_json())

    def test_c3_flag_equals_value_tokens_are_refused(self):
        self._confirmable_install('4.30')
        self._repo_md('4.30')
        for tok in ('--version=4.29', '--version=', '--baseline=2026-01-01 00:00:00', '--bogus'):
            with self.subTest(tok=tok):
                code, out = self._main('postclick', 'demo-skill', tok, '--no-append')
                self.assertEqual(code, 2, out)
                self.assertNotIn('CONFIRMED', out)

    def test_c4_override_is_compared_to_the_second_not_within_one_second(self):
        self._installed = None
        _write(rc.BASELINE_DIR / 'demo-skill' / 'sess-A.json',
               json.dumps({'skill': 'demo-skill', 'creation_time': '2026-10-01T11:59:59.600000',
                           'expected_version': '4.29'}))
        v, why = rc._override_expected_version('demo-skill', datetime(2026, 10, 1, 12, 0, 0))
        self.assertIsNone(v)
        self.assertIn('no baseline records', why)
        _write(rc.BASELINE_DIR / 'demo-skill' / 'sess-A.json',
               json.dumps({'skill': 'demo-skill', 'creation_time': '2026-10-01T12:00:00.900000',
                           'expected_version': '4.29'}))
        v, why = rc._override_expected_version('demo-skill', datetime(2026, 10, 1, 12, 0, 0))
        self.assertEqual((v, why), ('4.29', None))


class LedgerClearGuard(PostclickPackageVersion):
    """REFUTE round 4 (C1): the install of v4.29 is real, but the ledger clears by skill NAME,
    so clearing it after the repo moved to v4.30 wipes the pending v4.30 reimport. The true
    install is still logged; the ledger entry is kept."""

    def test_install_logged_but_ledger_kept_when_the_repo_moved_on(self):
        self._arm(packaged='4.29', installed='4.29', checkout='4.30')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, True)
        self.assertEqual(code, 0, out)
        self.assertIn('demo-skill v4.29 reimport confirmed', self.calls.read_text())
        self.assertIn('ledger NOT cleared: repo is v4.30', out)
        self.assertFalse(self.pending_calls.exists())

    def test_ledger_cleared_when_the_repo_matches_the_install(self):
        self._arm(packaged='4.29', installed='4.29', checkout='4.29')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, True)
        self.assertEqual(code, 0, out)
        self.assertNotIn('ledger NOT cleared', out)
        self.assertIn('clear demo-skill', self.pending_calls.read_text())

    def test_ledger_cleared_when_the_repo_declares_no_version(self):
        self._arm(packaged='4.29', installed='4.29', checkout='4.29')
        _write(self.repo / 'demo-skill' / 'SKILL.md',
               '---\nname: demo-skill\ndescription: d\n---\n\n# Demo, no version\n')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', None, False, True)
        self.assertEqual(code, 0, out)
        self.assertTrue(self.pending_calls.exists())

    def test_explicit_version_installed_is_compared_to_the_repo_too(self):
        self._arm(packaged='4.29', installed='4.29', checkout='4.30')
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.29', False, True)
        self.assertIn('ledger NOT cleared: repo is v4.30', out)
        self.assertFalse(self.pending_calls.exists())

    def test_guard_helper_is_fail_open_only_when_the_repo_version_is_unreadable(self):
        self._repo_md('4.30')
        self.assertIn('v4.30', rc.ledger_clear_blocker('demo-skill', '4.29'))
        self.assertIsNone(rc.ledger_clear_blocker('demo-skill', 'v4.30'))
        self.assertIsNone(rc.ledger_clear_blocker('no-such-skill', '4.29'))


class CyclePrepPackagesBeforeBaseline(unittest.TestCase):
    """reimport_cycle prep wrote the baseline FIRST, so a package_skills refusal (dirty
    shared dep) left an unconsumed baseline that could confirm a later unrelated install."""

    def _prep(self, package_rc):
        calls = []
        tmp = Path(tempfile.mkdtemp(prefix='reimport_correlate_test_'))
        self.addCleanup(_rmtree, tmp)
        out_dir = tmp / 'pkg'

        def fake_run(args, echo=True):
            calls.append([str(a) for a in args])
            is_pkg = 'package_skills.py' in str(args[0])
            if is_pkg and package_rc == 0:
                for s in args[2:]:
                    _make_pkg(out_dir / f'{s}.skill', s, {f'{s}/SKILL.md': b'---\nname: x\n---\n'})
            return subprocess.CompletedProcess(args, package_rc if is_pkg else 0,
                                               stdout='', stderr='')

        fake_git = lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout='', stderr='')  # noqa: E731
        with unittest.mock.patch.object(cyc, '_run', fake_run), \
                unittest.mock.patch.object(cyc, 'gate_failures', lambda *a, **k: []), \
                unittest.mock.patch.object(cyc.subprocess, 'run', fake_git), \
                redirect_stdout(io.StringIO()):
            code = cyc.cmd_prep(['demo-skill', 'demo-two'], out_dir)
        return code, calls, out_dir

    def test_packager_failure_leaves_no_baseline(self):
        code, calls, _ = self._prep(package_rc=3)
        self.assertEqual(code, 3)
        self.assertFalse(any('reimport_correlate.py' in c[0] for c in calls), calls)

    def test_baseline_follows_the_package_and_names_it(self):
        code, calls, out_dir = self._prep(package_rc=0)
        self.assertEqual(code, 0)
        pkg_at = next(i for i, c in enumerate(calls) if 'package_skills.py' in c[0])
        bases = [(i, c) for i, c in enumerate(calls) if 'reimport_correlate.py' in c[0]]
        self.assertEqual(len(bases), 2)                          # one per skill
        for (i, c), s in zip(bases, ['demo-skill', 'demo-two']):
            self.assertGreater(i, pkg_at)
            self.assertEqual(c[c.index('baseline') + 1], s)
            self.assertEqual(c[c.index('--package') + 1], str(out_dir / f'{s}.skill'))


class PostclickTestsNeverReachTheRealLedger(unittest.TestCase):
    """The base PostclickTests fixture must itself patch PENDING: its
    test_failed_append_returns_1_and_skips_ledger_clear passes clear_ledger=True, so a
    regression there would otherwise run the real pending_reimport.py clear."""

    def test_base_fixture_patches_pending(self):
        t = PostclickTests('test_no_append_flag_verifies_only')
        t.setUp()
        try:
            self.assertNotEqual(Path(rc.PENDING).resolve(),
                                (Path(rc.__file__).resolve().parent / 'pending_reimport.py'))
        finally:
            t.doCleanups()
            t.tearDown()


if __name__ == '__main__':
    unittest.main()
