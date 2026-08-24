import os, re, sys, warnings
warnings.filterwarnings("ignore")
try:
    import openpyxl
except ImportError:
    print("openpyxl missing"); sys.exit(0)

ROOT = r"C:\Users\Owner\OneDrive - Oxford Capital Partners\Business"
NAMEPAT = re.compile(r"ORA_|underwrit|model|returns|irr", re.I)
LABELPAT = re.compile(r"refi|refinanc", re.I)
RATEPAT = re.compile(r"rate|coupon|interest", re.I)

hits, scanned, errs = [], 0, 0
for dirpath, dirnames, filenames in os.walk(ROOT):
    dirnames[:] = [d for d in dirnames if d.lower() not in ("_archive", "archive")]
    for fn in filenames:
        if not fn.lower().endswith(".xlsx") or fn.startswith("~$"):
            continue
        if not NAMEPAT.search(fn):
            continue
        p = os.path.join(dirpath, fn)
        scanned += 1
        try:
            wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
        except Exception as e:
            errs += 1
            continue
        try:
            for ws in wb.worksheets:
                for row in ws.iter_rows():
                    for c in row:
                        v = c.value
                        if not isinstance(v, str):
                            continue
                        if LABELPAT.search(v) and RATEPAT.search(v):
                            # look right along the row for a numeric
                            for nb in row:
                                if nb.column <= c.column:
                                    continue
                                nv = nb.value
                                if isinstance(nv, (int, float)):
                                    hits.append((p, ws.title, c.coordinate, v.strip()[:60], nv))
                                    break
                            break
        except Exception:
            errs += 1
        finally:
            try: wb.close()
            except Exception: pass

print(f"scanned={scanned} unreadable={errs} hits={len(hits)}")
for p, sheet, coord, label, val in hits:
    pct = val * 100 if isinstance(val, float) and val < 1 else val
    flag = "  <-- STALE 7.00%" if isinstance(pct, float) and abs(pct - 7.0) < 0.001 else ""
    print(f"{os.path.relpath(p, ROOT)} | {sheet}!{coord} | {label} = {pct}{flag}")
