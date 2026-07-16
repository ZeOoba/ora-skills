#!/usr/bin/env python3
"""Regression tests for pending_reimport.py's drift-sweep and candidate-union logic.

Stdlib only — run with `python tools/test_pending_reimport.py` (no pytest).

Covers the 2026-07-16 fix for the "retroactively blind" ledger defect: the
post-commit PENDING_REIMPORT.md ledger only ever records skills touched by a
commit AFTER tools/hooks/post-commit existed (e5903c2). Drift that predates the
hook (or a hook run that failed/was bypassed) was previously invisible to every
downstream consumer that read the ledger as authoritative-or-nothing. These
tests build synthetic repo/cache fixture trees (never the real ora-skills repo
or the real AppData runtime cache) so they're deterministic regardless of live
drift state.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_reimport as pr  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='')


class FixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='pending_reimport_test_'))
        self.repo = self.tmp / 'repo'
        self.cache = self.tmp / 'cache'
        self.repo.mkdir()
        self.cache.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class SweepDrift(FixtureTestCase):
    """Full repo-vs-cache SHA256 sweep — the mechanism a backfill/candidates
    pass uses to see drift the ledger never recorded."""

    def test_drifted_skill_with_no_ledger_history_is_detected(self):
        # Simulates a skill edited and pushed BEFORE tools/hooks/post-commit
        # existed: repo has v2 content, cache still has v1, and no ledger
        # entry was ever written for it.
        _write(self.repo / 'stale-skill' / 'SKILL.md', 'name: stale-skill\nversion 2\n')
        _write(self.cache / 'stale-skill' / 'SKILL.md', 'name: stale-skill\nversion 1\n')

        drifted = pr.sweep_drift(repo_root=self.repo, cache_root=self.cache)

        self.assertIn('stale-skill', drifted)

    def test_synced_skill_is_not_flagged(self):
        _write(self.repo / 'synced-skill' / 'SKILL.md', 'name: synced-skill\ncontent\n')
        _write(self.cache / 'synced-skill' / 'SKILL.md', 'name: synced-skill\ncontent\n')

        drifted = pr.sweep_drift(repo_root=self.repo, cache_root=self.cache)

        self.assertNotIn('synced-skill', drifted)

    def test_eol_normalization_does_not_false_positive(self):
        # Repo working copies are CRLF (autocrlf); platform-imported cache
        # copies are LF. Raw byte comparison must not call this drift.
        _write(self.repo / 'crlf-skill' / 'SKILL.md', 'name: crlf-skill\r\ncontent\r\n')
        _write(self.cache / 'crlf-skill' / 'SKILL.md', 'name: crlf-skill\ncontent\n')

        drifted = pr.sweep_drift(repo_root=self.repo, cache_root=self.cache)

        self.assertNotIn('crlf-skill', drifted)

    def test_never_installed_skill_is_repo_only_not_drift(self):
        # A skill with no cache dir at all was never installed -- that's
        # ora-skill-store-drift-check's separate REPO-ONLY category (step 3),
        # not "drifted, needs reimport". Conflating the two would flood the
        # ledger with e.g. the 7 plugin-migrated skills that were never
        # pushed through package-and-stage-skill in the first place
        # (confirmed against the live repo: annual-cycle, capex-budgeting,
        # cash-position-monitor, deal-retirement, investor-relations,
        # submarket-spatial-analysis, vendor-management all have no cache
        # dir and are not "reimport" candidates).
        _write(self.repo / 'never-installed' / 'SKILL.md', 'name: never-installed\n')
        # no cache dir at all for this skill

        drifted = pr.sweep_drift(repo_root=self.repo, cache_root=self.cache)

        self.assertNotIn('never-installed', drifted)

    def test_partial_install_missing_a_bundled_file_is_drifted(self):
        # The cache dir DOES exist (it was installed once) but is missing a
        # file the repo now ships -- a real completeness gap, distinct from
        # "never installed". Must still be flagged.
        _write(self.repo / 'partial-skill' / 'SKILL.md', 'name: partial-skill\n')
        _write(self.repo / 'partial-skill' / 'references' / 'extra.md', 'new content\n')
        _write(self.cache / 'partial-skill' / 'SKILL.md', 'name: partial-skill\n')
        # cache never got references/extra.md

        drifted = pr.sweep_drift(repo_root=self.repo, cache_root=self.cache)

        self.assertIn('partial-skill', drifted)

    def test_non_skill_dirs_are_ignored(self):
        # A repo-root dir without a SKILL.md (e.g. tools/, _archive/) must
        # never be treated as a candidate skill.
        _write(self.repo / 'tools' / 'pending_reimport.py', 'print(1)\n')

        drifted = pr.sweep_drift(repo_root=self.repo, cache_root=self.cache)

        self.assertEqual(drifted, [])

    def test_missing_cache_root_yields_no_false_drift(self):
        # An unreachable cache root (e.g. unattended session, wrong machine)
        # must not be reported as universal drift — that would be fabrication.
        _write(self.repo / 'some-skill' / 'SKILL.md', 'name: some-skill\n')

        drifted = pr.sweep_drift(repo_root=self.repo, cache_root=self.cache / 'does-not-exist')

        self.assertEqual(drifted, [])


class Candidates(FixtureTestCase):
    """candidates() = union of ledger entries and a fresh full sweep — the
    'ledger AND always-verify' contract, replacing 'ledger OR derive'."""

    def test_pre_hook_drift_surfaces_even_with_no_ledger_entry(self):
        _write(self.repo / 'pre-hook-skill' / 'SKILL.md', 'v2\n')
        _write(self.cache / 'pre-hook-skill' / 'SKILL.md', 'v1\n')
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'  # never written -> missing

        result = pr.candidates(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        self.assertIn('pre-hook-skill', result)

    def test_synced_skill_never_appears_as_a_candidate(self):
        _write(self.repo / 'clean-skill' / 'SKILL.md', 'same\n')
        _write(self.cache / 'clean-skill' / 'SKILL.md', 'same\n')
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'

        result = pr.candidates(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        self.assertNotIn('clean-skill', result)

    def test_ledger_only_entry_still_surfaces_even_if_sweep_cant_see_it(self):
        # A commit landed seconds ago; the ledger recorded it but the skill
        # dir doesn't exist in this fixture repo (simulating a race/edge case).
        # The ledger side of the union must not be dropped.
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'
        _write(ledger_path, '# header\n\n- in-flight-skill | pending since 2026-07-16T18:43Z | commit abc123\n')

        result = pr.candidates(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        self.assertIn('in-flight-skill', result)

    def test_candidates_is_read_only_never_mutates_ledger(self):
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'
        _write(self.repo / 'sweep-only-skill' / 'SKILL.md', 'v2\n')
        _write(self.cache / 'sweep-only-skill' / 'SKILL.md', 'v1\n')
        self.assertFalse(ledger_path.is_file())

        pr.candidates(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        self.assertFalse(ledger_path.is_file(), 'candidates() must never write the ledger')


class Backfill(FixtureTestCase):
    """backfill() persists sweep-detected drift into the ledger so it becomes
    durably visible (not just a one-off in-memory union)."""

    def test_backfill_seeds_drift_the_hook_never_recorded(self):
        _write(self.repo / 'old-drift' / 'SKILL.md', 'v2\n')
        _write(self.cache / 'old-drift' / 'SKILL.md', 'v1\n')
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'

        seeded = pr.backfill(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        self.assertIn('old-drift', seeded)
        self.assertTrue(ledger_path.is_file())
        self.assertIn('old-drift', ledger_path.read_text(encoding='utf-8'))

    def test_backfill_does_not_duplicate_existing_ledger_entries(self):
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'
        original_line = '- already-tracked | pending since 2026-07-16T14:50Z | commit e5903c2 "real commit"'
        _write(ledger_path, f'# header\n\n{original_line}\n')
        _write(self.repo / 'already-tracked' / 'SKILL.md', 'v2\n')
        _write(self.cache / 'already-tracked' / 'SKILL.md', 'v1\n')

        pr.backfill(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        text = ledger_path.read_text(encoding='utf-8')
        self.assertEqual(text.count('already-tracked'), 1)
        self.assertIn('e5903c2', text, 'a real commit-hash entry must not be clobbered by a backfill stub')

    def test_backfill_leaves_synced_skills_out_of_the_ledger(self):
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'
        _write(self.repo / 'clean' / 'SKILL.md', 'same\n')
        _write(self.cache / 'clean' / 'SKILL.md', 'same\n')

        seeded = pr.backfill(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        self.assertEqual(seeded, [])
        self.assertFalse(ledger_path.is_file())


if __name__ == '__main__':
    unittest.main(verbosity=2)
