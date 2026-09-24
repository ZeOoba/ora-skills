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
        for p in (unittest.mock.patch.object(rc, 'REPO', self.repo),
                  unittest.mock.patch.object(rc, 'APPEND_LOG', self.fake_append)):
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

        code, out = self._main('sess-B', 'postclick', 'demo-skill', '--no-append',
                               '--baseline', '2026-09-23 12:00:00')

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
            cyc.main(['close', 'demo-skill', '--baseline', '2026-09-23 12:00:00'])

        self.assertEqual(seen['args'][-1], '2026-09-23 12:00:00')


class CycleCloseUsesTheBaselineUp(unittest.TestCase):
    """reimport_cycle close does its own combined event-log append (postclick runs
    with --no-append), so it must use the baselines up itself -- and only once that
    append exited 0."""

    def _close(self, append_rc, baseline=None, consume_rc=0):
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
            if baseline is None:
                code = cyc.cmd_close(['demo-skill'], None, False, False)
            else:
                code = cyc.cmd_close(['demo-skill'], None, False, False, baseline)
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


if __name__ == '__main__':
    unittest.main()
