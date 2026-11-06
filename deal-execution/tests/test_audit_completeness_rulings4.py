"""Pre-send gate, round 4: final merge-gate review of #225 (054613d5), fix-then-merge.

  (1) C2  a Form-of region ends at any block opening with EXHIBIT / SCHEDULE / ANNEX /
          APPENDIX / ATTACHMENT / RIDER + id (no constraint on the rest of the line),
          or at a short block carrying a data caption (RENT ROLL, SCHEDULE OF LEASES)
  (2) C4a notary sentence forms (I hereby certify, Witness my hand, In testimony
          whereof, Given under my hand, Before me / On ... / Personally appeared,
          acknowledged, sworn) are exempt only next to a notary cue; more value words
  (3) C4b a signature cue is a signature label followed by a blank (not prose like
          "Its lease expires"); the same-cell window is 3 lines; context exemptions
          are off in data-captioned exhibits (a rent roll's "Tenant: ____" is a value)
  (4) C5  long acknowledgment sentences (TN TCA 66-22-107, MD / MO corporate) are not
          cut off by the 400-char cap
  (5) C9  cue lookup is linear within a table cell
  (6) C3  more data captions

Self-contained fixture builder; D8 constraints; synthetic text; stdlib only.

Run: python deal-execution/tests/test_audit_completeness_rulings4.py
"""
from __future__ import annotations

import importlib.util
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_completeness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_completeness_rulings4_ut", SCRIPT)
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
       P("SELLER: By: ______________________")]
EXA = [P("EXHIBIT A"), P("(Legal Description)"), P(LOREM)]
FORM_B = [P("EXHIBIT B"), P("Form of Assignment and Assumption of Leases"), P(LOREM),
          P("ASSIGNOR:"), P("By: ________")]
RENT_ROLL = TBL([["Tenant", "Suite", "Monthly Rent"], ["Tenant One", "100", "$________"]])
NOTARY_CUES = [P("STATE OF ________ )"), P("COUNTY OF ________ )")]
NOTARY_TAIL = [P("________"), P("Notary Public")]


def closing_cert(*content):
    """A non-form, non-data exhibit B after the signature page."""
    return BODY + SIG + EXA + [P("EXHIBIT B"), P("(Closing Certificate)"), P(LOREM)] + list(content)


def rent_roll_exhibit(*content):
    """A data exhibit B (rent roll) after the signature page."""
    return BODY + SIG + EXA + [P("EXHIBIT B"), P("Rent Roll"), P(LOREM)] + list(content)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def audit(self, blocks):
        return ac.audit(write_docx(self.tmp / "fixture.docx", blocks))


# ------------------------------------------------------------------ (1) C2 region end
class TestFormRegionEndsAtScheduleHeadings(_Base):
    HEADINGS = ["SCHEDULE 1", "SCHEDULE 1 - Rent Roll", "SCHEDULE 1 Rent Roll", "SCHEDULE 1\tRENT ROLL",
                "Schedule 1 (Rent Roll)", "Schedule 1 to Purchase Agreement", "SCHEDULE OF LEASES",
                "RENT ROLL", "Rent Schedule", "Exhibit A to Assignment",
                "Exhibit A to Assignment and Assumption of Leases", "Annex I", "Rider 1", "Attachment 1",
                "EXHIBIT C RENT ROLL", "Exhibit C, Rent Roll", "SCHEDULE 1.1", "Schedule 3.1(a)", "SCHEDULE I"]

    def test_rent_roll_after_any_schedule_heading_blocks(self):
        for h in self.HEADINGS:
            with self.subTest(heading=h):
                r = self.audit(BODY + SIG + EXA + FORM_B + [P(h), RENT_ROLL])
                self.assertEqual(r["form_exhibits"], ["B"])
                self.assertEqual(len(r["body_blanks"]), 1)
                self.assertTrue(r["blocking"])

    def test_exhibit_reference_sentence_ends_the_region_fail_closed(self):
        r = self.audit(BODY + SIG + EXA + FORM_B + [P("Exhibit A attached hereto describes the Land."),
                                                     P("Grantee: ________")])
        self.assertEqual(len(r["body_blanks"]), 1)
        self.assertTrue(r["blocking"])

    def test_form_body_before_the_end_stays_exempt(self):
        r = self.audit(BODY + SIG + EXA + FORM_B + [P("Grantee: ________"), P("SCHEDULE 1"), P(LOREM)])
        self.assertEqual(r["body_blanks"], [])
        self.assertFalse(r["blocking"])


# ------------------------------------------------------------------ (6) C3 data captions
class TestMoreDataCaptions(_Base):
    CAPTIONS = ["Form of Rent Schedule", "Form of Schedule of Leases", "Form of Description of Premises",
                "Form of Lease Schedule", "Form of Tenant Schedule", "Form of Schedule of Tenants",
                "Form of Tenant List", "Form of Rent Roll Certification", "Form of Certified Rent Roll",
                "Form of Lease Abstract", "Form of Legal Descr.", "Form of Property Legal Description",
                "Form of Premises Description", "Form of Land Description", "Form of Leases",
                "Form of Schedule of Service Contracts", "Form of Personal Property List",
                "Form of Permitted Exceptions"]

    def test_data_synonyms_override_form_of(self):
        for c in self.CAPTIONS:
            with self.subTest(caption=c):
                r = self.audit(BODY + SIG + EXA + [P("EXHIBIT B"), P(c), RENT_ROLL])
                self.assertEqual(r["form_exhibits"], [])
                self.assertTrue(r["blocking"])

    def test_real_forms_still_exempt(self):
        for c in ("Form of Assignment and Assumption of Leases", "Form of Tenant Estoppel Certificate",
                  "Form of Limited Warranty Deed", "Form of Bill of Sale"):
            with self.subTest(caption=c):
                r = self.audit(BODY + SIG + EXA + [P("EXHIBIT B"), P(c), P("Grantee: ________")])
                self.assertEqual(r["form_exhibits"], ["B"])
                self.assertFalse(r["blocking"])


# ------------------------------------------------------------------ (3) C4b cues
class TestSignatureCues(_Base):
    def test_party_label_in_a_rent_roll_blocks_even_next_to_a_signature_line(self):
        for cue in (P("Name: ________"), P("By: ________"), P("________")):
            with self.subTest(cue=cue[-40:]):
                r = self.audit(rent_roll_exhibit(P("Tenant: ________"), cue))
                self.assertTrue(r["blocking"])

    def test_context_lines_in_a_rent_roll_block(self):
        for line in ("Landlord: ________", "________, a ________ limited liability company", "County of ________"):
            with self.subTest(line=line):
                r = self.audit(rent_roll_exhibit(P(line), P("By: ________"), P("Name: ________")))
                self.assertTrue(r["blocking"])

    def test_prose_is_not_a_signature_cue(self):
        for prose in ("Its lease expires in 2029.", "Title Company: First American", "By-laws of Tenant are attached.",
                      "Signature of the Seller is not required.", "Seller's seal (SEAL) applied",
                      "Name of guarantor: none", "By: /s/ J. Smith"):
            with self.subTest(prose=prose):
                r = self.audit(closing_cert(P("Tenant: ________"), P(prose)))
                self.assertTrue(r["blocking"])

    def test_party_label_needs_an_adjacent_label_cue(self):
        r = self.audit(closing_cert(P("Tenant: ________"), P("By: ________")))
        self.assertFalse(r["blocking"])
        r = self.audit(closing_cert(P("Tenant: ________"), P("Lorem."), P("By: ________")))
        self.assertTrue(r["blocking"])

    def test_two_bare_rules_in_one_rent_roll_cell_block(self):
        tbl = TBL([["Suite", "Rent"], ["200", CELL(P("________"), P("________"))]])
        self.assertTrue(self.audit(closing_cert(tbl))["blocking"])

    def test_same_cell_window_is_three_lines(self):
        box = TBL([[CELL(P("Tenant: ________"), *[P("Filler line %d" % k) for k in range(5)],
                         P("By: ________"))]])
        self.assertTrue(self.audit(closing_cert(box))["blocking"])


# ------------------------------------------------------------------ (2) C4a notary sentences
class TestNotarySentencesNeedANotaryCue(_Base):
    SENTENCES = ["I hereby certify that on ________ the undersigned appeared.",
                 "WITNESS my hand and official seal this ___ day of ________, 20__.",
                 "IN TESTIMONY WHEREOF, I have set my hand this ___ day of ________, 20__.",
                 "Given under my hand and seal this ___ day of ________, 20__.",
                 "Personally appeared before me, ________, with whom I am personally acquainted.",
                 "On this ___ day of ________, 20__, before me appeared ________.",
                 "Before me, a Notary Public in and for said County, personally appeared ________.",
                 "Acknowledged before me this ___ day of ________, 20__.",
                 "Subscribed and sworn to before me this ___ day of ________, 20__."]
    VALUE_SENTENCES = ["I hereby certify that the outstanding amounts owed by Tenant are ________.",
                       "I hereby certify that the Property contains ________ rentable square footage.",
                       "I hereby certify that the security balance held is ________.",
                       "IN TESTIMONY WHEREOF ________ units are leased",
                       "Personally appeared before me ________ who stated the premises address is ________",
                       "I hereby certify the monthly rental is ________", "I hereby certify the prices are ________",
                       "On the date below before me appeared ________; Unit ________"]

    def test_sentences_alone_block(self):
        for s in self.SENTENCES:
            with self.subTest(sentence=s[:40]):
                self.assertTrue(self.audit(closing_cert(P(s)))["blocking"])

    def test_sentences_in_a_notary_block_are_exempt(self):
        for s in self.SENTENCES:
            with self.subTest(sentence=s[:40]):
                r = self.audit(closing_cert(*(NOTARY_CUES + [P(s)] + NOTARY_TAIL)))
                self.assertEqual(r["body_blanks"], [])
                self.assertFalse(r["blocking"])

    def test_value_words_block_even_in_a_notary_block(self):
        for s in self.VALUE_SENTENCES:
            with self.subTest(sentence=s[:40]):
                r = self.audit(closing_cert(*(NOTARY_CUES + [P(s)] + NOTARY_TAIL)))
                self.assertTrue(r["blocking"])

    def test_sentences_do_not_cue_each_other(self):
        r = self.audit(closing_cert(P(self.SENTENCES[0]), P(self.SENTENCES[1])))
        self.assertTrue(r["blocking"])


# ------------------------------------------------------------------ (4) C5 long acks
ACKS = {
    "TN corp": "Personally appeared before me, ________, a Notary Public of the state and county aforesaid, ________, "
               "with whom I am personally acquainted (or proved to me on the basis of satisfactory evidence), and who, "
               "upon oath, acknowledged such person to be president (or other officer authorized to execute the "
               "instrument) of ________, the within named bargainor, a corporation, and that such president or officer "
               "as such president or officer, being authorized so to do, executed the foregoing instrument for the "
               "purposes therein contained, by personally signing the name of the corporation by such person as such "
               "president or officer.",
    "MD corp": "I HEREBY CERTIFY that on this ___ day of ________, 20__, before me, the subscriber, a Notary Public of "
               "the State of Maryland, personally appeared ________, who acknowledged himself/herself to be the ________ "
               "of ________, a ________, and that he/she, as such ________, being authorized so to do, executed the "
               "foregoing instrument for the purposes therein contained by signing the name of the ________ by "
               "himself/herself as ________.",
    "MO corp": "On this ___ day of ________, 20__, before me appeared ________, to me personally known, who, being by "
               "me duly sworn, did say that he/she is the ________ of ________, a ________, and that said instrument "
               "was signed in behalf of said ________ by authority of its ________, and said ________ acknowledged "
               "said instrument to be the free act and deed of said ________.",
}


class TestLongAcknowledgments(_Base):
    def test_long_corporate_acknowledgments_are_exempt(self):
        for k, v in ACKS.items():
            with self.subTest(form=k):
                self.assertGreater(len(v), 300)
                r = self.audit(closing_cert(*(NOTARY_CUES + [P(v)] + NOTARY_TAIL)))
                self.assertEqual(r["body_blanks"], [])
                self.assertFalse(r["blocking"])

    def test_over_900_chars_is_never_exempt(self):
        long_line = ACKS["TN corp"] + " " + "x" * 400
        r = self.audit(closing_cert(*(NOTARY_CUES + [P(long_line)] + NOTARY_TAIL)))
        self.assertTrue(r["blocking"])


# ------------------------------------------------------------------ (5) C9 linear cues
class TestCueLookupIsLinear(_Base):
    def test_ten_thousand_context_lines_in_one_cell(self):
        cell = "".join(P("Tenant: ________") for _ in range(10000))
        doc = closing_cert(TBL([[CELL(cell), "x"]]))
        t0 = time.perf_counter()
        r = self.audit(doc)
        self.assertLess(time.perf_counter() - t0, 1.0)
        self.assertTrue(r["blocking"])

    def test_ten_thousand_venue_lines_in_one_cell(self):
        cell = "".join(P("COUNTY OF ________") for _ in range(10000))
        t0 = time.perf_counter()
        self.audit(closing_cert(TBL([[CELL(cell)]])))
        self.assertLess(time.perf_counter() - t0, 1.0)


if __name__ == "__main__":
    unittest.main()
