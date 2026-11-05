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
