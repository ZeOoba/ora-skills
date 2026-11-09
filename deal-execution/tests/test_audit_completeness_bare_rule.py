"""Pre-send gate: a bare rule in a DATA exhibit after IN WITNESS WHEREOF.

A line consisting solely of underscores was classed as a signature rule
unconditionally, and the underscores counted toward the exhibit's population, so a
legal-description exhibit holding nothing but "________" passed the gate
(blocking=False, no body blank, not even THIN). SKILL.md Check D item 3: a blank in
a data exhibit after IN WITNESS WHEREOF blocks.

  (1) in a data-captioned exhibit (and after a Form-of region ends) a bare rule is a
      signature rule only with a signature / notary cue on an adjacent line
      (By:/Name:/Title:/Its:/Signature/Notary Public/(SEAL) ...); otherwise a body
      blank
  (2) underscore runs do not count toward exhibit population (EMPTY / THIN)
  (3) unchanged: Form-of exhibits, non-data exhibits and (SEAL) rules

Self-contained fixture builder; D8 constraints; synthetic text; stdlib only.

Run: python deal-execution/tests/test_audit_completeness_bare_rule.py
"""
from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "audit_completeness.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_completeness_bare_rule_ut", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ac = _load_module()

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
LOREM = ("Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod "
         "tempor incididunt ut labore et dolore magna aliqua.")
RULE = "_" * 80


def _r(text):
    return '<w:r><w:t xml:space="preserve">{}</w:t></w:r>'.format(escape(text))


def P(text):
    return "<w:p>{}</w:p>".format(_r(text))


def TBL(rows):
    def cell(c):
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
EXB = [P("EXHIBIT B"), P("(Schedule)"), P(LOREM)]


def legal_description(*content):
    """Data exhibit A (legal description) after the signature page, then exhibit B."""
    return BODY + SIG + [P("EXHIBIT A"), P("(Legal Description)")] + list(content) + EXB


def rent_roll(*content):
    """Data exhibit B (rent roll) after the signature page."""
    return BODY + SIG + [P("EXHIBIT A"), P("(Legal Description)"), P(LOREM),
                         P("EXHIBIT B"), P("Rent Roll"), P(LOREM)] + list(content)


def form_exhibit(caption, *content):
    return BODY + SIG + [P("EXHIBIT A"), P("(Legal Description)"), P(LOREM),
                         P("EXHIBIT B"), P(caption), P(LOREM)] + list(content)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def audit(self, blocks):
        return ac.audit(write_docx(self.tmp / "fixture.docx", blocks))


# ------------------------------------------------------------- (1) bare rule = body
class TestBareRuleInDataExhibitBlocks(_Base):
    def test_rule_only_legal_description_blocks(self):
        r = self.audit(legal_description(P(RULE)))
        self.assertTrue(r["blocking"])
        self.assertTrue(r["body_blanks"], "bare rule in a data exhibit must be a body blank")
        self.assertIn("A", r["empty_exhibits"])

    def test_rule_after_prose_in_legal_description_blocks(self):
        r = self.audit(legal_description(P(LOREM), P(RULE)))
        self.assertTrue(r["blocking"])
        self.assertEqual(len(r["body_blanks"]), 1)

    def test_rule_in_single_cell_table_of_data_exhibit_blocks(self):
        r = self.audit(legal_description(P(LOREM), TBL([[RULE]])))
        self.assertTrue(r["blocking"])
        self.assertTrue(r["body_blanks"])

    def test_cue_two_lines_away_is_not_enough(self):
        r = self.audit(rent_roll(P(RULE), P(LOREM), P("By: ________")))
        self.assertTrue(r["blocking"])
        self.assertTrue(r["body_blanks"])

    def test_two_adjacent_rules_do_not_cue_each_other(self):
        r = self.audit(rent_roll(P(RULE), P(RULE)))
        self.assertTrue(r["blocking"])

    def test_rule_after_form_region_ends_blocks(self):
        r = self.audit(form_exhibit("Form of Tenant Estoppel Certificate",
                                    P("SCHEDULE 1 Rent Roll"), P(LOREM), P(RULE)))
        self.assertTrue(r["blocking"])
        self.assertTrue(r["body_blanks"])

    def test_cue_three_lines_away_is_not_enough(self):
        r = self.audit(rent_roll(P(RULE), P(LOREM), P(LOREM), P("By: ________")))
        self.assertTrue(r["blocking"])

    def test_value_label_is_not_a_cue(self):
        r = self.audit(rent_roll(P(RULE), P("Name: Suite 100 monthly rent")))
        self.assertTrue(r["blocking"])


# ------------------------------------------- (1) bare rule with a cue stays signature
class TestBareRuleWithSignatureCueStaysSignature(_Base):
    CUES = [
        ("By: ________", "after"),
        ("By: Jane Q. Doe, Manager", "after"),
        ("(Signature)", "after"),
        ("Authorized Signatory", "after"),
        ("Printed Name: Jane Q. Doe", "after"),
        ("Notary Public", "after"),
        ("By: ________", "before"),
        ("________ (SEAL)", "before"),
        ("________ (L.S.)", "before"),
    ]

    def test_rule_beside_a_signature_cue_is_a_signature_blank(self):
        for cue, where in self.CUES:
            with self.subTest(cue=cue, where=where):
                lines = [P(RULE), P(cue)] if where == "after" else [P(cue), P(RULE)]
                r = self.audit(rent_roll(*lines))
                self.assertFalse(r["blocking"])
                self.assertFalse(r["body_blanks"])
                self.assertTrue(r["signature_blanks"])

    def test_certified_rent_roll_signature_block_passes(self):
        r = self.audit(rent_roll(P("Certified by Seller:"), P(RULE),
                                 P("By: Jane Q. Doe"), P("Title: Manager")))
        self.assertFalse(r["blocking"])

    def test_unfilled_by_name_title_date_stack_passes(self):
        r = self.audit(rent_roll(P("By: ________"), P("Name: ________"),
                                 P("Title: ________"), P("Date: ________")))
        self.assertFalse(r["blocking"])
        self.assertFalse(r["body_blanks"])

    def test_rule_above_name_title_above_by_stack_passes(self):
        r = self.audit(rent_roll(P(RULE), P("Name: Jane Q. Doe"), P("By: Its Manager")))
        self.assertFalse(r["blocking"])


# --------------------------- (1b) REFUTE C3: weak labels never clear a rule in data
class TestWeakLabelsDoNotClearDataRules(_Base):
    """Filled or unfilled Name:/Title:/Date:/Dated:/Its:/Witness/Attest lines are
    data in a data exhibit; only By:, a seal / notary cue or an unambiguous
    signature caption ((Signature), Authorized Signatory, Printed Name) clears a
    rule or an unfilled weak label."""

    def _blocks(self, blocks):
        r = self.audit(blocks)
        self.assertTrue(r["blocking"])
        self.assertTrue(r["body_blanks"])

    def test_probe1_date_line_in_rent_roll(self):
        self._blocks(rent_roll(P("Date: October 31, 2026"), P(RULE)))

    def test_probe2_dated_line(self):
        self._blocks(rent_roll(P(RULE), P("Dated: October 31, 2026")))

    def test_probe3_name_rule_pairs(self):
        self._blocks(rent_roll(P("Name: Acme LLC"), P(RULE), P("Name: Beta LLC"), P(RULE)))

    def test_probe4_title_in_schedule_of_leases(self):
        self._blocks(BODY + SIG + [P("EXHIBIT A"), P("(Legal Description)"), P(LOREM),
                                   P("EXHIBIT B"), P("Schedule of Leases"), P(LOREM),
                                   P("Title: Industrial Lease dated 1/1/2020"), P(RULE)])

    def test_probe5_name_in_legal_description(self):
        self._blocks(legal_description(P(LOREM), P(RULE), P("Name: Example Industrial Park")))

    def test_probe6_unfilled_name_label_and_rule(self):
        r = self.audit(legal_description(P(LOREM), P("Name: ________"), P(RULE)))
        self.assertTrue(r["blocking"])
        self.assertTrue(r["body_blanks"])

    def test_weak_label_alone_unfilled_blocks(self):
        for line in ("Name: ________", "Title: ________", "Date: ________"):
            with self.subTest(line=line):
                self._blocks(rent_roll(P(line)))

    def test_by_three_lines_away_through_prose_does_not_clear(self):
        self._blocks(rent_roll(P(RULE), P(LOREM), P("By: ________")))

    def test_typed_signer_without_by_blocks_fail_closed(self):
        # Accepted fail-closed (refute C2 note): SELLER / entity / rule / typed signer.
        self._blocks(rent_roll(P("SELLER:"), P("Acme Industrial LLC, an Ohio limited "
                                               "liability company"), P(RULE),
                               P("John Smith, Managing Member")))


# --------------------------- (1c) REFUTE C2: inline cross-reference in a Form of Deed
class TestInlineCrossReferenceKeepsFormRegion(_Base):
    def test_deed_with_legal_description_reference_does_not_block(self):
        r = self.audit(form_exhibit("Form of Limited Warranty Deed",
                                    P("Legal Description: See Exhibit A attached hereto."),
                                    P(LOREM), P("GRANTOR:"), P(RULE),
                                    P("Name: ________"), P("Title: ________")))
        self.assertFalse(r["blocking"])
        self.assertFalse(r["body_blanks"])

    def test_standalone_data_caption_still_ends_the_form(self):
        r = self.audit(form_exhibit("Form of Limited Warranty Deed", P(LOREM),
                                    P("Legal Description"), P(RULE)))
        self.assertTrue(r["blocking"])

    def test_data_caption_with_values_still_ends_the_form(self):
        r = self.audit(form_exhibit("Form of Limited Warranty Deed", P(LOREM),
                                    P("Rent Roll: Tenant One"), P(RULE)))
        self.assertTrue(r["blocking"])


class TestSealRule(_Base):
    def test_seal_rule_alone_in_data_exhibit_stays_exempt(self):
        r = self.audit(rent_roll(P("________ (SEAL)")))
        self.assertFalse(r["blocking"])


# ------------------------------------------------------------ (3) no regressions
class TestUnchangedOutsideDataExhibits(_Base):
    def test_form_of_deed_signature_rules_stay_exempt(self):
        r = self.audit(form_exhibit("Form of Limited Warranty Deed", P(LOREM), P(RULE),
                                    P(LOREM), P(RULE), P("GRANTOR:"), P("By: ________")))
        self.assertFalse(r["blocking"])
        self.assertFalse(r["body_blanks"])

    def test_non_data_exhibit_bare_rule_stays_signature(self):
        r = self.audit(BODY + SIG + [P("EXHIBIT A"), P("(Legal Description)"), P(LOREM),
                                     P("EXHIBIT B"), P("(Closing Certificate)"), P(LOREM),
                                     P(RULE)])
        self.assertFalse(r["blocking"])
        self.assertTrue(r["signature_blanks"])


# --------------------------------------------------------- (2) population count
class TestUnderscoresAreNotPopulation(_Base):
    def test_rule_only_exhibit_is_empty(self):
        r = self.audit(legal_description(P(RULE), P(RULE)))
        a = next(e for e in r["exhibits"] if e["letter"] == "A")
        self.assertEqual(a["text_chars"], 0)
        self.assertFalse(a["populated"])

    def test_short_text_plus_long_rule_is_thin(self):
        r = self.audit(legal_description(P("Parcel 010-123456"), P(RULE)))
        self.assertIn("A", r["thin_exhibits"])

    def test_rule_only_table_is_empty(self):
        r = self.audit(legal_description(TBL([[RULE, RULE], [RULE, RULE]])))
        self.assertIn("A", r["empty_exhibits"])
        self.assertTrue(r["blocking"])

    def test_text_around_blanks_still_counts(self):
        r = self.audit(legal_description(P(LOREM + " ____ " + LOREM)))
        a = next(e for e in r["exhibits"] if e["letter"] == "A")
        self.assertEqual(a["text_chars"], len(LOREM) * 2 + 2)


# --------------------- round 2, R2: "see Schedule ... below" must end a Form-of region
class TestRound2InlineXrefIsOutsideOnly(_Base):
    def test_leases_see_schedule_below_then_blank_grid_blocks(self):
        r = self.audit(form_exhibit("Form of Assignment and Assumption of Leases",
                                    P("Leases: see Schedule 1 below"),
                                    TBL([["Tenant", "Suite"], ["________", "________"]])))
        self.assertTrue(r["blocking"])

    def test_rent_roll_see_schedule_below_then_rules_blocks(self):
        r = self.audit(form_exhibit("Form of Tenant Estoppel Certificate",
                                    P("Rent Roll: see Schedule A below"), P(RULE), P(RULE)))
        self.assertTrue(r["blocking"])

    def test_attached_exhibit_reference_keeps_the_form_open(self):
        r = self.audit(form_exhibit("Form of Limited Warranty Deed",
                                    P("Legal Description: See Exhibit A attached hereto."),
                                    P(LOREM), P("GRANTOR:"), P(RULE)))
        self.assertFalse(r["blocking"])


# --------------------------- round 2, R1: cue laundering in strict context must block
class TestRound2CueLaundering(_Base):
    def _blocks(self, blocks):
        r = self.audit(blocks)
        self.assertTrue(r["blocking"])
        self.assertTrue(r["body_blanks"])

    def test_a_to_wit_prose_is_not_a_venue_cue(self):
        self._blocks(legal_description(
            P("Situated in the City of Columbus, County of Franklin and State of Ohio, "
              "to wit:"), P(RULE)))

    def test_b_three_rules_then_by(self):
        self._blocks(rent_roll(P(RULE), P(RULE), P(RULE), P("By: ________")))

    def test_b_rule_dated_rule_by(self):
        self._blocks(rent_roll(P(RULE), P("Dated October 31, 2026"), P(RULE),
                               P("By: ________")))

    def test_c_filled_by_with_entity_or_prose(self):
        for line in ("By: Acme LLC", "By: wire transfer to the account below",
                     "By: Acme Holdings"):
            with self.subTest(line=line):
                self._blocks(rent_roll(P(line), P(RULE)))

    def test_d_e_f_caption_words_inside_other_text(self):
        for line in ("Authorized Signatory: see Schedule 2", "Signature Aviation LLC",
                     "Printed Name of Tenant: Acme LLC"):
            with self.subTest(line=line):
                self._blocks(rent_roll(P(line), P(RULE)))

    def test_g_h_i_mid_prose_notary_and_seal_words(self):
        for line in ('County of Franklin (the "County")',
                     "Monument stamped (SEAL) at NE corner",
                     "I hereby certify that this rent roll is true and correct."):
            with self.subTest(line=line):
                self._blocks(legal_description(P(LOREM), P(line), P(RULE)))


class TestRound2RealBlocksStayGreen(_Base):
    def test_real_stacks_pass(self):
        stacks = [
            [P(RULE), P("By: ________"), P("Name: ________"), P("Title: ________")],
            [P("By: ________"), P("Name: Jane Q. Doe"), P("Title: Manager"),
             P("Date: ________")],
            [P(RULE), P("By: Acme LLC"), P("Its: Manager")],
            [P(RULE), P("By: Jane Q. Doe")],
            [P(RULE), P("Printed Name: ________")],
            [P(RULE), P("Signature: ________")],
            [P(RULE), P("Notary Public")],
            [P("________, Notary Public"), P(RULE)],
            [P("STATE OF OHIO )"), P(RULE)],
            [P("COUNTY OF FRANKLIN ) ss:"), P(RULE)],
            [P("________ (SEAL)")],
            [P(RULE), P("(L.S.)")],
        ]
        for stack in stacks:
            with self.subTest(stack=stack):
                r = self.audit(rent_roll(*stack))
                self.assertFalse(r["blocking"])
                self.assertFalse(r["body_blanks"])


# ---------------- round 3, X1/X3/X9: an xref keeps a Form-of region open only when
# it points OUTSIDE the exhibit (a heading for that id exists elsewhere) and never
# "below / following / herein"
GRID = TBL([["Tenant", "Suite"], ["________", "________"]])


class TestRound3XrefNeedsOutsideTarget(_Base):
    def test_x3_attached_as_schedule_below_blocks(self):
        r = self.audit(form_exhibit("Form of Assignment and Assumption of Leases",
                                    P("Leases: attached as Schedule 1 below"), GRID))
        self.assertTrue(r["blocking"])

    def test_x1_see_schedule_attached_with_no_schedule_heading_blocks(self):
        r = self.audit(form_exhibit("Form of Assignment and Assumption of Leases",
                                    P("Leases: see Schedule 1 attached"), GRID))
        self.assertTrue(r["blocking"])

    def test_x9_reference_to_missing_exhibit_ends_the_form(self):
        r = self.audit(form_exhibit("Form of Limited Warranty Deed",
                                    P("Legal Description: as described in Exhibit Z attached"),
                                    P(RULE)))
        self.assertTrue(r["blocking"])

    # final refute item 1: the target heading must be unique and outside the exhibit
    def _x1_with_exhibit_c(self, *c_content):
        return form_exhibit("Form of Assignment and Assumption of Leases",
                            P("Leases: see Schedule 1 attached"), GRID) + [
            P("EXHIBIT C"), P("(Closing Certificate)"), P(LOREM)] + list(c_content)

    def test_x1_with_unrelated_schedule_heading_in_exhibit_c_blocks(self):
        self.assertTrue(self.audit(self._x1_with_exhibit_c(P("SCHEDULE 1")))["blocking"])

    def test_x1_with_wire_instructions_schedule_in_exhibit_c_blocks(self):
        r = self.audit(self._x1_with_exhibit_c(P("Schedule 1 - Wire Instructions")))
        self.assertTrue(r["blocking"])

    def test_two_target_headings_are_ambiguous_and_block(self):
        r = self.audit(self._x1_with_exhibit_c(P("SCHEDULE 1"), P(LOREM), P("SCHEDULE 1")))
        self.assertTrue(r["blocking"])

    def test_duplicate_exhibit_a_heading_is_ambiguous_and_blocks(self):
        r = self.audit(form_exhibit("Form of Limited Warranty Deed",
                                    P("Legal Description: See Exhibit A attached hereto."),
                                    P(LOREM), P("GRANTOR:"), P(RULE)) + [
            P("EXHIBIT A"), P("(Legal Description)"), P(LOREM)])
        self.assertTrue(r["blocking"])

    def test_herein_after_attached_id_blocks(self):
        r = self.audit(form_exhibit("Form of Assignment and Assumption of Leases",
                                    P("Leases: see Schedule 1 attached hereinafter"), GRID))
        self.assertTrue(r["blocking"])

    def test_deed_reference_to_existing_exhibit_a_stays_a_form(self):
        r = self.audit(form_exhibit("Form of Limited Warranty Deed",
                                    P("Legal Description: See Exhibit A attached hereto."),
                                    P(LOREM), P("GRANTOR:"), P(RULE)))
        self.assertFalse(r["blocking"])

    def test_attached_as_existing_exhibit_stays_a_form(self):
        r = self.audit(form_exhibit("Form of Limited Warranty Deed",
                                    P("Legal Description: attached as Exhibit A"),
                                    P(LOREM), P("GRANTOR:"), P(RULE)))
        self.assertFalse(r["blocking"])


# ---------------------------- round 3 (a): placeholder words are never a person
class TestRound3PlaceholderSigners(_Base):
    def test_placeholder_signers_block(self):
        for line in ("By: To Be Provided", "By: See Schedule Two", "By: TBD",
                     "By: Pending Approval", "Signature: To Follow",
                     "Printed Name: Will Deliver", "By: Seller List",
                     "By: Not Yet Available", "By: Information Forthcoming",
                     "By: Seller Counsel"):
            with self.subTest(line=line):
                r = self.audit(rent_roll(P(line), P(RULE)))
                self.assertTrue(r["blocking"])


# ---------------------- round 3: false-block reductions (names, seal variants)
class TestRound3RealSignersPass(_Base):
    def test_caps_and_unicode_names_pass(self):
        for line in ("By: JOHN SMITH", "By: José Núñez", "By: Seán O'Brien-Murphy",
                     "By: Jane Q. Doe, Manager", "Printed Name: ZOË ADAMS"):
            with self.subTest(line=line):
                r = self.audit(rent_roll(P(RULE), P(line)))
                self.assertFalse(r["blocking"])
                self.assertFalse(r["body_blanks"])

    def test_bracket_and_corporate_seal_lines_pass(self):
        for line in ("[SEAL]", "(Corporate Seal)"):
            with self.subTest(line=line):
                r = self.audit(rent_roll(P(RULE), P(line)))
                self.assertFalse(r["blocking"])
                self.assertFalse(r["body_blanks"])


# ------------------- round 3 (b): Dated / Executed / Signed link only in label shape
class TestRound3DatedSignedShapes(_Base):
    def test_signed_prose_does_not_link_a_stack(self):
        r = self.audit(rent_roll(P(RULE), P("Signed leases are on file with Seller"),
                                 P("By: ________")))
        self.assertTrue(r["blocking"])

    def test_label_shapes_still_link(self):
        for line in ("Dated: ________", "Dated as of October 31, 2026",
                     "Executed this ___ day of ________, 20__."):
            with self.subTest(line=line):
                r = self.audit(rent_roll(P("By: ________"), P(line), P(RULE)))
                self.assertFalse(r["blocking"])


if __name__ == "__main__":
    unittest.main()
