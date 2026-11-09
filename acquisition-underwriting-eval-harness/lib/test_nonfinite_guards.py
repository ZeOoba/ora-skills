"""Non-finite number guards across the eval-harness gate (added 2026-11-08).

Audit row eval-harness-nan-passes: `_require_number` accepted float NaN, and
`abs(NaN) > tol` is False, so a NaN combined score or a NaN tolerance produced
PASS. Every number guard must now reject NaN and +/-Infinity, and every JSON
load on the replay/golden path must refuse the non-standard NaN/Infinity
literals that Python's json module accepts by default.

Kept in its own file (not test_parse_replays.py) so it runs in CI: that file
carries a CI_EXCLUDE for an unrelated filesystem case-folding case.
"""

import json
import math
import tempfile
import unittest
from pathlib import Path

from aggregate_replays import aggregate_replays
from diff_verdict import diff_verdict
from parse_replays import ReplayParseError, collect_replays, extract_json_block, load_json_strict

NAN = float("nan")
INF = float("inf")
FENCE = "`" * 3


def _golden(combined=65.0, tolerance=3.0, category_breakdown=None):
    return {
        "deal_id": "zephyr-test",
        "confidence": "HIGH",
        "known_gaps": [],
        "golden": {"combined": combined, "verdict_tier": "T2 WATCH", "floor_result": "N/A",
                   "category_breakdown": category_breakdown},
        "diff_policy": {"tolerance_combined_pts": tolerance},
    }


def _observed(combined=65.0, category_breakdown=None, aggregate=None):
    obs = {"combined": combined, "verdict_tier": "T2 WATCH", "floor_result": "N/A",
           "category_breakdown": category_breakdown}
    if aggregate is not None:
        obs["aggregate"] = aggregate
    return obs


class TestDiffVerdictRejectsNonFinite(unittest.TestCase):
    def _assert_never_pass(self, golden, observed):
        try:
            result = diff_verdict(golden, observed)
        except ValueError:
            return
        self.fail(f"non-finite input returned a verdict instead of raising: {result['status']}")

    def test_nan_observed_combined(self):
        self._assert_never_pass(_golden(), _observed(combined=NAN))

    def test_nan_golden_combined(self):
        self._assert_never_pass(_golden(combined=NAN), _observed())

    def test_nan_tolerance(self):
        self._assert_never_pass(_golden(tolerance=NAN), _observed(combined=99.0))

    def test_infinite_tolerance(self):
        self._assert_never_pass(_golden(tolerance=INF), _observed(combined=99.0))

    def test_negative_infinite_observed(self):
        self._assert_never_pass(_golden(), _observed(combined=-INF))

    def test_finite_values_still_pass(self):
        self.assertEqual(diff_verdict(_golden(), _observed(combined=66.0))["status"], "PASS")

    def test_nan_category_is_a_gap_not_a_delta(self):
        result = diff_verdict(_golden(category_breakdown={"basis": 20.0, "yield": 10.0}),
                              _observed(category_breakdown={"basis": NAN, "yield": 11.0}))
        self.assertIsNone(result["category_deltas"]["basis"])
        self.assertEqual(result["category_deltas"]["yield"], 1.0)

    def test_nan_golden_category_is_a_gap_not_dropped(self):
        result = diff_verdict(_golden(category_breakdown={"basis": NAN}),
                              _observed(category_breakdown={"basis": 20.0}))
        self.assertIn("basis", result["category_deltas"])
        self.assertIsNone(result["category_deltas"]["basis"])

    def test_nan_combined_range_raises(self):
        with self.assertRaises(ValueError):
            diff_verdict(_golden(), _observed(aggregate={"n": 3, "combined_range": NAN}))


class TestAggregateRejectsNonFinite(unittest.TestCase):
    def test_nan_combined_replay_raises(self):
        with self.assertRaises(ValueError):
            aggregate_replays([{"combined": 20.0}, {"combined": NAN}, {"combined": 21.0}])

    def test_infinite_combined_replay_raises(self):
        with self.assertRaises(ValueError):
            aggregate_replays([{"combined": INF}])

    def test_nan_category_counts_as_null(self):
        out = aggregate_replays([{"combined": 20.0, "category_breakdown": {"basis": NAN}},
                                 {"combined": 20.0, "category_breakdown": {"basis": 20.0}}])
        self.assertEqual(out["category_breakdown"]["basis"], 10.0)
        self.assertEqual(out["aggregate"]["category_null_counts"]["basis"], 1)

    def test_nan_scalar_excluded_from_mean(self):
        out = aggregate_replays([{"combined": 20.0, "quality": NAN},
                                 {"combined": 20.0, "quality": 10.0}])
        self.assertEqual(out["quality"], 10.0)


class TestStrictJsonLoading(unittest.TestCase):
    def test_load_json_strict_rejects_nan_literal(self):
        for literal in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(literal=literal), self.assertRaises(ValueError):
                load_json_strict('{"combined": %s}' % literal)

    def test_load_json_strict_rejects_overflow_to_infinity(self):
        with self.assertRaises(ValueError):
            load_json_strict('{"combined": 1e999}')

    def test_load_json_strict_accepts_ordinary_json(self):
        self.assertEqual(load_json_strict('{"combined": 1.5}'), {"combined": 1.5})

    def test_fenced_block_with_nan_fails(self):
        with self.assertRaises(ReplayParseError):
            extract_json_block(f"{FENCE}json\n{{\"combined\": NaN}}\n{FENCE}")

    def test_golden_file_with_nan_tolerance_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            golden_dir = Path(d) / "golden"
            golden_dir.mkdir()
            (golden_dir / "zephyr.json").write_text(
                '{"deal_id": "zephyr", "inputs": {}, "confidence": "HIGH", '
                '"diff_policy": {"tolerance_combined_pts": NaN}, "golden": {"combined": 10.0}}',
                encoding="utf-8")
            subagents = Path(d) / "subagents"
            subagents.mkdir()
            with self.assertRaises(ValueError):
                collect_replays(subagents, golden_dir)

    def test_sanity_python_json_accepts_nan_by_default(self):
        # Documents WHY the strict loader exists: stdlib json accepts the literal.
        self.assertTrue(math.isnan(json.loads('{"x": NaN}')["x"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
