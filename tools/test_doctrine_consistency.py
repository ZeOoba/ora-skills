#!/usr/bin/env python3
"""Tests for doctrine_consistency.py, the cross-skill restatement guard.

Written 2026-11-05. Stdlib unittest only: python tools/test_doctrine_consistency.py

Why: the 2026-11-05 data-flow review found facts paraphrased across skills drifting from
their source of truth in ways no existing probe saw. buybox-drift-probe checks price
statements and governor-drift-probe checks DSCR/LTV numbers. Neither checks:
  * cluster counts ("all ten canonical markets" while target-markets.json holds eleven);
  * target-geography lines that list only the holdings states, so verified-deal-recon's
    analyst was told Grand Rapids, Richmond, Des Moines, Louisville and Chicago were out
    of scope, and TN was in;
  * DSCR tested at the 40% portfolio-aggregate LTV instead of per-property refi sizing,
    the defect deal-comparison v1.2 fixed and portfolio-growth carried until v1.2.

The adversarial review of the first version (2026-11-05) supplied the misses and false
positives pinned in RoundTwo* below. The last class runs the checks on this repo: it is the gate.
"""
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doctrine_consistency as dc  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
MARKETS = ['Columbus OH', 'Kansas City MO/KS', 'Indianapolis IN', 'Maryland (Baltimore/DC)', 'Cincinnati OH',
           'Madison WI', 'Grand Rapids MI', 'Richmond VA', 'Des Moines IA', 'Louisville KY',
           'Chicago–Greater Cook County IL']
STATES = ['IA', 'IL', 'IN', 'KY', 'MD', 'MI', 'MO', 'OH', 'VA', 'WI']
CL = dc.Clusters(11, STATES, ['IN', 'MD', 'MO', 'OH', 'WI'], sorted(set(STATES) | {'KS', 'DC'}),
                 [(m, dc._cluster_tokens(m)) for m in MARKETS])


def messages(items):
    return [message for message, _ in items]


class CountClaimTests(unittest.TestCase):
    def check(self, line):
        return [c for c in dc.count_claims(line, 11) if c[0] == 'cluster-count']

    def test_wrong_canonical_count(self):
        self.assertEqual(len(self.check('run market-monitor across all ten canonical markets')), 1)

    def test_right_canonical_count(self):
        self.assertEqual(self.check('run market-monitor across all eleven canonical markets'), [])
        self.assertEqual(self.check('Eleven canonical clusters for ~27 properties'), [])

    def test_other_n_clusters_expects_n_minus_one(self):
        self.assertEqual(len(self.check('for each of the other 9 clusters')), 1)
        self.assertEqual(self.check('not tiered against the other ten clusters'), [])

    def test_target_market_clusters_and_oras_n_clusters(self):
        self.assertEqual(len(self.check("the canonical list of ORA's 10 target-market clusters")), 1)
        self.assertEqual(self.check("outside ORA's eleven clusters"), [])

    def test_unrelated_counts_are_ignored(self):
        self.assertEqual(self.check('500K+ SF / 140+ Tenants / 26 Properties / 3 Markets'), [])
        self.assertEqual(self.check('ratified as the 10th canonical cluster'), [])
        self.assertEqual(self.check('the other 9 counties in the ring'), [])


class RoundTwoCountTests(unittest.TestCase):
    """Misses and false positives from the 2026-11-05 adversarial reviews (finding C2c, rounds 1-2)."""

    def checks(self, line):
        return [c[0] for c in dc.count_claims(line, 11)]

    def test_oras_n_target_markets(self):
        self.assertEqual(self.checks("ORA's ten target markets"), ['cluster-count'])

    def test_other_n_target_markets_and_ora_clusters(self):
        self.assertEqual(self.checks('the other nine target markets'), ['cluster-count'])
        self.assertEqual(self.checks('the other eight ORA clusters are Tier B/C'), ['cluster-count'])

    def test_subset_excuse_is_reported_for_review_not_trusted(self):
        """Round 2: trusting a same-line subset passed the stale county-sales-monitor shape."""
        self.assertEqual(self.checks('Tier A covers three clusters; the other eight clusters are Tier B/C'),
                         ['cluster-count-subset'])
        self.assertEqual(self.checks('Tier A covers five clusters; the other eight clusters are Tier B/C'),
                         ['cluster-count'])

    def test_full_set_count_is_not_a_subset(self):
        found = dc.count_claims("Of ORA's eleven clusters, Tier A covers three clusters; the other eight clusters", 11)
        self.assertEqual([c[0] for c in found], ['cluster-count-subset'])
        self.assertNotIn('-3', found[0][1])

    def test_targets_n_clusters_and_ratified(self):
        self.assertEqual(self.checks('ORA now targets ten clusters'), ['cluster-count'])
        self.assertEqual(self.checks('not among the nine ratified clusters'), ['cluster-count'])


class TargetGeographyTests(unittest.TestCase):
    def check(self, line):
        return messages(dc.target_geography(line, CL))

    def test_target_line_missing_entry_states_and_listing_tn(self):
        found = self.check('ORA targets sub-$10M assets in OH, MD, IN, WI, MO, KS, and TN (DSCR >= 1.25x)')
        self.assertTrue(any('omits cluster states IA, IL, KY, MI, VA' in m for m in found))
        self.assertTrue(any('lists TN' in m for m in found))

    def test_target_markets_parenthetical(self):
        found = self.check('Covers all ORA target markets (OH, MD, IN, WI, MO, KS, TN) and submarkets.')
        self.assertTrue(any('omits cluster states' in m for m in found))

    def test_state_names_count_as_states(self):
        line = ("ORA's target-market clusters (Columbus OH, Kansas City MO/KS, Indianapolis IN, "
                "Maryland/Baltimore-DC, Madison WI, Grand Rapids MI, Richmond VA, Des Moines IA, Louisville KY)")
        found = self.check(line)
        self.assertTrue(any('omits cluster states IL ' in m for m in found))

    def test_holdings_statement_without_target_is_fine(self):
        self.assertEqual(self.check('ORA spans OH, MD, IN, WI, MO, KS and TN and the editions differ.'), [])

    def test_complete_target_line_is_fine(self):
        line = 'Covers every ORA target market: OH, MO/KS, IN, MD, WI, MI, VA, IA, KY and IL.'
        self.assertEqual(self.check(line), [])

    def test_short_state_mentions_are_not_target_lists(self):
        self.assertEqual(self.check('Target the MD and OH comps first'), [])

    def test_entry_phase_only_list_is_a_subset(self):
        line = ('Entry/beachhead clusters (score 4, "new target market") = Grand Rapids MI, Richmond VA, '
                'Des Moines IA, Louisville KY, Chicago-Greater Cook County IL')
        self.assertEqual(self.check(line), [])

    def test_counted_subset_is_not_the_target_set(self):
        line = ('Five of ten target clusters have no working local news source (OH, MO/KS, MI, KY, TN) and '
                'two are only partly covered (MD: DC/NoVA via Bisnow; WI: Milwaukee proxy).')
        self.assertEqual(self.check(line), [])

    def test_target_word_far_after_the_list_does_not_count(self):
        line = ('Cyclical states (OH/MD/IN/WI/MO/KS/TN/VA/IA/IL): tax chases market on the assessment cycle; '
                'a long clause later mentions the target markets only in passing, far past the list itself.')
        self.assertEqual(self.check(line), [])


class RoundTwoGeographyTests(unittest.TestCase):
    """Misses and false positives from the 2026-11-05 adversarial review (finding C2c)."""

    def check(self, line):
        return messages(dc.target_geography(line, CL))

    def test_dropping_one_city_in_a_shared_state_is_caught(self):
        line = ('ORA targets assets in its target-market clusters: Columbus OH, Kansas City MO/KS, Indianapolis IN, '
                'Maryland (Baltimore/DC), Madison WI, Grand Rapids MI, Richmond VA, Des Moines IA, '
                'Louisville KY and Chicago–Greater Cook County IL')
        found = self.check(line)
        self.assertTrue(any('missing Cincinnati OH' in m for m in found))

    def test_all_eleven_named_is_clean(self):
        line = ('ORA targets assets in its target-market clusters: Columbus and Cincinnati OH, Kansas City MO/KS, '
                'Indianapolis IN, Maryland (Baltimore/DC), Madison WI, Grand Rapids MI, Richmond VA, '
                'Des Moines IA, Louisville KY and Chicago–Greater Cook County IL')
        self.assertEqual(self.check(line), [])

    def test_target_word_just_after_the_list(self):
        found = self.check('OH, MD, IN, WI, MO, KS and TN are ORA\'s target states.')
        self.assertTrue(any('omits cluster states' in m for m in found))

    def test_non_geographic_targets_word(self):
        self.assertEqual(self.check('Tax-appeal filing targets: OH, MD, IN, WI, MO and KS this year.'), [])

    def test_state_labeled_watch_is_not_a_target_claim(self):
        line = ('- Target markets: OH, MD, IN, MO, KS, WI (Columbus, Cincinnati, Baltimore/DC, Indianapolis, Kansas '
                'City, Madison) + entry-phase MI (Grand Rapids), VA (Richmond), IA (Des Moines), KY (Louisville), '
                'IL (Chicago–Greater Cook County); TN watch')
        self.assertEqual(self.check(line), [])

    def test_holdings_line_that_mentions_targets_first(self):
        line = 'Unlike its target markets, ORA holds property in OH, MD, IN, WI, MO, KS and TN today.'
        self.assertEqual(self.check(line), [])


class AggregateLtvTests(unittest.TestCase):
    def test_dscr_tested_at_aggregate_ltv(self):
        self.assertEqual(len(dc.dscr_at_aggregate(
            'If DSCR <1.25x at 40% LTV: lower LTV until DSCR >=1.25x, or pass on the deal.')), 1)
        self.assertEqual(len(dc.dscr_at_aggregate('- DSCR cushion at 40% LTV')), 1)

    def test_round_two_variants(self):
        self.assertEqual(len(dc.dscr_at_aggregate('DSCR is tested at a 40% LTV for every deal')), 1)
        self.assertEqual(len(dc.dscr_at_aggregate('Size the loan at 40% LTV and confirm DSCR clears 1.25x')), 1)
        self.assertEqual(len(dc.dscr_at_aggregate('Size the loan to 40% LTV and confirm DSCR clears 1.25x')), 1)
        self.assertEqual(len(dc.dscr_at_aggregate('DSCR is tested at 40% loan-to-value')), 1)
        self.assertEqual(len(dc.dscr_at_aggregate('Debt service coverage is tested at 40% LTV')), 1)

    def test_governor_summary_is_not_a_dscr_basis(self):
        self.assertEqual(dc.dscr_at_aggregate('DSCR 1.25x per property; leverage capped at 40% LTV aggregate'), [])

    def test_correct_statements_pass(self):
        self.assertEqual(dc.dscr_at_aggregate(
            'size debt at the LESSER of 65% LTV per-property and 1.25x DSCR; 40% is the aggregate test'), [])
        self.assertEqual(dc.dscr_at_aggregate(
            'DSCR cushion at each deal\'s refi-sizing basis, and aggregate LTV against the 40% ceiling'), [])


class FloorAtLesserOfTests(unittest.TestCase):
    """Gabriel in-turn ratification 2026-11-08: the per-property 1.25x floor is DSCR at a loan sized
    to 65% LTV. A DSCR computed on the lesser-of loan is >= 1.25x by construction, so a floor stated
    against that loan can never flag (audit finding dscr-floor-unbreachable-at-lesser-of-sizing)."""

    def flags(self, line):
        return len(dc.dscr_floor_at_lesser_of(line))

    def test_pre_ratification_wordings_flag(self):
        for line in [
            # acquisition-underwriting STAGE 1, pre-v4.44
            '- **DSCR floor (per-property governor — v3.8):** post-refi DSCR must be ≥1.25x at the market-rate '
            'refi terms in UNDERWRITING CONVENTIONS (LESSER of 65% LTV per-property and 1.25x DSCR).',
            # deal-comparison pre-v1.7
            "**FLOOR FLAG (Ruling 5):** DSCR <1.25x at the deal's refi-sizing basis (the LESSER of 65% LTV "
            'per-property and 1.25x DSCR — see acquisition-underwriting Stage 1) = flag, not a kill.',
            '| DSCR at refi sizing (lesser of 65% LTV / 1.25x DSCR) | 10 | ≥2.5x=10; 1.25-1.99x=5; <1.25x=0 (FLOOR-FLAGGED) |',
            '| Any | Any | FLOOR-FLAGGED if DSCR <1.25x at refi sizing (Ruling 5 — flag, not a kill) |',
            '  DSCR @ refi sizing        X.Xx [X]   X.Xx [X]   <- lesser of 65% LTV / 1.25x DSCR',
            'FLOOR-FLAGGED?                       Y/N        Y/N   <- DSCR <1.25x at refi sizing (flag, not a kill)',
            # portfolio-growth pre-v1.3
            "Test DSCR at the deal's refi-sizing basis: the LESSER of 65% LTV per-property and 1.25x DSCR. "
            'If DSCR falls below 1.25x on that basis, size the loan down.',
            # variants
            'On the lesser-of loan, DSCR must clear 1.25x.',
            'Debt service coverage below 1.25x on the lesser-of-65%-LTV/1.25x-DSCR loan is FLOOR-FLAGGED.',
        ]:
            self.assertGreaterEqual(self.flags(line), 1, line)

    def test_ratified_basis_passes(self):
        for line in [
            '- **DSCR floor:** DSCR at a loan sized to 65% LTV, at the market refi terms, must be ≥1.25x; '
            'below 1.25x = FLOOR-FLAGGED. Lesser-of sizing (65% LTV / 1.25x DSCR) still sets refi proceeds.',
            '| DSCR at 65% LTV (floor basis; never the lesser-of loan) | 10 | ≥2.5x=10; <1.25x=0 (FLOOR-FLAGGED) |',
            'FLOOR-FLAGGED?   Y/N   Y/N   <- DSCR <1.25x on a 65%-LTV loan, i.e. DSCR binds under lesser-of sizing',
            'DSCR <1.25x at 65% LTV = flag, not a kill; equivalently DSCR, not LTV, binds under lesser-of sizing.',
            'The floor is never tested on the lesser-of loan, which clears 1.25x by construction.',
        ]:
            self.assertEqual(self.flags(line), 0, line)

    def test_review_round_one_misses(self):
        """2026-11-08 adversarial review: wordings the first version let through."""
        for line in [
            'Report PASS/BREACH: DSCR >=1.25x on the refi loan as sized.',
            'DSCR must clear 1.25x on the min(65% LTV, 1.25x DSCR) loan.',
            'DSCR must be >=1.25x at the smaller of 65% LTV and 1.25x DSCR.',
            'DSCR must be >=1.25x at the lower of 65% LTV and 1.25x DSCR.',
            'DSCR is tested against the 1.25x floor at refinance sizing.',
            'DSCR on refi-sized debt must be >=1.25x.',
            'DSCR (not debt yield) must be >=1.25x at the lesser-of loan.',
            'DSCR >=1.25x (cf. UNDERWRITING CONVENTIONS, i.e. the lesser of 65% LTV and 1.25x DSCR).',
            '| DSCR floor 1.25x | lesser of 65% LTV / 1.25x DSCR |',
            'Both DSCRs must be >=1.25x at refi sizing.',
            'The DSCR floor of 1.25x is tested on the modeled refi.',
        ]:
            self.assertGreaterEqual(self.flags(line), 1, line)

    def test_review_round_two_bare_numbers_are_not_sizing_caps(self):
        """Round 2 (C4b): a bare integer before DSCR ("Stage 1", "Year 1", "Module 2") is a label,
        not the "1.25x DSCR" sizing cap; x is required unless the number has a decimal or "minimum"."""
        for line in [
            'The Stage 1 DSCR floor of 1.25x is tested at refi sizing.',
            'Year 1 DSCR must be >=1.25x on the lesser-of loan.',
            'The Module 2 DSCR Check tests the 1.25x floor at refi sizing.',
            # portfolio-growth/SKILL.md:101 before v1.3
            "- DSCR cushion over the 1.25x floor on the scenario's own modeled debt (40% aggregate LTV), and "
            "the portfolio's aggregate LTV against the 40% ceiling. A specific deal's 65% / 1.25x refi-sizing "
            "test is the Module 2 DSCR Check, not a scenario output",
        ]:
            self.assertGreaterEqual(self.flags(line), 1, line)

    def test_review_round_two_65_ltv_paired_with_dscr_cap_is_not_trusted(self):
        """Round 2 (C4c): "65% LTV / 1.25x DSCR" names the lesser-of pair, not a 65%-LTV loan."""
        self.assertGreaterEqual(self.flags('DSCR must be >=1.25x at refi sizing (65% LTV / 1.25x DSCR).'), 1)
        self.assertGreaterEqual(self.flags('DSCR floor 1.25x: tested on the refi-sized loan (65% LTV and 1.25x DSCR).'), 1)
        self.assertEqual(self.flags('DSCR must be >=1.25x at a 65% LTV loan; refi sizing is separate.'), 0)

    def test_review_round_one_false_flags(self):
        for line in [
            'FLOOR-FLAG whenever DSCR is the binding constraint under lesser-of sizing.',
            'Flag below 1.25x: DSCR binds under lesser-of sizing.',
            'Report DSCR on the lesser-of loan too, but the 1.25x floor is tested at a 65%-LTV loan.',
            'Size the refi to the LESSER of 65% LTV and a 1.25 DSCR.',
            'Size the refi to the LESSER of 65% LTV and a 1.25x minimum DSCR.',
            'per UNDERWRITING CONVENTIONS: LESSER of 65% LTV and 1.25x DSCR, 25-yr amort — state which of LTV/DSCR binds',
        ]:
            self.assertEqual(self.flags(line), 0, line)

    def test_sizing_and_governor_summaries_pass(self):
        for line in [
            '- **All-cash bid + refi post-close (per-property governor: LESSER of 65% LTV and 1.25x DSCR).**',
            'refi sized to the LESSER of **65% LTV** (stabilized value at exit cap) **and 1.25x DSCR** (never exceed).',
            'DSCR binds whenever the exit cap is below 65% × 1.25 × the debt constant and LTV binds above it.',
            'No governor constant changed (DSCR 1.25x; 40% aggregate; 65% per-property).',
            'Three-scenario levered IRR through the full debt-sizing (LESSER of 65% LTV and 1.25x DSCR).',
        ]:
            self.assertEqual(self.flags(line), 0, line)

    def test_scan_reports_the_check(self):
        text = '# Demo (v1.0)\nFLOOR-FLAGGED if DSCR <1.25x at refi sizing.\n'
        with tempfile.TemporaryDirectory() as tmp:
            findings = dc.scan(make_repo(tmp, text))
        self.assertEqual([(f.line, f.check) for f in findings], [(2, 'dscr-floor-at-lesser-of')])


class FloorNoiBasisTests(unittest.TestCase):
    """Gabriel in-turn ruling 2026-11-08 (v4.45): the per-property floor DSCR at a 65%-LTV loan uses
    STABILIZED NOI, the NOI the refi is sized on. Year-1 DSCR is reported as its own coverage line and
    is not the floor."""

    def flags(self, line):
        return len(dc.dscr_floor_year1_noi(line))

    def test_year1_floor_statements_flag(self):
        for line in [
            # portfolio-growth/SKILL.md:75 at v1.3
            'DSCR = Year 1 NOI / Annual Debt Service on a loan sized to 65% LTV ≥ 1.25x',
            'DSCR on Year-1 NOI at a 65%-LTV loan must be >=1.25x.',
            'The floor DSCR uses Year 1 NOI.',
            'Year 1 DSCR must be >=1.25x at a loan sized to 65% LTV.',
            'FLOOR-FLAGGED if Year-1 DSCR <1.25x.',
            'Test the 1.25x DSCR floor on first-year NOI.',
            'DSCR floor: Y1 NOI over debt service at 65% LTV, >=1.25x.',
            'The DSCR floor is tested on going-in NOI at a 65%-LTV loan.',
            'Floor DSCR = Year One net operating income / debt service >= 1.25x.',
        ]:
            self.assertGreaterEqual(self.flags(line), 1, line)

    def test_stabilized_basis_and_reported_year1_pass(self):
        for line in [
            'DSCR = Stabilized NOI / Annual Debt Service on a loan sized to 65% LTV ≥ 1.25x',
            'The floor DSCR uses stabilized NOI, the same NOI the refi is sized on.',
            'Year-1 DSCR is reported as its own coverage line and is not the floor.',
            'Year 1 DSCR (Year 1 NOI / debt service on the same 65%-LTV loan) is reported; it is never the floor.',
            'The floor uses stabilized NOI, not Year-1 NOI.',
            'Report Year 1 NOI and going-in cap on the Returns tab.',
            'DSCR at maturity is reported under the refi-shock sub-case.',
            'The floor DSCR uses stabilized NOI rather than Year 1 NOI.',
        ]:
            self.assertEqual(self.flags(line), 0, line)

    def test_review_round_one_misses(self):
        """2026-11-08 adversarial review of v4.45: plural DSCRs, a "never the floor basis" elsewhere in
        the line, and a floor word split from the NOI phrase by ';' or "incl." all slipped through."""
        for line in [
            'Year-1 DSCRs below 1.25x are FLOOR-FLAGGED.',
            'The floor DSCR uses Year 1 NOI at a 65%-LTV loan, and the lesser-of loan is never the floor basis.',
            'FLOOR FLAG: DSCR <1.25x at a 65%-LTV loan; DSCR on Year-1 NOI, the NOI the refi is sized on.',
            'floors incl. per-property DSCR at a 65%-LTV loan on Year-1 NOI (v4.45) and the IRR floor',
        ]:
            self.assertGreaterEqual(self.flags(line), 1, line)

    def test_review_round_one_false_flags(self):
        for line in [
            'Year-1 DSCR is a coverage line separate from the 1.25x floor.',
            'The 1.25x floor DSCR uses stabilized NOI (going-in NOI is reported separately).',
        ]:
            self.assertEqual(self.flags(line), 0, line)

    def test_fails_closed_on_a_year1_figure_next_to_floor_wording(self):
        """Known, accepted noise: the whole-line read cannot tell a cited Year-1 value from a Year-1
        floor, so this correct line is flagged; reword it or allowlist the line."""
        self.assertEqual(self.flags('The floor uses stabilized NOI, not Year-1 NOI; a lease-up deal at 0.9x '
                                    'Year-1 DSCR still passes at 1.30x.'), 1)

    def test_every_live_stabilized_floor_line_flags_when_mutated_to_year1(self):
        """Mutation check over the live repo: each live line that states the floor on stabilized NOI
        must be flagged once 'stabilized NOI' is swapped for 'Year-1 NOI'."""
        mutated = []
        for path, rel in dc._files(dc.REPO):
            for number, line in dc.live_lines(path.read_text(encoding='utf-8')):
                if re.search(r'stabilized NOI', line, re.I) and re.search(r'DSCR', line) \
                        and re.search(r'65\s*%[- ]?LTV', line) and dc._FLOOR_CONTEXT.search(line):
                    mutated.append(('%s:%d' % (rel, number),
                                    re.sub(r'stabilized NOI', 'Year-1 NOI', line, flags=re.I)))
        self.assertGreaterEqual(len(mutated), 8, 'expected the v4.45 floor locations')
        missed = [where for where, line in mutated if not self.flags(line)]
        self.assertEqual(missed, [])

    def test_scan_reports_the_check(self):
        text = '# Demo (v1.0)\nDSCR = Year 1 NOI / debt service on a loan sized to 65% LTV >= 1.25x\n'
        with tempfile.TemporaryDirectory() as tmp:
            findings = dc.scan(make_repo(tmp, text))
        self.assertEqual([(f.line, f.check) for f in findings], [(2, 'dscr-floor-year1-noi')])


class HistorySkipTests(unittest.TestCase):
    def test_changelog_sections_and_version_bullets_are_skipped(self):
        text = '\n'.join([
            '# Skill (v1.3)',
            'Run across all ten canonical markets.',
            '## Changelog',
            '- the old text said all ten canonical markets',
            '## Procedure',
            '- v1.2 (2026-08-21): HIGH fix: DSCR was tested at 40% LTV, now fixed',
            '**v1.1 (2026-08-15):** Louisville became the 10th; all ten canonical markets',
            'Live line again: all ten canonical markets.',
        ])
        self.assertEqual([n for n, _ in dc.live_lines(text)], [1, 2, 5, 8])


def make_repo(tmp, skill_text):
    skill = Path(tmp, 'demo-skill')
    skill.mkdir()
    (skill / 'SKILL.md').write_text(skill_text, encoding='utf-8')
    Path(tmp, '_archive', 'old').mkdir(parents=True)
    Path(tmp, '_archive', 'old', 'SKILL.md').write_text('all ten canonical markets\n', encoding='utf-8')
    (skill / 'versions').mkdir()
    (skill / 'versions' / 'CHANGELOG.md').write_text('all ten canonical markets\n', encoding='utf-8')
    clusters = ','.join('{"state": "%s", "market": "%s", "status": "established"}' % (m.split()[-1][:2], m)
                        for m in MARKETS)
    Path(tmp, 'target-markets.json').write_text('{"clusters": [%s]}' % clusters, encoding='utf-8')
    return Path(tmp)


class ScanAndAllowlistTests(unittest.TestCase):
    """Finding C2b: an allowlist keyed by file and check hid any new defect in that file."""

    def setUp(self):
        self.saved = dict(dc.ALLOWED)

    def tearDown(self):
        dc.ALLOWED.clear()
        dc.ALLOWED.update(self.saved)

    def test_scan_reports_paths_and_line_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            findings = dc.scan(make_repo(tmp, '# Demo (v1.0)\nUse all ten canonical markets.\n'))
        self.assertEqual([(f.path, f.line, f.check) for f in findings], [('demo-skill/SKILL.md', 2, 'cluster-count')])

    def allow(self, line_text, phrase='all ten canonical markets'):
        dc.ALLOWED.clear()
        dc.ALLOWED[('demo-skill/SKILL.md', 'cluster-count', phrase, dc.line_key(line_text))] = (1, 'test')

    def test_allowlist_is_keyed_by_phrase(self):
        self.allow('Use all ten canonical markets.')
        text = '# Demo (v1.0)\nUse all ten canonical markets.\nThe other 9 clusters wait.\n'
        with tempfile.TemporaryDirectory() as tmp:
            findings = dc.scan(make_repo(tmp, text))
        self.assertEqual([(f.line, f.allowed) for f in findings], [(2, True), (3, False)])

    def test_allowlist_count_caps_a_repeated_phrase(self):
        self.allow('Use all ten canonical markets.')
        text = '# Demo (v1.0)\nUse all ten canonical markets.\nUse all ten canonical markets.\n'
        with tempfile.TemporaryDirectory() as tmp:
            findings = dc.scan(make_repo(tmp, text))
        self.assertEqual([f.allowed for f in findings], [True, False])

    def test_a_moved_phrase_is_unexplained(self):
        """Round 2: fixing the allowlisted line and adding the same phrase elsewhere read as clean."""
        self.allow('Use all ten canonical markets.')
        text = '# Demo (v1.0)\nUse every cluster in target-markets.json.\nLater: all ten canonical markets.\n'
        with tempfile.TemporaryDirectory() as tmp:
            findings = dc.scan(make_repo(tmp, text))
        self.assertEqual([(f.line, f.allowed) for f in findings], [(3, False)])


class LiveRepoGate(unittest.TestCase):
    def test_repo_has_no_unexplained_drift(self):
        unexplained = [str(f) for f in dc.scan(REPO) if not f.allowed]
        self.assertEqual([], unexplained)

    def test_every_allowlist_entry_matches_exactly_its_count(self):
        counts = {}
        for f in dc.scan(REPO):
            key = (f.path, f.check, f.phrase, f.linekey)
            counts[key] = counts.get(key, 0) + 1
        wrong = sorted((key, counts.get(key, 0), expected) for key, (expected, _) in dc.ALLOWED.items()
                       if counts.get(key, 0) != expected)
        self.assertEqual([], wrong, 'allowlist entries whose live count differs: fix the text or the entry')


if __name__ == '__main__':
    unittest.main()
