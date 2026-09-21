#!/usr/bin/env python3
"""package_census.py -- census a closing-package folder before anything is called NOT FOUND.

Step 0 of the settlement-basis-extraction method: read the whole package first. This lists
every PDF under a property or entity folder with its page count, whether it has a text layer
(sampled, so a 90-page scan costs a few pages, not all of them), whether an OCR twin
('<name> (OCR).pdf') already sits beside it, and any path long enough to break Windows tools.
With --factbase it also lists every fact-base field still marked NOT FOUND / INFERRED /
CONFLICT / illegible, and says whether the fact base was ever re-checked against the folder.

Usage:
  python package_census.py FOLDER [--factbase FACT.json] [--json]
Exit: 0 always (it reports; it does not judge). 2 if FOLDER is not a directory.
Needs PyMuPDF (pip install pymupdf).
"""
import argparse
import json
import os
import re
import sys

LONG_PATH = 240          # Windows tools fail near 260 characters
SAMPLE_PAGES = 6         # first pages sampled for a text layer
TEXT_MIN_CHARS = 100     # average characters per sampled page to call a page 'text'
FLAG_STATUS = re.compile(r"NOT FOUND|INFERRED|CONFLICT|illegible|UNVERIFIED", re.I)


def classify_pdf(path):
    """Return dict(status, pages, sample_chars). status: TEXT | PARTIAL | IMAGE-ONLY | UNREADABLE."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        raise SystemExit("package_census: PyMuPDF is required (pip install pymupdf)")
    try:
        doc = fitz.open(path)
    except Exception as e:  # noqa: BLE001 - any open failure is reported, never raised
        return {"status": "UNREADABLE", "pages": 0, "sample_chars": 0, "error": type(e).__name__}
    try:
        n = len(doc)
        sampled = [len(doc[i].get_text().strip()) for i in range(min(n, SAMPLE_PAGES))]
    finally:
        doc.close()
    with_text = sum(1 for c in sampled if c >= TEXT_MIN_CHARS)
    if not sampled or with_text == 0:
        status = "IMAGE-ONLY"
    elif with_text == len(sampled):
        status = "TEXT"
    else:
        status = "PARTIAL"
    return {"status": status, "pages": n, "sample_chars": sum(sampled)}


def is_twin(name):
    return name.lower().endswith(" (ocr).pdf")


def census(folder):
    rows = []
    for root, _dirs, files in os.walk(folder):
        names = set(files)
        for f in sorted(files):
            if not f.lower().endswith(".pdf") or is_twin(f):
                continue
            full = os.path.join(root, f)
            info = classify_pdf(full)
            info.update({
                "path": os.path.relpath(full, folder),
                "long_path": len(full) >= LONG_PATH,
                "has_twin": f"{f[:-4]} (OCR).pdf" in names,
            })
            rows.append(info)
    return rows


def scan_factbase(path):
    """List flagged fields and whether the corporate-folder recheck ran."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    flagged = []

    def walk(node, trail):
        if isinstance(node, dict):
            st = node.get("status")
            if isinstance(st, str) and FLAG_STATUS.search(st):
                flagged.append((".".join(trail), st[:80]))
            for k, v in node.items():
                walk(v, trail + [str(k)])
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, trail + [str(i)])

    body = {k: v for k, v in data.items() if not k.startswith("_")}
    walk(body, [])
    meta = data.get("_meta", {}) if isinstance(data, dict) else {}
    read_keys = [k for k in meta if k.startswith("corporate_folder_read")]
    rechecked = any(isinstance(meta[k], dict) and any(x.startswith("recheck") for x in meta[k]) for k in read_keys)
    return {"flagged": flagged, "corporate_folder_read": bool(read_keys), "rechecked": rechecked}


def render(rows, fb=None):
    out = ["STATUS      PAGES  TWIN  LONG  FILE"]
    for r in sorted(rows, key=lambda x: (x["status"] != "IMAGE-ONLY", x["path"])):
        out.append(f"{r['status']:<11} {r['pages']:>5}  {'yes' if r['has_twin'] else '-':<4}  {'LONG' if r['long_path'] else '-':<4}  {r['path']}")
    n = len(rows)
    img = [r for r in rows if r["status"] in ("IMAGE-ONLY", "PARTIAL")]
    need = [r for r in img if not r["has_twin"]]
    out += ["", f"{n} PDFs: {sum(r['status']=='TEXT' for r in rows)} text, {sum(r['status']=='PARTIAL' for r in rows)} partial, "
                f"{sum(r['status']=='IMAGE-ONLY' for r in rows)} image-only, {sum(r['status']=='UNREADABLE' for r in rows)} unreadable; "
                f"{len(need)} scan(s) without an OCR twin; {sum(r['long_path'] for r in rows)} long path(s)."]
    if any(r["long_path"] for r in rows):
        out.append("Long paths break Python/Windows tools ('no such file'): copy the file out with Git Bash `cp` before reading.")
    if fb is not None:
        out += ["", f"FACT BASE: {len(fb['flagged'])} field(s) flagged NOT FOUND / INFERRED / CONFLICT / illegible."]
        out += [f"  {p}: {s}" for p, s in fb["flagged"][:40]]
        if not fb["corporate_folder_read"]:
            out.append("  This fact base has NO corporate-folder read recorded: treat every flagged field as UNVERIFIED until this folder is read.")
        elif not fb["rechecked"]:
            out.append("  A corporate-folder read is noted but no recheck result is recorded: treat flagged fields as UNVERIFIED.")
        else:
            out.append("  Corporate-folder recheck recorded: flagged fields are what remains after that pass.")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("folder")
    ap.add_argument("--factbase")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not os.path.isdir(a.folder):
        print(f"package_census: not a directory: {a.folder}", file=sys.stderr)
        return 2
    rows = census(a.folder)
    fb = scan_factbase(a.factbase) if a.factbase else None
    if a.json:
        print(json.dumps({"rows": rows, "factbase": fb}, indent=1))
    else:
        print(render(rows, fb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
