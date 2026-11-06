"""Skeleton-table THIN tests for deal-execution/scripts/audit_completeness.py (A-2).

Finding completeness-empty-table-populated: an exhibit whose only content is a table
with a header row and no data rows (a blank rent roll or schedule) counted as
populated and was never flagged, because THIN required `not tables`. A-2 flags it as
advisory THIN. Blocking semantics (populated / empty / blocking) are unchanged, and
the regression cases below pin that.

Self-contained on purpose (its own minimal fixture builder) so this branch does not
depend on the A-1 characterization suite (test_audit_completeness.py).

Constraints (eval plan D8): main() is never called without a path argument, every
main() call runs under redirect_stdout/redirect_stderr, no assertion message includes
captured output, and fixtures are synthetic only. Stdlib only.

Run: python deal-execution/tests/test_audit_completeness_thin.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_completeness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_completeness_thin_under_test",
                                                  SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ac = _load_module()

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
LOREM = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
         "tempor incididunt ut labore et dolore magna aliqua.")
IMAGE_RUN = ('<w:r><w:drawing><a:graphic><a:graphicData><a:blip r:embed="rId9"/>'
             '</a:graphicData></a:graphic></w:drawing></w:r>')


def P(text: str) -> str:
    return '<w:p><w:r><w:t xml:space="preserve">{}</w:t></w:r></w:p>'.format(escape(text))


def P_DEL(text: str) -> str:
    return ('<w:p><w:del w:id="1" w:author="Reviewer"><w:r><w:delText xml:space="preserve">'
            '{}</w:delText></w:r></w:del></w:p>').format(escape(text))


def cell(content) -> str:
    """content: a string (text paragraph) or a raw-XML paragraph via ('xml', s)."""
    if isinstance(content, tuple):
        return "<w:tc>{}</w:tc>".format(content[1])
    return "<w:tc>{}</w:tc>".format(P(content))


def TBL(rows) -> str:
    return "<w:tbl>{}</w:tbl>".format("".join(
        "<w:tr>{}</w:tr>".format("".join(cell(c) for c in row)) for row in rows))


def write_docx(path: Path, blocks) -> Path:
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="{}" xmlns:a="{}" xmlns:r="{}"><w:body>{}<w:sectPr/>'
           '</w:body></w:document>').format(W_NS, A_NS, R_NS, "".join(blocks))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return path


BODY = [
    P("PURCHASE AND SALE AGREEMENT"),
    P("1. Leases. The Leases are listed on Exhibit A."),
    P("2. Purchase Price. The Purchase Price is One Dollar, payable per Section 1."),
]
SIG = [
    P("IN WITNESS WHEREOF, the parties have executed this Agreement."),
    P("SELLER: By: ______________________"),
]
HEADER = ["Suite", "Tenant", "Rent", "Expiration"]


def exhibit_blocks(*content):
    return BODY + SIG + [P("EXHIBIT A"), P("(Rent Roll)")] + list(content)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def doc(self, blocks) -> Path:
        return write_docx(self.tmp / "fixture.docx", blocks)

    def audit(self, blocks) -> dict:
        return ac.audit(self.doc(blocks))

    def run_main(self, path, *flags):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ac.main(["audit_completeness.py", str(path)] + list(flags))
        return rc, out.getvalue(), err.getvalue()

    def ex_a(self, r: dict) -> dict:
        self.assertEqual([e["letter"] for e in r["exhibits"]], ["A"])
        return r["exhibits"][0]

    def assert_gate_unchanged_populated(self, r: dict):
        """The A-2 change is advisory only: a table exhibit stays populated, never
        EMPTY, and adds no blocking defect."""
        e = self.ex_a(r)
        self.assertTrue(e["populated"])
        self.assertEqual(r["empty_exhibits"], [])
        self.assertFalse(r["blocking"])


class TestSkeletonTableIsThin(_Base):
    def test_header_only_table_exhibit_is_thin(self):
        r = self.audit(exhibit_blocks(TBL([HEADER])))
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assertTrue(self.ex_a(r)["thin"])
        self.assert_gate_unchanged_populated(r)

    def test_header_plus_blank_rows_is_thin(self):
        r = self.audit(exhibit_blocks(TBL([HEADER, ["", "", "", ""], ["", "", "", ""]])))
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assertEqual(self.ex_a(r)["data_tables"], 0)
        self.assert_gate_unchanged_populated(r)

    def test_struck_data_row_does_not_count_as_data(self):
        struck = ("xml", P_DEL("100"))
        r = self.audit(exhibit_blocks(TBL([HEADER, [struck, struck, struck, struck]])))
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assert_gate_unchanged_populated(r)

    def test_image_only_data_row_is_thin_advisory(self):
        # Validator defect: pin the image-in-table case. Chosen behavior: a row holding
        # only an image has no text, so the table is still a skeleton and gets the
        # advisory THIN -- consistent with an image-only exhibit, which is already
        # THIN. populated/blocking do not move.
        img = ("xml", "<w:p>{}</w:p>".format(IMAGE_RUN))
        r = self.audit(exhibit_blocks(TBL([HEADER, [img, "", "", ""]])))
        e = self.ex_a(r)
        self.assertEqual(e["images"], 1)
        self.assertTrue(e["thin"])
        self.assert_gate_unchanged_populated(r)

    def test_single_row_table_is_thin_advisory_false_positive(self):
        # Accepted advisory false positive: a one-row table that IS the data (no
        # header) cannot be told apart from a header-only skeleton.
        r = self.audit(exhibit_blocks(TBL([["Parcel 000-000-000", "Lorem ipsum"]])))
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assert_gate_unchanged_populated(r)


class TestPopulatedTablesStayOk(_Base):
    def test_multi_row_populated_table_exhibit_stays_ok(self):
        tbl = TBL([HEADER, ["100", "Tenant One", "1,000", "2030-01-31"],
                   ["200", "Tenant Two", "2,000", "2031-06-30"]])
        r = self.audit(exhibit_blocks(tbl))
        e = self.ex_a(r)
        self.assertFalse(e["thin"])
        self.assertEqual(e["data_tables"], 1)
        self.assertEqual(r["thin_exhibits"], [])
        self.assert_gate_unchanged_populated(r)

    def test_skeleton_table_with_substantive_prose_is_not_thin(self):
        r = self.audit(exhibit_blocks(P(LOREM), TBL([HEADER])))
        self.assertFalse(self.ex_a(r)["thin"])
        self.assert_gate_unchanged_populated(r)

    def test_one_populated_table_among_skeletons_is_not_thin(self):
        r = self.audit(exhibit_blocks(TBL([HEADER]),
                                      TBL([HEADER, ["100", "Tenant One", "1", "2"]])))
        e = self.ex_a(r)
        self.assertEqual((e["tables"], e["data_tables"]), (2, 1))
        self.assertFalse(e["thin"])

    def test_short_prose_without_table_is_still_thin(self):
        r = self.audit(exhibit_blocks(P("Parcel 000-000-000.")))
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assertEqual(self.ex_a(r)["data_tables"], 0)


def ROW(cells, tr_pr="") -> str:
    return "<w:tr>{}{}</w:tr>".format(tr_pr, "".join(cell(c) for c in cells))


DATA = [["100", "Tenant One", "1,000", "2030-01-31"],
        ["200", "Tenant Two", "2,000", "2031-06-30"]]


class TestWrappedAndNestedRows(_Base):
    """REFUTE (d): rows wrapped in content controls / custom XML, or data held in a
    nested table, are real data -- a populated rent roll must not read as THIN.
    populated and blocking must be identical to the plain-table case."""

    def _check_populated_ok(self, tbl):
        r = self.audit(exhibit_blocks(tbl))
        e = self.ex_a(r)
        self.assertEqual(e["data_tables"], 1)
        self.assertFalse(e["thin"])
        self.assertEqual(r["thin_exhibits"], [])
        self.assert_gate_unchanged_populated(r)
        plain = self.audit(exhibit_blocks(TBL([HEADER] + DATA)))
        self.assertEqual((r["blocking"], e["populated"], r["empty_exhibits"]),
                         (plain["blocking"], self.ex_a(plain)["populated"],
                          plain["empty_exhibits"]))

    def test_rows_inside_sdt_are_data(self):
        rows = "".join(ROW(d) for d in DATA)
        tbl = "<w:tbl>{}<w:sdt><w:sdtPr/><w:sdtContent>{}</w:sdtContent></w:sdt></w:tbl>" \
            .format(ROW(HEADER), rows)
        self._check_populated_ok(tbl)

    def test_rows_inside_custom_xml_are_data(self):
        rows = "".join(ROW(d) for d in DATA)
        tbl = '<w:tbl>{}<w:customXml w:element="rows">{}</w:customXml></w:tbl>' \
            .format(ROW(HEADER), rows)
        self._check_populated_ok(tbl)

    def test_data_in_nested_table_is_data(self):
        inner = TBL([HEADER] + DATA)
        tbl = "<w:tbl>{}</w:tbl>".format(ROW([("xml", "<w:p/>" + inner)]))
        self._check_populated_ok(tbl)

    def test_skeleton_rows_inside_sdt_still_thin(self):
        tbl = ("<w:tbl><w:sdt><w:sdtContent>{}{}</w:sdtContent></w:sdt></w:tbl>"
               .format(ROW(HEADER), ROW(["", "", "", ""])))
        r = self.audit(exhibit_blocks(tbl))
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assert_gate_unchanged_populated(r)


class TestMultiRowHeader(_Base):
    """REFUTE (e): a title row plus a column row with no data is still a skeleton,
    when the second header row is unambiguous (w:tblHeader repeat-header marker, or
    a first row that is one cell merged across columns)."""

    def test_repeat_header_rows_are_not_data(self):
        hdr = "<w:trPr><w:tblHeader/></w:trPr>"
        tbl = "<w:tbl>{}{}</w:tbl>".format(ROW(["Rent Roll"], hdr), ROW(HEADER, hdr))
        r = self.audit(exhibit_blocks(tbl))
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assert_gate_unchanged_populated(r)

    def test_merged_title_row_then_column_row_is_skeleton(self):
        title = ('<w:tr><w:tc><w:tcPr><w:gridSpan w:val="4"/></w:tcPr>{}</w:tc></w:tr>'
                 .format(P("Rent Roll")))
        tbl = "<w:tbl>{}{}</w:tbl>".format(title, ROW(HEADER))
        r = self.audit(exhibit_blocks(tbl))
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assert_gate_unchanged_populated(r)

    def test_merged_title_row_with_data_is_ok(self):
        title = ('<w:tr><w:tc><w:tcPr><w:gridSpan w:val="4"/></w:tcPr>{}</w:tc></w:tr>'
                 .format(P("Rent Roll")))
        tbl = "<w:tbl>{}{}{}</w:tbl>".format(title, ROW(HEADER), ROW(DATA[0]))
        r = self.audit(exhibit_blocks(tbl))
        self.assertEqual(r["thin_exhibits"], [])
        self.assert_gate_unchanged_populated(r)

    def test_malformed_grid_span_does_not_crash(self):
        title = ('<w:tr><w:tc><w:tcPr><w:gridSpan w:val="x"/></w:tcPr>{}</w:tc></w:tr>'
                 .format(P("Rent Roll")))
        p = self.doc(exhibit_blocks("<w:tbl>{}{}</w:tbl>".format(title, ROW(HEADER))))
        rc, _, _ = self.run_main(p)
        self.assertEqual(rc, 0)

    def test_single_column_list_second_row_is_data(self):
        # Unmerged single-cell first row is an ordinary header, not a title: the
        # next row is data.
        r = self.audit(exhibit_blocks(TBL([["Permitted Exceptions"], [LOREM]])))
        self.assertEqual(r["thin_exhibits"], [])

    def test_unmarked_two_row_header_is_not_detected(self):
        # Disclosed limit: two plain header rows with no tblHeader marker and no
        # merged title cell cannot be told apart from header + one data row.
        r = self.audit(exhibit_blocks(TBL([["Rent Roll", "", "", ""], HEADER])))
        self.assertEqual(r["thin_exhibits"], [])
        self.assert_gate_unchanged_populated(r)


class TestReviewRound2(_Base):
    """Independent review of 230f16cf: C6 crash on a non-ASCII-digit gridSpan, C4
    surviving prose_chars->chars mutant, C8 exponential nesting cost."""

    def test_superscript_digit_grid_span_does_not_crash(self):
        # C6: "²".isdigit() is True but int("²") raises ValueError -- an uncaught
        # crash exits 1 and reads as BLOCKING. A malformed span must count as 1.
        title = ('<w:tr><w:tc><w:tcPr><w:gridSpan w:val="²"/></w:tcPr>{}</w:tc></w:tr>'
                 .format(P("Rent Roll")))
        p = self.doc(exhibit_blocks("<w:tbl>{}{}</w:tbl>".format(
            title, ROW(["100", "Tenant One", "1,000", "2030-01-31"]))))
        rc, _, err = self.run_main(p)
        self.assertEqual(rc, 0)
        self.assertEqual(err, "")
        r = ac.audit(p)
        self.assertEqual(self.ex_a(r)["data_tables"], 1)
        self.assertFalse(r["blocking"])

    def test_other_non_ascii_digit_spans_do_not_crash(self):
        for val in ("¹", "₂", "①", "", "-1", "0", " 2 ", "x"):
            with self.subTest(val=val):
                title = ('<w:tr><w:tc><w:tcPr><w:gridSpan w:val="{}"/></w:tcPr>{}</w:tc>'
                         '</w:tr>').format(escape(val, {'"': "&quot;"}), P("Rent Roll"))
                p = self.doc(exhibit_blocks("<w:tbl>{}{}</w:tbl>".format(title,
                                                                         ROW(HEADER))))
                self.assertEqual(self.run_main(p)[0], 0)

    def test_long_header_skeleton_table_is_thin(self):
        # C4: the table's own text counts toward `chars`; THIN for a skeleton table
        # must key off prose_chars, so a 60+-char header row alone is still THIN.
        long_header = ["Tenant Legal Name", "Suite", "Rentable SF", "Lease Commencement",
                       "Lease Expiration", "Monthly Base Rent", "Security Deposit"]
        self.assertGreaterEqual(len("".join(long_header)), 60)
        r = self.audit(exhibit_blocks(TBL([long_header])))
        e = self.ex_a(r)
        self.assertGreaterEqual(e["text_chars"], 60)
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assert_gate_unchanged_populated(r)

    def test_deeply_nested_dataless_tables_are_fast(self):
        # C8: data detection must not be exponential in nesting depth.
        inner = P("")
        for _ in range(22):
            inner = "<w:tbl>{}</w:tbl>".format(ROW([("xml", P("hdr") + inner)]))
        p = self.doc(exhibit_blocks(inner))
        t0 = time.perf_counter()
        r = ac.audit(p)
        self.assertLess(time.perf_counter() - t0, 1.0)
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assertFalse(r["blocking"])


class TestBlockingUnchanged(_Base):
    def test_caption_only_exhibit_is_still_empty_and_blocks(self):
        p = self.doc(exhibit_blocks())
        r = ac.audit(p)
        self.assertEqual(r["empty_exhibits"], ["A"])
        self.assertTrue(r["blocking"])
        self.assertEqual(self.run_main(p)[0], 1)

    def test_skeleton_table_document_exits_0(self):
        p = self.doc(exhibit_blocks(TBL([HEADER])))
        self.assertEqual(self.run_main(p)[0], 0)

    def test_skeleton_table_plus_body_blank_still_blocks(self):
        blocks = BODY + [P("3. Deposit. The Deposit is $__________.")] + SIG + \
            [P("EXHIBIT A"), TBL([HEADER])]
        p = self.doc(blocks)
        r = ac.audit(p)
        self.assertTrue(r["blocking"])
        self.assertEqual(self.run_main(p)[0], 1)


class TestOutput(_Base):
    def test_json_carries_additive_data_tables_key(self):
        p = self.doc(exhibit_blocks(TBL([HEADER])))
        rc, out, _ = self.run_main(p, "--json")
        self.assertEqual(rc, 0)
        e = json.loads(out)["exhibits"][0]
        self.assertEqual((e["tables"], e["data_tables"], e["thin"]), (1, 0, True))

    def test_render_explains_skeleton_table(self):
        p = self.doc(exhibit_blocks(TBL([HEADER])))
        rc, out, _ = self.run_main(p)
        self.assertEqual(rc, 0)
        self.assertTrue("THIN    <-- verify sufficiency" in out, "THIN flag missing")
        self.assertTrue("no data rows" in out, "skeleton-table advice line missing")
        self.assertFalse("recordable" in out,
                         "prose-THIN advice printed for a skeleton-table exhibit")


if __name__ == "__main__":
    unittest.main()
