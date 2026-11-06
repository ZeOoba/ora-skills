"""Gabriel's 2026-11-06 rulings on the outbound-PSA pre-send gate, round 2.

Covers the merge-gate REFUTE of #221 (a7d9d2e0) and Gabriel's second in-turn ruling
of 2026-11-06: exhibits captioned "Form of ..." are templates completed at closing,
so their blanks never block; data exhibits (legal description, rent roll,
schedules) still block.

  (1) exhibit ranges after the signature page are built only from headings at or
      after IN WITNESS WHEREOF (an exhibit list or exhibit placed before it must not
      swallow the signature page)
  (2) "Form of ..." caption exemption (post-signature exhibits)
  (3) false passes: venue lines, unanchored notary wording, other value labels on a
      signature line, w:br line splitting, bare underscores in table cells, blanks in
      a heading table
  (4) false blocks: ORA signature / notary / recording-form lines
  (5) DMS stamp or content-control placeholder as the only table text -> EMPTY grid

Self-contained (own minimal fixture builder). Constraints (eval plan D8): main() is
never called without a path argument, every main() call is captured, no assertion
message includes captured output, fixtures are synthetic. Stdlib only.

Run: python deal-execution/tests/test_audit_completeness_rulings.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_completeness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_completeness_rulings_ut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ac = _load_module()

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
LOREM = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
         "tempor incididunt ut labore et dolore magna aliqua.")


def _r(text):
    return '<w:r><w:t xml:space="preserve">{}</w:t></w:r>'.format(escape(text))


def P(text):
    return "<w:p>{}</w:p>".format(_r(text))


def BR(*lines):
    """One paragraph whose lines are separated by soft line breaks (w:br)."""
    return "<w:p>{}</w:p>".format("<w:r><w:br/></w:r>".join(_r(t) for t in lines))


def PDEL(text):
    return ('<w:p><w:del w:id="1" w:author="R"><w:r><w:delText xml:space="preserve">{}'
            '</w:delText></w:r></w:del></w:p>').format(escape(text))


def STRIKE(text):
    return '<w:p><w:r><w:rPr><w:strike/></w:rPr><w:t>{}</w:t></w:r></w:p>'.format(escape(text))


PLACEHOLDER = ('<w:p><w:sdt><w:sdtPr><w:showingPlcHdr/></w:sdtPr><w:sdtContent><w:r>'
               '<w:t>Click or tap here to enter text.</w:t></w:r></w:sdtContent></w:sdt></w:p>')


def TBL(rows):
    """rows: list of lists; a cell is a text string or raw paragraph XML ('<w:p...')."""
    def cell(c):
        return "<w:tc>{}</w:tc>".format(c if c.startswith("<w:p") else P(c))
    return "<w:tbl>{}</w:tbl>".format("".join(
        "<w:tr>{}</w:tr>".format("".join(cell(c) for c in row)) for row in rows))


def write_docx(path, blocks):
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="{}" xmlns:a="{}" xmlns:r="{}"><w:body>{}<w:sectPr/>'
           '</w:body></w:document>').format(W_NS, A_NS, R_NS, "".join(blocks))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return path


BODY = [
    P("PURCHASE AND SALE AGREEMENT"),
    P("1. Property. Seller sells the Property described in Exhibit A; the closing "
      "documents are Exhibit B."),
    P("2. Purchase Price. The Purchase Price is One Dollar, payable per Section 1."),
]
SIG = [
    P("IN WITNESS WHEREOF, the parties have executed this Agreement."),
    P("SELLER: By: ______________________"),
    P("PURCHASER: By: ______________________"),
]
EXA = [P("EXHIBIT A"), P("(Legal Description)"), P(LOREM)]


def data_exhibit(*content):
    """Exhibit B as a DATA exhibit (not a form), after the signature page."""
    return BODY + SIG + EXA + [P("EXHIBIT B"), P("(Schedule of Closing Deliveries)"),
                               P(LOREM)] + list(content)


def form_exhibit(caption, *content):
    return BODY + SIG + EXA + [P("EXHIBIT B"), P(caption), P(LOREM)] + list(content)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def doc(self, blocks):
        return write_docx(self.tmp / "fixture.docx", blocks)

    def audit(self, blocks):
        return ac.audit(self.doc(blocks))

    def rc(self, blocks):
        p = self.doc(blocks)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            return ac.main(["audit_completeness.py", str(p)])

    def exhibit(self, r, letter):
        for e in r["exhibits"]:
            if e["letter"] == letter:
                return e
        self.fail("exhibit {} not detected".format(letter))


# ---------------------------------------------------------------------- (1) structure
class TestSignaturePageNotSwallowed(_Base):
    def test_exhibit_list_before_signature_page_does_not_swallow_it(self):
        toc = TBL([["Exhibit A", "Legal Description"], ["Exhibit B", "Rent Roll"]])
        blocks = [toc] + BODY + SIG + EXA + [P("EXHIBIT B"), P("(Rent Roll)"), P(LOREM)]
        r = self.audit(blocks)
        self.assertEqual(r["body_blanks"], [])
        self.assertFalse(r["blocking"])
        self.assertEqual(self.rc(blocks), 0)

    def test_exhibits_before_signature_page_do_not_swallow_it(self):
        blocks = BODY + EXA + [P("EXHIBIT B"), P("(Rent Roll)"), P(LOREM)] + SIG
        r = self.audit(blocks)
        self.assertEqual(r["body_blanks"], [])
        self.assertEqual(len(r["signature_blanks"]), 2)
        self.assertFalse(r["blocking"])
        self.assertEqual(self.rc(blocks), 0)

    def test_post_signature_data_exhibit_still_blocks_after_a_front_exhibit_list(self):
        toc = TBL([["Exhibit A", "Legal Description"], ["Exhibit B", "Rent Roll"]])
        blocks = [toc] + BODY + SIG + EXA + [P("EXHIBIT B"), P("(Rent Roll)"),
                                             P("Allocated value: $__________")]
        r = self.audit(blocks)
        self.assertEqual(len(r["body_blanks"]), 1)
        self.assertTrue(r["blocking"])


# ---------------------------------------------------------------------- (2) Form of
class TestFormOfExemption(_Base):
    BLANKS = [P("Closing Date: ____________"), P("Monthly Base Rent is $__________."),
              P("Grantee: ______________, a ______________"), P("[TBD]")]

    def test_form_captions_are_exempt(self):
        for caption in ("Form of Deed", "(Form of Limited Warranty Deed)",
                        "FORM OF TENANT ESTOPPEL CERTIFICATE",
                        "Exhibit B – Form of Assignment and Assumption of Leases",
                        "Exhibit B - Form of Bill of Sale", "Form of"):
            with self.subTest(caption=caption):
                blocks = form_exhibit(caption, *self.BLANKS)
                r = self.audit(blocks)
                self.assertEqual(r["body_blanks"], [])
                self.assertEqual(r["form_exhibits"], ["B"])
                self.assertTrue(self.exhibit(r, "B")["form"])
                self.assertEqual(len(r["form_blanks"]), len(self.BLANKS))
                self.assertFalse(r["blocking"])
                self.assertEqual(self.rc(blocks), 0)

    def test_form_caption_in_a_heading_table_is_exempt(self):
        blocks = BODY + SIG + EXA + [TBL([["EXHIBIT B"], ["Form of Assignment"]]),
                                     P(LOREM)] + self.BLANKS
        r = self.audit(blocks)
        self.assertEqual(r["form_exhibits"], ["B"])
        self.assertFalse(r["blocking"])

    def test_data_captions_are_not_forms(self):
        for caption in ("Legal Description", "(Rent Roll)", "Schedule of Leases",
                        "The form of deed is attached", "Formation Documents",
                        "Form of Payment: $__________"):
            with self.subTest(caption=caption):
                r = self.audit(form_exhibit(caption, P("Closing Date: ____________")))
                self.assertEqual(r["form_exhibits"], [])
                self.assertTrue(r["blocking"])

    def test_form_word_later_in_the_exhibit_is_not_a_caption(self):
        # the caption window is the first two blocks after the heading only
        blocks = BODY + SIG + EXA + [P("EXHIBIT B"), P("(Rent Roll)"), P(LOREM),
                                     P("Form of Deed"), P("Closing Date: ________")]
        r = self.audit(blocks)
        self.assertEqual(r["form_exhibits"], [])
        self.assertTrue(r["blocking"])

    def test_form_exhibit_still_counts_toward_empty_grid_rule(self):
        blocks = BODY + SIG + EXA + [P("EXHIBIT B"), P("Form of Deed"), TBL([["", ""]])]
        r = self.audit(blocks)
        self.assertEqual(r["empty_exhibits"], ["B"])
        self.assertTrue(r["blocking"])

    def test_pre_signature_form_exhibit_is_unchanged_from_main(self):
        # Exhibits attached before IN WITNESS WHEREOF keep main's behaviour: their
        # blanks were and remain body blanks. This PR relaxes nothing main blocks.
        blocks = BODY + [P("EXHIBIT B"), P("Form of Deed"), P(LOREM),
                         P("Grantee: ______________")] + SIG + EXA
        r = self.audit(blocks)
        self.assertEqual(len(r["body_blanks"]), 1)
        self.assertTrue(r["blocking"])


# ---------------------------------------------------------------------- (3) false passes
class TestFalsePassesBlock(_Base):
    LINES = [
        "State of Ohio, County of Lorem, being Parcel No. ________",
        "County of Lorem, Parcel No. ________, legal description to be provided",
        "State of Formation: ________",
        "Base Rent: ________ per month (notary public)",
        "Notary Public fee and Purchase Price of ________ Dollars",
        "By: ________ Purchase Price: ________ Dollars",
        "Title: ________ Commencement Date: ________",
        "Witness: ________ Expiration Date: ________",
        'Date: ________ (the "Effective Date")',
        "Name: ________ (Purchaser)",
        "Closing Date: ________",
        "Purchase Price: $________",
        "Dated as of the Effective Date, the Rent is ________",
        "Acknowledged before me: Base Rent ________ (Seller)",
    ]

    def test_value_lines_in_a_data_exhibit_block(self):
        for line in self.LINES:
            for where, blk in (("paragraph", P(line)), ("table cell", TBL([[line]]))):
                with self.subTest(line=line, where=where):
                    r = self.audit(data_exhibit(blk))
                    self.assertEqual(len(r["body_blanks"]), 1)
                    self.assertTrue(r["blocking"])

    def test_soft_line_breaks_are_split_before_matching(self):
        r = self.audit(data_exhibit(BR("Date: ________",
                                       "Being Parcel No. ________ in Lorem County")))
        self.assertEqual(len(r["body_blanks"]), 1)
        self.assertTrue(r["blocking"])
        r = self.audit(data_exhibit(BR("By: ________", "Name: ________", "Title: ________")))
        self.assertEqual(r["body_blanks"], [])
        self.assertFalse(r["blocking"])

    def test_bare_underscores_in_a_table_cell_block(self):
        tbl = TBL([["Tenant", "Suite", "Monthly Rent"], ["Tenant One", "________", "________"]])
        r = self.audit(data_exhibit(tbl))
        self.assertEqual(len(r["body_blanks"]), 1)
        self.assertTrue(r["blocking"])

    def test_bare_signature_rule_as_a_paragraph_is_still_exempt(self):
        r = self.audit(data_exhibit(P("______________________")))
        self.assertEqual(r["body_blanks"], [])
        self.assertFalse(r["blocking"])

    def test_blank_inside_a_heading_table_blocks(self):
        blocks = BODY + SIG + EXA + [
            TBL([["EXHIBIT B"], ["Tenant", "Rent"], ["Tenant One", "Rent: $________ per month"]]),
            P("Rent roll certified by Seller as of the Effective Date and true in all respects.")]
        r = self.audit(blocks)
        self.assertEqual(len(r["body_blanks"]), 1)
        self.assertTrue(r["blocking"])

    def test_heading_paragraph_of_a_heading_table_is_not_scanned_as_a_blank(self):
        blocks = BODY + SIG + EXA + [TBL([["EXHIBIT B"], ["Schedule"]]), P(LOREM)]
        r = self.audit(blocks)
        self.assertEqual(r["body_blanks"], [])
        self.assertFalse(r["blocking"])


# ---------------------------------------------------------------------- (4) false blocks
class TestSignatureNotaryRecordingLinesExempt(_Base):
    LINES = [
        "Authorized Signatory: ________", "By ________", "By:________", "Its ________",
        "Name and Title: ________", "Name/Title: ________", "Date Signed: ________",
        "Print: ________", "Attest: ________", "ATTEST: ________, Secretary",
        "WITNESSES: ________", "Witness ________", "Signature ________ (Seal)",
        "________________________ (SEAL)", "(Seal) ________",
        "Grantor: ________", "Grantee: ________", "Seller: ________", "Purchaser: ________",
        "Buyer: ________", "Landlord: ________", "TENANT: ________", "Assignor: ________",
        "ASSIGNEE: ________",
        "ASSIGNOR: ________, a ________ limited liability company",
        "________, a ________ limited liability company",
        "________, an Ohio limited liability company",
        "____________________, a ____________________",
        "Notary Public ________", "________, Notary Public",
        "My commission expires: ________", "Commission Expires: ________",
        "My Commission Expiration: ________", "My term expires: ________",
        "My appointment expires: ________", "My County of Residence: ________",
        "Commission No.: ________", "Printed Name of Notary: ________",
        "Notary Printed Name: ________",
        "STATE OF ________ )", "COUNTY OF ________ )", "STATE OF OHIO ) ss: COUNTY OF ________ )",
        "STATE OF ________", "COUNTY OF ________ ) ss.",
        "Acknowledged before me this ___ day of ________, 20__.",
        "The foregoing instrument was acknowledged before me this ___ day of ________, "
        "20__, by ________, the ________ of ________.",
        "Before me, a Notary Public in and for said County and State, personally "
        "appeared ________",
        "On ________, before me, ________, personally appeared ________",
        "Personally appeared before me, ________, a Notary Public",
        "Sworn to before me this ___ day of ________",
        "Subscribed and sworn to before me this ___ day of ________",
        "Executed as of the ___ day of ________, 20__.",
        "Executed this ___ day of ____________, 20__.",
        "Dated as of ________, 20__",
        "This instrument prepared by: ________",
        "Send tax statements to: ________",
        "After recording return to: ________",
        "Receipt acknowledged this ___ day of ________, 20__",
    ]

    def test_lines_do_not_block_in_a_data_exhibit(self):
        for line in self.LINES:
            for where, blk in (("paragraph", P(line)), ("table cell", TBL([[line]]))):
                with self.subTest(line=line, where=where):
                    r = self.audit(data_exhibit(blk))
                    self.assertEqual(r["body_blanks"], [])
                    self.assertEqual(len(r["signature_blanks"]), 3)
                    self.assertFalse(r["blocking"])

    def test_dollar_is_never_exempt(self):
        for line in ("By: $________", "Notary Public ________ $", "Seller: $________"):
            with self.subTest(line=line):
                self.assertTrue(self.audit(data_exhibit(P(line)))["blocking"])


# ---------------------------------------------------------------------- (5) LOW
class TestGridContentEdgeCases(_Base):
    def grid_exhibit(self, tbl):
        return BODY + SIG + EXA + [P("EXHIBIT B"), P("(Rent Roll)"), tbl]

    def test_dms_stamp_only_grid_is_empty(self):
        r = self.audit(self.grid_exhibit(TBL([["15744530.v2", ""]])))
        self.assertEqual(r["empty_exhibits"], ["B"])
        self.assertTrue(r["blocking"])

    def test_content_control_placeholder_only_grid_is_empty(self):
        r = self.audit(self.grid_exhibit(TBL([[PLACEHOLDER, ""]])))
        self.assertEqual(r["empty_exhibits"], ["B"])
        self.assertTrue(r["blocking"])

    def test_formatted_strike_grid_stays_populated(self):
        # w:strike is formatting, not a tracked deletion: no ruling, unchanged.
        r = self.audit(self.grid_exhibit(TBL([[STRIKE("Tenant One"), STRIKE("4,500")]])))
        self.assertEqual(r["empty_exhibits"], [])

    def test_tracked_deletion_grid_is_empty(self):
        r = self.audit(self.grid_exhibit(TBL([[PDEL("Tenant One"), PDEL("4,500")]])))
        self.assertEqual(r["empty_exhibits"], ["B"])

    def test_populated_grid_with_a_stamp_cell_is_populated(self):
        r = self.audit(self.grid_exhibit(TBL([["Suite", "Tenant"], ["100", "Tenant One"],
                                               ["15744530.v2", ""]])))
        self.assertEqual(r["empty_exhibits"], [])
        self.assertFalse(r["blocking"])


if __name__ == "__main__":
    unittest.main()
