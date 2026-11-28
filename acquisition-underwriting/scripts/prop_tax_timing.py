#!/usr/bin/env python3
"""prop_tax_timing.py — the 'seller's bill first, new assessment later' pattern (ORA acquisition-underwriting).
In some jurisdictions the buyer's first year is billed on the seller's assessment, and the purchase price reaches
the tax base only at a later tax year. This module turns a close date + jurisdiction profile into a calendar-year
(model-year) tax schedule under four assessment cases, and emits the matching Excel formula pattern.

Profiles (verify each tax year; [EST] where marked):
  DC  — tax year (TY) runs Oct 1–Sep 30 and is named by its ending year (TY2027 = Oct-2026..Sep-2027).
        Annual market reassessment; valuation date Jan 1 of the calendar year before the TY ends
        (TY2028 is valued 1/1/2027); notices by Mar 1; first-level appeal deadline Apr 1.
        A sale does not reset the base: the price reaches the base only through the assessor or an appeal.
        Earliest TY the price can reach = the TY after the one in force at close. A new owner may petition for
        administrative review within 45 days of the purchase date (OTR, Assessment Appeal Rights, 2025), so a close
        after Apr 1 does NOT forfeit the next TY: file the new-owner petition within 45 days, else by Apr 1.
        USUAL OUTCOME (2026-11-24 research): full reset to the price is the optimistic tail, not the norm. RPTAC
        reduced 3.6% (TY2023, 48/1,335) and 8.5% (TY2024, 41/485) of decided Class 2 appeals; practitioners cite
        5-25% reductions when an appeal succeeds; DC office assessments ran ~200% of sale price for 2023-24 trades.
        Class 2 rate is a whole-value step: 1.65% <= USD 5M, 1.77% <= USD 10M, 1.89% above (OTR FY2026).
  MI  — tax year = calendar year (summer + winter bills levied on that year's Taxable Value, TV).
        Tax day Dec 31. A transfer in year Y uncaps TV in Y+1: TV(Y+1) = SEV(Y+1) (MCL 211.27a(3)); afterwards
        TV grows by MIN(CPI, 5%) (the inflation rate multiplier) while SEV tracks ~50% of true cash value.
        The close year is billed on the seller's capped TV (prorated here on a calendar-accrual basis [EST];
        local closing custom may prorate on due dates instead).
Cases (TY after the reset point):
  A — base resets to the price (DC: AV = price; MI: SEV = 50% x price)       <- governing for MI (doctrine)
  B — midpoint of A and C                                                  <- governing for DC (Gabriel 2026-11-24)
  C — assessor's current value holds and grows (DC: current AV; MI: current assessor SEV)
  PW — probability-weighted A/B/C, standing default 20/50/30, reported only
"""
from dataclasses import dataclass, field
import datetime as dt
@dataclass
class Deal:
    profile: str                 # 'DC' or 'MI'
    close: dt.date
    price: float
    current_base: float          # DC: assessment in force at close; MI: seller's capped TV in force at close
    assessor_value: float        # DC: assessor's latest/proposed AV; MI: assessor's current SEV
    rate: float = None           # DC: None -> Class 2 step; MI: total mills / 1000 (incl. admin fee)
    addon_rate: float = 0.0      # e.g. a DC BID of about 0.001 of AV; MI special assessments as rate
    growth: float = 0.025        # assessor value growth [EST]
    mi_cap: float = 0.025        # MI inflation rate multiplier - 1 after uncap [EST] (capped at 5%)
    weights: tuple = (0.2, 0.5, 0.3)   # standing reported default (Gabriel 2026-11-24)
    next_ty_base: float = None   # DC: AV already noticed for the TY after close (else assessor_value)
def dc_rate(av):
    return 0.0165 if av <= 5_000_000 else (0.0177 if av <= 10_000_000 else 0.0189)
def dc_reset_ty(close):
    # TY in force at close, plus one (new-owner petition within 45 days covers the noticed next TY).
    close_ty = close.year + 1 if close.month >= 10 else close.year
    return close_ty + 1
def schedule(d: Deal, years=11, case='A'):
    """Return list of dicts per model year (calendar year from close year) with tax by month-weighting."""
    out = []
    y0 = d.close.year
    for i in range(years):
        cy = y0 + i; tot = 0.0; parts = []
        for m in range(1, 13):
            mdate = dt.date(cy, m, 1)
            if mdate < dt.date(d.close.year, d.close.month, 1): continue
            frac = 1/12
            if mdate.year == d.close.year and m == d.close.month:   # partial first month
                dim = (dt.date(cy + (m == 12), m % 12 + 1, 1) - mdate).days
                frac = (dim - (d.close.day - 1)) / dim / 12
            base = base_for(d, cy, m, case)
            r = d.rate if d.rate is not None else dc_rate(base)
            tot += base * (r + d.addon_rate) * frac
        out.append(dict(year=cy, tax=round(tot, 2)))
    return out
def base_for(d, cy, m, case):
    if d.profile == 'DC':
        ty = cy + 1 if m >= 10 else cy
        close_ty = d.close.year + 1 if d.close.month >= 10 else d.close.year
        reset = dc_reset_ty(d.close)
        if ty <= close_ty: return d.current_base
        n = ty - reset
        A = d.price * (1 + d.growth) ** n
        C = d.assessor_value * (1 + d.growth) ** (ty - close_ty)
    elif d.profile == 'MI':
        ty = cy
        if ty == d.close.year: return d.current_base
        n = ty - (d.close.year + 1)
        A0, C0 = 0.5 * d.price, d.assessor_value
        cap = min(d.mi_cap, 0.05)
        A = A0 * (1 + cap) ** n          # TV grows at the cap after uncap (SEV assumed to grow at least as fast)
        C = C0 * (1 + d.growth) * (1 + cap) ** n
    else:
        raise ValueError(d.profile)
    B = (A + C) / 2
    if case == 'A': return A
    if case == 'B': return B
    if case == 'C': return C
    wA, wB, wC = d.weights
    return wA * A + wB * B + wC * C
def excel_pattern(profile):
    """Formula pattern for an annual model row (CY in row 8; AV rows built per case)."""
    if profile == 'DC':
        return ("CY tax = (months of CY in TY=CY)/12 * AV(TY=CY) * rate(AV) + (months in TY=CY+1)/12 * AV(TY=CY+1) * rate(AV)\n"
                "  full years: =0.75*AV_CY*IF(AV_CY>1e7,1.89%,IF(AV_CY>5e6,1.77%,1.65%))+0.25*AV_CY1*IF(AV_CY1>1e7,1.89%,IF(AV_CY1>5e6,1.77%,1.65%))\n"   # ORA: 1.89% tier above USD 10M (dc_rate)
                "  AV(TY): =IF(TY<=CloseTY, AV_inforce, IF(TY<ResetTY, AV_noticed, IF(Case=\"A\",Price*(1+g)^(TY-ResetTY), ...)))\n"
                "  CloseTY = YEAR(Close)+IF(MONTH(Close)>=10,1,0); ResetTY = CloseTY+1 (file new-owner petition within 45 days)")
    return ("CY tax = IF(CY=YEAR(Close), TV_capped*mills*(DaysOwned/365), TV_uncapped(CY)*mills)\n"
            "  TV_uncapped(CY) = IF(Case=\"A\",0.5*Price,SEV_assessor*(1+g))*(1+MIN(CPIcap,5%))^(CY-YEAR(Close)-1)")
if __name__ == '__main__':
    # Test 1: synthetic DC deal (price 1.4M, AV 3.2M) — Y1 RP = 45,375; Y2 = 23,244 under case A
    d = Deal('DC', dt.date(2027, 1, 1), 1_400_000, 3_200_000, 3_200_000)
    s = schedule(d, 3, 'A'); print('DC synthetic, case A:', s)
    print('DC reset TY: close 1/1/2027 ->', dc_reset_ty(dt.date(2027, 1, 1)), '| 6/15/2027 ->', dc_reset_ty(dt.date(2027, 6, 15)), '| 10/15/2027 ->', dc_reset_ty(dt.date(2027, 10, 15)))
    d2 = Deal('DC', dt.date(2027, 6, 15), 1_400_000, 3_200_000, 3_200_000, next_ty_base=3_200_000 * 1.025)
    print('DC June close, case A (new-owner petition within 45 days; reset still TY2028):', schedule(d2, 3, 'A'))
    # Test 2: synthetic MI deal — capped TV 500,000, 40.00 mills, price 2.0M -> Y2 tax 40,000
    m = Deal('MI', dt.date(2026, 1, 1), 2_000_000, 500_000, 1_000_000, rate=0.04, growth=0.0)
    print('MI synthetic, case A:', schedule(m, 3, 'A'))
    print(excel_pattern('DC')); print(excel_pattern('MI'))
