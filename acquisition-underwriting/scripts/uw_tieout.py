#!/usr/bin/env python3
"""uw_tieout.py — mandatory engine-mirror tie-out for every FULL underwrite (ORA acquisition-underwriting QC Gate).
The workbook is the deliverable; an independent Python engine (written separately from the formulas) is the check.
This tool compares the recalculated workbook to the engine's expected values cell by cell and fails loudly.

Expected-values file (JSON), written by the deal's engine:
  {"tolerances": {"money": 1.0, "rate": 1e-4},
   "cells": {"PF_Base!E40": 142292.84, "PF_Base!B120": 0.041725, ...},
   "rows":  {"PF_Base!C39:M39": [14336.13, 119114.0, ...]}}          # optional: whole rows
Rule: |x| < 5 is treated as a rate (rate tolerance); otherwise money tolerance. ORA: list ratio/multiple cells
(DSCR, equity multiple) under "ratios": [...] to give them the rate tolerance; an empty expected file or a row
whose value count differs from its range is an input error (exit 2); any Excel error literal fails.

Usage:
  python uw_tieout.py model.xlsx expected.json --out tieout.md
Exit 0 = PASS (every cell within tolerance and the workbook has no formula errors);
     1 = FAIL (mismatches listed); 2 = input error (missing sheet/cell, workbook not recalculated).
Run recalc first (xlsx skill scripts/recalc.py) so cached values exist.
"""
import sys, json, argparse, openpyxl
from openpyxl.utils import range_boundaries, get_column_letter
ERRS=('#REF!','#VALUE!','#DIV/0!','#NAME?','#N/A','#NUM!','#NULL!')
import re as _re   # ORA
ERR_RX=_re.compile(r'^#(?:[A-Z0-9/]+[!?]|N/A|GETTING_DATA)$')   # ORA: any Excel error literal (#SPILL!, #CALC!, ...)
def cells_of(ref):
    sh,rng=ref.split('!'); c1,r1,c2,r2=range_boundaries(rng)
    return [(sh,f"{get_column_letter(c)}{r}") for r in range(r1,r2+1) for c in range(c1,c2+1)]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('xlsx'); ap.add_argument('expected'); ap.add_argument('--out')
    a=ap.parse_args(); E=json.load(open(a.expected,encoding='utf-8'))
    if hasattr(sys.stdout,'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')   # ORA: Windows console (cp1252)
    tm=E.get('tolerances',{}).get('money',1.0); tr=E.get('tolerances',{}).get('rate',1e-4)
    wb=openpyxl.load_workbook(a.xlsx,data_only=True)
    pairs=[(r.split('!')[0],r.split('!')[1],v) for r,v in E.get('cells',{}).items()]
    bad_rows=[]   # ORA: input errors (empty file, row-length mismatch)
    for ref,vals in E.get('rows',{}).items():
        cl=cells_of(ref)   # ORA
        if len(cl)!=len(vals): bad_rows.append(f"{ref}: {len(cl)} cells vs {len(vals)} values")   # ORA: never truncate
        for (sh,c),v in zip(cl,vals): pairs.append((sh,c,v))   # ORA
    ratios=set(E.get('ratios',[]))   # ORA: cells that are ratios/multiples (DSCR, EM): rate tolerance whatever the size
    errs=[f"{ws.title}!{c.coordinate}" for ws in wb for row in ws.iter_rows() for c in row if isinstance(c.value,str) and (c.value in ERRS or ERR_RX.match(c.value))]   # ORA: any error literal
    rows=[]; fails=0; missing=0
    for sh,c,exp in pairs:
        if sh not in wb.sheetnames: rows.append((f"{sh}!{c}",exp,'MISSING SHEET','FAIL')); missing+=1; continue
        got=wb[sh][c].value
        if got is None: rows.append((f"{sh}!{c}",exp,'None (not recalculated?)','FAIL')); missing+=1; continue
        if isinstance(exp,str):
            ok=str(got)==exp
        else:
            tol=tr if (abs(exp)<5 or f"{sh}!{c}" in ratios) else tm; ok=abs(float(got)-exp)<=tol   # ORA: ratios
        rows.append((f"{sh}!{c}",exp,got,'ok' if ok else 'FAIL')); fails+= (not ok)
    if not pairs: bad_rows.append("no checks: the expected file is empty")   # ORA: zero checks is never a PASS
    missing+=len(bad_rows)   # ORA
    status='PASS' if not fails and not missing and not errs else 'FAIL'
    L=[f"# Engine tie-out: {status}",f"- Workbook: {a.xlsx}",f"- Checks: {len(pairs)} · mismatches: {fails} · missing: {missing} · formula errors: {len(errs)}",
       f"- Tolerances: money ±{tm}, rate ±{tr}","","| Cell | Engine | Workbook | Result |","|---|---|---|---|"]
    show=[r for r in rows if r[3]!='ok'] or rows[:25]
    for r in show: L.append(f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} |")
    if errs: L+=["","Formula errors: "+", ".join(errs[:50])]
    if bad_rows: L+=["","Input errors: "+"; ".join(bad_rows)]   # ORA
    rep="\n".join(L); print(rep)
    if a.out: open(a.out,'w',encoding='utf-8').write(rep)
    sys.exit(0 if status=='PASS' else (2 if missing and not fails else 1))
if __name__=='__main__': main()
