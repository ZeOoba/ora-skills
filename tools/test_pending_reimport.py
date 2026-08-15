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
import os
import shutil
import subprocess
import sys
import tempfile
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


class FixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='pending_reimport_test_'))
        self.repo = self.tmp / 'repo'
        self.cache = self.tmp / 'cache'
        self.repo.mkdir()
        self.cache.mkdir()

    def tearDown(self):
        # Long-path-safe: a fixture built past MAX_PATH (see WindowsMaxPath below)
        # is invisible to a plain rmtree the same way it's invisible to a plain
        # is_file() -- ignore_errors=True would otherwise leak it on disk forever.
        shutil.rmtree(pr._win_long(self.tmp), ignore_errors=True)


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
        # policy, matching the live incident).
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
        self.assertEqual(
            pr.DELIBERATELY_UNPUBLISHED,
            frozenset({
                'annual-cycle', 'capex-budgeting', 'cash-position-monitor',
                'deal-retirement', 'investor-relations', 'vendor-management',
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
