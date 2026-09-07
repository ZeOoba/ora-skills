#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression tests for docx_edit_engine.py -- reproduce the four defects found by the
2026-09-07 Fable/Opus-pinned adversarial review (eos-review-gate.py, verdict `rejected`,
recorded in memory/event_log.md under "lease-generation skill landing attempted, blocked
at review gate"). Each test class below corresponds to one of the four MANDATORY defects
and must FAIL against the pre-fix engine, then PASS once the fix lands.

Stdlib + python-docx (to build fixtures) + lxml (engine dependency, already required by
docx_edit_engine.py itself). Run directly: `python lease-generation/tests/test_docx_edit_engine.py`
No pytest dependency required, matching tools/test_*.py and lease-form-qc/tests/test_lease_qc.py
convention in this repo -- though pytest will also discover and run this file unmodified.

DEFECT 1 -- sub_all skips table cells
  self.P (used by the pre-fix sub_all) is `self.body.findall('w:p', NS)`: direct-child
  paragraphs of <w:body> only. A table cell's paragraphs live under
  w:tbl/w:tr/w:tc/w:p, several levels below <w:body>, so `findall` (non-recursive) never
  sees them. A stale rent figure inside a rent-schedule table survives sub_all untouched,
  silently, with no error and no warning.

DEFECT 2 -- clean-mode substring-of-new self-match corruption
  sub_all's guard against re-matching inside text it just inserted --
  `if self.track and old in new: break` -- is gated on self.track. In redline mode this
  guard trips and sub_all does zero substitutions, then hard-fails loudly via its own
  `min` assertion (n=0 < minimum=1). In CLEAN mode (self.track is False) the guard never
  fires, so the `while ... in ...` loop re-finds `old` inside the very `new` text it just
  wrote (e.g. "Rent" inside "Base Rent") and keeps substituting into the freshly-inserted
  text, up to the 50-iteration cap -- silently corrupting the clean document, which is the
  one that actually ships.

DEFECT 3 -- set_body(keep=N) on a single-run paragraph
  set_body does `keep_runs, old = runs[:keep], runs[keep:]`. When a paragraph has exactly
  `keep` runs (e.g. one run, keep=1 -- the common case for a paragraph that was never
  split into a bold-title run + body runs), `old` is empty: nothing is removed, and the
  new text is inserted right after the preserved run -- i.e. appended after the existing
  text rather than replacing it. Exit code 0, two contradictory clauses left in the
  document (e.g. two different rent figures).

DEFECT 4 -- `fill` CLI doesn't enforce its own documented unfilled-token rule
  Both this script's own docstring ("any token found 0 times during a fill operation is a
  fill error") and lease-generation/SKILL.md say an unfilled token is a hard error. The
  `fill` CLI subcommand's actual behavior (pre-fix) only prints a WARNING and exits 0.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts'))
import docx_edit_engine as dee  # noqa: E402

from docx import Document  # noqa: E402  (python-docx -- fixture generation only)

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'docx_edit_engine.py')


def _engine_from(build_fn, track=False):
    """Build a fixture docx via build_fn(path), unpack it, and return a live Engine
    plus the temp dir (caller must rmtree it)."""
    tmp = tempfile.mkdtemp()
    docx_path = os.path.join(tmp, 'in.docx')
    build_fn(docx_path)
    unpack_dir = os.path.join(tmp, 'unpacked')
    dee._unpack(docx_path, unpack_dir)
    return dee.Engine(unpack_dir, track=track), tmp


class TestSubAllReachesTableCells(unittest.TestCase):
    """Defect 1: sub_all must walk paragraphs nested inside table cells (recursively),
    not just top-level body paragraphs. Uses an old/new pair with NO substring overlap
    ("Rent" / "Lease Payment") so this test is independent of Defect 2's fix."""

    @staticmethod
    def _build(path):
        doc = Document()
        doc.add_paragraph('The Rent for this Suite shall be as set forth in the schedule below.')
        table = doc.add_table(rows=1, cols=2)
        table.cell(0, 0).text = 'Year 1'
        table.cell(0, 1).text = 'Base Rent: $1,000.00 per month.'
        doc.save(path)

    def test_sub_all_updates_table_cell_paragraph(self):
        e, tmp = _engine_from(self._build, track=False)
        try:
            n = e.sub_all('Rent', 'Lease Payment', minimum=1)
            all_text = ' | '.join(e.text_of(p) for p in e.body.iter(dee.q('p')))
            self.assertIn(
                'Base Lease Payment: $1,000.00 per month.', all_text,
                'sub_all left the table-cell paragraph untouched (only scanned top-level '
                'body paragraphs): %r' % all_text)
            self.assertEqual(
                n, 2,
                'expected exactly 2 substitutions (one body paragraph, one table cell); '
                'got %d -- table cell was not reached' % n)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSubAllCleanModeSubstringSelfMatch(unittest.TestCase):
    """Defect 2: a substring-of-new pair ("Rent" -> "Base Rent") must not self-match and
    corrupt the document in CLEAN mode (self.track=False) -- the mode that ships."""

    @staticmethod
    def _build(path):
        doc = Document()
        doc.add_paragraph('Rent is due on the first day of each month.')
        doc.save(path)

    def test_clean_mode_does_not_corrupt(self):
        e, tmp = _engine_from(self._build, track=False)
        try:
            n = e.sub_all('Rent', 'Base Rent', minimum=1)
            text = e.text_of(e.P[0])
            self.assertEqual(
                n, 1,
                'expected exactly one legitimate substitution; got %d -- the '
                'substring-of-new guard is not protecting clean mode (self-match loop)' % n)
            self.assertEqual(
                text, 'Base Rent is due on the first day of each month.',
                'clean-mode substring-of-new self-match corrupted the paragraph: %r' % text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSubAllTabOffsetSpaceConsistency(unittest.TestCase):
    """Regression for a defect the 2026-09-07 second Fable-pinned independent review
    found in sub_all's start-offset bookkeeping: the existence check used text_of()
    (counts only <w:t> text, skipping <w:tab>/<w:noBreakHyphen> entirely) while `start`
    itself was expressed in _locate()'s offset space (via _segments(), which counts a
    tab as one character). On a paragraph with a tab (or no-break-hyphen) before a match,
    the text_of()-space search could land short of where the next real match actually is
    and silently stop early -- missing a later occurrence with no error, exactly the kind
    of silent skip Defect 1 was about. Fix: sub_all's existence check now goes through
    _locate() itself (single coordinate space), not text_of()."""

    @staticmethod
    def _build(path):
        doc = Document()
        p = doc.add_paragraph()
        p.add_run().add_tab()          # a real <w:tab/> before any text
        p.add_run('RentRent')          # two back-to-back, non-overlapping occurrences
        doc.save(path)

    def test_tab_before_match_does_not_hide_a_later_occurrence(self):
        e, tmp = _engine_from(self._build, track=False)
        try:
            n = e.sub_all('Rent', 'Lease Payment', minimum=1)
            text = e.text_of(e.P[0])
            self.assertEqual(
                n, 2,
                'expected both occurrences of "Rent" to be substituted; got %d -- a tab '
                'before the match desynced the existence-check offset space from the '
                'substitution offset space, silently hiding the second occurrence' % n)
            self.assertEqual(text, 'Lease PaymentLease Payment')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSubAllCleanRedlineEquivalence(unittest.TestCase):
    """Bonus regression for the root-cause fix: clean and redline mode should behave the
    SAME way on a substring-of-new pair (single shared code path), not silently corrupt
    in one mode while hard-failing in the other."""

    @staticmethod
    def _build(path):
        doc = Document()
        doc.add_paragraph('Rent is due on the first day of each month.')
        doc.save(path)

    def test_redline_mode_also_succeeds_cleanly(self):
        e, tmp = _engine_from(self._build, track=True)
        try:
            n = e.sub_all('Rent', 'Base Rent', minimum=1)
            self.assertEqual(n, 1, 'redline mode should perform the same one legitimate '
                                    'substitution as clean mode, not hard-fail at 0')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSubCrossesTrackedChangeBoundary(unittest.TestCase):
    """Regression for a defect the 2026-09-07 Fable-pinned independent review found IN
    THE FIRST ROUND OF THIS FIX (not one of the original four, but introduced by making
    <w:ins>-wrapped runs visible to _locate so later ops can still find live text a prior
    op inserted): a second op's match can straddle the boundary between plain
    (base-document) runs and an earlier op's <w:ins> wrapper. Merging across that
    boundary with no parent check either relabels original text as a fresh insertion
    (reviewer's first probe) or drops it with no <w:del> at all (reviewer's second probe)
    -- a real data-loss/mislabel risk on a legal instrument, and worse than the pre-fix
    behavior it replaced (a loud SUB FAILED). Must now fail loudly instead."""

    @staticmethod
    def _build(path):
        doc = Document()
        doc.add_paragraph('ABC def')
        doc.save(path)

    def test_second_op_spanning_earlier_insertion_boundary_fails_loudly(self):
        e, tmp = _engine_from(self._build, track=True)
        try:
            # First op: track-mode substitution creates a live <w:ins> for "XYZ".
            e.sub(e.P[0], 'ABC', 'XYZ')
            text_after_first = e.text_of(e.P[0])
            self.assertIn('XYZ', text_after_first)
            # Second op's match ("XYZ def") spans from inside that <w:ins> into the
            # trailing plain " def" run -- a mixed-parent span. Must not silently merge.
            with self.assertRaises(SystemExit):
                e.sub(e.P[0], 'XYZ def', 'QQQ')
            # And the original text must not have been silently corrupted/dropped by the
            # attempt -- text_of() should still account for every character that was
            # there before the second (failed) op, whatever XML shape it ended up in.
            text_after_attempt = e.text_of(e.P[0])
            self.assertIn('def', text_after_attempt,
                           '" def" appears to have been silently dropped by the failed '
                           'merge attempt: %r' % text_after_attempt)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestSetBodySingleRunParagraph(unittest.TestCase):
    """Defect 3: set_body(keep=1) on a paragraph with exactly one run must not silently
    append new text after the old text. Either a loud failure (SystemExit) or a correct
    replacement is acceptable; silently leaving both figures in the document is not."""

    @staticmethod
    def _build(path):
        doc = Document()
        doc.add_paragraph('Base Rent shall be $1,000.00 per month, payable in advance.')
        doc.save(path)

    def test_single_run_paragraph_fails_loudly_or_replaces_cleanly(self):
        e, tmp = _engine_from(self._build, track=False)
        try:
            ref = {'index': 0}
            runs_before = len(e.resolve(ref).findall('w:r', dee.NS))
            self.assertEqual(runs_before, 1,
                              'fixture must produce exactly one run for this test to be meaningful')
            try:
                e.set_body(ref, 'Base Rent shall be $2,000.00 per month, payable in advance.', keep=1)
            except SystemExit:
                return  # loud, documented failure is an acceptable fix
            text = e.text_of(e.resolve(ref))
            self.assertNotIn(
                '$1,000.00', text,
                'set_body silently APPENDED new text after old instead of replacing it '
                '(two contradictory rent figures now present): %r' % text)
            self.assertIn('$2,000.00', text)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestFillCLIUnfilledTokenExitCode(unittest.TestCase):
    """Defect 4: the `fill` CLI subcommand must exit non-zero when a token is found 0
    times, per its own docstring and SKILL.md's stated fill-error rule."""

    @staticmethod
    def _build(path):
        doc = Document()
        doc.add_paragraph('Tenant: [TENANT_NAME]')
        doc.add_paragraph('Suite: [SUITE_NUMBER]')
        doc.save(path)

    def test_fill_cli_nonzero_exit_on_unfilled_token(self):
        tmp = tempfile.mkdtemp()
        try:
            docx_path = os.path.join(tmp, 'in.docx')
            self._build(docx_path)
            tokens_path = os.path.join(tmp, 'tokens.json')
            out_path = os.path.join(tmp, 'out.docx')
            # RENT_AMOUNT is deliberately absent from the fixture document -> 0 occurrences.
            with open(tokens_path, 'w', encoding='utf-8') as f:
                json.dump({'TENANT_NAME': 'REDACTED-T01',
                           'RENT_AMOUNT': '$1,000.00'}, f)
            result = subprocess.run(
                [sys.executable, SCRIPT, 'fill', docx_path, tokens_path, out_path],
                capture_output=True, text=True)
            self.assertNotEqual(
                result.returncode, 0,
                'fill CLI must exit non-zero when a token is found 0 times; got exit 0. '
                'stdout=%r stderr=%r' % (result.stdout, result.stderr))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
