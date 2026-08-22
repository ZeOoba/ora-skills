#!/usr/bin/env python3
"""
Regression tests for diff_tenants.py's match_rr/diff (cc-audit-army 2026-08-21 finding
M10-diff-tenants-first-substring-match).

Stdlib only -- run with `python rent-roll-reconciliation/tests/test_diff_tenants.py`.

Pre-fix, match_rr did exactly what the skill's own SKILL.md step 4 prose warns against:
returned the FIRST token-substring hit with no SF/rent corroboration, could match the
same rent-roll row to more than one Notion record (many-to-one), applied its >2-char
floor only to the rent-roll token (never to the query name), and crashed with
AttributeError on a Notion "Tenant Name" field that is present but null.
"""
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))

from diff_tenants import diff, match_rr, build_rr_index  # noqa: E402


def rr_row(property_="123 Main St", contact="", company="", sf=None, monthly_rent=None, unit="A"):
    return {"property": property_, "unit": unit, "contact": contact, "company": company,
            "sf": sf, "monthly_rent": monthly_rent, "lease_start": None, "lease_end": None,
            "escalation_date": None, "escalation_pct": None}


def notion_rec(rec_id, name, sf=None, rent=None, property_="123 Main St"):
    return {"id": rec_id, "Tenant Name": name, "Property Address": property_,
            "SF": sf, "Monthly Rent": rent}


class TestAmbiguityAndCorroboration(unittest.TestCase):

    def test_shared_word_with_no_corroboration_is_ambiguous_not_matched(self):
        # The exact failure class SKILL.md history documents: two different tenants
        # sharing "Bay Area" must not silently resolve to whichever sorts first.
        rentroll = [rr_row(company="Bay Area Exteriors", sf=2000, monthly_rent=5000)]
        notion = [notion_rec("n1", "Bay Area Corporation", sf=9999, rent=9999)]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Bay Area Corporation", 9999, 9999, rr_idx)
        self.assertIsNone(rec)
        self.assertEqual(status, "ambiguous")

    def test_sf_corroboration_accepts_the_match(self):
        rentroll = [rr_row(company="Bay Area Exteriors", sf=2000, monthly_rent=5000)]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Bay Area Exteriors LLC", 2000, None, rr_idx)
        self.assertIsNotNone(rec)
        self.assertEqual(status, "matched")

    def test_rent_corroboration_accepts_the_match(self):
        rentroll = [rr_row(company="Bay Area Exteriors", sf=2000, monthly_rent=5000)]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Bay Area Exteriors LLC", None, 5000.00, rr_idx)
        self.assertIsNotNone(rec)
        self.assertEqual(status, "matched")

    def test_neither_sf_nor_rent_corroborated_is_ambiguous(self):
        rentroll = [rr_row(company="Acme Industries", sf=2000, monthly_rent=5000)]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Acme Industries LLC", 1234, 999.00, rr_idx)
        self.assertIsNone(rec)
        self.assertEqual(status, "ambiguous")

    def test_two_corroborated_candidates_is_ambiguous(self):
        # Both rent-roll rows corroborate on SF -- genuine ambiguity, must not guess.
        rentroll = [
            rr_row(company="Acme West", sf=1500, monthly_rent=4000, unit="A"),
            rr_row(company="Acme East", sf=1500, monthly_rent=4500, unit="B"),
        ]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Acme", 1500, None, rr_idx)
        self.assertIsNone(rec)
        self.assertEqual(status, "ambiguous")

    def test_no_candidate_at_all_returns_none_status(self):
        rentroll = [rr_row(company="Unrelated Tenant", sf=500, monthly_rent=1000)]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Completely Different Name", None, None, rr_idx)
        self.assertIsNone(rec)
        self.assertIsNone(status)


class TestOneToOneConsumption(unittest.TestCase):

    def test_a_matched_rr_row_cannot_also_match_a_second_notion_record(self):
        rentroll = [rr_row(company="Acme Industries", sf=2000, monthly_rent=5000)]
        rr_idx = build_rr_index(rentroll)
        rec1, status1 = match_rr("Acme Industries LLC", 2000, None, rr_idx)
        self.assertEqual(status1, "matched")
        # Same row, second lookup -- must now be consumed, not re-matched.
        rec2, status2 = match_rr("Acme Industries LLC", 2000, None, rr_idx)
        self.assertIsNone(rec2)


class TestLenFloorAppliesToBothSides(unittest.TestCase):

    def test_short_query_name_does_not_match_on_a_short_fragment(self):
        # Pre-fix, len(t) > 2 was checked on the rent-roll token only -- a 1-2 char
        # normalized query name could still match by being a substring of a longer
        # token. Both sides must clear the floor.
        rentroll = [rr_row(company="Co", sf=500, monthly_rent=1000)]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Co", 500, 1000, rr_idx)
        self.assertIsNone(rec)
        self.assertIsNone(status)


class TestNullTenantNameDoesNotCrash(unittest.TestCase):

    def test_null_tenant_name_field_does_not_crash_and_lands_in_no_match(self):
        # rec.get("Tenant Name", "") only supplies the default when the KEY is absent;
        # a present-but-null field still yields None, and pre-fix, None.startswith(...)
        # raised AttributeError. A null name has nothing to search on, so (unlike the
        # intentional "[Unknown"/"⛔" placeholder skip) it correctly surfaces in
        # no_match rather than being silently dropped -- the fix here is "does not
        # crash", not "gets special-cased".
        notion = [{"id": "n1", "Tenant Name": None, "Property Address": "123 Main St",
                   "SF": None, "Monthly Rent": None}]
        rentroll = [rr_row(company="Acme Industries", sf=2000, monthly_rent=5000)]
        mismatches, no_match, unmatched_rr, ambiguous = diff(notion, rentroll)  # must not raise
        self.assertEqual(mismatches, [])
        self.assertEqual(ambiguous, [])
        self.assertEqual(len(no_match), 1)
        self.assertEqual(no_match[0]["id"], "n1")


class TestDiffEndToEnd(unittest.TestCase):

    def test_ambiguous_records_are_reported_separately_never_merged_into_mismatches_or_no_match(self):
        notion = [notion_rec("n1", "Bay Area Corporation", sf=9999, rent=9999)]
        rentroll = [rr_row(company="Bay Area Exteriors", sf=2000, monthly_rent=5000)]
        mismatches, no_match, unmatched_rr, ambiguous = diff(notion, rentroll)
        self.assertEqual(mismatches, [])
        self.assertEqual(no_match, [])
        self.assertEqual(len(ambiguous), 1)
        self.assertEqual(ambiguous[0]["id"], "n1")

    def test_clean_corroborated_match_with_field_agreement_produces_no_mismatch(self):
        notion = [notion_rec("n1", "Acme Industries", sf=2000, rent=5000)]
        rentroll = [rr_row(company="Acme Industries LLC", sf=2000, monthly_rent=5000)]
        mismatches, no_match, unmatched_rr, ambiguous = diff(notion, rentroll)
        self.assertEqual(mismatches, [])
        self.assertEqual(no_match, [])
        self.assertEqual(unmatched_rr, [])
        self.assertEqual(ambiguous, [])

    def test_corroborated_match_with_a_real_field_mismatch_is_reported(self):
        notion = [notion_rec("n1", "Acme Industries", sf=2000, rent=4500)]  # rent stale
        rentroll = [rr_row(company="Acme Industries LLC", sf=2000, monthly_rent=5000)]
        mismatches, no_match, unmatched_rr, ambiguous = diff(notion, rentroll)
        self.assertEqual(len(mismatches), 1)
        self.assertIn("Monthly Rent", mismatches[0]["diffs"])


# cc-audit-army code-review finding (2026-08-22): corroborates() previously required SF or
# rent agreement to accept ANY match, even when neither field exists on the Notion side at
# all -- exactly the sparsest records this skill exists to fill in were silently diverted
# to "ambiguous", whose own resolution guidance (use SF/rent as deciding evidence) doesn't
# apply to them.
class TestMatchedUnverified(unittest.TestCase):

    def test_single_distinctive_candidate_with_no_sf_or_rent_data_is_accepted_unverified(self):
        rentroll = [rr_row(company="Acme Industries", sf=2000, monthly_rent=5000)]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Acme Industries LLC", None, None, rr_idx)
        self.assertIsNotNone(rec)
        self.assertEqual(status, "matched_unverified")

    def test_multiple_candidates_with_no_sf_or_rent_data_stay_ambiguous(self):
        # The exception is ONLY for a single candidate -- 2+ token-matched candidates with
        # nothing to corroborate against must not be guessed between.
        rentroll = [
            rr_row(company="Acme West", unit="A"),
            rr_row(company="Acme East", unit="B"),
        ]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Acme", None, None, rr_idx)
        self.assertIsNone(rec)
        self.assertEqual(status, "ambiguous")

    def test_attempted_and_failed_corroboration_stays_ambiguous_not_unverified(self):
        # Data present on both sides but disagreeing is a DIFFERENT case from no data at
        # all -- must not be swept into the same "accept it" exception.
        rentroll = [rr_row(company="Acme Industries", sf=2000, monthly_rent=5000)]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Acme Industries LLC", 9999, None, rr_idx)
        self.assertIsNone(rec)
        self.assertEqual(status, "ambiguous")

    def test_diff_surfaces_an_unverified_match_with_its_note_even_when_it_also_fills_in_missing_fields(self):
        # Notion has neither SF nor rent -- exactly the skill's own stated purpose (fill in
        # missing fields), so the normal per-field diff logic correctly reports both as
        # diffs (Notion is missing data the rent roll has). The "note" must ALSO be present
        # so a human knows this match itself was never corroborated, on top of those diffs.
        notion = [notion_rec("n1", "Acme Industries", sf=None, rent=None)]
        rentroll = [rr_row(company="Acme Industries LLC", sf=2000, monthly_rent=5000)]
        mismatches, no_match, unmatched_rr, ambiguous = diff(notion, rentroll)
        self.assertEqual(no_match, [])
        self.assertEqual(ambiguous, [])
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["diffs"], {"SF": (None, 2000), "Monthly Rent": (None, 5000)})
        self.assertIn("note", mismatches[0])
        self.assertIn("no SF/rent", mismatches[0]["note"])

    def test_diff_surfaces_an_unverified_match_with_zero_field_diffs_when_dates_also_agree(self):
        # A cleaner case: nothing to diff EXCEPT the corroboration itself is unverified.
        notion = [{"id": "n1", "Tenant Name": "Acme Industries", "Property Address": "123 Main St",
                   "SF": None, "Monthly Rent": None}]
        rentroll = [rr_row(company="Acme Industries LLC", sf=None, monthly_rent=None)]
        mismatches, no_match, unmatched_rr, ambiguous = diff(notion, rentroll)
        self.assertEqual(no_match, [])
        self.assertEqual(ambiguous, [])
        self.assertEqual(len(mismatches), 1)
        self.assertEqual(mismatches[0]["diffs"], {})
        self.assertIn("note", mismatches[0])
        self.assertIn("no SF/rent", mismatches[0]["note"])


# cc-audit-army code-review finding (2026-08-22): greedy single-pass consumption is
# order-dependent -- a later Notion record whose only candidate was already consumed by an
# earlier record must not read identically to "genuinely no candidate at all".
class TestConsumedByOther(unittest.TestCase):

    def test_second_record_losing_its_only_candidate_to_an_earlier_record_is_flagged_not_silently_no_match(self):
        rentroll = [rr_row(company="Acme Industries", sf=2000, monthly_rent=5000)]
        rr_idx = build_rr_index(rentroll)
        first_rec, first_status = match_rr("Acme Industries LLC", 2000, None, rr_idx)
        self.assertEqual(first_status, "matched")
        second_rec, second_status = match_rr("Acme Industries LLC", 2000, None, rr_idx)
        self.assertIsNone(second_rec)
        self.assertEqual(second_status, "consumed_by_other")

    def test_diff_routes_consumed_by_other_into_the_ambiguous_bucket(self):
        notion = [
            notion_rec("n1", "Acme Industries", sf=2000, rent=5000),
            notion_rec("n2", "Acme Industries", sf=2000, rent=5000),
        ]
        rentroll = [rr_row(company="Acme Industries LLC", sf=2000, monthly_rent=5000)]
        mismatches, no_match, unmatched_rr, ambiguous = diff(notion, rentroll)
        self.assertEqual(len(mismatches), 0)
        self.assertEqual(no_match, [])
        self.assertEqual(len(ambiguous), 1)
        self.assertEqual(ambiguous[0]["id"], "n2")

    def test_no_token_match_at_all_still_returns_plain_none_status_not_consumed_by_other(self):
        rentroll = [rr_row(company="Unrelated Tenant", sf=500, monthly_rent=1000)]
        rr_idx = build_rr_index(rentroll)
        rec, status = match_rr("Completely Different Name", None, None, rr_idx)
        self.assertIsNone(rec)
        self.assertIsNone(status)


if __name__ == "__main__":
    unittest.main()
