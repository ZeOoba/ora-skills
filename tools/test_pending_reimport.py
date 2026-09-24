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
import contextlib
import importlib
import io
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_reimport as pr  # noqa: E402


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='')


def _write_long(path: Path, text: str) -> None:
    """Like _write(), but long-path-safe for fixture paths that deliberately
    exceed Windows' 260-char MAX_PATH -- plain pathlib mkdir/write_text fail
    silently or raise on this machine (no LongPathsEnabled policy), same as the
    plain is_file()/read_bytes() reads the fix targets."""
    os.makedirs(pr._win_long(path.parent), exist_ok=True)
    with open(pr._win_long(path), 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def _rmtree(path: Path) -> None:
    """Long-path-safe: a fixture built past MAX_PATH (see WindowsMaxPath below) is
    invisible to a plain rmtree the same way it's invisible to a plain is_file().
    And git writes object files read-only, which rmtree cannot unlink on Windows --
    with ignore_errors=True every git-backed fixture leaked silently (~2,585 dirs in
    %TEMP% by 2026-09-23). Clear the bit and retry; still best-effort, so a locked
    file never fails a test."""
    def _retry(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:  # onexc can also hand over os.open/os.close
            pass
    shutil.rmtree(pr._win_long(path), onexc=_retry)


class FixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='pending_reimport_test_'))
        self.repo = self.tmp / 'repo'
        self.cache = self.tmp / 'cache'
        self.repo.mkdir()
        self.cache.mkdir()

    def tearDown(self):
        _rmtree(self.tmp)


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


class FrontmatterQuotingAndTrailingBlankLineIsNotDrift(FixtureTestCase):
    """2026-08-03: skill_drift_report.py's _normalize_frontmatter (PR #35,
    commit 3d15526, "YAML scalar quoting is serialization, not drift") strips
    top-level YAML scalar quoting before comparing frontmatter, because the
    Cowork platform re-serializes SKILL.md frontmatter on install and its
    quoting style varies over time. pending_reimport.py's OWN separate
    comparator (_normalized_hash/_normalized_hash_bytes, feeding
    skill_drifted() -> sweep_drift() -> candidates()) was not updated alongside
    it: a confirmed-correct Save-skill install of masterlease-jurisdiction-rebase
    -- content-verified identical to the repo except for that same quoting-class
    difference plus a trailing blank line -- still reported as a live-sweep
    candidate. These fixtures mirror test_skill_drift_report.py's quoting tests
    so the two comparators can never silently disagree again."""

    def test_name_quoting_difference_alone_is_not_drift(self):
        _write(self.repo / 'demo' / 'SKILL.md',
               '---\nname: "demo"\ndescription: d\n---\n\nBODY\n')
        _write(self.cache / 'demo' / 'SKILL.md',
               '---\nname: demo\ndescription: d\n---\n\nBODY\n')

        self.assertFalse(pr.skill_drifted(self.repo, self.cache, 'demo'))
        self.assertNotIn('demo', pr.sweep_drift(repo_root=self.repo, cache_root=self.cache))

    def test_single_and_double_quoting_agree(self):
        _write(self.repo / 'demo' / 'SKILL.md', "---\nname: 'demo'\ndescription: d\n---\n\nB\n")
        _write(self.cache / 'demo' / 'SKILL.md', '---\nname: demo\ndescription: d\n---\n\nB\n')

        self.assertFalse(pr.skill_drifted(self.repo, self.cache, 'demo'))

    def test_trailing_blank_line_alone_is_not_drift(self):
        _write(self.repo / 'demo' / 'SKILL.md', '---\nname: demo\ndescription: d\n---\n\nBODY\n')
        _write(self.cache / 'demo' / 'SKILL.md', '---\nname: demo\ndescription: d\n---\n\nBODY\n\n')

        self.assertFalse(pr.skill_drifted(self.repo, self.cache, 'demo'))

    def test_quoting_plus_trailing_blank_line_together_is_not_drift(self):
        """The live masterlease-jurisdiction-rebase case: both deltas at once."""
        _write(self.repo / 'demo' / 'SKILL.md',
               '---\nname: "demo"\ndescription: d\n---\n\nBODY\n')
        _write(self.cache / 'demo' / 'SKILL.md',
               '---\nname: demo\ndescription: d\n---\n\nBODY\n\n')

        self.assertFalse(pr.skill_drifted(self.repo, self.cache, 'demo'))
        self.assertNotIn('demo', pr.sweep_drift(repo_root=self.repo, cache_root=self.cache))

    def test_quoting_normalization_never_masks_a_real_content_change(self):
        """Same constraint PR #35 enforced: the normalization must never hide an
        actual value change, only a difference in how it was serialized."""
        _write(self.repo / 'demo' / 'SKILL.md',
               '---\nname: "demo"\ndescription: OLD\n---\n\nB\n')
        _write(self.cache / 'demo' / 'SKILL.md',
               '---\nname: demo\ndescription: NEW\n---\n\nB\n')

        self.assertTrue(pr.skill_drifted(self.repo, self.cache, 'demo'))
        self.assertIn('demo', pr.sweep_drift(repo_root=self.repo, cache_root=self.cache))

    def test_real_body_content_change_is_still_drift_even_with_quoting_noise(self):
        _write(self.repo / 'demo' / 'SKILL.md',
               '---\nname: "demo"\ndescription: d\n---\n\nBODY v1\n')
        _write(self.cache / 'demo' / 'SKILL.md',
               '---\nname: demo\ndescription: d\n---\n\nBODY v2\n\n')

        self.assertTrue(pr.skill_drifted(self.repo, self.cache, 'demo'))

    def test_non_frontmatter_file_trailing_blank_line_is_unaffected(self):
        """Scope guard: the trailing-blank-line collapse must stay confined to
        SKILL.md-shaped (frontmatter-fenced) content. A bundled non-SKILL.md file
        (e.g. a script) with a genuine trailing-blank-line difference must still
        hash differently -- this normalization was never asked for there, and
        widening it silently would risk masking real changes in bundled files
        that never had anything to do with the platform's frontmatter
        re-serialization behavior."""
        repo_hash = pr._normalized_hash_bytes(b'print(1)\n')
        cache_hash = pr._normalized_hash_bytes(b'print(1)\n\n')

        self.assertNotEqual(repo_hash, cache_hash)

    def test_frontmatter_quoting_fixture_pair_hashes_equal(self):
        """Direct unit coverage of the hashing primitive with a fixture pair that
        differs ONLY in quoting style, mirroring
        test_skill_drift_report.py's ReviewFindingsRemediation quoting tests."""
        repo_bytes = '---\nname: "demo"\ndescription: d\n---\n\nBODY\n'.encode('utf-8')
        cache_bytes = '---\nname: demo\ndescription: d\n---\n\nBODY\n'.encode('utf-8')

        self.assertEqual(pr._normalized_hash_bytes(repo_bytes),
                          pr._normalized_hash_bytes(cache_bytes))


class WindowsMaxPath(FixtureTestCase):
    """2026-08-03 regression: skill_drifted() used plain pathlib is_file()/
    read_bytes() against CACHE_ROOT, which silently reports a file MISSING once
    the resolved path exceeds Windows' legacy 260-char MAX_PATH -- even though
    the file is genuinely present and byte-identical. Caught live:
    masterlease-jurisdiction-rebase's bundled fixture
    (scripts/fixtures/ORA_MasterLease_ShallowBayIndustrial_v2.4.1_TEMPLATE.docx)
    resolves to a 265-char cache path and was flagged as sweep-drifted with an
    empty ledger entry, even though `main.log` showed a clean install and a
    byte-for-byte hash match once read with a `\\\\?\\`-prefixed path. These
    build a synthetic path past that threshold under a real temp dir (never the
    live AppData cache) so the test is deterministic regardless of machine or
    session state.

    Only the CACHE side is pushed past MAX_PATH -- mirroring production, where
    CACHE_ROOT is a fixed ~150-char deeply-nested AppData path and REPO is not.
    Deepening the repo side too would just prove pathlib's rglob() also breaks
    on a deep repo tree, a different (and not live) problem; skill_source_files()
    enumerates the REPO, which stays short in this codebase."""

    def setUp(self):
        super().setUp()
        # Simulate CACHE_ROOT's real depth (the live AppData path is ~150 chars
        # before a skill name is even appended) without hardcoding the live path.
        self.cache = self.cache.joinpath(
            *(f'deep_cache_root_segment_{i}' for i in range(4))
        )
        self.cache.mkdir(parents=True)

    def _long_rel(self, skill: str, leaf: str = 'fixture.docx') -> str:
        segments = []
        rel = leaf
        while len(str(self.cache / skill / rel)) <= 260:
            segments.append('nested_directory_segment')
            rel = '/'.join(segments + [leaf])
        assert len(str(self.repo / skill / rel)) <= 260, (
            'fixture rel path pushed the (short) repo side past MAX_PATH too -- '
            'this test is meant to isolate the cache-only long-path case'
        )
        return rel

    def test_identical_content_past_max_path_is_not_drifted(self):
        skill = 'long-path-skill'
        rel = self._long_rel(skill)
        content = 'identical content\n'
        _write(self.repo / skill / 'SKILL.md', 'name: long-path-skill\n')
        _write(self.cache / skill / 'SKILL.md', 'name: long-path-skill\n')
        _write(self.repo / skill / rel, content)
        _write_long(self.cache / skill / rel, content)
        self.assertGreater(len(str(self.cache / skill / rel)), 260)
        # Sanity: plain pathlib really does false-negative here on this machine --
        # otherwise this test would pass for the wrong reason (no LongPathsEnabled
        # policy, matching the live incident). WINDOWS-ONLY PRECONDITION: MAX_PATH
        # is a Windows limitation, so on POSIX (the CI runner) pathlib sees the
        # file and this would fail on a correct _win_long() no-op. The assertion
        # below is what the test is actually for and is checked on both platforms.
        if os.name == 'nt':
            self.assertFalse((self.cache / skill / rel).is_file())

        drifted = pr.sweep_drift(repo_root=self.repo, cache_root=self.cache)

        self.assertNotIn(skill, drifted)

    def test_genuinely_missing_file_past_max_path_is_still_drifted(self):
        skill = 'long-path-missing-skill'
        rel = self._long_rel(skill)
        _write(self.repo / skill / 'SKILL.md', 'name: long-path-missing-skill\n')
        _write(self.cache / skill / 'SKILL.md', 'name: long-path-missing-skill\n')
        _write(self.repo / skill / rel, 'only in repo\n')
        # cache never gets this file at all -- must still read as drifted, not
        # be masked by the long-path fix.

        drifted = pr.sweep_drift(repo_root=self.repo, cache_root=self.cache)

        self.assertIn(skill, drifted)

    def test_differing_content_past_max_path_is_drifted(self):
        skill = 'long-path-diff-skill'
        rel = self._long_rel(skill)
        _write(self.repo / skill / 'SKILL.md', 'name: long-path-diff-skill\n')
        _write(self.cache / skill / 'SKILL.md', 'name: long-path-diff-skill\n')
        _write(self.repo / skill / rel, 'repo version\n')
        _write_long(self.cache / skill / rel, 'cache version\n')

        drifted = pr.sweep_drift(repo_root=self.repo, cache_root=self.cache)

        self.assertIn(skill, drifted)


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

    def test_backfill_never_seeds_a_deliberately_unpublished_skill(self):
        """OI-157 extended to backfill (2026-09-07 adversarial review).

        candidates() already pops DELIBERATELY_UNPUBLISHED, but backfill WRITES the
        ledger and cmd_list() prints it unfiltered -- so seeding one of these puts a
        never-published skill in front of a batch Save-skill click. capex-budgeting
        was revived exactly that way on 2026-08-13.
        """
        victim = sorted(pr.DELIBERATELY_UNPUBLISHED)[0]
        _write(self.repo / victim / 'SKILL.md', 'v2\n')
        _write(self.cache / victim / 'SKILL.md', 'v1\n')
        _write(self.repo / 'ordinary-skill' / 'SKILL.md', 'v2\n')
        _write(self.cache / 'ordinary-skill' / 'SKILL.md', 'v1\n')
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'

        seeded = pr.backfill(repo_root=self.repo, cache_root=self.cache,
                             ledger_path=ledger_path)

        self.assertIn('ordinary-skill', seeded,
                      'the ordinary drifted skill must still seed')
        self.assertNotIn(victim, seeded)
        self.assertNotIn(victim, ledger_path.read_text(encoding='utf-8'))

    def test_backfill_does_not_rewrite_the_ledger_when_nothing_is_seeded(self):
        """write_entries() rebuilds the file from parsed "- <skill> |" lines only,
        so an unconditional write drops hand-added annotations. Tolerable when this
        ran only on commit; as of 2026-09-07 it also runs DAILY and unattended from
        ora-doctrine-integrity-guard, making the loss recurring and silent.
        """
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'
        original = ('# header' + chr(10) + chr(10)
                    + '- alpha | pending since 2026-07-16T14:50Z | commit e5903c2 "real"' + chr(10)
                    + 'NOTE hand-added by Gabriel: alpha is blocked on Eric' + chr(10))
        _write(ledger_path, original)
        _write(self.repo / 'alpha' / 'SKILL.md', 'v2\n')
        _write(self.cache / 'alpha' / 'SKILL.md', 'v1\n')

        seeded = pr.backfill(repo_root=self.repo, cache_root=self.cache,
                             ledger_path=ledger_path)

        self.assertEqual(seeded, [])
        self.assertEqual(ledger_path.read_text(encoding='utf-8'), original,
                         'a no-op backfill must leave the ledger byte-identical')

    def test_backfill_leaves_synced_skills_out_of_the_ledger(self):
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'
        _write(self.repo / 'clean' / 'SKILL.md', 'same\n')
        _write(self.cache / 'clean' / 'SKILL.md', 'same\n')

        seeded = pr.backfill(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        self.assertEqual(seeded, [])
        self.assertFalse(ledger_path.is_file())


class SharedDepClassify(unittest.TestCase):
    """classify_shared_copy() — the pure direction logic behind `shared-deps`.

    Guards the 2026-07-16 lesson: sweep_drift() flags a shared-dep mismatch once
    per consumer with no direction, so a stale cache (fix = reimport) reads the
    same as runtime-only content (fix = commit; a reimport would DOWNGRADE). This
    classifier must never conflate the two. No git needed — history is passed in."""

    def test_identical_content_is_in_sync(self):
        self.assertEqual(
            pr.classify_shared_copy('h1', 'h1', {'h1'}, {'h1'}), 'IN-SYNC')

    def test_cache_is_an_older_committed_version_is_repo_ahead(self):
        # cache 'old' sits on HEAD's ancestry; repo working file is 'new' -> reimport.
        self.assertEqual(
            pr.classify_shared_copy('old', 'new', {'old', 'new'}, {'old', 'new'}),
            'REPO-AHEAD')

    def test_cache_content_never_committed_is_cache_ahead(self):
        # The dangerous case: cache 'runtime' exists nowhere in history. A reimport
        # would overwrite it with the repo's 'repo' content -> must say CACHE-AHEAD.
        self.assertEqual(
            pr.classify_shared_copy('runtime', 'repo', {'repo'}, {'repo'}),
            'CACHE-AHEAD')

    def test_cache_matches_off_head_commit_is_divergent(self):
        # 'branchonly' is in all-history but not on HEAD's ancestry -> don't auto-reimport.
        self.assertEqual(
            pr.classify_shared_copy('branchonly', 'head', {'head'}, {'head', 'branchonly'}),
            'DIVERGENT')

    def test_git_unavailable_degrades_to_unknown_not_a_guess(self):
        # ancestor_hashes=None (git missing/untracked) and content differs -> UNKNOWN,
        # never a fabricated REPO-AHEAD/CACHE-AHEAD direction.
        self.assertEqual(
            pr.classify_shared_copy('x', 'y', None, None), 'UNKNOWN')

    def test_missing_repo_file_is_repo_missing(self):
        # repo_hash None means the declared shared dep no longer exists in the repo.
        self.assertEqual(
            pr.classify_shared_copy('x', None, {'x'}, {'x'}), 'REPO-MISSING')

    def test_in_sync_wins_even_when_git_history_is_unavailable(self):
        self.assertEqual(
            pr.classify_shared_copy('same', 'same', None, None), 'IN-SYNC')


class AffectedSkills(unittest.TestCase):
    """affected_skills() recognizes a repo-root SHARED_ROOT_DEPS file as a shared
    dep regardless of whether its source path lives at the repo root or nested in
    a subdirectory.

    Regression for the tuple-form fix (2026-08-17): the original guard was
    `if '/' not in f and f in SHARED_CONSUMERS`, which only ever worked because the
    sole real consumer at the time (target-markets.json) happens to sit at the repo
    root. Once tools/ora_doc_qc.py -- a SLASHED source path -- became a shared-dep
    source, that guard would have silently stopped firing the fast per-commit hook
    path for it: a commit touching tools/ora_doc_qc.py would never queue its three
    consumers into PENDING_REIMPORT.md via this fast path, only the slower full
    sweep_drift() SHA256 sweep would eventually catch it."""

    def test_top_level_dep_still_recognized(self):
        with unittest.mock.patch.object(
            pr, 'SHARED_CONSUMERS', {'target-markets.json': [('daily-brief', 'target-markets.json')]}
        ):
            hits = pr.affected_skills(['target-markets.json'])
        self.assertIn('daily-brief', hits)
        self.assertIn('target-markets.json (shared dep)', hits['daily-brief'])

    def test_nested_path_dep_now_recognized(self):
        with unittest.mock.patch.object(
            pr, 'SHARED_CONSUMERS', {'tools/shared.py': [('demo-skill', 'scripts/shared.py')]}
        ):
            hits = pr.affected_skills(['tools/shared.py'])
        self.assertIn('demo-skill', hits)
        self.assertIn('tools/shared.py (shared dep)', hits['demo-skill'])

    def test_unrelated_nested_file_is_not_a_false_positive(self):
        with unittest.mock.patch.object(
            pr, 'SHARED_CONSUMERS', {'tools/shared.py': [('demo-skill', 'scripts/shared.py')]}
        ):
            hits = pr.affected_skills(['some-other-skill/scripts/unrelated.py'])
        self.assertNotIn('demo-skill', hits)


def _git(repo: Path, *args: str) -> None:
    subprocess.run(['git', '-C', str(repo), *args], check=True,
                    capture_output=True, text=True)


def _git_commit(repo: Path, dep: str, content: str, message: str) -> None:
    (repo / dep).write_text(content, encoding='utf-8', newline='')
    _git(repo, 'add', dep)
    _git(repo, 'commit', '-m', message)


class SharedDepGitIntegration(FixtureTestCase):
    """End-to-end coverage for the git-integration layer behind `shared-deps`:
    _git_text / _git_blob_bytes / _file_history_hashes / shared_dep_report /
    shared_dep_problems, exercised against a REAL git repo (not just the pure
    classify_shared_copy() branch logic already covered above). Guards the
    reviewer-flagged gap: the pure classifier was tested, but nothing exercised
    the subprocess plumbing that actually feeds it live git history."""

    DEP = 'target-markets.json'
    # A real SHARED_ROOT_DEPS consumer name -- shared_dep_report() walks the
    # module-level SHARED_CONSUMERS reverse-map built from package_skills.py,
    # so the cache fixture must use one of the real consumer skill names.
    CONSUMER = 'acquisition-underwriting'

    def setUp(self):
        super().setUp()
        _git(self.repo, 'init', '-q', '-b', 'main')
        _git(self.repo, 'config', 'user.email', 'test@example.com')
        _git(self.repo, 'config', 'user.name', 'Test')

    def _cache_file(self, content: str) -> None:
        _write(self.cache / self.CONSUMER / self.DEP, content)

    def _report_status(self) -> str:
        report = pr.shared_dep_report(repo_root=self.repo, cache_root=self.cache)
        return report[self.DEP][self.CONSUMER]

    def test_in_sync_end_to_end(self):
        _git_commit(self.repo, self.DEP, 'v1\n', 'add')
        self._cache_file('v1\n')

        self.assertEqual(self._report_status(), 'IN-SYNC')
        self.assertEqual(pr.shared_dep_problems(
            pr.shared_dep_report(repo_root=self.repo, cache_root=self.cache)), [])

    def test_repo_ahead_end_to_end(self):
        # cache holds an OLDER committed version of the file -- reimport upgrades it.
        _git_commit(self.repo, self.DEP, 'v1\n', 'add v1')
        _git_commit(self.repo, self.DEP, 'v2\n', 'bump v2')
        self._cache_file('v1\n')

        self.assertEqual(self._report_status(), 'REPO-AHEAD')

    def test_cache_ahead_end_to_end(self):
        # cache holds content that was NEVER committed anywhere -- the dangerous
        # case a reimport would silently downgrade (the 2026-07-16 incident).
        _git_commit(self.repo, self.DEP, 'repo-content\n', 'add')
        self._cache_file('runtime-only-content\n')

        self.assertEqual(self._report_status(), 'CACHE-AHEAD')

    def test_divergent_end_to_end(self):
        # cache matches a commit that exists in history but is OFF HEAD's own
        # ancestry (a different branch) -- must never auto-reimport.
        _git_commit(self.repo, self.DEP, 'v1\n', 'add v1')
        _git(self.repo, 'checkout', '-q', '-b', 'other')
        _git_commit(self.repo, self.DEP, 'branch-only\n', 'branch edit')
        _git(self.repo, 'checkout', '-q', 'main')
        _git_commit(self.repo, self.DEP, 'v2\n', 'main bump v2')
        self._cache_file('branch-only\n')

        self.assertEqual(self._report_status(), 'DIVERGENT')

    def test_missing_in_cache_end_to_end(self):
        _git_commit(self.repo, self.DEP, 'v1\n', 'add')
        (self.cache / self.CONSUMER).mkdir(parents=True, exist_ok=True)
        # cache dir exists (skill is installed) but never got the shared dep file.

        self.assertEqual(self._report_status(), 'MISSING-IN-CACHE')

    def test_not_installed_end_to_end(self):
        _git_commit(self.repo, self.DEP, 'v1\n', 'add')
        # no cache dir at all for the consumer skill.

        self.assertEqual(self._report_status(), 'NOT-INSTALLED')

    def test_repo_missing_end_to_end(self):
        _git_commit(self.repo, self.DEP, 'v1\n', 'add')
        (self.repo / self.DEP).unlink()  # working-tree file gone, never committed as a delete
        self._cache_file('v1\n')

        self.assertEqual(self._report_status(), 'REPO-MISSING')

    def test_git_unavailable_degrades_to_unknown_not_a_guess(self):
        # A repo_root with no .git at all (e.g. untracked path) must degrade to
        # UNKNOWN rather than fabricating a direction -- never raises.
        non_git_root = self.tmp / 'not-a-repo'
        _write(non_git_root / self.DEP, 'content\n')
        self._cache_file('different-content\n')

        report = pr.shared_dep_report(repo_root=non_git_root, cache_root=self.cache)

        self.assertEqual(report[self.DEP][self.CONSUMER], 'UNKNOWN')

    def test_git_text_returns_none_for_non_repo(self):
        non_git_root = self.tmp / 'not-a-repo-2'
        non_git_root.mkdir()

        self.assertIsNone(pr._git_text(non_git_root, 'rev-list', 'HEAD', '--', self.DEP))

    def test_git_blob_bytes_returns_none_for_missing_rev(self):
        _git_commit(self.repo, self.DEP, 'v1\n', 'add')

        self.assertIsNone(pr._git_blob_bytes(self.repo, 'deadbeef', self.DEP))

    def test_file_history_hashes_none_none_when_file_never_committed(self):
        """REVERSED 2026-08-03 (code review). This test previously asserted
        `set()`, with a comment reasoning that a successful-but-empty rev-list
        "must not be conflated with git-unavailable". True at the git layer, wrong
        at the consumer: classify_shared_copy treats a non-None ancestor set as a
        completed search, so an empty set resolves to CACHE-AHEAD -- "this content
        was never committed anywhere" -- on no evidence whatsoever. Both cases mean
        the same thing to a DIRECTION verdict: nothing was searched. The old
        assertion certified the defect, which is why it survived review.

        Blast radius here is modest (no shared-dep remedy is a byte-exact copy),
        but the identical bug in skill_drift_report._part_history_hashes made an
        untracked SKILL.md report CACHE-NEWER and prescribe a destructive pull.
        """
        _git(self.repo, 'commit', '--allow-empty', '-q', '-m', 'empty init')
        ancestor, all_hist = pr._file_history_hashes(self.repo, self.DEP)

        self.assertIsNone(ancestor)
        self.assertIsNone(all_hist)

    def test_untracked_shared_dep_is_unknown_not_cache_ahead(self):
        """End-to-end consequence of the above: with no history to search, the
        direction must be UNKNOWN ("verify by hand"), not CACHE-AHEAD ("commit the
        runtime content back to the repo")."""
        _git(self.repo, 'commit', '--allow-empty', '-q', '-m', 'empty init')
        ancestor, all_hist = pr._file_history_hashes(self.repo, self.DEP)

        self.assertEqual(
            pr.classify_shared_copy('cachehash', 'repohash', ancestor, all_hist),
            'UNKNOWN')


class SharedDepReportTupleForm(FixtureTestCase):
    """shared_dep_report() resolves a tuple-form SHARED_CONSUMERS entry's DEST path
    -- not its source path -- when checking the runtime cache. Same source!=dest
    gap as AffectedSkills above, on the report/classify side instead of the fast
    per-commit hook side: SHARED_CONSUMERS now stores (skill, dest) pairs, and both
    the cache-existence check and the hash comparison must key off `dest`."""

    def test_report_reads_cache_at_dest_path_not_source_path(self):
        # No git init: classify_shared_copy() degrades gracefully without git
        # history (see test_in_sync_wins_even_when_git_history_is_unavailable
        # above) -- IN-SYNC still wins on matching content with no history at all.
        # This test only needs to prove the DEST path is what gets checked.
        _write(self.repo / 'tools' / 'shared.py', 'x = 1\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'shared.py', 'x = 1\n')

        with unittest.mock.patch.object(
            pr, 'SHARED_CONSUMERS', {'tools/shared.py': [('demo-skill', 'scripts/shared.py')]}
        ):
            report = pr.shared_dep_report(repo_root=self.repo, cache_root=self.cache)

        self.assertEqual(report['tools/shared.py']['demo-skill'], 'IN-SYNC')

    def test_missing_in_cache_checked_at_dest_path(self):
        _write(self.repo / 'tools' / 'shared.py', 'x = 1\n')
        (self.cache / 'demo-skill').mkdir(parents=True)
        # cache dir exists (skill installed) but nothing at scripts/shared.py.

        with unittest.mock.patch.object(
            pr, 'SHARED_CONSUMERS', {'tools/shared.py': [('demo-skill', 'scripts/shared.py')]}
        ):
            report = pr.shared_dep_report(repo_root=self.repo, cache_root=self.cache)

        self.assertEqual(report['tools/shared.py']['demo-skill'], 'MISSING-IN-CACHE')


class LedgerLineRouting(unittest.TestCase):
    """format_ledger_line() — plugin-bundled skills must be tagged with the
    plugin-rebuild remedy, never left to imply a standalone Save-skill install
    (the deal-retirement / submarket-spatial-analysis wrong-target, 2026-07-16)."""

    def test_standalone_skill_has_no_plugin_tag(self):
        line = pr.format_ledger_line(
            'acquisition-underwriting', '2026-07-16T23:00Z', 'abc1234',
            'fix something', 'acquisition-underwriting/SKILL.md', owner=None)
        self.assertIn('- acquisition-underwriting', line)
        self.assertNotIn('plugin:', line)
        self.assertNotIn('remedy:', line)

    def test_plugin_member_is_tagged_with_rebuild_remedy(self):
        line = pr.format_ledger_line(
            'deal-retirement', '2026-07-16T23:00Z', 'abc1234',
            'wire workflows', 'deal-retirement/SKILL.md',
            owner='ora-operations-extensions')
        self.assertIn('plugin: ora-operations-extensions', line)
        self.assertIn('build_plugin.py', line)
        self.assertIn('NOT a standalone Save-skill', line)

    def test_membership_routing_tags_bundled_and_not_standalone(self):
        # A bundled skill gets the plugin tag, a standalone one does not.
        # 2026-08-05: ora-operations-extensions was retired and archived, so there
        # is no live bundle to read membership from — the owner is passed
        # explicitly here to keep the routing behavior itself covered.
        bundled = pr.format_ledger_line(
            'submarket-spatial-analysis', 'now', 'h', 's', 't',
            owner='ora-operations-extensions')
        standalone = pr.format_ledger_line(
            'daily-brief', 'now', 'h', 's', 't', pr.plugin_of('daily-brief'))
        self.assertIn('plugin: ora-operations-extensions', bundled)
        self.assertNotIn('plugin:', standalone)

    def test_live_membership_is_empty_after_bundle_retirement(self):
        # Post-retirement invariant: every skill routes as a standalone
        # Save-skill install, so no ledger line carries a plugin tag.
        for s in ('submarket-spatial-analysis', 'deal-retirement', 'daily-brief'):
            self.assertIsNone(pr.plugin_of(s))
            line = pr.format_ledger_line(s, 'now', 'h', 's', 't', pr.plugin_of(s))
            self.assertNotIn('plugin:', line)


class WinLongNonWindowsNoOp(unittest.TestCase):
    """2026-08-03: _win_long() unconditionally prepended the `\\\\?\\` prefix,
    which is meaningless outside Windows. Resolving a path from a POSIX context
    (e.g. this script run via Cowork's bash sandbox against the mounted repo)
    then produced a string neither OS could open, surfacing as a silent
    `pending_reimport: skipped (...)` rather than the loud failure the ledger
    exists to produce.

    Can't exercise a real cross-platform run on this Windows box, and patching
    os.name alone isn't enough: it's a process-global flag pathlib itself
    dispatches on, so calling the real WindowsPath.resolve() while os.name says
    'posix' crashes with UnsupportedOperation rather than exercising the guard.
    Path is stubbed out here so the test isolates the `if os.name != 'nt'`
    branch in _win_long() from real path resolution."""

    def _win_long_with(self, os_name, resolved):
        fake_resolved = unittest.mock.MagicMock()
        fake_resolved.__str__.return_value = resolved
        fake_path = unittest.mock.MagicMock()
        fake_path.resolve.return_value = fake_resolved
        with unittest.mock.patch.object(pr, 'Path', return_value=fake_path), \
                unittest.mock.patch.object(pr.os, 'name', os_name):
            return pr._win_long('irrelevant-input')

    def test_prefix_skipped_when_not_windows(self):
        result = self._win_long_with('posix', '/sessions/example/ora-skills/target-markets.json')
        self.assertEqual(result, '/sessions/example/ora-skills/target-markets.json')
        self.assertFalse(result.startswith('\\\\?\\'))

    def test_prefix_applied_when_windows(self):
        result = self._win_long_with('nt', r'C:\Users\Owner\ora-skills\target-markets.json')
        self.assertTrue(result.startswith('\\\\?\\'))


class DeliberatelyUnpublished(FixtureTestCase):
    """Skills in DELIBERATELY_UNPUBLISHED (package_skills.py) must never surface
    as a candidate, from either the ledger or a fresh sweep -- OI-157:
    capex-budgeting was deliberately unpublished 2026-08-09, then a docs-only
    repo commit on 2026-08-12 made it look like ordinary reimport drift, got it
    staged, and Gabriel accidentally re-registered it in a routine Save-skill
    batch click on 2026-08-13. candidates() is the single consumption contract
    every downstream caller (package-and-stage-skill Entry Point A included)
    reads from, so filtering there closes the gap regardless of whether a given
    skill's drift was detected via the post-commit ledger or the full sweep."""

    def test_ledger_entry_for_unpublished_skill_is_suppressed(self):
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'
        _write(ledger_path, '# header\n\n- retired-skill | pending since 2026-08-12T00:00Z | commit abc123\n')

        with unittest.mock.patch.object(pr, 'DELIBERATELY_UNPUBLISHED', frozenset({'retired-skill'})):
            result = pr.candidates(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        self.assertNotIn('retired-skill', result)

    def test_sweep_drift_for_unpublished_skill_is_suppressed(self):
        _write(self.repo / 'retired-skill' / 'SKILL.md', 'v2\n')
        _write(self.cache / 'retired-skill' / 'SKILL.md', 'v1\n')
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'

        with unittest.mock.patch.object(pr, 'DELIBERATELY_UNPUBLISHED', frozenset({'retired-skill'})):
            result = pr.candidates(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        self.assertNotIn('retired-skill', result)

    def test_unrelated_skill_still_surfaces_normally(self):
        # Regression guard: the exclusion set must not swallow unrelated skills.
        _write(self.repo / 'active-skill' / 'SKILL.md', 'v2\n')
        _write(self.cache / 'active-skill' / 'SKILL.md', 'v1\n')
        ledger_path = self.tmp / 'PENDING_REIMPORT.md'

        with unittest.mock.patch.object(pr, 'DELIBERATELY_UNPUBLISHED', frozenset({'retired-skill'})):
            result = pr.candidates(repo_root=self.repo, cache_root=self.cache, ledger_path=ledger_path)

        self.assertIn('active-skill', result)

    def test_real_capex_budgeting_is_in_the_exclusion_set(self):
        # Pins the production set that motivated this class -- OI-157 is a real,
        # already-happened incident, not a hypothetical. If this set legitimately
        # changes (e.g. Gabriel republishes one of the six), update this test
        # deliberately rather than letting it silently drift.
        #
        # 2026-09-11 (ORA Setup Audit R25 remediation): vendor-management left
        # this set on Gabriel's explicit in-turn re-publish decision (commit
        # 97ff6a4) -- exactly the deliberate-update case this comment already
        # anticipated. Five remain.
        self.assertEqual(
            pr.DELIBERATELY_UNPUBLISHED,
            frozenset({
                'annual-cycle', 'capex-budgeting', 'cash-position-monitor',
                'deal-retirement', 'investor-relations',
            }),
        )

    def test_cmd_candidates_reports_suppressed_skills(self):
        # cmd_candidates() must not silently drop these -- "no silent caps" is
        # this codebase's own standing rule (e.g. _print_shared_dep_advisory).
        # candidates()/read_entries()/sweep_drift() default arguments bind to
        # REPO/CACHE_ROOT/LEDGER at function-DEFINITION time, so patching those
        # module attributes afterward has no effect on cmd_candidates()'s
        # already-bound defaults -- mock the functions cmd_candidates() actually
        # calls instead (name lookups inside a function body ARE late-bound).
        with unittest.mock.patch.object(pr, 'DELIBERATELY_UNPUBLISHED', frozenset({'retired-skill'})), \
             unittest.mock.patch.object(pr, 'candidates', return_value={}), \
             unittest.mock.patch.object(pr, 'read_entries', return_value={'retired-skill': '- retired-skill | ...'}), \
             unittest.mock.patch.object(pr, 'sweep_drift', return_value=[]), \
             unittest.mock.patch.object(pr, '_print_shared_dep_advisory'), \
             unittest.mock.patch('sys.stdout', new_callable=__import__('io').StringIO) as out:
            pr.cmd_candidates()

        self.assertIn('retired-skill', out.getvalue())
        self.assertIn('suppressed', out.getvalue())


class ChangedFilesMergeCommit(unittest.TestCase):
    """`changed_files()` feeds cmd_record(), which the post-commit hook calls on
    every commit. Proven blind spot (2026-09-07, Automation Audit R23 close-out):
    plain `git diff-tree -r <merge>` prints NOTHING for a merge commit, so a
    branch merged into main recorded ZERO ledger lines -- package-and-stage-skill
    (577397f, merged as db7ea76) and tenant-intelligence (00c553b, merged as
    3a2f352) both changed packaged SKILL.md content and produced no PENDING
    REIMPORT entry, leaving the store serving stale bytes under a current version
    token. Non-merge commits must keep their exact prior file list."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='pending_reimport_merge_'))
        self.repo = self.tmp / 'repo'
        self.repo.mkdir()
        self._git('init', '-q', '-b', 'main')
        self._git('config', 'user.email', 'test@example.invalid')
        self._git('config', 'user.name', 'Test')
        # Never let the real repo's core.hooksPath fire inside the fixture.
        self._git('config', 'core.hooksPath', str(self.tmp / 'no-hooks'))

    def tearDown(self):
        _rmtree(self.tmp)

    def _git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args],
                              capture_output=True, text=True, check=True).stdout

    def _commit(self, relpath, text, msg):
        _write(self.repo / relpath, text)
        self._git('add', '-A')
        self._git('commit', '-q', '-m', msg)
        return self._git('rev-parse', 'HEAD').strip()

    def _changed(self, commit):
        with unittest.mock.patch.object(pr, 'REPO', self.repo):
            return pr.changed_files(commit)

    def test_merge_commit_reports_the_files_the_branch_brought_in(self):
        self._commit('seed.md', 'seed\n', 'seed')
        self._git('checkout', '-q', '-b', 'topic')
        self._commit('a-skill/SKILL.md', 'branch content\n', 'branch edit')
        self._git('checkout', '-q', 'main')
        self._commit('other.md', 'main-side\n', 'main edit')
        self._git('merge', '-q', '--no-ff', '-m', 'merge topic', 'topic')
        merge_sha = self._git('rev-parse', 'HEAD').strip()

        self.assertIn('a-skill/SKILL.md', self._changed(merge_sha))

    def test_non_merge_commit_file_list_is_unchanged(self):
        self._commit('seed.md', 'seed\n', 'seed')
        sha = self._commit('b-skill/SKILL.md', 'x\n', 'normal commit')
        self.assertEqual(['b-skill/SKILL.md'], self._changed(sha))

    def test_root_commit_does_not_raise(self):
        sha = self._commit('seed.md', 'seed\n', 'seed')
        self.assertEqual([], self._changed(sha))


REAL_ENTRY_MIXED = """## 2026-09-07 -- Entry Point A: 2 reimports confirmed, county-parcel-screen publish stopped

**package-and-stage-skill** (v1.30): Save-skill click CONFIRMED. Cache-dir CreationTime moved, exact-second match to main.log.

**county-parcel-screen** (v1.1, 16 files): NOT packaged, staged, or presented this session. Per brief instruction, stopped rather than risk a duplicate store entry; no action taken on this skill.
"""

REAL_ENTRY_ALL_CONFIRMED = """## 2026-09-07 -- Second Save-skill batch: all 4 reimports CONFIRMED

`tools/reimport_correlate.py verify` returned CONFIRMED for all four:

- **county-parcel-screen** (v1.1, 16 files): CreationTime 11:58:24 -> 13:14:09; main.log Sync complete @ 13:14:09. Post-install file count 16/16.
- **ora-setup-audit** (v1.12): CreationTime 13:04:26 -> 13:14:09, paired with the same Sync-complete line.
"""


class LogBeforeClearGuard(unittest.TestCase):
    """The guard shipped in 9e0fca7 gates `clear` on the newest event_log entry.
    It matched on the skill NAME alone, so an entry that named a skill as
    deliberately NOT installed authorized clearing it just as well as one
    recording a confirmed install -- which is exactly what happened on
    2026-09-07: county-parcel-screen was cleared against an entry whose own text
    said "publish stopped ... no action taken on this skill"."""

    def setUp(self):
        # read/write_entries are mocked per test, but cmd_clear still takes LEDGER's
        # lock -- point LEDGER at a temp dir so its sidecar never lands in the real
        # _staging/.
        tmp = Path(tempfile.mkdtemp(prefix='pending_reimport_clear_'))
        self.addCleanup(_rmtree, tmp)
        patch = unittest.mock.patch.object(pr, 'LEDGER', tmp / 'PENDING_REIMPORT.md')
        patch.start()
        self.addCleanup(patch.stop)

    def _clear(self, skills, block, header='## 2026-09-07 -- x', known=None):
        """`known` overrides the repo's real skill roster, which _sole_subject()
        consults to decide whether a scope is a verdict about ONE skill or prose
        mentioning several. Tests using placeholder names must supply it."""
        err = __import__('io').StringIO()
        entries = {s: f'- {s} | ...' for s in skills}
        with unittest.mock.patch.object(pr, 'newest_event_log_block',
                                        return_value=(header, block)),              unittest.mock.patch.object(pr, 'all_skill_dirs',
                                        return_value=(known or pr.all_skill_dirs(pr.REPO))), \
             unittest.mock.patch.object(pr, 'read_entries', return_value=dict(entries)), \
             unittest.mock.patch.object(pr, 'write_entries') as wrote, \
             unittest.mock.patch('sys.stderr', err), \
             unittest.mock.patch('sys.stdout', __import__('io').StringIO()) as out:
            try:
                pr.cmd_clear(skills)
            except SystemExit:
                pass
        return err.getvalue(), out.getvalue(), wrote

    def test_skill_named_as_NOT_installed_is_refused(self):
        err, out, _ = self._clear(['county-parcel-screen'], REAL_ENTRY_MIXED)
        self.assertIn('REFUSED', err)
        self.assertNotIn('cleared county-parcel-screen', out)

    def test_sibling_confirmed_skill_in_the_same_entry_still_clears(self):
        err, out, _ = self._clear(['package-and-stage-skill'], REAL_ENTRY_MIXED)
        self.assertNotIn('REFUSED', err)
        self.assertIn('cleared package-and-stage-skill', out)

    def test_entry_confirming_all_of_them_clears_without_per_bullet_token(self):
        """Real 2026-09-07 entry: the confirmation is stated once up front and in
        the header, NOT repeated in every bullet. Requiring a per-bullet CONFIRMED
        would refuse a legitimate log and push sessions to --force."""
        err, out, _ = self._clear(['county-parcel-screen', 'ora-setup-audit'],
                                  REAL_ENTRY_ALL_CONFIRMED)
        self.assertNotIn('REFUSED', err)
        self.assertIn('cleared', out)

    def test_entry_with_no_confirmation_token_at_all_is_refused(self):
        block = ('## 2026-09-07 -- packaging notes\n\n'
                 '- **some-skill**: repackaged, awaiting Gabriel.\n')
        err, out, _ = self._clear(['some-skill'], block, known=['some-skill'])
        self.assertIn('REFUSED', err)

    def test_negation_in_a_sibling_bullet_does_not_block_a_clean_skill(self):
        block = ('## 2026-09-07 -- batch\n\nAll CONFIRMED except one:\n\n'
                 '- **skill-a**: install CONFIRMED at 13:14:09.\n'
                 '- **skill-b**: NOT packaged this session.\n')
        err, out, _ = self._clear(['skill-a'], block, known=['skill-a', 'skill-b'])
        self.assertNotIn('REFUSED', err)
        self.assertIn('cleared skill-a', out)

    def test_preamble_mention_does_not_rescue_a_negated_bullet(self):
        """The skill is listed in a dispatch preamble AND negated in its own
        bullet. Scoping to the first mention would wrongly authorize the clear."""
        block = ('## 2026-09-07 -- batch\n\n'
                 'Dispatch: skill-a, skill-b. Verify returned CONFIRMED:\n\n'
                 '- **skill-a**: CreationTime moved, exact-second match.\n'
                 '- **skill-b**: publish stopped; no action taken on this skill.\n')
        err, out, _ = self._clear(['skill-b'], block, known=['skill-a', 'skill-b'])
        self.assertIn('REFUSED', err)

    def test_unnamed_skill_still_refused(self):
        err, out, _ = self._clear(['never-mentioned'], REAL_ENTRY_ALL_CONFIRMED)
        self.assertIn('REFUSED', err)

    def test_force_overrides_a_negated_bullet(self):
        entries = {'county-parcel-screen': '- county-parcel-screen | ...'}
        out = __import__('io').StringIO()
        with unittest.mock.patch.object(pr, 'read_entries', return_value=dict(entries)), \
             unittest.mock.patch.object(pr, 'write_entries'), \
             unittest.mock.patch('sys.stdout', out):
            pr.cmd_clear(['county-parcel-screen'], force=True)
        self.assertIn('cleared county-parcel-screen', out.getvalue())

    def test_stale_install_claim_refuses(self):
        """Real 2026-09-07 Cowork bullet: the log itself says the installed content
        is stale, so it must not authorize a clear."""
        block = (
            '## 2026-09-07 -- batch\n'
            '\n'
            'verify returned CONFIRMED:\n'
            '\n'
            '- **skill-a**: Net effect: the currently-installed skill-a content is\n'
            '  stale/inconsistent versus origin/main.\n'
        )
        err, out, _ = self._clear(['skill-a'], block, known=['skill-a'])
        self.assertIn('REFUSED', err)

    def test_stale_workbook_inside_a_skill_bullet_does_not_refuse(self):
        """Real 2026-08-24 bullet: the stale thing is a WORKBOOK, not the install.
        The loose copular-stale pattern refused this skill across the whole corpus;
        requiring install/cache/store context first is what fixed it."""
        block = (
            '## 2026-08-24 -- close-out\n'
            '\n'
            'Install CONFIRMED.\n'
            '\n'
            '- **skill-a** consumer-sweep: only 754 Old State has a refi model, and\n'
            '  it is still stale -- but on a v04 workbook.\n'
        )
        err, out, _ = self._clear(['skill-a'], block, known=['skill-a'])
        self.assertNotIn('REFUSED', err)
        self.assertIn('cleared skill-a', out)


class CmdRecordDeliberatelyUnpublishedWarning(unittest.TestCase):
    """Commit-time flag added 2026-09-11 (ORA Setup Audit R25 remediation): a
    commit touching a DELIBERATELY_UNPUBLISHED skill's packaged files must warn
    in the commit's own console output (post-commit only redirects stderr, not
    stdout -- see tools/hooks/post-commit), not just in a later `candidates`
    run someone has to think to make. Real trigger: today's 735a376 merged
    vendor-contract-qc into vendor-management while vendor-management still
    sat in the exclusion set, with nothing at commit time distinguishing it
    from the two ordinary skills (daily-brief, pma-qc) in the same commit.

    Uses the same git-fixture pattern as ChangedFilesMergeCommit. read_entries/
    write_entries are replaced (not just their default `ledger_path` patched --
    see the Candidates test class's own note: defaults bind at function-
    DEFINITION time) so this test can never touch the real, gitignored
    _staging/PENDING_REIMPORT.md ledger."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='pending_reimport_record_'))
        self.repo = self.tmp / 'repo'
        self.repo.mkdir()
        self._git('init', '-q', '-b', 'main')
        self._git('config', 'user.email', 'test@example.invalid')
        self._git('config', 'user.name', 'Test')
        self._git('config', 'core.hooksPath', str(self.tmp / 'no-hooks'))
        # A repo's ROOT commit yields [] from changed_files() by design (see
        # ChangedFilesMergeCommit.test_root_commit_does_not_raise) -- seed one
        # harmless commit first so the commit under test is never the root.
        _write(self.repo / 'seed.md', 'seed\n')
        self._git('add', '-A')
        self._git('commit', '-q', '-m', 'seed')
        self.fake_ledger: dict = {}
        self.patches = [
            unittest.mock.patch.object(pr, 'REPO', self.repo),
            unittest.mock.patch.object(pr, 'read_entries', lambda *a, **k: dict(self.fake_ledger)),
            unittest.mock.patch.object(pr, 'write_entries',
                                        lambda entries, *a, **k: self.fake_ledger.clear() or self.fake_ledger.update(entries)),
            unittest.mock.patch.object(pr, 'plugin_of', lambda skill: None),
            # record_hits takes LEDGER's lock -- keep its sidecar out of the real _staging/.
            unittest.mock.patch.object(pr, 'LEDGER', self.tmp / '_staging' / 'PENDING_REIMPORT.md'),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        _rmtree(self.tmp)

    def _git(self, *args):
        return subprocess.run(['git', '-C', str(self.repo), *args],
                              capture_output=True, text=True, check=True).stdout

    def _commit_skill(self, skill, text, msg):
        _write(self.repo / skill / 'SKILL.md', text)
        self._git('add', '-A')
        self._git('commit', '-q', '-m', msg)
        return self._git('rev-parse', 'HEAD').strip()

    def _record(self, commit):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            pr.cmd_record(commit)
        return buf.getvalue()

    def test_warns_when_commit_touches_a_suppressed_skill(self):
        with unittest.mock.patch.object(pr, 'DELIBERATELY_UNPUBLISHED', frozenset({'held-back-skill'})):
            sha = self._commit_skill('held-back-skill', 'name: held-back-skill\nv2\n', 'edit')
            out = self._record(sha)

        self.assertIn('held-back-skill', self.fake_ledger,
                       'must still record the ledger line -- the warning is additive, not a skip')
        self.assertIn('WARNING', out)
        self.assertIn('held-back-skill', out)
        self.assertIn('OI-157', out)

    def test_no_warning_for_an_ordinary_skill(self):
        with unittest.mock.patch.object(pr, 'DELIBERATELY_UNPUBLISHED', frozenset({'held-back-skill'})):
            sha = self._commit_skill('ordinary-skill', 'name: ordinary-skill\nv2\n', 'edit')
            out = self._record(sha)

        self.assertNotIn('WARNING', out)

    def test_mixed_commit_names_only_the_suppressed_skill(self):
        with unittest.mock.patch.object(pr, 'DELIBERATELY_UNPUBLISHED', frozenset({'held-back-skill'})):
            _write(self.repo / 'held-back-skill' / 'SKILL.md', 'name: held-back-skill\nv2\n')
            _write(self.repo / 'ordinary-skill' / 'SKILL.md', 'name: ordinary-skill\nv2\n')
            self._git('add', '-A')
            self._git('commit', '-q', '-m', 'mixed edit')
            sha = self._git('rev-parse', 'HEAD').strip()
            out = self._record(sha)

        self.assertIn('WARNING', out)
        self.assertIn('held-back-skill', out.split('WARNING', 1)[1])
        # ordinary-skill must be recorded normally but not named in the warning line
        warning_line = [ln for ln in out.splitlines() if 'WARNING' in ln][0]
        self.assertNotIn('ordinary-skill', warning_line)


class LedgerResolvesToPrimaryCheckout(FixtureTestCase):
    """The ledger is untracked, gitignored state. Resolved relative to a git
    worktree it lands in that worktree's _staging/ and is destroyed by
    `git worktree remove` (2026-09-23: isolated-commit #77's entry was stranded
    that way). It must resolve to the PRIMARY checkout that every worktree shares."""

    def setUp(self):
        super().setUp()
        _git(self.repo, 'init', '-q')
        _git(self.repo, '-c', 'user.name=t', '-c', 'user.email=t@t',
             'commit', '-q', '--allow-empty', '-m', 'init')

    def test_worktree_resolves_to_primary_checkout(self):
        wt = self.tmp / 'wt'
        _git(self.repo, 'worktree', 'add', '-q', str(wt))
        self.assertEqual(pr._primary_checkout(wt).resolve(), self.repo.resolve())

    def test_ledger_path_from_worktree_lands_in_primary_staging(self):
        wt = self.tmp / 'wt'
        _git(self.repo, 'worktree', 'add', '-q', str(wt))
        self.assertEqual(pr._ledger_path(wt).resolve(),
                         (self.repo / '_staging' / 'PENDING_REIMPORT.md').resolve())

    def test_primary_checkout_resolves_to_itself(self):
        self.assertEqual(pr._primary_checkout(self.repo).resolve(), self.repo.resolve())

    def test_non_git_dir_falls_back_to_itself(self):
        plain = self.tmp / 'plain'
        plain.mkdir()
        self.assertEqual(pr._primary_checkout(plain), plain)

    def test_module_ledger_uses_ledger_path(self):
        self.assertEqual(pr.LEDGER, pr._ledger_path(pr.REPO))

    def test_module_ledger_from_a_worktree_survives_worktree_remove(self):
        # The assertion above passes on a revert whenever the suite runs from the
        # primary checkout (both sides collapse to REPO/_staging). Reloading with
        # REPO pointed at a real fixture worktree fails a revert from anywhere.
        import package_skills
        wt = self.tmp / 'wt'
        _git(self.repo, 'worktree', 'add', '-q', str(wt))
        self.addCleanup(importlib.reload, pr)
        with unittest.mock.patch.object(package_skills, 'REPO', wt):
            importlib.reload(pr)

        pr.write_entries({'demo-skill': '- demo-skill | pending'})
        _git(self.repo, 'worktree', 'remove', '--force', str(wt))

        self.assertIn('demo-skill',
                      pr.read_entries(self.repo / '_staging' / 'PENDING_REIMPORT.md'))

    def test_old_git_echoing_unknown_option_falls_back(self):
        # git < 2.31 prints an unrecognised rev-parse option back with exit 0.
        fake = subprocess.CompletedProcess([], 0, stdout='--path-format=absolute\nC:/x/.git\n', stderr='')
        with unittest.mock.patch.object(pr.subprocess, 'run', return_value=fake):
            self.assertEqual(pr._primary_checkout(self.repo), self.repo)


class WriteEntriesIsAtomic(FixtureTestCase):
    """write_entries() is the only writer of both durable ledgers (PENDING_REIMPORT
    and repo_first_check's STORE_AHEAD_OF_REPO). A write that dies midway must leave
    the previous ledger intact -- Path.write_text truncates the target BEFORE
    writing, so any failure after open() used to leave an empty ledger behind."""

    def setUp(self):
        super().setUp()
        self.ledger = self.tmp / '_staging' / 'LEDGER.md'
        pr.write_entries({'kept-skill': '- kept-skill | pending'}, self.ledger)
        self.before = self.ledger.read_bytes()

    def test_failed_write_leaves_previous_ledger_intact(self):
        # A lone surrogate cannot be UTF-8 encoded, so the write fails after open().
        with self.assertRaises(UnicodeEncodeError):
            pr.write_entries({'bad-skill': '- bad-skill | \ud800'}, self.ledger)

        self.assertEqual(self.ledger.read_bytes(), self.before)

    def test_failed_write_leaves_no_temp_file_behind(self):
        with self.assertRaises(UnicodeEncodeError):
            pr.write_entries({'bad-skill': '- bad-skill | \ud800'}, self.ledger)

        self.assertEqual([p.name for p in self.ledger.parent.iterdir()], ['LEDGER.md'])

    def test_transient_lock_on_the_ledger_is_retried(self):
        # On Windows os.replace fails while ANY reader has the target open (Python's
        # open() does not share delete access) -- a concurrent read_entries from
        # another session, which write_text used to tolerate.
        real_replace = os.replace
        calls = []

        def locked_twice(src, dst):
            calls.append(dst)
            if len(calls) <= 2:
                raise PermissionError(13, 'being used by another process')
            real_replace(src, dst)

        with unittest.mock.patch.object(pr.os, 'replace', side_effect=locked_twice), \
                unittest.mock.patch.object(pr.time, 'sleep'):
            pr.write_entries({'new-skill': '- new-skill | pending'}, self.ledger)

        self.assertEqual(len(calls), 3)
        self.assertEqual(list(pr.read_entries(self.ledger)), ['new-skill'])
        self.assertEqual([p.name for p in self.ledger.parent.iterdir()], ['LEDGER.md'])

    def test_persistent_lock_raises_and_leaves_previous_ledger_intact(self):
        with unittest.mock.patch.object(pr.os, 'replace',
                                        side_effect=PermissionError(13, 'locked')), \
                unittest.mock.patch.object(pr.time, 'sleep'), \
                self.assertRaises(PermissionError):
            pr.write_entries({'new-skill': '- new-skill | pending'}, self.ledger)

        self.assertEqual(self.ledger.read_bytes(), self.before)
        self.assertEqual([p.name for p in self.ledger.parent.iterdir()], ['LEDGER.md'])

    def test_transient_lock_on_a_ledger_read_is_retried(self):
        # os.replace makes a reader that opens mid-rename fail with PermissionError on
        # Windows (merge-gate race finding F3: 14 of 6,000 reads under contention).
        real_read = Path.read_text
        failures = []

        def locked_twice(path, *a, **kw):
            if path == self.ledger and len(failures) < 2:
                failures.append(path)
                raise PermissionError(13, 'being used by another process')
            return real_read(path, *a, **kw)

        with unittest.mock.patch.object(Path, 'read_text', locked_twice), \
                unittest.mock.patch.object(pr.time, 'sleep'):
            entries = pr.read_entries(self.ledger)

        self.assertEqual(len(failures), 2)
        self.assertEqual(list(entries), ['kept-skill'])

    def test_a_ledger_that_vanishes_before_the_read_reads_as_empty(self):
        # A concurrent `clear` of the last entry deletes the file between is_file()
        # and the read (merge-gate round 2, race F1); that is "absent", not a crash.
        def vanished(path, *a, **kw):
            raise FileNotFoundError(2, 'No such file or directory', str(path))

        with unittest.mock.patch.object(Path, 'read_text', vanished):
            self.assertEqual(pr.read_entries(self.ledger), {})

    def test_successful_write_replaces_content(self):
        pr.write_entries({'new-skill': '- new-skill | pending'}, self.ledger)

        self.assertEqual(list(pr.read_entries(self.ledger)), ['new-skill'])
        self.assertEqual([p.name for p in self.ledger.parent.iterdir()], ['LEDGER.md'])


# A worker process for the multi-process tests below: waits for the go-file so every
# worker starts contending at once, then runs `cycles` real ledger read-modify-writes.
# Stdlib subprocess (not multiprocessing) so the worker imports pending_reimport
# fresh, exactly as tools/hooks/post-commit does.
_WORKER = r"""
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import pending_reimport as pr
ledger, go, wid, cycles, mode = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4], int(sys.argv[5]), sys.argv[6]
while not go.exists():
    time.sleep(0.001)
for j in range(cycles):
    if mode == 'record':
        pr.record_hits({f'w{wid}-{j}': {f'w{wid}-{j}/SKILL.md'}}, 'abc1234', 'subject',
                       ledger_path=ledger, timeout=600)
    else:
        pr.clear_entries([f'seed-{wid}-{j}'], ledger_path=ledger, timeout=600)
"""

_HOLDER = r"""
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import pending_reimport as pr
ledger, held, release = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
with pr.ledger_lock(ledger):
    held.write_text('held')
    while not release.exists():
        time.sleep(0.005)
"""


class LedgerReadModifyWriteIsSerialized(FixtureTestCase):
    """PR #79's adversarial merge gate (2026-09-23, race-hunter finding F2): three
    processes x 200 concurrent read-modify-write cycles on the cmd_record path lost
    91.8% of updates on base and 21.7-40.2% after #79's atomic write, because
    nothing serialized read_entries -> mutate -> write_entries across processes.
    The ledgers live in the PRIMARY checkout's _staging/, shared by every worktree's
    post-commit hook, so concurrent writers are the normal case. These tests count
    lost updates (must be zero), never elapsed time."""

    PROCS = 3
    CYCLES = 200          # F2's harness shape: 3 processes x 200 cycles
    MIXED_CYCLES = 100    # 6 processes; each ledger write costs ~10ms+ under AV here

    def setUp(self):
        super().setUp()
        self.ledger = self.tmp / '_staging' / 'PENDING_REIMPORT.md'
        self.go = self.tmp / 'go'

    def _spawn(self, script, *args):
        return subprocess.Popen(
            [sys.executable, '-c', script, str(Path(pr.__file__).parent), *map(str, args)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def _run_workers(self, specs, cycles):
        procs = []
        try:
            for wid, mode in specs:
                procs.append(self._spawn(_WORKER, self.ledger, self.go, wid, cycles, mode))
        finally:
            self.go.write_text('go')     # never leave a spawned worker polling forever
        errors = []
        for p in procs:
            try:
                _out, err = p.communicate(timeout=900)   # a hang bound, not an assertion
            except subprocess.TimeoutExpired:
                p.kill()
                _out, err = p.communicate()
                err = f'worker hung: {err}'
            if p.returncode != 0:
                errors.append(err.strip().splitlines()[-1] if err.strip() else p.returncode)
        return errors

    def test_concurrent_records_lose_no_update(self):
        errors = self._run_workers([(w, 'record') for w in range(self.PROCS)], self.CYCLES)

        entries = set(pr.read_entries(self.ledger))
        expected = {f'w{w}-{j}' for w in range(self.PROCS) for j in range(self.CYCLES)}
        lost = expected - entries
        self.assertEqual(len(lost), 0, f'{len(lost)} of {len(expected)} updates lost; '
                                       f'worker errors: {errors}')
        self.assertEqual(errors, [])

    def test_concurrent_records_and_clears_lose_no_update(self):
        n = self.MIXED_CYCLES
        seeded = {f'seed-{w}-{j}': f'- seed-{w}-{j} | pending'
                  for w in range(self.PROCS) for j in range(n)}
        pr.write_entries(seeded, self.ledger)

        errors = self._run_workers([(w, 'record') for w in range(self.PROCS)]
                                   + [(w, 'clear') for w in range(self.PROCS)], n)

        entries = set(pr.read_entries(self.ledger))
        recorded = {f'w{w}-{j}' for w in range(self.PROCS) for j in range(n)}
        self.assertEqual(len(recorded - entries), 0,
                         f'{len(recorded - entries)} recorded entries lost; worker errors: {errors}')
        self.assertEqual(len(entries & set(seeded)), 0,
                         f'{len(entries & set(seeded))} cleared entries came back')
        self.assertEqual(errors, [])

    def test_backfill_keeps_an_entry_recorded_while_its_sweep_ran(self):
        # backfill's sweep hashes every skill and takes seconds; a commit's record that
        # lands meanwhile must survive backfill's write. The sweep runs outside the
        # lock and the ledger is re-read under it.
        def sweep_with_a_concurrent_commit(*_a, **_k):
            pr.record_hits({'committed-meanwhile': {'x/SKILL.md'}}, 'abc1234', 's',
                           ledger_path=self.ledger)
            return {'drifted-skill': 'drift'}

        with unittest.mock.patch.object(pr, 'sweep_drift', sweep_with_a_concurrent_commit):
            seeded = pr.backfill(repo_root=self.repo, cache_root=self.cache,
                                 ledger_path=self.ledger)

        self.assertEqual(seeded, ['drifted-skill'])
        self.assertEqual(set(pr.read_entries(self.ledger)),
                         {'committed-meanwhile', 'drifted-skill'})


class LedgerLockTimeoutFailsOpen(FixtureTestCase):
    """A lock that cannot be taken within its bound must be reported loudly and leave
    the ledger exactly as it was -- never block, never write unlocked, never corrupt."""

    def setUp(self):
        super().setUp()
        self.ledger = self.tmp / '_staging' / 'PENDING_REIMPORT.md'
        pr.write_entries({'kept-skill': '- kept-skill | pending'}, self.ledger)
        self.before = self.ledger.read_bytes()
        held, self.release = self.tmp / 'held', self.tmp / 'release'
        self.holder = subprocess.Popen(
            [sys.executable, '-c', _HOLDER, str(Path(pr.__file__).parent),
             str(self.ledger), str(held), str(self.release)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        while not held.exists():
            if self.holder.poll() is not None:
                err = self.holder.stderr.read()
                super().tearDown()       # a failing setUp skips tearDown
                self.fail(f'lock holder died: {err}')
            time.sleep(0.01)

    def tearDown(self):
        # Before super().tearDown() removes the temp dir the release file lives in
        # (addCleanup would run after it); an already-dead holder just returns.
        self.release.write_text('release')
        self.holder.communicate()
        super().tearDown()

    def test_update_raises_lock_timeout_and_leaves_ledger_intact(self):
        with self.assertRaises(pr.LedgerLockTimeout):
            pr.record_hits({'new-skill': {'new-skill/SKILL.md'}}, 'abc1234', 's',
                           ledger_path=self.ledger, timeout=0)

        self.assertEqual(self.ledger.read_bytes(), self.before)

    def test_lock_timeout_is_an_oserror_so_repo_first_check_degrades_it(self):
        # repo_first_check.run() already turns an OSError from record_ledger into a
        # "ledger write failed" warning and exit 0.
        self.assertTrue(issubclass(pr.LedgerLockTimeout, OSError))

    def test_cmd_record_reports_on_stdout_and_exits_nonzero(self):
        # post-commit discards stderr (2>/dev/null); stdout is the commit's console.
        out = io.StringIO()
        with unittest.mock.patch.object(pr, 'LEDGER', self.ledger), \
                unittest.mock.patch.object(pr, 'LOCK_TIMEOUT_S', 0), \
                unittest.mock.patch.object(pr, 'changed_files', return_value=['s/SKILL.md']), \
                unittest.mock.patch.object(pr, 'affected_skills',
                                           return_value={'new-skill': {'new-skill/SKILL.md'}}), \
                unittest.mock.patch.object(pr, '_git', return_value='abc1234\n'), \
                contextlib.redirect_stdout(out), \
                self.assertRaises(SystemExit) as exit_:
            pr.cmd_record('HEAD')

        self.assertNotEqual(exit_.exception.code, 0)
        self.assertIn('LOCK TIMEOUT', out.getvalue())
        self.assertIn('new-skill', out.getvalue())
        # backfill would not reproduce the row (no cache dir, OI-157, plugin tag,
        # commit provenance); re-running record for the same commit does.
        self.assertIn('pending_reimport.py record abc1234', out.getvalue())
        self.assertEqual(self.ledger.read_bytes(), self.before)

    def _record_failing(self, hits, exc):
        out = io.StringIO()
        with unittest.mock.patch.object(pr, 'changed_files', return_value=['s/SKILL.md']), \
                unittest.mock.patch.object(pr, 'affected_skills', return_value=hits), \
                unittest.mock.patch.object(pr, '_git', return_value='abc1234\n'), \
                unittest.mock.patch.object(pr, 'record_hits', side_effect=exc), \
                contextlib.redirect_stdout(out), \
                self.assertRaises(SystemExit) as exit_:
            pr.cmd_record('HEAD')
        self.assertNotEqual(exit_.exception.code, 0)
        return out.getvalue()

    def test_cmd_record_reports_any_ledger_oserror_on_stdout(self):
        # e.g. os.replace still locked by an unlocked `list` reader after its retry,
        # or flock unsupported on a mounted filesystem. main()'s blanket except would
        # send these to stderr, which post-commit discards.
        out = self._record_failing({'new-skill': {'new-skill/SKILL.md'}},
                                   PermissionError(13, 'being used by another process'))

        self.assertIn('LEDGER WRITE FAILED', out)
        self.assertIn('pending_reimport.py record abc1234', out)

    def test_cmd_record_still_warns_about_a_suppressed_skill_on_failure(self):
        # The OI-157 flag is about what the commit touched, not about the ledger write.
        suppressed = sorted(pr.DELIBERATELY_UNPUBLISHED)[0]
        out = self._record_failing({suppressed: {f'{suppressed}/SKILL.md'}},
                                   pr.LedgerLockTimeout('held'))

        self.assertIn('DELIBERATELY_UNPUBLISHED', out)
        self.assertIn(suppressed, out)

    def test_cmd_clear_reports_on_stderr_and_exits_nonzero(self):
        err = io.StringIO()
        with unittest.mock.patch.object(pr, 'LEDGER', self.ledger), \
                unittest.mock.patch.object(pr, 'LOCK_TIMEOUT_S', 0), \
                contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit) as exit_:
            pr.cmd_clear(['kept-skill'], force=True)

        self.assertNotEqual(exit_.exception.code, 0)
        self.assertIn('LOCK TIMEOUT', err.getvalue())
        self.assertEqual(self.ledger.read_bytes(), self.before)

    def test_cmd_backfill_reports_on_stderr_and_exits_nonzero(self):
        # The doctrine guard treats any stderr or non-zero exit from backfill as ERROR.
        err = io.StringIO()
        with unittest.mock.patch.object(pr, 'LEDGER', self.ledger), \
                unittest.mock.patch.object(pr, 'LOCK_TIMEOUT_S', 0), \
                unittest.mock.patch.object(pr, 'sweep_drift', return_value={'d': 'x'}), \
                contextlib.redirect_stderr(err), \
                contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaises(SystemExit) as exit_:
            pr.cmd_backfill()

        self.assertNotEqual(exit_.exception.code, 0)
        self.assertIn('LOCK TIMEOUT', err.getvalue())
        self.assertEqual(self.ledger.read_bytes(), self.before)

    def test_backfill_with_no_drift_never_takes_the_lock(self):
        # A clean sweep stays lock-free, so the lock can't fail the daily guard's run.
        with unittest.mock.patch.object(pr, 'sweep_drift', return_value={}):
            seeded = pr.backfill(repo_root=self.repo, cache_root=self.cache,
                                 ledger_path=self.ledger, timeout=0)

        self.assertEqual(seeded, [])
        self.assertEqual(self.ledger.read_bytes(), self.before)

    def test_lock_is_released_when_its_holder_dies(self):
        # The kernel owns the lock, so a crashed holder can never leave a stale one.
        self.holder.kill()
        self.holder.communicate()

        pr.record_hits({'new-skill': {'new-skill/SKILL.md'}}, 'abc1234', 's',
                       ledger_path=self.ledger, timeout=60)

        self.assertEqual(set(pr.read_entries(self.ledger)), {'kept-skill', 'new-skill'})


class FixtureTeardownRemovesGitRepos(unittest.TestCase):
    """git writes object files read-only; rmtree(ignore_errors=True) skipped them on
    Windows and every git-backed fixture in this suite leaked into %TEMP%."""

    def test_rmtree_removes_a_git_repo_with_read_only_objects(self):
        tmp = Path(tempfile.mkdtemp(prefix='pending_reimport_test_'))
        _git(tmp, 'init', '-q')
        _git(tmp, '-c', 'user.name=t', '-c', 'user.email=t@t',
             'commit', '-q', '--allow-empty', '-m', 'init')

        _rmtree(tmp)

        self.assertFalse(tmp.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
