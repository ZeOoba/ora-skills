"""Characterization suite for deal-execution/scripts/audit_completeness.py.

audit_completeness.py is the outbound-PSA pre-send gate (deal-execution Workflow 2B):
exit 1 blocks a send, exit 0 clears it. This suite pins its CURRENT behavior so any
change to the gate verdict is a visible, reviewed diff. Cases marked KNOWN DEFECT pin
behavior that is arguably wrong today; they assert the present result on purpose and
must be flipped (not deleted) by the PR that fixes the defect.

Constraints (eval plan A-1, D8):
  * main() is never called without a path argument: main([]) prints the module
    docstring, which must not reach CI logs.
  * every main() call runs under redirect_stdout/redirect_stderr into StringIO, and no
    assertion message includes captured output.
  * fixtures are synthetic only (Seller / Purchaser / lorem-style text).
  * stdlib only.

Run: python deal-execution/tests/test_audit_completeness.py
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_completeness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_completeness_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ac = _load_module()

# --------------------------------------------------------------------------- fixtures
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

LOREM = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
         "tempor incididunt ut labore et dolore magna aliqua.")


def _run(text: str) -> str:
    return '<w:r><w:t xml:space="preserve">{}</w:t></w:r>'.format(escape(text))


def _del_run(text: str) -> str:
    return ('<w:del w:id="1" w:author="Reviewer"><w:r><w:delText xml:space="preserve">'
            '{}</w:delText></w:r></w:del>').format(escape(text))


def P(text: str) -> str:
    """Plain paragraph."""
    return "<w:p>{}</w:p>".format(_run(text))


def PR(*runs) -> str:
    """Paragraph from ('t', text) / ('del', text) runs (tracked deletions)."""
    body = "".join(_run(t) if k == "t" else _del_run(t) for k, t in runs)
    return "<w:p>{}</w:p>".format(body)


def IMG() -> str:
    """Paragraph holding only an inline image reference (a:blip), no text."""
    return ('<w:p><w:r><w:drawing><a:graphic><a:graphicData><a:blip r:embed="rId9"/>'
            '</a:graphicData></a:graphic></w:drawing></w:r></w:p>')


def TBL(rows) -> str:
    """Table: rows is a list of lists of cell strings."""
    out = []
    for row in rows:
        cells = "".join("<w:tc>{}</w:tc>".format(P(c)) for c in row)
        out.append("<w:tr>{}</w:tr>".format(cells))
    return "<w:tbl>{}</w:tbl>".format("".join(out))


def document_xml(blocks) -> str:
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="{}" xmlns:a="{}" xmlns:r="{}"><w:body>{}'
            '<w:sectPr/></w:body></w:document>').format(W_NS, A_NS, R_NS, "".join(blocks))


def write_docx(dirpath: Path, name: str, blocks) -> Path:
    path = Path(dirpath) / name
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", document_xml(blocks))
    return path


# Synthetic baseline: every check resolves, no blocking defect.
BODY_CLEAN = [
    P("PURCHASE AND SALE AGREEMENT"),
    P("1. Property. Seller shall sell and Purchaser shall buy the Property described in "
      "Exhibit A."),
    P("2. Purchase Price. The Purchase Price is One Dollar, payable as provided in "
      "Section 1."),
    P('3. Knowledge. As used herein, the phrase "to Seller\'s knowledge" shall mean the '
      "actual knowledge of A. Placeholder, Manager."),
]
SIG = [
    P("IN WITNESS WHEREOF, the parties have executed this Agreement."),
    P("SELLER: By: ______________________"),
    P("PURCHASER: By: ______________________"),
]
EXHIBIT_A_OK = [P("EXHIBIT A"), P("(Legal Description)"), P(LOREM)]


def clean_blocks():
    return BODY_CLEAN + SIG + EXHIBIT_A_OK


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def doc(self, blocks, name="fixture.docx") -> Path:
        return write_docx(self.tmp, name, blocks)

    def audit(self, blocks) -> dict:
        return ac.audit(self.doc(blocks))

    def run_main(self, *argv):
        """Call main() with captured output. Returns (rc, stdout, stderr). argv must
        include a path: main() without one prints the module docstring."""
        assert argv and not str(argv[0]).startswith("--"), "main() needs a path argument"
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = ac.main(["audit_completeness.py"] + [str(a) for a in argv])
        return rc, out.getvalue(), err.getvalue()

    def exhibit(self, r: dict, letter: str) -> dict:
        for e in r["exhibits"]:
            if e["letter"] == letter:
                return e
        self.fail("exhibit {} not detected".format(letter))


# --------------------------------------------------------------------------- verdicts
class TestVerdict(_Base):
    def test_clean_document_is_not_blocking_and_exits_0(self):
        p = self.doc(clean_blocks())
        r = ac.audit(p)
        self.assertFalse(r["blocking"])
        self.assertEqual(r["empty_exhibits"], [])
        self.assertEqual(r["thin_exhibits"], [])
        self.assertEqual(r["dangling_exhibit_refs"], [])
        self.assertEqual(r["dangling_section_refs"], [])
        self.assertEqual(r["body_blanks"], [])
        self.assertTrue(r["knowledge_party"]["found"])
        self.assertFalse(r["knowledge_party"]["unfilled"])
        self.assertEqual(self.exhibit(r, "A")["caption"], "(Legal Description)")
        rc, out, _ = self.run_main(p)
        self.assertEqual(rc, 0)
        self.assertTrue("NO BLOCKING DEFECTS" in out, "render verdict line missing")

    def test_signature_block_blanks_are_reported_but_not_blocking(self):
        r = self.audit(clean_blocks())
        self.assertEqual(len(r["signature_blanks"]), 2)
        self.assertEqual({b["kind"] for b in r["signature_blanks"]},
                         {"underscore placeholder"})
        self.assertFalse(r["blocking"])

    def test_empty_exhibit_blocks_and_exits_1(self):
        blocks = BODY_CLEAN + SIG + [P("EXHIBIT A"), P("(Legal Description)")]
        p = self.doc(blocks)
        r = ac.audit(p)
        self.assertEqual(r["empty_exhibits"], ["A"])
        self.assertFalse(self.exhibit(r, "A")["populated"])
        self.assertTrue(r["blocking"])
        rc, out, _ = self.run_main(p)
        self.assertEqual(rc, 1)
        self.assertTrue("BLOCKING DEFECTS PRESENT" in out, "render verdict line missing")
        self.assertTrue("EMPTY   <-- BLOCKING" in out, "EMPTY flag missing from render")


# --------------------------------------------------------------------------- exhibits
class TestExhibitPopulation(_Base):
    def test_dms_stamp_only_exhibit_is_empty(self):
        blocks = BODY_CLEAN + SIG + [P("EXHIBIT A"), P("(Legal Description)"),
                                     P("12345678.v2")]
        r = self.audit(blocks)
        self.assertEqual(r["empty_exhibits"], ["A"])
        self.assertTrue(r["blocking"])

    def test_concatenated_dms_stamps_are_still_empty(self):
        blocks = BODY_CLEAN + SIG + [P("EXHIBIT A"), P("12345678.v2 87654321.v10")]
        r = self.audit(blocks)
        self.assertEqual(r["empty_exhibits"], ["A"])
        self.assertTrue(r["blocking"])

    def test_struck_only_exhibit_content_is_empty(self):
        blocks = BODY_CLEAN + SIG + [P("EXHIBIT A"), P("(Legal Description)"),
                                     PR(("del", LOREM))]
        r = self.audit(blocks)
        self.assertEqual(self.exhibit(r, "A")["text_chars"], 0)
        self.assertEqual(r["empty_exhibits"], ["A"])
        self.assertTrue(r["blocking"])

    def test_short_prose_exhibit_is_thin_advisory_not_blocking(self):
        blocks = BODY_CLEAN + SIG + [P("EXHIBIT A"), P("(Legal Description)"),
                                     P("Parcel 000-000-000 as shown on the plat.")]
        r = self.audit(blocks)
        self.assertEqual(r["thin_exhibits"], ["A"])
        self.assertEqual(r["empty_exhibits"], [])
        self.assertFalse(r["blocking"])

    def test_image_only_exhibit_is_populated_and_thin(self):
        blocks = BODY_CLEAN + SIG + [P("EXHIBIT A"), P("(Site Plan)"), IMG()]
        r = self.audit(blocks)
        e = self.exhibit(r, "A")
        self.assertEqual(e["images"], 1)
        self.assertTrue(e["populated"])
        self.assertTrue(e["thin"])
        self.assertFalse(r["blocking"])

    def test_populated_table_exhibit_is_ok(self):
        tbl = TBL([["Suite", "Tenant", "Rent"], ["100", "Tenant One", "1,000"],
                   ["200", "Tenant Two", "2,000"]])
        blocks = BODY_CLEAN + SIG + [P("EXHIBIT A"), P("(Rent Roll)"), tbl]
        r = self.audit(blocks)
        e = self.exhibit(r, "A")
        self.assertEqual(e["tables"], 1)
        self.assertTrue(e["populated"])
        self.assertFalse(e["thin"])
        self.assertFalse(r["blocking"])

    def test_header_only_table_exhibit_is_not_thin_today(self):
        # KNOWN DEFECT (finding completeness-empty-table-populated, target A-2): a
        # skeleton table with only a header row counts as populated and is NOT flagged
        # THIN, because thin requires `not tables`. A-2 flips the thin assertion; the
        # populated/blocking assertions must stay as they are.
        tbl = TBL([["Suite", "Tenant", "Rent"], ["", "", ""]])
        blocks = BODY_CLEAN + SIG + [P("EXHIBIT A"), P("(Rent Roll)"), tbl]
        r = self.audit(blocks)
        e = self.exhibit(r, "A")
        self.assertTrue(e["populated"])
        self.assertFalse(e["thin"])
        self.assertFalse(r["blocking"])

    def test_heading_inside_table_is_detected(self):
        blocks = BODY_CLEAN + SIG + [TBL([["EXHIBIT A"]]), P(LOREM)]
        r = self.audit(blocks)
        self.assertEqual([e["letter"] for e in r["exhibits"]], ["A"])
        self.assertFalse(r["blocking"])

    def test_heading_with_inline_title_is_not_an_exhibit_heading(self):
        # Characterization: the heading regex wants the bare "EXHIBIT X" line. A
        # one-line "EXHIBIT A - LEGAL DESCRIPTION" is not detected, so the body's
        # reference dangles and the gate blocks (fails closed, not open).
        blocks = BODY_CLEAN + SIG + [P("EXHIBIT A - LEGAL DESCRIPTION"), P(LOREM)]
        r = self.audit(blocks)
        self.assertEqual(r["exhibits"], [])
        self.assertEqual(r["dangling_exhibit_refs"], ["A"])
        self.assertTrue(r["blocking"])


# --------------------------------------------------------------------------- cross-refs
class TestCrossReferences(_Base):
    def test_dangling_exhibit_reference_blocks(self):
        body = BODY_CLEAN + [P("4. Leases. The rent roll is attached as Exhibit B.")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(r["dangling_exhibit_refs"], ["B"])
        self.assertTrue(r["blocking"])

    def test_plural_exhibit_reference_lists_each_letter(self):
        body = BODY_CLEAN + [P("4. Deliveries. See Exhibits A, B and C.")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(r["dangling_exhibit_refs"], ["B", "C"])
        self.assertTrue(r["blocking"])

    def test_unreferenced_exhibit_is_advisory(self):
        blocks = clean_blocks() + [P("EXHIBIT B"), P(LOREM)]
        r = self.audit(blocks)
        self.assertEqual(r["unreferenced_exhibits"], ["B"])
        self.assertFalse(r["blocking"])

    def test_dangling_section_reference_blocks(self):
        body = BODY_CLEAN + [P("4. Closing. Subject to Section 9, Closing shall occur.")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(r["dangling_section_refs"], ["9"])
        self.assertTrue(r["blocking"])

    def test_subsection_heading_establishes_parent_article(self):
        body = BODY_CLEAN + [P("9.2 Default. Lorem ipsum."),
                             P("4. Closing. Subject to Section 9, Closing shall occur.")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(r["dangling_section_refs"], [])
        self.assertFalse(r["blocking"])

    def test_statute_after_signal_is_suppressed(self):
        body = BODY_CLEAN + [P("4. Exchange. Either party may effect an exchange under "
                               "Section 1031 of the Code.")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(r["dangling_section_refs"], [])
        self.assertEqual(r["likely_statutory_citations"], [])
        self.assertFalse(r["blocking"])

    def test_statute_before_signal_is_suppressed(self):
        body = BODY_CLEAN + [P("4. FIRPTA. Seller shall deliver a certificate under "
                               "26 U.S.C. § 1445.")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(r["dangling_section_refs"], [])
        self.assertEqual(r["likely_statutory_citations"], [])
        self.assertFalse(r["blocking"])

    def test_unsignalled_high_number_is_likely_citation_not_blocking(self):
        body = BODY_CLEAN + [P("4. FIRPTA. Seller shall comply with Section 1445.")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(r["likely_statutory_citations"], ["1445"])
        self.assertEqual(r["dangling_section_refs"], [])
        self.assertFalse(r["blocking"])

    def test_section_100_is_still_internal_and_blocks(self):
        # MAX_PLAUSIBLE_SECTION boundary: head > 100 is a citation; 100 is not.
        body = BODY_CLEAN + [P("4. Misc. See Section 100.")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(r["dangling_section_refs"], ["100"])
        self.assertTrue(r["blocking"])


# --------------------------------------------------------------------------- blanks
class TestBlanks(_Base):
    def test_body_underscore_blank_blocks(self):
        body = BODY_CLEAN + [P("4. Deposit. The Deposit is $__________.")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(len(r["body_blanks"]), 1)
        self.assertTrue(r["blocking"])

    def test_bracket_placeholder_blocks(self):
        body = BODY_CLEAN + [P("4. Closing Date. Closing shall occur on [TBD].")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual([b["kind"] for b in r["body_blanks"]], ["bracket placeholder"])
        self.assertTrue(r["blocking"])

    def test_struck_underscore_replaced_by_value_is_not_a_blank(self):
        body = BODY_CLEAN + [PR(("t", "4. Deposit. The Deposit is "),
                                ("del", "$__________"), ("t", "$1.00."))]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(r["body_blanks"], [])
        self.assertFalse(r["blocking"])

    def test_counterparts_boilerplate_does_not_start_signature_block(self):
        # "signature pages" in a Counterparts clause must not downgrade a later body
        # blank to an expected signature blank.
        body = BODY_CLEAN + [
            P("4. Counterparts. Signature pages may be delivered by email."),
            P("5. Deposit. The Deposit is $__________."),
        ]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertEqual(len(r["body_blanks"]), 1)
        self.assertTrue(r["blocking"])

    def test_blank_inside_exhibit_after_signature_is_not_blocking(self):
        # KNOWN DEFECT (false clean): every block from the signature start onward is
        # treated as signature territory, and exhibits normally follow the signature
        # page. An open $____ inside an exhibit is therefore reported only as a
        # signature blank and the gate exits 0. Pinned here; flip this assertion only
        # together with a reviewed change to the gate.
        blocks = BODY_CLEAN + SIG + [P("EXHIBIT A"), P("(Legal Description)"), P(LOREM),
                                     P("Allocated value: $__________")]
        p = self.doc(blocks)
        r = ac.audit(p)
        self.assertEqual(r["body_blanks"], [])
        self.assertEqual(len(r["signature_blanks"]), 3)
        self.assertFalse(r["blocking"])
        rc, _, _ = self.run_main(p)
        self.assertEqual(rc, 0)

    def test_unfilled_knowledge_party_blocks(self):
        body = BODY_CLEAN[:3] + [
            P('3. Knowledge. As used herein, the phrase "to Seller\'s knowledge" shall '
              "mean the actual knowledge of ______________.")]
        r = self.audit(body + SIG + EXHIBIT_A_OK)
        self.assertTrue(r["knowledge_party"]["found"])
        self.assertTrue(r["knowledge_party"]["unfilled"])
        self.assertTrue(r["blocking"])

    def test_missing_knowledge_definition_is_not_blocking(self):
        r = self.audit(BODY_CLEAN[:3] + SIG + EXHIBIT_A_OK)
        self.assertFalse(r["knowledge_party"]["found"])
        self.assertFalse(r["blocking"])

    def test_compare_summary_chrome_is_ignored(self):
        # Everything from a compare-tool summary page onward is chrome, not contract.
        blocks = clean_blocks() + [P("Litera Compare summary report"),
                                   P("Deposit $__________"), P("See Exhibit Z.")]
        r = self.audit(blocks)
        self.assertEqual(r["body_blanks"], [])
        self.assertEqual(r["dangling_exhibit_refs"], [])
        self.assertFalse(r["blocking"])


# --------------------------------------------------------------------------- CLI
class TestCli(_Base):
    def test_json_output_parses_and_matches_audit(self):
        p = self.doc(clean_blocks())
        rc, out, _ = self.run_main(p, "--json")
        self.assertEqual(rc, 0)
        data = json.loads(out)
        self.assertEqual(data, ac.audit(p))
        self.assertFalse(data["blocking"])

    def test_json_blocking_exit_code(self):
        p = self.doc(BODY_CLEAN + SIG + [P("EXHIBIT A")])
        rc, out, _ = self.run_main(p, "--json")
        self.assertEqual(rc, 1)
        self.assertTrue(json.loads(out)["blocking"])

    def test_unknown_flag_exits_3(self):
        p = self.doc(clean_blocks())
        rc, out, err = self.run_main(p, "--bogus")
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertTrue("unknown flag" in err, "unknown-flag error message missing")

    def test_non_docx_exits_3(self):
        p = self.tmp / "not_a_docx.docx"
        p.write_text("plain text, not a zip", encoding="utf-8")
        rc, out, _ = self.run_main(p)
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")

    def test_zip_without_document_xml_exits_3(self):
        p = self.tmp / "no_body.docx"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("[Content_Types].xml", "<Types/>")
        rc, out, _ = self.run_main(p)
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")

    def test_malformed_xml_exits_3(self):
        p = self.tmp / "bad_xml.docx"
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("word/document.xml", "<w:document")
        rc, _, _ = self.run_main(p)
        self.assertEqual(rc, 3)

    def test_missing_file_exits_3(self):
        rc, out, err = self.run_main(self.tmp / "does_not_exist.docx")
        self.assertEqual(rc, 3)
        self.assertEqual(out, "")
        self.assertTrue("no such file" in err, "missing-file error message missing")


if __name__ == "__main__":
    unittest.main()
