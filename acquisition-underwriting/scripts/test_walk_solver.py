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
    """Literal values from SKILL.md v4.55 (v4.55 adds the Milwaukee exit cap row; v4.53 adds the land-credit cap and the IRR add-ons; v4.52/v4.54 mirror the Rollover Block; governor constants unchanged since v4.45) — any drift fails (Hard Invariant 4 for governors)."""
    def test_governors(self):
        self.assertEqual((D.DSCR_FLOOR, D.PER_PROPERTY_LTV_CEILING, D.AGGREGATE_LTV_CEILING), (1.25, 0.65, 0.40))
        self.assertEqual((D.YOC_FLOOR, D.IRR_FLOOR_MIN, D.IRR_FLOOR_UST_SPREAD, D.MAJORITY_VACANT_PREMIUM),
                         (0.08, 0.10, 0.055, 0.01))
        self.assertEqual((D.REFI_SPREAD, D.REFI_AMORT_YEARS, D.REFI_FINANCING_COST, D.CLOSING_COST),
                         (0.02, 25, 0.01, 0.02))
        self.assertEqual((D.RESERVES_PSF, D.EXPENSE_GROWTH, D.MARKET_RENT_GROWTH), (0.15, 0.03, 0.025))
        self.assertEqual(D.LEASE_UP_TI_PSF, 8.00)  # Lease-Up Assumption Block TI default
        self.assertEqual(D.STRUCTURAL_VACANCY, 0.05)  # Suite-Level Block vacancy-line floor

    def test_rollover_block(self):  # SKILL.md Suite-Level Rollover & Credit Block (a)/(b) and Lease-Up Block free rent
        inf = float("inf")
        self.assertEqual(D.RENEWAL_PROB_BY_SF, ((5_000, 0.65), (10_000, 0.70), (25_000, 0.72), (inf, 0.75)))
        self.assertEqual(D.ROLLOVER_DOWNTIME_BY_SF, ((10_000, 5), (25_000, 9), (inf, 12)))
        self.assertEqual(D.LEASE_UP_FREE_MONTHS, 2)
        self.assertEqual(D.RENEWAL_CAPTURE, 0.50)    # Renewal economics: 50% capture to market
        self.assertEqual(D.MGMT_FEE_EGI, 0.04)       # NOI input basis: 4% EGI management
        self.assertEqual(D.CREDIT_LOSS_EGI, 0.0125)  # Rollover Block (d) base credit loss
        self.assertEqual(D.RENEWAL_TI_PSF, 1.50)     # Renewal economics: renewal TI
        self.assertEqual(D.LEASE_UP_DOWNTIME_MONTHS, 9)  # Lease-Up Block standing downtime

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
            "Louisville KY": 0.0775, "Chicago-Cook IL": 0.08, "Milwaukee WI": 0.0875})  # v4.55 Milwaukee row
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
        nx = dict(no_lease_expiry_in_hold=True)  # v4.54: isolate these guards from the rollover flag
        r = solve(base(vacant_sf_at_close=30_000, **nx), UST)
        looser = [f for f in r.flags if f.startswith("LOOSER THAN DOCTRINE")]
        self.assertEqual(len(looser), 2)
        r = solve(base(vacant_sf_at_close=30_000, in_place_noi=0, stabilization_year=2, lease_up_carry=245_000,
                       **nx), UST)
        self.assertFalse(any(f.startswith("LOOSER THAN DOCTRINE") for f in r.flags))
        # majority (not fully) vacant, stabilized at close -> only the stabilization flag
        r = solve(base(vacant_sf_at_close=20_000, **nx), UST)
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
        r = solve(base(vacant_sf_at_close=30_000, no_lease_expiry_in_hold=True), UST)
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
        # the improvements-only discount uses the CAPPED credit, never the full market land value
        self.assertAlmostEqual(r.ask["ask_discount_to_replacement"], 1 - (ask_allin - 0.60 * ask_allin) / B,
                               places=6)

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
        # stated False applies no add-on; multifamily is always False (RE-4.60-5, v4.60)
        self.assertAlmostEqual(r.floors["irr_floor"], 0.10)
        self.assertEqual(r.floors["irr_floor_addons"], [])
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
                   dict(new_operating_competency="yes"), dict(single_tenant=1), dict(land_flood_cleared=None),
                   dict(land_comp_count=True)):
            with self.assertRaises(ValueError, msg=kw):
                solve(base(**kw), UST)

    def test_satellite_is_exempt_from_off_cluster_flag(self):
        self.assertTrue(any(f.startswith("Off-cluster") for f in solve(base(market="Nowhere"), UST).flags))
        self.assertFalse(any(f.startswith("Off-cluster")
                             for f in solve(base(market="Nowhere", satellite=True), UST).flags))

    def test_cli_names_each_irr_floor_addon(self):
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout
        from ora_walk.cli import main
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(dict(name="Z", sf=30_000, stabilized_noi=300_000, market="Columbus OH", year_built=2000,
                           construction_type="tilt-up", single_tenant=True), fh)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main([fh.name, "--ust", "0.045"]), 0)
        os.unlink(fh.name)
        self.assertIn("+ 100 bps single tenant", buf.getvalue())

    def test_portfolio_floor_is_highest_building_floor(self):
        p = solve_portfolio([base(name="A", single_tenant=False),
                             base(name="B", single_tenant=True, market="Richmond VA")], UST)
        self.assertAlmostEqual(p["portfolio_irr_floor"], 0.115)

    def test_off_cluster_flagged(self):
        self.assertTrue(any(f.startswith("Off-cluster") for f in solve(base(market="Nowhere"), UST).flags))

    def test_v455_milwaukee_row_sets_exit_cap_but_stays_off_cluster(self):
        for m in ("Milwaukee WI", "milwaukee", "Waukesha"):
            r = solve(base(market=m), UST)
            self.assertAlmostEqual(r.floors["exit_cap"], 0.0875, msg=m)
            self.assertTrue(any(f.startswith("Off-cluster") for f in r.flags), msg=m)
        self.assertFalse(any(f.startswith("Off-cluster") for f in solve(base(market="Madison WI"), UST).flags))
        self.assertEqual(D.NON_CANONICAL_EXIT_ROWS, {"Milwaukee WI"})
        # every exit-cap row without a ratified RCT market must be declared non-canonical (no silent flag loss)
        self.assertEqual(set(D.EXIT_CAPS) - set(D.RCT_MARKETS), set(D.NON_CANONICAL_EXIT_ROWS))


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
        self.assertGreater(p["max_premium_over_sum"], 0)
        self.assertTrue(any(f.startswith("PREMIUM-TEST: A") for f in p["flags"]))
        self.assertFalse(any(f.startswith("FLOOR-FLAGGED") for f in p["flags"]))  # walk = sum clears every floor
        self.assertFalse(any("single-asset band" in f for f in p["flags"]))
        # v4.55 (RE-4.55-2): a building breaching at its allocated price rejects the premium -> walk = sum of walks
        self.assertFalse(p["premium_admissible"])
        self.assertAlmostEqual(p["rejected_premium"], p["max_premium_over_sum"])
        self.assertAlmostEqual(p["portfolio_walk_price"], p["sum_of_walks"])
        self.assertTrue(any(f.startswith("PREMIUM REJECTED") for f in p["flags"]))

    def test_v455_premium_never_survives_any_positive_share(self):
        # Each walk sits on its binding leg, so any positive premium share breaches that leg.
        for kw in ({}, {"stabilized_noi": 200_000, "sf": 20_000}, {"single_tenant": True}):
            p = solve_portfolio([base(name="A"), base(name="B", **kw)], UST)
            self.assertAlmostEqual(p["portfolio_walk_price"], p["sum_of_walks"])
            if p["max_premium_over_sum"] > 1e-6:
                self.assertFalse(p["premium_admissible"])
            self.assertLessEqual(p["portfolio_walk_price"], p["sum_of_walks"] + 1e-6)

    def test_v455_cli_prints_rejected_premium_and_sum_walk(self):
        import io
        import json
        import tempfile
        from contextlib import redirect_stdout
        from ora_walk.cli import main
        spec = {"portfolio": [dict(name="A", sf=30_000, stabilized_noi=300_000, market="Columbus OH",
                                   year_built=2000, construction_type="tilt-up"),
                              dict(name="B", sf=20_000, stabilized_noi=200_000, market="Columbus OH",
                                   year_built=2000, construction_type="tilt-up")]}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump(spec, fh)
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertEqual(main([fh.name, "--ust", "0.045"]), 0)
        os.unlink(fh.name)
        out = buf.getvalue()
        from ora_walk.cli import _deal, _usd
        p = solve_portfolio([_deal(d) for d in spec["portfolio"]], 0.045)  # the same deals the CLI ran
        self.assertGreater(p["max_premium_over_sum"], 1e-6)  # non-vacuous: a premium exists and is rejected
        self.assertIn("REJECTED (a building breaches its own floor, v4.55)", out)  # the summary line itself
        self.assertNotIn("admissible ·", out)
        self.assertIn(f"**Portfolio walk {_usd(p['sum_of_walks'])}**", out)
        self.assertNotIn(f"**Portfolio walk {_usd(p['sum_of_walks'] + p['max_premium_over_sum'])}**", out)

    def test_v455_gap_to_ask_and_15m_gate_read_the_sum_of_walks(self):
        a = base(name="A", stabilized_noi=300_000, sf=30_000)
        b = base(name="B", stabilized_noi=200_000, sf=20_000)
        p = solve_portfolio([a, b], UST, portfolio_ask=9_000_000)
        self.assertAlmostEqual(p["gap_to_ask"], 9_000_000 - p["sum_of_walks"])
        # gate: scale NOI so the sum of walks sits under USD 15M while sum + rejected premium sits above it
        k = 14_000_000 / p["sum_of_walks"]
        q = solve_portfolio([base(name="A", stabilized_noi=300_000 * k, sf=30_000),
                             base(name="B", stabilized_noi=200_000 * k, sf=20_000)], UST)
        self.assertLess(q["sum_of_walks"], 15_000_000)
        if q["sum_of_walks"] + q["max_premium_over_sum"] > 15_000_000:
            self.assertFalse(any("walk > $15M" in f for f in q["flags"]))
        else:
            self.skipTest("premium too small at this scale to straddle the USD 15M gate")

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
        self.assertTrue(any(f.startswith("PREMIUM-TEST: A") for f in p["flags"]))  # v4.55: premium rejected
        self.assertAlmostEqual(p["portfolio_walk_price"], p["sum_of_walks"])
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
    """v4.54: partial-year lease-up and expected-value rollovers on a gross-revenue basis (Rollover Block)."""
    EGI_NET = 1 - 0.04 - 0.0125           # management fee and credit loss move with EGI
    NX = dict(no_lease_expiry_in_hold=True)

    def _lease_up(self, **kw):
        d = dict(vacant_sf_at_close=30_000, in_place_noi=0, stabilization_year=3, lease_up_carry=300_000)
        d.update(kw)
        return base(**d)

    # --- C1: backward compatibility ---
    def test_no_rollover_path_is_plain_market_growth(self):
        from ora_walk.solver import noi_path
        for t, v in enumerate(noi_path(base(**self.NX)), start=1):
            self.assertAlmostEqual(v, 300_000 * 1.025 ** (t - 1))

    # --- C7(a): downtime priced on gross revenue, opex still paid ---
    def test_downtime_cut_is_on_gross_revenue_hand_computed(self):
        from ora_walk.solver import noi_path
        d = base(sf=20_000, stabilized_noi=150_000, gpr=250_000, lease_expiry_month=3,
                 renewal_prob=0.7, rollover_downtime_months=12)
        p = noi_path(d)
        # Y1: months 4-12 dark w.p. 0.3 -> 0.3 x 9/12 x 250,000 = 56,250 vs the 12,500 already netted
        self.assertAlmostEqual(p[0], 150_000 - (56_250 - 12_500) * self.EGI_NET)
        # Y2: months 13-15 -> 0.3 x 3/12 x 256,250 = 19,218.75 vs 12,812.50
        self.assertAlmostEqual(p[1], 153_750 - (19_218.75 - 12_812.5) * self.EGI_NET)
        self.assertAlmostEqual(p[2], 150_000 * 1.025 ** 2)
        # the cut does not depend on the NOI level (opex does not fall when the space is dark)
        q = noi_path(base(sf=20_000, stabilized_noi=100_000, gpr=250_000, lease_expiry_month=3,
                          renewal_prob=0.7, rollover_downtime_months=12))
        self.assertAlmostEqual(p[0] - 150_000, q[0] - 100_000)

    def test_max_rule_not_additive(self):
        from ora_walk.solver import noi_path
        d = self._lease_up(gpr=400_000, lease_expiry_month=81, renewal_prob=0.95, rollover_downtime_months=12)
        p, q = noi_path(d), noi_path(self._lease_up(**self.NX))
        # 5% x 3/12 and 5% x 9/12 expected downtime both sit under the 5% structural floor -> no cut
        self.assertAlmostEqual(p[6], q[6]); self.assertAlmostEqual(p[7], q[7])

    # --- C7(b): every expiry rolls ---
    def test_branch_calendar_hand_computed(self):
        # sf 30,000: p 0.75, downtime 12 vacant + 2 free = 14 dark. Renewal expires at e + 36; the new lease's
        # term starts after the 12 vacant months, free rent inside the term (Gabriel ruling 2026-11-14): e + 48.
        from ora_walk.solver import _calendar, _rollover_cost_years, cash_path, noi_path
        d = base(gpr=400_000, lease_expiry_month=36, lease_term_months=36, rollover_cost=100_000)
        cal = _calendar(d, 132)
        got = [(e, round(w, 6)) for e, w in cal.events]
        self.assertEqual(got, [(36, 1.0), (72, 0.75), (84, 0.25), (108, 0.5625), (120, 0.375), (132, 0.0625)])  # 120 merges; 132 is year 11
        self.assertAlmostEqual(cal.dark[40], 0.25)                # 37-50: first new-lease downtime
        self.assertAlmostEqual(cal.dark[51], 0.0)
        self.assertAlmostEqual(cal.dark[80], 0.75 * 0.25)         # 73-86: downtime after the month-72 renewal
        self.assertAlmostEqual(cal.dark[90], 0.25 * 0.25)         # 85-98: downtime after the month-84 new lease
        yc = _rollover_cost_years(d, 11)
        self.assertEqual([y for y, _ in yc], [3, 6, 7, 9, 10, 11])    # year of the expiry month
        for (y, c), w in zip(yc, (1.0, 0.75, 0.25, 0.5625, 0.375, 0.0625)):
            self.assertAlmostEqual(c, w * 100_000 * 1.03 ** (y - 3))
        diff = [a - b for a, b in zip(noi_path(d), cash_path(d))]
        self.assertEqual([i + 1 for i, x in enumerate(diff) if abs(x) > 1e-9], [3, 6, 7, 9, 10, 11])
        one = noi_path(base(gpr=400_000, lease_expiry_month=36, rollover_cost=100_000))
        self.assertLess(noi_path(d)[6], one[6])                   # the month-72 renewal expiry goes dark too

    def test_new_lease_branch_runs_full_term_from_end_of_downtime(self):
        # review round 3: a lockstep calendar (both branches expiring at e + term) left the exit year almost
        # free of vacancy. With e 34, term 24: renewal expiries 58, 82, 106, 130; the new lease from 34 starts
        # its term after 12 vacant months (free rent inside the term) and expires at 70.
        from ora_walk.solver import _calendar
        cal = _calendar(base(gpr=240_000, stabilized_noi=170_000, lease_expiry_month=34, lease_term_months=24), 132)
        months = dict(cal.events)
        self.assertAlmostEqual(months[58], 0.75)              # lockstep would also expire the new lease here
        self.assertAlmostEqual(months[70], 0.25)
        self.assertGreater(sum(cal.dark[121:133]), 0.25)

    # --- C7(c): base rent resets toward market at each rollover ---
    def test_rent_reset_hand_computed(self):
        from ora_walk.solver import _calendar, noi_path
        d = base(gpr=450_000, base_rent=360_000, market_rent_ratio=0.8, lease_expiry_month=60,
                 lease_term_months=60, rollover_cost=100_000)
        cal = _calendar(d, 132)
        # after month 60: renewal at 0.9 (w 0.75), new lease at 0.8 (w 0.25) -> excess -0.125
        self.assertAlmostEqual(cal.excess[90], 0.75 * -0.1 + 0.25 * -0.2)
        # after the month-120 renewal expiry: renewal again at 0.85 (w 0.5625), its new lease dark at 0.8
        # (w 0.1875), and the month-60 new lease still running at 0.8 (w 0.25)
        self.assertAlmostEqual(cal.excess[125], 0.5625 * -0.15 + 0.1875 * -0.2 + 0.25 * -0.2)
        self.assertAlmostEqual(cal.dark[125], 0.1875)
        # year 8 (months 85-96): after the first rollover, outside any downtime window
        base8 = 360_000 * 1.025 ** 7
        want = 300_000 * 1.025 ** 7 - 0.125 * base8 * 0.95 * self.EGI_NET
        self.assertAlmostEqual(noi_path(d)[7], want)

    def test_dark_months_lose_the_new_lease_market_rent(self):
        # the (1 - p) branch is dark: it loses the market rent its new lease would earn, never a blend
        from ora_walk.solver import noi_path
        d = base(gpr=450_000, base_rent=360_000, market_rent_ratio=1.4, lease_expiry_month=36,
                 lease_term_months=60, rollover_cost=1)
        g = 1.025 ** 3
        gpr4, base4 = 450_000 * g, 360_000 * g
        level = 1 + 0.4 * (0.75 * 0.5 + 0.25)                 # 1.25 after the first rollover
        revenue = gpr4 + (level - 1) * base4                    # year 4 = months 37-48, all after the expiry
        dark = 0.25 * (gpr4 + 0.4 * base4)                      # every month dark (downtime 14), market rent lost
        d_egi = (revenue - gpr4) - (max(0.05 * revenue, dark) - 0.05 * gpr4)
        self.assertAlmostEqual(noi_path(d)[3], 300_000 * g + d_egi * self.EGI_NET)
        # stabilization-year downtime feeds the yield leg: year 1, expiry month 1, months 2-12 dark (11 of 12)
        up = solve(base(gpr=450_000, base_rent=360_000, market_rent_ratio=1.4, lease_expiry_month=1,
                        lease_term_months=60, rollover_cost=1), UST)
        revenue = 450_000 + (level - 1) * 360_000 * 11 / 12
        dark = 0.25 * (450_000 + 0.4 * 360_000) * 11 / 12
        d_egi = (revenue - 450_000) - (max(0.05 * revenue, dark) - 0.05 * 450_000)
        self.assertAlmostEqual(up.floors["stabilized_noi_net"], 300_000 + d_egi * self.EGI_NET)

    # --- C6: flags ---
    def test_no_rollover_flag_fires_on_stabilized_deals_unless_asserted(self):
        self.assertTrue(any("no modeled rollover" in f for f in solve(base(), UST).flags))
        self.assertTrue(any("no modeled rollover" in f for f in solve(self._lease_up(), UST).flags))
        self.assertFalse(any("no modeled rollover" in f for f in solve(base(**self.NX), UST).flags))

    def test_zero_cost_flag_only_when_cost_lands_inside_hold(self):
        full = dict(gpr=400_000, lease_term_months=60, market_rent_ratio=1.0, base_rent=300_000)
        zero = lambda e: any("rollover_cost $0" in f for f in solve(base(lease_expiry_month=e, **full), UST).flags)
        self.assertTrue(zero(119))
        self.assertTrue(zero(120))      # cost booked in the expiry month, year 10: inside the hold
        self.assertTrue(zero(121))      # year 11: comes off the sale proceeds (v4.54 refute round 7)
        self.assertTrue(zero(131))
        self.assertTrue(zero(132))      # last month of year 11 (refute round 8)
        self.assertFalse(zero(133))     # nothing rolls inside the modeled 11 years

    def test_year_11_rollover_cost_comes_off_the_sale_proceeds(self):
        # v4.54 refute round 7: the exit capitalized year-11 NOI but dropped the year-11 re-leasing cost, so a
        # cost booked in year 11 never reached the IRR leg and the walk jumped when the expiry moved 120 -> 121
        from ora_walk import doctrine as D
        from ora_walk.solver import _unlevered_pv, cash_path, noi_path
        full = dict(gpr=400_000, lease_term_months=60, market_rent_ratio=1.0, base_rent=300_000)
        d = base(lease_expiry_month=125, rollover_cost=150_000, **full)
        cap, rate = 0.0775, 0.10
        noi, cash = noi_path(d), cash_path(d)
        self.assertAlmostEqual(noi[10] - cash[10], 150_000)            # first expiry: weight 1, first-expiry dollars
        flows = [0.0] + cash[:10]
        flows[-1] += noi[10] / cap * (1 - d.sale_cost_pct) - 150_000
        from ora_walk.solver import npv
        self.assertAlmostEqual(_unlevered_pv(d, rate, cap), npv(rate, flows))
        # the cost is never free: a dearer year-11 rollover lowers the IRR leg
        cheap = solve(base(lease_expiry_month=125, rollover_cost=100_000, **full), UST)
        dear = solve(base(lease_expiry_month=125, rollover_cost=250_000, **full), UST)
        self.assertLess(dear.legs["irr"], cheap.legs["irr"])
        # no jump at the hold/exit boundary: the walk cost of the re-leasing spend is the same whether the expiry
        # books it in year 10 (cash flow) or year 11 (off the proceeds, same end-of-year-10 timing)
        cost = lambda e: (solve(base(lease_expiry_month=e, rollover_cost=1, **full), UST).legs["irr"]
                          - solve(base(lease_expiry_month=e, rollover_cost=150_000, **full), UST).legs["irr"])
        self.assertGreater(cost(121), 0)
        self.assertAlmostEqual(cost(120), cost(121), delta=1.0)
        self.assertAlmostEqual(cost(120), cost(131), delta=1.0)
        self.assertAlmostEqual(cost(120), cost(132), delta=1.0)   # refute round 8: month 132 is year 11

    def test_year_11_cost_reaches_the_levered_irr_too(self):
        from ora_walk.solver import _refi
        full = dict(gpr=400_000, lease_term_months=60, market_rent_ratio=1.0, base_rent=300_000)
        lo = _refi(base(lease_expiry_month=125, rollover_cost=100_000, **full), 3_000_000, UST, 0.0775)
        hi = _refi(base(lease_expiry_month=125, rollover_cost=250_000, **full), 3_000_000, UST, 0.0775)
        self.assertLess(hi["levered_irr_reported"], lo["levered_irr_reported"])

    def test_ti_floor_covers_year_11_expiries(self):
        full = dict(gpr=400_000, lease_expiry_month=125, lease_term_months=60, market_rent_ratio=1.0, base_rent=300_000)
        low = lambda c: any("TI floor" in f for f in solve(base(rollover_cost=c, **full), UST).flags)
        self.assertTrue(low(93_750))
        self.assertFalse(low(93_750 * 1.03 ** 10 + 1))

    def test_refi_sized_on_noi_including_stabilization_year_downtime(self):
        # refute round 7 low: the refi reads stabilization-year NOI including modeled downtime
        full = dict(gpr=400_000, lease_term_months=60, market_rent_ratio=1.0, base_rent=300_000, rollover_cost=100_000)
        dark = solve(base(lease_expiry_month=1, **full), UST)
        clean = solve(base(lease_expiry_month=200, **full), UST)
        self.assertLess(dark.refi["loan"], clean.refi["loan"])
        self.assertLess(dark.refi["stabilized_value"], clean.refi["stabilized_value"])

    def test_month_132_expiry_contradicts_the_no_expiry_assertion(self):
        with self.assertRaises(ValueError):
            solve(base(gpr=400_000, lease_expiry_month=132, no_lease_expiry_in_hold=True), UST)
        solve(base(gpr=400_000, lease_expiry_month=133, no_lease_expiry_in_hold=True), UST)

    def test_month_132_boundaries_pinned(self):
        # refute round 8 lows: boundaries moved to month 132 with no test on the edge
        full = dict(gpr=400_000, base_rent=300_000, market_rent_ratio=1.0, rollover_cost=150_000)
        chk = lambda e: any("lease_term_months" in f and f.startswith("CHECK") for f in solve(base(
            lease_expiry_month=e, lease_term_months=15, **full), UST).flags)
        self.assertTrue(chk(119))       # second expiry could land by month 132 (119 + 13), the term puts it at 134
        self.assertFalse(chk(120))      # 120 + 13 = 133: no second expiry possible anyway
        # the reset starts the month after the expiry, so a month-132 expiry moves nothing and is not flagged
        reset = lambda e: any("no market-rent reset" in f for f in solve(base(
            gpr=400_000, lease_expiry_month=e, lease_term_months=60, rollover_cost=150_000), UST).flags)
        self.assertTrue(reset(131))
        self.assertFalse(reset(132))

    def test_free_rent_clamp_with_a_one_month_downtime(self):
        # downtime 1 is shorter than the 2 free months: the new lease's term starts at the expiry, never before
        from ora_walk.solver import _calendar
        cal = _calendar(base(gpr=400_000, lease_expiry_month=36, lease_term_months=24, rollover_downtime_months=1), 132)
        self.assertEqual([(e, round(w, 6)) for e, w in cal.events][:2], [(36, 1.0), (60, 1.0)])

    def test_negative_gpr_rejected(self):
        with self.assertRaises(ValueError):
            solve(base(stabilized_noi=-50_000, gpr=-10_000, lease_expiry_month=60), UST)

    def test_expiry_past_the_exit_year_checked(self):
        # refute low: an expiry past month 132 silences the no-rollover flag without the assertion
        r = solve(base(gpr=400_000, lease_expiry_month=200), UST)
        self.assertFalse(any("no modeled rollover" in f for f in r.flags))
        self.assertTrue(any(f.startswith("CHECK") and "past the exit year" in f for f in r.flags))

    def test_term_and_reset_flags(self):
        r = solve(base(gpr=400_000, lease_expiry_month=60, rollover_cost=1), UST)
        self.assertTrue(any("no lease_term_months" in f for f in r.flags))
        self.assertTrue(any("no market-rent reset" in f for f in r.flags))
        r = solve(base(gpr=400_000, lease_expiry_month=60, rollover_cost=120_000, lease_term_months=60,
                       market_rent_ratio=1.0, base_rent=300_000), UST)
        self.assertFalse(any(f.startswith("LOOSER THAN DOCTRINE") for f in r.flags))

    def test_overrides_looser_than_band_defaults_flagged(self):
        full = dict(gpr=400_000, lease_expiry_month=60, lease_term_months=60, market_rent_ratio=1.0,
                    base_rent=300_000, rollover_cost=250_000)
        flags = lambda **kw: [f for f in solve(base(**full, **kw), UST).flags if f.startswith("LOOSER THAN DOCTRINE")]
        self.assertTrue(any("renewal_prob" in f for f in flags(renewal_prob=0.9)))   # band default 0.75
        self.assertEqual(flags(renewal_prob=0.75), [])
        self.assertEqual(flags(renewal_prob=0.5), [])                                # stricter: no flag
        self.assertTrue(any("rollover_downtime_months" in f for f in flags(rollover_downtime_months=6)))   # moves the IRR leg
        self.assertEqual(flags(rollover_downtime_months=12), [])   # 2 fewer months, but under the 5% floor: no leg moves
        self.assertEqual(flags(rollover_downtime_months=14), [])
        # refute round 8: a longer downtime pushes the new lease's month-132 expiry (and its cost) past the
        # modeled years, so the IRR leg rises and the measured flag fires
        self.assertTrue(any("rollover_downtime_months" in f for f in flags(rollover_downtime_months=20)))
        # review round 4: below-market lease, LOWER renewal_prob means more new leases capturing the full gap,
        # so the walk rises: the flag follows the walk, not a fixed direction
        small = dict(sf=4_000, stabilized_noi=15_300, gpr=21_600, base_rent=16_200, market_rent_ratio=1.5,
                     lease_expiry_month=12, lease_term_months=36, rollover_cost=38_000)
        hit = lambda **kw: any("renewal_prob" in f and f.startswith("LOOSER") for f in solve(base(**small, **kw), UST).flags)
        self.assertGreater(solve(base(**small, renewal_prob=0.3), UST).walk_price, solve(base(**small), UST).walk_price)
        self.assertTrue(hit(renewal_prob=0.3))
        self.assertFalse(hit(renewal_prob=0.65))
        for p in (0.0, 1.0):                                   # degenerate probabilities solve cleanly
            solve(base(**small, renewal_prob=p), UST)

    def test_exit_year_expiries_gated_like_hold_expiries(self):
        e125 = dict(gpr=400_000, lease_expiry_month=125, rollover_cost=1)
        r = solve(base(**e125), UST)
        self.assertTrue(any("no market-rent reset" in f for f in r.flags))     # year-11 exit NOI moves
        self.assertFalse(any("no lease_term_months" in f for f in r.flags))     # a second expiry cannot land
        with self.assertRaises(ValueError):
            solve(base(no_lease_expiry_in_hold=True, **e125), UST)
        term = lambda e: any("no lease_term_months" in f for f in solve(
            base(gpr=400_000, lease_expiry_month=e, rollover_cost=1, market_rent_ratio=1.0, base_rent=300_000), UST).flags)
        self.assertTrue(term(119))      # next expiry could be month 132, the last month of year 11
        self.assertFalse(term(120))     # next expiry is month 133 at the earliest: outside every modeled year

    def test_token_rollover_cost_flagged_against_ti_floor(self):
        # floor per expiry = sf x (p x 1.50 renewal TI + (1 - p) x 8.00 new-lease TI); sf 30,000, p 0.75 -> 93,750,
        # grown to the first expiry year (month 60 = year 5): x 1.03^4
        full = dict(gpr=400_000, lease_expiry_month=60, lease_term_months=60, market_rent_ratio=1.0, base_rent=300_000)
        low = lambda c: any("rollover_cost" in f and "TI floor" in f for f in solve(base(rollover_cost=c, **full), UST).flags)
        floor = 93_750 * 1.03 ** 4
        self.assertTrue(low(1)); self.assertTrue(low(floor - 1)); self.assertTrue(low(0))
        self.assertFalse(low(floor + 1))

    def test_early_cash_rent_start_flagged_and_misstated_stabilization_rejected(self):
        early = lambda c, s=2: any("cash_rent_start_month" in f for f in solve(
            self._lease_up(stabilization_year=s, cash_rent_start_month=c, **self.NX), UST).flags)
        self.assertTrue(early(2)); self.assertTrue(early(11))     # Lease-Up Block: 9 months + 2 free -> month 12
        self.assertFalse(early(12)); self.assertFalse(early(13))
        with self.assertRaises(ValueError):                        # a full year of rent before stabilization
            solve(self._lease_up(stabilization_year=3, cash_rent_start_month=13, **self.NX), UST)

    def test_override_cannot_shrink_the_ti_floor(self):
        # review round 5: renewal_prob 1.0 halved the floor (USD 3.125 -> 1.50/SF), so a 45,000 cost passed
        # unflagged and the walk rose 2.2%; the floor now uses the stricter of the default and override p
        d = dict(sf=30_000, stabilized_noi=300_000, gpr=420_000, base_rent=300_000, lease_expiry_month=12,
                 lease_term_months=84, market_rent_ratio=1.5, market_land_value=6_000_000, land_comp_count=3,
                 land_flood_cleared=True, exit_cap=0.13, noi_growth=0.0)
        r = solve(base(**d, renewal_prob=1.0, rollover_cost=45_000), UST)
        self.assertTrue(any("TI floor" in f for f in r.flags))

    def test_ti_floor_grows_to_the_first_expiry_year(self):
        # first expiry month 108 = year 9: floor 93,750 x 1.03^8
        full = dict(gpr=400_000, lease_expiry_month=108, lease_term_months=60, market_rent_ratio=1.0, base_rent=300_000)
        low = lambda c: any("TI floor" in f for f in solve(base(rollover_cost=c, **full), UST).flags)
        self.assertTrue(low(93_750))
        self.assertFalse(low(93_750 * 1.03 ** 8 + 1))

    def test_override_valid_only_with_itself_is_flagged_not_crashed(self):
        # term 13 is valid with a 5-month downtime override but not with the 14-month default
        r = solve(base(gpr=400_000, lease_expiry_month=24, lease_term_months=13, rollover_downtime_months=5,
                       market_rent_ratio=1.0, base_rent=300_000, rollover_cost=100_000), UST)
        self.assertTrue(any(f.startswith("LOOSER") and "rollover_downtime_months" in f for f in r.flags))

    def test_market_rent_above_in_place_checked(self):
        chk = lambda m: any("market_rent_ratio" in f and f.startswith("CHECK") for f in solve(base(
            gpr=400_000, base_rent=300_000, market_rent_ratio=m, lease_expiry_month=60, lease_term_months=60,
            rollover_cost=100_000), UST).flags)
        self.assertTrue(chk(1.3)); self.assertFalse(chk(1.0)); self.assertFalse(chk(0.9))

    def test_long_term_that_suppresses_repeat_rollover_checked(self):
        # review round 6: a term that puts every second expiry past month 132 behaves like no term at all
        chk = lambda T: any("lease_term_months" in f and f.startswith("CHECK") for f in solve(base(
            gpr=400_000, base_rent=300_000, market_rent_ratio=1.0, lease_expiry_month=18, lease_term_months=T,
            rollover_cost=120_000), UST).flags)
        self.assertTrue(chk(120)); self.assertTrue(chk(115))     # 18 + 115 = 133
        self.assertFalse(chk(114)); self.assertFalse(chk(36))

    def test_non_finite_leg_is_an_error_even_past_validation(self):
        from unittest import mock
        from ora_walk import solver as S
        with mock.patch.object(S, "validate", lambda deal: None):  # backstop behind validate()
            with self.assertRaises(ValueError):
                solve(base(gpr=400_000, lease_expiry_month=60, rollover_cost=float("nan")), UST)

    def test_gpr_equal_to_base_rent_checked(self):
        nnn = lambda g: any("gpr equals base_rent" in f for f in solve(base(
            gpr=g, base_rent=400_000, market_rent_ratio=1.0, lease_expiry_month=60, lease_term_months=60,
            rollover_cost=100_000), UST).flags)
        self.assertTrue(nnn(400_000)); self.assertFalse(nnn(450_000))

    def test_override_flags_silent_when_nothing_is_modeled(self):
        r = solve(base(gpr=400_000, lease_expiry_month=200, renewal_prob=0.99, rollover_downtime_months=1), UST)
        self.assertFalse(any("renewal_prob" in f or "rollover_downtime_months" in f for f in r.flags))

    # --- lease-up timing and leg ordering ---
    def test_partial_year_cash_start_lowers_irr_leg_vs_linear_ramp(self):
        lin = solve(self._lease_up(**self.NX), UST)
        part = solve(self._lease_up(cash_rent_start_month=24, **self.NX), UST)
        self.assertLess(part.legs["irr"], lin.legs["irr"])
        self.assertAlmostEqual(part.legs["yield"], lin.legs["yield"], places=2)  # stabilized year unchanged

    def test_rollover_and_its_cost_lower_the_irr_leg(self):
        no = solve(self._lease_up(**self.NX), UST)
        r0 = solve(self._lease_up(gpr=400_000, lease_expiry_month=81), UST)
        r = solve(self._lease_up(gpr=400_000, lease_expiry_month=81, rollover_cost=150_000), UST)
        self.assertLess(r0.legs["irr"], no.legs["irr"])
        self.assertLess(r.legs["irr"], r0.legs["irr"])

    def test_rollover_defaults_by_sf_band(self):
        from ora_walk.solver import _renewal_defaults
        self.assertEqual(_renewal_defaults(base(sf=30_000)), (0.75, 14))
        self.assertEqual(_renewal_defaults(base(sf=4_000)), (0.65, 7))
        self.assertEqual(_renewal_defaults(base(sf=4_999)), (0.65, 7))
        self.assertEqual(_renewal_defaults(base(sf=5_000)), (0.70, 7))
        self.assertEqual(_renewal_defaults(base(sf=10_000)), (0.72, 11))
        self.assertEqual(_renewal_defaults(base(sf=25_000)), (0.75, 14))

    # --- C4: validation ---
    def test_bad_rollover_inputs_rejected(self):
        nan = float("nan")
        ok = dict(gpr=400_000, lease_expiry_month=60)
        cases = [
            self._lease_up(renewal_prob=1.5, **ok), self._lease_up(lease_expiry_month=0, gpr=400_000),
            self._lease_up(rollover_cost=-1, **ok), self._lease_up(cash_rent_start_month=40, **self.NX),
            base(rollover_cost=nan, **ok), base(gpr=nan, lease_expiry_month=60), base(renewal_prob=True, **ok),
            base(cash_rent_start_month=6, **self.NX),                        # stabilized at close: would be ignored
            self._lease_up(gpr=400_000, lease_expiry_month=12),              # expiry inside lease-up
            base(gpr=400_000), base(rollover_cost=5), base(market_rent_ratio=0.9, base_rent=1),  # no expiry
            base(lease_expiry_month=60),                                      # no gpr
            base(gpr=300_000, lease_expiry_month=60),                         # gpr below grossed-up NOI
            base(gpr=333_000, lease_expiry_month=60),                         # implies negative opex (< 333,287)
            base(lease_term_months=12, **ok), base(lease_term_months=14, **ok),   # term <= 12 or <= downtime
            base(market_rent_ratio=0.9, **ok), base(base_rent=1, **ok),           # ratio and base rent go together
            base(market_rent_ratio=0.9, base_rent=500_000, **ok),                 # base rent above gpr
            base(no_lease_expiry_in_hold=True, **ok),                             # contradiction
            self._lease_up(gpr=400_000, lease_expiry_month=26, cash_rent_start_month=24 + 3),
        ]
        for d in cases:
            with self.assertRaises(ValueError, msg=repr(d)):
                solve(d, UST)


class ComponentMode(unittest.TestCase):
    """v4.61 (RE-4.61-3): Mixed-Use Component Lens, property-tax timing and entity tax in the walk solver.
    Fixture = walk_examples/synthetic_dc_mixed_use.json: fictional inputs (two components, DC tax profile, DC UBT).
    The pins below are this solver's own outputs on that fixture (regression locks, 0.5%); the cross-engine
    acceptance against the real deal runs off-repo (test_walk_real_acceptance.py). The Basis leg runs on the synthetic RCT
    table."""
    FIXTURE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "walk_examples", "synthetic_dc_mixed_use.json")
    ENGINE_UST = 0.05

    @classmethod
    def setUpClass(cls):
        from ora_walk import components as C
        cls.C = C
        with open(cls.FIXTURE, encoding="utf-8") as fh:
            cls.spec = json.load(fh)
        cls._cache = {}

    def fd(self, spec):
        """from_dict, citing every departure (tests exercise departures on purpose; the citation requirement
        itself is tested in test_undeclared_departure_rejected)."""
        d = self.C.from_dict(spec)
        try:
            labels = self.C.departure_labels(d)
        except Exception:
            return d
        cites = {**(d.cited_overrides or {}), **{lb: "test" for lb in labels if lb not in (d.cited_overrides or {})}}
        return self.C.replace(d, cited_overrides=cites)

    def deal(self, **kw):
        spec = json.loads(json.dumps(self.spec))
        pt = kw.pop("tax_case", None)
        if pt:
            spec["property_tax"]["case"] = pt
        spec.update(kw)
        return self.fd(spec)

    def solved(self, case):
        if case not in self._cache:
            self._cache[case] = self.C.solve_components(self.deal(tax_case=case), self.ENGINE_UST)
        return self._cache[case]

    def assertWithin(self, got, want, tol, label):
        self.assertLessEqual(abs(got / want - 1), tol, f"{label}: {got:,.0f} vs pin {want:,.0f}")

    # --- regression pins on the synthetic fixture (solver outputs 2026-11-27, UST 5.00%) ---
    def test_fixture_base_tax_a_pinned(self):
        self.assertWithin(self.solved("A")["input_case"]["legs_base"]["irr"], 926_352, 0.005, "Base tax A")

    def test_fixture_downside_tax_a_pinned(self):
        self.assertWithin(self.solved("A")["input_case"]["legs_downside"]["irr"], 600_415, 0.005, "Downside tax A")

    def test_fixture_assessment_holds_pinned(self):
        self.assertWithin(self.solved("C")["input_case"]["legs_base"]["irr"], 546_239, 0.005, "Base tax C")

    def test_fixture_tax_b_pinned(self):
        self.assertWithin(self.solved("B")["input_case"]["legs_base"]["irr"], 750_515, 0.005, "Base tax B")
        self.assertWithin(self.solved("B")["input_case"]["legs_downside"]["irr"], 405_886, 0.005, "Downside tax B (RE-4.61-6)")

    def test_fixture_is_marked_synthetic(self):
        self.assertIs(self.spec.get("_synthetic"), True)

    # --- handoff section 8.6 ---
    def test_component_split_sums_to_building_noi(self):
        d = self.deal()
        for downside in (False, True):
            m = self.C.model(d, 1_000_000, downside)
            for t in range(11):
                total = sum(v[t] for v in m["component_noi"].values())
                self.assertAlmostEqual(total, m["rows"]["noi"][t], places=6)

    def test_downside_never_above_base(self):
        for case in ("A", "B", "C"):
            r = self.solved(case)
            self.assertLessEqual(r["downside_walk"], r["base_walk"] + 0.5, case)
            self.assertEqual(r["binding_walk"], r["downside_walk"], case)
            self.assertAlmostEqual(r["spread"], r["base_walk"] - r["downside_walk"])
            # the Basis leg binds both cases on the synthetic table, so check the legs a stall can move
            for leg in ("yield", "irr"):
                for side in (r, r["input_case"]):
                    self.assertLessEqual(side["legs_downside"][leg], side["legs_base"][leg] + 0.5, (case, leg))

    def test_dc_reset_ty_is_close_ty_plus_one(self):
        from datetime import date
        P = self.C._ptt()
        self.assertEqual(P.dc_reset_ty(date(2027, 1, 1)), 2028)
        self.assertEqual(P.dc_reset_ty(date(2027, 6, 15)), 2028)      # new-owner petition within 45 days
        self.assertEqual(P.dc_reset_ty(date(2027, 9, 30)), 2028)
        self.assertEqual(P.dc_reset_ty(date(2027, 10, 15)), 2029)     # TY2028 already in force at close
        # In the model: a June close still reaches the price in TY2028 (Oct 2027), so model year 1 (Jun 2027 -
        # May 2028) carries 4 months of the seller's base and 8 of the price, not 12 of the seller's base.
        price = 1_400_000
        d = self.deal(close_date="2027-06-01")
        tax, _ = self.C.tax_by_year(d, price)
        rate = 0.0165 + 0.0010
        self.assertAlmostEqual(tax[0], 4 / 12 * 3_200_000 * rate + 8 / 12 * price * rate, places=2)

    def test_tax_line_matches_prop_tax_timing_schedule(self):
        from datetime import date
        P = self.C._ptt()
        for case in ("A", "B", "C", "PW"):
            d = self.deal(tax_case=case)
            tax, _ = self.C.tax_by_year(d, 1_400_000)
            ref = P.schedule(P.Deal("DC", date(2027, 1, 1), 1_400_000, 3_200_000, 3_200_000, addon_rate=0.0010),
                             11, case)
            for t in range(11):
                self.assertAlmostEqual(tax[t], ref[t]["tax"], delta=0.01, msg=f"{case} year {t + 1}")

    def test_dc_tax_y1_is_seller_base_not_price(self):
        tax, fee = self.C.tax_by_year(self.deal(), 1_400_000)
        self.assertAlmostEqual(tax[0], 45_375.0 + 0.75 * 3_200_000 * 0.0010 + 0.25 * 1_400_000 * 0.0010, places=1)
        self.assertGreater(fee[1], 0)            # appeal fee in the reset year
        _, fee_c = self.C.tax_by_year(self.deal(tax_case="C"), 1_400_000)
        self.assertEqual(sum(fee_c), 0)          # no appeal, no fee

    def test_entity_tax_lowers_the_irr_walk(self):
        with_tax = self.solved("A")["input_case"]["legs_base"]["irr"]
        r = self.C.solve_components(self.deal(entity_tax=None), self.ENGINE_UST)
        self.assertGreater(r["input_case"]["legs_base"]["irr"], with_tax)
        self.assertTrue(any("no entity_tax on a DC deal" in f for f in r["flags"]))

    def test_flags(self):
        fa = self.solved("A")["flags"]
        self.assertTrue(any("Tax case A is reported only" in f for f in fa))
        self.assertFalse(any("is reported only: the walk is solved" in f for f in self.solved("B")["flags"]))
        for case in ("A", "B", "C", "PW"):                              # assessment 3.2M > every walk: B governs
            self.assertEqual(self.solved(case)["tax_case"], "B", case)
            self.assertAlmostEqual(self.solved(case)["binding_walk"], self.solved("B")["binding_walk"], delta=1)
        self.assertTrue(any("Retail (L1-L2).renewal_at_contract raises legs" in f and "cited: Synthetic" in f
                            for f in fa))
        self.assertTrue(self.solved("A")["majority_vacant"])            # office 3,000 of 5,000 SF vacant
        self.assertAlmostEqual(self.solved("A")["irr_floor"], 0.125)    # 10.5% + 100 vacant + 100 single tenant

    def test_validation(self):
        bad_comp = json.loads(json.dumps(self.spec))
        bad_comp["components"][1].pop("exit_cap")
        bad_tax = json.loads(json.dumps(self.spec))
        bad_tax["property_tax"]["case"] = "D"
        no_core = json.loads(json.dumps(self.spec))
        no_core["components"][0]["core"] = False
        half_in_place = json.loads(json.dumps(self.spec))
        half_in_place["components"][0].pop("lease_expiry_month")
        for spec in (bad_comp, bad_tax, no_core, half_in_place):
            with self.assertRaises(ValueError):
                self.C.solve_components(self.fd(spec), UST)
        with self.assertRaises(ValueError):
            self.C.from_dict({**self.spec, "bogus": 1})

    # --- adversarial review fixes (2026-11-24) ---
    def _leased(self, **kw):
        """One fully leased core component, flat inputs: a deal with nothing vacant."""
        comp = dict(name="Flex", sf=20_000, use_class="flex", core=True, rent_psf=12, exit_cap=0.075, in_place_rent_monthly=20_000,
                    in_place_bump=0.03, first_bump_month=13, lease_expiry_month=200, renewal_p=0.75,
                    renewal_downtime_m=12)
        comp.update(kw.pop("comp", {}))
        spec = dict(name="leased", market="Columbus OH", state="OH", components=[comp], year_built=1990,
                    single_tenant=True,
                    satellite=False, environmental_heavy_use=False, new_operating_competency=False,
                    property_tax={"profile": "at_price", "rate": 0.02})
        spec.update(kw)
        return self.fd(spec)

    def test_vacancy_floor_every_year(self):
        m = self.C.model(self._leased(), 1_000_000)
        for t in range(11):
            self.assertAlmostEqual(m["rows"]["vacancy"][t], 0.05 * m["rows"]["gpr"][t], places=6)

    def test_stabilization_year_cannot_be_later_than_schedule(self):
        with self.assertRaises(ValueError):
            self.C.solve_components(self._leased(stabilization_year=3), UST)   # fully leased: first full year = 1
        self.assertEqual(self.C.first_full_year(self.deal()), 3)              # office paying from month 15

    def test_core_vacant_lease_up_carry_in_allin(self):
        vac = self._leased(comp=dict(in_place_rent_monthly=None, lease_expiry_month=None, downtime_m=9))
        m = self.C.model(vac, 1_000_000)
        allin = self.C.lease_up_allin(vac, 1_000_000)
        carry = 9 / 12 * m["rows"]["opex"][self.C._stab_year(vac) - 1] / 20_000 * 20_000
        self.assertAlmostEqual(allin, m["allin"] + sum(m["rows"]["lease_up_cost"]) + carry, places=4)
        self.assertGreater(carry, 0)

    def test_basis_fields_validated(self):
        for kw in (dict(adders=["cranes", "cranes"]), dict(adders=["site_work", "paving_lighting"]),
                   dict(year_built=2040), dict(land_flood_cleared="false"), dict(renovation_spend=100_000)):
            with self.assertRaises(ValueError, msg=repr(kw)):
                self.C.solve_components(self._leased(**kw), UST)

    def test_exit_caps_checked_against_market(self):
        r = self.C.solve_components(self._leased(comp=dict(exit_cap=0.05)), UST)
        self.assertTrue(any("LOOSER THAN DOCTRINE" in f and "exit cap 5.00%" in f for f in r["flags"]))
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1]["exit_cap"] = 0.07          # non-core office below the 7.25% Mid-Atlantic cap
        with self.assertRaises(ValueError):
            self.C.solve_components(self.fd(spec), UST)

    def test_looser_inputs_flagged(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1].update(ti_psf=0, lc_pct=0, downtime_m=1, free_m=0, growth=0.05)
        spec.update(reserves_psf=0, credit_loss=0, mgmt_pct=0)
        flags = " | ".join(self.C.solve_components(self.fd(spec), self.ENGINE_UST)["flags"])
        for needle in ("new-lease TI", "new-lease LC", "free rent", "lease-up downtime", "market rent growth",
                       "reserves", "credit loss", "management"):
            self.assertIn(needle, flags)

    def test_renewal_override_measured(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1].update(renewal_p=0.95, renewal_downtime_m=0)
        r = self.C.solve_components(self.fd(spec), self.ENGINE_UST)
        self.assertTrue(any("Office (L3-L4).renewal_downtime_m raises legs" in f for f in r["flags"]))

    def test_office_finish_default_downtime_12(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1].pop("renewal_downtime_m")
        c = self.fd(spec).components[1]
        self.assertEqual(self.C._renewal_defaults(c, [])[1], 12)

    def test_renewal_at_contract_keeps_bump_calendar(self):
        c = self.C.Component(name="R", sf=1000, rent_psf=12, exit_cap=0.075, in_place_rent_monthly=1000,
                             in_place_bump=0.03, first_bump_month=13, lease_expiry_month=66, renewal_p=1.0,
                             renewal_downtime_m=5, renewal_at_contract=True)
        sch = self.C.schedule(c, [])
        self.assertAlmostEqual(sch.rent[66], 1000 * 1.03 ** 5)        # bumps at 13, 25, 37, 49, 61
        self.assertAlmostEqual(sch.rent[67], sch.rent[66])            # no bump at the expiry
        self.assertAlmostEqual(sch.rent[73], 1000 * 1.03 ** 6)        # next anniversary, month 73

    def test_appeal_fee_on_full_bill_saving(self):
        tax, fee = self.C.tax_by_year(self.deal(), 1_400_000)
        hold, a = 3_200_000 * 1.025, 1_400_000
        saving = hold * (0.0165 + 0.0010) - a * (0.0165 + 0.0010)
        self.assertAlmostEqual(fee[1], 0.30 * saving, places=2)

    def test_case_b_flag_only_when_assessment_above_price(self):
        spec = json.loads(json.dumps(self.spec))
        spec["property_tax"].update(current_base=100_000, assessor_value=100_000)   # below every walk here
        r = self.C.solve_components(self.fd(spec), self.ENGINE_UST)
        self.assertEqual(r["tax_case"], "A")                         # assessment below the price: A governs
        self.assertFalse(any("is reported only: the walk is solved" in f for f in r["flags"]))
        spec["property_tax"]["case"] = "C"
        r = self.C.solve_components(self.fd(spec), self.ENGINE_UST)
        self.assertEqual(r["tax_case"], "A")
        self.assertLessEqual(r["binding_walk"], r["input_case"]["downside_walk"] + 0.5)

    def test_entity_tax_fields_validated(self):
        for kw in (dict(improvements_life=0), dict(depr_years=2), dict(minimum=-1e5), dict(exemption=-1)):
            spec = json.loads(json.dumps(self.spec))
            spec["entity_tax"].update(kw)
            with self.assertRaises(ValueError, msg=repr(kw)):
                self.C.solve_components(self.fd(spec), UST)

    def test_capture_below_default_measured(self):
        r = self.C.solve_components(self._leased(comp=dict(rent_psf=6, renewal_capture=0.0, lease_expiry_month=40)),
                                    UST)
        self.assertTrue(any("renewal_capture raises legs" in f for f in r["flags"]))

    def test_property_tax_fields_validated(self):
        for kw in (dict(addon_rate=-0.02), dict(rate=-0.01), dict(rate=0.0), dict(growth=-0.5),
                   dict(appeal_fee_pct=-5), dict(growth="x")):
            spec = json.loads(json.dumps(self.spec))
            spec["property_tax"].update(kw)
            with self.assertRaises(ValueError, msg=repr(kw)):
                self.C.solve_components(self.fd(spec), UST)

    def test_contract_bump_and_missing_costs_flagged(self):
        r = self.C.solve_components(self._leased(comp=dict(contract_bump=0.10)), UST)
        flags = " | ".join(r["flags"])
        self.assertIn("contract bump 10.0%", flags)
        self.assertIn("no insurance modeled", flags)
        self.assertIn("no R&M modeled", flags)

    # --- refute round 3 fixes ---
    def test_dc_flat_rate_rejected(self):
        spec = json.loads(json.dumps(self.spec))
        spec["property_tax"]["rate"] = 0.0177
        with self.assertRaises(ValueError):
            self.C.solve_components(self.fd(spec), UST)

    def test_state_must_match_profile(self):
        spec = json.loads(json.dumps(self.spec))
        spec["property_tax"] = {"profile": "at_price", "rate": 0.0165}
        with self.assertRaises(ValueError):
            self.C.solve_components(self.fd(spec), UST)

    def test_dc_selector_uses_assessor_value(self):
        # high in-force base, low proposed assessment: B (midpoint with the low path) would be looser than A
        spec = json.loads(json.dumps(self.spec))
        spec["property_tax"].update(current_base=3_200_000, assessor_value=150_000)
        r = self.C.solve_components(self.fd(spec), self.ENGINE_UST)
        self.assertEqual(r["tax_case"], "A")

    def test_yield_never_reads_the_seller_bill_year(self):
        # all leased, DC close: Yield reads the first year past the reset TY, never Year 1
        spec = json.loads(json.dumps(self.spec))
        spec["components"] = [spec["components"][0]]
        d = self.fd(spec)
        self.assertEqual(self.C.first_full_year(d), 1)
        self.assertEqual(self.C.tax_reset_year(d), 2)
        self.assertEqual(self.C._stab_year(d), 2)
        oct_close = self.fd({**spec, "close_date": "2027-10-01"})
        self.assertEqual(self.C.tax_reset_year(oct_close), 2)   # TY2028 in force at close; reset TY2029 from Oct 2028

    def test_office_as_core_flagged(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1]["core"] = True
        r = self.C.solve_components(self.fd(spec), self.ENGINE_UST)
        self.assertTrue(any("is office but marked core" in f for f in r["flags"]))

    def test_office_finish_false_is_measured(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1].pop("renewal_downtime_m")
        spec["components"][1]["office_finish"] = False
        r = self.C.solve_components(self.fd(spec), self.ENGINE_UST)
        self.assertTrue(any("Office (L3-L4).office_finish raises legs" in f for f in r["flags"]))

    # --- refute round 4 fixes ---
    def test_stabilization_year_before_reset_rejected(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"] = [spec["components"][0]]                 # all leased: first full year 1, reset year 2
        spec["stabilization_year"] = 1
        with self.assertRaises(ValueError):
            self.C.solve_components(self.fd(spec), UST)

    def test_office_core_flag_ignores_office_finish(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1].update(core=True, office_finish=False)
        flags = self.C.solve_components(self.fd(spec), self.ENGINE_UST)["flags"]
        self.assertTrue(any("is office but marked core" in f for f in flags))
        self.assertTrue(any("Office (L3-L4).core raises legs" in f for f in flags))

    def test_short_lease_term_measured(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1]["lease_term_m"] = 13
        flags = self.C.solve_components(self.fd(spec), self.ENGINE_UST)["flags"]
        self.assertTrue(any("lease_term_m raises legs" in f for f in flags))

    def test_state_required_with_property_tax(self):
        spec = json.loads(json.dumps(self.spec))
        spec.pop("state")
        with self.assertRaises(ValueError):
            self.C.solve_components(self.fd(spec), UST)

    # --- refute round 5 fixes ---
    def test_occ_cap_does_not_shrink_lease_up_allin(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1]["occ_cap"] = 0.45
        d = self.fd(spec)
        self.assertAlmostEqual(self.C.lease_up_allin(d, 1_000_000), self.C.lease_up_allin(self.deal(), 1_000_000),
                               places=4)

    def test_property_tax_defaults_measured(self):
        spec = json.loads(json.dumps(self.spec))
        spec["property_tax"].update(growth=0.0, appeal_fee_pct=0.0)
        flags = self.C.solve_components(self.fd(spec), self.ENGINE_UST)["flags"]
        self.assertTrue(any("property_tax.growth raises legs" in f for f in flags))

    def test_combined_overrides_measured(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1].update(office_finish=False, renewal_downtime_m=5)
        flags = self.C.solve_components(self.fd(spec), self.ENGINE_UST)["flags"]
        self.assertTrue(any("together) raises legs" in f for f in flags))

    def test_dc_without_close_date_and_stab_year_is_a_clean_error(self):
        spec = json.loads(json.dumps(self.spec))
        spec.pop("close_date")
        spec["stabilization_year"] = 3
        with self.assertRaises(ValueError):
            self.C.solve_components(self.fd(spec), UST)

    def test_dc_profile_needs_dc_state_and_ubt(self):
        spec = json.loads(json.dumps(self.spec))
        spec["state"] = "MD"
        with self.assertRaises(ValueError):
            self.C.solve_components(self.fd(spec), UST)
        r = self.C.solve_components(self.deal(entity_tax=None), self.ENGINE_UST)
        self.assertTrue(any("no entity_tax on a DC deal" in f for f in r["flags"]))

    # --- merge gate round 1 (test validity, correctness) ---
    def _land_lifted(self, case="B"):
        """Fixture with a large cleared land credit, so the Basis leg no longer binds and Base != Downside."""
        return self.deal(tax_case=case, market_land_value=5_000_000, land_comp_count=5, land_flood_cleared=True)

    def test_basis_leg_pinned(self):
        r = self.solved("B")
        self.assertAlmostEqual(r["legs_base"]["basis"], 207_535, delta=2)      # synthetic RCT regression pin
        self.assertAlmostEqual(r["binding_walk"], 207_535, delta=2)
        # independent check: the all-in at the Basis-leg price equals the doctrine maximum all-in
        from ora_walk.solver import max_allin_basis, basis_context
        d = self.deal(tax_case="B")
        b = basis_context(self.C._whole_view(d), "Mid-Atlantic", [])
        self.assertAlmostEqual(self.C.lease_up_allin(d, r["legs_base"]["basis"]),
                               max_allin_basis(b["replacement"], b["v_floor"], b["land"]), delta=5)

    def test_downside_binds_when_it_differs(self):
        r = self.C.solve_components(self._land_lifted(), self.ENGINE_UST)
        self.assertLess(r["downside_walk"], r["base_walk"] - 1)
        self.assertEqual(r["binding_walk"], r["downside_walk"])
        self.assertEqual(r["binding_case"], "Downside")

    def test_lease_up_allin_reads_base_case_and_no_noncore_carry(self):
        d = self.deal()
        full = self.C.replace(d, components=[self.C.replace(c, occ_cap=1.0) for c in d.components])
        m = self.C.model(full, 1_000_000, False)
        # office is non-core: no Lease-Up carry; TI/LC on the Base case, never the Downside's capped/cut figures
        self.assertAlmostEqual(self.C.lease_up_allin(d, 1_000_000), m["allin"] + sum(m["rows"]["lease_up_cost"]),
                               places=4)

    def test_renewal_cost_booked_in_expiry_year(self):
        c = self.C.Component(name="R", sf=1000, rent_psf=12, exit_cap=0.075, in_place_rent_monthly=1000,
                             lease_expiry_month=12, renewal_p=1.0, renewal_downtime_m=5)
        years = [y for y, cost, lu in self.C.schedule(c, []).costs if not lu and cost > 0]
        self.assertEqual(years[0], 1)                 # December expiry: cost in year 1, not the renewal's year 2

    def test_each_default_departure_is_measured(self):
        vac = dict(in_place_rent_monthly=None, lease_expiry_month=None, downtime_m=9)
        cases = [
            ("ti_psf", dict(vac, ti_psf=0)), ("lc_pct", dict(vac, lc_pct=0)), ("free_m", dict(vac, free_m=0)),
            ("downtime_m", dict(vac, downtime_m=1)), ("growth", dict(vac, growth=0.05)),
            ("contract_bump", dict(vac, contract_bump=0.08)),
            ("renewal_ti_psf", dict(lease_expiry_month=40, renewal_ti_psf=0)),
            ("renewal_lc_pct", dict(lease_expiry_month=40, renewal_lc_pct=0)),
            ("renewal_downtime_m", dict(lease_expiry_month=40, renewal_downtime_m=0)),
            ("renewal_p", dict(lease_expiry_month=40, renewal_p=0.95)),
        ]
        for key, comp in cases:
            r = self.C.solve_components(self._leased(comp=comp), UST)
            self.assertTrue(any(f"Flex.{key} raises legs" in f for f in r["flags"]), (key, r["flags"]))

    def test_same_override_on_two_components_is_measured(self):
        comps = [dict(name=n, sf=sf, use_class="flex", core=True, rent_psf=12, exit_cap=0.075, downtime_m=12, renewal_p=0.75,
                      renewal_downtime_m=12) for n, sf in (("WH", 20_000), ("WH2", 15_000))]
        comps.append(dict(name="INPL", sf=40_000, use_class="flex", core=True, rent_psf=12, exit_cap=0.075,
                          in_place_rent_monthly=40_000, in_place_bump=0.03, lease_expiry_month=200, renewal_p=0.75,
                          renewal_downtime_m=12))
        spec = dict(name="two-vacant", market="Columbus OH", state="OH", components=comps, year_built=1990,
                    single_tenant=False, satellite=False, environmental_heavy_use=False,
                    new_operating_competency=False, insurance_psf=0.5, rm_psf=0.5,
                    property_tax={"profile": "at_price", "rate": 0.015})
        r = self.C.solve_components(self.fd(spec), 0.03)
        self.assertTrue(any("all overrides together raises legs" in f or "downtime_m raises legs" in f
                            for f in r["flags"]), r["flags"])

    def test_dc_ubt_below_default_measured(self):
        spec = json.loads(json.dumps(self.spec))
        spec.update(market_land_value=5_000_000, land_comp_count=5, land_flood_cleared=True)
        spec["entity_tax"]["rate"] = 0.0
        r = self.C.solve_components(self.fd(spec), self.ENGINE_UST)
        self.assertTrue(any("entity_tax.rate raises legs" in f for f in r["flags"]), r["flags"])

    def test_entity_tax_nol_and_first_year_fraction(self):
        d = self.deal()
        noi = [-50_000.0] + [100_000.0] * 9
        cap = [0.0] * 10
        t = self.C._entity_tax(d, noi, cap, 1_000_000.0, 0.0)
        self.assertEqual(t[0], 250.0)                                   # loss year: minimum tax
        no_nol = self.C._entity_tax(d, [100_000.0] * 10, cap, 1_000_000.0, 0.0)
        self.assertLess(t[1], no_nol[1])                                 # year-1 loss shelters year 2
        jun = self.deal(close_date="2027-06-01")
        self.assertGreater(self.C._entity_tax(jun, [100_000.0] * 10, cap, 1_000_000.0, 0.0)[0],
                           no_nol[0])                                    # mid-month fraction 6.5/12 < 11.5/12

    def test_year11_releasing_cost_comes_off_proceeds(self):
        comp = dict(lease_expiry_month=126, renewal_ti_psf=10)
        m = self.C.model(self._leased(comp=comp), 1_000_000)
        self.assertGreater(m["rows"]["capital"][10], 0)
        gross = m["exit_gross"] * (1 - self._leased(comp=comp).sale_cost_pct)
        self.assertAlmostEqual(m["net_sale"], gross - m["rows"]["capital"][10], places=4)

    def test_cli_labels(self):
        import contextlib
        import io
        import tempfile
        from ora_walk import cli
        spec = dict(name="lbl", market="Columbus OH", state="OH", year_built=1990, single_tenant=True,
                    satellite=False, environmental_heavy_use=False, new_operating_competency=False,
                    property_tax={"profile": "at_price", "rate": 0.02, "case": "C"},
                    components=[dict(name="Flex", sf=20_000, use_class="flex", core=True, rent_psf=12, exit_cap=0.075,
                                     in_place_rent_monthly=20_000, lease_expiry_month=200)])
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
            json.dump(spec, fh)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cli.main([fh.name, "--ust", "0.045"])
        out = buf.getvalue()
        self.assertIn("tax case at_price", out)
        self.assertIn("IRR (no entity tax)", out)

    # --- merge gate round 2 ---
    def test_undeclared_departure_rejected(self):
        spec = json.loads(json.dumps(self.spec))
        spec.pop("cited_overrides")
        with self.assertRaises(ValueError) as cm:
            self.C.solve_components(self.C.from_dict(spec), UST)
        self.assertIn("Office (L3-L4).downtime_m", str(cm.exception))
        spec = json.loads(json.dumps(self.spec))
        spec["cited_overrides"]["credit_loss"] = " "
        with self.assertRaises(ValueError):
            self.C.solve_components(self.C.from_dict(spec), UST)

    def test_depreciation_departures_declared_and_measured(self):
        for kw, label in ((dict(cost_seg_5yr=1.0, cost_seg_15yr=0.0), "entity_tax.cost_seg"),
                          (dict(depr_years=27.5), "entity_tax.depr_years")):
            spec = json.loads(json.dumps(self.spec))
            spec.update(market_land_value=5_000_000, land_comp_count=5, land_flood_cleared=True)
            spec["entity_tax"].update(kw)
            self.assertIn(label, self.C.departure_labels(self.C.from_dict(spec)))
            with self.assertRaises(ValueError):                       # undeclared
                self.C.solve_components(self.C.from_dict(spec), UST)
            r = self.C.solve_components(self.fd(spec), self.ENGINE_UST)
            self.assertTrue(any(f"{label} raises legs" in f for f in r["flags"]), (label, r["flags"]))

    def test_noncore_warehouse_is_a_departure(self):
        d = self._leased(comp=dict(core=False))
        self.assertIn("Flex.core", self.C.departure_labels(self.C.replace(d, cited_overrides={})))

    def test_occ_cap_departure_measured(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1].update(occ_cap=0.45, services_psf=40)
        r = self.C.solve_components(self.fd(spec), self.ENGINE_UST)
        self.assertTrue(any("Office (L3-L4).occ_cap raises legs" in f for f in r["flags"]), r["flags"])

    def test_base_binds_when_downside_is_higher(self):
        spec = json.loads(json.dumps(self.spec))
        spec.update(market_land_value=5_000_000, land_comp_count=5, land_flood_cleared=True)
        spec["components"][1]["services_psf"] = 28
        r = self.C.solve_components(self.fd(spec), self.ENGINE_UST)
        self.assertEqual(r["binding_case"], "Base")
        self.assertEqual(r["binding_walk"], r["base_walk"])
        self.assertTrue(any("Base walk below Downside walk" in f for f in r["flags"]))

    def test_yield_leg_reads_lease_up_allin(self):
        d = self._land_lifted()
        r = self.C.solve_components(d, self.ENGINE_UST)
        y = r["legs_base"]["yield"]
        s = self.C._stab_year(d) - 1
        noi = self.C.model(d, y, False)["rows"]["noi"][s]
        self.assertAlmostEqual(noi, D.YOC_FLOOR * self.C.lease_up_allin(d, y), delta=1.0)

    def test_supplied_stabilization_year_is_read(self):
        comps = [dict(name="WH", sf=20_000, use_class="flex", core=True, rent_psf=12, exit_cap=0.075, downtime_m=12),
                 dict(name="INPL", sf=20_000, use_class="flex", core=True, rent_psf=12, exit_cap=0.075,
                      in_place_rent_monthly=20_000, in_place_bump=0.03, lease_expiry_month=200)]
        base = dict(name="stab", market="Columbus OH", state="OH", components=comps, year_built=1990,
                    single_tenant=False, satellite=False, environmental_heavy_use=False,
                    new_operating_competency=False, insurance_psf=0.5, rm_psf=0.5,
                    property_tax={"profile": "at_price", "rate": 0.015})
        d_none = self.fd(base)
        d_one = self.fd({**base, "stabilization_year": 1})
        self.assertEqual(self.C._stab_year(d_one), 1)
        self.assertGreater(self.C._stab_year(d_none), 1)
        # the carry reads stabilized OpEx at the derived year either way (an earlier year never lowers it)
        self.assertAlmostEqual(self.C.lease_up_allin(d_one, 1_000_000), self.C.lease_up_allin(d_none, 1_000_000),
                               places=4)

    def test_entity_tax_depreciation_terms_pinned(self):
        d = self.deal()
        cap = [0.0] * 10
        base = self.C._entity_tax(d, [100_000.0] * 10, cap, 1_000_000.0, 0.0)
        no_cs = self.C._entity_tax(self.C.replace(d, entity_tax={**d.entity_tax, "cost_seg_5yr": 0.0,
                                                                 "cost_seg_15yr": 0.0}),
                                   [100_000.0] * 10, cap, 1_000_000.0, 0.0)
        self.assertLess(base[0], no_cs[0])                           # cost-seg front-loads depreciation
        # same building basis (all-in minus capex) both ways, so only the capex depreciation can move the tax
        more = self.C._entity_tax(self.C.replace(d, capex=d.capex + 100_000.0), [100_000.0] * 10, cap,
                                  1_100_000.0, 0.0)
        rate = d.entity_tax["rate"]
        self.assertAlmostEqual(base[0] - more[0], rate * 100_000.0 / 15 / 2, places=4)   # year 1: half-year
        self.assertAlmostEqual(base[1] - more[1], rate * 100_000.0 / 15, places=4)       # year 2: full year
        # re-leasing capital depreciates the same way (15-yr SL, half-year)
        capd = self.C._entity_tax(d, [100_000.0] * 10, [0.0, 30_000.0] + [0.0] * 8, 1_000_000.0, 0.0)
        self.assertAlmostEqual(base[1] - capd[1], rate * 30_000.0 / 15 / 2, places=4)
        # R3-T2: the 15-yr MACRS share is depreciated (year 1 = 5% of the 15-yr basis)
        only15 = self.C.replace(d, entity_tax={**d.entity_tax, "cost_seg_5yr": 0.0, "cost_seg_15yr": 0.08})
        none = self.C.replace(d, entity_tax={**d.entity_tax, "cost_seg_5yr": 0.0, "cost_seg_15yr": 0.0})
        t15 = self.C._entity_tax(only15, [100_000.0] * 10, cap, 1_000_000.0, 0.0)
        t0 = self.C._entity_tax(none, [100_000.0] * 10, cap, 1_000_000.0, 0.0)
        b15 = (1_000_000.0 - d.capex) * (1 - d.entity_tax["land_share"]) * 0.08
        dep39_saved = b15 / 39 * (11.5 / 12)                         # the 15-yr share leaves the 39-yr basis
        self.assertAlmostEqual(t0[0] - t15[0], rate * (b15 * 0.05 - dep39_saved), places=4)

    # --- merge gate round 3 ---
    def test_deal_tax_entity_defaults_each_a_departure(self):
        spec = json.loads(json.dumps(self.spec))
        cases = [("credit_loss", lambda s: s.update(credit_loss=0.01)),
                 ("mgmt_pct", lambda s: s.update(mgmt_pct=0.03)),
                 ("reserves_psf", lambda s: s.update(reserves_psf=0.10)),
                 ("expense_growth", lambda s: s.update(expense_growth=0.02)),
                 ("property_tax.growth", lambda s: s["property_tax"].update(growth=0.0)),
                 ("property_tax.appeal_fee_pct", lambda s: s["property_tax"].update(appeal_fee_pct=0.1)),
                 ("entity_tax.improvements_life", lambda s: s["entity_tax"].update(improvements_life=20)),
                 ("entity_tax.depr_years", lambda s: s["entity_tax"].update(depr_years=27.5)),
                 ("entity_tax.rate", lambda s: s["entity_tax"].update(rate=0.05)),
                 ("entity_tax.exemption", lambda s: s["entity_tax"].update(exemption=50_000)),
                 ("entity_tax.minimum", lambda s: s["entity_tax"].update(minimum=0)),
                 ("entity_tax.cost_seg", lambda s: s["entity_tax"].update(cost_seg_5yr=0.15, cost_seg_15yr=0.0)),
                 ("stabilization_year", lambda s: s.update(stabilization_year=2))]
        for label, mutate in cases:
            sp = json.loads(json.dumps(spec))
            sp.update(market_land_value=5_000_000, land_comp_count=5, land_flood_cleared=True)
            mutate(sp)
            sp["cited_overrides"].pop(label, None)          # the fixture cites its own credit_loss departure
            self.assertIn(label, self.C.departure_labels(self.C.from_dict(sp)), label)
            with self.assertRaises(ValueError, msg=label):
                self.C.solve_components(self.C.from_dict(sp), UST)

    def test_looser_deal_level_departures_flagged(self):
        for label, kw in (("credit_loss", dict(credit_loss=0.005)), ("reserves_psf", dict(reserves_psf=0.05))):
            r = self.C.solve_components(self.fd({**json.loads(json.dumps(self.spec)), **kw,
                                                 "market_land_value": 5_000_000, "land_comp_count": 5,
                                                 "land_flood_cleared": True}), self.ENGINE_UST)
            self.assertTrue(any(f"{label} raises legs" in f for f in r["flags"]), (label, r["flags"]))
        for kw, label in ((dict(exemption=50_000), "entity_tax.exemption"),
                          (dict(minimum=0.0), "entity_tax.minimum")):
            sp = json.loads(json.dumps(self.spec))
            sp.update(market_land_value=5_000_000, land_comp_count=5, land_flood_cleared=True)
            sp["entity_tax"].update(kw)
            r = self.C.solve_components(self.fd(sp), self.ENGINE_UST)
            self.assertTrue(any(f"{label} raises legs" in f for f in r["flags"]), (label, r["flags"]))

    def test_cost_seg_default_is_seven_eight(self):
        d = self.deal()
        self.assertNotIn("entity_tax.cost_seg", self.C.departure_labels(d))            # fixture 0.07 / 0.08
        absent = self.C.replace(d, entity_tax={k: v for k, v in d.entity_tax.items()
                                               if k not in ("cost_seg_5yr", "cost_seg_15yr")})
        self.assertNotIn("entity_tax.cost_seg", self.C.departure_labels(absent))       # absent = default
        noi = [150_000.0] * 10
        self.assertEqual(self.C._entity_tax(absent, noi, [0.0] * 10, 1_000_000.0, 0.0),
                         self.C._entity_tax(d, noi, [0.0] * 10, 1_000_000.0, 0.0))        # engine applies 7/8 too
        one = self.C.replace(d, entity_tax={**absent.entity_tax, "cost_seg_5yr": 0.95})    # 15-yr omitted = 0.08
        with self.assertRaises(ValueError):
            self.C.validate(self.C.replace(one, cited_overrides={"entity_tax.cost_seg": "t", **d.cited_overrides}))
        for cs in ((0.08, 0.08), (0.0, 0.20), (0.15, 0.0), (0.0, 0.0), (0.07, 0.20), (0.07, 0.0)):
            other = self.C.replace(d, entity_tax={**d.entity_tax, "cost_seg_5yr": cs[0], "cost_seg_15yr": cs[1]})
            self.assertIn("entity_tax.cost_seg", self.C.departure_labels(other), cs)

    def test_core_default_comes_from_use_class_only(self):
        base = self._leased(comp=dict(in_place_rent_monthly=None, lease_expiry_month=None, downtime_m=9))
        c = base.components[0]
        # office_finish on a warehouse-class component never makes non-core the default
        of = self.C.replace(base, components=[self.C.replace(c, office_finish=True, core=False)])
        self.assertIn("Flex.core", self.C.departure_labels(of))
        # free text mentioning an office never changes the default either
        txt = self.C.replace(base, components=[self.C.replace(c, use="flex warehouse with front office",
                                                               core=False)])
        self.assertIn("Flex.core", self.C.departure_labels(txt))
        ok = self.C.replace(base, components=[self.C.replace(c, use="flex warehouse with front office")])
        self.assertNotIn("Flex.core", self.C.departure_labels(ok))

    def test_office_finish_default_comes_from_use_class_only(self):
        c = self.C.Component(name="WH2", sf=4_000, use="flex warehouse with front office", use_class="flex",
                             core=True, rent_psf=12, exit_cap=0.075, downtime_m=9)
        band = next(v for bound, v in D.ROLLOVER_DOWNTIME_BY_SF if 4_000 < bound)
        self.assertEqual(self.C._renewal_defaults(c, [])[1], band)          # not the 12-month office-finish value
        d = self._leased(comp=dict(use="flex warehouse with front office"))
        self.assertFalse([lb for lb in self.C.departure_labels(d) if lb.endswith(".office_finish")])
        # the departure comparison reads use_class, never the free text, in both directions
        flex_of = self._leased(comp=dict(use="flex warehouse with front office", office_finish=True))
        self.assertIn("Flex.office_finish", self.C.departure_labels(flex_of))
        spec = json.loads(json.dumps(self.spec))
        spec["components"][1].update(use="walk-up suites, full service", office_finish=False)
        spec["components"][1].pop("renewal_downtime_m")
        self.assertIn("Office (L3-L4).office_finish", self.C.departure_labels(self.C.from_dict(spec)))

    def test_use_class_required_and_names_reserved(self):
        spec = json.loads(json.dumps(self.spec))
        spec["components"][0].pop("use_class")
        with self.assertRaises(ValueError):
            self.C.solve_components(self.C.from_dict(spec), UST)
        for bad in ("property_tax", "entity_tax", "credit_loss", "a.b"):
            spec = json.loads(json.dumps(self.spec))
            old = spec["components"][0]["name"]
            spec["components"][0]["name"] = bad
            spec["cited_overrides"] = {k.replace(old, bad, 1): v for k, v in spec["cited_overrides"].items()}
            with self.assertRaisesRegex(ValueError, "reserved", msg=bad):
                self.C.solve_components(self.C.from_dict(spec), UST)
        ok = json.loads(json.dumps(self.spec))                       # control: a plain name with citations passes
        self.C.validate(self.C.from_dict(ok))

    def test_clamp_keeps_a_reference_valid(self):
        # supplied stabilization_year 3 is valid with 12-month downtime; resetting downtime to 9 moves the derived
        # year to 2, so the downtime trial must not read year 3 against its own schedule (clamp)
        comps = [dict(name="WH", sf=20_000, use_class="flex", core=True, rent_psf=12, exit_cap=0.075, downtime_m=12),
                 dict(name="INPL", sf=20_000, use_class="flex", core=True, rent_psf=12, exit_cap=0.075,
                      in_place_rent_monthly=20_000, in_place_bump=0.03, lease_expiry_month=200)]
        spec = dict(name="clamp", market="Columbus OH", state="OH", components=comps, year_built=1990,
                    single_tenant=False, satellite=False, environmental_heavy_use=False,
                    new_operating_competency=False, insurance_psf=0.5, rm_psf=0.5, stabilization_year=3,
                    property_tax={"profile": "at_price", "rate": 0.015})
        d = self.fd(spec)
        ref = [r for lb, r in self.C.departures(d) if lb == "WH.downtime_m"][0]
        self.assertEqual(self.C._min_stab_year(ref), 2)
        r = self.C.solve_components(d, UST)
        down = [f for f in r["flags"] if f.startswith("LOOSER THAN DOCTRINE: WH.downtime_m")]
        self.assertTrue(down, r["flags"])
        self.assertIn("Base yield", down[0])          # measured against the year-2 reference, not year 3

    def test_dc_parcel_null_assessment_is_a_gap(self):
        import dc_parcel_pull as DCP
        attrs = {"SSL": "1234    0056", "PREMISEADD": "X", "CLASSTYPE": "2", "NEWTOTAL": None, "LANDAREA": 1100}
        orig = DCP.get
        DCP.get = lambda url, params, timeout=40: {"features": [{"attributes": attrs, "geometry": {}}]} \
            if "MapServer/40" in url else {"features": []}
        try:
            out = DCP.pull(ssl="1234 0056")
        finally:
            DCP.get = orig
        self.assertIsNone(out["next_bill"]["real_property_tax"])
        self.assertIn("proposed [DATA-GAP]", DCP.to_md(out))

    def test_cli_routes_components(self):
        import contextlib
        import io
        from ora_walk import cli
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = cli.main([self.FIXTURE, "--ust", "0.05", "--json"])
        self.assertEqual(rc, 0)
        out = json.loads(buf.getvalue())
        self.assertIn("binding_walk", out)
        self.assertAlmostEqual(out["binding_walk"], self.solved("A")["binding_walk"], delta=1)



if __name__ == "__main__":
    unittest.main()
