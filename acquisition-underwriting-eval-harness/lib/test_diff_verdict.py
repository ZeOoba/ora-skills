"""Tests for lib/diff_verdict.py — golden-set comparison/tolerance engine.

Written FIRST (TDD). Fixtures mirror the real golden_set/*.json shape:
top-level `confidence` and `diff_policy`; scores under `golden`;
`quality`/`economics`/`category_breakdown` sometimes null; Hamilton-style
breakdowns carry non-numeric `*_flag` entries that must be skipped.

Also loads the 6 real golden files as a smoke check that the engine
handles every real row without error.
"""

import copy
import json
import unittest
from pathlib import Path

from diff_verdict import diff_verdict

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden_set"


def make_golden(
    deal_id="test-deal",
    confidence="HIGH",
    combined=65.0,
    golden_tier="T2 WATCH",
    category_breakdown=None,
    known_gaps=None,
    tolerance=3.0,
):
    return {
        "deal_id": deal_id,
        "deal_name": "Test Deal",
        "mode": "SCREEN",
        "confidence": confidence,
        "known_gaps": known_gaps if known_gaps is not None else [],
        "inputs": {},
        "golden": {
            "quality": None,
            "economics": None,
            "combined": combined,
            "category_breakdown": category_breakdown,
            "expected_score": None,
            "p_exec_pct": None,
            "verdict_tier": golden_tier,
            "bands_predicted_tier": "T2 WATCH",
            "floor_result": "N/A",
        },
        "diff_policy": {
            "primary_signal": "combined_score",
            "tolerance_combined_pts": tolerance,
            "tier_check": "informational_only",
        },
    }


def make_observed(
    combined=65.0,
    verdict_tier="T2 WATCH",
    category_breakdown=None,
):
    return {
        "combined": combined,
        "quality": None,
        "economics": None,
        "expected_score": None,
        "p_exec_pct": None,
        "verdict_tier": verdict_tier,
        "floor_result": "N/A",
        "category_breakdown": category_breakdown,
        "notes": "",
    }


class TestPassFlag(unittest.TestCase):
    def test_pass_within_tolerance(self):
        """(a) Observed within tolerance -> PASS."""
        result = diff_verdict(make_golden(combined=65.0), make_observed(combined=66.5))
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(result["scored"])
        self.assertFalse(result["informational_only"])
        self.assertAlmostEqual(result["combined_delta"], 1.5)
        self.assertEqual(result["combined_golden"], 65.0)
        self.assertEqual(result["combined_observed"], 66.5)
        self.assertEqual(result["tolerance_pts"], 3.0)
        self.assertEqual(result["deal_id"], "test-deal")

    def test_flag_beyond_tolerance(self):
        """(b) Observed beyond tolerance -> FLAG (both directions)."""
        result = diff_verdict(make_golden(combined=65.0), make_observed(combined=70.0))
        self.assertEqual(result["status"], "FLAG")
        self.assertAlmostEqual(result["combined_delta"], 5.0)

        result_neg = diff_verdict(make_golden(combined=65.0), make_observed(combined=60.5))
        self.assertEqual(result_neg["status"], "FLAG")
        self.assertAlmostEqual(result_neg["combined_delta"], -4.5)

    def test_boundary_exactly_at_tolerance_is_pass(self):
        """(d) |delta| == tolerance is PASS — only strictly-beyond flags."""
        result = diff_verdict(make_golden(combined=65.0), make_observed(combined=68.0))
        self.assertAlmostEqual(result["combined_delta"], 3.0)
        self.assertEqual(result["status"], "PASS")

        result_neg = diff_verdict(make_golden(combined=65.0), make_observed(combined=62.0))
        self.assertAlmostEqual(result_neg["combined_delta"], -3.0)
        self.assertEqual(result_neg["status"], "PASS")


class TestConfidenceScoring(unittest.TestCase):
    def test_low_confidence_not_scored_but_delta_reported(self):
        """(c) LOW confidence -> scored False even with a large delta; delta still computed."""
        golden = make_golden(confidence="LOW", combined=48.0)
        result = diff_verdict(golden, make_observed(combined=60.0))
        self.assertFalse(result["scored"])
        self.assertTrue(result["informational_only"])
        self.assertAlmostEqual(result["combined_delta"], 12.0)
        # Status still computed/reported (delta > tolerance -> FLAG label),
        # but scored=False tells the caller to exclude it from strict tallies.
        self.assertEqual(result["status"], "FLAG")
        self.assertTrue(
            any("LOW confidence" in n for n in result["notes"]),
            f"expected a LOW-confidence exclusion note in {result['notes']}",
        )

    def test_high_and_medium_confidence_scored(self):
        for conf in ("HIGH", "MEDIUM"):
            result = diff_verdict(
                make_golden(confidence=conf), make_observed()
            )
            self.assertTrue(result["scored"], f"confidence={conf} should be scored")
            self.assertFalse(result["informational_only"])

    def test_unrecognized_confidence_raises_not_silently_excludes(self):
        """REFUTE-pass finding: `scored = confidence in ("HIGH","MEDIUM")` used to
        silently treat any typo'd or missing confidence value (e.g. "High", "") as
        equivalent to LOW -- excluding a row from the strict pass/fail tally without
        anyone deciding to. Must raise instead."""
        for bad_confidence in ("High", "", None, "MED"):
            golden = make_golden(confidence=bad_confidence)
            with self.assertRaises(ValueError):
                diff_verdict(golden, make_observed())


class TestTierInformational(unittest.TestCase):
    def test_reads_golden_verdict_tier_key_not_archived_verdict_tier(self):
        """Regression test: a 2026-08-14 rebaseline renamed golden['golden']'s tier
        key from archived_verdict_tier to verdict_tier. diff_verdict.py briefly read
        the old name after the rename, silently returning archived_tier=None for
        every real golden file -- caught by the mutated-input self-test (see
        SKILL.md 'Self-test'), not by this suite, because make_golden() had drifted
        to match the same stale key name as the bug. Assert directly against a
        golden dict shaped like the REAL schema (verdict_tier only, no
        archived_verdict_tier key at all) so this class of key-rename desync
        cannot silently reintroduce itself.
        """
        golden = make_golden(combined=65.0, golden_tier="T2 WATCH")
        self.assertNotIn(
            "archived_verdict_tier",
            golden["golden"],
            "make_golden() fixture must match the real golden_set/*.json schema "
            "(verdict_tier), not the retired archived_verdict_tier key name",
        )
        result = diff_verdict(golden, make_observed(combined=65.0, verdict_tier="T2 WATCH"))
        self.assertEqual(result["golden_tier"], "T2 WATCH")
        self.assertTrue(result["tier_match"])

    def test_tier_mismatch_alone_does_not_flag(self):
        """(e) Combined matches, tier differs -> still PASS; tier reported."""
        golden = make_golden(combined=65.0, golden_tier="T2 WATCH")
        observed = make_observed(combined=65.0, verdict_tier="T1 PURSUE")
        result = diff_verdict(golden, observed)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["tier_match"])
        self.assertEqual(result["golden_tier"], "T2 WATCH")
        self.assertEqual(result["observed_tier"], "T1 PURSUE")

    def test_tier_match_reported(self):
        result = diff_verdict(
            make_golden(golden_tier="T2 WATCH"),
            make_observed(verdict_tier="T2 WATCH"),
        )
        self.assertTrue(result["tier_match"])

    def test_tier_match_ignores_parenthetical_annotation(self):
        """REDACTED-148's golden tier is 'KILLED (post-hoc status overwrite, ...)' —
        normalization compares the label before the parenthetical."""
        golden = make_golden(
            golden_tier="KILLED (post-hoc status overwrite, not a skill verdict band -- see known_gaps)"
        )
        result = diff_verdict(golden, make_observed(verdict_tier="KILLED"))
        self.assertTrue(result["tier_match"])


class TestCategoryBreakdown(unittest.TestCase):
    def test_category_deltas_when_both_present(self):
        """(f) Per-category deltas computed; non-numeric *_flag entries skipped."""
        golden_bd = {
            "basis": 20,
            "basis_flag": "[est]",
            "yield": 0,
            "yield_flag": "[est]",
            "product_physical": 10,
        }
        observed_bd = {"basis": 22, "yield": 1.0, "product_physical": 10}
        result = diff_verdict(
            make_golden(combined=30.0, category_breakdown=golden_bd),
            make_observed(combined=33.0, category_breakdown=observed_bd),
        )
        deltas = result["category_deltas"]
        self.assertIsNotNone(deltas)
        self.assertAlmostEqual(deltas["basis"], 2.0)
        self.assertAlmostEqual(deltas["yield"], 1.0)
        self.assertAlmostEqual(deltas["product_physical"], 0.0)
        self.assertNotIn("basis_flag", deltas)
        self.assertNotIn("yield_flag", deltas)
        # Category deltas never gate: |combined delta| == 3.0 -> still PASS.
        self.assertEqual(result["status"], "PASS")

    def test_category_none_safe_golden_null(self):
        result = diff_verdict(
            make_golden(category_breakdown=None),
            make_observed(category_breakdown={"basis": 20}),
        )
        self.assertIsNone(result["category_deltas"])

    def test_category_none_safe_observed_null(self):
        result = diff_verdict(
            make_golden(category_breakdown={"basis": 20}),
            make_observed(category_breakdown=None),
        )
        self.assertIsNone(result["category_deltas"])

    def test_category_key_missing_in_observed_reported_as_none(self):
        golden_bd = {"basis": 20, "yield": 4.2}
        observed_bd = {"basis": 20}
        result = diff_verdict(
            make_golden(category_breakdown=golden_bd),
            make_observed(category_breakdown=observed_bd),
        )
        self.assertAlmostEqual(result["category_deltas"]["basis"], 0.0)
        self.assertIsNone(result["category_deltas"]["yield"])


class TestNotes(unittest.TestCase):
    def test_known_gaps_carried_forward(self):
        gaps = ["NOI is not recorded anywhere.", "Scoring used a $700K walk price."]
        result = diff_verdict(make_golden(known_gaps=gaps), make_observed())
        for gap in gaps:
            self.assertTrue(
                any(gap in n for n in result["notes"]),
                f"known_gap not carried into notes: {gap}",
            )


class TestInputValidation(unittest.TestCase):
    def test_missing_observed_combined_raises(self):
        observed = make_observed()
        observed["combined"] = None
        with self.assertRaises(ValueError):
            diff_verdict(make_golden(), observed)

    def test_missing_tolerance_raises(self):
        golden = make_golden()
        del golden["diff_policy"]["tolerance_combined_pts"]
        with self.assertRaises(ValueError):
            diff_verdict(golden, make_observed())

    def test_inputs_not_mutated(self):
        golden = make_golden(category_breakdown={"basis": 20})
        observed = make_observed(category_breakdown={"basis": 21})
        golden_copy = copy.deepcopy(golden)
        observed_copy = copy.deepcopy(observed)
        diff_verdict(golden, observed)
        self.assertEqual(golden, golden_copy)
        self.assertEqual(observed, observed_copy)


class TestRealGoldenFiles(unittest.TestCase):
    """Smoke test: every real golden file runs through the engine cleanly."""

    def test_all_six_real_files(self):
        files = sorted(GOLDEN_DIR.glob("*.json"))
        self.assertEqual(len(files), 6, f"expected 6 golden files, found {len(files)}")
        # Re-baselined 2026-08-14: golden values are now the fresh replay under
        # current doctrine (see each file's known_gaps re: the RCT v03 date-boundary
        # finding), not the pre-v03 archived Notion scores. Confidence reflects how
        # many scorecard categories that fresh replay left null.
        expected_scored = {
            "REDACTED-027": False,      # LOW
            "REDACTED-021": False,    # LOW
            "REDACTED-031": False,         # LOW
            "REDACTED-024": True,      # HIGH
            # Enriched 2026-08-14 (real sourced physical specs, 3-run repeatability
            # check) -- promoted LOW -> MEDIUM. Tenancy & Lease stays null by design
            # (occupancy was a genuine unknown at the 6/9 screen date, not a research
            # gap), so it never reaches HIGH, but MEDIUM is scored=True same as HIGH.
            "REDACTED-020": True,    # MEDIUM
            "REDACTED-019": True,  # HIGH
        }
        for f in files:
            golden = json.loads(f.read_text(encoding="utf-8"))
            # Perfect replay: observed == golden values.
            g = golden["golden"]
            observed = make_observed(
                combined=g["combined"],
                verdict_tier=g["verdict_tier"],
                category_breakdown=g.get("category_breakdown"),
            )
            result = diff_verdict(golden, observed)
            self.assertEqual(result["status"], "PASS", f.name)
            self.assertAlmostEqual(result["combined_delta"], 0.0, msg=f.name)
            self.assertEqual(
                result["scored"], expected_scored[golden["deal_id"]], f.name
            )
            # Widened 3.0 -> 5.0 harness-wide after the repeatability check (see
            # SKILL.md 'Limitations') showed a 3-run range as large as 4.5 pts.
            self.assertEqual(result["tolerance_pts"], 5.0, f.name)
            # Golden files with a breakdown produce deltas; null stays None.
            if g.get("category_breakdown"):
                self.assertIsNotNone(result["category_deltas"], f.name)
                for v in result["category_deltas"].values():
                    self.assertAlmostEqual(v, 0.0, msg=f.name)
            else:
                self.assertIsNone(result["category_deltas"], f.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
