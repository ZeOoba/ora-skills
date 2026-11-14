"""tools/hook_pin_check.py: warn after a merge/rebase that leaves install_hooks.py's pinned
scanner/shims stale (2026-11-13, after #257). Never re-pins, never fails the merge."""
import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hook_pin_check as hpc  # noqa: E402


class Check(unittest.TestCase):
    def _check(self, changed, rc=1, out='DRIFT: stale pin'):
        calls = []

        def run(repo):
            calls.append(repo)
            return rc, out
        buf = io.StringIO()
        with redirect_stderr(buf):
            verdict = hpc.check(Path('/r'), 'A', 'B', changed=lambda *a: changed, run=run,
                                gate=lambda r: True)
        return verdict, calls, buf.getvalue()

    def test_outside_the_primary_on_main_it_stays_silent(self):
        # PR #260 review finding 2: advice from an older worktree would downgrade the pin.
        calls = []
        verdict = hpc.check(Path('/r'), 'A', 'B', changed=lambda *a: ['tools/hooks/pre-push'],
                            run=lambda r: calls.append(r) or (1, 'x'), gate=lambda r: False)
        self.assertEqual((verdict, calls), ('skip', []))

    def test_unrelated_merge_does_not_run_the_check(self):
        verdict, calls, err = self._check([])
        self.assertEqual((verdict, calls, err), ('skip', [], ''))

    def test_scanner_change_with_stale_pin_warns_with_the_repin_command(self):
        verdict, calls, err = self._check(['tools/prepush_confidential_scan.py'])
        self.assertEqual(verdict, 'stale')
        self.assertEqual(len(calls), 1)
        self.assertIn('WARNING', err)
        self.assertIn('install_hooks.py --repo', err)
        self.assertIn('DRIFT: stale pin', err)

    def test_scanner_change_with_current_pin_is_quiet(self):
        verdict, _, err = self._check(['tools/hooks/pre-push'], rc=0, out='ok')
        self.assertEqual((verdict, err), ('ok', ''))

    def test_unreadable_range_checks_anyway(self):
        verdict, calls, err = self._check(None)
        self.assertEqual(verdict, 'stale')
        self.assertEqual(len(calls), 1)
        self.assertIn('no ORIG_HEAD', err)

    def test_main_always_exits_0_even_when_check_raises(self):
        orig = hpc.check
        hpc.check = lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom'))
        try:
            with redirect_stderr(io.StringIO()):
                self.assertEqual(hpc.main(['--range', 'X', 'Y']), 0)
        finally:
            hpc.check = orig


class ChangedPinnedInputsLiveGit(unittest.TestCase):
    """The real `git diff` path, in a throwaway repo."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.r = Path(self.tmp.name)
        g = lambda *a: subprocess.run(['git', '-C', str(self.r), *a], check=True, capture_output=True)
        self.g = g
        g('init', '-q')
        g('config', 'user.email', 't@example.invalid')
        g('config', 'user.name', 't')
        (self.r / 'tools' / 'hooks').mkdir(parents=True)
        (self.r / 'tools' / 'prepush_confidential_scan.py').write_text('v1\n')
        (self.r / 'README.md').write_text('a\n')
        g('add', '-A')
        g('commit', '-qm', 'base')

    def tearDown(self):
        self.tmp.cleanup()

    def test_detects_scanner_and_hook_changes_only(self):
        (self.r / 'README.md').write_text('b\n')
        self.g('commit', '-qam', 'docs')
        self.assertEqual(hpc.changed_pinned_inputs(self.r, 'HEAD~1', 'HEAD'), [])
        (self.r / 'tools' / 'prepush_confidential_scan.py').write_text('v2\n')
        (self.r / 'tools' / 'hooks' / 'post-merge').write_text('#!/bin/sh\n')
        self.g('add', '-A')
        self.g('commit', '-qm', 'scanner')
        self.assertEqual(sorted(hpc.changed_pinned_inputs(self.r, 'HEAD~1', 'HEAD')),
                         ['tools/hooks/post-merge', 'tools/prepush_confidential_scan.py'])

    def test_missing_ref_reads_as_unknown(self):
        self.assertIsNone(hpc.changed_pinned_inputs(self.r, 'ORIG_HEAD', 'HEAD'))

    def test_primary_on_main_gate(self):
        self.g('branch', '-M', 'main')
        self.assertTrue(hpc.primary_on_main(self.r))
        self.g('checkout', '-q', '-b', 'feature')
        self.assertFalse(hpc.primary_on_main(self.r), 'a branch other than main')
        self.g('checkout', '-q', 'main')
        wt = Path(self.tmp.name + '-wt')
        self.g('worktree', 'add', '-q', '-b', 'wt-branch', str(wt))
        self.addCleanup(lambda: __import__('shutil').rmtree(wt, ignore_errors=True))
        self.assertFalse(hpc.primary_on_main(wt), 'a linked worktree is never the primary')


if __name__ == '__main__':
    unittest.main()
