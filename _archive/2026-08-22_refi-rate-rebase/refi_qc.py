import os, re, warnings, json
warnings.filterwarnings("ignore")
import openpyxl

ROOT = r"C:\Users\Owner\OneDrive - Oxford Capital Partners\Business\Investment Candidates -- 2026"
STAMP = "2026-08-22_refi-rebase-6.50"
FILES = [
 "20260610_470-McCormick_Model_v03.xlsx",
 "2262-112th-Ave-Holland-MI IRR Model.xlsx",
 "8025-8009 IRR Model.xlsx",
 "808 Rhoads Columbus IRR Model.xlsx",
 "IRR Model Pike Plaza Indy Car Dealerships 7.27.2026.xlsx",
 "ORA_UnderwritingModel_125DouglasPike_v2.0.xlsx",
 "ORA_Underwriting_2900-Northridge-Dr-NW_v1.0.xlsx",
 "ORA_Underwriting_4331-Brockton-Dr-SE_v1.0.xlsx",
 r"outputs\2026-07-18_2900-Northridge-Dr-NW_Underwriting-Model_v01.xlsx",
 r"outputs\2026-07-18_4331-Brockton-Dr-SE_Underwriting-Model_v01.xlsx",
]
KEY = re.compile(r"\bDSCR\b|levered IRR|IRR --|refi proceeds|loan amount|equity multiple|refi rate|refi interest|refi fixed", re.I)

def grab(path):
    d = {}
    wb = openpyxl.load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for c in row:
                if not isinstance(c.value, str) or not KEY.search(c.value):
                    continue
                for nb in row:
                    if nb.column <= c.column: continue
                    v = nb.value
                    if isinstance(v, (int, float)):
                        d[f"{ws.title}!{nb.coordinate} {c.value.strip()[:46]}"] = float(v)
                        break
                break
    wb.close(); return d

for f in FILES:
    live = os.path.join(ROOT, f)
    dirn, base = os.path.split(live)
    arch = os.path.join(dirn, "_archive", STAMP, base)
    print("=" * 78); print(base)
    if not os.path.exists(arch): print("  no archive"); continue
    b, a = grab(arch), grab(live)
    nones = sum(1 for v in a.values() if v is None)
    print(f"  cached values present after recalc: {len(a)} metrics, {nones} null")
    shown = 0
    for k in sorted(set(b) | set(a)):
        vb, va = b.get(k), a.get(k)
        if vb is None or va is None: continue
        if abs(va - vb) < 1e-9: continue
        if abs(vb) < 5:   # rates / ratios / multiples
            print(f"  {k}: {vb:.4f} -> {va:.4f}")
        else:
            print(f"  {k}: {vb:,.0f} -> {va:,.0f}")
        shown += 1
    if shown == 0: print("  (no metric moved)")
    # DSCR floor check
    for k, va in a.items():
        if re.search(r"actual dscr|dscr at|dscr check|dscr at stabil|dscr \(yr", k, re.I):
            vb = b.get(k)
            if vb is None or va is None:
                print(f"  FLOOR 1.25x | {k}: before={vb} after={va} (not comparable)"); continue
            fb = "PASS" if vb >= 1.25 else "BREACH"
            fa = "PASS" if va >= 1.25 else "BREACH"
            flag = "  <== FLOOR STATE CHANGED" if fb != fa else ""
            print(f"  FLOOR 1.25x | {k}: {fb} ({vb:.3f}) -> {fa} ({va:.3f}){flag}")
