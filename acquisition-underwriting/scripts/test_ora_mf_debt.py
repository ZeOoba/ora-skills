"""Tests for ora_mf_debt (agency / HUD fully-amortizing debt scenarios). Run: python acquisition-underwriting/scripts/test_ora_mf_debt.py"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ora_mf_debt as M  # noqa: E402
from ora_walk import doctrine as D  # noqa: E402

UST = 0.049955  # 30-day 10-yr UST average used on the 2026-11-20 validation run


class TestAmortization(unittest.TestCase):
    def test_fully_amortizes_at_term(self):
        self.assertAlmostEqual(M.balance(5e6, 0.0655, 35, 35), 0.0, delta=1.0)

    def test_balance_pinned_to_numpy_financial(self):
        # Independent oracle: -npf.fv(0.0655/12, 120, npf.pmt(0.0655/12, 420, 5e6), 5e6), computed once, hard-coded.
        self.assertAlmostEqual(M.balance(5e6, 0.0655, 35, 10), 4_478_556.985319717, places=3)

    def test_loan_year_one_pinned(self):
        # -sum(npf.ppmt / npf.ipmt over months 1..12) at 6.55%, 420 months, 5e6.
        d = M.loan_year(5e6, 0.0655, 35, 0.0, 1)
        self.assertAlmostEqual(d["principal"], 38_188.2559603294, places=3)
        self.assertAlmostEqual(d["interest"], 326_367.0771795625, places=3)

    def test_balance_zero_years_is_loan(self):
        self.assertAlmostEqual(M.balance(5e6, 0.0655, 35, 0), 5e6, places=4)

    def test_hud_constant_with_mip(self):
        c = M.constant(0.0655, 35, 0.0025)
        self.assertTrue(0.0754 < c < 0.0755, c)

    def test_pmt_closed_form(self):
        # 100,000 at 6%/12 over 360 months: textbook 599.55
        self.assertAlmostEqual(M._pmt(0.005, 360, 100_000), 599.55, places=2)

    def test_loan_year_principal_sums_to_loan(self):
        tot = sum(M.loan_year(1e6, 0.07, 30, 0.0, k)["principal"] for k in range(1, 31))
        self.assertAlmostEqual(tot, 1e6, delta=1.0)

    def test_loan_year_mip_on_average_balance(self):
        d = M.loan_year(1e6, 0.065, 35, 0.0025, 1)
        self.assertAlmostEqual(d["mip"], 0.0025 * (d["b0"] + d["b1"]) / 2, places=6)
        self.assertAlmostEqual(d["ds"], d["principal"] + d["interest"] + d["mip"], places=6)

    def test_zero_rate(self):
        self.assertAlmostEqual(M.balance(1200, 0.0, 10, 5), 600, places=6)


class TestSizing(unittest.TestCase):
    NOI, VALUE = 621_045, 8_872_071

    def test_hud_binds_ltv(self):
        s = M.size_loan(self.NOI, self.VALUE, M.terms("HUD_223F", UST, 0))
        self.assertEqual(s["binds"], "LTV")
        self.assertAlmostEqual(s["loan"], 0.80 * self.VALUE, places=2)

    def test_fannie_binds_dscr(self):
        s = M.size_loan(self.NOI, self.VALUE, M.terms("FNMA_SML_30", UST, 0))
        self.assertEqual(s["binds"], "DSCR")
        self.assertLess(s["loan"], s["ltv_loan"])

    def test_mip_in_dscr_constant_flips_binding(self):
        # At this value, 80% LTV (7.2877M) sits between the DSCR loan without MIP (7.4106M) and with MIP (7.1648M):
        # dropping MIP from the constant would wrongly report LTV binding.
        s = M.size_loan(self.NOI, 9_109_624.95, M.terms("HUD_223F", UST, 0))
        self.assertEqual(s["binds"], "DSCR")
        self.assertAlmostEqual(s["loan"], 7_164_802.695, delta=1.0)

    def test_rate_override_wins(self):
        self.assertEqual(M.terms("HUD_223F", UST, 1, rate=0.0612)["rate"], 0.0612)
        self.assertAlmostEqual(M.terms("HUD_223F", UST, 1)["rate"], UST + 0.0155, places=12)

    def test_doctrine_preset_reads_governors(self):
        p = M.PRESETS["DOCTRINE_REFI"]
        self.assertEqual((p["max_ltv_cashout"], p["max_ltv_purchase"], p["min_dscr"], p["spread"], p["amort"],
                          p["upfront_pct"], p["mip"], p["fixed"]),
                         (D.PER_PROPERTY_LTV_CEILING, D.PER_PROPERTY_LTV_CEILING, D.DSCR_FLOOR, D.REFI_SPREAD,
                          D.REFI_AMORT_YEARS, D.REFI_FINANCING_COST, 0.0, 0))
        self.assertEqual(p["prepay"], [0.0] * 10)

    def test_program_terms_pinned(self):
        # Ratified 2026-11-20 proposal terms. A change here is a terms change: update the CHANGELOG, not just this test.
        h, f = M.PRESETS["HUD_223F"], M.PRESETS["FNMA_SML_30"]
        self.assertEqual((h["amort"], h["spread"], h["mip"], h["fixed"], h["max_ltv_purchase"], h["max_ltv_cashout"],
                          h["min_dscr"]), (35, 0.0155, 0.0025, 25_000, 0.85, 0.80, 1.15))
        self.assertAlmostEqual(h["upfront_pct"], 0.0155, places=12)
        self.assertEqual(h["prepay"], [0.10, 0.09, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01])
        self.assertEqual((f["amort"], f["spread"], f["mip"], f["upfront_pct"], f["fixed"], f["max_ltv_purchase"],
                          f["max_ltv_cashout"], f["min_dscr"]), (30, 0.0210, 0.0, 0.0100, 20_000, 0.80, 0.80, 1.25))
        self.assertEqual(f["prepay"], [0.05, 0.04, 0.03, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01])

    def test_tie_reports_ltv(self):
        t = M.terms("FNMA_SML_30", UST, 0, max_ltv_cashout=1.0)
        value = self.NOI / (t["min_dscr"] * M.constant(t["rate"], t["amort"], t["mip"]))
        self.assertEqual(M.size_loan(self.NOI, value, t)["binds"], "LTV")

    def test_purchase_vs_cashout_ltv(self):
        t = M.terms("HUD_223F", UST, 0)
        self.assertAlmostEqual(M.size_loan(1e9, 1e6, t, cashout=False)["loan"], 850_000, places=4)
        self.assertAlmostEqual(M.size_loan(1e9, 1e6, t, cashout=True)["loan"], 800_000, places=4)


class TestLevered(unittest.TestCase):
    def setUp(self):
        self.noi = [600_000 * 1.03 ** i for i in range(10)]
        self.cfbu = [n - 20_000 for n in self.noi]
        self.allin, self.sale = 8_000_000, 9_500_000
        self.t = M.terms("HUD_223F", UST, 5_000_000)

    def test_levered_pinned_to_independent_build(self):
        # Flows rebuilt with numpy_financial (pmt/fv) outside this module: HUD, 5M, funded end of year 1, exit year 10.
        out = M.levered(self.noi, self.cfbu, self.allin, self.sale, self.t)
        self.assertAlmostEqual(out["cf"][2], 221_178.27880387625, places=2)
        self.assertAlmostEqual(out["irr"], 0.11292980808970943, places=9)
        self.assertAlmostEqual(out["em"], 1.6313433011268377, places=9)

    def test_irr_above_100pct_solves(self):
        self.assertAlmostEqual(M._irr([-1, 2.5]), 1.5, places=9)
        self.assertAlmostEqual(M._irr([-1_090_000, 2_239_047]), 1.0541715596330277, places=9)
        self.assertIsNone(M._irr([1, 2]))

    def test_irr_extremes_and_root_choice(self):
        self.assertAlmostEqual(M._irr([-100, 0.5]), -0.995, places=9)
        self.assertAlmostEqual(M._irr([-1, 6]), 5.0, places=9)
        # Two roots (~10.0% and ~29.9%): the one closest to zero, as numpy_financial.irr picks.
        self.assertAlmostEqual(M._irr([0.757576, -1.742424, 1]), 0.10000739262220981, places=9)
        # Roots at -50% and +10%: NPV = c0 + c1 v + v^2 with v = 1/(1+r) has roots v = 2 and v = 1/1.1, so
        # c0 = 2/1.1 and c1 = -(2 + 1/1.1). The scan finds both; the closest to zero (+10%) wins, not the first (-50%).
        flows = [2 / 1.1, -(2 + 1 / 1.1), 1.0]
        self.assertAlmostEqual(M._irr(flows), 0.1, places=9)
        # Grid edges: just inside both ends.
        self.assertAlmostEqual(M._irr([-1e5, 1]), -0.99999, places=9)
        self.assertAlmostEqual(M._irr([-1, 10_000]), 9_999.0, places=6)

    def test_non_conventional_flagged(self):
        noi = [300_000] * 10
        t = M.terms("FNMA_SML_30", UST, 9_000_000)
        out = M.levered(noi, noi, self.allin, self.sale, t, fund_year=0)
        self.assertEqual(out["irr_flag"], "NON-CONVENTIONAL")
        self.assertAlmostEqual(out["irr"], -0.2232594557185854, places=6)
        self.assertEqual(M.levered(self.noi, self.cfbu, self.allin, self.sale, self.t)["irr_flag"], "")

    def test_zero_loan_dscr_is_infinite(self):
        out = M.levered(self.noi, self.cfbu, self.allin, self.sale, dict(self.t, loan=0.0, fixed=0))
        self.assertTrue(all(d == float("inf") for d in out["dscr"]))

    def test_exit_year_zero_raises(self):
        with self.assertRaises(ValueError):
            M.levered(self.noi, self.cfbu, self.allin, self.sale, self.t, fund_year=0, exit_year=0)

    def test_exit_beyond_model_years_raises(self):
        with self.assertRaises(ValueError):
            M.levered(self.noi, self.cfbu, self.allin, self.sale, self.t, exit_year=11)

    def test_hold_past_amortization_raises_at_term_plus_one_only(self):
        t = M.terms("DOCTRINE_REFI", UST, 4_000_000)
        cf = [500_000] * 27
        M.levered(cf, cf, 8e6, 9e6, t, fund_year=1, exit_year=26)          # 25 loan years = term: allowed
        with self.assertRaises(ValueError):
            M.levered(cf, cf, 8e6, 9e6, t, fund_year=1, exit_year=27)      # 26 loan years: paid off before exit

    def test_cash_out_beyond_basis(self):
        t = M.terms("FNMA_SML_30", UST, 9_000_000)
        out = M.levered(self.noi, self.cfbu, self.allin, self.sale, t, fund_year=0)
        self.assertGreater(out["cf"][0], 0)
        self.assertIsNone(out["em"])

    def test_irr_is_root_of_flows(self):
        out = M.levered(self.noi, self.cfbu, self.allin, self.sale, self.t)
        self.assertAlmostEqual(M._npv(out["irr"], out["cf"]), 0.0, delta=1e-4)

    def test_unlevered_identity_with_zero_loan(self):
        t0 = dict(self.t, loan=0.0, fixed=0)
        out = M.levered(self.noi, self.cfbu, self.allin, self.sale, t0)
        self.assertEqual(out["cf"][0], -self.allin)
        self.assertAlmostEqual(out["cf"][10], self.cfbu[9] + self.sale, places=6)

    def test_fund_year_one_cash_flows(self):
        t = self.t
        out = M.levered(self.noi, self.cfbu, self.allin, self.sale, t, fund_year=1)
        self.assertEqual(out["cf"][0], -self.allin)
        self.assertAlmostEqual(out["cf"][1], self.cfbu[0] + 5e6 * (1 - t["upfront_pct"]) - t["fixed"], places=6)
        d2 = M.loan_year(5e6, t["rate"], 35, 0.0025, 1)
        self.assertAlmostEqual(out["cf"][2], self.cfbu[1] - d2["ds"], places=6)
        self.assertEqual(len(out["dscr"]), 9)
        # exit at year 10 = loan year 9: 2% prepay on the outstanding balance
        bal = M.balance(5e6, t["rate"], 35, 9)
        d10 = M.loan_year(5e6, t["rate"], 35, 0.0025, 9)
        self.assertAlmostEqual(out["cf"][10], self.cfbu[9] - d10["ds"] + self.sale - bal * 1.02, places=6)

    def test_fund_at_close(self):
        out = M.levered(self.noi, self.cfbu, self.allin, self.sale, self.t, fund_year=0)
        self.assertAlmostEqual(out["cf"][0], -self.allin + 5e6 * (1 - self.t["upfront_pct"]) - 25_000, places=6)
        self.assertEqual(len(out["dscr"]), 10)

    def test_tax_hook_receives_deduction(self):
        seen = {}
        M.levered(self.noi, self.cfbu, self.allin, self.sale, self.t,
                  tax_fn=lambda y, ded: seen.setdefault(y, ded) * 0)
        self.assertEqual(seen[1], 0.0)
        d = M.loan_year(5e6, self.t["rate"], 35, 0.0025, 1)
        self.assertAlmostEqual(seen[2], d["interest"] + d["mip"], places=6)

    def test_bad_years_raise(self):
        with self.assertRaises(ValueError):
            M.levered(self.noi, self.cfbu, self.allin, self.sale, self.t, fund_year=10)


class TestLiveWalk(unittest.TestCase):
    CFBU = [420_000 * 1.025 ** i for i in range(10)]
    SALE = 7_400_000

    def _bisect(self, floor, **kw):
        lo, hi = 1.0, 50_000_000.0
        for _ in range(200):
            mid = (lo + hi) / 2
            flows, _ = M._after_tax_unlevered(mid, self.CFBU, self.SALE, kw.get("t", 0.0), kw.get("exemption", 0.0),
                                              kw.get("land_share", 0.0))
            lo, hi = (mid, hi) if M._npv(floor, flows) > 0 else (lo, mid)
        return (lo + hi) / 2

    def test_before_tax_matches_bisection(self):
        w = M.live_walk_allin(self.CFBU, self.SALE, 0.105)
        self.assertEqual(w["status"], "SOLVED")
        self.assertAlmostEqual(w["allin"], self._bisect(0.105), delta=1.0)

    def test_after_tax_matches_bisection(self):
        kw = dict(t=0.0975, exemption=5_000, land_share=0.25)
        w = M.live_walk_allin(self.CFBU, self.SALE, 0.105, **kw)
        self.assertEqual(w["status"], "SOLVED")
        self.assertAlmostEqual(w["allin"], self._bisect(0.105, **kw), delta=1.0)
        self.assertAlmostEqual(w["irr"], 0.105, places=6)

    def test_tax_lower_walk_than_pretax(self):
        self.assertLess(M.live_walk_allin(self.CFBU, self.SALE, 0.105, t=0.0975, land_share=0.25)["allin"],
                        M.live_walk_allin(self.CFBU, self.SALE, 0.105)["allin"])

    def test_hold_past_depreciation_life_flags_check(self):
        cf = [420_000 * 1.025 ** i for i in range(35)]
        self.assertEqual(M.live_walk_allin(cf, self.SALE, 0.105, t=0.0975)["status"], "CHECK")

    def test_hold_past_depreciation_life_with_land_flags_check(self):
        # 25% land: cumulative depreciation n*k stays below all-in until year 36.7, but improvements are fully written
        # off at 27.5 years, so the uncapped closed form overstates the walk for n = 28..36.
        for n in (28, 30, 35):
            cf = [420_000 * 1.025 ** i for i in range(n)]
            self.assertEqual(M.live_walk_allin(cf, self.SALE, 0.105, t=0.0975, land_share=0.25)["status"], "CHECK", n)
        cf = [420_000 * 1.025 ** i for i in range(27)]
        self.assertEqual(M.live_walk_allin(cf, self.SALE, 0.105, t=0.0975, land_share=0.25)["status"], "SOLVED")

    def test_marginal_zero_tax_year_flags_check_even_when_irr_ties(self):
        # Exemption chosen so year-1 taxable income is -USD 1 at the solved walk: the closed form is off by cents, the
        # IRR still ties to 1e-6, and only the MAX()-binding flag reports CHECK.
        t, land = 0.0975, 0.25
        k = (1 - land) / 27.5
        x = 0.0
        for _ in range(60):
            a = M.live_walk_allin(self.CFBU, self.SALE, 0.105, t=t, exemption=x, land_share=land)["allin"]
            x = self.CFBU[0] - k * a + 1.0
        w = M.live_walk_allin(self.CFBU, self.SALE, 0.105, t=t, exemption=x, land_share=land)
        self.assertAlmostEqual(w["irr"], 0.105, places=6)
        self.assertEqual(w["status"], "CHECK")

    def test_marginal_negative_sale_gain_flags_check(self):
        # Net sale chosen so the sale gain is -USD 1 at the solved walk: only the gain<=0 flag reports CHECK.
        t, land = 0.0975, 0.25
        k = (1 - land) / 27.5
        sale = self.SALE
        for _ in range(200):
            a = M.live_walk_allin(self.CFBU, sale, 0.105, t=t, land_share=land)["allin"]
            sale = a * (1 - 10 * k) - 1.0
        w = M.live_walk_allin(self.CFBU, sale, 0.105, t=t, land_share=land)
        self.assertAlmostEqual(w["irr"], 0.105, places=6)
        self.assertEqual(w["status"], "CHECK")

    def test_tolerance_backstop(self):
        real = M._irr
        try:
            M._irr = lambda flows: 0.105 + 2e-6
            self.assertEqual(M.live_walk_allin(self.CFBU, self.SALE, 0.105)["status"], "CHECK")
            M._irr = lambda flows: 0.105 + 5e-7
            self.assertEqual(M.live_walk_allin(self.CFBU, self.SALE, 0.105)["status"], "SOLVED")
        finally:
            M._irr = real

    def test_untaxed_walk_ignores_tax_flags(self):
        cf = [5_000] + self.CFBU[1:]      # a zero-tax year only matters when t > 0
        self.assertEqual(M.live_walk_allin(cf, self.SALE, 0.105)["status"], "SOLVED")

    def test_negative_allin_is_check(self):
        w = M.live_walk_allin([-50_000] * 10, 1_000.0, 0.105)
        self.assertLess(w["allin"], 0)
        self.assertEqual(w["status"], "CHECK")

    def test_zero_tax_year_flags_check(self):
        cf = [5_000] + self.CFBU[1:]   # year-1 taxable income negative: MAX() binds, closed form inexact
        self.assertEqual(M.live_walk_allin(cf, self.SALE, 0.105, t=0.0975, land_share=0.25)["status"], "CHECK")


def _ref_balance(loan, rate_m, n, m):
    """Textbook remaining balance after m payments (independent of ora_mf_debt)."""
    g = (1 + rate_m) ** m
    pay = loan * rate_m / (1 - (1 + rate_m) ** -n)
    return loan * g - pay * (g - 1) / rate_m


def _evaluate(ws, external):
    """Tiny evaluator for the formulas write_loan_block emits (cell refs, ranges, arithmetic, a few functions)."""
    import re
    from openpyxl.utils import column_index_from_string as ci, get_column_letter as gl
    cache = {}

    def val(sheet, a):
        a = a.replace("$", "")
        if sheet != "_":
            return external[f"{sheet}!{a}"]
        if a not in cache:
            v = ws[a].value
            cache[a] = ev(v[1:]) if isinstance(v, str) and v.startswith("=") else (v or 0)
        return cache[a]

    def rng(a, b):
        m1, m2 = re.match(r"([A-Z]+)(\d+)", a.replace("$", "")), re.match(r"([A-Z]+)(\d+)", b.replace("$", ""))
        return [val("_", f"{gl(c)}{m1[2]}") for c in range(ci(m1[1]), ci(m2[1]) + 1)]

    def CUMPRINC(r, n, pv, s, e, _t):
        return -(_ref_balance(pv, r, n, s - 1) - _ref_balance(pv, r, n, e))

    def CUMIPMT(r, n, pv, s, e, _t):
        pay = pv * r / (1 - (1 + r) ** -n)
        return -(pay * (e - s + 1) - (_ref_balance(pv, r, n, s - 1) - _ref_balance(pv, r, n, e)))

    def IF(c, a, b):
        return a if c else b

    fns = dict(CUMPRINC=CUMPRINC, CUMIPMT=CUMIPMT, IRR=M._irr, SUM=sum, MIN=min, NA=lambda: None, IF=IF,
               MAX=lambda *a: max(a))

    def ev(f):
        f = re.sub(r"(\$?[A-Z]+\$?\d+):(\$?[A-Z]+\$?\d+)", lambda m: f'rng("{m[1]}","{m[2]}")', f)
        f = re.sub(r'(?<![\w"])(?:([A-Za-z]+)!)?(\$?[A-Z]{1,2}\$?\d+)(?![\w"(])',
                   lambda m: f'val("{m[1] or "_"}","{m[2]}")', f)
        return eval(f, {"__builtins__": {}}, dict(fns, val=val, rng=rng))

    return val


class TestWriterValues(unittest.TestCase):
    """The written workbook block must compute the same numbers as levered() and the independent pin."""
    NOI = [600_000 * 1.03 ** i for i in range(10)]
    CF = [n - 20_000 for n in NOI]

    def _run(self, preset, loan, fund_year, exit_year, taxed=False):
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter as gl
        ws = Workbook().active
        ext = {"Inputs!B2": 8e6, "Sale!B1": 9.5e6, "Inputs!B3": 1e7, "Inputs!B4": self.NOI[1]}
        for y in range(1, 11):
            ext[f"NOI!A{y}"] = self.NOI[y - 1]
            ext[f"CF!A{y}"] = self.CF[y - 1]
        t = M.terms(preset, UST, loan)
        tax = (lambda y, ded: f"MAX(0,0.0975*(CF!A{y}-({ded})))") if taxed else None
        _, res = M.write_loan_block(ws, 1, t, years=10, noi_ref=lambda y: f"NOI!A{y}", cfbu_ref=lambda y: f"CF!A{y}",
                                    allin_ref="Inputs!$B$2", sale_expr="Sale!$B$1", exit_year=exit_year,
                                    fund_year=fund_year, tax_expr=tax, value_ref="Inputs!$B$3",
                                    stab_noi_ref="Inputs!$B$4")
        val = _evaluate(ws, ext)
        out = {k: val("_", v.split("!")[1]) for k, v in res.items() if isinstance(v, str)}
        row = res["rows"]["Levered CF"]
        cfs = [val("_", f"{gl(c)}{row}") for c in range(2, exit_year + 3)]
        tf = (lambda y, ded: max(0.0, 0.0975 * (self.CF[y - 1] - ded))) if taxed else None
        eng = M.levered(self.NOI, self.CF, 8e6, 9.5e6, t, fund_year=fund_year, exit_year=exit_year, tax_fn=tf)
        return out, cfs, eng, t

    def test_hud_matches_independent_pin(self):
        out, cfs, _, _ = self._run("HUD_223F", 5e6, 1, 10)
        self.assertAlmostEqual(cfs[2], 221_178.27880387625, places=2)
        self.assertAlmostEqual(out["Levered IRR"], 0.11292980808970943, places=9)
        self.assertAlmostEqual(out["Equity multiple"], 1.6313433011268377, places=9)

    def test_block_ties_to_engine_across_layouts(self):
        for preset in ("HUD_223F", "FNMA_SML_30", "DOCTRINE_REFI"):
            for fy, ex in ((0, 10), (1, 7), (2, 10), (1, 2)):
                for taxed in (False, True):
                    with self.subTest(preset=preset, fund_year=fy, exit_year=ex, taxed=taxed):
                        out, cfs, eng, t = self._run(preset, 5e6, fy, ex, taxed)
                        self.assertEqual(len(cfs), len(eng["cf"]))
                        for a, b in zip(cfs, eng["cf"]):
                            self.assertAlmostEqual(a, b, places=4)
                        self.assertAlmostEqual(out["Levered IRR"], eng["irr"], places=9)
                        self.assertAlmostEqual(out["Equity multiple"], eng["em"], places=9)
                        self.assertAlmostEqual(out["Balance at exit"],
                                               M.balance(5e6, t["rate"], t["amort"], ex - fy), places=3)
                        self.assertAlmostEqual(out["Minimum DSCR to exit"], min(eng["dscr"]), places=9)
                        net = 5e6 * (1 - t["upfront_pct"]) - t["fixed"]
                        coc = out["First full-year cash-on-cash on remaining equity"]
                        if ex == fy + 1:
                            self.assertIsNone(coc)
                        else:
                            self.assertAlmostEqual(coc, eng["cf"][fy + 1] / (8e6 - net), places=9)
                        self.assertAlmostEqual(out["Equity left in after funding"], 8e6 - net, places=4)
                        self.assertAlmostEqual(out["Net loan proceeds (after fees)"], net, places=4)
                        self.assertAlmostEqual(out["LTV at stabilized value"], 5e6 / 1e7, places=12)
                        first = M.loan_year(5e6, t["rate"], t["amort"], t["mip"], 1)
                        self.assertAlmostEqual(out["Max loan at program DSCR on stabilized NOI"],
                                               self.NOI[1] / t["min_dscr"] / first["ds"] * 5e6, places=3)
                        self.assertAlmostEqual(out["Loan constant incl. MIP (first full year)"], first["ds"] / 5e6,
                                               places=9)

    def test_long_hold_past_prepay_schedule_ties(self):
        # HUD funded year 1, exit year 20 = loan year 19: past the 10-yr prepay schedule (premium 0 in both engine and
        # workbook); also a 35-yr tab with the exit at 20, so post-exit columns stay inside the 35-yr term.
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter as gl
        n = 35
        noi = [600_000 * 1.03 ** i for i in range(n)]
        cf = [x - 20_000 for x in noi]
        ws = Workbook().active
        ext = {"Inputs!B2": 8e6, "Sale!B1": 1.4e7}
        for y in range(1, n + 1):
            ext[f"NOI!A{y}"] = noi[y - 1]
            ext[f"CF!A{y}"] = cf[y - 1]
        t = M.terms("HUD_223F", UST, 5e6)
        _, res = M.write_loan_block(ws, 1, t, years=n, noi_ref=lambda y: f"NOI!A{y}", cfbu_ref=lambda y: f"CF!A{y}",
                                    allin_ref="Inputs!$B$2", sale_expr="Sale!$B$1", exit_year=20, fund_year=1)
        val = _evaluate(ws, ext)
        row = res["rows"]["Levered CF"]
        cfs = [val("_", f"{gl(c)}{row}") for c in range(2, 20 + 3)]
        eng = M.levered(noi, cf, 8e6, 1.4e7, t, fund_year=1, exit_year=20)
        for a, b in zip(cfs, eng["cf"]):
            self.assertAlmostEqual(a, b, places=4)
        self.assertEqual(val("_", res["inputs"]["prepay_exit"].split("!")[1]), 0.0)
        self.assertAlmostEqual(eng["cf"][20], cf[19] - M.loan_year(5e6, t["rate"], 35, 0.0025, 19)["ds"] + 1.4e7
                               - M.balance(5e6, t["rate"], 35, 19), places=4)

    def test_unbracketed_caller_tax_formula_still_deducts_mip(self):
        # A caller writing `cf-{ded}` without brackets must still subtract interest AND MIP.
        from openpyxl import Workbook
        from openpyxl.utils import get_column_letter as gl
        ws = Workbook().active
        ext = {"Inputs!B2": 8e6, "Sale!B1": 9.5e6}
        for y in range(1, 11):
            ext[f"NOI!A{y}"] = self.NOI[y - 1]
            ext[f"CF!A{y}"] = self.CF[y - 1]
        t = M.terms("HUD_223F", UST, 5e6)
        _, res = M.write_loan_block(ws, 1, t, years=10, noi_ref=lambda y: f"NOI!A{y}", cfbu_ref=lambda y: f"CF!A{y}",
                                    allin_ref="Inputs!$B$2", sale_expr="Sale!$B$1", exit_year=10, fund_year=1,
                                    tax_expr=lambda y, ded: f"MAX(0,0.0975*(CF!A{y}-{ded}))")
        val = _evaluate(ws, ext)
        row = res["rows"]["Levered CF"]
        cfs = [val("_", f"{gl(c)}{row}") for c in range(2, 13)]
        eng = M.levered(self.NOI, self.CF, 8e6, 9.5e6, t,
                        tax_fn=lambda y, d: max(0.0, 0.0975 * (self.CF[y - 1] - d)))
        for a, b in zip(cfs, eng["cf"]):
            self.assertAlmostEqual(a, b, places=4)

    def test_doctrine_label_built_from_doctrine(self):
        lab = M.PRESETS["DOCTRINE_REFI"]["label"]
        self.assertIn(f"{round(D.REFI_SPREAD * 1e4)} bp", lab)
        self.assertIn(f"{D.REFI_AMORT_YEARS}-yr amortization", lab)

    def test_cash_out_beyond_basis_multiple_is_na(self):
        out, _, eng, _ = self._run("FNMA_SML_30", 9e6, 0, 10)
        self.assertIsNone(out["Equity multiple"])
        self.assertIsNone(eng["em"])


class TestWriter(unittest.TestCase):
    def _block(self, fund_year):
        from openpyxl import Workbook
        ws = Workbook().active
        ws.title = "Financing Scenarios"
        t = M.terms("HUD_223F", UST, 5_000_000)
        nr, res = M.write_loan_block(ws, 1, t, years=10, noi_ref=lambda y: f"NOI!A{y}", cfbu_ref=lambda y: f"CF!A{y}",
                                     allin_ref="Inputs!$B$2", sale_expr="Sale!$B$1", exit_year=10,
                                     fund_year=fund_year, value_ref="Inputs!$B$3", stab_noi_ref="Inputs!$B$4")
        return ws, nr, res

    def test_fund_year_one_layout(self):
        ws, nr, res = self._block(1)
        rr = res["rows"]
        self.assertEqual(ws[f"B{rr['Levered CF']}"].value, "=-Inputs!$B$2")
        self.assertIsNone(ws[f"C{rr['Debt service']}"].value)          # no debt service in the funding year
        self.assertIn("CUMPRINC", ws[f"D{rr['Principal']}"].value)
        self.assertIn("Sale!$B$1", ws[f"L{rr['Levered CF']}"].value)  # year 10 = column L
        self.assertIn("Levered IRR", res)
        self.assertGreater(nr, rr["Levered CF"])

    def test_fund_at_close_puts_proceeds_in_year_zero(self):
        ws, _, res = self._block(0)
        rr = res["rows"]
        self.assertIn("(1-", ws[f"B{rr['Levered CF']}"].value)
        self.assertIn("CUMPRINC", ws[f"C{rr['Principal']}"].value)
        self.assertNotIn("(1-", ws[f"C{rr['Levered CF']}"].value)

    def test_eligibility_note_written(self):
        ws, nr, _ = self._block(1)
        notes = [ws.cell(r, 1).value for r in range(1, nr) if str(ws.cell(r, 1).value or "").startswith("Eligibility:")]
        self.assertEqual(len(notes), 1)
        self.assertIn("Rate source:", notes[0])

    def test_writer_amortization_guard_boundary(self):
        from openpyxl import Workbook
        t = M.terms("DOCTRINE_REFI", UST, 4_000_000)
        kw = dict(noi_ref=lambda y: f"A{y}", cfbu_ref=lambda y: f"A{y}", allin_ref="B1", sale_expr="0")
        M.write_loan_block(Workbook().active, 1, t, years=30, exit_year=26, fund_year=1, **kw)   # 25 = term: ok
        with self.assertRaises(ValueError):
            M.write_loan_block(Workbook().active, 1, t, years=30, exit_year=27, fund_year=1, **kw)

    def test_writer_blank_schedule_past_term_and_exit(self):
        from openpyxl import Workbook
        ws = Workbook().active
        t = M.terms("DOCTRINE_REFI", UST, 4_000_000)
        _, res = M.write_loan_block(ws, 1, t, years=35, exit_year=10, fund_year=1, noi_ref=lambda y: f"A{y}",
                                    cfbu_ref=lambda y: f"A{y}", allin_ref="B1", sale_expr="0")
        from openpyxl.utils import get_column_letter as gl
        self.assertIsNotNone(ws[f"{gl(26 + 2)}{res['rows']['Principal']}"].value)   # loan year 25: written
        self.assertIsNone(ws[f"{gl(27 + 2)}{res['rows']['Principal']}"].value)      # loan year 26: blank

    def test_writer_rejects_zero_loan_or_rate(self):
        from openpyxl import Workbook
        kw = dict(years=10, noi_ref=str, cfbu_ref=str, allin_ref="A1", sale_expr="0", exit_year=10, fund_year=1)
        with self.assertRaises(ValueError):
            M.write_loan_block(Workbook().active, 1, M.terms("HUD_223F", UST, 0), **kw)
        with self.assertRaises(ValueError):
            M.write_loan_block(Workbook().active, 1, M.terms("HUD_223F", UST, 1e6, rate=0.0), **kw)

    def test_writer_rejects_exit_beyond_years(self):
        from openpyxl import Workbook
        with self.assertRaises(ValueError):
            M.write_loan_block(Workbook().active, 1, M.terms("HUD_223F", UST, 1e6), years=10, noi_ref=str,
                               cfbu_ref=str, allin_ref="A1", sale_expr="0", exit_year=11, fund_year=1)

    def test_writer_rejects_exit_before_funding(self):
        with self.assertRaises(ValueError):
            from openpyxl import Workbook
            M.write_loan_block(Workbook().active, 1, M.terms("HUD_223F", UST, 1), years=10, noi_ref=str, cfbu_ref=str,
                               allin_ref="A1", sale_expr="0", exit_year=1, fund_year=1)


if __name__ == "__main__":
    unittest.main()
