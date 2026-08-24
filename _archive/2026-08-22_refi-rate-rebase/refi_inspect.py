import os, re, sys, warnings, json
warnings.filterwarnings("ignore")
import openpyxl

ROOT = r"C:\Users\Owner\OneDrive - Oxford Capital Partners\Business"
TARGETS = [
 r"Investment Candidates -- 2026\20260610_470-McCormick_Model_v03.xlsx",
 r"Investment Candidates -- 2026\2262-112th-Ave-Holland-MI IRR Model.xlsx",
 r"Investment Candidates -- 2026\8025-8009 IRR Model.xlsx",
 r"Investment Candidates -- 2026\808 Rhoads Columbus IRR Model.xlsx",
 r"Investment Candidates -- 2026\IRR Model Pike Plaza Indy Car Dealerships 7.27.2026.xlsx",
 r"Investment Candidates -- 2026\ORA_UnderwritingModel_125DouglasPike_v2.0.xlsx",
 r"Investment Candidates -- 2026\ORA_Underwriting_2900-Northridge-Dr-NW_v1.0.xlsx",
 r"Investment Candidates -- 2026\ORA_Underwriting_4331-Brockton-Dr-SE_v1.0.xlsx",
 r"Investment Candidates -- 2026\outputs\2026-07-18_2900-Northridge-Dr-NW_Underwriting-Model_v01.xlsx",
 r"Investment Candidates -- 2026\outputs\2026-07-18_4331-Brockton-Dr-SE_Underwriting-Model_v01.xlsx",
]
LABEL = re.compile(r"refi|refinanc", re.I)
RATE = re.compile(r"rate|coupon|interest", re.I)
METRIC = re.compile(r"\bDSCR\b|levered IRR|IRR \(levered\)|equity multiple|refi proceeds|loan amount", re.I)

out = []
for rel in TARGETS:
    p = os.path.join(ROOT, rel)
    rec = {"file": rel, "exists": os.path.exists(p), "cells": [], "metrics": [], "charts": 0, "sheets": []}
    if not rec["exists"]:
        out.append(rec); continue
    wf = openpyxl.load_workbook(p, data_only=False)   # formulas
    wv = openpyxl.load_workbook(p, data_only=True)    # cached values
    rec["sheets"] = wf.sheetnames
    for ws in wf.worksheets:
        try: rec["charts"] += len(ws._charts)
        except Exception: pass
        vs = wv[ws.title]
        for row in ws.iter_rows():
            for c in row:
                if not isinstance(c.value, str): continue
                if LABEL.search(c.value) and RATE.search(c.value):
                    for nb in row:
                        if nb.column <= c.column: continue
                        f = nb.value
                        v = vs.cell(row=nb.row, column=nb.column).value
                        if f is None and v is None: continue
                        isform = isinstance(f, str) and f.startswith("=")
                        if isform or isinstance(f, (int, float)):
                            rec["cells"].append({
                                "sheet": ws.title, "label": c.value.strip()[:70],
                                "label_at": c.coordinate, "value_at": nb.coordinate,
                                "stored": repr(f), "cached": repr(v),
                                "is_formula": isform,
                                "numfmt": nb.number_format})
                            break
                    break
                if METRIC.search(c.value):
                    for nb in row:
                        if nb.column <= c.column: continue
                        v = vs.cell(row=nb.row, column=nb.column).value
                        if isinstance(v, (int, float)):
                            rec["metrics"].append({"sheet": ws.title, "label": c.value.strip()[:50],
                                                   "at": nb.coordinate, "before": round(float(v), 6)})
                            break
                    break
    wf.close(); wv.close()
    out.append(rec)

print(json.dumps(out, indent=1)[:14000])
