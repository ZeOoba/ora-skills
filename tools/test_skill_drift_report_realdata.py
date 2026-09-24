#!/usr/bin/env python3
"""Real-data coverage for skill_drift_report.py — the companion to the hermetic
synthetic suite in test_skill_drift_report.py.

WHY A SEPARATE FILE. The synthetic suite deliberately never touches the real
ora-skills repo or the real runtime cache, so it is deterministic regardless of
live drift state. That hermeticity is also its blind spot: it proves the logic
against SKILL.md shapes *I invented*, and two coverage limits were disclosed when
the comparator shipped —

  1. The DESCRIPTION-REGRESSION detector was proven only on synthetic fixtures.
     The historical 850 -> 203 char truncation of parcel-data-recovery's
     description was never committed (the 2026-08-03 session merged by hand
     rather than byte-copying), so there is no real "after" state in git to
     replay.
  2. A pure section reorder reports MANUAL-MERGE by design — neither side is
     then a superset — but nothing pinned that as intended rather than incidental.

These tests close both by driving the comparator with the ACTUAL frontmatter and
body text of skills on disk. Doing that immediately surfaced a real defect the
synthetic suite could never have found: three live skills declare their
description as a YAML FOLDED BLOCK SCALAR (`description: >`), and the original
`^description:\\s*(.*)$` regex returned literally `'>'` for all three — so
`len(cache_desc) < len(repo_desc)` could never fire and the regression detector
was silently disabled on them. See DescriptionParsingOnRealShapes below.

These tests SKIP rather than fail when the repo is unavailable, so they stay
runnable from a packaged checkout. Run: python tools/test_skill_drift_report_realdata.py
"""
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_drift_report as sdr  # noqa: E402

REPO = Path(__file__).resolve().parent.parent

# Skills chosen for their DESCRIPTION SHAPE, not their content:
#   parcel-data-recovery  -> double-quoted single-line scalar, and the actual
#                            subject of the 2026-08-03 near-miss
#   ratify-hurdle-rate    -> folded block scalar (`description: >`)
#
# BLOCK_SCALAR_SKILL was 'census-acs-extract' until 2026-08-12. That skill was
# retired 2026-08-05 (moved to _archive/), and because _real_parts() returns None
# for an absent SKILL.md, the three tests below did not FAIL -- they silently
# SKIPPED, leaving the folded-block-scalar parse path untested for a week. If you
# retire whatever skill this points at, repoint it at another LIVE skill using
# `description: >`; do not let it fall back to skipping.
QUOTED_SCALAR_SKILL = 'parcel-data-recovery'
BLOCK_SCALAR_SKILL = 'ratify-hurdle-rate'

# The trigger phrases the incident record names as lost when the cache
# description collapsed to 203 chars. These ARE the routing surface.
LOST_TRIGGERS = ['UNSCREENABLE rows', 'DATA-GAP rows', 'CAMA extract',
                 'county GIS pull', 'Wyandotte KS']


def _rmtree(path) -> None:
    """git writes object files read-only, which rmtree cannot unlink on Windows --
    with ignore_errors=True every git-backed fixture here leaked silently into %TEMP%.
    Clear the bit and retry; still best-effort, so a locked file never fails a test.
    (Same helper as PR #79 adds to tools/test_pending_reimport.py.)"""
    def _retry(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:  # onexc can also hand over os.open/os.close
            pass
    shutil.rmtree(path, onexc=_retry)


def _real_parts(skill: str):
    """(frontmatter, body) of a real on-disk SKILL.md, or None if absent."""
    f = REPO / skill / 'SKILL.md'
    if not f.is_file():
        return None
    return sdr.split_skill_md(sdr.normalized_text(f.read_bytes()))


def _require(skill: str):
    parts = _real_parts(skill)
    if parts is None:
        raise unittest.SkipTest(f'{skill}/SKILL.md not present in this checkout')
    return parts


class GitFixture(unittest.TestCase):
    """A throwaway repo+cache pair seeded with REAL skill text, so direction
    classification runs against genuine ancestry rather than toy commits."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='drift_realdata_'))
        self.repo = self.tmp / 'repo'
        self.cache = self.tmp / 'cache'
        (self.repo / 'demo').mkdir(parents=True)
        (self.cache / 'demo').mkdir(parents=True)
        for a in (['init', '-q'], ['config', 'user.email', 't@t.invalid'],
                  ['config', 'user.name', 't'], ['config', 'core.autocrlf', 'false']):
            subprocess.run(['git', '-C', str(self.repo), *a], capture_output=True)

    def tearDown(self):
        _rmtree(self.tmp)

    def _write(self, root: Path, text: str):
        (root / 'demo' / 'SKILL.md').write_text(text, encoding='utf-8', newline='')

    def _commit_repo(self):
        subprocess.run(['git', '-C', str(self.repo), 'add', '-A'], capture_output=True)
        subprocess.run(['git', '-C', str(self.repo), 'commit', '-q', '-m', 'x'],
                       capture_output=True)

    def _verdict(self):
        return sdr.report(self.repo, self.cache, skills=['demo'])['skills']['demo']


# ---------------------------------------------------------------------------
# Coverage limit fallout: the real description SHAPES on disk.
# ---------------------------------------------------------------------------

class DescriptionParsingOnRealShapes(unittest.TestCase):
    """Found by driving the parser with real files: three live skills use a YAML
    folded block scalar, for which the original regex returned '>'."""

    def test_quoted_scalar_description_has_its_quotes_stripped(self):
        fm, _ = _require(QUOTED_SCALAR_SKILL)
        desc = sdr.description_of(fm)
        self.assertIsNotNone(desc)
        self.assertFalse(desc.startswith('"'), 'YAML quotes leaked into the description')
        self.assertFalse(desc.endswith('"'))
        # Truncation guard (the incident collapsed 850 -> 203 chars). Compare against
        # the full quoted literal on disk rather than a fixed length: a snapshot floor
        # on live content broke when the description was legitimately trimmed to a
        # trigger-only form (2026-09-22).
        raw = re.search(r'^description:\s*"(.*)"\s*$', fm, re.M).group(1)
        self.assertEqual(desc, raw, 'parsed description is not the full quoted literal')
        for trigger in LOST_TRIGGERS:
            self.assertIn(trigger, desc)

    def test_block_scalar_description_is_folded_not_returned_as_the_indicator(self):
        """The defect: description_of returned '>' (1 char) for every block-scalar
        skill, which silently disables the regression detector on them."""
        fm, _ = _require(BLOCK_SCALAR_SKILL)
        desc = sdr.description_of(fm)
        self.assertIsNotNone(desc)
        self.assertNotEqual(desc, '>')
        self.assertGreater(len(desc), 200, 'block scalar was not folded')
        # Anchor on a phrase that SPANS a source line break ("...in the\n
        # capital_config table..."). Presence of it proves the fold actually
        # JOINED continuation lines with a single space -- a length check alone
        # would still pass if each line were concatenated without separators, or
        # kept its newline. (Replaces an `assertIn('Census', ...)` anchor that was
        # tied to the retired census-acs-extract.)
        self.assertIn('in the capital_config table', desc)

    def test_every_real_skill_yields_a_usable_description(self):
        """Conformance sweep over the live checkout — a new skill added with an
        unhandled description shape fails here instead of silently losing its
        regression coverage."""
        skills = [d.name for d in REPO.iterdir()
                  if d.is_dir() and (d / 'SKILL.md').is_file()]
        if not skills:
            self.skipTest('no skills in this checkout')
        broken = []
        for s in skills:
            fm, _ = _real_parts(s)
            desc = sdr.description_of(fm)
            if desc is None or len(desc) < 50:
                broken.append((s, repr(desc)[:40]))
        self.assertEqual(broken, [], f'unparsed description shapes: {broken}')

    def test_literal_block_scalar_joins_with_newlines(self):
        fm = 'name: x\ndescription: |\n  line one\n  line two\n'
        self.assertEqual(sdr.description_of(fm), 'line one\nline two')

    def test_block_scalar_chomping_indicators_are_handled(self):
        for head in ('>-', '>+', '|-', '|+'):
            fm = f'name: x\ndescription: {head}\n  alpha\n'
            self.assertEqual(sdr.description_of(fm), 'alpha', f'failed for {head}')

    def test_block_scalar_stops_at_the_next_top_level_key(self):
        fm = 'name: x\ndescription: >\n  the real description\nmetadata:\n  type: reference\n'
        self.assertEqual(sdr.description_of(fm), 'the real description')

    def test_nested_description_under_metadata_is_not_mistaken_for_the_real_one(self):
        fm = 'name: x\ndescription: the real one\nmetadata:\n  description: a decoy\n'
        self.assertEqual(sdr.description_of(fm), 'the real one')


# ---------------------------------------------------------------------------
# Coverage limit 1: replay the 850 -> 203 truncation on real source text.
# ---------------------------------------------------------------------------

class ReplayedDescriptionRegression(GitFixture):
    """The 2026-08-03 near-miss, driven by parcel-data-recovery's ACTUAL
    description rather than an invented one.

    Honest scope: the repo-side text is real and the truncation SHAPE is real (a
    prefix cut that drops every trailing trigger phrase), but the exact 203-char
    cache string was never committed, so it is reconstructed as a prefix of the
    genuine description. That is the closest replay the git history permits.
    """

    def _build(self, skill, cut=203):
        fm, body = _require(skill)
        full = sdr.description_of(fm)
        truncated = full[:cut]
        repo_text = f'---\nname: demo\ndescription: "{full}"\n---\n\n{body}'
        # Platform-side edit: description truncated AND the body genuinely advanced.
        cache_text = (f'---\nname: demo\ndescription: "{truncated}"\n---\n\n'
                      f'{body}\n## NEW PLATFORM SECTION\n')
        self._write(self.repo, repo_text)
        self._commit_repo()
        self._write(self.cache, cache_text)
        return full, truncated

    def test_truncation_of_a_real_description_forces_manual_merge(self):
        self._build(QUOTED_SCALAR_SKILL)
        r = self._verdict()
        self.assertEqual(r['verdict'], sdr.MANUAL_MERGE)
        self.assertNotEqual(r['verdict'], sdr.CACHE_NEWER,
                            'a byte-exact pull here would destroy the routing surface')

    def test_regression_finding_carries_the_real_char_counts(self):
        full, truncated = self._build(QUOTED_SCALAR_SKILL)
        reg = [f for f in self._verdict()['findings']
               if f['kind'] == sdr.DESCRIPTION_REGRESSION]
        self.assertEqual(len(reg), 1)
        self.assertEqual(reg[0]['repo_chars'], len(full))
        self.assertEqual(reg[0]['cache_chars'], len(truncated))
        self.assertTrue(reg[0]['cache_is_substring_of_repo'])

    def test_the_named_trigger_phrases_are_demonstrably_lost(self):
        """Not a tautology about lengths — assert the specific routing phrases the
        incident record names are absent from the truncated description."""
        full, truncated = self._build(QUOTED_SCALAR_SKILL)
        for trigger in LOST_TRIGGERS:
            self.assertIn(trigger, full)
            self.assertNotIn(trigger, truncated)

    def test_block_scalar_skill_regression_is_also_detected(self):
        """Before the parser fix this silently produced NO finding, because both
        sides' descriptions read as the 1-char string '>'."""
        full, truncated = self._build(BLOCK_SCALAR_SKILL, cut=60)
        r = self._verdict()
        reg = [f for f in r['findings'] if f['kind'] == sdr.DESCRIPTION_REGRESSION]
        self.assertEqual(len(reg), 1, 'block-scalar regression went undetected')
        self.assertEqual(reg[0]['repo_chars'], len(full))
        self.assertGreater(reg[0]['repo_chars'], 200)
        self.assertEqual(r['verdict'], sdr.MANUAL_MERGE)

    def test_point_in_time_desc_chars_reflect_the_real_description(self):
        full, _ = self._build(BLOCK_SCALAR_SKILL, cut=60)
        pit = self._verdict()['point_in_time']
        self.assertEqual(pit['repo_desc_chars'], len(full))
        self.assertGreater(pit['repo_desc_chars'], 200,
                           'block-scalar description counted as 1 char')


# ---------------------------------------------------------------------------
# Coverage limit 2: pin the pure-reorder verdict as INTENDED, not incidental.
# ---------------------------------------------------------------------------

class SectionReorderIsManualMergeByDesign(GitFixture):
    """A pure section reorder leaves each side containing all of the other's
    lines, so NEITHER side is a superset. Requirement 3 says that is exactly when
    MANUAL-MERGE must be emitted rather than a byte-exact pull — a copy in either
    direction would silently impose one document's ordering on the other."""

    def _reordered_real_body(self):
        _, body = _require(QUOTED_SCALAR_SKILL)
        blocks = [b for b in body.split('\n## ') if b.strip()]
        if len(blocks) < 3:
            self.skipTest('real body has too few sections to reorder')
        head, rest = blocks[0], blocks[1:]
        forward = head + '\n## ' + '\n## '.join(rest)
        reversed_ = head + '\n## ' + '\n## '.join(list(reversed(rest)))
        return forward, reversed_

    def test_reordered_real_sections_differ_only_in_ORDER(self):
        """Proves the DISJOINT verdict comes from the neither-is-a-superset rule
        rather than from the two sides merely differing: the line MULTISETS are
        identical (so nothing was added or removed), yet neither side is an
        ordered superset of the other."""
        from collections import Counter
        fwd, rev = self._reordered_real_body()
        self.assertNotEqual(fwd, rev)
        nonblank = lambda t: Counter(l for l in t.splitlines() if l.strip())  # noqa: E731
        self.assertEqual(nonblank(fwd), nonblank(rev),
                         'fixture should differ in ordering only')
        # Order-aware containment: a reorder is a superset in NEITHER direction.
        self.assertFalse(sdr._line_subset(fwd, rev))
        self.assertFalse(sdr._line_subset(rev, fwd))
        self.assertEqual(sdr.part_relation(fwd, rev), sdr.DISJOINT)

    def test_reorder_yields_manual_merge_never_a_pull(self):
        fwd, rev = self._reordered_real_body()
        fm, _ = _require(QUOTED_SCALAR_SKILL)
        self._write(self.repo, f'---\n{fm}---\n\n{fwd}')
        self._commit_repo()
        self._write(self.cache, f'---\n{fm}---\n\n{rev}')
        r = self._verdict()
        self.assertEqual(r['verdict'], sdr.MANUAL_MERGE)
        self.assertIn('no byte-exact copy', r['remedy'].lower())

    def test_reorder_plus_added_section_still_refuses_the_pull(self):
        """The dangerous near-miss: the cache added real content AND reordered.
        Line-containment alone would call that a cache superset; ordering must
        still block the byte-exact copy."""
        fwd, rev = self._reordered_real_body()
        fm, _ = _require(QUOTED_SCALAR_SKILL)
        self._write(self.repo, f'---\n{fm}---\n\n{fwd}')
        self._commit_repo()
        self._write(self.cache, f'---\n{fm}---\n\n{rev}\n## GENUINELY NEW\nnew line\n')
        self.assertEqual(self._verdict()['verdict'], sdr.MANUAL_MERGE)


class FixtureTeardownRemovesGitRepos(unittest.TestCase):
    """git writes object files read-only; rmtree(ignore_errors=True) skipped them on
    Windows and every git-backed fixture in this file leaked into %TEMP%."""

    def test_teardown_removes_a_committed_fixture_repo(self):
        fx = GitFixture()
        fx.setUp()
        subprocess.run(['git', '-C', str(fx.repo), 'commit', '-q', '--allow-empty', '-m', 'init'],
                       capture_output=True, check=True)
        fx.tearDown()

        self.assertFalse(fx.tmp.exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
