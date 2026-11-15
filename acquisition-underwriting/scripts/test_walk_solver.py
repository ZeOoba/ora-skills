"""Hand-checkable tests for the walk-price solver. Run: python acquisition-underwriting/scripts/test_walk_solver.py"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ora_walk import doctrine as D  # noqa: E402
from ora_walk import rct_table  # noqa: E402
from ora_walk.solver import (  # noqa: E402
    Deal, annual_debt_constant, credited_land, irr, irr_floor, loan_balance, max_allin_basis, noi_path, npv, solve,
    solve_portfolio, vintage_floor,
)

UST = 0.045

# The real RCT table is private (rct_table.py). These tests run on INVENTED figures only; every expected
# value below is derived from the fixture, never from a real figure.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "rct-table.synthetic.json"),
          encoding="utf-8") as _fh:
    SYN = json.load(_fh)
P = rct_table.points(rct_table.validate(SYN, allow_synthetic=True))
P_COL, P_CHI, P_IND = P["Columbus OH"], P["Chicago-Cook IL"], P["Indianapolis IN"]


def setUpModule():
    rct_table.use(SYN)


def tearDownModule():
    rct_table.use(None)


def base(**kw):
    d = dict(name="T", sf=30_000, stabilized_noi=300_000, market="Columbus OH",
             year_built=1985, construction_type="tilt-up", reserves_psf=0.0)
    d.update(kw)
    return Deal(**d)


class DoctrinePins(unittest.TestCase):
    """Literal values from SKILL.md v4.53 (v4.53 adds the land-credit cap and the IRR add-ons; governor constants unchanged since v4.45) — any drift fails (Hard Invariant 4 for governors)."""
    def test_governors(self):
        self.assertEqual((D.DSCR_FLOOR, D.PER_PROPERTY_LTV_CEILING, D.AGGREGATE_LTV_CEILING), (1.25, 0.65, 0.40))
        self.assertEqual((D.YOC_FLOOR, D.IRR_FLOOR_MIN, D.IRR_FLOOR_UST_SPREAD, D.MAJORITY_VACANT_PREMIUM),
                         (0.08, 0.10, 0.055, 0.01))
        self.assertEqual((D.REFI_SPREAD, D.REFI_AMORT_YEARS, D.REFI_FINANCING_COST, D.CLOSING_COST),
                         (0.02, 25, 0.01, 0.02))
        self.assertEqual((D.RESERVES_PSF, D.EXPENSE_GROWTH, D.MARKET_RENT_GROWTH), (0.15, 0.03, 0.025))
        self.assertEqual(D.LEASE_UP_TI_PSF, 8.00)  # Lease-Up Assumption Block TI default
        self.assertEqual(D.STRUCTURAL_VACANCY, 0.05)  # Suite-Level Block vacancy-line floor

    def test_rollover_block(self):  # SKILL.md Suite-Level Rollover & Credit Block (a)/(b); Lease-Up Block free rent
        inf = float("inf")
        self.assertEqual(D.RENEWAL_PROB_BY_SF, ((5_000, 0.65), (10_000, 0.70), (25_000, 0.72), (inf, 0.75)))
        self.assertEqual(D.ROLLOVER_DOWNTIME_BY_SF, ((10_000, 5), (25_000, 9), (inf, 12)))
        self.assertEqual(D.LEASE_UP_FREE_MONTHS, 2)

    def test_v453_land_and_irr_addons(self):  # SKILL.md v4.53 STAGE 1 Basis + IRR floors (RE-4.53-1, RE-4.53-2)
        self.assertEqual((D.LAND_CREDIT_CAP, D.LAND_COMP_MIN), (0.60, 3))
        self.assertEqual((D.SINGLE_TENANT_PREMIUM, D.TERTIARY_MARKET_PREMIUM, D.ENVIRONMENTAL_PREMIUM,
                          D.NEW_COMPETENCY_PREMIUM), (0.01, 0.005, 0.005, 0.01))
        self.assertEqual(D.TERTIARY_MARKETS, {"Grand Rapids MI", "Richmond VA", "Des Moines IA"})

    def test_exit_caps(self):  # SKILL.md UNDERWRITING CONVENTIONS exit cap
        self.assertEqual(D.EXIT_CAPS, {
            "Columbus OH": 0.075, "Cincinnati OH": 0.075, "Indianapolis IN": 0.075,
            "Kansas City MO": 0.0775, "Madison WI": 0.0725, "Mid-Atlantic": 0.0725,
            "Grand Rapids MI": 0.08, "Richmond VA": 0.0775, "Des Moines IA": 0.0775,
            "Louisville KY": 0.0775, "Chicago-Cook IL": 0.08})
        self.assertEqual(D.DEFAULT_EXIT_CAP, 0.0775)

    def test_rct_markets(self):  # SKILL.md RCT v03 market rows (names only; the figures are private)
        self.assertEqual(D.RCT_MARKETS, (
            "Columbus OH", "Cincinnati OH", "Kansas City MO", "Indianapolis IN", "Madison WI", "Mid-Atlantic",
            "Grand Rapids MI", "Richmond VA", "Des Moines IA", "Louisville KY", "Chicago-Cook IL"))
        self.assertEqual(D.RCT_VERSION, "RCT v03")
        self.assertFalse(hasattr(D, "RCT_POINT"), "RCT figures must not be back in source")

    def test_construction(self):  # SKILL.md Construction-Type Multiplier Schedule
        self.assertEqual(D.CONSTRUCTION_MULT, {"tilt-up": 1.00, "precast": 1.00, "cmu": 0.97, "brick": 1.10, "hybrid": 0.93})
        self.assertEqual(D.PEMB_TILT, ((20_000, 0.88), (40_000, 0.90), (float("inf"), 0.92)))
        self.assertEqual(D.UNKNOWN_MULT_CAP, 0.90)

    def test_denominator_sensitive(self):  # SKILL.md RCT v03 standing-flag markets
        self.assertEqual(D.DENOMINATOR_SENSITIVE, {"Madison WI", "Grand Rapids MI", "Richmond VA",
                                                    "Des Moines IA", "Chicago-Cook IL", "Indianapolis IN"})


class Primitives(unittest.TestCase):
    def test_vintage_ramp(self):
        for y, f in ((1980, 0.65), (1995, 0.65), (2000, 0.625), (2005, 0.60), (2020, 0.60), (None, 0.65)):
            self.assertAlmostEqual(vintage_floor(y), f)

    def test_irr_floor(self):
        self.assertAlmostEqual(irr_floor(0.04, False), 0.10)
        self.assertAlmostEqual(irr_floor(0.05, False), 0.105)
        self.assertAlmostEqual(irr_floor(0.05, True), 0.115)

    def test_debt_constant_and_balance(self):
        self.assertAlmostEqual(annual_debt_constant(0.072), 0.0864, places=3)  # doctrine ~8.6%
        self.assertAlmostEqual(loan_balance(1_000_000, 0.072, 0), 1_000_000, places=2)
        self.assertAlmostEqual(loan_balance(1_000_000, 0.072, 25), 0, places=2)

    def test_irr_roundtrip(self):
        self.assertAlmostEqual(irr([-100, 10, 10, 110]), 0.10, places=8)
        self.assertAlmostEqual(npv(0.10, [-100, 10, 10, 110]), 0, places=8)


class Legs(unittest.TestCase):
    def test_yield_leg_hand_number(self):
        self.assertAlmostEqual(solve(base(), UST).legs["yield"], 3_676_470.588, places=2)  # 300000/.08/1.02

    def test_basis_leg_hand_number(self):
        # synthetic Columbus POINT 240: 0.35 x 0.9 x 240 x 30000 / 1.02 = 2,223,529.41
        self.assertEqual(P_COL, 240.0)
        self.assertAlmostEqual(solve(base(), UST).legs["basis"], 2_223_529.41, places=1)

    def test_default_reserves_applied(self):
        d = Deal(name="T", sf=30_000, stabilized_noi=300_000, market="Columbus OH", year_built=1985,
                 construction_type="tilt-up")
        self.assertAlmostEqual(solve(d, UST).legs["yield"], (300_000 - 4_500) / 0.08 / 1.02, places=4)

    def test_capex_and_carry_reduce_every_leg(self):
        a, b = solve(base(), UST), solve(base(capex=100_000, lease_up_carry=20_000), UST)
        for leg in ("basis", "yield", "irr"):
            self.assertAlmostEqual(a.legs[leg] - b.legs[leg], 120_000 / 1.02, places=4)

    def test_irr_leg_hits_floor_exactly_at_2_5_growth(self):
        d = base()
        r = solve(d, UST)
        self.assertEqual(r.floors["noi_growth"], 0.025)
        flows = [-(r.legs["irr"] * 1.02)] + [300_000 * 1.025 ** t for t in range(10)]
        flows[-1] += 300_000 * 1.025 ** 10 / 0.075
        self.assertAlmostEqual(irr(flows), r.floors["irr_floor"], places=7)

    def test_sale_cost_lowers_irr_leg_by_pv(self):
        a, b = solve(base(), UST), solve(base(sale_cost_pct=0.02), UST)
        rev = 300_000 * 1.025 ** 10 / 0.075
        self.assertAlmostEqual(a.legs["irr"] - b.legs["irr"], 0.02 * rev / 1.10 ** 10 / 1.02, places=2)

    def test_walk_is_min_leg(self):
        r = solve(base(), UST)
        self.assertEqual(r.walk_price, min(r.legs.values()))
        self.assertEqual(r.legs[r.binding_leg], r.walk_price)

    def test_lease_up_ramp(self):
        p = noi_path(base(in_place_noi=100_000, stabilization_year=3))
        self.assertEqual([round(x) for x in p[:4]], [100_000, 200_000, 300_000, 307_500])


class Construction(unittest.TestCase):
    def test_unknown_small_and_large(self):
        small = solve(base(construction_type=None, sf=15_000, stabilized_noi=150_000), UST)
        large = solve(base(construction_type=None, sf=45_000, stabilized_noi=450_000), UST)
        self.assertAlmostEqual(small.floors["construction_multiplier"], 0.88)
        self.assertAlmostEqual(large.floors["construction_multiplier"], 0.90)  # PEMB 0.92 capped at 0.90
        self.assertTrue(any("construction type" in f for f in small.flags))

    def test_known_pemb_tilt_and_types(self):
        self.assertAlmostEqual(solve(base(construction_type="pemb", sf=45_000, stabilized_noi=450_000), UST)
                               .floors["construction_multiplier"], 0.92)
        self.assertAlmostEqual(solve(base(construction_type="pemb", sf=20_000), UST).floors["construction_multiplier"], 0.90)
        self.assertAlmostEqual(solve(base(construction_type="brick"), UST).floors["construction_multiplier"], 1.10)

    def test_no_numeric_multiplier_override(self):
        with self.assertRaises(TypeError):  # field removed: type is the only way to set the multiplier
            Deal(name="x", sf=1, stabilized_noi=1, construction_multiplier=1.10)
        with self.assertRaises(ValueError):
            solve(base(construction_type="adobe"), UST)

    def test_adders_schedule(self):
        self.assertEqual(D.ADDERS, {"office_buildout": 15.0, "climate_control": 12.0, "cranes": 18.0,
                                    "esfr": 4.0, "site_work": 8.0, "paving_lighting": 8.0})
        r = solve(base(adders=["cranes", "esfr"]), UST)
        self.assertAlmostEqual(r.floors["rct_low_psf_adjusted"], 0.9 * (P_COL + 22))
        for bad in (["site_work", "paving_lighting"], ["cranes", "cranes"], ["gold_plating"]):
            with self.assertRaises(ValueError, msg=bad):
                solve(base(adders=bad), UST)


class Vintage(unittest.TestCase):
    def test_renovation_rule(self):
        point = P_COL  # tilt-up
        # R% = 15% -> halfway between 1970 and 2010 = 1990
        r = solve(base(year_built=1970, renovation_year=2010, renovation_spend=0.15 * point * 30_000), UST)
        self.assertEqual(r.floors["vintage_used"], 1990)
        r = solve(base(year_built=1970, renovation_year=2010, renovation_spend=0.04 * point * 30_000), UST)
        self.assertEqual(r.floors["vintage_used"], 1970)
        r = solve(base(year_built=1970, renovation_year=2010, renovation_spend=0.30 * point * 30_000), UST)
        self.assertEqual(r.floors["vintage_used"], 2010)

    def test_unknown_type_r_pct_at_1_00(self):
        # unknown type: R% denominator uses x1.00, so the shift is smaller than at 0.90
        spend = 0.15 * P_COL * 30_000
        r = solve(base(construction_type=None, year_built=1970, renovation_year=2010, renovation_spend=spend), UST)
        self.assertEqual(r.floors["vintage_used"], 1990)

    def test_effective_vintage_guards(self):
        with self.assertRaises(ValueError):
            solve(base(year_built=1970, effective_vintage=2050), UST)
        with self.assertRaises(ValueError):
            solve(base(year_built=1990, effective_vintage=1980), UST)
        # asserted vintage without documented spend is capped at year_built (can only tighten)
        r = solve(base(year_built=1970, effective_vintage=2000), UST)
        self.assertEqual(r.floors["vintage_used"], 1970)
        self.assertTrue(any("not supported" in f for f in r.flags))
        self.assertAlmostEqual(r.walk_price, solve(base(year_built=1970), UST).walk_price)
        # a tighter (earlier) asserted vintage is honoured
        r = solve(base(year_built=1990, renovation_year=2010, renovation_spend=0.30 * P_COL * 30_000,
                       effective_vintage=2000), UST)
        self.assertEqual(r.floors["vintage_used"], 2000)
        with self.assertRaises(ValueError):
            solve(base(year_built=1990, renovation_year=1950, renovation_spend=1), UST)

    def test_vintage_continuous_no_rounding(self):
        # R% = 16% on 1990 -> 2000: 1995.5 exactly; floor 0.6475, never rounded up to 1996 (0.645)
        r = solve(base(year_built=1990, renovation_year=2000, renovation_spend=0.16 * P_COL * 30_000), UST)
        self.assertAlmostEqual(r.floors["vintage_used"], 1995.5)
        self.assertAlmostEqual(r.floors["basis_floor_pct"], 0.6475)

    def test_unknown_market_r_pct_uses_largest_point(self):
        spend = 0.15 * P_IND * 30_000  # 15% of the largest POINT (Indianapolis)
        r = solve(base(market="Nowhere", year_built=1970, renovation_year=2010, renovation_spend=spend), UST)
        self.assertAlmostEqual(r.floors["vintage_used"], 1990)


class LooserThanDoctrineGuards(unittest.TestCase):
    def test_non_finite_inputs_rejected(self):
        nan, inf = float("nan"), float("inf")
        for f in ("sf", "stabilized_noi", "capex", "lease_up_carry", "market_land_value", "reserves_psf",
                  "sale_cost_pct", "noi_growth", "ask_price", "exit_cap"):
            for bad in (nan, inf):
                with self.assertRaises(ValueError, msg=(f, bad)):
                    solve(base(**{f: bad}), UST)
        with self.assertRaises(ValueError):
            solve(base(in_place_noi=nan, stabilization_year=2), UST)
        with self.assertRaises(ValueError):
            solve(base(vacant_sf_at_close=nan), UST)
        with self.assertRaises(ValueError):
            solve(base(), float("nan"))

    def test_denominator_sensitive_near_floor(self):
        # basis binds -> walk sits exactly on the floor at LOW -> always flagged
        r = solve(base(), UST)
        self.assertEqual(r.binding_leg, "basis")
        self.assertTrue(any(f.startswith("DENOMINATOR-SENSITIVE at walk") for f in r.flags))
        # an ask far above the floor (deep discount lost) is not "near" at LOW or POINT and does not flip
        far = solve(base(ask_price=500_000), UST)
        self.assertFalse(any(f.startswith("DENOMINATOR-SENSITIVE at ask") for f in far.flags))

    def test_denominator_sensitive_flip_between_low_and_point(self):
        # an ask priced so it clears the floor at POINT but not at LOW
        self.assertEqual(D.DENOM_SENSITIVE_BAND, 0.05)
        low_repl, point_repl = 0.9 * P_COL * 30_000, P_COL * 30_000
        price = (0.35 * (low_repl + point_repl) / 2) / 1.02   # between the two floors
        r = solve(base(stabilized_noi=150_000, ask_price=price), UST)
        self.assertTrue(any(f.startswith("DENOMINATOR-SENSITIVE at ask") for f in r.flags))

    def test_vacant_building_without_vacant_sf_allocated_by_method_2(self):
        p = solve_portfolio([base(name="A"), base(name="V", in_place_noi=0, stabilization_year=2)], UST)
        self.assertEqual(p["allocation_method"], "(2) replacement-cost-weighted GBA")

    def test_cli_renders_no_noi_deal(self):
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout
        from ora_walk.cli import main
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(dict(name="Z", sf=20_000, stabilized_noi=0, market="Columbus OH", year_built=1990,
                           construction_type="tilt-up", ask_price=1_000_000), fh)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main([fh.name, "--ust", "0.045"]), 0)
        os.unlink(fh.name)
        self.assertIn("DSCR @65% LTV —", buf.getvalue())

    def test_land_credit_gates(self):
        # v4.53: missing value -> DATA-GAP land; < 3 comps -> DATA-GAP land comps; no flood clearance -> Ruling 4.
        # Every one of them credits $0, so the basis leg equals the no-land leg.
        no_land = solve(base(), UST)
        self.assertTrue(any(f.startswith("[DATA-GAP: land]") for f in no_land.flags))
        for kw, tag in ((dict(market_land_value=500_000, land_comp_count=2, land_flood_cleared=True),
                         "[DATA-GAP: land comps]"),
                        (dict(market_land_value=500_000, land_comp_count=3), "Ruling 4"),
                        (dict(market_land_value=500_000, land_flood_cleared=True), "[DATA-GAP: land comps]")):
            r = solve(base(**kw), UST)
            self.assertTrue(any(f.startswith(tag) for f in r.flags), kw)
            self.assertAlmostEqual(r.legs["basis"], no_land.legs["basis"], msg=kw)
        ok = solve(base(market_land_value=500_000, land_comp_count=3, land_flood_cleared=True), UST)
        self.assertAlmostEqual(ok.legs["basis"] - no_land.legs["basis"], 500_000 / 1.02, places=4)
        # review C4: the reported credits tie to the legs
        self.assertAlmostEqual(ok.floors["land_credit_at_basis_leg"], 500_000)
        walk_allin = ok.walk_price * 1.02
        self.assertAlmostEqual(ok.floors["land_credit_at_walk"], min(500_000, 0.60 * walk_allin))
        self.assertFalse(any("DATA-GAP: land" in f or "Ruling 4" in f for f in ok.flags))
        with self.assertRaises(ValueError):
            solve(base(land_comp_count=-1), UST)
        with self.assertRaises(ValueError):
            solve(base(land_flood_cleared="yes"), UST)

    def test_negative_inputs_rejected(self):
        for f in ("capex", "lease_up_carry", "market_land_value", "reserves_psf", "sale_cost_pct", "renovation_spend"):
            with self.assertRaises(ValueError, msg=f):
                solve(base(**{f: -1}), UST)

    def test_in_place_noi_needs_lease_up_year(self):
        with self.assertRaises(ValueError):
            solve(base(in_place_noi=100_000), UST)

    def test_majority_vacant_derived(self):
        r = solve(base(in_place_noi=0, stabilization_year=2, vacant_sf_at_close=30_000), UST)
        self.assertAlmostEqual(r.floors["irr_floor"], 0.11)
        r = solve(base(in_place_noi=0, stabilization_year=2, vacant_sf_at_close=30_000, majority_vacant=False), UST)
        self.assertAlmostEqual(r.floors["irr_floor"], 0.11)  # explicit False cannot remove it
        r = solve(base(in_place_noi=0, stabilization_year=2), UST)
        self.assertTrue(any("vacancy at close" in f for f in r.flags))
        for kw in (dict(lease_up_carry=200_000), dict(stabilization_year=3, in_place_noi=100_000)):
            self.assertTrue(any("vacancy at close" in f for f in solve(base(**kw), UST).flags), kw)
        self.assertFalse(any("vacancy at close" in f for f in solve(base(), UST).flags))

    def test_lease_up_without_in_place_noi_rejected(self):
        with self.assertRaises(ValueError):
            solve(base(stabilization_year=3), UST)

    def test_vacant_modeled_as_stabilized_flagged(self):
        # review C12: 100% vacant, stabilized at close, no carry -> walk would be ~36% looser, so flag both gaps
        r = solve(base(vacant_sf_at_close=30_000), UST)
        looser = [f for f in r.flags if f.startswith("LOOSER THAN DOCTRINE")]
        self.assertEqual(len(looser), 2)
        r = solve(base(vacant_sf_at_close=30_000, in_place_noi=0, stabilization_year=2, lease_up_carry=245_000,
                       lease_expiry_month=200), UST)  # v4.52: lease runs past the hold -> no rollover flag
        self.assertFalse(any(f.startswith("LOOSER THAN DOCTRINE") for f in r.flags))
        # majority (not fully) vacant, stabilized at close -> only the stabilization flag
        r = solve(base(vacant_sf_at_close=20_000), UST)
        self.assertEqual(sum(f.startswith("LOOSER THAN DOCTRINE") for f in r.flags), 1)

    def test_exit_cap_above_market_does_not_loosen_dscr_floor(self):
        # review C16: DSCR @65% LTV = cap / (0.65 k); an override above market must not flip FLOOR-FLAGGED to PASS
        ust = 0.065
        market = solve(base(), ust)
        self.assertFalse(market.refi["dscr_floor_pass"])
        over = solve(base(exit_cap=0.08), ust)
        self.assertFalse(over.refi["dscr_floor_pass"])
        self.assertAlmostEqual(over.refi["dscr_at_65_ltv"], market.refi["dscr_at_65_ltv"])
        self.assertTrue(any("above the doctrine cap" in f for f in over.flags))
        self.assertLess(over.legs["irr"], market.legs["irr"])  # the IRR leg still uses the stricter override

    def test_token_lease_up_carry_flagged(self):
        token = lambda r: [f for f in r.flags if "below the Lease-Up Block TI default" in f]
        lu = dict(in_place_noi=0, stabilization_year=2)
        # 100% vacant: $8.00 x 30,000 = $240,000 is the TI floor alone
        r = solve(base(vacant_sf_at_close=30_000, lease_up_carry=239_999, **lu), UST)
        self.assertEqual(len(token(r)), 1)
        self.assertTrue(token(r)[0].startswith("LOOSER THAN DOCTRINE"))
        self.assertEqual(token(solve(base(vacant_sf_at_close=30_000, lease_up_carry=240_000, **lu), UST)), [])
        # partial vacancy: a CHECK, scaled to the vacant SF only (10,000 SF -> $80,000)
        r = solve(base(vacant_sf_at_close=10_000, lease_up_carry=79_999, in_place_noi=150_000, stabilization_year=2), UST)
        self.assertEqual(len(token(r)), 1)
        self.assertTrue(token(r)[0].startswith("CHECK"))
        self.assertEqual(token(solve(base(vacant_sf_at_close=10_000, lease_up_carry=80_000,
                                          in_place_noi=150_000, stabilization_year=2), UST)), [])
        # partial vacancy with zero carry is token too
        self.assertEqual(len(token(solve(base(vacant_sf_at_close=10_000), UST))), 1)
        # 100% vacant with $1 carry is token: exactly one token flag, on top of no zero-carry flag
        r = solve(base(vacant_sf_at_close=30_000, lease_up_carry=1, **lu), UST)
        self.assertEqual(len(token(r)), 1)
        self.assertFalse(any("no lease_up_carry" in f for f in r.flags))
        # 100% vacant with zero carry keeps its existing flag and is not double-counted
        r = solve(base(vacant_sf_at_close=30_000), UST)
        self.assertEqual(token(r), [])
        self.assertEqual(sum(f.startswith("LOOSER THAN DOCTRINE") for f in r.flags), 2)
        # no vacancy given, or none at close: nothing to test against
        self.assertEqual(token(solve(base(), UST)), [])
        self.assertEqual(token(solve(base(vacant_sf_at_close=0), UST)), [])

    def test_in_place_noi_above_occupied_share_flagged(self):
        hi = lambda r: [f for f in r.flags if "exceeds the occupied share" in f]
        kw = dict(vacant_sf_at_close=10_000, stabilization_year=2, lease_up_carry=200_000)
        # occupied share = (1 - 15,000/30,000) / 0.95 x 300,000 = 157,894.74
        half = dict(kw, vacant_sf_at_close=15_000)
        self.assertEqual(len(hi(solve(base(in_place_noi=157_895, **half), UST))), 1)
        self.assertEqual(hi(solve(base(in_place_noi=157_894, **half), UST)), [])
        # occupied share = (1 - 10,000/30,000) / 0.95 x 300,000 = 210,526.32
        self.assertEqual(len(hi(solve(base(in_place_noi=210_527, **kw), UST))), 1)
        self.assertEqual(hi(solve(base(in_place_noi=210_526, **kw), UST)), [])
        # 100% vacant: any positive in-place NOI is above the occupied share of zero
        self.assertEqual(len(hi(solve(base(vacant_sf_at_close=30_000, in_place_noi=1, stabilization_year=2,
                                          lease_up_carry=240_000), UST))), 1)
        # vacancy known to be zero: in-place above stabilized still flags (review C2)
        self.assertEqual(len(hi(solve(base(vacant_sf_at_close=0, in_place_noi=400_000, stabilization_year=3), UST))), 1)
        self.assertEqual(hi(solve(base(vacant_sf_at_close=0, in_place_noi=300_000, stabilization_year=3), UST)), [])
        # partly vacant but modeled stabilized at close: Year-1 NOI = stabilized > occupied share (review C10)
        r = solve(base(vacant_sf_at_close=12_000, lease_up_carry=96_000), UST)
        self.assertEqual(len(hi(r)), 1)
        self.assertIn("modeled stabilized at close", hi(r)[0])
        self.assertEqual(hi(solve(base(vacant_sf_at_close=0), UST)), [])
        # low vacancy (<= 5% structural, already in stabilized NOI) modeled stabilized at close: no flag
        for v in (300, 900, 1_500):
            self.assertEqual(hi(solve(base(vacant_sf_at_close=v), UST)), [], v)
        # ... but Year-1 above stabilized still flags at low vacancy, and just over 5% vacancy flags
        self.assertEqual(len(hi(solve(base(vacant_sf_at_close=900, in_place_noi=300_001, stabilization_year=2), UST))), 1)
        self.assertEqual(len(hi(solve(base(vacant_sf_at_close=1_530), UST))), 1)  # 5.1% vacant
        # without vacant_sf_at_close there is no occupied share to test
        self.assertEqual(hi(solve(base(in_place_noi=290_000, stabilization_year=2), UST)), [])
        # the flag is reported only: it does not change the walk
        a = solve(base(in_place_noi=200_000, **kw), UST)
        b = solve(base(in_place_noi=250_000, **kw), UST)
        self.assertGreater(b.legs["irr"], a.legs["irr"])  # higher Year-1 NOI loosens the IRR leg ...
        self.assertEqual(len(hi(b)), 1)                    # ... which is why it is flagged

    def test_hardening_flags_roll_up_to_portfolio(self):
        lu = dict(in_place_noi=250_000, stabilization_year=2, vacant_sf_at_close=10_000, lease_up_carry=1)
        res = solve_portfolio([base(name="A", **lu), base(name="B")], UST)
        self.assertTrue(any("below the Lease-Up Block TI default" in f for f in res["flags"]))
        self.assertTrue(any("exceeds the occupied share" in f for f in res["flags"]))

    def test_exactly_half_vacant_is_not_majority(self):
        r = solve(base(vacant_sf_at_close=15_000), UST)
        self.assertAlmostEqual(r.floors["irr_floor"], 0.10)
        r = solve(base(vacant_sf_at_close=15_001), UST)
        self.assertAlmostEqual(r.floors["irr_floor"], 0.11)

    def test_exit_cap_override_unmatched_market_flagged(self):
        r = solve(base(market="Nowhere TX", exit_cap=0.05), UST)
        self.assertTrue(any("BELOW" in f for f in r.flags))

    def test_low_reserves_flagged_and_stabilization_year_integer(self):
        self.assertTrue(any("Reserves" in f for f in solve(base(reserves_psf=0.0), UST).flags))
        with self.assertRaises(ValueError):
            solve(base(stabilization_year=2.5, in_place_noi=0), UST)

    def test_exit_cap_override_below_market_flagged(self):
        r = solve(base(exit_cap=0.06), UST)
        self.assertTrue(any("BELOW" in f for f in r.flags))
        with self.assertRaises(ValueError):
            solve(base(exit_cap=0.5), UST)

    def test_growth_above_base_flagged(self):
        self.assertTrue(any("above market Base" in f for f in solve(base(noi_growth=0.03), UST).flags))

    def test_chicago_alias_rct_and_flag(self):
        r = solve(base(market="Chicago–Greater Cook County IL"), UST)
        self.assertEqual(r.floors["market"], "Chicago-Cook IL")
        self.assertAlmostEqual(r.floors["rct_low_psf_adjusted"], 0.9 * P_CHI)
        self.assertEqual(r.floors["exit_cap"], 0.08)
        self.assertTrue(any("DENOMINATOR-SENSITIVE" in f for f in r.flags))
        self.assertEqual(solve(base(market="grand rapids"), UST).floors["exit_cap"], 0.08)

    def test_unknown_market_uses_cheapest_rct(self):
        r = solve(base(market="Nowhere"), UST)
        self.assertAlmostEqual(r.floors["rct_low_psf_adjusted"], 0.9 * P_CHI)
        self.assertEqual(r.floors["exit_cap"], 0.0775)

    def test_invalid_stabilization_year(self):
        with self.assertRaises(ValueError):
            solve(base(stabilization_year=10, in_place_noi=0), UST)


class LandAtMarket(unittest.TestCase):
    """v4.53 RE-4.53-1: all-in - MIN(L, 60% x all-in) <= (1 - floor) x improvements LOW."""
    def test_cap_and_inequality_tight_at_walk(self):
        B = 0.9 * P_COL * 30_000
        for L in (0, 100_000, 1_000_000, 2_000_000, 10_000_000):
            a = max_allin_basis(B, 0.65, L)
            self.assertAlmostEqual(a - credited_land(a, L), 0.35 * B, places=4)
            self.assertLessEqual(credited_land(a, L), 0.60 * a + 1e-9)
            # one dollar more all-in breaks the inequality
            self.assertGreater(a + 1 - credited_land(a + 1, L), 0.35 * B)

    def test_reported_credits_tie_when_cap_binds(self):
        # Round-3 review: every reported land-credit field must equal 60% x its own all-in once the cap binds,
        # all-in including the 2% closing, CapEx and carry.
        capex, carry, land = 100_000, 20_000, 5_000_000
        r = solve(base(capex=capex, lease_up_carry=carry, ask_price=3_000_000, market_land_value=land,
                       land_comp_count=3, land_flood_cleared=True), UST)
        B = 0.9 * P_COL * 30_000
        walk_allin = r.walk_price * 1.02 + capex + carry
        self.assertLess(0.60 * walk_allin, land)                      # the cap binds at walk
        self.assertAlmostEqual(r.floors["land_credit_at_walk"], 0.60 * walk_allin, places=4)
        self.assertAlmostEqual(r.floors["land_credit_at_basis_leg"], 0.60 * (0.35 * B / 0.4), places=4)
        ask_allin = 3_000_000 * 1.02 + capex + carry
        self.assertAlmostEqual(r.ask["ask_land_credit"], 0.60 * ask_allin, places=4)

    def test_cap_binds_on_land_heavy_rows(self):
        B = 0.9 * P_COL * 30_000
        self.assertAlmostEqual(max_allin_basis(B, 0.65, 5 * B), 0.35 * B / 0.4)

    def test_discount_measured_on_improvements_only(self):
        r = solve(base(ask_price=2_000_000, market_land_value=400_000, land_comp_count=4,
                       land_flood_cleared=True), UST)
        allin = 2_000_000 * 1.02
        self.assertAlmostEqual(r.ask["ask_land_credit"], 400_000)
        self.assertAlmostEqual(r.ask["ask_discount_to_replacement"], 1 - (allin - 400_000) / (0.9 * P_COL * 30_000))
        self.assertAlmostEqual(r.floors["replacement_total"], 0.9 * P_COL * 30_000)

    def test_denominator_sensitive_uses_improvements_discount(self):
        # Review C3: a land-credited ask that is "near" on the improvements-only discount but far on the old
        # all-in / replacement discount must flag; the old formula would miss it.
        B = 0.9 * P_COL * 30_000
        land = 1_200_000                   # below the 60% cap at this all-in
        allin = 0.35 * B + land            # exactly on the floor once land is credited
        price = allin / 1.02
        r = solve(base(stabilized_noi=150_000, ask_price=price, market_land_value=land, land_comp_count=3,
                       land_flood_cleared=True), UST)
        self.assertLess(land, 0.60 * allin)
        for denom in (B, P_COL * 30_000):                 # old formula, at LOW and at POINT: not "near", no flip
            self.assertGreater(abs((1 - allin / denom) - 0.65), 0.05)
            self.assertLess(1 - allin / denom, 0.65)
        self.assertTrue(any(f.startswith("DENOMINATOR-SENSITIVE at ask") for f in r.flags))
        # both the LOW and the POINT discount in the flag are improvements-only
        d_point = 1 - (allin - land) / (P_COL * 30_000)
        flag = next(f for f in r.flags if f.startswith("DENOMINATOR-SENSITIVE at ask"))
        self.assertIn(f"{0.65:.1%} (LOW) / {d_point:.1%} (POINT)", flag)

    def test_golden_kc_pemb_1974_land_comps_tbd(self):
        # RE-4.53-1 incident row (2026-11-14): KC, 7,000 SF PEMB (x0.88), built 1974, $1.3M ask, land comps TBD.
        # Synthetic RCT figures only (public repo). No NOI disclosed -> Yield = 0 by convention.
        p_kc = P["Kansas City MO"]
        d = Deal(name="KC PEMB 1974 (RE-4.53-1)", sf=7_000, stabilized_noi=0, market="Kansas City MO",
                 year_built=1974, construction_type="pemb", ask_price=1_300_000, single_tenant=False)
        r = solve(d, UST)
        low = 0.9 * p_kc * 0.88 * 7_000
        self.assertAlmostEqual(r.floors["construction_multiplier"], 0.88)
        self.assertAlmostEqual(r.floors["basis_floor_pct"], 0.65)
        self.assertAlmostEqual(r.legs["basis"], 0.35 * low / 1.02, places=4)
        self.assertTrue(any(f.startswith("[DATA-GAP: land]") for f in r.flags))
        self.assertAlmostEqual(r.ask["ask_discount_to_replacement"], 1 - 1_300_000 * 1.02 / low)
        self.assertIn("basis", r.ask["floors_flagged_at_ask"])
        # Once >= 3 cleared comps land, the credit is capped at 60% of all-in.
        big = solve(Deal(**{**d.__dict__, "market_land_value": 5_000_000, "land_comp_count": 3,
                            "land_flood_cleared": True}), UST)
        self.assertAlmostEqual(big.legs["basis"], 0.35 * low / 0.4 / 1.02, places=4)


class RiskTieredIrr(unittest.TestCase):
    """v4.53 RE-4.53-2: MAX(10%, UST + 550) + stacked add-ons."""
    def test_primitive_stacks(self):
        self.assertAlmostEqual(irr_floor(0.04, False, single_tenant=True), 0.11)
        self.assertAlmostEqual(irr_floor(0.05, True, single_tenant=True, tertiary=True, environmental=True,
                                         new_competency=True), 0.105 + 0.04)

    def test_deal_fields_drive_addons(self):
        f = lambda **kw: solve(base(**{"single_tenant": False, **kw}), UST).floors["irr_floor"]  # noqa: E731
        self.assertAlmostEqual(f(single_tenant=True), 0.11)
        self.assertAlmostEqual(f(market="Grand Rapids MI"), 0.105)
        self.assertAlmostEqual(f(market="Louisville KY"), 0.10)   # entry, not tertiary under RE-4.53-2
        self.assertAlmostEqual(f(satellite=True), 0.105)
        self.assertAlmostEqual(f(environmental_heavy_use=True), 0.105)
        self.assertAlmostEqual(f(environmental_heavy_use=True, clean_phase_ii=True), 0.10)
        self.assertAlmostEqual(f(new_operating_competency=True), 0.11)
        r = solve(base(single_tenant=True, market="Des Moines IA"), UST)
        self.assertAlmostEqual(r.floors["irr_floor"], 0.115)
        self.assertEqual([k for k, _ in r.floors["irr_floor_addons"]],
                         ["single tenant / tenant >50% of rent", "tertiary market"])
        self.assertAlmostEqual(r.floors["irr_floor_base"], 0.10)       # base excludes the add-ons

    def test_unstated_addon_inputs_flagged_not_applied(self):
        # Gabriel ruling 2026-11-14: satellite / environmental use / new competency unstated -> DATA-GAP, no add-on.
        r = solve(base(single_tenant=False), UST)
        for tag in ("DATA-GAP: satellite", "DATA-GAP: environmental use", "DATA-GAP: operating competency"):
            self.assertTrue(any(tag in f for f in r.flags), tag)
        self.assertAlmostEqual(r.floors["irr_floor"], 0.10)
        r = solve(base(single_tenant=False, satellite=False, environmental_heavy_use=False,
                       new_operating_competency=False), UST)
        self.assertFalse(any("DATA-GAP: satellite" in f or "DATA-GAP: environmental" in f
                             or "DATA-GAP: operating" in f for f in r.flags))
        # a tertiary market needs no satellite answer
        r = solve(base(market="Des Moines IA", single_tenant=False), UST)
        self.assertFalse(any("DATA-GAP: satellite" in f for f in r.flags))
        with self.assertRaises(ValueError):
            solve(base(satellite="no"), UST)

    def test_unknown_tenancy_flagged_not_applied(self):
        r = solve(base(), UST)
        self.assertTrue(any("DATA-GAP: tenant concentration" in f for f in r.flags))
        self.assertAlmostEqual(r.floors["irr_floor"], 0.10)
        # no vacancy exemption (ruling 2026-11-14): a fully vacant building still has to answer it
        r = solve(base(in_place_noi=0, stabilization_year=2, vacant_sf_at_close=30_000, lease_up_carry=400_000), UST)
        self.assertTrue(any("DATA-GAP: tenant concentration" in f for f in r.flags))

    def test_bad_types_on_addon_inputs_rejected(self):
        # review C4: a string must never lift or skip an add-on silently
        for kw in (dict(clean_phase_ii="false"), dict(environmental_heavy_use=""), dict(satellite=0),
                   dict(new_operating_competency="yes"), dict(single_tenant=1), dict(land_flood_cleared=None)):
            with self.assertRaises(ValueError, msg=kw):
                solve(base(**kw), UST)

    def test_portfolio_floor_is_highest_building_floor(self):
        p = solve_portfolio([base(name="A", single_tenant=False),
                             base(name="B", single_tenant=True, market="Richmond VA")], UST)
        self.assertAlmostEqual(p["portfolio_irr_floor"], 0.115)

    def test_off_cluster_flagged(self):
        self.assertTrue(any(f.startswith("Off-cluster") for f in solve(base(market="Nowhere"), UST).flags))


class Refi(unittest.TestCase):
    def test_dscr_floor_and_breakeven(self):
        r = solve(base(), 0.052)
        self.assertAlmostEqual(r.refi["breakeven_exit_cap"], 0.070, places=3)
        self.assertEqual(r.refi["binding_constraint"], "LTV")
        self.assertTrue(r.refi["dscr_floor_pass"])
        low = solve(base(exit_cap=0.065), 0.052)
        self.assertEqual(low.refi["binding_constraint"], "DSCR")
        self.assertFalse(low.refi["dscr_floor_pass"])
        self.assertTrue(any("FLOOR-FLAGGED" in f for f in low.flags))

    def test_loan_never_exceeds_either_governor_and_fee_applied(self):
        for cap in (0.06, 0.07, 0.08, 0.09):
            r = solve(base(exit_cap=cap), 0.05)
            self.assertLessEqual(r.refi["loan"], 0.65 * r.refi["stabilized_value"] + 1e-6)
            self.assertGreaterEqual(300_000 / (r.refi["loan"] * r.refi["debt_constant"]), 1.25 - 1e-9)
            self.assertAlmostEqual(r.refi["net_refi_proceeds"], 0.99 * r.refi["loan"])


class AskAndPortfolio(unittest.TestCase):
    def test_ask_gap(self):
        r = solve(base(ask_price=4_000_000), UST)
        self.assertAlmostEqual(r.ask["gap_to_ask"], 4_000_000 - r.walk_price)
        self.assertIn(r.binding_leg, r.ask["floors_flagged_at_ask"])

    def test_portfolio_premium_flags_buildings_and_skips_single_band(self):
        a = base(name="A", ask_price=12_000_000)
        b = base(name="B", stabilized_noi=200_000, sf=20_000)
        p = solve_portfolio([a, b], UST)
        self.assertAlmostEqual(p["sum_of_walks"], solve(a, UST).walk_price + solve(b, UST).walk_price)
        self.assertAlmostEqual(p["portfolio_walk_price"],
                               max(p["sum_of_walks"], min(p["max_price_blended_yoc"], p["max_price_portfolio_irr"])))
        self.assertGreater(p["max_premium_over_sum"], 0)
        self.assertTrue(any(f.startswith("FLOOR-FLAGGED: A") for f in p["flags"]))
        self.assertFalse(any("single-asset band" in f for f in p["flags"]))

    def test_allocation_method_noi_share(self):
        a = base(name="A", stabilized_noi=600_000, sf=40_000)
        c = base(name="C", stabilized_noi=160_000, sf=20_000)
        p = solve_portfolio([a, c], UST)
        self.assertEqual(p["allocation_method"], "(1) stabilized NOI share")
        prem = p["max_premium_over_sum"]
        self.assertAlmostEqual(p["allocation"][0]["premium_share"], prem * 600 / 760)

    def test_allocation_rct_gba_includes_adders(self):
        a = base(name="A", adders=["cranes", "climate_control", "office_buildout"])  # +$45/SF
        v = base(name="V", vacant_sf_at_close=30_000, in_place_noi=0, stabilization_year=2)
        p = solve_portfolio([a, v], UST)
        wa, wv = P_COL + 45, P_COL
        self.assertAlmostEqual(p["allocation"][0]["premium_share"], p["max_premium_over_sum"] * wa / (wa + wv))

    def test_explicit_false_does_not_silence_vacancy_gap(self):
        r = solve(base(in_place_noi=0, stabilization_year=2, majority_vacant=False), UST)
        self.assertTrue(any("vacancy at close" in f for f in r.flags))
        r = solve(base(in_place_noi=0, stabilization_year=2, majority_vacant=True), UST)
        self.assertFalse(any("vacancy at close" in f for f in r.flags))
        self.assertAlmostEqual(r.floors["irr_floor"], 0.11)

    def test_allocation_method_rct_gba_when_vacant(self):
        a = base(name="A")
        v = base(name="V", vacant_sf_at_close=30_000, in_place_noi=0, stabilization_year=2)
        p = solve_portfolio([a, v], UST)
        self.assertEqual(p["allocation_method"], "(2) replacement-cost-weighted GBA")
        self.assertAlmostEqual(p["allocation"][0]["premium_share"], p["max_premium_over_sum"] / 2)

    def test_negative_sum_of_walks_still_flags_buildings(self):
        a = base(name="A")
        b = base(name="B", capex=6_000_000)
        p = solve_portfolio([a, b], UST)
        self.assertLessEqual(p["sum_of_walks"], 0)
        self.assertGreater(p["max_premium_over_sum"], 0)
        self.assertTrue(any(f.startswith("FLOOR-FLAGGED: A") for f in p["flags"]))
        self.assertTrue(any("Sum of walks <= 0" in f for f in p["flags"]))

    def test_portfolio_gates(self):
        big = [base(name=str(i), stabilized_noi=3_000_000, sf=49_000) for i in range(6)]
        p = solve_portfolio(big, UST)
        self.assertTrue(any("2–5 buildings" in f for f in p["flags"]))
        self.assertTrue(any("walk > $15M" in f for f in p["flags"]))

    def test_portfolio_uses_highest_irr_floor_and_rolls_up_flags(self):
        p = solve_portfolio([base(name="A"), base(name="B", construction_type=None)], UST)
        self.assertTrue(any(f.startswith("B: [DATA-GAP: construction type]") for f in p["flags"]))
        p = solve_portfolio([base(name="A"), base(name="B", majority_vacant=True)], UST)
        self.assertAlmostEqual(p["portfolio_irr_floor"], 0.11)


class RolloverAndLeaseUpTiming(unittest.TestCase):
    """v4.52: partial-year lease-up and one expected-value rollover (Rollover Block)."""

    def _lease_up(self, **kw):
        d = dict(vacant_sf_at_close=30_000, in_place_noi=0, stabilization_year=3, lease_up_carry=300_000)
        d.update(kw)
        return base(**d)

    def test_lease_up_without_rollover_flagged(self):
        r = solve(self._lease_up(), UST)
        self.assertTrue(any("no modeled rollover" in f for f in r.flags))

    def test_partial_year_cash_start_lowers_irr_leg_vs_linear_ramp(self):
        lin = solve(self._lease_up(lease_expiry_month=200), UST)
        part = solve(self._lease_up(lease_expiry_month=200, cash_rent_start_month=24), UST)
        self.assertLess(part.legs["irr"], lin.legs["irr"])
        self.assertAlmostEqual(part.legs["yield"], lin.legs["yield"], places=2)  # stabilized year unchanged

    def test_rollover_lowers_irr_leg_and_flags_zero_cost(self):
        no = solve(self._lease_up(lease_expiry_month=200), UST)
        r0 = solve(self._lease_up(lease_expiry_month=81), UST)
        self.assertTrue(any("rollover_cost $0" in f for f in r0.flags))
        r = solve(self._lease_up(lease_expiry_month=81, rollover_cost=150_000), UST)
        self.assertLess(r0.legs["irr"], no.legs["irr"])
        self.assertLess(r.legs["irr"], r0.legs["irr"])

    def test_rollover_defaults_by_sf_band(self):
        from ora_walk.solver import _renewal_defaults
        self.assertEqual(_renewal_defaults(base(sf=30_000)), (0.75, 14))
        self.assertEqual(_renewal_defaults(base(sf=4_000)), (0.65, 7))

    def test_rollover_max_rule_not_additive(self):
        from ora_walk.solver import noi_path
        d = self._lease_up(lease_expiry_month=81, renewal_prob=0.95, rollover_downtime_months=12)
        p, q = noi_path(d), noi_path(self._lease_up(lease_expiry_month=200))
        # 5% x 3/12 and 5% x 9/12 expected downtime both sit under the 5% structural floor -> no haircut
        self.assertAlmostEqual(p[6], q[6]); self.assertAlmostEqual(p[7], q[7])

    def test_rollover_band_boundaries(self):
        from ora_walk.solver import _renewal_defaults
        expect = {4_999: (0.65, 7), 5_000: (0.70, 7), 9_999: (0.70, 7), 10_000: (0.72, 11),
                  24_999: (0.72, 11), 25_000: (0.75, 14)}
        for sf, want in expect.items():
            self.assertEqual(_renewal_defaults(base(sf=sf)), want, msg=sf)

    def test_rollover_year_and_cost_pinned(self):
        from ora_walk.solver import cash_path
        d = self._lease_up(lease_expiry_month=81, rollover_cost=150_000)   # month 81 -> year 7
        n, c = noi_path(d), cash_path(d)
        for t in range(11):
            self.assertAlmostEqual(c[t], n[t] - (150_000 if t == 6 else 0), msg=t)
        # The cost lands in the year downtime starts (month expiry + 1): expiry 83 -> month 84 (year 7),
        # expiry 84 -> month 85 (year 8).
        d = self._lease_up(lease_expiry_month=83, rollover_cost=1)
        self.assertAlmostEqual(cash_path(d)[6], noi_path(d)[6] - 1)
        d = self._lease_up(lease_expiry_month=84, rollover_cost=1)
        self.assertAlmostEqual(cash_path(d)[6], noi_path(d)[6])
        self.assertAlmostEqual(cash_path(d)[7], noi_path(d)[7] - 1)

    def test_rollover_haircut_exact_above_floor(self):
        # 30,000 SF defaults: renewal 75%, downtime 12 + 2 free = 14 months. Expiry month 72 -> months 73-84
        # (12 in year 7) and 85-86 (2 in year 8). f7 = 0.25 x 12/12, f8 = 0.25 x 2/12 (under the 5% floor).
        d = self._lease_up(lease_expiry_month=72)
        roll, flat = noi_path(d), noi_path(d, rollover=False)
        f7 = 0.25
        self.assertAlmostEqual(roll[6], flat[6] * (1 - (f7 - 0.05) / 0.95))
        self.assertAlmostEqual(roll[7], flat[7])          # 0.25 x 2/12 = 4.2% < 5% -> no haircut
        self.assertAlmostEqual(roll[5], flat[5])
        d = self._lease_up(lease_expiry_month=66)         # months 67-72 (6 in y6) and 73-80 (8 in y7)
        roll, flat = noi_path(d), noi_path(d, rollover=False)
        self.assertAlmostEqual(roll[5], flat[5] * (1 - (0.25 * 6 / 12 - 0.05) / 0.95))
        self.assertAlmostEqual(roll[6], flat[6] * (1 - (0.25 * 8 / 12 - 0.05) / 0.95))

    def test_partial_year_cash_share_exact(self):
        d = self._lease_up(lease_expiry_month=200, cash_rent_start_month=18)   # year 2: months 18-24 paid
        self.assertAlmostEqual(noi_path(d)[1], 300_000 * 7 / 12)
        self.assertAlmostEqual(noi_path(d)[0], 0.0)

    def test_cash_start_with_stabilized_close_rejected(self):
        with self.assertRaises(ValueError):
            solve(base(cash_rent_start_month=7), UST)
        solve(base(cash_rent_start_month=1), UST)  # month 1 is consistent with stabilized at close

    def test_yield_leg_and_refi_ignore_one_time_rollover(self):
        no = solve(self._lease_up(lease_expiry_month=200), UST)
        early = solve(self._lease_up(lease_expiry_month=26, renewal_prob=0.0, rollover_cost=100_000), UST)
        self.assertAlmostEqual(early.legs["yield"], no.legs["yield"], places=2)
        self.assertAlmostEqual(early.refi["loan"], no.refi["loan"], places=2)
        self.assertLess(early.legs["irr"], no.legs["irr"])

    def test_exit_year_rollover_is_a_credit_not_capitalized(self):
        no = solve(self._lease_up(lease_expiry_month=200), UST)
        y9 = solve(self._lease_up(lease_expiry_month=96, rollover_cost=1), UST)    # year 9, inside the hold
        y11 = solve(self._lease_up(lease_expiry_month=120), UST)                   # forward (exit) year, no cost
        loss9, loss11 = no.legs["irr"] - y9.legs["irr"], no.legs["irr"] - y11.legs["irr"]
        self.assertGreater(loss11, 0.5 * loss9)  # the forward-year rent loss is credited at sale on its own
        self.assertLess(loss11, 2 * loss9)   # capitalizing it at the exit cap would be ~1/cap (13x) larger
        c0 = solve(self._lease_up(lease_expiry_month=120), UST)
        c5 = solve(self._lease_up(lease_expiry_month=120, rollover_cost=500_000), UST)
        self.assertLess(c5.legs["irr"], c0.legs["irr"])  # forward-year re-leasing cost is credited at sale
        past = solve(self._lease_up(lease_expiry_month=140, rollover_cost=500_000), UST)
        self.assertAlmostEqual(past.legs["irr"], no.legs["irr"], places=2)
        self.assertFalse(any("rollover_cost $0" in f
                             for f in solve(self._lease_up(lease_expiry_month=140), UST).flags))
        self.assertTrue(any("rollover_cost $0" in f for f in y11.flags))  # forward year: cost matters, so flag

    def test_exit_credit_equals_forward_year_rent_loss(self):
        from ora_walk.solver import _reversion
        d0 = self._lease_up(lease_expiry_month=200)
        d = self._lease_up(lease_expiry_month=120, rollover_cost=50_000)
        cap = D.EXIT_CAPS["Columbus OH"]
        loss = noi_path(d, rollover=False)[10] - noi_path(d)[10]
        self.assertGreater(loss, 0)
        self.assertAlmostEqual(_reversion(d0, cap) - _reversion(d, cap), loss + 50_000)

    def test_non_finite_leg_is_an_error_even_past_validation(self):
        from unittest import mock
        from ora_walk import solver as S
        with mock.patch.object(S, "validate", lambda deal: None):  # backstop behind validate()
            with self.assertRaises(ValueError):
                solve(self._lease_up(lease_expiry_month=81, rollover_cost=float("nan")), UST)

    def test_non_finite_and_bool_rollover_inputs_rejected(self):
        for kw in (dict(rollover_cost=float("nan")), dict(rollover_cost=float("inf")), dict(rollover_cost=True),
                   dict(renewal_prob=float("nan")), dict(renewal_prob=True), dict(rollover_cost="40000")):
            with self.assertRaises(ValueError, msg=str(kw)):
                solve(self._lease_up(lease_expiry_month=81, **kw), UST)

    def test_levered_irr_reflects_rollover_cost(self):
        r0 = solve(self._lease_up(lease_expiry_month=81), UST)
        r1 = solve(self._lease_up(lease_expiry_month=81, rollover_cost=400_000), UST)
        self.assertLess(r1.refi["levered_irr_reported"], r0.refi["levered_irr_reported"])

    def test_bad_rollover_inputs_rejected(self):
        for kw in (dict(renewal_prob=1.5), dict(lease_expiry_month=0), dict(rollover_cost=-1),
                   dict(cash_rent_start_month=40)):
            with self.assertRaises(ValueError, msg=str(kw)):
                solve(self._lease_up(**kw), UST)


if __name__ == "__main__":
    unittest.main()
