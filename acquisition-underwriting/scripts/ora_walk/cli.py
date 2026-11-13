"""CLI: python -m ora_walk deal.json [--ust 0.045 | --fetch-ust] [--json]

deal.json is one deal object (fields of solver.Deal) or {"portfolio": [...], "portfolio_ask": N}.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.request
from dataclasses import fields
from datetime import date, timedelta

from .solver import Deal, solve, solve_portfolio

FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DGS10"


def fetch_ust_30d() -> tuple[float, str]:
    """Trailing 30-calendar-day average of FRED DGS10 (no API key; no user data sent)."""
    with urllib.request.urlopen(FRED_CSV, timeout=20) as r:
        rows = list(csv.reader(io.StringIO(r.read().decode())))[1:]
    obs = [(date.fromisoformat(d), float(v)) for d, v in rows if v not in (".", "")]
    last = obs[-1][0]
    window = [v for d, v in obs if d > last - timedelta(days=30)]
    return sum(window) / len(window) / 100, last.isoformat()


def _deal(obj: dict) -> Deal:
    known = {f.name for f in fields(Deal)}
    unknown = set(obj) - known
    if unknown:
        raise SystemExit(f"Unknown deal fields: {sorted(unknown)}")
    return Deal(**obj)


def _usd(x) -> str:
    return "—" if x is None else f"${x:,.0f}"


def _pct(x) -> str:
    return "—" if x is None else f"{x:.2%}"


def render(res: dict, ust_note: str) -> str:
    L = res["legs"]; F = res["floors"]; R = res["refi"]; A = res["ask"]
    out = [
        f"## {res['name']} — Walk Price {_usd(res['walk_price'])} ({res['binding_leg'].upper()} binds)",
        f"Doctrine: {F['doctrine']} · UST {_pct(F['ust'])} {ust_note} · NOI must be after vacancy/credit/mgmt (reserves deducted here)",
        "",
        "| Leg | Max price | Floor |",
        "|---|---:|---|",
        f"| Basis | {_usd(L['basis'])} | {_pct(F['basis_floor_pct'])} discount to RCT LOW ${F['rct_low_psf_adjusted']:,.2f}/SF (vintage {F['vintage_used'] or 'unknown'}; construction ×{F['construction_multiplier']:.2f}, adders ${F['adders_psf']:.0f}/SF) |",
        f"| Yield | {_usd(L['yield'])} | stabilized YoC {_pct(F['yoc_floor'])} on NOI {_usd(F['stabilized_noi_net'])} (net of reserves) |",
        f"| IRR (10-yr unlevered) | {_usd(L['irr'])} | {_pct(F['irr_floor'])} · exit cap {_pct(F['exit_cap'])} |",
        "",
        f"**Refi governor (reported at walk):** rate {_pct(R['refi_rate'])}, constant {_pct(R['debt_constant'])}, "
        f"loan {_usd(R['loan'])} — **{R['binding_constraint']} binds**; DSCR @65% LTV "
        f"{'—' if R['dscr_at_65_ltv'] is None else format(R['dscr_at_65_ltv'], '.2f') + 'x'} "
        f"({'PASS' if R['dscr_floor_pass'] else 'FLOOR-FLAGGED'}); "
        f"DSCR binds below exit cap {_pct(R['breakeven_exit_cap'])}. Levered IRR (reported only): {_pct(R['levered_irr_reported'])}",
    ]
    if A:
        out += ["", f"**Ask {_usd(A['ask_price'])}:** gap {_usd(A['gap_to_ask'])} ({_pct(A['gap_pct_of_ask'])} of ask) · "
                f"YoC at ask {_pct(A['ask_yoc'])} · discount to replacement {_pct(A['ask_discount_to_replacement'])} · "
                f"floors flagged at ask: {', '.join(A['floors_flagged_at_ask']) or 'none'}"]
    if res["flags"]:
        out += ["", "**Flags:**"] + [f"- {f}" for f in res["flags"]]
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ora_walk", description="ORA walk-price solver")
    ap.add_argument("deal_json")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ust", type=float, help="10-yr UST as decimal (e.g. 0.0452), DGS10 30-day avg")
    g.add_argument("--fetch-ust", action="store_true", help="pull DGS10 30-day avg from FRED")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    if a.fetch_ust:
        ust, asof = fetch_ust_30d()
        note = f"(FRED DGS10 30-day avg as of {asof})"
    else:
        if not 0 < a.ust < 0.2:
            raise SystemExit("--ust must be a decimal, e.g. 0.0452")
        ust, note = a.ust, "(supplied — cite source and date) [UST UNVERIFIED unless sourced]"

    with open(a.deal_json, encoding="utf-8") as fh:
        spec = json.load(fh)

    if "portfolio" in spec:
        res = solve_portfolio([_deal(d) for d in spec["portfolio"]], ust, spec.get("portfolio_ask"))
        if a.json:
            print(json.dumps(res, indent=2)); return 0
        print("\n\n".join(render(b, note) for b in res["buildings"]))
        print(f"\n## Portfolio (Amendment H)\nSum of walks {_usd(res['sum_of_walks'])} · max premium "
              f"{_usd(res['max_premium_over_sum'])} · **Portfolio walk {_usd(res['portfolio_walk_price'])}** "
              f"(IRR floor {_pct(res['portfolio_irr_floor'])}; blended-YoC cap {_usd(res['max_price_blended_yoc'])}, "
              f"IRR cap {_usd(res['max_price_portfolio_irr'])})")
        print(f"\nPremium allocation: {res['allocation_method']} (SKILL.md:103)")
        print("\n| Building | Walk | Premium share | Allocated | Floors breached |\n|---|---:|---:|---:|---|")
        for al in res["allocation"]:
            print(f"| {al['name']} | {_usd(al['walk'])} | {_usd(al['premium_share'])} | "
                  f"{_usd(al['allocated_price'])} | {', '.join(al['floors_breached']) or 'none'} |")
        if "portfolio_ask" in res:
            print(f"\n**Portfolio ask {_usd(res['portfolio_ask'])}:** gap {_usd(res['gap_to_ask'])}")
        if res["flags"]:
            print("\n**Portfolio flags:**")
        for f in res["flags"]:
            print(f"- {f}")
        return 0

    res = solve(_deal(spec), ust).to_dict()
    print(json.dumps(res, indent=2) if a.json else render(res, note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
