"""Tests for the v4.61 tax and intake tools: prop_tax_timing.py (RE-4.61-4), uw_tieout.py (RE-4.61-2) and the
offline parts of dc_parcel_pull.py (RE-4.61-1). Network calls are never made here; the live DC acceptance call
(`python dc_parcel_pull.py --ssl "0067 0066"`) is a manual verification step.
Run: python acquisition-underwriting/scripts/test_tax_intake_tools.py"""
import contextlib
import datetime as dt
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import dc_parcel_pull as DCP  # noqa: E402
import prop_tax_timing as P  # noqa: E402


class PropTaxTiming(unittest.TestCase):
    """The module's own acceptance figures (handoff section 9.1)."""

    def test_dc_1500_21st_case_a(self):
        d = P.Deal("DC", dt.date(2027, 1, 1), 2_100_000, 4_359_090, 4_359_090)
        s = P.schedule(d, 2, "A")
        self.assertEqual([r["tax"] for r in s], [62_606.24, 34_866.56])

    def test_dc_reset_ty(self):
        self.assertEqual(P.dc_reset_ty(dt.date(2027, 1, 1)), 2028)
        self.assertEqual(P.dc_reset_ty(dt.date(2027, 6, 15)), 2028)
        self.assertEqual(P.dc_reset_ty(dt.date(2027, 10, 15)), 2029)

    def test_mi_walker_case_a(self):
        m = P.Deal("MI", dt.date(2026, 1, 1), 2_250_000, 562_626, 1_125_000, rate=0.04475, growth=0.0)
        self.assertEqual([r["tax"] for r in P.schedule(m, 2, "A")], [25_177.51, 50_343.75])

    def test_standing_pw_weights_20_50_30(self):
        # Gabriel in-turn 2026-11-24 (revised): PW = 20/50/30 (A/B/C), reported only
        self.assertEqual(P.Deal("DC", dt.date(2027, 1, 1), 1, 1, 1).weights, (0.2, 0.5, 0.3))

    def test_pw_is_the_weighted_mix(self):
        d = P.Deal("DC", dt.date(2027, 1, 1), 2_100_000, 4_359_090, 4_359_090)
        a, b, c, pw = (P.base_for(d, 2029, 1, k) for k in ("A", "B", "C", "PW"))
        self.assertAlmostEqual(pw, 0.2 * a + 0.5 * b + 0.3 * c, places=6)

    def test_dc_class2_step(self):
        self.assertEqual(P.dc_rate(5_000_000), 0.0165)
        self.assertEqual(P.dc_rate(5_000_001), 0.0177)
        self.assertEqual(P.dc_rate(10_000_001), 0.0189)


class UwTieout(unittest.TestCase):
    """Handoff section 7b on a synthetic workbook: PASS when every cell ties, FAIL (exit 1) when one value is off
    by +500, exit 2 on a missing cell."""

    @classmethod
    def setUpClass(cls):
        try:
            import openpyxl  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("openpyxl not installed")

    def _run(self, cells, rows=None, corrupt=None, extra=None, ratios=None):
        import openpyxl
        tmp = tempfile.mkdtemp()
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "PF_Base"
        for i, v in enumerate([14336.13, 119114.0, 142292.84], start=3):
            ws.cell(39, i, v)
        ws["E40"] = 142292.84
        ws["B120"] = 0.041725
        if corrupt:
            ws[corrupt] = ws[corrupt].value + 500
        for k, v in (extra or {}).items():
            ws[k] = v
        xlsx = os.path.join(tmp, "m.xlsx")
        wb.save(xlsx)
        exp = os.path.join(tmp, "e.json")
        with open(exp, "w", encoding="utf-8") as fh:
            json.dump({"tolerances": {"money": 1.0, "rate": 1e-4}, "cells": cells, "rows": rows or {},
                       "ratios": ratios or []}, fh)
        r = subprocess.run([sys.executable, "-B", os.path.join(HERE, "uw_tieout.py"), xlsx, exp],
                           capture_output=True, text=True, encoding="utf-8")
        return r.returncode, r.stdout

    CELLS = {"PF_Base!E40": 142292.84, "PF_Base!B120": 0.041725}
    ROWS = {"PF_Base!C39:E39": [14336.13, 119114.0, 142292.84]}

    def test_pass(self):
        rc, out = self._run(self.CELLS, self.ROWS)
        self.assertEqual(rc, 0, out)
        self.assertIn("Engine tie-out: PASS", out)
        self.assertIn("Checks: 5", out)

    def test_plus_500_fails_exit_1(self):
        rc, out = self._run(self.CELLS, self.ROWS, corrupt="E40")
        self.assertEqual(rc, 1, out)
        self.assertIn("FAIL", out)

    def test_formula_error_fails(self):
        for err in ("#REF!", "#SPILL!", "#CALC!"):
            rc, out = self._run(self.CELLS, extra={"A1": err})
            self.assertEqual(rc, 1, (err, out))
            self.assertIn("Formula errors", out)

    def test_empty_expected_is_input_error(self):
        rc, out = self._run({})
        self.assertEqual(rc, 2, out)

    def test_row_length_mismatch_is_input_error(self):
        rc, out = self._run(self.CELLS, {"PF_Base!C39:E39": [14336.13]})
        self.assertEqual(rc, 2, out)

    def test_ratio_cells_get_rate_tolerance(self):
        rc, _ = self._run({"PF_Base!F1": 6.9}, extra={"F1": 6.0})
        self.assertEqual(rc, 0)                       # vendored rule: >= 5 reads as money (+/-1.0)
        rc, out = self._run({"PF_Base!F1": 6.9}, extra={"F1": 6.0}, ratios=["PF_Base!F1"])
        self.assertEqual(rc, 1, out)

    def test_missing_cell_exit_2(self):
        rc, out = self._run({**self.CELLS, "PF_Base!Z99": 1.0})
        self.assertEqual(rc, 2, out)


class DcParcelOffline(unittest.TestCase):
    def test_ssl_key_pads_square_to_8(self):
        self.assertEqual(DCP.ssl_key("0067 0066"), "0067    0066")
        self.assertEqual(DCP.ssl_key("5128N 0012"), "5128N   0012")

    def test_ssl_key_rejects_bad_input(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            DCP.ssl_key("00670066")

    def _pull_with(self, flood):
        calls = []
        attrs = {"SSL": "0067    0066", "PREMISEADD": "X", "CLASSTYPE": "2", "NEWTOTAL": 1_000_000}
        feat = {"attributes": attrs, "geometry": {"rings": [[[-77.0, 38.9], [-77.0, 38.91], [-77.01, 38.9]]]}}

        def fake_get(url, params, timeout=40):
            calls.append(url)
            return {"features": [feat]} if "MapServer/40" in url else {"features": []}
        orig = DCP.get
        DCP.get = fake_get
        try:
            out = DCP.pull(ssl="0067 0066", flood=flood)
        finally:
            DCP.get = orig
        return out, calls

    def test_fema_not_called_by_default(self):
        out, calls = self._pull_with(False)
        self.assertFalse(any("hazards.fema.gov" in u for u in calls), calls)
        self.assertNotIn("flood", out)
        self.assertIn("flood_note", out)

    def test_fema_only_with_flood_flag(self):
        _, calls = self._pull_with(True)
        self.assertTrue(any("hazards.fema.gov" in u for u in calls), calls)

    def test_class_rate(self):
        self.assertEqual(DCP.class_rate("2", 4_359_090), 0.0165)
        self.assertEqual(DCP.class_rate("2", 5_000_000), 0.0165)        # whole-value step: <= USD 5M
        self.assertEqual(DCP.class_rate("2", 5_000_001), 0.0177)
        self.assertEqual(DCP.class_rate("2", 6_000_000), 0.0177)
        self.assertEqual(DCP.class_rate("1", 1), 0.0085)


if __name__ == "__main__":
    unittest.main()
