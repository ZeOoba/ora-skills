#!/usr/bin/env python3
"""entry_b_precheck.baseline_cache and verify_installed_cache read rpm store-plugin
installs (R34-6 follow-up, 2026-11-23). Stdlib only: `python tools/test_install_check_rpm.py`.

Hermetic: both install roots are patched to fixture dirs; the real AppData stores are
never read."""
import contextlib
import io
import shutil
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_reimport as pr  # noqa: E402
import entry_b_precheck as eb  # noqa: E402
import verify_installed_cache as vic  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='')


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='install_check_rpm_'))
        self.cache, self.rpm = self.tmp / 'cache', self.tmp / 'rpm'
        self.cache.mkdir()
        self.rpm.mkdir()
        for name, val in (('CACHE_ROOT', self.cache), ('RPM_ROOT', self.rpm)):
            p = unittest.mock.patch.object(pr, name, val)
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class EntryBBaseline(Fixture):
    def test_baseline_names_the_rpm_install(self):
        d = self.rpm / 'plugin_A' / 'skills' / 'demo'
        _write(d / 'SKILL.md', 'x')
        b = eb.baseline_cache('demo')
        self.assertEqual(b['cache_dir'], str(d))
        self.assertIsNotNone(b['creation_time'])
        self.assertEqual(b['rpm_root'], str(self.rpm))
        self.assertEqual(b['unreadable_roots'], [])

    def test_legacy_install_still_wins(self):
        _write(self.cache / 'demo' / 'SKILL.md', 'x')
        _write(self.rpm / 'plugin_A' / 'skills' / 'demo' / 'SKILL.md', 'x')
        self.assertEqual(eb.baseline_cache('demo')['cache_dir'], str(self.cache / 'demo'))

    def test_blind_baseline_is_marked(self):
        shutil.rmtree(self.rpm)
        b = eb.baseline_cache('demo')
        self.assertIsNone(b['creation_time'])
        self.assertEqual(b['unreadable_roots'], [str(self.rpm)])


class VerifyInstalledCache(Fixture):
    def _main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = vic.main(argv)
        return code, buf.getvalue()

    def test_rpm_installs_are_inspected(self):
        _write(self.rpm / 'plugin_A' / 'skills' / 'ora-a' / 'SKILL.md',
               '---\nname: ora-a\ndescription: rpm copy\n---\nbody\n')
        _write(self.cache / 'docx' / 'SKILL.md',
               '---\nname: docx\ndescription: legacy copy\n---\nbody\n')
        code, out = self._main([])
        self.assertEqual(code, 0)
        self.assertIn('ora-a', out)
        self.assertIn('docx', out)
        self.assertIn('2 installed copy(ies) inspected', out)

    def test_unreachable_root_fails_closed(self):
        _write(self.cache / 'docx' / 'SKILL.md', '---\nname: docx\ndescription: d\n---\n')
        shutil.rmtree(self.rpm)
        code, out = self._main([])
        self.assertEqual(code, 1)
        self.assertIn('install root unreadable', out)
        self.assertNotIn('docx ', out)


if __name__ == '__main__':
    unittest.main(verbosity=2)
