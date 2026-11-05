#!/usr/bin/env python3
"""Tests for doctrine_consistency.py, the cross-skill restatement guard.

Written 2026-11-05. Stdlib unittest only: python tools/test_doctrine_consistency.py

Why: the 2026-11-05 data-flow review found facts paraphrased across skills drifting from
their source of truth in ways no existing probe saw. buybox-drift-probe checks price
statements and governor-drift-probe checks DSCR/LTV numbers. Neither checks:
  * cluster counts ("all ten canonical markets" while target-markets.json holds eleven);
  * target-geography lines that list only the holdings states, so verified-deal-recon's
    analyst was told Grand Rapids, Richmond, Des Moines, Louisville and Chicago were out
    of scope;
  * DSCR tested at the 40% portfolio-aggregate LTV instead of per-property refi sizing,
    the defect deal-comparison v1.2 fixed and portfolio-growth still carries.

The last test runs the checks on this repo. It is the gate.
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import doctrine_consistency as dc  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
CLUSTER_STATES = ['OH', 'MO', 'IN', 'MD', 'WI', 'MI', 'VA', 'IA', 'KY', 'IL']


class CountClaimTests(unittest.TestCase):
    def check(self, line, n=11):
        return dc.count_claims(line, n)

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


ESTABLISHED = ['OH', 'MO', 'IN', 'MD', 'WI']


class TargetGeographyTests(unittest.TestCase):
    def check(self, line):
        return dc.target_geography(line, CLUSTER_STATES, ESTABLISHED, 11)

    def test_target_line_missing_entry_states(self):
        found = self.check('ORA targets sub-$10M assets in OH, MD, IN, WI, MO, KS, and TN (DSCR >= 1.25x)')
        self.assertEqual(len(found), 1)
        self.assertIn('IA, IL, KY, MI, VA', found[0])

    def test_target_markets_parenthetical(self):
        self.assertEqual(len(self.check('Covers all ORA target markets (OH, MD, IN, WI, MO, KS, TN) and submarkets.')), 1)

    def test_state_names_count_as_states(self):
        line = ("ORA's target-market clusters (Columbus OH, Kansas City MO/KS, Indianapolis IN, "
                "Maryland/Baltimore-DC, Madison WI, Grand Rapids MI, Richmond VA, Des Moines IA, Louisville KY)")
        found = self.check(line)
        self.assertEqual(len(found), 1)
        self.assertIn('omits cluster states IL ', found[0])

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

    def test_target_word_after_the_list_does_not_count(self):
        line = ('Cyclical states (OH/MD/IN/WI/MO/KS/TN/VA/IA/IL): tax chases market on the assessment cycle; '
                'a long clause later mentions the target markets only in passing, far past the list itself.')
        self.assertEqual(self.check(line), [])


class AggregateLtvTests(unittest.TestCase):
    def test_dscr_tested_at_aggregate_ltv(self):
        self.assertEqual(len(dc.dscr_at_aggregate(
            'If DSCR <1.25x at 40% LTV: lower LTV until DSCR >=1.25x, or pass on the deal.')), 1)
        self.assertEqual(len(dc.dscr_at_aggregate('- DSCR cushion at 40% LTV')), 1)

    def test_correct_statements_pass(self):
        self.assertEqual(dc.dscr_at_aggregate(
            'size debt at the LESSER of 65% LTV per-property and 1.25x DSCR; 40% is the aggregate test'), [])


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
        lines = [n for n, _ in dc.live_lines(text)]
        self.assertEqual(lines, [1, 2, 5, 8])

    def test_scan_reports_paths_and_line_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill = Path(tmp, 'demo-skill')
            skill.mkdir()
            (skill / 'SKILL.md').write_text('# Demo (v1.0)\nUse all ten canonical markets.\n', encoding='utf-8')
            (Path(tmp, '_archive', 'old')).mkdir(parents=True)
            (Path(tmp, '_archive', 'old', 'SKILL.md')).write_text('all ten canonical markets\n', encoding='utf-8')
            (skill / 'versions').mkdir()
            (skill / 'versions' / 'CHANGELOG.md').write_text('all ten canonical markets\n', encoding='utf-8')
            Path(tmp, 'target-markets.json').write_text(
                '{"clusters": [' + ','.join('{"state": "%s"}' % s for s in CLUSTER_STATES + ['OH']) + ']}',
                encoding='utf-8')
            findings = dc.scan(Path(tmp))
        self.assertEqual([(f.path, f.line, f.check) for f in findings],
                         [('demo-skill/SKILL.md', 2, 'cluster-count')])


class LiveRepoGate(unittest.TestCase):
    def test_repo_has_no_unexplained_drift(self):
        findings = dc.scan(REPO)
        unexplained = [f for f in findings if not f.allowed]
        self.assertEqual([], [str(f) for f in unexplained])

    def test_every_allowlist_entry_still_matches_something(self):
        findings = dc.scan(REPO)
        used = {(f.path, f.check) for f in findings if f.allowed}
        stale = sorted(set(dc.ALLOWED) - used)
        self.assertEqual([], stale, 'allowlist entries that no longer match: remove them')


if __name__ == '__main__':
    unittest.main()
