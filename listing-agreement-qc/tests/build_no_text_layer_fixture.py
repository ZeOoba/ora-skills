#!/usr/bin/env python3
"""
build_no_text_layer_fixture.py — generate no_text_layer_fixture.pdf.

Regression fixture for the false-clean bug this skill's ora_doc_qc.py
retrofit exists to close: a broker sends a scanned listing agreement with no
usable text layer, extraction yields (near-)empty text, and a naive scanner
that treats "empty" as "zero defects found" reports the document clean.

This fixture does NOT need to be an actual scanned image. The shared
ora_doc_qc.extract() gates on word count, not on *how* the PDF failed to
carry text — DEFAULT_MIN_WORDS is 150. A PDF whose only real content is a
handful of words (well under that floor) trips the exact same code path a
truly blank/scanned page would, without needing a rasterizer or OCR engine to
construct. This one page carries 6 words of real, pdftotext-extractable
text: "Sample listing agreement cover page only." That is deliberate — a
non-empty extraction that still fails the word-count floor proves the gate
checks word count, not just emptiness.

On this Windows dev host (2026-08-17), poppler's pdftoppm is not installed
(confirmed via `which pdftoppm` -> not found), so ora_doc_qc.ocr_available()
returns False regardless of this fixture — running listing_qc.py against it
is expected to hit the "OCR unavailable" branch of the UNREADABLE gate, not
an actual failed OCR attempt. That is the gate working as designed on a host
without the OCR toolchain, not a bug.

Usage:
    python3 build_no_text_layer_fixture.py
    (writes no_text_layer_fixture.pdf next to this script)
"""

import os

from reportlab.pdfgen import canvas

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "no_text_layer_fixture.pdf")


def build():
    c = canvas.Canvas(OUT, pagesize=(612, 792))
    c.setFont("Helvetica", 10)
    c.drawString(72, 720, "Sample listing agreement cover page only.")
    c.showPage()
    c.save()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    build()
