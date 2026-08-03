#!/usr/bin/env python3
"""Regression tests for skill_drift_report.py — the content-comparison engine behind
ora-skill-store-drift-check's step-2 verdict.

Stdlib only — run with `python tools/test_skill_drift_report.py` (no pytest).

Every test class below is anchored to a specific false positive or destructive
prescription from the 2026-08-03 drift-check run (Notion Ops Hub comment
3b16ecd8-9e59-81fa-9fa5-001da9abf07f; memory/reference_skill_store_drift_check_false_positives.md):

  * 12 skills reported CACHE-NEWER, only 2 genuinely actionable.
  * 7 of the false flags were BYTE-IDENTICAL to the cache — no content comparison
    can produce those; the check was reading version tokens.
  * market-monitor / tenant-email differed only in CRLF.
  * parcel-data-recovery's prescribed byte-exact pull would have collapsed its
    frontmatter description 850 -> 203 chars, destroying every trigger phrase.

Fixtures are synthetic temp trees + throwaway git repos — never the real
ora-skills repo or the real AppData runtime cache — so results are deterministic
regardless of live drift state.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import skill_drift_report as sdr  # noqa: E402


def _write(path: Path, text: str, newline: str = '') -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline=newline)


def _skill_md(desc: str, body: str) -> str:
    return f'---\nname: demo\ndescription: {desc}\n---\n\n{body}\n'


class FixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='skill_drift_test_'))
        self.repo = self.tmp / 'repo'
        self.cache = self.tmp / 'cache'
        self.repo.mkdir()
        self.cache.mkdir()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _git(self, *args):
        subprocess.run(['git', '-C', str(self.repo), *args],
                       capture_output=True, check=True)

    def _init_git(self):
        self._git('init', '-q')
        self._git('config', 'user.email', 'test@example.invalid')
        self._git('config', 'user.name', 'test')
        # Never let autocrlf rewrite fixture content out from under a hash test.
        self._git('config', 'core.autocrlf', 'false')

    def _commit(self, msg='c'):
        self._git('add', '-A')
        self._git('commit', '-q', '-m', msg)

    def _report_for(self, skill='demo'):
        rep = sdr.report(self.repo, self.cache, skills=[skill])
        return rep['skills'][skill]


# ---------------------------------------------------------------------------
# Pure helpers — no I/O, so the branch logic is provable without fixtures.
# ---------------------------------------------------------------------------

class SplitSkillMd(unittest.TestCase):
    def test_splits_frontmatter_from_body(self):
        fm, body = sdr.split_skill_md('---\nname: x\ndescription: d\n---\n\nBODY\n')
        self.assertIn('description: d', fm)
        self.assertNotIn('BODY', fm)
        self.assertIn('BODY', body)

    def test_missing_frontmatter_yields_empty_frontmatter(self):
        fm, body = sdr.split_skill_md('no frontmatter here\n')
        self.assertEqual(fm, '')
        self.assertIn('no frontmatter here', body)

    def test_body_containing_hrule_does_not_end_frontmatter_early(self):
        text = '---\nname: x\n---\n\nintro\n\n---\n\nafter the rule\n'
        fm, body = sdr.split_skill_md(text)
        self.assertNotIn('intro', fm)
        self.assertIn('after the rule', body)


class Normalization(unittest.TestCase):
    def test_crlf_normalizes_to_lf(self):
        self.assertEqual(sdr.normalized_text(b'a\r\nb\r\n'), 'a\nb\n')

    def test_trailing_nul_padding_is_stripped(self):
        """Platform upload artifact (drift-check step 2b) — padding is not content."""
        self.assertEqual(sdr.normalized_text(b'abc\n\x00\x00\x00'), 'abc\n')

    def test_hash_is_eol_insensitive(self):
        self.assertEqual(sdr.norm_hash(b'a\r\nb\r\n'), sdr.norm_hash(b'a\nb\n'))

    def test_hash_of_the_documented_formula(self):
        """Verdict must be sha256(bytes.replace(b'\\r\\n', b'\\n')) on both sides."""
        import hashlib
        raw = b'x\r\ny\r\n'
        self.assertEqual(sdr.norm_hash(raw),
                         hashlib.sha256(raw.replace(b'\r\n', b'\n')).hexdigest())


class PartRelation(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(sdr.part_relation('a\nb\n', 'a\nb\n'), sdr.IDENTICAL)

    def test_repo_superset_when_cache_is_a_substring(self):
        self.assertEqual(sdr.part_relation('long full text here', 'full text'),
                         sdr.REPO_SUPERSET)

    def test_cache_superset_when_repo_is_a_substring(self):
        self.assertEqual(sdr.part_relation('full text', 'long full text here'),
                         sdr.CACHE_SUPERSET)

    def test_repo_superset_by_line_containment(self):
        self.assertEqual(sdr.part_relation('a\nb\nc\n', 'a\nc\n'), sdr.REPO_SUPERSET)

    def test_disjoint_when_each_side_has_unique_content(self):
        self.assertEqual(sdr.part_relation('a\nb\n', 'a\nz\n'), sdr.DISJOINT)


class CombineVerdict(unittest.TestCase):
    """The pure verdict table. Directions come from git ancestry; relations from
    text containment. The superset gate applies ONLY to the cache->repo pull,
    because that remedy overwrites the authoritative store with unreviewed
    platform-side content, while a reimport is proven safe by ancestry."""

    def _parts(self, fm_rel, fm_dir, body_rel, body_dir):
        return {
            'frontmatter': {'relation': fm_rel, 'direction': fm_dir},
            'body': {'relation': body_rel, 'direction': body_dir},
        }

    def test_all_identical_is_in_sync(self):
        p = self._parts(sdr.IDENTICAL, sdr.IN_SYNC_DIR, sdr.IDENTICAL, sdr.IN_SYNC_DIR)
        self.assertEqual(sdr.combine_verdict(p), sdr.IN_SYNC)

    def test_uniform_cache_ahead_and_cache_superset_is_cache_newer(self):
        p = self._parts(sdr.IDENTICAL, sdr.IN_SYNC_DIR,
                        sdr.CACHE_SUPERSET, sdr.CACHE_AHEAD)
        self.assertEqual(sdr.combine_verdict(p), sdr.CACHE_NEWER)

    def test_repo_ahead_is_repo_newer_even_when_not_a_superset(self):
        """A repo-side rewrite is normal under the repo-first rule; ancestry proves
        the cache content is an older point on HEAD's own history."""
        p = self._parts(sdr.IDENTICAL, sdr.IN_SYNC_DIR, sdr.DISJOINT, sdr.REPO_AHEAD)
        self.assertEqual(sdr.combine_verdict(p), sdr.REPO_NEWER)

    def test_cache_ahead_body_with_repo_superset_frontmatter_is_manual_merge(self):
        """The parcel-data-recovery case: cache body newer, cache DESCRIPTION a
        truncation. A byte-exact pull would destroy the routing surface."""
        p = self._parts(sdr.REPO_SUPERSET, sdr.CACHE_AHEAD,
                        sdr.CACHE_SUPERSET, sdr.CACHE_AHEAD)
        self.assertEqual(sdr.combine_verdict(p), sdr.MANUAL_MERGE)

    def test_conflicting_directions_are_manual_merge(self):
        p = self._parts(sdr.DISJOINT, sdr.REPO_AHEAD, sdr.DISJOINT, sdr.CACHE_AHEAD)
        self.assertEqual(sdr.combine_verdict(p), sdr.MANUAL_MERGE)

    def test_divergent_direction_is_manual_merge(self):
        p = self._parts(sdr.IDENTICAL, sdr.IN_SYNC_DIR, sdr.DISJOINT, sdr.DIVERGENT)
        self.assertEqual(sdr.combine_verdict(p), sdr.MANUAL_MERGE)

    def test_unknown_direction_never_prescribes_a_pull(self):
        """git unavailable -> we cannot prove the cache content is unreviewed-new.
        Refuse to emit the destructive remedy."""
        p = self._parts(sdr.IDENTICAL, sdr.IN_SYNC_DIR,
                        sdr.CACHE_SUPERSET, sdr.UNKNOWN)
        self.assertEqual(sdr.combine_verdict(p), sdr.MANUAL_MERGE)

    def test_cache_ahead_disjoint_body_is_manual_merge(self):
        p = self._parts(sdr.IDENTICAL, sdr.IN_SYNC_DIR, sdr.DISJOINT, sdr.CACHE_AHEAD)
        self.assertEqual(sdr.combine_verdict(p), sdr.MANUAL_MERGE)


# ---------------------------------------------------------------------------
# End-to-end against fixture trees — the actual 2026-08-03 false-positive classes.
# ---------------------------------------------------------------------------

class ByteIdenticalIsInSync(FixtureTestCase):
    """7 of the 12 CACHE-NEWER flags were byte-identical to the cache."""

    def test_byte_identical_is_in_sync(self):
        text = _skill_md('does a thing. v1.5 (2026-07-01)', 'BODY\n')
        _write(self.repo / 'demo' / 'SKILL.md', text)
        _write(self.cache / 'demo' / 'SKILL.md', text)
        self.assertEqual(self._report_for()['verdict'], sdr.IN_SYNC)

    def test_stale_version_token_alone_never_produces_drift(self):
        """The exact defect: the repo description advertises an OLDER version
        marker than the cache, but the CONTENT is identical. Version tokens are
        not evidence."""
        text = _skill_md('v1.5 (2026-07-01) old marker', 'IDENTICAL BODY\n')
        _write(self.repo / 'demo' / 'SKILL.md', text)
        _write(self.cache / 'demo' / 'SKILL.md', text)
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.IN_SYNC)
        self.assertEqual(r['parts']['frontmatter']['relation'], sdr.IDENTICAL)
        self.assertEqual(r['parts']['body']['relation'], sdr.IDENTICAL)


class CrlfOnlyIsInSync(FixtureTestCase):
    """market-monitor / tenant-email differed only in line endings."""

    def test_crlf_repo_vs_lf_cache_is_in_sync(self):
        text = _skill_md('desc', 'line one\nline two\n')
        _write(self.repo / 'demo' / 'SKILL.md', text.replace('\n', '\r\n'))
        _write(self.cache / 'demo' / 'SKILL.md', text)
        self.assertEqual(self._report_for()['verdict'], sdr.IN_SYNC)


class FrontmatterAndBodyAreDistinctFindings(FixtureTestCase):
    def test_parts_are_reported_separately(self):
        self._init_git()
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('desc A', 'BODY v1\n'))
        self._commit()
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('desc A', 'BODY v1\nEXTRA\n'))
        r = self._report_for()
        self.assertEqual(r['parts']['frontmatter']['relation'], sdr.IDENTICAL)
        self.assertNotEqual(r['parts']['body']['relation'], sdr.IDENTICAL)
        self.assertEqual(set(r['parts']), {'frontmatter', 'body'})

    def test_findings_name_the_part(self):
        self._init_git()
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('desc A', 'BODY v1\n'))
        self._commit()
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('desc A', 'BODY v1\nEXTRA\n'))
        findings = self._report_for()['findings']
        self.assertTrue(any(f['part'] == 'body' for f in findings))
        self.assertFalse(any(f['part'] == 'frontmatter' for f in findings))


class DescriptionRegressionBlocksThePull(FixtureTestCase):
    """parcel-data-recovery: cache body newer, cache description truncated
    850 -> 203 chars. The prescribed byte-exact copy would have destroyed the
    skill's entire routing surface."""

    def test_truncated_cache_description_forces_manual_merge(self):
        self._init_git()
        long_desc = ('recover SF, UNSCREENABLE rows, DATA-GAP rows, CAMA extract, '
                     'county GIS pull, Jackson MO, Wyandotte KS, Clay MO, Hamilton OH')
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md(long_desc, 'BODY v1\n'))
        self._commit()
        # Platform-side edit: body advanced, description truncated.
        _write(self.cache / 'demo' / 'SKILL.md',
               _skill_md('recover SF', 'BODY v1\nNEW CACHE SECTION\n'))
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.MANUAL_MERGE)
        self.assertNotEqual(r['verdict'], sdr.CACHE_NEWER)

    def test_description_regression_is_an_explicit_finding_with_char_counts(self):
        self._init_git()
        long_desc = 'a' * 400
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md(long_desc, 'BODY\n'))
        self._commit()
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('a' * 40, 'BODY\n'))
        findings = self._report_for()['findings']
        reg = [f for f in findings if f['kind'] == sdr.DESCRIPTION_REGRESSION]
        self.assertEqual(len(reg), 1)
        self.assertEqual(reg[0]['repo_chars'], 400)
        self.assertEqual(reg[0]['cache_chars'], 40)

    def test_remedy_for_manual_merge_is_never_a_byte_exact_copy(self):
        self._init_git()
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('a long routing description', 'B\n'))
        self._commit()
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('short', 'B\nNEW\n'))
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.MANUAL_MERGE)
        # The remedy must actively forbid the copy, not merely omit the word.
        self.assertIn('no byte-exact copy', r['remedy'].lower())
        self.assertIn('merge', r['remedy'].lower())
        # And it must never reuse the prescriptive pull language.
        self.assertNotIn(sdr.REMEDY[sdr.CACHE_NEWER], r['remedy'])


class GenuineCacheNewerStillReports(FixtureTestCase):
    """The fix must not swing to under-reporting: a real, clean cache-ahead
    superset still gets the pull remedy."""

    def test_clean_cache_superset_is_cache_newer(self):
        self._init_git()
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('desc', 'BODY v1\n'))
        self._commit()
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('desc', 'BODY v1\nADDED SECTION\n'))
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.CACHE_NEWER)
        self.assertIn('REPO-FIRST VIOLATION', r['remedy'])

    def test_repo_ahead_is_repo_newer(self):
        self._init_git()
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('desc', 'BODY v1\n'))
        self._commit()
        # Cache holds the committed v1; repo working tree moves ahead.
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('desc', 'BODY v1\n'))
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('desc', 'BODY v2 rewritten\n'))
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.REPO_NEWER)


class NotInstalledIsNotDrift(FixtureTestCase):
    def test_skill_with_no_cache_dir_is_not_installed(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        self.assertEqual(self._report_for()['verdict'], sdr.NOT_INSTALLED)


class PointInTimeFiguresAreStamped(FixtureTestCase):
    """acquisition-underwriting was reported as cache v4.6 / 138,460 B when the
    cache actually held v4.7 / 146,847 B — the figures were stale before the
    report was read."""

    def test_report_carries_a_read_at_stamp(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d v1.0', 'B\n'))
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('d v1.0', 'B\n'))
        rep = sdr.report(self.repo, self.cache, skills=['demo'])
        self.assertRegex(rep['read_at'], r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$')

    def test_version_and_byte_figures_live_under_point_in_time(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d v1.0', 'B\n'))
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('d v2.0', 'B\n'))
        r = self._report_for()
        pit = r['point_in_time']
        self.assertEqual(pit['cache_version_token'], 'v2.0')
        self.assertEqual(pit['repo_version_token'], 'v1.0')
        self.assertIn('cache_bytes', pit)
        self.assertIn('read_at', pit)
        # The figures must not be promoted to the authoritative top level.
        self.assertNotIn('cache_bytes', r)
        self.assertNotIn('cache_version_token', r)

    def test_rendered_text_stamps_every_point_in_time_figure(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d v1.0', 'B\n'))
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('d v2.0', 'B\n'))
        rep = sdr.report(self.repo, self.cache, skills=['demo'])
        text = sdr.render_text(rep)
        self.assertIn(rep['read_at'], text)
        self.assertIn('NOT authoritative', text)

    def test_cache_mutating_during_the_run_is_flagged(self):
        """The cache is a live, moving target — it changed underneath a single
        session between two verification passes on 2026-08-03."""
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        cache_file = self.cache / 'demo' / 'SKILL.md'
        _write(cache_file, _skill_md('d', 'B\n'))
        rep = sdr.report(self.repo, self.cache, skills=['demo'],
                         _after_read=lambda: _write(cache_file, _skill_md('d', 'MUTATED\n')))
        self.assertEqual(rep['skills']['demo']['stability'], sdr.CHANGED_DURING_RUN)

    def test_stable_run_reports_stable(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        rep = sdr.report(self.repo, self.cache, skills=['demo'])
        self.assertEqual(rep['skills']['demo']['stability'], sdr.STABLE)


class AbsentGitHistoryNeverPrescribesAPull(FixtureTestCase):
    """A CACHE-AHEAD direction is INFERRED FROM ABSENCE: the cache content matches
    no commit anywhere. That inference is only valid if we could actually LOOK.
    When history is missing rather than searched-and-empty, `absence` degrades from
    'this was never committed' to 'I could not check' -- and the remedy for
    CACHE-AHEAD overwrites the authoritative store.

    Found in code review 2026-08-03: `git rev-list HEAD -- <path>` exits 0 with
    EMPTY stdout for a path with no history, so the empty ancestor set was being
    treated as proof rather than as ignorance.
    """

    def _seed(self, repo_body, cache_body, commit=True):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('desc', repo_body))
        if commit:
            self._commit()
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('desc', cache_body))

    def test_untracked_repo_file_never_reports_cache_newer(self):
        """Nothing is committed at this path, so rev-list yields nothing -- which
        is ignorance, not evidence the cache content is unreviewed-new."""
        self._init_git()
        # Commit something else so HEAD exists but demo/SKILL.md has no history.
        _write(self.repo / 'unrelated.txt', 'x')
        self._commit()
        self._seed('BODY\n', 'BODY\nADDED\n', commit=False)
        r = self._report_for()
        self.assertEqual(r['parts']['body']['direction'], sdr.UNKNOWN)
        self.assertEqual(r['verdict'], sdr.MANUAL_MERGE)
        self.assertNotEqual(r['verdict'], sdr.CACHE_NEWER)

    def test_part_history_hashes_is_none_when_the_path_has_no_history(self):
        self._init_git()
        _write(self.repo / 'unrelated.txt', 'x')
        self._commit()
        self.assertEqual(sdr._part_history_hashes(self.repo, 'demo/SKILL.md'),
                         (None, None))

    def test_shallow_clone_does_not_turn_a_repo_deletion_into_cache_newer(self):
        """The dangerous one. Repo deliberately DELETED a section in c2; the cache
        still holds the pre-deletion text, which is a textual superset. With full
        history that is REPO-AHEAD (reimport). In a shallow clone the deletion
        commit is invisible, so absence would read as CACHE-AHEAD and the pull
        would RE-INTRODUCE the deleted content into the authoritative store."""
        self._init_git()
        self._seed('KEEP\nDELETE ME\n', 'KEEP\nDELETE ME\n')          # c1
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('desc', 'KEEP\n'))
        self._commit('remove section')                                 # c2

        # Full history: the cache content IS an ancestor -> safe reimport.
        self.assertEqual(self._report_for()['verdict'], sdr.REPO_NEWER)

        shallow = self.tmp / 'shallow'
        subprocess.run(['git', 'clone', '-q', '--depth', '1',
                        self.repo.as_uri(), str(shallow)], capture_output=True)
        if not (shallow / '.git').exists():
            self.skipTest('shallow clone unavailable in this environment')
        r = sdr.report(shallow, self.cache, skills=['demo'])['skills']['demo']
        self.assertEqual(r['parts']['body']['direction'], sdr.UNKNOWN)
        self.assertEqual(r['verdict'], sdr.MANUAL_MERGE)

    def test_full_history_still_reports_a_genuine_cache_superset(self):
        """Guard against over-correcting into never emitting CACHE-NEWER."""
        self._init_git()
        self._seed('BODY\n', 'BODY\nADDED\n')
        self.assertEqual(self._report_for()['verdict'], sdr.CACHE_NEWER)


class ReviewFindingsRemediation(FixtureTestCase):
    """Code-review findings 3, 4, 6-10 (2026-08-03). Each test names the finding
    it pins so a future edit can't quietly undo one."""

    # --- finding 3: a half-installed skill was invisible -------------------
    def test_cache_dir_without_a_skill_md_is_broken_install_not_not_installed(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        (self.cache / 'demo').mkdir(parents=True)
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.BROKEN_INSTALL)

    def test_broken_install_is_actionable_and_rendered(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        (self.cache / 'demo').mkdir(parents=True)
        rep = sdr.report(self.repo, self.cache, skills=['demo'])
        self.assertIn(sdr.BROKEN_INSTALL, sdr.ACTIONABLE)
        self.assertIn('demo', sdr.render_text(rep))

    def test_never_installed_stays_non_actionable(self):
        """Guard: BROKEN-INSTALL must not swallow the ordinary never-installed case."""
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        self.assertEqual(self._report_for()['verdict'], sdr.NOT_INSTALLED)

    # --- finding 4: blind to anything absent from the repo working tree ----
    def test_cache_only_skill_is_reported_not_silently_dropped(self):
        """Installed platform-side with no authoritative repo source — the single
        most important direction to surface, and it was invisible."""
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        _write(self.cache / 'ghost' / 'SKILL.md', _skill_md('g', 'G\n'))
        rep = sdr.report(self.repo, self.cache)
        self.assertIn('ghost', rep['skills'])
        self.assertEqual(rep['skills']['ghost']['verdict'], sdr.CACHE_ONLY)
        self.assertIn(sdr.CACHE_ONLY, sdr.ACTIONABLE)

    def test_anthropic_stock_skills_are_not_reported_as_cache_only(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        for stock in ('docx', 'xlsx', 'pdf'):
            _write(self.cache / stock / 'SKILL.md', _skill_md('s', 'S\n'))
        rep = sdr.report(self.repo, self.cache)
        for stock in ('docx', 'xlsx', 'pdf'):
            self.assertNotIn(stock, rep['skills'])

    # --- YAML scalar quoting is serialization, not content ----------------
    def test_name_quoting_difference_alone_is_in_sync(self):
        """The platform re-serializes frontmatter on install and its quoting style
        VARIES over time: acquisition-underwriting's `name` was pulled from the
        cache QUOTED on 2026-07-27 (commit 20a936e) and the same cache served it
        UNQUOTED on 2026-08-03. That is a serialization delta with identical YAML
        meaning -- reporting it as drift is the same false-positive family as CRLF."""
        repo = '---\nname: "demo"\ndescription: d\n---\n\nBODY\n'
        cache = '---\nname: demo\ndescription: d\n---\n\nBODY\n'
        _write(self.repo / 'demo' / 'SKILL.md', repo)
        _write(self.cache / 'demo' / 'SKILL.md', cache)
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.IN_SYNC)
        self.assertEqual(r['findings'], [])

    def test_single_and_double_quoting_agree(self):
        _write(self.repo / 'demo' / 'SKILL.md', "---\nname: 'demo'\ndescription: d\n---\n\nB\n")
        _write(self.cache / 'demo' / 'SKILL.md', '---\nname: "demo"\ndescription: d\n---\n\nB\n')
        self.assertEqual(self._report_for()['verdict'], sdr.IN_SYNC)

    def test_quoting_normalization_never_masks_a_real_value_change(self):
        _write(self.repo / 'demo' / 'SKILL.md', '---\nname: "demo"\ndescription: OLD\n---\n\nB\n')
        _write(self.cache / 'demo' / 'SKILL.md', '---\nname: demo\ndescription: NEW\n---\n\nB\n')
        r = self._report_for()
        self.assertNotEqual(r['verdict'], sdr.IN_SYNC)
        self.assertNotEqual(r['parts']['frontmatter']['relation'], sdr.IDENTICAL)

    def test_block_scalar_frontmatter_survives_quoting_normalization(self):
        """The `>` indicator must not be mistaken for a quoted scalar, and indented
        continuation lines are not top-level keys."""
        fm = '---\nname: demo\ndescription: >\n  folded line one\n  folded line two\n---\n\nB\n'
        _write(self.repo / 'demo' / 'SKILL.md', fm)
        _write(self.cache / 'demo' / 'SKILL.md', fm)
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.IN_SYNC)

    def test_quoting_difference_is_ignored_in_ancestry_too(self):
        """History hashes are split the same way, so a quoting-only change in an
        older commit must not read as a real ancestral revision."""
        self._init_git()
        _write(self.repo / 'demo' / 'SKILL.md', '---\nname: "demo"\ndescription: d\n---\n\nB\n')
        self._commit()
        _write(self.repo / 'demo' / 'SKILL.md', '---\nname: demo\ndescription: d\n---\n\nB\nADDED\n')
        _write(self.cache / 'demo' / 'SKILL.md', '---\nname: demo\ndescription: d\n---\n\nB\n')
        r = self._report_for()
        self.assertEqual(r['parts']['frontmatter']['relation'], sdr.IDENTICAL)
        self.assertEqual(r['verdict'], sdr.REPO_NEWER)

    def test_reported_description_chars_come_from_RAW_frontmatter(self):
        """Compare-only normalization must never reach the reporting path. Unquoting
        a scalar discards the leading/trailing whitespace YAML quotes exist to
        protect, which silently shaved a char off the reported length (caught live
        by the replayed parcel-data-recovery fixture: 203 -> 202)."""
        desc = 'ends with a space '            # 18 chars, trailing space significant
        _write(self.repo / 'demo' / 'SKILL.md',
               f'---\nname: demo\ndescription: "{desc}"\n---\n\nB\n')
        _write(self.cache / 'demo' / 'SKILL.md',
               f'---\nname: demo\ndescription: "{desc}"\n---\n\nB\n')
        pit = self._report_for()['point_in_time']
        self.assertEqual(pit['repo_desc_chars'], len(desc))
        self.assertEqual(pit['cache_desc_chars'], len(desc))

    def test_platform_stock_skills_are_excluded_by_name(self):
        """STOCK_SKILLS is the boundary between 'ORA owns this and it is missing
        from the repo' and 'the platform ships this'. Pinned because capturing a
        stock skill would give it a bogus authoritative source that then reads as
        drift on every platform update."""
        for stock in ('docx', 'schedule', 'setup-cowork', 'morning'):
            self.assertIn(stock, sdr.STOCK_SKILLS)
        # ORA-authored skills must never be excluded as stock.
        for ora in ('lease-form-qc', 'masterlease-jurisdiction-rebase',
                    'acquisition-underwriting', 'parcel-data-recovery'):
            self.assertNotIn(ora, sdr.STOCK_SKILLS)

    def test_unknown_skill_argument_is_reported_not_silently_empty(self):
        """`... report.py dmeo` used to render a clean, empty, reassuring report."""
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        rep = sdr.report(self.repo, self.cache, skills=['dmeo'])
        self.assertEqual(rep['unknown_skills'], ['dmeo'])
        self.assertIn('dmeo', sdr.render_text(rep))

    # --- finding 6: whitespace-only churn manufactured a MANUAL-MERGE ------
    def test_trailing_newline_only_difference_is_in_sync(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'BODY\n'))
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('d', 'BODY'))
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.IN_SYNC)

    def test_blank_line_only_difference_is_in_sync(self):
        _write(self.repo / 'demo' / 'SKILL.md', '---\nname: d\ndescription: x\n---\n\nA\n\nB\n')
        _write(self.cache / 'demo' / 'SKILL.md', '---\nname: d\ndescription: x\n---\n\nA\nB\n')
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.IN_SYNC)
        self.assertEqual(r['parts']['body']['relation'], sdr.WHITESPACE_ONLY)

    def test_whitespace_normalization_never_masks_a_real_content_change(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'A\nB\n'))
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('d', 'A\nB\nREAL NEW LINE\n'))
        self.assertNotEqual(self._report_for()['verdict'], sdr.IN_SYNC)

    # --- finding 7: git history walked even when nothing differs ----------
    def test_git_history_is_not_walked_when_both_parts_are_identical(self):
        self._init_git()
        text = _skill_md('d', 'BODY\n')
        _write(self.repo / 'demo' / 'SKILL.md', text)
        self._commit()
        _write(self.cache / 'demo' / 'SKILL.md', text)
        calls = []
        real = sdr._part_history_hashes
        sdr._part_history_hashes = lambda *a, **k: (calls.append(a), real(*a, **k))[1]
        try:
            self.assertEqual(self._report_for()['verdict'], sdr.IN_SYNC)
        finally:
            sdr._part_history_hashes = real
        self.assertEqual(calls, [], 'history walked despite identical parts')

    # --- finding 8: internal key leaked from the public helper -------------
    def test_skill_md_report_does_not_leak_internal_keys(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        _write(self.cache / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        rec = sdr.skill_md_report(self.repo, self.cache, 'demo', '2026-01-01T00:00:00Z')
        self.assertFalse([k for k in rec if k.startswith('_')], f'leaked: {list(rec)}')

    # --- finding 9: a BOM defeated frontmatter detection -------------------
    def test_utf8_bom_does_not_defeat_frontmatter_detection(self):
        body = 'BODY\n'
        (self.repo / 'demo').mkdir(parents=True)
        (self.cache / 'demo').mkdir(parents=True)
        (self.repo / 'demo' / 'SKILL.md').write_bytes(
            b'\xef\xbb\xbf' + _skill_md('d', body).encode('utf-8'))
        (self.cache / 'demo' / 'SKILL.md').write_bytes(_skill_md('d', body).encode('utf-8'))
        r = self._report_for()
        self.assertEqual(r['verdict'], sdr.IN_SYNC)
        self.assertEqual(r['findings'], [])

    # --- finding 10: MAX_DESC duplicated from the packager ----------------
    def test_max_desc_is_the_packagers_constant(self):
        import package_skills
        self.assertIs(sdr.MAX_DESC, package_skills.MAX_DESC)

    # --- speculative: an unreadable file killed the entire run ------------
    def test_an_unreadable_file_does_not_abort_the_whole_report(self):
        for name in ('demo', 'locked'):
            _write(self.repo / name / 'SKILL.md', _skill_md('d', 'B\n'))
            _write(self.cache / name / 'SKILL.md', _skill_md('d', 'B\n'))
        real = sdr._read_bytes

        def boom(path):
            if 'locked' in str(path):
                raise PermissionError('file is locked by another process')
            return real(path)

        sdr._read_bytes = boom
        try:
            rep = sdr.report(self.repo, self.cache)
        finally:
            sdr._read_bytes = real
        self.assertEqual(rep['skills']['demo']['verdict'], sdr.IN_SYNC)
        self.assertEqual(rep['skills']['locked']['verdict'], sdr.UNREADABLE)
        self.assertIn('locked', sdr.render_text(rep))

    # --- speculative: read_at was the run-start stamp, not the file's -----
    def test_each_skill_carries_its_own_read_stamp(self):
        for name in ('a_demo', 'b_demo'):
            _write(self.repo / name / 'SKILL.md', _skill_md('d', 'B\n'))
            _write(self.cache / name / 'SKILL.md', _skill_md('d', 'B\n'))
        rep = sdr.report(self.repo, self.cache)
        for name in ('a_demo', 'b_demo'):
            stamp = rep['skills'][name]['point_in_time']['read_at']
            self.assertRegex(stamp, r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$')
            self.assertGreaterEqual(stamp, rep['read_at'])


class UnreadableStoreNeverFabricates(FixtureTestCase):
    def test_missing_cache_root_yields_no_drift_findings(self):
        _write(self.repo / 'demo' / 'SKILL.md', _skill_md('d', 'B\n'))
        rep = sdr.report(self.repo, self.tmp / 'nonexistent', skills=['demo'])
        self.assertTrue(rep['cache_root_unreadable'])
        self.assertEqual(rep['skills'], {})


if __name__ == '__main__':
    unittest.main(verbosity=2)
