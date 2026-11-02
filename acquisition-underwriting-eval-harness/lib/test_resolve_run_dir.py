"""resolve_run_dir() is the ONE place the harness's runs/ location is decided (v1.3).

Regression for 2026-10-30: Step 4's run_dir="runs/" followed the CWD and
parse_replays.py defaulted to "<running copy>/runs", so a run launched from the
INSTALLED copy wrote 12 snapshots into the platform's skills cache, which every
re-install wipes.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import record_run as rr  # noqa: E402
from test_record_run import _result  # noqa: E402  (a valid diff_verdict() dict)

CACHE = os.path.join(tempfile.gettempdir(), "AppData", "Roaming", "Claude", "local-agent-mode-sessions",
                     "skills-plugin", "a", "b", "skills", "acquisition-underwriting-eval-harness", "runs")


class ResolveRunDir(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.runs = os.path.join(self.tmp.name, "canonical-runs")
        self.env = mock.patch.dict(os.environ, {"ORA_EVAL_HARNESS_RUNS_DIR": self.runs})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_none_and_runs_aliases_resolve_to_the_override_from_any_cwd(self):
        old = os.getcwd()
        with tempfile.TemporaryDirectory() as elsewhere:
            os.chdir(elsewhere)
            try:
                for v in (None, "runs", "runs/", "./runs", ".\\runs"):
                    self.assertEqual(rr.resolve_run_dir(v), os.path.normpath(self.runs), v)
            finally:
                os.chdir(old)

    def test_other_relative_paths_raise(self):
        for v in ("out", "..\\..\\x", "runs/sub"):
            with self.assertRaises(ValueError, msg=v):
                rr.resolve_run_dir(v)

    def test_absolute_is_kept(self):
        self.assertEqual(rr.resolve_run_dir(self.tmp.name), os.path.normpath(self.tmp.name))

    def test_runtime_cache_is_refused_directly_via_env_and_via_record_run(self):
        with self.assertRaises(ValueError):
            rr.resolve_run_dir(CACHE)
        with mock.patch.dict(os.environ, {"ORA_EVAL_HARNESS_RUNS_DIR": CACHE}):
            with self.assertRaises(ValueError):
                rr.resolve_run_dir(None)
        with self.assertRaises(ValueError):
            # a VALID result, so the path check -- not the empty-results guard -- is what raises
            rr.record_run([_result("a")], run_dir=CACHE, run_timestamp="2026-10-30T000000Z")

    def test_relative_override_is_rejected(self):
        with mock.patch.dict(os.environ, {"ORA_EVAL_HARNESS_RUNS_DIR": "relative/runs"}):
            with self.assertRaises(ValueError):
                rr.default_run_dir()

    def test_no_override_and_no_repo_copy_raises(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ORA_EVAL_HARNESS_RUNS_DIR", None)
            with mock.patch.object(rr, "_CANONICAL_HARNESS_DIR", os.path.join(self.tmp.name, "absent")):
                with self.assertRaises(ValueError):
                    rr.default_run_dir()

    def test_windows_branch_uses_the_repo_copy_when_it_exists(self):
        # exercised on every platform by pretending to be Windows (gate finding: on
        # Linux os.name short-circuited this branch, so its guard was never tested)
        os.environ.pop("ORA_EVAL_HARNESS_RUNS_DIR", None)
        home = os.path.join(self.tmp.name, "harness")
        os.makedirs(home)
        with mock.patch.object(rr.os, "name", "nt"), mock.patch.object(rr, "_CANONICAL_HARNESS_DIR", home):
            self.assertEqual(rr.default_run_dir(), os.path.normpath(os.path.join(home, "runs")))
        with mock.patch.object(rr.os, "name", "nt"), \
                mock.patch.object(rr, "_CANONICAL_HARNESS_DIR", os.path.join(self.tmp.name, "absent")):
            with self.assertRaises(ValueError):
                rr.default_run_dir()

    def test_record_run_with_no_run_dir_writes_to_the_canonical_dir(self):
        rr.record_run([_result("a")], run_timestamp="2026-10-30T000000Z")
        names = os.listdir(self.runs)
        self.assertIn("summary.csv", names)
        self.assertTrue(any(n.endswith(".json") for n in names), names)


class ParseReplaysUsesTheResolver(unittest.TestCase):
    """parse_replays --record with NO --run-dir must land in the resolver's dir, and a
    run-dir error must keep the computed report (merge-gate findings, PR #196)."""

    def setUp(self):
        # helper FUNCTIONS only: importing a TestCase class would make pytest collect it
        from test_parse_replays import (GOLDEN_INPUTS, OTHER_INPUTS, _assistant, _block,
                                        _prompt, _result, _write_agent, _write_golden)
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.sub, self.gold = root / "subagents", root / "golden_set"
        self.sub.mkdir()
        self.gold.mkdir()
        _write_golden(self.gold, "deal-a", GOLDEN_INPUTS)
        _write_golden(self.gold, "deal-b", OTHER_INPUTS)
        for aid, inputs in (("a1", GOLDEN_INPUTS), ("b1", OTHER_INPUTS)):
            _write_agent(self.sub, aid, _prompt(inputs), [_assistant(_block(_result(10.0)), "r", "end_turn")])
        self.runs = os.path.join(self.tmp.name, "canonical-runs")

    def tearDown(self):
        self.tmp.cleanup()

    def _main(self, env):
        import contextlib
        import io
        import json
        from parse_replays import main
        buf = io.StringIO()
        with mock.patch.dict(os.environ, env), contextlib.redirect_stdout(buf):
            code = main(["--subagents-dir", str(self.sub), "--golden-dir", str(self.gold), "--record"])
        return code, json.loads(buf.getvalue())

    def test_default_run_dir_is_the_resolvers_not_the_script_dir(self):
        code, report = self._main({"ORA_EVAL_HARNESS_RUNS_DIR": self.runs})
        self.assertEqual(code, 0, report)
        self.assertNotIn("record_error", report)
        self.assertTrue(any(n.endswith(".json") for n in os.listdir(self.runs)))
        script_runs = Path(__file__).resolve().parent.parent / "runs"
        self.assertNotIn(os.path.normcase(str(script_runs)), os.path.normcase(str(report["recorded"])))

    def test_unresolvable_run_dir_keeps_the_report(self):
        os.environ.pop("ORA_EVAL_HARNESS_RUNS_DIR", None)
        with mock.patch.object(rr.os, "name", "nt"), \
                mock.patch.object(rr, "_CANONICAL_HARNESS_DIR", os.path.join(self.tmp.name, "absent")):
            code, report = self._main({})
        self.assertEqual(code, 4, report)
        self.assertIn("no canonical runs/ dir", report["record_error"])
        self.assertEqual(report["deals"]["deal-a"]["status"], "PASS")
        self.assertNotIn("recorded", report)


if __name__ == "__main__":
    unittest.main()
