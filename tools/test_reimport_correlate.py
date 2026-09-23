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
import io
import json
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reimport_correlate as rc  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='')


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
        shutil.rmtree(self.tmp, ignore_errors=True)

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
        self.assertTrue((self.baselines / 'demo-skill.json').is_file())

    def test_existing_baseline_is_never_overwritten(self):
        _write(self.baselines / 'demo-skill.json',
               json.dumps({'skill': 'demo-skill', 'creation_time': '2026-01-01T00:00:00'}))
        _make_pkg(self.pkg, 'demo-skill', self._good_entries())
        code, out = self._run(rc.cmd_precheck, [str(self.pkg)])
        self.assertEqual(code, 0, out)
        self.assertIn('baseline kept (2026-01-01T00:00:00)', out)
        self.assertEqual(json.loads((self.baselines / 'demo-skill.json').read_text())['creation_time'],
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
        _write(self.baselines / 'demo-skill.json',
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
        _write(self.baselines / 'demo-skill.json',
               json.dumps({'skill': 'demo-skill', 'creation_time': ct.isoformat()}))
        code, out = self._run(rc.cmd_postclick, 'demo-skill', '4.23', False, False)
        self.assertEqual(code, 1)
        self.assertIn('STOP', out)
        self.assertFalse(self.calls.exists())

    def test_moved_only_stops_and_appends_nothing(self):
        (self.cache / 'demo-skill').mkdir()
        _write(self.baselines / 'demo-skill.json',
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


if __name__ == '__main__':
    unittest.main()
