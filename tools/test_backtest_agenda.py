#!/usr/bin/env python3
"""Tests for backtest_agenda.py, the December back-test agenda compiler.

Written 2026-11-05 with the tool. Stdlib unittest only:
    python tools/test_backtest_agenda.py

Why the tool exists: acquisition-underwriting moves scorecard weights and constants ONLY
at the annual December back-test, and its admission rule sends every single-incident rule
to that session for review. On 2026-11-05 thirteen Rule Evidence entries carried
"Sunset: December 2026 back-test", but nothing compiled what the session had to review:
the inputs sat in the Rule Evidence ledger, the deal decision ledger and staged patches,
and a hand-written agenda from 2026-10-17 was already nine doctrine versions behind.

Synthetic fixtures pin the parsing rules. One smoke test runs the parsers against the live
acquisition-underwriting files, so a change to their format fails here instead of quietly
emptying the agenda.
"""
import datetime as dt
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_agenda as ba  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

CHANGELOG = """# Acquisition Underwriting: Changelog (single index, newest first)

## Version index

| Version | Date | Ratifier | Summary | Constants changed | Evidence ID |
|---|---|---|---|---|---|
| v9.2 | 2026-10-29 | Gabriel, in-turn | Two rules. | none | RE-9.2-1, RE-9.2-2 |

## Rule Evidence ledger (retro-tagged 2026-10-23)
Fields per the RULE EVIDENCE section of SKILL.md.

| Evidence ID | Entry | Incidents | Expected loss | Class | Testable via |
|---|---|---|---|---|---|
| RE-9.2-1 | Rule A | 1: Deal X (2026-10-29) | [UNQUANTIFIED: needs Y] | RATIFIED-JUDGMENT (Gabriel, in-turn); evidence: ORA-OBSERVED, EVIDENCE: SINGLE-INCIDENT | Metric A. Sunset: December 2026 back-test |
| RE-9.2-2 | Rule B | 0 (decided from review) | n/a | RATIFIED-JUDGMENT | Next screens; Sunset: December 2026 back-test |
| RE-9.1-1 | Rule C | 1: Deal Z | [UNQUANTIFIED] | ORA-OBSERVED, EVIDENCE: SINGLE-INCIDENT | Next deal |
| RE-9.1-1 | Rule D | 0 | [per archive] | [per archive] | none |
| RE-9.0-1 | Rule E | 2: Deal P, Deal Q | $5,000 per deal | EXTERNAL-ANCHORED | Variance_Review; sunset 2027-06-30 |

## Full entries (v4.36 onward)

| RE-9.9-9 | a row after the ledger section is not part of the ledger | x | x | x | Sunset: December 2026 back-test |
"""

SKILL_H1 = """---
name: acquisition-underwriting
description: "Use when..."
---

# Acquisition Underwriting — Oxford Realty Advisors (v9.2 — Buy Box & Scorecard v1.1)

Body.
"""

LEDGER = """---
name: deal-decision-ledger
---

# Deal Decision Ledger

| Date | Deal | Verdict | One-line reason | Buy-box rule validated / refined | FORT |
|---|---|---|---|---|---|
| 2026-11-04 | 1 Main St, Town WI | PASS | Gabriel-confirmed. | REFINED (ratified in-turn, staged as v9.3 patch): exit row 8.75% | — |
| 2026-10-30 | 2 Oak Ave, City OH | PASS at ask | Flip at market basis. | VALIDATED: lot/yard verification before underwriting | — |
| 2026-09-19 | 3 Elm Rd, City IN | PASS | Seller floor above walk. | Refines: a stale "proceed" row is not a mandate | — |
| 2026-08-24 | 4 Pine Ln, City MD | PASS | Notion Stage -> Passed; reason not logged elsewhere | — | — |
| 2025-06-01 | 5 Old Rd, City MO | PASS | Too old for the window. | REFINED: an old lesson | — |
| 2026-07-09 | 6 Lake Rd, City OH | TERMINATED | Phase II findings. | Materially-impaired Phase II findings: walk or re-trade | — |
"""

TARGET_MARKETS = '{"version": "9.9", "clusters": [{"state": "OH"}, {"state": "MO"}, {"state": "MI"}]}'

SESSION = dt.date(2026, 12, 16)


def write(dirpath, rel, text):
    path = Path(dirpath, rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    return path


def make_repo(tmp):
    write(tmp, 'acquisition-underwriting/versions/CHANGELOG.md', CHANGELOG)
    write(tmp, 'acquisition-underwriting/SKILL.md', SKILL_H1)
    write(tmp, 'target-markets.json', TARGET_MARKETS)
    return Path(tmp)


class EvidenceLedgerTests(unittest.TestCase):
    def setUp(self):
        self.rows = ba.parse_evidence_ledger(CHANGELOG)

    def test_parses_only_rows_inside_the_ledger_section(self):
        self.assertEqual([r['id'] for r in self.rows],
                         ['RE-9.2-1', 'RE-9.2-2', 'RE-9.1-1', 'RE-9.1-1', 'RE-9.0-1'])
        self.assertEqual(self.rows[0]['entry'], 'Rule A')
        self.assertEqual(self.rows[0]['incidents'], '1: Deal X (2026-10-29)')

    def test_single_incident_flag(self):
        flagged = [r['id'] for r in self.rows if r['single_incident']]
        self.assertEqual(flagged, ['RE-9.2-1', 'RE-9.1-1'])

    def test_sunset_text_is_extracted(self):
        self.assertEqual(self.rows[0]['sunset'], 'December 2026 back-test')
        self.assertEqual(self.rows[4]['sunset'], '2027-06-30')
        self.assertIsNone(self.rows[2]['sunset'])

    def test_sunset_due_by_session_year_and_by_date(self):
        due = [r['id'] for r in self.rows if ba.sunset_due(r['sunset'], SESSION)]
        self.assertEqual(due, ['RE-9.2-1', 'RE-9.2-2'])
        later = dt.date(2027, 7, 1)
        due_later = [r['id'] for r in self.rows if ba.sunset_due(r['sunset'], later)]
        self.assertEqual(due_later, ['RE-9.2-1', 'RE-9.2-2', 'RE-9.0-1'])

    def test_integrity_checks(self):
        problems = ba.evidence_integrity(self.rows)
        self.assertEqual(problems['duplicate_ids'], ['RE-9.1-1'])
        self.assertEqual(problems['single_incident_without_sunset'], ['RE-9.1-1'])
        self.assertEqual(problems['incomplete'], ['RE-9.1-1'])
        self.assertEqual(problems['unquantified'], ['RE-9.2-1', 'RE-9.1-1'])

    def test_missing_ledger_section_raises(self):
        with self.assertRaises(ba.AgendaError):
            ba.parse_evidence_ledger('# no ledger here\n')


INDEX = """# Acquisition Underwriting (v9.2 — Buy Box & Scorecard v1.1)

| Version | Date | Ratifier | Summary | Constants changed | Evidence ID |
|---|---|---|---|---|---|
| v9.2 | 2026-10-29 | Gabriel, in-turn | Two rules. | none | RE-9.2-1, RE-9.2-2 |
| v9.1 | 2026-10-17 | Gabriel, in-turn | Rule C. | none | RE-9.1-1 |
| v9.0 | 2025-09-01 | Gabriel | Rule E. | none | RE-9.0-1 |
| v8.0-v8.9 | see archives | | | | |

## BODY
"""


class DefaultSunsetTests(unittest.TestCase):
    """RULE EVIDENCE defaults: single-incident -> the next December back-test; otherwise the
    December back-test that follows the next 12 months of data."""

    def setUp(self):
        self.dates = ba.parse_version_dates(INDEX)
        self.rows = ba.apply_default_sunsets(ba.parse_evidence_ledger(CHANGELOG), self.dates)

    def test_version_dates(self):
        self.assertEqual(self.dates, {'9.2': dt.date(2026, 10, 29), '9.1': dt.date(2026, 10, 17),
                                      '9.0': dt.date(2025, 9, 1)})

    def test_single_incident_without_sunset_defaults_to_next_december(self):
        rule_c = self.rows[2]
        self.assertEqual((rule_c['id'], rule_c['sunset'], rule_c['sunset_default']),
                         ('RE-9.1-1', 'December 2026 back-test', True))
        self.assertTrue(ba.sunset_due(rule_c['sunset'], SESSION))

    def test_other_rule_without_sunset_defaults_twelve_months_out(self):
        rule_d = self.rows[3]
        self.assertEqual((rule_d['sunset'], rule_d['sunset_default']), ('December 2027 back-test', True))
        self.assertFalse(ba.sunset_due(rule_d['sunset'], SESSION))

    def test_explicit_sunsets_are_kept(self):
        self.assertEqual((self.rows[0]['sunset'], self.rows[0]['sunset_default']),
                         ('December 2026 back-test', False))

    def test_unknown_version_date_stays_unset(self):
        rows = ba.apply_default_sunsets(ba.parse_evidence_ledger(CHANGELOG), {})
        self.assertIsNone(rows[2]['sunset'])


class SunsetRobustnessTests(unittest.TestCase):
    """Review finding C1f: a rephrased sunset or a new column must never empty the agenda silently."""

    LEDGER_NEXT = CHANGELOG.replace('Metric A. Sunset: December 2026 back-test',
                                    'Metric A. Sunset: next December back-test')
    LEDGER_COLUMN = """## Rule Evidence ledger (retro-tagged 2026-10-23)

| Evidence ID | Entry | Incidents | Expected loss | Class | Testable via | Sunset review |
|---|---|---|---|---|---|---|
| RE-9.2-1 | Rule A | 1 | [UNQUANTIFIED] | EVIDENCE: SINGLE-INCIDENT | Metric A | December 2026 back-test |
| RE-9.2-2 | Rule B | 0 | n/a | RATIFIED-JUDGMENT | Next screens | when the register lands |
"""

    def test_next_december_resolves_from_the_version_date(self):
        rows = ba.apply_default_sunsets(ba.parse_evidence_ledger(self.LEDGER_NEXT), ba.parse_version_dates(INDEX))
        self.assertEqual((rows[0]['sunset'], rows[0]['sunset_basis']), ('December 2026 back-test', 'resolved'))
        self.assertTrue(ba.sunset_due(rows[0]['sunset'], SESSION))

    def test_sunset_column_is_read_by_header(self):
        rows = ba.parse_evidence_ledger(self.LEDGER_COLUMN)
        self.assertEqual([r['sunset'] for r in rows], ['December 2026 back-test', 'when the register lands'])
        self.assertEqual(rows[0]['testable'], 'Metric A')

    def test_unparsed_sunset_is_reported(self):
        rows = ba.apply_default_sunsets(ba.parse_evidence_ledger(self.LEDGER_COLUMN), ba.parse_version_dates(INDEX))
        self.assertEqual(ba.evidence_integrity(rows)['sunset_unparsed'], ['RE-9.2-2'])

    def test_missing_required_header_raises(self):
        broken = self.LEDGER_COLUMN.replace('| Evidence ID | Entry |', '| ID | Entry |')
        with self.assertRaises(ba.AgendaError):
            ba.parse_evidence_ledger(broken)


class DoctrineVersionTests(unittest.TestCase):
    def test_version_with_suffix_inside_parentheses(self):
        self.assertEqual(ba.parse_doctrine_version(SKILL_H1), '9.2')

    def test_plain_version(self):
        self.assertEqual(ba.parse_doctrine_version('# Annual Cycle (v1.2)\n'), '1.2')

    def test_no_version(self):
        self.assertIsNone(ba.parse_doctrine_version('# Title without a version\n'))

    def test_duplicate_version_labels_in_the_index(self):
        text = ('# T (v4.41)\n\n| Version | Date |\n|---|---|\n| v4.41 | 2026-10-30 |\n'
                '| v4.40 | 2026-10-30 |\n| v4.40 | 2026-10-29 |\n| v4.23-v4.28 | see archives |\n'
                '\n## BODY\n| v4.39 | not in the index |\n| v4.39 | still not |\n')
        self.assertEqual(ba.duplicate_versions(text), ['v4.40'])


class DecisionLedgerTests(unittest.TestCase):
    def test_window_and_classification(self):
        rows = ba.parse_decision_ledger(LEDGER, since=dt.date(2025, 12, 16))
        self.assertEqual([r['date'] for r in rows],
                         ['2026-11-04', '2026-10-30', '2026-09-19', '2026-08-24', '2026-07-09'])
        self.assertEqual([r['kind'] for r in rows], ['refined', 'validated', 'refined', 'none', 'other'])
        self.assertEqual(rows[0]['deal'], '1 Main St, Town WI')

    def test_unlabeled_lessons_are_rendered_not_dropped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            ledger = write(tmp, 'ledger.md', LEDGER)
            buf = io.StringIO()
            with redirect_stdout(buf):
                ba.main(['--repo', str(repo), '--session-date', '2026-12-16', '--ledger', str(ledger)])
        out = buf.getvalue()
        self.assertIn('Other lessons', out)
        self.assertIn('Materially-impaired Phase II findings', out)

    def test_reason_not_logged_is_flagged(self):
        rows = ba.parse_decision_ledger(LEDGER, since=dt.date(2025, 12, 16))
        self.assertEqual([r['date'] for r in rows if r['reason_missing']], ['2026-08-24'])


class PatchBaseTests(unittest.TestCase):
    """Stamp formats seen in the 2026-10-17 back-test package, plus the v4.8 rule's own form."""

    def scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, 'D1_patch.md', '# base: v9.1 · SKILL.md SHA256 abcdef012345 · 2026-10-17\nbody\n')
            write(tmp, 'D2_named.md', '# base: acquisition-underwriting v9.2 · SKILL.md SHA256 9e98546a47bb (CRLF form)\n')
            write(tmp, 'D3_loi.md', '# base: loi-generation · SKILL.md SHA256 5119f3126ff2 (LF blob at HEAD)\n')
            write(tmp, 'notes.md', 'no stamp here\n')
            write(tmp, 'deep/a/b/c/d/too-deep.md', '# base: v1.0\n')
            return {Path(p['path']).name: p for p in ba.scan_patch_bases(Path(tmp))}

    def test_stamp_formats(self):
        found = self.scan()
        self.assertEqual(sorted(found), ['D1_patch.md', 'D2_named.md', 'D3_loi.md', 'notes.md'])
        self.assertEqual((found['D1_patch.md']['skill'], found['D1_patch.md']['version']),
                         ('acquisition-underwriting', '9.1'))
        self.assertEqual((found['D2_named.md']['skill'], found['D2_named.md']['version']),
                         ('acquisition-underwriting', '9.2'))
        self.assertEqual((found['D3_loi.md']['skill'], found['D3_loi.md']['version'], found['D3_loi.md']['sha']),
                         ('loi-generation', None, '5119f3126ff2'))
        self.assertIsNone(found['notes.md']['skill'])

    def test_status_compares_each_stamp_with_its_own_skill(self):
        found = self.scan()
        versions = {'acquisition-underwriting': '9.2'}
        self.assertTrue(ba.patch_status(found['D1_patch.md'], versions).startswith('STALE BASE'))
        self.assertTrue(ba.patch_status(found['D2_named.md'], versions).startswith('CURRENT'))
        self.assertTrue(ba.patch_status(found['D3_loi.md'], versions).startswith('SHA STAMP'))
        self.assertTrue(ba.patch_status(found['notes.md'], versions).startswith('NO STAMP'))

    def test_matching_version_with_a_different_sha_is_stale(self):
        """Review finding C1e: two changes have shared one version label, so a version match is not enough."""
        found = self.scan()
        versions = {'acquisition-underwriting': '9.2'}
        same = {'acquisition-underwriting': {'9e98546a47bb' + '0' * 52}}
        other = {'acquisition-underwriting': {'f' * 64}}
        self.assertEqual(ba.patch_status(found['D2_named.md'], versions, same), 'CURRENT')
        self.assertTrue(ba.patch_status(found['D2_named.md'], versions, other).startswith('STALE BASE'))
        self.assertIn('SHA not checked', ba.patch_status(found['D2_named.md'], versions, {}))

    def test_sha_stamp_is_checked_against_the_current_file(self):
        found = self.scan()
        current = {'loi-generation': {'5119f3126ff2' + '0' * 52}}
        self.assertTrue(ba.patch_status(found['D3_loi.md'], {}, current).startswith('CURRENT'))
        changed = {'loi-generation': {'0' * 64}}
        self.assertTrue(ba.patch_status(found['D3_loi.md'], {}, changed).startswith('STALE BASE'))

    def test_file_shas_cover_lf_and_crlf_forms(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp, 'SKILL.md')
            path.write_bytes(b'line one\r\nline two\r\n')
            shas = ba.file_shas(path)
        self.assertIn(hashlib.sha256(b'line one\r\nline two\r\n').hexdigest(), shas)
        self.assertIn(hashlib.sha256(b'line one\nline two\n').hexdigest(), shas)


class RenderAndCliTests(unittest.TestCase):
    def run_main(self, argv):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ba.main(argv)
        return code, buf.getvalue()

    def test_agenda_sections_and_guard_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            ledger = write(tmp, 'ledger.md', LEDGER)
            patches = Path(tmp, 'patches')
            write(patches, 'D1_patch.md', '# base: v9.1 · SKILL.md SHA256 abcdef012345 · 2026-10-17\n')
            code, out = self.run_main(['--repo', str(repo), '--session-date', '2026-12-16',
                                       '--ledger', str(ledger), '--patches', str(patches)])
        self.assertEqual(code, 0)
        self.assertIn('proposes nothing', out)
        self.assertIn('v9.2', out)
        self.assertIn('RE-9.2-1', out)
        self.assertIn('Duplicate Evidence IDs: RE-9.1-1', out)
        self.assertIn('STALE BASE', out)
        self.assertIn('1 Main St, Town WI', out)
        self.assertNotIn('5 Old Rd', out)
        self.assertIn('every cluster in `target-markets.json` (3 at v9.9)', out)

    def test_missing_ledger_is_reported_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            code, out = self.run_main(['--repo', str(repo), '--session-date', '2026-12-16',
                                       '--ledger', str(Path(tmp, 'absent.md'))])
        self.assertEqual(code, 0)
        self.assertIn('deal decision ledger not found', out)

    def test_unreadable_doctrine_exits_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, 'acquisition-underwriting/SKILL.md', SKILL_H1)
            code, _ = self.run_main(['--repo', tmp, '--session-date', '2026-12-16', '--no-ledger'])
        self.assertEqual(code, 1)

    def test_bad_date_exits_2(self):
        code, _ = self.run_main(['--session-date', '2026-13-40', '--no-ledger'])
        self.assertEqual(code, 2)

    def test_out_file_is_written_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            out_path = Path(tmp, 'agenda.md')
            code, _ = self.run_main(['--repo', str(repo), '--session-date', '2026-12-16',
                                     '--no-ledger', '--out', str(out_path)])
            self.assertEqual(code, 0)
            self.assertIn('RE-9.2-1', out_path.read_text(encoding='utf-8'))


class LiveRepoSmokeTest(unittest.TestCase):
    """The parsers must keep working on the real files. A format change fails here."""

    def test_live_evidence_ledger_parses(self):
        text = (REPO / 'acquisition-underwriting/versions/CHANGELOG.md').read_text(encoding='utf-8')
        rows = ba.parse_evidence_ledger(text)
        self.assertGreaterEqual(len(rows), 10)
        for row in rows:
            self.assertRegex(row['id'], r'^RE-\d+\.\d+-\d+$')

    def test_live_doctrine_version_parses(self):
        text = (REPO / 'acquisition-underwriting/SKILL.md').read_text(encoding='utf-8')
        self.assertRegex(ba.parse_doctrine_version(text) or '', r'^\d+\.\d+$')

    def test_live_december_sunsets_produce_due_rows(self):
        """If the live ledger cites 'December <year>', that December's agenda cannot be empty."""
        import re
        text = (REPO / 'acquisition-underwriting/versions/CHANGELOG.md').read_text(encoding='utf-8')
        doctrine = (REPO / 'acquisition-underwriting/SKILL.md').read_text(encoding='utf-8')
        rows = ba.apply_default_sunsets(ba.parse_evidence_ledger(text), ba.parse_version_dates(doctrine))
        years = [int(y) for y in re.findall(r'December (\d{4}) back-test', text)]
        if not years:
            return  # nothing cites a December sunset, so there is nothing to lose (run_suite fails on skips)
        session = dt.date(max(years), 12, 16)
        self.assertGreater(sum(ba.sunset_due(r['sunset'], session) for r in rows), 0)

    def test_live_agenda_runs(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = ba.main(['--repo', str(REPO), '--session-date', '2026-12-16', '--no-ledger'])
        self.assertEqual(code, 0)
        self.assertIn('Rule Evidence up for review', buf.getvalue())


if __name__ == '__main__':
    unittest.main()
