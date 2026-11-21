"""ora_mf_debt v1.0 (2026-11-20) — reusable fully-amortizing agency / HUD debt scenarios for ORA multifamily underwrites.

First used on a 2026-11-20 DC multifamily underwrite. Deal-agnostic: the caller supplies NOI, cash flow, all-in basis,
net sale and an optional entity-tax hook; this module supplies loan terms, sizing, schedules, levered cash flows and a
formula-driven openpyxl block.

Status: INFORMATIONAL. The doctrine refi (terms in ora_walk/doctrine.py) stays the gating levered case; these scenarios sit beside it and never move a floor. The DOCTRINE_REFI preset reads its
constants from ora_walk.doctrine (single home for governor constants); this module never changes them.

Rates are UST-linked spreads [EST] calibrated to Northmarq's 11/18/2026 indications (HUD 6.30-6.80%; UST 4.9955%).
Re-quote before relying on them; structural terms (amortization, MIP, LTV/DSCR, occupancy) are program rules.

Stdlib only (no numpy_financial): _pmt is the closed-form level payment and _irr a bisection solver, so the module runs
in CI, which installs only openpyxl and the document libraries. openpyxl is needed only by write_loan_block.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ora_walk import doctrine as _D  # noqa: E402

PRESETS = {
    "HUD_223F": dict(
        label="HUD 223(f) — 35-yr fixed, fully amortizing, non-recourse",
        short="HUD 223(f) 35/35", amort=35, spread=0.0155, mip=0.0025,
        upfront_pct=0.0025 + 0.0030 + 0.0100,      # upfront MIP + HUD application fee + lender fee
        fixed=25_000,                             # third-party reports [EST]
        max_ltv_purchase=0.85, max_ltv_cashout=0.80, min_dscr=1.15,
        prepay=[0.10, 0.09, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01],   # 10-to-1 declining by loan year [EST; negotiable]
        eligibility="Stable >=85% occupancy; commercial <=25% NRA / 20% EGI; HUD-approved management agent; "
                    "Regulatory Agreement (surplus-cash distributions, audited financials); assumable; 4-6 month close.",
        rate_source="Northmarq 11/18/2026: 6.30-6.80% note rate; MIP 0.25% upfront / 0.25% annual (HUD FR-6522-N-02)"),
    "FNMA_SML_30": dict(
        label="Fannie Mae Small Mortgage Loan — 30-yr fixed, fully amortizing, non-recourse",
        short="Fannie Small 30/30", amort=30, spread=0.0210, mip=0.0,
        upfront_pct=0.0100, fixed=20_000,
        max_ltv_purchase=0.80, max_ltv_cashout=0.80, min_dscr=1.25,
        prepay=[0.05, 0.04, 0.03, 0.02, 0.01, 0.01, 0.01, 0.01, 0.01, 0.01],   # graduated option [EST]; yield maintenance costs far more
        eligibility="90% occupancy for 90 days; net worth >= loan; ~9 months P&I liquidity; loans up to ~USD 9M.",
        rate_source="[EST] 6.9-7.3% for 30-yr fully amortizing small loans (Nov-2026)"),
    "DOCTRINE_REFI": dict(
        label=(f"ORA doctrine refi — 10-yr UST + {round(_D.REFI_SPREAD * 1e4)} bp, "
               f"{_D.REFI_AMORT_YEARS}-yr amortization, 5-yr balloon"),
        short="Doctrine refi", amort=_D.REFI_AMORT_YEARS, spread=_D.REFI_SPREAD, mip=0.0,
        upfront_pct=_D.REFI_FINANCING_COST, fixed=0,
        max_ltv_purchase=_D.PER_PROPERTY_LTV_CEILING, max_ltv_cashout=_D.PER_PROPERTY_LTV_CEILING,
        min_dscr=_D.DSCR_FLOOR, prepay=[0.0] * 10,
        eligibility="Gating levered case (acquisition-underwriting v4.37).", rate_source="Doctrine v4.37"),
}


def _pmt(rate_m, n, pv):
    """Level payment per period for a fully amortizing loan of pv (positive result; npf.pmt sign flipped)."""
    if rate_m == 0:
        return pv / n
    return pv * rate_m / (1 - (1 + rate_m) ** (-n))


def _npv(rate, flows):
    return sum(f / (1 + rate) ** t for t, f in enumerate(flows))


# Rate grid for the IRR root scan: just above -100%, 1% steps to +100%, then doubling to ~1e4 (1,000,000%).
_IRR_GRID = ([-0.999999, -0.9999, -0.999] + [round(-0.99 + 0.01 * i, 10) for i in range(200)]
             + [2.0 ** j for j in range(0, 15)])


def _npv_safe(rate, flows):
    try:
        return _npv(rate, flows)
    except (ZeroDivisionError, OverflowError):
        return None


def sign_changes(flows):
    """Sign changes in a cash-flow series (zeros ignored). More than one = non-conventional: several IRRs may exist."""
    s = [f > 0 for f in flows if f != 0]
    return sum(1 for a, b in zip(s, s[1:]) if a != b)


def _irr(flows):
    """IRR by grid scan + bisection over every root bracketed by a sign change on the grid [-99.9999%, 1,638,400%];
    returns the closest-to-zero bracketed root (numpy_financial.irr's rule), or None when NPV never changes sign.
    Conventional flows (one sign change) have one root, so the answer is unique and ties to numpy_financial. For
    non-conventional flows, two roots inside one grid cell are not bracketed and can be missed, so the result may be
    a different root or None; levered() flags such flows NON-CONVENTIONAL."""
    pts = [(r, _npv_safe(r, flows)) for r in _IRR_GRID]
    pts = [(r, v) for r, v in pts if v is not None]
    roots = []
    for (lo, f_lo), (hi, f_hi) in zip(pts, pts[1:]):
        if f_lo == 0:
            roots.append(lo); continue
        if f_lo * f_hi > 0:
            continue
        for _ in range(200):
            mid = (lo + hi) / 2
            f_mid = _npv(mid, flows)
            if f_lo * f_mid <= 0:
                hi = mid
            else:
                lo, f_lo = mid, f_mid
        roots.append((lo + hi) / 2)
    if pts and pts[-1][1] == 0:
        roots.append(pts[-1][0])
    return min(roots, key=abs) if roots else None


def terms(preset_key, ust, loan, **override):
    """Resolve a preset into concrete terms: rate = UST + spread unless rate= is given."""
    p = dict(PRESETS[preset_key]); p.update(override)
    p["rate"] = override.get("rate", ust + p["spread"]); p["loan"] = loan
    return p


def balance(loan, rate, amort, years):
    i = rate / 12; n = years * 12
    if i == 0:
        return max(0.0, loan * (1 - n / (amort * 12)))
    pm = loan * i / (1 - (1 + i) ** (-amort * 12))
    return max(0.0, loan * (1 + i) ** n - pm * ((1 + i) ** n - 1) / i)


def loan_year(loan, rate, amort, mip, k):
    """Debt service for loan year k (1-based)."""
    pmt = _pmt(rate / 12, amort * 12, loan) * 12
    b0, b1 = balance(loan, rate, amort, k - 1), balance(loan, rate, amort, k)
    prin = b0 - b1; m = mip * (b0 + b1) / 2
    return dict(b0=b0, b1=b1, principal=prin, interest=pmt - prin, mip=m, ds=pmt + m)


def constant(rate, amort, mip=0.0):
    return _pmt(rate / 12, amort * 12, 1) * 12 + mip


def size_loan(noi, value, t, cashout=True):
    """Lesser of LTV and DSCR proceeds; DSCR constant includes annual MIP."""
    ltv = t["max_ltv_cashout" if cashout else "max_ltv_purchase"] * value
    dscr = noi / (t["min_dscr"] * constant(t["rate"], t["amort"], t["mip"]))
    return dict(loan=min(ltv, dscr), ltv_loan=ltv, dscr_loan=dscr, binds="LTV" if ltv <= dscr else "DSCR")


def _check_years(fund_year, exit_year, n):
    if not 0 <= fund_year < exit_year <= n:
        raise ValueError(f"need 0 <= fund_year ({fund_year}) < exit_year ({exit_year}) <= model years ({n})")


def levered(noi, cfbu, allin, net_sale, t, fund_year=1, exit_year=None, tax_fn=None):
    """noi, cfbu: lists for model years 1..N. Loan funds at the END of fund_year (0 = at close).
    tax_fn(y, deductible_interest_and_mip) -> entity tax for year y. Returns IRR, cash flows, DSCRs."""
    if exit_year is None:
        exit_year = len(cfbu)
    _check_years(fund_year, exit_year, len(cfbu))
    if exit_year - fund_year > t["amort"]:
        raise ValueError(f"loan years to exit ({exit_year - fund_year}) exceed amortization ({t['amort']}): the loan "
                         "is paid off before exit; model the debt-free years separately")
    loan = t["loan"]; cf = [-allin + (loan * (1 - t["upfront_pct"]) - t["fixed"] if fund_year == 0 else 0)]
    dscr = []
    for y in range(1, exit_year + 1):
        c = cfbu[y - 1]; ded = 0.0; k = y - fund_year
        if y == fund_year: c += loan * (1 - t["upfront_pct"]) - t["fixed"]
        if k >= 1:
            d = loan_year(loan, t["rate"], t["amort"], t["mip"], k); c -= d["ds"]; ded = d["interest"] + d["mip"]
            dscr.append(noi[y - 1] / d["ds"] if d["ds"] else float("inf"))
        if tax_fn: c -= tax_fn(y, ded)
        if y == exit_year:
            kk = exit_year - fund_year
            pp = t["prepay"][kk - 1] if 1 <= kk <= len(t["prepay"]) else 0.0
            c += net_sale - balance(loan, t["rate"], t["amort"], kk) * (1 + pp)
        cf.append(c)
    # Equity multiple is undefined when loan proceeds at close cover the basis (no equity in): None, not a sign flip.
    # irr_flag: NON-CONVENTIONAL when the flows change sign more than once (e.g. a cash-out at close followed by
    # negative carry); the IRR is then the root closest to zero and may differ from Excel's guess-seeded IRR.
    return dict(irr=_irr(cf), cf=cf, dscr=dscr, em=sum(cf[1:]) / -cf[0] if cf[0] < 0 else None,
                irr_flag="NON-CONVENTIONAL" if sign_changes(cf) > 1 else "")


def _after_tax_unlevered(allin, cfbu, net_sale, t, exemption, land_share):
    """After-tax unlevered flows with the real MAX(0, .) tax terms; straight-line 27.5-yr depreciation on improvements.
    Returns (flows, any_year_tax_zero)."""
    k = (1 - land_share) / 27.5; n = len(cfbu); zero = False; flows = [-allin]
    for y, c in enumerate(cfbu, 1):
        taxable = c - k * allin - exemption
        zero = zero or taxable <= 0
        f = c - t * max(0.0, taxable)
        if y == n:
            gain = net_sale - allin * (1 - n * k)
            zero = zero or gain <= 0
            f += net_sale - t * max(0.0, gain)
        flows.append(f)
    return flows, zero


def live_walk_allin(cfbu, net_sale, floor, t=0.0, exemption=0.0, land_share=0.0):
    """Closed-form all-in basis A at which after-tax unlevered NPV at `floor` is zero (SKILL.md Live walk, v4.56).
    Exact when entity tax is positive every year and the sale produces a gain; status CHECK otherwise (re-solve the
    walk by bisection in ora_walk). Price = (A - day-1 capital) / (1 + closing %), applied by the caller.
    Returns dict(allin, status, irr) where irr is the self-check IRR re-run on the real MAX() cash flows."""
    n = len(cfbu); k = (1 - land_share) / 27.5
    d = [(1 + floor) ** -y for y in range(1, n + 1)]
    num = sum(dy * ((1 - t) * c + t * exemption) for dy, c in zip(d, cfbu)) + d[-1] * (1 - t) * net_sale
    den = 1 - t * k * sum(d) - d[-1] * t * (1 - n * k)
    a = num / den
    flows, zero = _after_tax_unlevered(a, cfbu, net_sale, t, exemption, land_share)
    r = _irr(flows)
    # n > 27.5: the hold outlasts the 27.5-yr schedule (whatever the land share), so uncapped depreciation overstates
    # the walk -> CHECK.
    ok = (a > 0 and (not zero or t == 0) and (n <= 27.5 or t == 0) and r is not None
          and abs(r - floor) <= 1e-6)
    return dict(allin=a, status="SOLVED" if ok else "CHECK", irr=r)


# ---------------- openpyxl writer (formula-driven) ----------------
NAVY = "1B2A4A"
USD = '#,##0;(#,##0)'; PCT = '0.00%'; X = '0.00"x"'


def _styles():
    from openpyxl.styles import Font, PatternFill, Alignment
    return dict(HF=Font(name="DM Sans", bold=True, color="FFFFFF", size=10), HFILL=PatternFill("solid", fgColor=NAVY),
                BLUE=Font(name="DM Sans", color="1F4E9E", size=10), BOLD=Font(name="DM Sans", bold=True, size=10),
                NOTE=Font(name="DM Sans", size=9, color="595959"), CENTER=Alignment(horizontal="center"))


def write_loan_block(ws, r, t, *, years, noi_ref, cfbu_ref, allin_ref, sale_expr, exit_year,
                     tax_expr=None, fund_year=1, value_ref=None, stab_noi_ref=None, notes=None):
    """Write one formula-driven loan scenario starting at row r. Columns: A label, B = Y0, C.. = Y1..Y{years}.
    noi_ref(y)/cfbu_ref(y): cell refs for model year y. sale_expr: formula text (no '=') for after-tax net sale at exit.
    tax_expr(y, deduction_expr): formula text for entity tax in year y, or None. Returns (next_row, refs)."""
    from openpyxl.utils import get_column_letter as _L
    _check_years(fund_year, exit_year, years)
    if exit_year - fund_year > t["amort"]:
        raise ValueError(f"loan years to exit ({exit_year - fund_year}) exceed amortization ({t['amort']}); "
                         "CUMPRINC/CUMIPMT return #NUM! past the last period")
    if t["loan"] <= 0 or t["rate"] <= 0:
        raise ValueError("write_loan_block needs loan > 0 and rate > 0 (CUMPRINC/CUMIPMT return #NUM! otherwise)")
    S = _styles()
    notes = notes or {}
    ws.cell(r, 1, t["label"]).font = S["HF"]
    for cc in range(1, years + 3): ws.cell(r, cc).fill = S["HFILL"]
    r += 1; inp = {}
    spec = [("loan", "Loan amount", USD), ("rate", "Note rate", PCT), ("amort", "Amortization = term (yrs)", "0"),
            ("mip", "Annual MIP", PCT), ("upfront_pct", "Upfront fees % of loan", PCT),
            ("fixed", "Third-party / fixed costs", USD), ("prepay_exit", "Prepayment premium at exit", PCT)]
    kk = exit_year - fund_year
    t = dict(t, prepay_exit=t["prepay"][kk - 1] if 1 <= kk <= len(t["prepay"]) else 0.0)
    for k, lab, fmt in spec:
        ws.cell(r, 1, lab); c = ws.cell(r, 2, t[k]); c.number_format = fmt; c.font = S["BLUE"]
        ws.cell(r, 3, notes.get(k, "")).font = S["NOTE"]
        inp[k] = f"$B${r}"; r += 1
    for i, v in enumerate(["Year"] + list(range(0, years + 1))):
        c = ws.cell(r, 1 + i, v); c.font = S["HF"]; c.fill = S["HFILL"]; c.alignment = S["CENTER"]
    r += 1
    names = ["Beginning balance", "Principal", "Interest", "Ending balance", "MIP", "Debt service", "DSCR (NOI / DS)",
             "Entity tax (levered)", "Levered CF"]
    rr = {n: r + i for i, n in enumerate(names)}
    for n in names: ws.cell(rr[n], 1, n)
    LN, RT, AM = inp["loan"], inp["rate"], inp["amort"]
    net = f"({LN}*(1-{inp['upfront_pct']})-{inp['fixed']})"
    for y in range(1, years + 1):
        c = _L(y + 2); k = y - fund_year; ded = "0"
        if k > t["amort"] and y > exit_year:
            k = 0   # past both the term and the exit: leave the schedule blank instead of writing #NUM! cells
        if k >= 1:
            ws[f"{c}{rr['Beginning balance']}"] = f"={LN}" if k == 1 else f"={_L(y + 1)}{rr['Ending balance']}"
            ws[f"{c}{rr['Principal']}"] = f"=-CUMPRINC({RT}/12,{AM}*12,{LN},{(k-1)*12+1},{k*12},0)"
            ws[f"{c}{rr['Interest']}"] = f"=-CUMIPMT({RT}/12,{AM}*12,{LN},{(k-1)*12+1},{k*12},0)"
            ws[f"{c}{rr['Ending balance']}"] = f"={c}{rr['Beginning balance']}-{c}{rr['Principal']}"
            ws[f"{c}{rr['MIP']}"] = f"={inp['mip']}*({c}{rr['Beginning balance']}+{c}{rr['Ending balance']})/2"
            ws[f"{c}{rr['Debt service']}"] = f"={c}{rr['Principal']}+{c}{rr['Interest']}+{c}{rr['MIP']}"
            ws[f"{c}{rr['DSCR (NOI / DS)']}"] = f"={noi_ref(y)}/{c}{rr['Debt service']}"
            ded = f"({c}{rr['Interest']}+{c}{rr['MIP']})"   # bracketed: callers may write `cf-{ded}`
        ws[f"{c}{rr['Entity tax (levered)']}"] = f"={tax_expr(y, ded)}" if tax_expr else "=0"
        f_ = f"={cfbu_ref(y)}-{c}{rr['Entity tax (levered)']}"
        if y == fund_year: f_ += f"+{net}"
        if k >= 1: f_ += f"-{c}{rr['Debt service']}"
        if y == exit_year: f_ += f"+{sale_expr}-{c}{rr['Ending balance']}*(1+{inp['prepay_exit']})"
        ws[f"{c}{rr['Levered CF']}"] = f_
    ws[f"B{rr['Levered CF']}"] = f"=-{allin_ref}" + (f"+{net}" if fund_year == 0 else "")
    for n in names:
        for col in range(2, years + 3): ws.cell(rr[n], col).number_format = X if n.startswith("DSCR") else USD
    r = r + len(names); res = {}
    E = _L(exit_year + 2); D2 = _L(fund_year + 3)
    out = [("Levered IRR", f"=IRR(B{rr['Levered CF']}:{E}{rr['Levered CF']})", PCT),
           ("Equity multiple", f"=IF(B{rr['Levered CF']}<0,SUM(C{rr['Levered CF']}:{E}{rr['Levered CF']})/-B{rr['Levered CF']},NA())", X),
           ("Net loan proceeds (after fees)", f"={net}", USD),
           ("Equity left in after funding", f"={allin_ref}-{net}", USD),
           # N/A when the first full year is the exit year (the sale would be in it) or no equity remains.
           ("First full-year cash-on-cash on remaining equity",
            "=NA()" if exit_year == fund_year + 1 else
            f"=IF({allin_ref}-{net}>0,{D2}{rr['Levered CF']}/({allin_ref}-{net}),NA())", PCT),
           ("Loan constant incl. MIP (first full year)", f"={D2}{rr['Debt service']}/{LN}", PCT),
           ("Minimum DSCR to exit", f"=MIN({D2}{rr['DSCR (NOI / DS)']}:{E}{rr['DSCR (NOI / DS)']})", X)]
    if value_ref: out.append(("LTV at stabilized value", f"={LN}/{value_ref}", PCT))
    if stab_noi_ref:
        out.append(("Max loan at program DSCR on stabilized NOI",
                    f"={stab_noi_ref}/{t['min_dscr']}/{D2}{rr['Debt service']}*{LN}", USD))
    out.append(("Balance at exit", f"={E}{rr['Ending balance']}", USD))
    for lab, f_, fmt in out:
        ws.cell(r, 1, lab).font = S["BOLD"]; c = ws.cell(r, 2, f_); c.number_format = fmt
        res[lab] = f"'{ws.title}'!$B${r}"; r += 1
    ws.cell(r, 1, "Eligibility: " + t["eligibility"] + "  Rate source: " + t["rate_source"]).font = S["NOTE"]
    res["inputs"] = {k: f"'{ws.title}'!{v}" for k, v in inp.items()}; res["rows"] = rr
    return r + 2, res
