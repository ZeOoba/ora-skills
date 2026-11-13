"""Fail-closed tests for the private RCT table loader. Run: python acquisition-underwriting/scripts/test_rct_table.py

Every figure here is INVENTED (fixtures/rct-table.synthetic.json). Never use a real RCT value in this file.
"""
import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ora_walk import rct_table as R  # noqa: E402
from ora_walk.solver import Deal, solve  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "rct-table.synthetic.json"
SYN = json.loads(FIXTURE.read_text(encoding="utf-8"))


def as_real(t):
    """The synthetic fixture relabelled as a ratified copy, to exercise the non-synthetic checks."""
    t = copy.deepcopy(t)
    t.pop("_synthetic", None)
    t["rctVersion"] = R.RCT_VERSION
    return t


def bad(mutate):
    t = as_real(SYN)
    mutate(t)
    return t


class Validate(unittest.TestCase):
    def test_well_formed_copy_accepted(self):
        self.assertIs(type(R.validate(as_real(SYN))), dict)

    def test_synthetic_refused_unless_code_allows(self):
        with self.assertRaisesRegex(R.RctTableUnavailable, "synthetic"):
            R.validate(SYN)
        R.validate(SYN, allow_synthetic=True)
        flagged_only = as_real(SYN)
        flagged_only["_synthetic"] = True
        with self.assertRaisesRegex(R.RctTableUnavailable, "synthetic"):
            R.validate(flagged_only)

    def test_wrong_version_refused(self):
        with self.assertRaisesRegex(R.RctTableUnavailable, "rctVersion"):
            R.validate(bad(lambda t: t.update(rctVersion="RCT v02")))

    def test_market_set_and_order_pinned(self):
        def drop(t):
            t["markets"].pop("Chicago-Cook IL")
        def reorder(t):
            t["markets"] = dict(reversed(list(t["markets"].items())))
        def extra(t):
            t["markets"]["Nowhere ZZ"] = dict(t["markets"]["Columbus OH"])
        for m in (drop, reorder, extra):
            with self.assertRaisesRegex(R.RctTableUnavailable, "market rows", msg=m.__name__):
                R.validate(bad(m))

    def test_numbers_bounded_and_finite(self):
        for v in (float("nan"), float("inf"), True, "240", None, 10.0, 5000.0):
            with self.assertRaises(R.RctTableUnavailable, msg=repr(v)):
                R.validate(bad(lambda t, v=v: t["markets"]["Columbus OH"].update(point=v)))

    def test_mistyped_column_refused(self):
        # LOW off by more than a cent of rounding from 0.90 x POINT: a typo, a stale row or a swapped column
        with self.assertRaisesRegex(R.RctTableUnavailable, "POINT -/\\+10%"):
            R.validate(bad(lambda t: t["markets"]["Columbus OH"].update(low=t["markets"]["Columbus OH"]["low"] + 1)))
        with self.assertRaisesRegex(R.RctTableUnavailable, "LOW < POINT < HIGH"):
            R.validate(bad(lambda t: t["markets"]["Columbus OH"].update(high=t["markets"]["Columbus OH"]["low"])))

    def test_markdown_must_agree_with_numbers(self):
        def edit_md(t):
            t["markdownTable"] = t["markdownTable"].replace("| 240.00 |", "| 241.00 |", 1)
        with self.assertRaisesRegex(R.RctTableUnavailable, "disagrees"):
            R.validate(bad(edit_md))
        with self.assertRaisesRegex(R.RctTableUnavailable, "markdownTable"):
            R.validate(bad(lambda t: t.pop("markdownTable")))

    def test_markdown_cell_may_carry_no_unbound_figure(self):
        # Adversarial review 2026-11-13: only the first number in a cell used to be checked.
        for old, new in (("| 240.00 |", "| 240.00 (revised 999) |"), ("| 240.00 |", "| 240.00e1 |"),
                         ("| 240.00 |", "| -240.00 |"), ("| 105.00 [SYNTHETIC] |", "| 105.00 [SYNTHETIC] 999 |"),
                         ("| 105.00 [SYNTHETIC] |", "| 105.00 |")):
            def edit(t, old=old, new=new):
                assert old in t["markdownTable"], old
                t["markdownTable"] = t["markdownTable"].replace(old, new, 1)
            with self.assertRaisesRegex(R.RctTableUnavailable, "disagrees", msg=new):
                R.validate(bad(edit))
        def extra_cell(t):
            t["markdownTable"] = t["markdownTable"].replace("| 240.00 |", "| 240.00 | 999 |", 1)
        with self.assertRaisesRegex(R.RctTableUnavailable, "5 cells"):
            R.validate(bad(extra_cell))

    def test_markdown_layout_is_bound(self):
        # Round-2 review: a swapped header, a replaced header or a stray line passed unchecked.
        def swap_header(t):
            t["markdownTable"] = t["markdownTable"].replace("| LOW $/SF | POINT $/SF | HIGH $/SF |",
                                                            "| HIGH $/SF | POINT $/SF | LOW $/SF |", 1)
        def stray_line(t):
            t["markdownTable"] = t["markdownTable"].replace("|---|---|---|---|---|\n",
                                                            "|---|---|---|---|---|\ncorrected POINT: 999.99\n", 1)
        def no_rule(t):
            t["markdownTable"] = t["markdownTable"].replace("|---|---|---|---|---|\n", "", 1)
        for m in (swap_header, stray_line, no_rule):
            with self.assertRaisesRegex(R.RctTableUnavailable, "layout|one row per market", msg=m.__name__):
                R.validate(bad(m))

    def test_note_cannot_carry_an_unbound_figure(self):
        def note(t):
            t["markets"]["Columbus OH"]["cwNote"] = "[SYNTHETIC] corrected 999.99"
            t["markdownTable"] = t["markdownTable"].replace("| 100.00 [SYNTHETIC] |",
                                                            "| 100.00 [SYNTHETIC] corrected 999.99 |", 1)
        with self.assertRaisesRegex(R.RctTableUnavailable, "cwNote carries a figure"):
            R.validate(bad(note))
        for text in ("$999", "999/SF", "999 /SF"):  # whole-dollar forms (round-3 review)
            def whole(t, text=text):
                t["markets"]["Columbus OH"]["cwNote"] = f"[SYNTHETIC] {text}"
                t["markdownTable"] = t["markdownTable"].replace("| 100.00 [SYNTHETIC] |",
                                                                f"| 100.00 [SYNTHETIC] {text} |", 1)
            with self.assertRaisesRegex(R.RctTableUnavailable, "cwNote carries a figure", msg=text):
                R.validate(bad(whole))
        def own_figure(t):  # a note may restate the row's own figure (the ratified Chicago note does)
            t["markets"]["Columbus OH"]["cwNote"] = "[SYNTHETIC] re-derives to POINT 240.01"
            t["markdownTable"] = t["markdownTable"].replace("| 100.00 [SYNTHETIC] |",
                                                            "| 100.00 [SYNTHETIC] re-derives to POINT 240.01 |", 1)
        R.validate(bad(own_figure))

    def test_derivation_mismatches_ties_parameters_to_rows(self):
        import math
        t = as_real(SYN)
        d = t["derivation"]
        cw = {}
        for name, m in t["markets"].items():
            b = math.log(m["point"] / (m["cwHard"] * d["softCostMultiplier"] * d["escalation"])) / math.log(
                R.CW_SMALL_RSF / d["referenceSf"])
            cw[name] = {"small25": m["cwHard"], "med25": m["cwHard"] / math.exp(b * math.log(R.CW_MEDIUM_RSF / R.CW_SMALL_RSF))}
        self.assertEqual(R.derivation_mismatches(t, cw), [])
        t["derivation"]["softCostMultiplier"] += 0.01
        self.assertEqual(R.derivation_mismatches(t, cw), list(R.RCT_MARKETS))
        self.assertEqual(R.derivation_mismatches(as_real(SYN), {}), list(R.RCT_MARKETS))

    def test_derivation_block_required_and_bounded(self):
        with self.assertRaisesRegex(R.RctTableUnavailable, "derivation block"):
            R.validate(bad(lambda t: t.pop("derivation")))
        for key, v in (("referenceSf", 25000.5), ("referenceSf", True), ("referenceSf", 200_000),
                       ("softCostMultiplier", 0.9), ("softCostMultiplier", float("nan")), ("escalation", 2.0),
                       ("formula", ""), ("escalationNote", None)):
            with self.assertRaisesRegex(R.RctTableUnavailable, f"derivation.{key}", msg=(key, v)):
                R.validate(bad(lambda t, key=key, v=v: t["derivation"].update({key: v})))

    def test_not_an_object(self):
        for v in (None, [], "x", 3):
            with self.assertRaises(R.RctTableUnavailable):
                R.validate(v)


class Load(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        R.use(None)
        env = {k: v for k, v in os.environ.items() if k != R.ENV_VAR}
        self.env = mock.patch.dict(os.environ, env, clear=True)
        self.env.start()
        self.paths = mock.patch.object(R, "DEFAULT_PATHS", (self.dir / "skill" / R.FILE_NAME, self.dir / R.FILE_NAME))
        self.paths.start()

    def tearDown(self):
        self.paths.stop()
        self.env.stop()
        R.use(None)
        self.tmp.cleanup()

    def write(self, rel, table):
        p = self.dir / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(table) if not isinstance(table, str) else table, encoding="utf-8")
        return p

    def test_missing_file_fails_closed_and_solver_produces_no_walk(self):
        with self.assertRaisesRegex(R.RctTableUnavailable, "not found"):
            R.load()
        with self.assertRaises(R.RctTableUnavailable):
            solve(Deal(name="T", sf=30_000, stabilized_noi=300_000, market="Columbus OH", year_built=1985,
                       construction_type="tilt-up"), 0.045)

    def test_skill_root_copy_wins_over_repo_root(self):
        self.write(R.FILE_NAME, "not json")
        self.write(f"skill/{R.FILE_NAME}", as_real(SYN))
        self.assertEqual(R.load()["rctVersion"], R.RCT_VERSION)

    def test_repo_root_copy_used_in_a_checkout(self):
        self.write(R.FILE_NAME, as_real(SYN))
        self.assertEqual(R.load()["rctVersion"], R.RCT_VERSION)

    def test_unreadable_json_fails_closed(self):
        self.write(R.FILE_NAME, "{not json")
        with self.assertRaisesRegex(R.RctTableUnavailable, "not JSON"):
            R.load()

    def test_synthetic_file_refused_even_via_env(self):
        p = self.write("elsewhere.json", SYN)
        os.environ[R.ENV_VAR] = str(p)
        with self.assertRaisesRegex(R.RctTableUnavailable, "synthetic"):
            R.load()

    def test_env_path_used(self):
        p = self.write("elsewhere.json", as_real(SYN))
        os.environ[R.ENV_VAR] = str(p)
        self.assertEqual(R.load()["rctVersion"], R.RCT_VERSION)

    def test_cli_exits_nonzero_without_table(self):
        from ora_walk.cli import main
        deal = self.write("deal.json", {"name": "T", "sf": 30_000, "stabilized_noi": 300_000,
                                        "market": "Columbus OH", "year_built": 1985,
                                        "construction_type": "tilt-up"})
        with mock.patch("sys.stdout"), mock.patch("sys.stderr"):
            self.assertEqual(main([str(deal), "--ust", "0.045"]), 3)


if __name__ == "__main__":
    unittest.main()
