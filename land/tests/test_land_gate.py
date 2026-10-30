#!/usr/bin/env python3
"""Tests for land_gate.evaluate. Stdlib only: python land/tests/test_land_gate.py"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import land_gate  # noqa: E402

ALLOW = json.loads(land_gate.DEFAULT_ALLOWLIST.read_text(encoding='utf-8'))
LH = 'Lighthouse budget (informational)'
OK_PR = {'state': 'OPEN', 'mergeable': 'MERGEABLE', 'reviewDecision': '', 'files': [{'path': 'a.md'}]}


def chk(name, bucket):
    return {'name': name, 'bucket': bucket, 'link': 'http://x'}


class LandGate(unittest.TestCase):
    def ev(self, repo, pr, checks):
        return land_gate.evaluate(repo, pr, checks, ALLOW)

    def test_green_is_go(self):
        r = self.ev('ZeOoba/ora-skills', OK_PR, [chk('skill-tests', 'pass'), chk('bot', 'skipping')])
        self.assertEqual(r['verdict'], 'GO')
        self.assertFalse(r['confirm_required'])

    def test_lighthouse_fail_is_informational(self):
        r = self.ev('ZeOoba/Website', OK_PR, [chk('Build & verify', 'pass'), chk(LH, 'fail')])
        self.assertEqual(r['verdict'], 'GO')
        self.assertEqual(len(r['informational']), 1)
        self.assertTrue(r['confirm_required'])

    def test_lighthouse_pending_does_not_block(self):
        self.assertEqual(self.ev('ZeOoba/Website', OK_PR, [chk(LH, 'pending')])['verdict'], 'GO')

    def test_other_red_check_stops_even_with_lighthouse_red(self):
        r = self.ev('ZeOoba/Website', OK_PR, [chk(LH, 'fail'), chk('Build & verify', 'fail')])
        self.assertEqual(r['verdict'], 'STOP')

    def test_allowlist_is_repo_scoped(self):
        self.assertEqual(self.ev('ZeOoba/ora-skills', OK_PR, [chk(LH, 'fail')])['verdict'], 'STOP')

    def test_pending_waits(self):
        self.assertEqual(self.ev('ZeOoba/ora-skills', OK_PR, [chk('t', 'pending')])['verdict'], 'WAIT')

    def test_stop_beats_wait(self):
        r = self.ev('ZeOoba/ora-skills', OK_PR, [chk('t', 'pending'), chk('u', 'fail')])
        self.assertEqual(r['verdict'], 'STOP')

    def test_conflicting_unknown_merged_and_review(self):
        for patch in ({'mergeable': 'CONFLICTING'}, {'mergeable': 'UNKNOWN'}, {'state': 'MERGED'},
                      {'reviewDecision': 'CHANGES_REQUESTED'}, {'reviewDecision': 'REVIEW_REQUIRED'}):
            r = self.ev('ZeOoba/ora-skills', {**OK_PR, **patch}, [])
            self.assertEqual(r['verdict'], 'STOP', patch)

    def test_approved_ok(self):
        r = self.ev('ZeOoba/ora-skills', {**OK_PR, 'reviewDecision': 'APPROVED'}, [])
        self.assertEqual(r['verdict'], 'GO')

    def test_blast_radius_flag(self):
        files = [{'path': 'hooks/x.py'}, {'path': 'sub/CLAUDE.md'}, {'path': 'CLAUDE.md'}, {'path': 'docs/a.md'}]
        r = self.ev('ZeOoba/ora-skills', {**OK_PR, 'files': files}, [])
        self.assertTrue(r['adversarial_review_required'])
        self.assertEqual(r['blast_radius_files'], ['CLAUDE.md', 'hooks/x.py', 'sub/CLAUDE.md'])
        self.assertFalse(self.ev('ZeOoba/ora-skills', OK_PR, [])['adversarial_review_required'])


if __name__ == '__main__':
    unittest.main()
