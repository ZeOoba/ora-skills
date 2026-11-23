"""Shape tests for the v4.59 screen packet. Run: python acquisition-underwriting/scripts/test_screen_packet.py

Every figure, id and address is INVENTED (fixtures/ScreenPacket_100SampleWay_11232026.json). Never use a
real deal figure in this file: ora-skills is a public repo.
"""
import copy
import io
import json
import os
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import screen_packet as SP  # noqa: E402

HERE = Path(__file__).resolve().parent
FIXTURE = HERE / "fixtures" / "ScreenPacket_100SampleWay_11232026.json"
GOOD = json.loads(FIXTURE.read_text(encoding="utf-8"))
SKILL_MD = (HERE.parent / "SKILL.md").read_text(encoding="utf-8")
REFERENCE = (HERE.parent / "references" / "screen-packet.md").read_text(encoding="utf-8")


def mutate(fn):
    p = copy.deepcopy(GOOD)
    fn(p)
    return p


class SyntheticFixture(unittest.TestCase):
    def test_fixture_is_valid(self):
        self.assertEqual(SP.check_payload(GOOD), [])

    def test_fixture_is_marked_synthetic(self):
        self.assertIn("SYNTHETIC", GOOD["notes"]["_synthetic"])
        self.assertTrue(GOOD["deal"]["candidateId"].startswith("deal:00000000-"))

    def test_fixture_name_matches_the_skill_naming_rule(self):
        self.assertRegex(FIXTURE.name, SP.FILENAME_RE)

    def test_batch_form_is_accepted(self):
        other = mutate(lambda p: p["deal"].__setitem__("candidateId", "deal:00000000-0000-4000-8000-000000000001"))
        self.assertEqual(SP.check_payload({"packets": [GOOD, other]}), [])

    def test_cli_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            ok = Path(d) / "ScreenPacket_X_11232026.json"
            ok.write_text(json.dumps(GOOD), encoding="utf-8")
            bad = Path(d) / "ScreenPacket_Y_11232026.json"
            bad.write_text(json.dumps(mutate(lambda p: p.__setitem__("schema", "x"))), encoding="utf-8")
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(SP.main([str(ok)]), 0)
                self.assertEqual(SP.main([str(bad)]), 1)
                self.assertEqual(SP.main([str(Path(d) / "missing.json")]), 2)


class ImporterFormatRejects(unittest.TestCase):
    """Each case is a reject in import-acq-screen-packet.ts parseScreenPacket (PR #591)."""

    def assertRejects(self, packet, pattern):
        errs = SP.validate_packet(packet)
        self.assertTrue(any(re.search(pattern, e) for e in errs), f"no reject matching {pattern!r}: {errs}")

    def test_wrong_schema(self):
        self.assertRejects(mutate(lambda p: p.__setitem__("schema", "ora.acq-screen-packet/2")), r"^schema")

    def test_blank_skill_version(self):
        self.assertRejects(mutate(lambda p: p.__setitem__("skillVersion", "  ")), r"^skillVersion")

    def test_non_iso_screened_at(self):
        for bad in ("11/23/2026", "2026-02-30", "2026-11-23T10:00:00Z"):
            self.assertRejects(mutate(lambda p, b=bad: p.__setitem__("screenedAt", b)), r"^screenedAt")

    def test_no_deal_identity(self):
        self.assertRejects(mutate(lambda p: p.__setitem__("deal", {"address": "label only"})), r"needs candidateId")

    def test_unknown_envelope_key(self):
        self.assertRejects(mutate(lambda p: p.__setitem__("verdict", "T1")), r"unknown key")

    def test_unknown_input_key_is_a_reject_not_dropped(self):
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("stabilisedYoc", 0.08)), r"unknown key")

    def test_percent_form_rates_are_rejected_never_divided(self):
        for field, pct in (("stabilizedYoc", 8.5), ("unleveredIrr10yr", 10.5), ("leveredIrr", 12.0)):
            self.assertRejects(mutate(lambda p, f=field, v=pct: p["input"].__setitem__(f, v)), rf"input\.{field}.*decimal")

    def test_env_share_is_a_decimal(self):
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("envRemediationPctOfPrice", 5)), r"envRemediationPctOfPrice")

    def test_exit_cap_and_ust_bounds(self):
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("exitCapPct", 8.0)), r"exitCapPct")
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("exitCapPct", 0)), r"exitCapPct")
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("ust10yr", 4.5)), r"ust10yr")

    def test_negative_money_and_nonpositive_sf(self):
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("price", -1)), r"input\.price")
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("totalSf", 0)), r"input\.totalSf")

    def test_max_building_exceeds_total(self):
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("maxBuildingSf", 25000)), r"maxBuildingSf exceeds")

    def test_enums(self):
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("productType", "multifamily")), r"productType")
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("clusterTier", "tertiary")), r"clusterTier")
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("underwriteHorizonYrs", 7)), r"underwriteHorizonYrs")
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("rctAdders", ["mezzanine"])), r"rctAdders")

    def test_dd_known_values(self):
        self.assertRejects(mutate(lambda p: p["input"]["ddKnown"].__setitem__("roof", "yes")), r"ddKnown")

    def test_use_object_needs_all_three_flags(self):
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("use", {"automotive": False})), r"input\.use")

    def test_optional_envelope_keys_are_not_nullable(self):
        self.assertRejects(mutate(lambda p: p.__setitem__("sourceFiles", None)), r"^sourceFiles")
        self.assertRejects(mutate(lambda p: p.__setitem__("notes", None)), r"^notes")

    def test_blank_deal_id_is_rejected_even_beside_a_good_one(self):
        self.assertRejects(mutate(lambda p: p.__setitem__("deal", {"candidateId": " ", "notionPageId": "x"})), r"deal\.candidateId")

    def test_unhashable_values_reject_instead_of_crashing(self):
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("productType", [])), r"productType")
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("rctAdders", [[]])), r"rctAdders")
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("clusterTier", {})), r"clusterTier")

    def test_legacy_construction_alias_is_accepted_like_the_importer(self):
        self.assertEqual(SP.validate_packet(mutate(lambda p: p["input"].__setitem__("constructionType", "block-tilt-brick"))), [])

    def test_nested_extra_keys_are_an_importer_reject(self):
        # Merged importer (PR #591 merge gate S-1): a key Zod strips from ddKnown / use is a reject.
        self.assertRejects(mutate(lambda p: p["input"]["ddKnown"].__setitem__("roofs", True)), r"input\.ddKnown\.roofs")
        use = {"automotive": False, "childRelated": False, "childSafetyReviewed": False, "auto": False}
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("use", use)), r"input\.use\.auto")

    def test_future_screened_at_is_rejected(self):
        today = SP._dt.date(2026, 11, 24)
        self.assertEqual(SP.validate_packet(mutate(lambda p: p.__setitem__("screenedAt", "2026-11-25")), today=today), [])
        self.assertRejects_today(mutate(lambda p: p.__setitem__("screenedAt", "2062-11-23")), today, r"screenedAt.*future")
        self.assertRejects_today(mutate(lambda p: p.__setitem__("screenedAt", "2026-11-26")), today, r"screenedAt.*future")

    def assertRejects_today(self, packet, today, pattern):
        errs = SP.validate_packet(packet, today=today)
        self.assertTrue(any(re.search(pattern, e) for e in errs), f"no reject matching {pattern!r}: {errs}")

    def test_non_finite_numbers_are_rejected(self):
        # JSON 1e400 parses to inf in Python (Infinity in JS); the importer rejects it (merge gate C-3).
        self.assertEqual(json.loads('{"x": 1e400}')["x"], float("inf"))
        for field in ("truckCourtFt", "price", "yearBuilt", "underwriteHorizonYrs"):
            self.assertRejects(mutate(lambda p, f=field: p["input"].__setitem__(f, float("inf"))), rf"input\.{field}")

    def test_one_file_naming_a_candidate_twice_is_flagged(self):
        errs = SP.check_payload({"packets": [GOOD, GOOD]})
        self.assertTrue(any("twice" in e for e in errs), errs)

    def test_null_is_allowed_where_the_contract_is_nullable(self):
        self.assertEqual(SP.validate_packet(mutate(lambda p: p["input"].__setitem__("clearHeightFt", None))), [])

    def test_is_vacant_and_dd_known_are_not_nullable(self):
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("isVacant", None)), r"isVacant")
        self.assertRejects(mutate(lambda p: p["input"].__setitem__("ddKnown", None)), r"ddKnown")


class SkillProvenanceRules(unittest.TestCase):
    def test_left_null_is_required(self):
        p = mutate(lambda p: p["notes"].pop("left-null"))
        self.assertTrue(any("left-null" in e for e in SP.skill_rules(p)))

    def test_every_populated_field_needs_a_source_note(self):
        p = mutate(lambda p: p["notes"].pop("yearBuilt"))
        self.assertTrue(any("input.yearBuilt" in e for e in SP.skill_rules(p)))

    def test_combined_note_keys_cover_each_field(self):
        self.assertEqual(SP.skill_rules(GOOD), [])

    def test_notion_and_hubspot_twins_rejected(self):
        p = mutate(lambda p: p["deal"].__setitem__("hubspotDealId", "123"))
        self.assertTrue(any("ONE twin" in e for e in SP.skill_rules(p)))


class DocsTieToValidator(unittest.TestCase):
    def test_skill_md_carries_the_section_and_the_rules(self):
        self.assertIn("## SCREEN PACKET", SKILL_MD)
        for phrase in ("ora.acq-screen-packet/1", "ScreenPacket_<Property>_<MMDDYYYY>.json", "Blank beats inferred",
                       "left-null", "--dry-run", "scripts/acq-sync.ts", "import-acq-screen-packet.ts"):
            self.assertIn(phrase, SKILL_MD, phrase)

    def test_reference_lists_every_contract_field(self):
        for field in SP.INPUT_FIELDS:
            if field in ("dealId", "replacementCostBand"):
                continue  # dealId is filled by the importer; replacementCostBand is dormant in the engine
            self.assertIn(f"`{field}`", REFERENCE, field)


if __name__ == "__main__":
    unittest.main()
