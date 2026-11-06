"""Pre-send gate, round 3: merge-gate REFUTE of #225 (689ca6eb) and Gabriel's
in-turn rulings of 2026-11-06.

Ruling: DATA captions override the Form-of exemption -- a rent roll, legal
description, leases / schedule of leases, property description (and similar data
exhibits) BLOCK on blanks even when captioned "Form of". Real forms (deed,
assignment, estoppel, bill of sale, notice letters ...) stay exempt.

  (1) ReDoS: venue matching is linear; a 10k-char venue-looking line is judged fast
  (2) a Form-of region ends at any heading-like block (EXHIBIT / SCHEDULE / ANNEX /
      APPENDIX / ATTACHMENT + id, incl. EXHIBIT "D" and EXHIBIT D:)
  (3) caption = FIRST non-blank block after the heading (spacers, page breaks and a
      "to Purchase Agreement" heading continuation skipped; soft breaks joined)
  (4) party labels / return-to / entity lines / bare venue lines are exempt only in
      a signature-block context with nothing after the blank; value words block
      even without a colon
  (5) notary acknowledgment forms used in OH / IN / MD / MO / KS / WI / TN

Self-contained fixture builder; D8 constraints; synthetic text; stdlib only.

Run: python deal-execution/tests/test_audit_completeness_rulings3.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_completeness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_completeness_rulings3_ut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ac = _load_module()

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
LOREM = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
         "tempor incididunt ut labore et dolore magna aliqua.")


def _r(text):
    return '<w:r><w:t xml:space="preserve">{}</w:t></w:r>'.format(escape(text))


def P(text):
    return "<w:p>{}</w:p>".format(_r(text))


def BR(*lines):
    return "<w:p>{}</w:p>".format("<w:r><w:br/></w:r>".join(_r(t) for t in lines))


PAGEBREAK = '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def CELL(*paras):
    return "<w:tc>{}</w:tc>".format("".join(paras))


def TBL(rows):
    def cell(c):
        if c.startswith("<w:tc"):
            return c
        return "<w:tc>{}</w:tc>".format(c if c.startswith("<w:p") else P(c))
    return "<w:tbl>{}</w:tbl>".format("".join(
        "<w:tr>{}</w:tr>".format("".join(cell(c) for c in row)) for row in rows))


def write_docx(path, blocks):
    xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="{}"><w:body>{}<w:sectPr/></w:body></w:document>'
           ).format(W_NS, "".join(blocks))
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", xml)
    return path


BODY = [P("PURCHASE AND SALE AGREEMENT"),
        P("1. Property. Seller sells the Property described in Exhibit A; the closing "
          "documents are Exhibit B."),
        P("2. Purchase Price. The Purchase Price is One Dollar, payable per Section 1.")]
SIG = [P("IN WITNESS WHEREOF, the parties have executed this Agreement."),
       P("SELLER: By: ______________________"),
       P("PURCHASER: By: ______________________")]
EXA = [P("EXHIBIT A"), P("(Legal Description)"), P(LOREM)]
DEED_BODY = [P(LOREM), P("Grantee: ______________"), P("Consideration: $__________"),
             P("Instrument No. __________")]


def data_exhibit(*content):
    return BODY + SIG + EXA + [P("EXHIBIT B"), P("(Closing Certificate)"),
                               P(LOREM)] + list(content)


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


# ------------------------------------------------------------------ (1) ReDoS
class TestNoCatastrophicBacktracking(_Base):
    def test_long_venue_looking_line_is_fast(self):
        line = ("State of Ohio County of Lorem " * 340)[:10000] + " Parcel ________ ,"
        self.assertGreaterEqual(len(line), 10000)
        t0 = time.perf_counter()
        self.assertFalse(ac._is_signature_line(line, False))
        self.assertLess(time.perf_counter() - t0, 0.1)

    def test_long_venue_looking_line_in_a_document_is_fast_and_blocks(self):
        line = ("State of Ohio County of Lorem " * 340)[:10000] + " Parcel ________ ,"
        t0 = time.perf_counter()
        r = self.audit(data_exhibit(P(line)))
        self.assertLess(time.perf_counter() - t0, 0.5)
        self.assertTrue(r["blocking"])


# ------------------------------------------------------------------ (2) region end
class TestFormRegionEndsAtNextHeadingLikeBlock(_Base):
    def form_then(self, *tail):
        return BODY + SIG + EXA + [P("EXHIBIT B"), P("Form of Assignment"), P(LOREM)] + list(tail)

    def test_schedule_after_last_form_exhibit_blocks(self):
        for heading in ("SCHEDULE 1", "Schedule A", 'EXHIBIT "C"', "EXHIBIT C:", "ANNEX 1",
                        "Appendix A", "ATTACHMENT 1", "Schedule 1 – Rent Roll"):
            with self.subTest(heading=heading):
                r = self.audit(self.form_then(P(heading), P("Rent Roll"),
                                              TBL([["Tenant", "Rent"], ["Tenant One", "$______"]])))
                self.assertEqual(r["form_exhibits"], ["B"])
                self.assertEqual(len(r["body_blanks"]), 1)
                self.assertTrue(r["blocking"])

    def test_form_blanks_before_the_heading_like_block_stay_exempt(self):
        r = self.audit(self.form_then(P("Grantee: ________"), P("SCHEDULE 1"), P(LOREM)))
        self.assertEqual(r["body_blanks"], [])
        self.assertEqual(len(r["form_blanks"]), 1)
        self.assertFalse(r["blocking"])

    # (round 4: a block opening with "Exhibit A ..." now ends the region -- see
    # test_audit_completeness_rulings4.py, fail-closed)


# ------------------------------------------------------------------ (3) caption
class TestCaption(_Base):
    def deed(self, *caption_blocks):
        return BODY + SIG + EXA + [P("EXHIBIT B")] + list(caption_blocks) + DEED_BODY

    def test_form_caption_variants_are_exempt(self):
        cases = {
            "spacer then caption": [P(""), P("FORM OF LIMITED WARRANTY DEED")],
            "two spacers": [P(""), P(""), P("FORM OF LIMITED WARRANTY DEED")],
            "heading continuation": [P("to Purchase and Sale Agreement"), P(""),
                                     P("FORM OF LIMITED WARRANTY DEED")],
            "page break then spacer": [PAGEBREAK, P(""), P("FORM OF LIMITED WARRANTY DEED")],
            "[FORM OF] prefix": [P("[FORM OF] LIMITED WARRANTY DEED")],
            "(Form) suffix": [P("Limited Warranty Deed (Form)")],
            "soft break": [BR("FORM OF", "LIMITED WARRANTY DEED")],
            "Exhibit B - Form of": [P("Exhibit B – Form of Limited Warranty Deed")],
            "Exhibit B to Agreement: Form of": [P("Exhibit B to Purchase Agreement: Form of Deed")],
            "nbsp": [P("Form of Limited Warranty Deed")],
        }
        for label, caption in cases.items():
            with self.subTest(case=label):
                r = self.audit(self.deed(*caption))
                self.assertEqual(r["form_exhibits"], ["B"])
                self.assertEqual(r["body_blanks"], [])
                self.assertFalse(r["blocking"])

    def test_heading_table_with_spacer_row_and_form_caption(self):
        blocks = BODY + SIG + EXA + [TBL([["EXHIBIT B"], [""], ["FORM OF LIMITED WARRANTY DEED"]])] + DEED_BODY
        r = self.audit(blocks)
        self.assertEqual(r["form_exhibits"], ["B"])
        self.assertFalse(r["blocking"])

    def test_rejected_and_data_captions_block(self):
        for caption in ("Form of", "Form of payment: wire transfer", "Rent Roll (Form of Deed attached)",
                        "(Form of) Rent Roll", "Exhibit B – Formation of Title", "Form of Rent Roll",
                        "FORM OF RENT ROLL", "Form of legal description to be conformed to the Title Commitment",
                        "Form of Property Description", "Form of Schedule of Leases", "Form of Leases",
                        "Form of Lease Schedule", "Legal Description (Form of Deed attached)",
                        "LIMITED WARRANTY DEED"):
            with self.subTest(caption=caption):
                r = self.audit(self.deed(P(caption)))
                self.assertEqual(r["form_exhibits"], [])
                self.assertTrue(r["blocking"])

    def test_real_form_nouns_with_leases_stay_forms(self):
        for caption in ("Form of Assignment and Assumption of Leases", "Form of Tenant Estoppel Certificate",
                        "Form of Bill of Sale", "Form of Notice Letter to Tenants"):
            with self.subTest(caption=caption):
                r = self.audit(self.deed(P(caption)))
                self.assertEqual(r["form_exhibits"], ["B"])
                self.assertFalse(r["blocking"])

    def test_only_the_first_non_blank_block_is_the_caption(self):
        r = self.audit(self.deed(P("Rent Roll"), P("Form of rent roll as certified by Seller at Closing.")))
        self.assertEqual(r["form_exhibits"], [])
        self.assertTrue(r["blocking"])


# ------------------------------------------------------------------ (4) context / value words
class TestContextAndValueWords(_Base):
    CONTEXT_LINES = ["Tenant: ________", "Landlord: ________", "Seller: ________", "Grantee: ________",
                     "Assignee: ________", "Return to: ________", "After recording return to: ________",
                     "Send tax statements to: ________", "________, a ________ limited liability company",
                     "________, an Ohio limited liability company"]
    VENUE_LINES = ["STATE OF ________", "COUNTY OF ________"]
    BLOCK_LINES = ["County of Lorem Parcel No. ________", "State of Ohio Lot ________ Example Park",
                   "Signed: ________ Base Rent ________", "Name: ________ Suite ________",
                   "Its: ________; Lease commencement ________", "Title: Fee Simple, Parcel No. ________",
                   "Witness: ________ and Parcel ________", "Notary Public ________ Rent ________",
                   "Print: ________ Annual Rent ________ Dollars", "By: ________ Square Feet ________",
                   "Tenant: Tenant One Suite: ________", "Dated ________",
                   "Effective Date: ________", "Monthly Rent: ________", "Suite ________",
                   "ASSIGNOR: ________, a ________ limited liability company",
                   "Tenant: ________ Base Rent ________", "Seller: ________ (to be confirmed)"]

    def test_context_lines_block_when_alone(self):
        for line in self.CONTEXT_LINES:
            with self.subTest(line=line):
                r = self.audit(data_exhibit(P(line)))
                self.assertEqual(len(r["body_blanks"]), 1)
                self.assertTrue(r["blocking"])

    def test_context_lines_are_exempt_inside_a_signature_block(self):
        for line in self.CONTEXT_LINES:
            with self.subTest(line=line):
                r = self.audit(data_exhibit(P("ACKNOWLEDGED:"), P(line), P("By: ________"),
                                            P("Name: ________")))
                self.assertEqual(r["body_blanks"], [])
                self.assertFalse(r["blocking"])

    def test_party_and_entity_lines_need_a_signature_cue_not_a_notary_cue(self):
        for line in self.CONTEXT_LINES:
            with self.subTest(line=line):
                r = self.audit(data_exhibit(P("Notary Public"), P(line),
                                            P("My commission expires: ________")))
                self.assertEqual(len(r["body_blanks"]), 1)
                self.assertTrue(r["blocking"])

    def test_bare_venue_lines_need_a_notary_cue(self):
        for line in self.VENUE_LINES:
            with self.subTest(line=line, cue="notary"):
                r = self.audit(data_exhibit(P(line), P(") ss:"),
                                            P("Acknowledged before me this ___ day of ________, 20__.")))
                self.assertEqual(r["body_blanks"], [])
                self.assertFalse(r["blocking"])
            with self.subTest(line=line, cue="signature only"):
                r = self.audit(data_exhibit(P(line), P("By: ________"), P("Name: ________")))
                self.assertEqual(len(r["body_blanks"]), 1)
                self.assertTrue(r["blocking"])
            with self.subTest(line=line, cue="none"):
                self.assertTrue(self.audit(data_exhibit(P(line)))["blocking"])

    def test_value_lines_block_even_inside_a_signature_block(self):
        for line in self.BLOCK_LINES:
            with self.subTest(line=line):
                r = self.audit(data_exhibit(P(line), P("By: ________"), P("Name: ________")))
                self.assertEqual(len(r["body_blanks"]), 1)
                self.assertTrue(r["blocking"])

    def test_bare_rule_in_two_column_signature_table_is_exempt(self):
        sigt = TBL([[CELL(P("ASSIGNOR:"), P("Lorem Holdings LLC"), P("By: ______"), P("Name: ______")),
                     CELL(P("ASSIGNEE:"), P("______"), P("By: ______"), P("Name: ______"))]])
        r = self.audit(data_exhibit(sigt))
        self.assertEqual(r["body_blanks"], [])
        self.assertFalse(r["blocking"])

    def test_bare_rule_in_a_rent_roll_cell_still_blocks(self):
        r = self.audit(data_exhibit(TBL([["Tenant", "Suite"], ["Tenant One", "________"]])))
        self.assertEqual(len(r["body_blanks"]), 1)
        self.assertTrue(r["blocking"])


# ------------------------------------------------------------------ (5) notary forms
NOTARY = {
    "OH": ["STATE OF OHIO )", ") ss:", "COUNTY OF ________ )",
           "The foregoing instrument was acknowledged before me this ___ day of ________, 20__, by "
           "________, the ________ of Lorem Holdings LLC, an Ohio limited liability company, on behalf "
           "of the company.", "________________________", "Notary Public", "My commission expires: ________"],
    "OH-statutory": ["STATE OF OHIO", ") ss:", "COUNTY OF ________",
                     "The foregoing instrument was acknowledged before me this ________ (date) by ________ "
                     "(name of officer), ________ (title of officer) of ________ (name of company), a "
                     "________ (state) limited liability company, on behalf of the company.",
                     "________________________", "Notary Public"],
    "IN": ["STATE OF INDIANA )", ") SS:", "COUNTY OF ________ )",
           "Before me, a Notary Public in and for said County and State, personally appeared ________, "
           "who acknowledged the execution of the foregoing instrument.",
           "Witness my hand and Notarial Seal this ___ day of ________, 20__.",
           "________________________, Notary Public", "My Commission Expires ________",
           "County of Residence: ________", "Commission No.: ________",
           "This instrument prepared by ________, Attorney at Law.",
           "I affirm, under the penalties for perjury, that I have taken reasonable care to redact each "
           "Social Security number in this document, unless required by law. ________"],
    "MD": ["STATE OF MARYLAND, COUNTY OF ________, TO WIT:",
           "I HEREBY CERTIFY that on this ___ day of ________, 20__, before me, the subscriber, a Notary "
           "Public of the State aforesaid, personally appeared ________, who acknowledged himself to be "
           "the ________ of Lorem Holdings LLC.", "AS WITNESS my hand and Notarial Seal.",
           "________________________", "Notary Public", "My Commission Expires: ________"],
    "MO": ["STATE OF MISSOURI )", ") ss.", "COUNTY OF ________ )",
           "On this ___ day of ________, 20__, before me appeared ________, to me personally known, who, "
           "being by me duly sworn, did say that he is the ________ of Lorem Holdings LLC.",
           "IN TESTIMONY WHEREOF, I have hereunto set my hand and affixed my official seal this ___ day "
           "of ________, 20__.", "________________________ (Notary Seal)", "My term expires: ________"],
    "KS": ["STATE OF KANSAS )", ") ss.", "COUNTY OF ________ )",
           "This instrument was acknowledged before me on ________, 20__, by ________ as ________ of "
           "Lorem Holdings LLC.", "________________________", "Notary Public",
           "My appointment expires: ________"],
    "WI": ["STATE OF WISCONSIN )", ") ss.", "________ COUNTY )",
           "Personally came before me on ________, 20__, the above-named ________, to me known to be the "
           "person who executed the foregoing instrument and acknowledged the same.",
           "________________________", "Notary Public, State of Wisconsin",
           "My commission (is permanent) (expires: ________)"],
    "TN": ["STATE OF TENNESSEE )", "COUNTY OF ________ )",
           "Personally appeared before me, the undersigned, a Notary Public in and for said State and "
           "County, ________, with whom I am personally acquainted, and who acknowledged that he "
           "executed the within instrument.",
           "Given under my hand and seal at office this ___ day of ________, 20__.",
           "________________________", "Notary Public", "My Commission Expires: ________"],
}


class TestStateNotaryForms(_Base):
    def test_state_acknowledgments_do_not_block(self):
        for state, lines in NOTARY.items():
            with self.subTest(state=state):
                r = self.audit(data_exhibit(*[P(l) for l in lines]))
                self.assertEqual([b["context"][:40] for b in r["body_blanks"]], [])
                self.assertFalse(r["blocking"])

    def test_value_blank_inside_a_notary_block_still_blocks(self):
        for state, lines in NOTARY.items():
            with self.subTest(state=state):
                r = self.audit(data_exhibit(*([P(l) for l in lines] + [P("Consideration: ________ Dollars")])))
                self.assertEqual(len(r["body_blanks"]), 1)
                self.assertTrue(r["blocking"])


if __name__ == "__main__":
    unittest.main()
