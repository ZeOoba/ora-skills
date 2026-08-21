#!/usr/bin/env python3
"""
build_no_text_layer_fixture.py — generate no_text_layer_fixture.pdf.

Regression fixture for the extraction bug the ora_doc_qc.py retrofit closes in
this skill. addendum_qc.py's text_of() is unconditional `zipfile.ZipFile(path)`
with no format branch at all — a PDF handed to it raises an uncaught
zipfile.BadZipFile ("File is not a zip file"), crashing the whole scan instead
of returning a QC result. That is a different failure shape than lease_qc.py's
former bug (which misread a PDF as UTF-8 prose and scored it "FAILED" on
content it never read) or pma-qc/listing-agreement-qc's former bug (an empty
extraction scoring "clean") — but it is the same root cause: no real format
detection before applying a format-specific parser to file bytes.

This fixture does NOT need to be a genuine scanned image. The shared
ora_doc_qc.extract() gates on WORD COUNT, not on how the PDF failed to carry
text — DEFAULT_MIN_WORDS is 150. A PDF whose only content is a handful of
words trips the identical code path a blank/scanned page would, with no
rasterizer or OCR engine needed to construct it.

Mirrors lease-form-qc/tests/build_no_text_layer_fixture.py and
listing-agreement-qc/tests/build_no_text_layer_fixture.py — keep the three in
step.

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
    c.drawString(72, 720, "Sample ORA addendum cover page only.")
    c.drawString(72, 72, "Page 1")
    c.showPage()
    c.save()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
