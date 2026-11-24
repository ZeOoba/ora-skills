"""Tests for reimport_cycle.gate_failures (pure gate logic).

Stdlib only — run with `python tools/test_reimport_cycle.py` (no pytest).

Converted 2026-09-23 from bare pytest-style `def test_*` functions, which
`python <file>` (tools/run_suite.sh) never executed: the file exited 0 having
run zero tests and was reported `ok`. run_suite.sh now fails any file that
does not print `Ran N tests` with N >= 1.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reimport_cycle as rc  # noqa: E402

SKILL = "loi-generation"  # exists in the repo
clean = lambda s: False  # noqa: E731
dirty = lambda s: True  # noqa: E731
no_plugin = lambda s: None  # noqa: E731


class GateFailures(unittest.TestCase):
    def test_clean_standalone_passes(self):
        self.assertEqual(rc.gate_failures(SKILL, no_plugin, clean, set(), ""), [])

    def test_plugin_member_stops(self):
        bad = rc.gate_failures(SKILL, lambda s: "ora-ops", clean, set(), "")
        self.assertTrue(any("plugin member" in b for b in bad), bad)

    def test_dirty_tree_stops(self):
        bad = rc.gate_failures(SKILL, no_plugin, dirty, set(), "")
        self.assertTrue(any("dirty" in b for b in bad), bad)

    def test_missing_skill_stops(self):
        bad = rc.gate_failures("no-such-skill-xyz", no_plugin, clean, set(), "")
        self.assertTrue(any("SKILL.md" in b for b in bad), bad)

    def test_cache_ahead_stops_only_consumer(self):
        rep = f"  target-markets.json: CACHE-AHEAD {SKILL}"
        self.assertTrue(rc.gate_failures(SKILL, no_plugin, clean, {SKILL}, rep))
        self.assertEqual(rc.gate_failures(SKILL, no_plugin, clean, set(), rep), [])

    def test_ok_dep_report_passes_consumer(self):
        rep = f"  target-markets.json: OK\n     in sync: {SKILL}"
        self.assertEqual(rc.gate_failures(SKILL, no_plugin, clean, {SKILL}, rep), [])

    def test_every_bad_label_stops(self):
        # Pinned labels, not just rc.BAD_DEP_LABELS: dropping one from the tuple
        # must fail here rather than silently shrink the loop.
        for lbl in sorted({"CACHE-AHEAD", "DIVERGENT", "UNKNOWN"} | set(rc.BAD_DEP_LABELS)):
            with self.subTest(label=lbl):
                self.assertTrue(
                    rc.gate_failures(SKILL, no_plugin, clean, {SKILL}, f"dep: {lbl} {SKILL}"))



class PrepStopsWhenSharedDepsDidNotRun(unittest.TestCase):
    """shared-deps exits 2 (no rows) when an install root is unreadable; prep must not
    read the empty output as a clean shared-dep gate (2026-11-23 refute, round 2)."""

    def test_nonzero_shared_deps_stops_prep(self):
        import io
        import subprocess
        import tempfile
        import unittest.mock
        from contextlib import redirect_stdout
        failed = subprocess.CompletedProcess([], 2, stdout='', stderr='install root unreadable')
        with unittest.mock.patch.object(rc, '_run', return_value=failed) as run,                 unittest.mock.patch.object(rc, '_git_dirty', return_value=False),                 redirect_stdout(io.StringIO()) as out:
            code = rc.cmd_prep(['loi-generation'], Path(tempfile.mkdtemp()) / 'out')
        self.assertEqual(code, 1)
        self.assertIn('shared-deps check did not run', out.getvalue())
        self.assertEqual(run.call_count, 1, 'nothing may be packaged after the gate stops')


if __name__ == '__main__':
    unittest.main()
