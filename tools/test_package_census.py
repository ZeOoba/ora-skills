#!/usr/bin/env python3
"""Tests for settlement-basis-extraction/scripts/package_census.py. Run: python tools/test_package_census.py"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "settlement-basis-extraction", "scripts"))
import package_census as pc  # noqa: E402

try:
    import fitz
except ImportError:  # pragma: no cover
    fitz = None


def make_pdf(path, pages):
    """pages: list of text strings ('' = blank page, which has no text layer)."""
    d = fitz.open()
    for t in pages:
        p = d.new_page()
        if t:
            p.insert_text((72, 72), t)
    d.save(path)
    d.close()


@unittest.skipIf(fitz is None, "PyMuPDF not installed")
class Census(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.long_text = "Settlement statement line item " * 8

    def test_text_scan_and_partial_are_classified(self):
        make_pdf(os.path.join(self.dir, "text.pdf"), [self.long_text, self.long_text])
        make_pdf(os.path.join(self.dir, "scan.pdf"), ["", ""])
        make_pdf(os.path.join(self.dir, "mixed.pdf"), [self.long_text, ""])
        by = {r["path"]: r["status"] for r in pc.census(self.dir)}
        self.assertEqual(by["text.pdf"], "TEXT")
        self.assertEqual(by["scan.pdf"], "IMAGE-ONLY")
        self.assertEqual(by["mixed.pdf"], "PARTIAL")

    def test_existing_twin_is_recognised_and_not_listed_as_original(self):
        make_pdf(os.path.join(self.dir, "deed.pdf"), [""])
        make_pdf(os.path.join(self.dir, "deed (OCR).pdf"), [self.long_text])
        rows = pc.census(self.dir)
        self.assertEqual([r["path"] for r in rows], ["deed.pdf"])
        self.assertTrue(rows[0]["has_twin"])

    def test_unreadable_pdf_is_reported_not_raised(self):
        with open(os.path.join(self.dir, "bad.pdf"), "wb") as f:
            f.write(b"not a pdf")
        rows = pc.census(self.dir)
        self.assertEqual(rows[0]["status"], "UNREADABLE")

    def test_render_counts_scans_without_twin(self):
        make_pdf(os.path.join(self.dir, "a.pdf"), [""])
        make_pdf(os.path.join(self.dir, "b.pdf"), [""])
        make_pdf(os.path.join(self.dir, "b (OCR).pdf"), [self.long_text])
        text = pc.render(pc.census(self.dir))
        self.assertIn("1 scan(s) without an OCR twin", text)

    def test_sampling_reads_only_the_first_pages(self):
        make_pdf(os.path.join(self.dir, "long.pdf"), [""] * 30)
        row = pc.census(self.dir)[0]
        self.assertEqual(row["pages"], 30)
        self.assertEqual(row["sample_chars"], 0)


class FactBase(unittest.TestCase):
    def write(self, obj):
        fd, p = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f)
        return p

    def test_flagged_fields_are_listed_and_unverified_without_a_read(self):
        p = self.write({"_meta": {}, "loan": {"lender": {"value": "x", "status": "NOT FOUND"}, "rate": {"status": "CONFIRMED"}},
                        "ownership": {"pct": {"status": "INFERRED (from OA)"}}})
        fb = pc.scan_factbase(p)
        self.assertEqual(sorted(x[0] for x in fb["flagged"]), ["loan.lender", "ownership.pct"])
        self.assertFalse(fb["corporate_folder_read"])
        self.assertIn("UNVERIFIED", pc.render([], fb))

    def test_recheck_recorded_is_recognised(self):
        p = self.write({"_meta": {"corporate_folder_read_2026-09-21": {"recheck_2026-09-21": {"result": "ok"}}}, "a": {"status": "CONFLICT"}})
        fb = pc.scan_factbase(p)
        self.assertTrue(fb["rechecked"])
        self.assertIn("recheck recorded", pc.render([], fb))

    def test_read_without_recheck_still_warns(self):
        p = self.write({"_meta": {"corporate_folder_read_2026-09-21": {"note": "not searched"}}, "a": {"status": "NOT FOUND"}})
        fb = pc.scan_factbase(p)
        self.assertTrue(fb["corporate_folder_read"])
        self.assertFalse(fb["rechecked"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
