#!/usr/bin/env python3
"""
build_no_text_layer_fixture.py — generate no_text_layer_fixture.pdf.

Regression fixture for the extraction bug the ora_doc_qc.py retrofit closes in
this skill. lease_qc.py's former text_of() branched on `.docx` only; ANY other
path — including a PDF — fell through to
`open(path, encoding='utf-8', errors='replace').read()`, i.e. a PDF's binary
container was read as if it were UTF-8 prose. That does not produce the
false-clean failure pma-qc/listing-agreement-qc had; it produces the opposite
shape — mojibake that trips almost every absence-based check at once, so the
tool reports a catastrophic-looking lease that it never actually read. Same
root cause (no format detection), different symptom.

This fixture does NOT need to be a genuine scanned image. The shared
ora_doc_qc.extract() gates on WORD COUNT, not on how the PDF failed to carry
text — DEFAULT_MIN_WORDS is 150. A PDF whose only content is a handful of
words trips the identical code path a blank/scanned page would, with no
rasterizer or OCR engine needed to construct it. This one page carries 7 words
of real, pdftotext-extractable text ("Sample ORA lease cover page only."
plus a two-word footer line) — deliberately non-empty, so the test proves the
gate counts words rather than merely checking for emptiness.

On this Windows dev host (2026-08-17) poppler's pdftoppm is NOT installed
(`command -v pdftoppm` -> not found) while tesseract IS, so
ora_doc_qc.ocr_available() returns False and the fixture exercises the
"OCR unavailable" branch of the UNREADABLE gate rather than a failed OCR
attempt. That is the gate working as designed on a host without the full OCR
toolchain, not a bug. The tests assert on the UNREADABLE outcome and exit
code, which are identical either way.

Mirrors listing-agreement-qc/tests/build_no_text_layer_fixture.py — keep the
two in step.

Usage:
    python3 build_no_text_layer_fixture.py
    (writes no_text_layer_fixture.pdf next to this script)
"""

import os

from reportlab.pdfgen import canvas

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "no_text_layer_fixture.pdf")


def build():
    c = canvas.Canvas(OUT, pagesize=(612, 792))
    c.setFont("Helvetica", 10)
    c.drawString(72, 720, "Sample ORA lease cover page only.")
    c.drawString(72, 72, "Page 1")
    c.showPage()
    c.save()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
