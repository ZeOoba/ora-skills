"""ORA Walk-Price Solver — deterministic inversion of the STAGE 1 floors.

For one building it solves, in closed form, the highest price that still clears each floor:
  * Basis leg  — all-in <= (1 - vintage floor) x (construction-adjusted RCT LOW x SF + land)
  * Yield leg  — stabilized NOI (net of reserves) / all-in >= 8%
  * IRR leg    — 10-yr unlevered IRR >= max(10%, UST + 550 bps) [+100 bps majority-vacant]
                 (unlevered cash flows do not depend on price, so NPV(r_floor) = 0 solves exactly)
where all-in = price x 1.02 + CapEx + lease-up carry. The walk is the lowest leg; that leg binds.

NOI INPUT BASIS: both NOI inputs must already be net of the vacancy line, credit loss and 4% EGI
management; the solver deducts only reserves. The vacancy line each year is MAX(5% structural,
expected modeled downtime as % of GPR): the 5% is a floor, never added on top. So `stabilized_noi`
nets 5% (or modeled downtime if higher), and `in_place_noi` nets Year-1 MAX(5%, downtime on space
vacant at close + expected downtime on in-place leases expiring in Year 1).
Feeding OM NOI at 100% occupancy overstates every leg. Suite-level rollover is NOT modeled; NOI grows at market Base 2.5%.

Reports the per-property refi governor at the walk (LESSER of 65% LTV and 1.25x DSCR, UST + 200 bps,
25-yr amortization, 1% cost), the 65%-LTV DSCR floor test, and levered IRR (reported only).
Amendment H portfolios: per-building walks summed, the largest premium that keeps blended YoC >= 8%
and portfolio IRR >= its highest floor, and per-building floor flags at the allocated price.

Pure functions, standard library only. Floors are flags, never kills (Ruling 5). Inputs that would
make a walk LOOSER than doctrine raise ValueError rather than pass silently.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import date
from typing import Optional

from . import doctrine as D
from . import rct_table


@dataclass
class Deal:
    name: str
    sf: float
    stabilized_noi: float                 # after vacancy/credit/mgmt, BEFORE reserves; stabilization-year $
    market: Optional[str] = None
    in_place_noi: Optional[float] = None  # Year-1 NOI on the same basis (lease-up deals; needs stabilization_year >= 2)
    stabilization_year: int = 1           # 1 = stabilized at close
    vacant_sf_at_close: Optional[float] = None   # drives the majority-vacant IRR premium
    majority_vacant: Optional[bool] = None       # explicit override; can only ADD the premium
    year_built: Optional[int] = None
    renovation_spend: float = 0.0         # $ total; with renovation_year drives effective vintage (R% rule)
    renovation_year: Optional[int] = None
    effective_vintage: Optional[int] = None      # asserted; can only TIGHTEN (capped at the R%-computed vintage)
    construction_type: Optional[str] = None      # tilt-up|precast|cmu|brick|hybrid|pemb; None = unknown (strictest)
    adders: tuple = ()                    # names from doctrine.ADDERS; only features the subject carries
    land_value: float = 0.0               # Ruling 4: $0 until FEMA determination lands
    capex: float = 0.0
    lease_up_carry: float = 0.0
    ask_price: Optional[float] = None
    exit_cap: Optional[float] = None      # override; flagged if below the market cap
    sale_cost_pct: float = 0.0            # doctrine silent; supply if known
    reserves_psf: float = D.RESERVES_PSF
    noi_growth: float = D.MARKET_RENT_GROWTH


@dataclass
class Result:
    name: str
    walk_price: float
    binding_leg: str
    legs: dict
    floors: dict
    refi: dict
    ask: dict
    flags: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


# ---------- primitives ----------

def vintage_floor(vintage: Optional[int]) -> float:
    """Linear ramp 65% at/below 1995 -> 60% at/above 2005. Unknown vintage -> strictest (65%)."""
    if vintage is None or vintage <= D.BASIS_RAMP_START:
        return D.BASIS_FLOOR_OLD
    if vintage >= D.BASIS_RAMP_END:
        return D.BASIS_FLOOR_NEW
    frac = (vintage - D.BASIS_RAMP_START) / (D.BASIS_RAMP_END - D.BASIS_RAMP_START)
    return D.BASIS_FLOOR_OLD - frac * (D.BASIS_FLOOR_OLD - D.BASIS_FLOOR_NEW)


def irr_floor(ust: float, majority_vacant: bool) -> float:
    base = max(D.IRR_FLOOR_MIN, ust + D.IRR_FLOOR_UST_SPREAD)
    return base + (D.MAJORITY_VACANT_PREMIUM if majority_vacant else 0.0)


def annual_debt_constant(rate: float, years: int = D.REFI_AMORT_YEARS) -> float:
    i, n = rate / 12, years * 12
    if i == 0:
        return 1 / years
    return 12 * i / (1 - (1 + i) ** -n)


def loan_balance(loan: float, rate: float, years_paid: float, amort: int = D.REFI_AMORT_YEARS) -> float:
    i, n, k = rate / 12, amort * 12, round(years_paid * 12)
    if i == 0:
        return loan * (1 - k / n)
    pmt = loan * i / (1 - (1 + i) ** -n)
    return loan * (1 + i) ** k - pmt * ((1 + i) ** k - 1) / i


def npv(rate: float, flows: list) -> float:
    return sum(cf / (1 + rate) ** t for t, cf in enumerate(flows))


def irr(flows: list, lo: float = -0.99, hi: float = 1.0) -> Optional[float]:
    """Bisection IRR; None when no sign change in [lo, hi]."""
    f_lo, f_hi = npv(lo, flows), npv(hi, flows)
    if f_lo * f_hi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        f_mid = npv(mid, flows)
        if f_lo * f_mid <= 0:
            hi = mid
        else:
            lo, f_lo = mid, f_mid
    return (lo + hi) / 2


def normalize_market(market: Optional[str]) -> Optional[str]:
    if market is None:
        return None
    if market in D.RCT_MARKETS or market in D.EXIT_CAPS:
        return market
    return D.MARKET_ALIASES.get(market.strip().lower(), market)


# ---------- validation ----------

def validate(deal: Deal) -> None:
    """Reject inputs that would price a deal looser than doctrine."""
    for f in ("sf", "stabilized_noi", "in_place_noi", "vacant_sf_at_close", "renovation_spend", "land_value",
              "capex", "lease_up_carry", "ask_price", "exit_cap", "sale_cost_pct", "reserves_psf", "noi_growth"):
        v = getattr(deal, f)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)):
            raise ValueError(f"{f} must be a finite number (got {v!r})")
    if deal.sf <= 0:
        raise ValueError("sf must be positive")
    if not 1 <= deal.stabilization_year < D.HOLD_YEARS:
        raise ValueError("stabilization_year must be 1-9 (refi must occur inside the 10-yr hold)")
    if deal.in_place_noi is None and isinstance(deal.stabilization_year, int) and deal.stabilization_year > 1:
        raise ValueError("stabilization_year >= 2 needs in_place_noi (otherwise the lease-up ramp starts at "
                         "full stabilized NOI)")
    if deal.in_place_noi is not None and deal.stabilization_year == 1:
        raise ValueError("in_place_noi given but stabilization_year=1 — set the lease-up year or drop in_place_noi")
    if not isinstance(deal.stabilization_year, int) or isinstance(deal.stabilization_year, bool):
        raise ValueError("stabilization_year must be an integer")
    for f in ("capex", "lease_up_carry", "land_value", "reserves_psf", "sale_cost_pct", "renovation_spend"):
        if getattr(deal, f) < 0:
            raise ValueError(f"{f} cannot be negative")
    if deal.sale_cost_pct >= 1:
        raise ValueError("sale_cost_pct must be a decimal < 1")
    if deal.vacant_sf_at_close is not None and not 0 <= deal.vacant_sf_at_close <= deal.sf:
        raise ValueError("vacant_sf_at_close must be between 0 and sf")
    unknown_adders = set(deal.adders) - set(D.ADDERS)
    if unknown_adders:
        raise ValueError(f"unknown adders {sorted(unknown_adders)}; allowed: {sorted(D.ADDERS)}")
    if len(set(deal.adders)) != len(deal.adders) or D.NON_STACKING_ADDERS <= set(deal.adders):
        raise ValueError("adders may not repeat, and site_work and paving_lighting never stack")
    if deal.construction_type is not None and deal.construction_type.lower() not in {*D.CONSTRUCTION_MULT, "pemb"}:
        raise ValueError(f"unknown construction_type '{deal.construction_type}'")
    if deal.exit_cap is not None and not 0.03 <= deal.exit_cap <= 0.20:
        raise ValueError("exit_cap must be a decimal between 0.03 and 0.20")
    if not 0 <= deal.noi_growth <= 0.10:
        raise ValueError("noi_growth must be a decimal between 0 and 0.10")
    this_year = date.today().year
    for f in ("effective_vintage", "renovation_year", "year_built"):
        v = getattr(deal, f)
        if v is not None and not 1800 <= v <= this_year:
            raise ValueError(f"{f} must be a past year")
    if deal.effective_vintage is not None and deal.year_built is not None and deal.effective_vintage < deal.year_built:
        raise ValueError("effective_vintage cannot precede year_built")
    if deal.renovation_spend > 0 and (deal.renovation_year is None or deal.year_built is None):
        raise ValueError("renovation_spend needs renovation_year and year_built")
    if deal.renovation_year is not None and deal.year_built is not None and deal.renovation_year < deal.year_built:
        raise ValueError("renovation_year cannot precede year_built")


# ---------- deal model ----------

def _construction_mult(deal: Deal, flags: list) -> tuple[float, float]:
    """Returns (multiplier for basis/walk, multiplier for R% denominator)."""
    t = (deal.construction_type or "").lower()
    if t in D.CONSTRUCTION_MULT:
        m = D.CONSTRUCTION_MULT[t]
        return m, m
    tilt = next(m for bound, m in D.PEMB_TILT if deal.sf < bound)
    if t == "pemb":
        if deal.sf > D.MAX_SF_PER_BUILDING:
            flags.append("[EST: outside band] PEMB tilt above 50,000 SF")
        return tilt, tilt
    flags.append("[DATA-GAP: construction type] strictest PEMB multiplier applied (R% at x1.00)")
    return min(tilt, D.UNKNOWN_MULT_CAP), 1.00


def _effective_vintage(deal: Deal, point_psf_r: float, flags: list) -> Optional[float]:
    """R% rule (SKILL.md STAGE 1 renovation effective-vintage rule), continuous (no rounding). An asserted effective_vintage can only tighten:
    it is capped at the vintage the documented renovation spend supports."""
    computed = deal.year_built
    if deal.renovation_spend > 0:
        r = deal.renovation_spend / deal.sf / point_psf_r
        yb, ry = deal.year_built, deal.renovation_year
        if r >= D.RENO_FULL_RESET:
            computed = ry
        elif r >= D.RENO_NO_SHIFT:
            computed = yb + (r - D.RENO_NO_SHIFT) / (D.RENO_FULL_RESET - D.RENO_NO_SHIFT) * (ry - yb)
    if deal.effective_vintage is not None:
        if computed is None or deal.effective_vintage > computed:
            flags.append(f"Asserted effective vintage {deal.effective_vintage} not supported by documented "
                         f"renovation spend (R%) — capped at {computed if computed is not None else 'unknown'}")
            return computed
        return deal.effective_vintage
    return computed


def _exit_cap(deal: Deal, market: Optional[str], flags: list) -> float:
    market_cap = D.EXIT_CAPS.get(market or "")
    if deal.exit_cap is not None:
        ref = market_cap if market_cap is not None else D.DEFAULT_EXIT_CAP
        if deal.exit_cap < ref:
            flags.append(f"Exit cap override {deal.exit_cap:.2%} is BELOW the doctrine cap {ref:.2%} "
                         f"({market or 'default'}) — looser than doctrine")
        elif deal.exit_cap > ref:
            flags.append(f"Exit cap override {deal.exit_cap:.2%} is above the doctrine cap {ref:.2%} — "
                         f"refi and DSCR floor tested at the doctrine cap (stricter)")
        return deal.exit_cap
    if market_cap is None:
        flags.append(f"Exit cap: no market match for '{deal.market}' — default {D.DEFAULT_EXIT_CAP:.2%} used")
        return D.DEFAULT_EXIT_CAP
    return market_cap


def noi_path(deal: Deal, years: int = D.HOLD_YEARS + 1) -> list:
    """NOI net of reserves for years 1..years. Linear lease-up ramp to stabilization, then market growth."""
    s = max(1, deal.stabilization_year)
    start = deal.stabilized_noi if deal.in_place_noi is None else deal.in_place_noi
    out = []
    for t in range(1, years + 1):
        if t >= s:
            gross = deal.stabilized_noi * (1 + deal.noi_growth) ** (t - s)
        else:
            gross = start + (deal.stabilized_noi - start) * (t - 1) / (s - 1)
        reserves = deal.reserves_psf * deal.sf * (1 + D.EXPENSE_GROWTH) ** (t - 1)
        out.append(gross - reserves)
    return out


def _unlevered_pv(deal: Deal, rate: float, cap: float) -> float:
    path = noi_path(deal)
    reversion = path[D.HOLD_YEARS] / cap * (1 - deal.sale_cost_pct)
    flows = [0.0] + path[: D.HOLD_YEARS]
    flows[-1] += reversion
    return npv(rate, flows)


def _price_from_allin(allin: float, deal: Deal) -> float:
    return (allin - deal.capex - deal.lease_up_carry) / (1 + D.CLOSING_COST)


def _allin(price: float, deal: Deal) -> float:
    return price * (1 + D.CLOSING_COST) + deal.capex + deal.lease_up_carry


def _refi(deal: Deal, price: float, ust: float, cap: float) -> dict:
    s = deal.stabilization_year
    path = noi_path(deal)
    stab_noi = path[s - 1]
    rate = ust + D.REFI_SPREAD
    k = annual_debt_constant(rate)
    value = max(0.0, stab_noi / cap)
    loan_ltv = D.PER_PROPERTY_LTV_CEILING * value
    loan_dscr = max(0.0, stab_noi / (D.DSCR_FLOOR * k))
    loan = min(loan_ltv, loan_dscr)
    dscr_at_65 = stab_noi / (loan_ltv * k) if loan_ltv > 0 else None
    net_proceeds = loan * (1 - D.REFI_FINANCING_COST)

    # Levered (reported only): all-cash close, refi at end of stabilization year, payoff at exit.
    flows = [-_allin(price, deal)] + path[: D.HOLD_YEARS]
    flows[s] += net_proceeds
    for t in range(s + 1, D.HOLD_YEARS + 1):
        flows[t] -= loan * k
    flows[-1] += path[D.HOLD_YEARS] / cap * (1 - deal.sale_cost_pct)
    flows[-1] -= loan_balance(loan, rate, D.HOLD_YEARS - s)
    return {
        "refi_rate": rate,
        "debt_constant": k,
        "stabilized_value": value,
        "loan": loan,
        "net_refi_proceeds": net_proceeds,
        "binding_constraint": "n/a (no NOI)" if loan_ltv <= 0 else ("DSCR" if loan_dscr < loan_ltv else "LTV"),
        "dscr_at_65_ltv": dscr_at_65,
        "dscr_floor_pass": dscr_at_65 is not None and dscr_at_65 >= D.DSCR_FLOOR,
        "breakeven_exit_cap": D.PER_PROPERTY_LTV_CEILING * D.DSCR_FLOOR * k,
        "levered_irr_reported": irr(flows) if loan > 0 else None,
    }


def _is_majority_vacant(deal: Deal, flags: list) -> bool:
    derived = None
    if deal.vacant_sf_at_close is not None:
        derived = deal.vacant_sf_at_close / deal.sf > 0.5
    if deal.majority_vacant is False and derived:
        flags.append("majority_vacant=False overridden: vacant_sf_at_close > 50% of SF")
    lease_up = deal.in_place_noi is not None or deal.stabilization_year > 1 or deal.lease_up_carry > 0
    # Only an explicit True (premium applied) silences this; an unverified False does not.
    if derived is None and deal.majority_vacant is not True and lease_up:
        flags.append("[DATA-GAP: vacancy at close] lease-up deal without vacant_sf_at_close — "
                     "majority-vacant +100 bps IRR premium NOT applied; supply it")
    mv = bool(derived) or bool(deal.majority_vacant)
    # SKILL.md Lease-Up Assumption Block (UNDERWRITING CONVENTIONS): a vacant deal must carry its lease-up (downtime, TI, LC)
    # in all-in and in the Year-1 NOI line. Modeling it as stabilized at close prices it looser.
    if mv and deal.stabilization_year == 1:
        flags.append("LOOSER THAN DOCTRINE: majority-vacant at close but modeled as stabilized at close — "
                     "Lease-Up Block (SKILL.md UNDERWRITING CONVENTIONS) not applied; set in_place_noi, stabilization_year >= 2 "
                     "and lease_up_carry")
    if deal.vacant_sf_at_close is not None and deal.vacant_sf_at_close >= deal.sf and deal.lease_up_carry == 0:
        flags.append("LOOSER THAN DOCTRINE: 100% vacant with no lease_up_carry — Lease-Up Block downtime, "
                     "TI and LC (SKILL.md Lease-Up Assumption Block) missing from all-in")
    _lease_up_hardening(deal, flags)
    return mv


def _lease_up_hardening(deal: Deal, flags: list) -> None:
    """Two plausibility checks on lease-up inputs; flags only (a leasing-broker quote can supersede
    the Lease-Up Block defaults, so neither is a hard error)."""
    vac = deal.vacant_sf_at_close
    if vac is None:
        return
    # (1) Token carry: the Block's TI default alone is $8.00/SF on the vacant space; downtime and LC
    # come on top. 100% vacant with zero carry is already flagged above, so it is not repeated.
    ti_floor = D.LEASE_UP_TI_PSF * vac
    fully_vacant_no_carry = vac >= deal.sf and deal.lease_up_carry == 0
    if vac > 0 and deal.lease_up_carry < ti_floor and not fully_vacant_no_carry:
        head = "LOOSER THAN DOCTRINE" if vac >= deal.sf else "CHECK"
        flags.append(f"{head}: lease_up_carry ${deal.lease_up_carry:,.0f} is below the Lease-Up Block TI "
                     f"default alone (${D.LEASE_UP_TI_PSF:.2f}/SF x {vac:,.0f} vacant SF = ${ti_floor:,.0f}); "
                     "downtime and LC come on top — supply a leasing-broker quote or raise the carry")
    # (2) Year-1 NOI above the occupied share of stabilized NOI (SF pro-rata): vacant space would be
    # earning at close, or stabilized NOI is understated. Stabilized NOI already nets the 5% structural
    # vacancy floor, so vacancy up to 5% is priced in: the share is grossed up by 1/(1 - 5%) and capped
    # at stabilized NOI (Year-1 above stabilized still flags). Year-1 NOI is in_place_noi, or stabilized_noi
    # when the deal is modeled as stabilized at close. Either way it loosens the IRR leg.
    year1 = deal.in_place_noi if deal.in_place_noi is not None else deal.stabilized_noi
    source = "in_place_noi" if deal.in_place_noi is not None else "Year-1 NOI (modeled stabilized at close)"
    vac_share = vac / deal.sf
    if vac_share <= D.STRUCTURAL_VACANCY:
        occupied_share = deal.stabilized_noi
    else:
        occupied_share = (1 - vac_share) / (1 - D.STRUCTURAL_VACANCY) * deal.stabilized_noi
    if year1 > occupied_share:
        flags.append(f"CHECK: {source} ${year1:,.0f} exceeds the occupied share of "
                     f"stabilized NOI (${occupied_share:,.0f}; SF pro-rata, vacancy up to 5% structural already priced in) — vacant space earning at "
                     "close or stabilized NOI understated; Year-1 NOI loosens the IRR leg")


def solve(deal: Deal, ust: float, portfolio_mode: bool = False) -> Result:
    """Walk price for one building. `ust` = 10-yr Treasury, FRED DGS10 trailing 30-day average."""
    validate(deal)
    if not 0 < ust < 0.20:
        raise ValueError("ust must be a decimal, e.g. 0.0452")
    flags: list = []
    market = normalize_market(deal.market)
    cap = _exit_cap(deal, market, flags)

    # Private RCT table (rct_table.py): raises RctTableUnavailable, so no walk is produced without it.
    rct_point = rct_table.points(rct_table.current())
    point = rct_point.get(market or "")
    point_r = point  # R% denominator: largest POINT when the market is unknown (smallest vintage shift)
    if point is None:
        flags.append(f"RCT: no row for market '{deal.market}' — cheapest-market fallback (strictest floor)")
        point, point_r = min(rct_point.values()), max(rct_point.values())
    if market in D.DENOMINATOR_SENSITIVE:
        flags.append("DENOMINATOR-SENSITIVE market — local insurance comp or GC quote REQUIRED pre-LOI")
    mult, mult_r = _construction_mult(deal, flags)
    adders_psf = sum(D.ADDERS[a] for a in deal.adders)
    low_psf = D.RCT_LOW_FACTOR * (point * mult + adders_psf)
    vintage = _effective_vintage(deal, point_r * mult_r + adders_psf, flags)
    if vintage is None:
        flags.append("[DATA-GAP: vintage] strictest 65% basis floor applied")
    v_floor = vintage_floor(vintage)
    replacement = low_psf * deal.sf + deal.land_value
    replacement_point = (point * mult + adders_psf) * deal.sf + deal.land_value
    if deal.land_value > 0:
        flags.append("Ruling 4: land credited in the basis test — cite the FEMA determination; "
                     "land is $0 until it lands")
    mv = _is_majority_vacant(deal, flags)
    r_floor = irr_floor(ust, mv)
    if deal.reserves_psf < D.RESERVES_PSF:
        flags.append(f"Reserves ${deal.reserves_psf:.2f}/SF below ORA convention ${D.RESERVES_PSF:.2f}/SF — looser than doctrine")
    if deal.noi_growth > D.MARKET_RENT_GROWTH:
        flags.append(f"NOI growth {deal.noi_growth:.2%} above market Base {D.MARKET_RENT_GROWTH:.2%} — looser than doctrine")

    stab_noi_net = noi_path(deal)[deal.stabilization_year - 1]
    legs = {
        "basis": _price_from_allin((1 - v_floor) * replacement, deal),
        "yield": _price_from_allin(stab_noi_net / D.YOC_FLOOR, deal),
        "irr": _price_from_allin(_unlevered_pv(deal, r_floor, cap), deal),
    }
    binding = min(legs, key=legs.get)
    walk = legs[binding]
    if walk <= 0:
        flags.append("No positive walk price — floors cannot be cleared at any price")

    ask = {}
    if deal.ask_price:
        ask = {
            "ask_price": deal.ask_price,
            "gap_to_ask": deal.ask_price - walk,
            "gap_pct_of_ask": (deal.ask_price - walk) / deal.ask_price,
            "ask_yoc": stab_noi_net / _allin(deal.ask_price, deal),
            "ask_discount_to_replacement": 1 - _allin(deal.ask_price, deal) / replacement,
            "floors_flagged_at_ask": [k for k, v in legs.items() if deal.ask_price > v],
        }
        if not portfolio_mode and not D.SINGLE_PRICE_MIN <= deal.ask_price <= D.SINGLE_PRICE_MAX:
            flags.append("GATE: ask outside $500K–$10M single-asset band")
    if deal.sf >= D.MAX_SF_PER_BUILDING:
        flags.append("GATE: building >= 50,000 SF")
    # SKILL.md STAGE 1 DENOMINATOR-SENSITIVE flag: within ±5 discount-pts of the floor at LOW or POINT, or the
    # floor verdict flips between LOW and POINT -> local replacement verification REQUIRED pre-LOI.
    for label, price in (("walk", walk), ("ask", deal.ask_price)):
        if not price or price <= 0:
            continue
        d_low = 1 - _allin(price, deal) / replacement
        d_point = 1 - _allin(price, deal) / replacement_point
        near = min(abs(d_low - v_floor), abs(d_point - v_floor)) <= D.DENOM_SENSITIVE_BAND
        # Kept because doctrine states it. With LOW = 0.90 x POINT the two discounts differ by
        # 0.111 x (1 - d_point), about 3.3 pts near a 60-65% floor, so any flip is already "near".
        flips = (d_low >= v_floor) != (d_point >= v_floor)
        if near or flips:
            flags.append(f"DENOMINATOR-SENSITIVE at {label}: discount {d_low:.1%} (LOW) / {d_point:.1%} (POINT) "
                         f"vs floor {v_floor:.1%} — local insurance comp or GC quote REQUIRED pre-LOI")

    # DSCR at 65% LTV = cap / (0.65 k): a higher cap raises it, so the refi block never uses a cap above
    # the doctrine cap (an override above it would turn a DSCR floor breach into a pass).
    doctrine_cap = D.EXIT_CAPS.get(market or "", D.DEFAULT_EXIT_CAP)
    refi = _refi(deal, max(walk, 0.0), ust, min(cap, doctrine_cap))
    if not refi["dscr_floor_pass"]:
        flags.append("FLOOR-FLAGGED: DSCR at 65% LTV < 1.25x (DSCR binds the refi)")
    return Result(
        name=deal.name, walk_price=walk, binding_leg=binding, legs=legs,
        floors={
            "market": market, "vintage_used": vintage, "basis_floor_pct": v_floor,
            "construction_multiplier": mult, "adders_psf": adders_psf, "rct_point_psf": point,
            "rct_low_psf_adjusted": low_psf,
            "replacement_total": replacement, "yoc_floor": D.YOC_FLOOR, "irr_floor": r_floor,
            "majority_vacant": mv, "ust": ust, "exit_cap": cap, "noi_growth": deal.noi_growth,
            "stabilized_noi_net": stab_noi_net, "doctrine": D.DOCTRINE_VERSION,
        },
        refi=refi, ask=ask, flags=flags,
    )


def solve_portfolio(deals: list, ust: float, portfolio_ask: Optional[float] = None) -> dict:
    """Amendment H: 2-5 buildings, <= $15M. Base price = sum of walks; premium only if blended
    YoC >= 8% AND portfolio unlevered IRR >= the highest building floor still clear. Each building
    is then floor-tested at its allocated price (walk + pro-rata premium share); breaches flag."""
    results = [solve(d, ust, portfolio_mode=True) for d in deals]
    base = sum(r.walk_price for r in results)
    hi_floor = max(r.floors["irr_floor"] for r in results)
    fixed = sum(d.capex + d.lease_up_carry for d in deals)
    noi = sum(r.floors["stabilized_noi_net"] for r in results)
    pv = sum(_unlevered_pv(d, hi_floor, r.floors["exit_cap"]) for d, r in zip(deals, results))
    cap_yield = (noi / D.YOC_FLOOR - fixed) / (1 + D.CLOSING_COST)
    cap_irr = (pv - fixed) / (1 + D.CLOSING_COST)
    walk = max(base, min(cap_yield, cap_irr))
    premium = walk - base

    flags = [f"{r.name}: {f}" for r in results for f in r.flags]
    # SKILL.md STAGE 1 Portfolios allocation priority: (1) stabilized NOI share when every building has credible positive NOI and none is
    # vacant; otherwise (2) replacement-cost-weighted GBA (SF x construction-adjusted POINT). An unknown
    # type uses (2) at the strictest multiplier, so (3) raw GBA never applies here.
    # "a vacant building in a leased portfolio is always allocated by (2)": majority-vacant, or no
    # in-place income at close, counts as vacant here.
    use_noi = all(r.floors["stabilized_noi_net"] > 0 and not r.floors["majority_vacant"]
                  and not (d.in_place_noi is not None and d.in_place_noi <= 0)
                  for d, r in zip(deals, results))
    if use_noi:
        method = "(1) stabilized NOI share"
        weights = [r.floors["stabilized_noi_net"] for r in results]
    else:
        method = "(2) replacement-cost-weighted GBA"
        weights = [d.sf * (r.floors["rct_point_psf"] * r.floors["construction_multiplier"] + r.floors["adders_psf"])
                   for d, r in zip(deals, results)]
    total_w = sum(weights)
    if base <= 0 and premium > 0:
        flags.append("Sum of walks <= 0: premium is most of the price; each building tested at its allocated share")
    allocation = []
    for r, w in zip(results, weights):
        share = premium * w / total_w
        price = r.walk_price + share
        breached = [k for k, v in r.legs.items() if price > v + 1e-6]
        allocation.append({"name": r.name, "walk": r.walk_price, "premium_share": share,
                           "allocated_price": price, "floors_breached": breached})
        if breached:
            flags.append(f"FLOOR-FLAGGED: {r.name} breaches {', '.join(breached)} at allocated price ${price:,.0f}")
    if not D.PORTFOLIO_MIN_BLDGS <= len(deals) <= D.PORTFOLIO_MAX_BLDGS:
        flags.append("GATE: Amendment H scope is 2–5 buildings")
    if walk > D.PORTFOLIO_PRICE_MAX:
        flags.append("GATE: portfolio walk > $15M")
    out = {
        "buildings": [r.to_dict() for r in results],
        "sum_of_walks": base,
        "portfolio_irr_floor": hi_floor,
        "max_price_blended_yoc": cap_yield,
        "max_price_portfolio_irr": cap_irr,
        "max_premium_over_sum": premium,
        "portfolio_walk_price": walk,
        "allocation_method": method,
        "allocation": allocation,
        "flags": flags,
    }
    if portfolio_ask is not None:
        out["portfolio_ask"] = portfolio_ask
        out["gap_to_ask"] = portfolio_ask - walk
        if portfolio_ask > D.PORTFOLIO_PRICE_MAX:
            flags.append("GATE: portfolio ask > $15M")
    return out
