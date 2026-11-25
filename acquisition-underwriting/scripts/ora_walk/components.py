"""Component mode for the ORA walk solver: the Mixed-Use Component Lens (SKILL.md UNDERWRITING CONVENTIONS,
v4.57/v4.58), property-tax timing (property-tax-timing skill, prop_tax_timing.py) and an entity-level tax in the
floor test (DC UBT precedent: 3930 Georgia 2026-11-20, 1500 21st St NW 2026-11-24). Added v4.61 (RE-4.61-3).

One building, split into components (for example ground-floor retail and upper-floor office). Each component
runs its own monthly schedule, expected value over branches:
  * vacant at close: dark for `downtime_m`, then a new lease of `lease_term_m` months whose first `free_m` months
    are occupied but pay no rent; rent = market at lease start, then the contractual bump each lease year;
  * in place: `in_place_rent_monthly` (rent in the close month), bumped by `in_place_bump` every 12 months from
    `first_bump_month`, expiring at `lease_expiry_month` (last month of the lease, months from close);
  * at every expiry inside the 11 modeled years: renewal with probability `renewal_p` (rent = contract bump when
    `renewal_at_contract`, else level + `renewal_capture` x (market - level); doctrine capture 50%), or dark for
    `renewal_downtime_m` and a new lease at market after `free_m` free months. Branches that start in the same
    month merge exactly (revenue is linear in weight and rent level).
Re-leasing cost (TI + LC on total lease consideration) is booked, weighted, in the year the new lease starts.

Building lines: gross potential rent, vacancy = MAX(5% x GPR, modeled downtime and free rent) every year,
credit loss on collected rent, management on EGI. Building costs
(property tax, insurance, R&M, reserves, fixed fees) allocate to components by SF; occupied-services and vacant
carry by component; management by EGI share. Component NOI sums to building NOI exactly.
Below NOI: re-leasing cost and the long-term capital reserve. Exit: year-11 component NOI / component exit cap,
less `sale_cost_pct` (selling cost + transfer tax). All-in at t0: price x (1 + 2% closing + `acquisition_tax_pct`)
+ capex; the Basis and Yield legs add lease-up TI/LC and core lease-up carry (lease_up_allin).

Lens Downside (v4.57/v4.58 defaults, [EST]): every non-core component's occupancy capped at 45% (rent, occupancy and
re-leasing cost scale with it; potential rent does not), market rent -20%, exit cap +100 bps. Base and Downside
are each the lowest of the Basis, Yield and IRR legs; binding = the Downside walk (SKILL.md: "normally the
Downside"); when Base comes out lower, binding = Base and it is flagged.

Pure functions, standard library only (plus the sibling prop_tax_timing.py).
"""
from __future__ import annotations

import importlib.util
import math
import sys
from dataclasses import dataclass, field, asdict, replace
from datetime import date
from pathlib import Path
from typing import Optional

from . import doctrine as D
from .solver import (Deal as _WholeDeal, basis_context, irr, irr_floor, irr_addons, max_allin_basis,
                     normalize_market, npv, _irr_addons, validate as _validate_whole)

MONTHS = 12 * (D.HOLD_YEARS + 1)          # 132: year 11 sets the exit NOI
DOWNSIDE_OCC_CAP = 0.45                   # v4.57 lens Downside defaults, [EST] until the December back-test
DOWNSIDE_RENT_CUT = 0.20
DOWNSIDE_EXIT_CAP_ADD = 0.01
NEW_LEASE_LC = 0.05                       # Lease-Up Block: 5% of total lease consideration
RENEWAL_LC = 0.025                        # v4.33 brokered renewal
CONTRACT_BUMP_MIN = 0.03                  # in-model contractual minimum (SKILL.md Rollover Block (e))
DEFAULT_LEASE_TERM_M = 60
DC_UBT = {"rate": 0.0825, "exemption": 5000.0, "minimum": 250.0}   # D.C. Code 47-1808.03; OTR
OFFICE_FINISH_DOWNTIME_M = 12             # v4.55 (RE-4.55-3) office-finish suite, Base; free rent on top
APPEAL_FEE_DEFAULT = 0.30                # [EST] contingency fee, share of the first-year saving (property-tax-timing)
MACRS_5 = (0.20, 0.32, 0.192, 0.1152, 0.1152, 0.0576)
MACRS_15 = (0.05, 0.095, 0.0855, 0.077, 0.0693, 0.0623, 0.059, 0.059, 0.0591, 0.059, 0.0591, 0.059, 0.0591,
            0.059, 0.0591, 0.0295)


def _ptt():
    """The sibling prop_tax_timing.py (scripts/), loaded by path so the package works from any cwd."""
    mod = sys.modules.get("prop_tax_timing")
    if mod is None:
        path = Path(__file__).resolve().parent.parent / "prop_tax_timing.py"
        spec = importlib.util.spec_from_file_location("prop_tax_timing", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules["prop_tax_timing"] = mod
        spec.loader.exec_module(mod)
    return mod


@dataclass
class Component:
    name: str
    sf: float
    use: str = ""
    use_class: Optional[str] = None       # REQUIRED: office | flex | warehouse | industrial | retail | other.
                                          # Drives the core default (office non-core, every other class core)
                                          # and the office-finish default; free-text `use` is never parsed.
    core: bool = True
    rent_psf: float = 0.0                 # market rent at close, USD/SF/yr (gross or net, consistently with costs)
    growth: float = D.MARKET_RENT_GROWTH  # market rent growth
    downtime_m: Optional[int] = None      # vacant at close: months dark before the lease starts (None = 9, [EST])
    free_m: int = D.LEASE_UP_FREE_MONTHS
    ti_psf: float = D.LEASE_UP_TI_PSF     # new-lease TI
    lc_pct: float = NEW_LEASE_LC          # new-lease LC, % of total consideration
    renewal_p: Optional[float] = None     # None -> Rollover Block (a) by component SF
    renewal_downtime_m: Optional[int] = None   # dark months on non-renewal, free rent on top (None -> (b) by SF)
    exit_cap: Optional[float] = None      # required: component exit cap (per-deal judgment, cite it)
    occ_cap: float = 1.0                  # Base occupancy cap
    lease_term_m: int = DEFAULT_LEASE_TERM_M
    contract_bump: float = CONTRACT_BUMP_MIN
    renewal_ti_psf: float = D.RENEWAL_TI_PSF
    renewal_lc_pct: float = RENEWAL_LC
    renewal_capture: float = D.RENEWAL_CAPTURE
    renewal_at_contract: bool = False     # renewal continues the contract bumps (cite the option terms)
    in_place_rent_monthly: Optional[float] = None
    in_place_bump: float = 0.0
    first_bump_month: int = 13
    lease_expiry_month: Optional[int] = None
    services_psf: float = 0.0             # landlord services on occupied SF, USD/SF/yr (full-service office)
    vacant_carry_psf: float = 0.0         # carry on dark SF, USD/SF/yr
    office_finish: Optional[bool] = None  # finished-office suite (v4.55: 12-month non-renewal downtime);
                                          # None = inferred from `use` containing "office"


@dataclass
class ComponentDeal:
    name: str
    components: list
    ask_price: Optional[float] = None
    market: Optional[str] = None
    close_date: Optional[str] = None      # ISO date; required with a DC/MI property_tax profile
    state: Optional[str] = None           # two-letter jurisdiction; DC and MI must use their own tax profile
    cited_overrides: dict = field(default_factory=dict)   # {departure label: source}: every departure from a
                                          # doctrine default must be declared here with its source (v4.61 gate)
    stabilization_year: Optional[int] = None   # year the Yield leg reads; None = derived from the schedule (first
                                               # year with every vacant-at-close lease paying all 12 months)
    capex: float = 0.0                    # day-1 capital (in all-in)
    acquisition_tax_pct: float = 0.0      # buyer recordation / transfer tax, % of price (on top of 2% closing)
    sale_cost_pct: float = 0.0            # selling cost + seller transfer tax, % of gross exit value
    capital_reserve: float = 0.0          # long-term capital reserve below NOI, USD/yr in year 1 (years 1-10)
    credit_loss: float = D.CREDIT_LOSS_EGI   # % of collected rent (2.0% weak-credit case is per-deal)
    mgmt_pct: float = D.MGMT_FEE_EGI
    insurance_psf: float = 0.0
    rm_psf: float = 0.0
    reserves_psf: float = D.RESERVES_PSF
    fixed_costs: float = 0.0              # other building costs, USD/yr in year 1 (e.g. public-space permits)
    expense_growth: float = D.EXPENSE_GROWTH
    property_tax: Optional[dict] = None   # {profile: DC|MI|at_price, close_date, current_base, assessor_value,
                                          #  case: A|B|C|PW, addon_rate, rate, growth, appeal_fee_pct}
    entity_tax: Optional[dict] = None     # {rate, exemption, minimum, land_share, depr_years, cost_seg_5yr,
                                          #  cost_seg_15yr, improvements_life}
    # building fields for the Basis leg (same meaning as solver.Deal)
    year_built: Optional[int] = None
    renovation_spend: float = 0.0
    renovation_year: Optional[int] = None
    effective_vintage: Optional[int] = None
    construction_type: Optional[str] = None
    adders: tuple = ()
    market_land_value: Optional[float] = None
    land_comp_count: Optional[int] = None
    land_flood_cleared: bool = False
    # IRR add-ons (same meaning as solver.Deal); majority-vacant is derived from components vacant at close
    single_tenant: Optional[bool] = None
    satellite: Optional[bool] = None
    environmental_heavy_use: Optional[bool] = None
    clean_phase_ii: bool = False
    new_operating_competency: Optional[bool] = None

    @property
    def sf(self) -> float:
        return sum(c.sf for c in self.components)


# ---------- validation ----------

def _num(v, name, lo=None, hi=None):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{name} must be a finite number (got {v!r})")
    if lo is not None and v < lo or hi is not None and v > hi:
        raise ValueError(f"{name} must be between {lo} and {hi} (got {v})")


def validate(deal: ComponentDeal) -> None:
    if not deal.components:
        raise ValueError("components: at least one component is required")
    names = [c.name for c in deal.components]
    if len(set(names)) != len(names):
        raise ValueError("component names must be unique")
    reserved = {"property_tax", "entity_tax", "stabilization_year", "all overrides together", *DEAL_DEFAULTS}
    for n in names:
        if not isinstance(n, str) or not n.strip() or "." in n or n in reserved:
            raise ValueError(f"component name {n!r} is reserved or contains '.': departure labels must not collide")
    for c in deal.components:
        if c.use_class not in USE_CLASSES:
            raise ValueError(f"{c.name}.use_class must be one of {sorted(USE_CLASSES)} (got {c.use_class!r}): it sets "
                             "the core and office-finish defaults")
    if not any(c.core for c in deal.components):
        raise ValueError("at least one component must be core (the buy-box use)")
    for c in deal.components:
        _num(c.sf, f"{c.name}.sf", 1)
        _num(c.rent_psf, f"{c.name}.rent_psf", 0)
        _num(c.growth, f"{c.name}.growth", 0, 0.10)
        _num(c.occ_cap, f"{c.name}.occ_cap", 0, 1)
        _num(c.contract_bump, f"{c.name}.contract_bump", 0, 0.10)
        _num(c.renewal_capture, f"{c.name}.renewal_capture", 0, 1)
        for f in ("ti_psf", "lc_pct", "renewal_ti_psf", "renewal_lc_pct", "services_psf", "vacant_carry_psf"):
            _num(getattr(c, f), f"{c.name}.{f}", 0)
        if c.exit_cap is None:
            raise ValueError(f"{c.name}.exit_cap is required (component exit cap, per-deal judgment: cite it)")
        _num(c.exit_cap, f"{c.name}.exit_cap", 0.03, 0.20)
        if c.renewal_p is not None:
            _num(c.renewal_p, f"{c.name}.renewal_p", 0, 1)
        for f in ("downtime_m", "renewal_downtime_m", "lease_expiry_month"):
            v = getattr(c, f)
            if v is not None and (isinstance(v, bool) or not isinstance(v, int) or v < 0):
                raise ValueError(f"{c.name}.{f} must be a non-negative integer month count")
        if not isinstance(c.free_m, int) or c.free_m < 0:
            raise ValueError(f"{c.name}.free_m must be a non-negative integer")
        if not isinstance(c.lease_term_m, int) or c.lease_term_m <= max(12, c.free_m):
            raise ValueError(f"{c.name}.lease_term_m must exceed 12 months and the free rent")
        if (c.in_place_rent_monthly is None) != (c.lease_expiry_month is None):
            raise ValueError(f"{c.name}: in_place_rent_monthly and lease_expiry_month go together (in place), "
                             "or neither (vacant at close)")
        if c.lease_expiry_month is not None and c.lease_expiry_month < 1:
            raise ValueError(f"{c.name}.lease_expiry_month must be >= 1")
        if c.in_place_rent_monthly is not None:
            _num(c.in_place_rent_monthly, f"{c.name}.in_place_rent_monthly", 0)
            _num(c.in_place_bump, f"{c.name}.in_place_bump", 0, 0.10)
            if not isinstance(c.first_bump_month, int) or c.first_bump_month < 1:
                raise ValueError(f"{c.name}.first_bump_month must be a positive integer month")
    if deal.stabilization_year is not None and (isinstance(deal.stabilization_year, bool) or
                                                not isinstance(deal.stabilization_year, int) or
                                                not 1 <= deal.stabilization_year < D.HOLD_YEARS):
        raise ValueError("stabilization_year must be an integer 1-9")
    for f in ("capex", "acquisition_tax_pct", "sale_cost_pct", "capital_reserve", "credit_loss", "mgmt_pct",
              "insurance_psf", "rm_psf", "reserves_psf", "fixed_costs", "expense_growth"):
        _num(getattr(deal, f), f, 0)
    if deal.sale_cost_pct >= 1 or deal.acquisition_tax_pct >= 1:
        raise ValueError("sale_cost_pct and acquisition_tax_pct are decimals < 1")
    if deal.ask_price is not None:
        _num(deal.ask_price, "ask_price", 0)
    if deal.state is not None and (not isinstance(deal.state, str) or len(deal.state) != 2):
        raise ValueError("state must be a two-letter code")
    _validate_whole(_whole_view(deal))      # Basis fields: adders, vintage years, booleans, renovation, land
    for c in deal.components:
        if c.office_finish is not None and not isinstance(c.office_finish, bool):
            raise ValueError(f"{c.name}.office_finish must be true, false or null")
        if not isinstance(c.core, bool) or not isinstance(c.renewal_at_contract, bool):
            raise ValueError(f"{c.name}: core and renewal_at_contract must be true or false")
    ref = D.EXIT_CAPS.get(normalize_market(deal.market) or "", D.DEFAULT_EXIT_CAP)
    for c in deal.components:
        if not c.core and c.exit_cap < ref - 1e-12:
            raise ValueError(f"{c.name}.exit_cap {c.exit_cap:.2%} is below the market's industrial exit cap {ref:.2%}: "
                             "a non-core Base cap is never below it (Mixed-Use Component Lens)")
    pt = deal.property_tax
    if pt is not None:
        prof = pt.get("profile")
        if prof not in ("DC", "MI", "at_price"):
            raise ValueError("property_tax.profile must be DC, MI or at_price")
        if pt.get("case", "A") not in ("A", "B", "C", "PW"):
            raise ValueError("property_tax.case must be A, B, C or PW")
        if prof in ("DC", "MI"):
            for f in ("current_base", "assessor_value"):
                if f not in pt:
                    raise ValueError(f"property_tax.{f} is required for profile {prof}")
                _num(pt[f], f"property_tax.{f}", 0)
            if not (pt.get("close_date") or deal.close_date):
                raise ValueError(f"property_tax profile {prof} needs close_date")
        if prof in ("MI", "at_price") and pt.get("rate") is None:
            raise ValueError(f"property_tax.rate is required for profile {prof}")
        if pt.get("rate") is not None:
            if prof == "DC":
                raise ValueError("property_tax.rate is not allowed for DC: the Class 2 whole-value step applies "
                                 "month by month (prop_tax_timing.dc_rate)")
            _num(pt["rate"], "property_tax.rate", 0.001, 0.10)
        if not isinstance(deal.state, str) or len(deal.state.strip()) != 2 or not deal.state.strip().isalpha():
            raise ValueError("state (two-letter jurisdiction) is required with property_tax: DC and MI must use "
                             "their own profile")
        st = deal.state.strip().upper()
        if (st in ("DC", "MI") or prof in ("DC", "MI")) and prof != st:
            raise ValueError(f"state {st} must use property_tax profile {st} (seller's bill first, reset later), "
                             f"not {prof}")
        _num(pt.get("addon_rate", 0.0), "property_tax.addon_rate", 0, 0.05)
        _num(pt.get("growth", 0.025), "property_tax.growth", 0, 0.10)
        _num(pt.get("appeal_fee_pct", APPEAL_FEE_DEFAULT), "property_tax.appeal_fee_pct", 0, 1)
        unknown = set(pt) - {"profile", "close_date", "current_base", "assessor_value", "case", "addon_rate", "rate",
                             "growth", "appeal_fee_pct"}
        if unknown:
            raise ValueError(f"unknown property_tax fields {sorted(unknown)}")
    if deal.stabilization_year is not None and deal.stabilization_year < tax_reset_year(deal):
        raise ValueError(f"stabilization_year {deal.stabilization_year} is before the tax reset year "
                         f"{tax_reset_year(deal)}: the Yield leg would read NOI billed on the seller's base (looser); "
                         "omit it")
    if deal.stabilization_year is not None and deal.stabilization_year > _min_stab_year(deal):
        raise ValueError(f"stabilization_year {deal.stabilization_year} is later than the schedule's first full-rent, "
                         f"post-reset year {_min_stab_year(deal)}: the Yield leg would read a grown NOI (looser); omit it")
    if not isinstance(deal.cited_overrides, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and v.strip() for k, v in deal.cited_overrides.items()):
        raise ValueError("cited_overrides must map each departure label to a non-empty source string")
    et = deal.entity_tax
    if et is not None:
        unknown = set(et) - {"rate", "exemption", "minimum", "land_share", "depr_years", "cost_seg_5yr",
                             "cost_seg_15yr", "improvements_life"}
        if unknown:
            raise ValueError(f"unknown entity_tax fields {sorted(unknown)}")
        for f in ("rate", "land_share"):
            if f not in et:
                raise ValueError(f"entity_tax.{f} is required")
        _num(et["rate"], "entity_tax.rate", 0, 0.5)
        _num(et["land_share"], "entity_tax.land_share", 0, 1)
        _num(et.get("exemption", 0.0), "entity_tax.exemption", 0)
        _num(et.get("minimum", 0.0), "entity_tax.minimum", 0)
        _num(et.get("depr_years", 39), "entity_tax.depr_years", 27.5, 40)        # shorter lives over-depreciate
        _num(et.get("improvements_life", 15), "entity_tax.improvements_life", 15, 40)
        _num(et.get("cost_seg_5yr", 0.0), "entity_tax.cost_seg_5yr", 0, 1)
        _num(et.get("cost_seg_15yr", 0.0), "entity_tax.cost_seg_15yr", 0, 1)
        if et.get("cost_seg_5yr", 0) + et.get("cost_seg_15yr", 0) > 1:
            raise ValueError("entity_tax cost-seg shares exceed 100%")
    undeclared = [lb for lb in departure_labels(deal) if lb not in deal.cited_overrides]
    if undeclared:
        raise ValueError(f"undeclared departures from doctrine defaults: {undeclared}. Use the default, or add each "
                         "label to cited_overrides with its source (lease, tenant, broker opinion, ruling)")


def _whole_view(deal: ComponentDeal) -> _WholeDeal:
    """The building as a whole-building Deal, for the Basis-field checks and basis_context."""
    return _WholeDeal(
        name=deal.name, sf=deal.sf, stabilized_noi=1.0, market=deal.market, year_built=deal.year_built,
        renovation_spend=deal.renovation_spend, renovation_year=deal.renovation_year,
        effective_vintage=deal.effective_vintage, construction_type=deal.construction_type,
        adders=tuple(deal.adders), market_land_value=deal.market_land_value, land_comp_count=deal.land_comp_count,
        land_flood_cleared=deal.land_flood_cleared, single_tenant=deal.single_tenant, satellite=deal.satellite,
        environmental_heavy_use=deal.environmental_heavy_use, clean_phase_ii=deal.clean_phase_ii,
        new_operating_competency=deal.new_operating_competency, no_lease_expiry_in_hold=True)


def _office_finish(c: Component) -> bool:
    return c.office_finish if c.office_finish is not None else c.use_class == "office"


def first_full_year(deal: ComponentDeal) -> int:
    """First model year in which every component vacant at close pays rent all 12 months (Base schedule)."""
    y = 1
    for c in deal.components:
        if c.lease_expiry_month is None:
            d0 = c.downtime_m if c.downtime_m is not None else D.LEASE_UP_DOWNTIME_MONTHS
            pay = d0 + 1 + c.free_m                  # first paying month
            y = max(y, (pay - 2) // 12 + 2 if pay > 1 else 1)
    return min(y, D.HOLD_YEARS - 1)


# ---------- schedules ----------

def _renewal_defaults(c: Component, flags: list) -> tuple:
    p, dm = c.renewal_p, c.renewal_downtime_m
    if p is None:
        p = next(v for bound, v in D.RENEWAL_PROB_BY_SF if c.sf < bound)
    if dm is None:
        dm = (OFFICE_FINISH_DOWNTIME_M if _office_finish(c)
              else next(v for bound, v in D.ROLLOVER_DOWNTIME_BY_SF if c.sf < bound))
    return p, dm


@dataclass
class _Sched:
    rent: list          # expected collected rent by month (1..MONTHS)
    pot: list           # expected potential rent (lease rent when leased or free, market when dark)
    occ: list           # expected occupied share (leased or free)
    costs: list         # (model year, expected re-leasing cost, is_lease_up)
    vacant_at_close: bool


def schedule(c: Component, flags: list, occ_cap: Optional[float] = None) -> _Sched:
    """Expected-value monthly schedule for one component (see the module docstring)."""
    cap = c.occ_cap if occ_cap is None else occ_cap
    rent, pot, occ = [0.0] * (MONTHS + 1), [0.0] * (MONTHS + 1), [0.0] * (MONTHS + 1)
    costs = []
    p, dm = _renewal_defaults(c, flags)
    mo_mkt = c.rent_psf * c.sf / 12

    def market(m):
        return mo_mkt * (1 + c.growth) ** ((m - 1) / 12)

    def yr(m):
        return (m - 1) // 12 + 1

    pending = {}   # start month -> [weight, rent0 (weight-averaged), free months, bump offset, bump, kind]

    def add_lease(s, w, rent0, free, off, bump, kind):
        if s > MONTHS or w <= 0:
            return
        key = (s, free, off, bump, kind)
        if key in pending:
            w0, r0 = pending[key]
            pending[key] = [w0 + w, (w0 * r0 + w * rent0) / (w0 + w)]
        else:
            pending[key] = [w, rent0]

    def level(rent0, k, off, bump):
        n = 0 if k < off else (k - off) // 12 + 1
        return rent0 * (1 + bump) ** n

    def consideration(rent0, term, off, bump):
        return sum(level(rent0, k, off, bump) for k in range(term))

    vacant = c.lease_expiry_month is None
    if vacant:
        d0 = c.downtime_m if c.downtime_m is not None else D.LEASE_UP_DOWNTIME_MONTHS
        for m in range(1, min(d0, MONTHS) + 1):
            pot[m] += market(m)
        s = d0 + 1
        if s <= MONTHS:
            r0 = market(s)
            costs.append((yr(s), cap * (c.ti_psf * c.sf + c.lc_pct * consideration(r0, c.lease_term_m, 12,
                                                                                   c.contract_bump)), True))
            add_lease(s, 1.0, r0, c.free_m, 12, c.contract_bump, "new")
        first = None
    else:
        first = (1, c.in_place_rent_monthly, c.lease_expiry_month, c.first_bump_month - 1, c.in_place_bump)

    def run(s, w, rent0, free, off, bump, term):
        last = None
        for k in range(term):
            m = s + k
            if m > MONTHS:
                return
            lv = level(rent0, k, off, bump)
            last = lv
            pot[m] += w * lv
            occ[m] += w * cap
            if k >= free:
                rent[m] += w * cap * lv
        e = s + term - 1
        if e >= MONTHS:
            return
        # renewal branch. At contract: the option rent continues the original bump calendar (the anniversary
        # need not fall on the expiry). Otherwise: capture of the gap to market, then the contract bump yearly.
        if c.renewal_at_contract:
            nxt, rb = level(rent0, term, off, bump), bump
            roff = (off - term) % 12 or 12
        else:
            nxt, rb, roff = last + c.renewal_capture * (market(e + 1) - last), c.contract_bump, 12
        # renewal TI/LC is committed before the lease ends: booked in the expiry year (conservative side,
        # as solver._rollover_cost_years)
        costs.append((yr(e), w * p * cap * (c.renewal_ti_psf * c.sf + c.renewal_lc_pct *
                                            consideration(nxt, c.lease_term_m, roff, rb)), False))
        add_lease(e + 1, w * p, nxt, 0, roff, rb, "renewal")
        # non-renewal: dark, then a new lease at market after the free months
        for m in range(e + 1, min(e + dm, MONTHS) + 1):
            pot[m] += w * (1 - p) * market(m)
        s2 = e + dm + 1
        if s2 <= MONTHS:
            r0 = market(s2)
            costs.append((yr(s2), w * (1 - p) * cap * (c.ti_psf * c.sf + c.lc_pct *
                                                       consideration(r0, c.lease_term_m, 12, c.contract_bump)),
                          False))
            add_lease(s2, w * (1 - p), r0, c.free_m, 12, c.contract_bump, "new")

    if first is not None:
        s, r0, term, off, bump = first
        run(s, 1.0, r0, 0, off, bump, term)
    while pending:
        key = min(pending)
        w, r0 = pending.pop(key)
        s, free, off, bump, _ = key
        run(s, w, r0, free, off, bump, c.lease_term_m)
    return _Sched(rent, pot, occ, costs, vacant)


# ---------- property tax and entity tax ----------

def _close(deal: ComponentDeal) -> Optional[date]:
    pt = deal.property_tax or {}
    s = pt.get("close_date") or deal.close_date
    return date.fromisoformat(s) if s else None


def tax_by_year(deal: ComponentDeal, price: float, flags: Optional[list] = None) -> tuple:
    """(annual property tax incl. add-ons for model years 1..11, appeal fee by year). DC/MI use
    prop_tax_timing.base_for month by month (the engine behind prop_tax_timing.schedule(); identical for a
    first-of-month close); at_price taxes the price from Year 1."""
    pt = deal.property_tax
    years = D.HOLD_YEARS + 1
    if pt is None:
        return [0.0] * years, [0.0] * years
    case = pt.get("case", "A")
    g = pt.get("growth", 0.025)
    addon = pt.get("addon_rate", 0.0)
    if pt["profile"] == "at_price":
        return [price * (pt["rate"] + addon) * (1 + g) ** t for t in range(years)], [0.0] * years
    P = _ptt()
    close = _close(deal)
    d = P.Deal(pt["profile"], close, price, pt["current_base"], pt["assessor_value"], rate=pt.get("rate"),
               addon_rate=addon, growth=g)
    tax = [0.0] * years
    for m in range(1, MONTHS + 1):
        idx = close.month - 1 + m - 1
        cy, mo = close.year + idx // 12, idx % 12 + 1
        base = P.base_for(d, cy, mo, case)
        r = d.rate if d.rate is not None else P.dc_rate(base)
        tax[(m - 1) // 12] += base * (r + addon) / 12
    fee = [0.0] * years
    pct = pt.get("appeal_fee_pct", APPEAL_FEE_DEFAULT)
    if case != "C" and pct:
        if pt["profile"] == "DC":
            reset_cy, mo = P.dc_reset_ty(close), 1          # TY T runs Oct T-1..Sep T; month 1 of CY T is in TY T
        else:
            reset_cy, mo = close.year + 1, 1
        def bill(av):   # annual bill on an AV: real property (DC Class 2 step when no flat rate) + add-ons
            return av * ((d.rate if d.rate is not None else P.dc_rate(av)) + addon)
        saving = bill(P.base_for(d, reset_cy, mo, "C")) - bill(P.base_for(d, reset_cy, mo, case))
        t = (reset_cy - close.year) * 12 - (close.month - 1)   # months from close to Jan of the reset CY
        y = max(0, t) // 12 + 1
        if 1 <= y <= years and saving > 0:
            fee[y - 1] = pct * saving
    return tax, fee


def _entity_tax(deal: ComponentDeal, noi: list, capital: list, allin: float, net_sale: float) -> list:
    """Entity tax by year 1..10 (year 10 includes the tax on the sale gain), unlevered. Base = NOI - depreciation
    - exemption; a loss carries forward; minimum tax every year. Depreciation (no bonus): building at
    `depr_years` straight line (mid-month first year), cost-seg 5-yr and 15-yr shares on MACRS half-year, every
    capital item (day-1 capex, re-leasing cost, capital reserve) at `improvements_life` straight line, half-year."""
    et = deal.entity_tax
    if et is None:
        return [0.0] * D.HOLD_YEARS
    rate, ex, mn = et["rate"], et.get("exemption", 0.0), et.get("minimum", 0.0)
    life = et.get("depr_years", 39)
    il = et.get("improvements_life", 15)
    close = _close(deal)
    frac1 = (12 - (close.month if close else 1) + 0.5) / 12
    basis = (allin - deal.capex) * (1 - et["land_share"])
    b5 = basis * et.get("cost_seg_5yr", COST_SEG_DEFAULT[0])
    b15 = basis * et.get("cost_seg_15yr", COST_SEG_DEFAULT[1])
    b39 = basis - b5 - b15
    imps = [capital[t] + (deal.capex if t == 0 else 0.0) for t in range(D.HOLD_YEARS)]
    out, nol, cum = [], 0.0, 0.0
    for t in range(D.HOLD_YEARS):
        dep = b39 / life * (frac1 if t == 0 else 1.0)
        dep += b5 * (MACRS_5[t] if t < len(MACRS_5) else 0.0) + b15 * (MACRS_15[t] if t < len(MACRS_15) else 0.0)
        dep += sum(imps[: t + 1]) / il - imps[t] / (2 * il)
        cum += dep
        base = noi[t] - dep - ex
        if base < 0:
            nol += -base
            tax = mn
        else:
            used = min(nol, base)
            nol -= used
            tax = max(mn, rate * (base - used))
        out.append(tax)
    cost_basis = allin + sum(capital[: D.HOLD_YEARS])
    gain = net_sale - (cost_basis - cum)
    used = min(nol, max(gain, 0.0))
    out[-1] += rate * max(gain - used, 0.0)
    return out


# ---------- cash flows ----------

def _apply_case(deal: ComponentDeal, downside: bool) -> list:
    out = []
    for c in deal.components:
        if downside and not c.core:
            c = replace(c, rent_psf=c.rent_psf * (1 - DOWNSIDE_RENT_CUT), occ_cap=min(c.occ_cap, DOWNSIDE_OCC_CAP),
                        exit_cap=c.exit_cap + DOWNSIDE_EXIT_CAP_ADD)
        out.append(c)
    return out


def model(deal: ComponentDeal, price: float, downside: bool = False, flags: Optional[list] = None) -> dict:
    """Annual building and component lines, years 1..11, and the unlevered cash flows at `price`."""
    flags = [] if flags is None else flags
    comps = _apply_case(deal, downside)
    sch = [schedule(c, flags) for c in comps]
    years = D.HOLD_YEARS + 1
    eg = [(1 + deal.expense_growth) ** t for t in range(years)]
    tax, fee = tax_by_year(deal, price, flags)
    gba = deal.sf
    rows = {k: [0.0] * years for k in ("gpr", "collected", "downtime", "vacancy", "credit", "egi", "tax", "appeal_fee",
                                       "insurance", "rm", "reserves", "fixed", "services", "mgmt", "opex", "noi",
                                       "capital", "lease_up_cost")}
    comp_noi = {c.name: [0.0] * years for c in comps}
    for t in range(years):
        ms = range(12 * t + 1, 12 * t + 13)
        pot_i = [sum(s.pot[m] for m in ms) for s in sch]
        col_i = [sum(s.rent[m] for m in ms) for s in sch]
        occ_i = [sum(s.occ[m] for m in ms) / 12 for s in sch]
        gpr, col = sum(pot_i), sum(col_i)
        down = gpr - col
        vac = max(D.STRUCTURAL_VACANCY * gpr, down)      # every year (SKILL.md Rollover Block vacancy netting)
        credit = deal.credit_loss * col
        egi = gpr - vac - credit
        extra = vac - down
        egi_i = [col_i[i] * (1 - deal.credit_loss) - (extra * pot_i[i] / gpr if gpr else 0.0)
                 for i in range(len(comps))]
        svc_i = [(c.services_psf * c.sf * occ_i[i] + c.vacant_carry_psf * c.sf * (1 - occ_i[i])) * eg[t]
                 for i, c in enumerate(comps)]
        shared = (tax[t] + fee[t] + (deal.insurance_psf + deal.rm_psf + deal.reserves_psf) * gba * eg[t]
                  + deal.fixed_costs * eg[t])
        for i, c in enumerate(comps):
            comp_noi[c.name][t] = egi_i[i] - c.sf / gba * shared - svc_i[i] - deal.mgmt_pct * egi_i[i]
        R = rows
        R["gpr"][t], R["collected"][t], R["downtime"][t], R["vacancy"][t] = gpr, col, down, vac
        R["credit"][t], R["egi"][t], R["tax"][t], R["appeal_fee"][t] = credit, egi, tax[t], fee[t]
        R["insurance"][t] = deal.insurance_psf * gba * eg[t]
        R["rm"][t] = deal.rm_psf * gba * eg[t]
        R["reserves"][t] = deal.reserves_psf * gba * eg[t]
        R["fixed"][t] = deal.fixed_costs * eg[t]
        R["services"][t] = sum(svc_i)
        R["mgmt"][t] = deal.mgmt_pct * egi
        R["opex"][t] = shared + sum(svc_i) + deal.mgmt_pct * egi
        R["noi"][t] = egi - R["opex"][t]
        R["capital"][t] = deal.capital_reserve * eg[t] if t < D.HOLD_YEARS else 0.0
    for s in sch:
        for y, cost, lease_up in s.costs:
            if 1 <= y <= years:
                rows["capital"][y - 1] += cost
                if lease_up:
                    rows["lease_up_cost"][y - 1] += cost
    exit_gross = sum(comp_noi[c.name][D.HOLD_YEARS] / c.exit_cap for c in comps)
    # a year-11 re-leasing cost is a buyer credit off the proceeds (the hold's cash flows never carry it)
    net_sale = exit_gross * (1 - deal.sale_cost_pct) - rows["capital"][D.HOLD_YEARS]
    allin = price * (1 + D.CLOSING_COST + deal.acquisition_tax_pct) + deal.capex
    cf = [-allin] + [rows["noi"][t] - rows["capital"][t] for t in range(D.HOLD_YEARS)]
    cf[-1] += net_sale
    ent = _entity_tax(deal, rows["noi"], rows["capital"], allin, net_sale)
    cf_after = [cf[0]] + [cf[t + 1] - ent[t] for t in range(D.HOLD_YEARS)]
    return {"rows": rows, "component_noi": comp_noi, "exit_gross": exit_gross, "net_sale": net_sale, "allin": allin,
            "cf_pre_tax": cf, "entity_tax": ent, "cf_floor_test": cf_after,
            "components": [asdict(c) for c in comps]}


# ---------- legs and walk ----------

def _bisect(f, lo, hi, tol=0.5):
    """Largest price with f(price) >= 0 for f decreasing; None if f(lo) < 0."""
    if f(lo) < 0:
        return None
    while f(hi) >= 0:
        hi *= 2
        if hi > 1e10:
            raise ValueError("walk search did not bracket: check the inputs")
    for _ in range(200):
        mid = (lo + hi) / 2
        if f(mid) >= 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return lo


def tax_reset_year(deal: ComponentDeal) -> int:
    """First model year whose 12 months all sit in tax years at or after the reset tax year (DC: the TY in force at
    close + 1; MI: the year after the transfer). 1 when no DC/MI profile. The Yield leg never reads a year still
    billed on the seller's base (SKILL.md: never trend the seller's in-place bill)."""
    pt = deal.property_tax
    if pt is None or pt.get("profile") not in ("DC", "MI"):
        return 1
    close = _close(deal)
    reset = _ptt().dc_reset_ty(close) if pt["profile"] == "DC" else close.year + 1
    for t in range(1, D.HOLD_YEARS):
        ok = True
        for m in range(12 * (t - 1) + 1, 12 * t + 1):
            idx = close.month - 1 + m - 1
            cy, mo = close.year + idx // 12, idx % 12 + 1
            ty = (cy + 1 if mo >= 10 else cy) if pt["profile"] == "DC" else cy
            if ty < reset:
                ok = False
                break
        if ok:
            return t
    return D.HOLD_YEARS - 1


def _min_stab_year(deal: ComponentDeal) -> int:
    return min(max(first_full_year(deal), tax_reset_year(deal)), D.HOLD_YEARS - 1)


def _stab_year(deal: ComponentDeal) -> int:
    """Year the Yield leg and the lease-up carry read: the derived year (first full-rent year, never before the tax
    reset), or an earlier supplied year (stricter)."""
    return deal.stabilization_year if deal.stabilization_year is not None else _min_stab_year(deal)


def lease_up_allin(deal: ComponentDeal, price: float) -> float:
    """All-in for the Basis and Yield legs (SKILL.md Lease-Up Assumption Block): price x (1 + closing + transfer)
    + capex + lease-up TI/LC + lease-up carry, carry = downtime months x stabilized OpEx/SF x SF for every CORE
    component vacant at close (a non-core vacant component carries (b) in its cash flow instead). Always read on
    the Base case: a stalled Downside spends less on lease-up and must never pay more for the building."""
    full = replace(deal, components=[replace(c, occ_cap=1.0) for c in deal.components])
    m = model(full, price, False)     # lease-up TI/LC on the whole vacant space, never scaled by an occupancy cap
    # stabilized OpEx = the schedule's first full-rent year, never an earlier supplied year (lower OpEx, looser)
    opex_psf = m["rows"]["opex"][max(_stab_year(deal), _min_stab_year(deal)) - 1] / deal.sf
    carry = sum((c.downtime_m if c.downtime_m is not None else D.LEASE_UP_DOWNTIME_MONTHS) / 12 * opex_psf * c.sf
                for c in deal.components if c.core and c.lease_expiry_month is None)
    return m["allin"] + sum(m["rows"]["lease_up_cost"]) + carry


def _legs(deal: ComponentDeal, downside: bool, r_floor: float, basis: dict) -> dict:
    s = _stab_year(deal) - 1
    basis_allin = max_allin_basis(basis["replacement"], basis["v_floor"], basis["land"])

    def irr_gap(price):
        return npv(r_floor, model(deal, price, downside)["cf_floor_test"])

    def yld_gap(price):
        return model(deal, price, downside)["rows"]["noi"][s] - D.YOC_FLOOR * lease_up_allin(deal, price)

    def basis_gap(price):
        return basis_allin - lease_up_allin(deal, price)

    hi = max(deal.ask_price or 0.0, 1_000_000.0)
    out = {}
    for leg, f in (("basis", basis_gap), ("yield", yld_gap), ("irr", irr_gap)):
        p = _bisect(f, 1.0, hi)
        out[leg] = p if p is not None else 0.0      # no positive price clears this leg: walk 0, flagged
    return out


LOOSE = "LOOSER THAN DOCTRINE"


def _looser_flags(deal: ComponentDeal, market: Optional[str], flags: list) -> None:
    """Inputs below the Lease-Up / Rollover Block and convention defaults are flagged, never assumed away."""
    for c in deal.components:
        vac = c.lease_expiry_month is None
        if c.ti_psf < D.LEASE_UP_TI_PSF:
            flags.append(f"{LOOSE}: {c.name} new-lease TI USD {c.ti_psf:.2f}/SF below the Lease-Up Block USD "
                         f"{D.LEASE_UP_TI_PSF:.2f}/SF: cite a leasing-broker quote")
        if c.lc_pct < NEW_LEASE_LC:
            flags.append(f"{LOOSE}: {c.name} new-lease LC {c.lc_pct:.1%} below the Lease-Up Block 5%")
        if c.free_m < D.LEASE_UP_FREE_MONTHS:
            flags.append(f"{LOOSE}: {c.name} free rent {c.free_m} months below the Lease-Up Block "
                         f"{D.LEASE_UP_FREE_MONTHS}")
        if vac and c.downtime_m is not None and c.downtime_m < D.LEASE_UP_DOWNTIME_MONTHS:
            flags.append(f"{LOOSE}: {c.name} lease-up downtime {c.downtime_m} months below the Lease-Up Block "
                         f"{D.LEASE_UP_DOWNTIME_MONTHS}: cite the marketing history or a broker opinion")
        if vac and c.downtime_m is None:
            flags.append(f"{c.name}: vacant at close, Lease-Up Block default {D.LEASE_UP_DOWNTIME_MONTHS} months "
                         "downtime [EST]")
        if c.growth > D.MARKET_RENT_GROWTH + 1e-12:
            flags.append(f"{LOOSE}: {c.name} market rent growth {c.growth:.2%} above the Base "
                         f"{D.MARKET_RENT_GROWTH:.2%}")
        if c.renewal_ti_psf < D.RENEWAL_TI_PSF:
            flags.append(f"{LOOSE}: {c.name} renewal TI USD {c.renewal_ti_psf:.2f}/SF below USD "
                         f"{D.RENEWAL_TI_PSF:.2f}/SF (renewal economics v4.33)")
        if c.renewal_lc_pct < RENEWAL_LC:
            flags.append(f"{LOOSE}: {c.name} renewal LC {c.renewal_lc_pct:.1%} below 2.5% (brokered renewal, v4.33)")
        if abs(c.renewal_capture - D.RENEWAL_CAPTURE) > 1e-9 or c.renewal_at_contract:
            what = "renewal_at_contract" if c.renewal_at_contract else f"renewal_capture {c.renewal_capture:.0%}"
            flags.append(f"{c.name}: {what} replaces the 50% doctrine capture: cite the option terms (measured "
                         "against the default below)")
        if c.core and c.use_class == "office":
            flags.append(f"{LOOSE}: {c.name} is office but marked core: office, and upper-floor office above all, is "
                         "non-core under the Mixed-Use Component Lens (c) and gets the Downside; cite why it is core")
        if c.lease_term_m != DEFAULT_LEASE_TERM_M:
            flags.append(f"CHECK: {c.name} lease_term_m {c.lease_term_m} months (default {DEFAULT_LEASE_TERM_M}): "
                         "cite the lease or a leasing-broker opinion (measured below)")
        if c.contract_bump > CONTRACT_BUMP_MIN + 1e-12:
            flags.append(f"{LOOSE}: {c.name} contract bump {c.contract_bump:.1%} above the 3% in-model minimum: cite "
                         "the lease abstract (an escalator is never growth)")
        if c.renewal_p is None or c.renewal_downtime_m is None:
            src = "office-finish 12 months (v4.55)" if _office_finish(c) else "the Rollover Block SF band"
            flags.append(f"{c.name}: renewal probability / downtime defaults ({src}; {c.sf:,.0f} SF)")
    if deal.reserves_psf < D.RESERVES_PSF:
        flags.append(f"{LOOSE}: reserves USD {deal.reserves_psf:.2f}/SF below USD {D.RESERVES_PSF:.2f}/SF")
    if deal.credit_loss < D.CREDIT_LOSS_EGI:
        flags.append(f"{LOOSE}: credit loss {deal.credit_loss:.2%} below {D.CREDIT_LOSS_EGI:.2%} (Rollover Block (d))")
    if deal.mgmt_pct < D.MGMT_FEE_EGI:
        flags.append(f"{LOOSE}: management {deal.mgmt_pct:.1%} of EGI below {D.MGMT_FEE_EGI:.0%}")
    for f, label in (("insurance_psf", "insurance"), ("rm_psf", "R&M")):
        if getattr(deal, f) <= 0:
            flags.append(f"{LOOSE}: no {label} modeled ({f} = 0): set it, or state the NNN recovery that covers it")
    if deal.expense_growth < D.EXPENSE_GROWTH:
        flags.append(f"{LOOSE}: expense growth {deal.expense_growth:.1%} below {D.EXPENSE_GROWTH:.0%}")
    ref = D.EXIT_CAPS.get(market or "")
    if ref is None:
        ref = D.DEFAULT_EXIT_CAP
        flags.append(f"Exit cap reference: no market row for '{deal.market}': default {ref:.2%} used to test "
                     "component caps")
    for c in deal.components:
        if c.core and c.exit_cap < ref - 1e-12:
            flags.append(f"{LOOSE}: {c.name} exit cap {c.exit_cap:.2%} below the market exit cap {ref:.2%}: "
                         "per-deal judgment, cite the ruling and the comps")
    flags.append("Component exit caps are per-deal judgment (Mixed-Use Component Lens): cite each")


COMPONENT_DEFAULTS = dict(lease_term_m=DEFAULT_LEASE_TERM_M, renewal_capture=D.RENEWAL_CAPTURE,
                          renewal_at_contract=False, ti_psf=D.LEASE_UP_TI_PSF, lc_pct=NEW_LEASE_LC,
                          free_m=D.LEASE_UP_FREE_MONTHS, growth=D.MARKET_RENT_GROWTH, contract_bump=CONTRACT_BUMP_MIN,
                          renewal_ti_psf=D.RENEWAL_TI_PSF, renewal_lc_pct=RENEWAL_LC, occ_cap=1.0)
DEAL_DEFAULTS = dict(credit_loss=D.CREDIT_LOSS_EGI, mgmt_pct=D.MGMT_FEE_EGI, reserves_psf=D.RESERVES_PSF,
                     expense_growth=D.EXPENSE_GROWTH)
TAX_DEFAULTS = dict(growth=0.025, appeal_fee_pct=APPEAL_FEE_DEFAULT)
ENTITY_DEFAULTS = dict(depr_years=39, improvements_life=15)
COST_SEG_DEFAULT = (0.07, 0.08)   # doctrine DEFAULT allocation, 5-yr 7% / 15-yr 8% (cost-seg-tax-layer);
                                  # used in the entity-tax floor test (Gabriel ruling 2026-11-24)
USE_CLASSES = {"office", "flex", "warehouse", "industrial", "retail", "other"}


def _core_default(c: Component) -> bool:
    """Lens (c): office is non-core; every other declared use class is core. Never inferred from other inputs."""
    return c.use_class != "office"


def departures(deal: ComponentDeal) -> list:
    """Every input that departs from its doctrine default, as (label, deal with that input reset to the default).
    ONE table drives both the citation requirement (validate) and the LOOSER measurement (_override_flags).
    Inputs not in the table are facts (SF, rents, dates, exit caps, assessments) or stricter-only caps."""
    out = []
    for i, c in enumerate(deal.components):
        def put(f, dv, c=c, i=i):
            comps = list(deal.components)
            comps[i] = replace(c, **{f: dv})
            out.append((f"{c.name}.{f}", replace(deal, components=comps)))
        for f, dv in COMPONENT_DEFAULTS.items():
            if getattr(c, f) != dv:
                put(f, dv)
        p_def, dm_def = _renewal_defaults(replace(c, renewal_p=None, renewal_downtime_m=None, office_finish=None), [])
        if c.renewal_p is not None and c.renewal_p != p_def:
            put("renewal_p", None)
        if c.renewal_downtime_m is not None and c.renewal_downtime_m != dm_def:
            put("renewal_downtime_m", None)
        if c.office_finish is not None and c.office_finish != (c.use_class == "office"):
            put("office_finish", None)
        if c.lease_expiry_month is None and c.downtime_m is not None and c.downtime_m != D.LEASE_UP_DOWNTIME_MONTHS:
            put("downtime_m", None)
        if c.core != _core_default(c):                # lens (c): office non-core, buy-box uses core
            put("core", _core_default(c))
    for f, dv in DEAL_DEFAULTS.items():
        if getattr(deal, f) != dv:
            out.append((f, replace(deal, **{f: dv})))
    pt = deal.property_tax
    if pt is not None:
        for f, dv in TAX_DEFAULTS.items():
            if pt.get(f, dv) != dv:
                out.append((f"property_tax.{f}", replace(deal, property_tax={**pt, f: dv})))
    if deal.stabilization_year is not None:
        out.append(("stabilization_year", replace(deal, stabilization_year=None)))
    et = deal.entity_tax
    if et is not None:
        for f, dv in ENTITY_DEFAULTS.items():
            if et.get(f, dv) != dv:
                out.append((f"entity_tax.{f}", replace(deal, entity_tax={**et, f: dv})))
        cs = (et.get("cost_seg_5yr", COST_SEG_DEFAULT[0]), et.get("cost_seg_15yr", COST_SEG_DEFAULT[1]))
        if any(abs(a - b) > 1e-12 for a, b in zip(cs, COST_SEG_DEFAULT)):
            out.append(("entity_tax.cost_seg", replace(deal, entity_tax={**et, "cost_seg_5yr": COST_SEG_DEFAULT[0],
                                                                         "cost_seg_15yr": COST_SEG_DEFAULT[1]})))
        if (deal.state or "").strip().upper() == "DC":
            for f, dv in DC_UBT.items():
                if et.get(f, 0.0) != dv:
                    out.append((f"entity_tax.{f}", replace(deal, entity_tax={**et, f: dv})))
    return out


def departure_labels(deal: ComponentDeal) -> list:
    return [label for label, _ in departures(deal)]


def _all_defaults(deal: ComponentDeal) -> ComponentDeal:
    """Every departure reset at once (each reset applied to the running deal)."""
    ref = deal
    for _ in range(3):                       # resets are independent; a few passes settle office_finish / core
        deps = departures(ref)
        if not deps:
            break
        ref = deps[0][1]
        for label, _d in deps[1:]:
            again = [r for lb, r in departures(ref) if lb == label]
            if again:
                ref = again[0]
    return ref


def _override_flags(deal, r_floor, basis, legs_b, legs_d, flags) -> None:
    """Every departure from a doctrine default (the `departures` table) is measured: one at a time, per component
    together, and all together; reset to the default, both cases re-solved, LOOSER flagged when any leg was higher
    with the input. The direction of most of these depends on market vs in-place rent, so it is measured, never
    assumed. A cited departure is still measured and flagged; the citation is quoted beside it."""
    cites = deal.cited_overrides or {}
    trials = departures(deal)
    for c in deal.components:
        own = [(lb, r) for lb, r in trials if lb.startswith(c.name + ".")]
        if len(own) > 1:                     # inputs that look neutral one at a time can loosen together
            ref = deal
            for lb, _r in own:
                again = [r for l2, r in departures(ref) if l2 == lb]
                if again:
                    ref = again[0]
            trials.append((f"{c.name} ({', '.join(sorted(lb.split('.', 1)[1] for lb, _ in own))} together)", ref))
    every = _all_defaults(deal)
    if len(departures(deal)) > 1 and every != deal:
        trials.append(("all overrides together", every))

    def clamp(ref):   # a reference may not read a stabilization year its own schedule would reject
        if ref.stabilization_year is not None and not (tax_reset_year(ref) <= ref.stabilization_year
                                                       <= _min_stab_year(ref)):
            return replace(ref, stabilization_year=None)
        return ref
    for label, ref in [(lb, clamp(r)) for lb, r in trials]:
        up = []
        for case, legs, downside in (("Base", legs_b, False), ("Downside", legs_d, True)):
            r = _legs(ref, downside, r_floor, basis)
            up += [f"{case} {k} +USD {legs[k] - r[k]:,.0f}" for k in legs if legs[k] > r[k] + 0.5]
        if up:
            cite = f" (cited: {cites[label]})" if label in cites else ""
            flags.append(f"{LOOSE}: {label} raises legs above its doctrine default ({', '.join(up)}){cite}")


def solve_components(deal: ComponentDeal, ust: float) -> dict:
    """Base and Downside lowest-leg walks for a component deal; binding = the Downside walk (lower of the two)."""
    validate(deal)
    if not 0 < ust < 0.20:
        raise ValueError("ust must be a decimal, e.g. 0.0452")
    flags: list = []
    market = normalize_market(deal.market)
    basis = basis_context(_whole_view(deal), market, flags)
    vac_close = sum(c.sf for c in deal.components if c.lease_expiry_month is None)
    mv = vac_close / deal.sf > 0.5
    addons = _irr_addons(deal, market, flags)
    r_floor = irr_floor(ust, mv, **addons)
    if not any(not c.core for c in deal.components):
        flags.append("COMPONENT LENS: no non-core component — Downside equals Base")
    _looser_flags(deal, market, flags)
    derived = _min_stab_year(deal)
    if deal.stabilization_year is not None and deal.stabilization_year < derived:
        flags.append(f"CHECK: stabilization_year {deal.stabilization_year} is before the first full-rent year "
                     f"{derived}: the Yield leg reads a lease-up year (measured below)")
    pt = deal.property_tax
    if pt is None:
        flags.append("LOOSER THAN DOCTRINE: no property_tax input — no property tax modeled")
    if deal.entity_tax is None:
        if (deal.state or "").strip().upper() == "DC":
            flags.append(f"{LOOSE}: no entity_tax on a DC deal: the floor test runs after DC UBT (3930 Georgia / "
                         "1500 21st precedent)")
        else:
            flags.append("No entity_tax: floor test before entity-level tax (state it)")

    def with_case(case):
        return deal if pt is None else replace(deal, property_tax={**pt, "case": case})

    def walks(d):
        lb, ld = _legs(d, False, r_floor, basis), _legs(d, True, r_floor, basis)
        return {"legs_base": lb, "legs_downside": ld, "base_walk": min(lb.values()), "downside_walk": min(ld.values())}

    # The walk is always solved on the GOVERNING tax case; the input case is reported beside it.
    input_case = (pt or {}).get("case", "A") if pt else None
    if pt is None or pt["profile"] == "at_price":
        gov = input_case
        res = walks(deal)
    elif pt["profile"] == "MI":
        gov = "A"
        res = walks(with_case("A"))
    else:   # DC (RE-4.61-6): B where the assessment exceeds the price, else A (stricter when price > assessment)
        res = walks(with_case("B"))
        gov = "B"
        # B = midpoint of the price and the assessor_value path (prop_tax_timing), so B is stricter than A exactly
        # when that assessment exceeds the price: test assessor_value, not the in-force base
        # path C at the reset TY is assessor_value x (1 + growth); B is stricter than A exactly when that exceeds
        # the price, so A governs only when the walk is at or above it
        if pt["assessor_value"] * (1 + pt.get("growth", 0.025)) <= min(res["base_walk"], res["downside_walk"]):
            gov, res = "A", walks(with_case("A"))
    gdeal = with_case(gov) if gov else deal
    if input_case is not None and input_case != gov:
        rep = walks(deal)
        flags.append(f"Tax case {input_case} is reported only: the walk is solved on the governing case {gov} "
                     f"({pt['profile']}: {'B where the assessment exceeds the price, else A (RE-4.61-6)' if pt['profile'] == 'DC' else 'A (doctrine)'}); "
                     f"case {input_case} would give Base USD {rep['base_walk']:,.0f} / Downside USD {rep['downside_walk']:,.0f}")
    else:
        rep = res
    legs_b, legs_d = res["legs_base"], res["legs_downside"]
    _override_flags(gdeal, r_floor, basis, legs_b, legs_d, flags)
    base_walk, down_walk = res["base_walk"], res["downside_walk"]
    binding = down_walk
    if base_walk < down_walk - 0.5:
        binding = base_walk
        flags.append("CHECK: Base walk below Downside walk — the non-core component helps in Downside; binding = Base")
    if binding <= 1.0:
        flags.append("No positive walk price — floors cannot be cleared at any price")
    out = {
        "name": deal.name,
        "binding_walk": binding,
        "base_walk": base_walk,
        "downside_walk": down_walk,
        "spread": base_walk - down_walk,
        "base_binding_leg": min(legs_b, key=legs_b.get),
        "downside_binding_leg": min(legs_d, key=legs_d.get),
        "legs_base": legs_b,
        "legs_downside": legs_d,
        "irr_floor": r_floor,
        "irr_floor_addons": [[k, v] for k, v in irr_addons(mv, **addons)],
        "majority_vacant": mv,
        "tax_case": gov,
        "tax_profile": (pt or {}).get("profile"),
        "entity_tax_modeled": deal.entity_tax is not None,
        "input_tax_case": input_case,
        "input_case": rep,
        "flags": flags,
        "doctrine": "acquisition-underwriting v4.61 component mode / " + D.DOCTRINE_VERSION,
        "binding_case": "Downside" if binding == down_walk else "Base",
    }
    if deal.ask_price:
        m = model(gdeal, deal.ask_price)
        out["ask"] = {"ask_price": deal.ask_price, "gap_to_ask": deal.ask_price - binding,
                      "floor_test_irr_at_ask": irr(m["cf_floor_test"])}
    return out


def from_dict(obj: dict) -> ComponentDeal:
    from dataclasses import fields
    comp_fields = {f.name for f in fields(Component)}
    deal_fields = {f.name for f in fields(ComponentDeal)}
    obj = {k: v for k, v in obj.items() if not k.startswith("_")}
    unknown = set(obj) - deal_fields
    if unknown:
        raise ValueError(f"Unknown component-deal fields: {sorted(unknown)}")
    comps = []
    for c in obj.get("components", []):
        c = {k: v for k, v in c.items() if not k.startswith("_")}
        bad = set(c) - comp_fields
        if bad:
            raise ValueError(f"Unknown component fields: {sorted(bad)}")
        comps.append(Component(**c))
    rest = {k: v for k, v in obj.items() if k != "components"}
    if "adders" in rest:
        rest["adders"] = tuple(rest["adders"])
    return ComponentDeal(components=comps, **rest)
