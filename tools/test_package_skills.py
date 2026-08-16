#!/usr/bin/env python3
"""Regression tests for package_skills.check_named_counts and the shared
validate_skill_frontmatter()/check_staged() gate (2026-07-17, psa-reconciliation
1274-char description follow-up: package-time validation existed but nothing
blocked the defect at commit time).

Stdlib only — run with `python tools/test_package_skills.py` (no pytest).
Guards the named-count drift gate, including the 2026-06-11 follow-up that
taught it to count Markdown TABLE rows (e.g. loi-generation/references/
qc-gate.md presents its gate as a numbered table, not a checkbox list).
"""
import io
import json
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime
from pathlib import Path

# package_skills.py is a sibling, imported flat rather than package-relative.
# `python tools/test_package_skills.py` gets tools/ on sys.path for free (script
# dir), but `python -m unittest tools.test_package_skills` from the repo root does
# not, and fails with a bare ModuleNotFoundError that reads like a missing
# dependency rather than a cwd problem. Make both entry points work.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from package_skills import (  # noqa: E402  (deliberate: needs the path bootstrap above)
    REPO,
    _staged_content,
    check_named_counts,
    check_staged,
    check_tree_hygiene,
    is_bundled,
    resolve_outdir_collision,
    staged_skill_dirs,
    validate_skill_frontmatter,
    write_staging_manifest,
)


def run(text: str) -> str:
    """Return stdout from check_named_counts; propagate SystemExit on mismatch."""
    buf = io.StringIO()
    with redirect_stdout(buf):
        check_named_counts('fixture', text)
    return buf.getvalue()


class TableRowCounting(unittest.TestCase):
    def test_numbered_table_rows_are_counted(self):
        text = (
            '# 16-Point QC Gate\n\n'
            '| # | Check | How |\n'
            '|---|-------|-----|\n'
            + ''.join(f'| {i} | item {i} | verify |\n' for i in range(1, 17))
        )
        out = run(text)
        self.assertIn('16-Point (16 items) OK', out,
                      'numbered table rows under an N-Point header must be counted')

    def test_table_header_and_delimiter_not_counted(self):
        # 5 data rows + header + delimiter; a naive count would see 7.
        text = (
            '## 5-Point Gate\n\n'
            '| # | Check |\n'
            '|---|-------|\n'
            + ''.join(f'| {i} | x |\n' for i in range(1, 6))
        )
        out = run(text)
        self.assertIn('5-Point (5 items) OK', out)

    def test_table_count_mismatch_raises(self):
        text = (
            '## 5-Point Gate\n\n'
            '| # | Check |\n'
            '|---|-------|\n'
            + ''.join(f'| {i} | x |\n' for i in range(1, 7))  # 6 rows, claims 5
        )
        with self.assertRaises(SystemExit):
            run(text)


class ExistingFormatsStillWork(unittest.TestCase):
    def test_checkbox_list(self):
        text = '## 3-Item List\n\n- [ ] a\n- [ ] b\n- [ ] c\n'
        self.assertIn('3-Item (3 items) OK', run(text))

    def test_numbered_list(self):
        text = '## 3-Point List\n\n1. a\n2. b\n3. c\n'
        self.assertIn('3-Point (3 items) OK', run(text))

    def test_no_checklist_is_silently_skipped(self):
        text = '## 9-Point Narrative\n\nProse with no list and no table.\n'
        self.assertEqual(run(text), '')


def _make_skill(root: Path, name: str, description: str) -> Path:
    """Write a minimal valid-frontmatter skill fixture; caller controls description length."""
    skill_dir = root / name
    skill_dir.mkdir()
    (skill_dir / 'SKILL.md').write_text(
        f'---\nname: {name}\ndescription: "{description}"\n---\n\n# {name}\n\nBody.\n',
        encoding='utf-8',
    )
    return skill_dir


class ValidateSkillFrontmatter(unittest.TestCase):
    """Direct tests of the shared validator both package_skills.py (packaging time) and
    tools/hooks/pre-commit (commit time) call, so the two paths can never diverge."""

    def test_overlength_description_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = _make_skill(Path(tmp), 'fixture-skill', 'x' * 1100)
            errors = validate_skill_frontmatter(skill_dir)
            self.assertTrue(
                any('1100' in e and 'exceeds the 1024-char' in e for e in errors),
                f'expected an over-length description error, got: {errors}',
            )

    def test_valid_skill_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = _make_skill(Path(tmp), 'fixture-skill', 'a short valid description')
            errors = validate_skill_frontmatter(skill_dir)
            self.assertEqual(errors, [])

    def test_name_mismatch_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = root / 'fixture-skill'
            skill_dir.mkdir()
            (skill_dir / 'SKILL.md').write_text(
                '---\nname: wrong-name\ndescription: "ok"\n---\n\n# x\n', encoding='utf-8',
            )
            errors = validate_skill_frontmatter(skill_dir)
            self.assertTrue(any("!= directory name" in e for e in errors))

    def test_missing_description_field_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / 'fixture-skill'
            skill_dir.mkdir()
            (skill_dir / 'SKILL.md').write_text(
                '---\nname: fixture-skill\n---\n\n# x\n', encoding='utf-8',
            )
            errors = validate_skill_frontmatter(skill_dir)
            self.assertTrue(any("no 'description'" in e for e in errors))

    def test_xml_tag_in_description_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / 'fixture-skill'
            skill_dir.mkdir()
            (skill_dir / 'SKILL.md').write_text(
                '---\nname: fixture-skill\ndescription: "Use <skill> for X"\n---\n\n# x\n',
                encoding='utf-8',
            )
            errors = validate_skill_frontmatter(skill_dir)
            self.assertTrue(any('XML-like tag' in e for e in errors))

    def test_read_text_and_md_files_override(self):
        """The read_text/md_files hooks let a caller (check_staged) supply STAGED content
        instead of disk content — skill_dir need not even exist on disk when both are given."""
        calls = []

        def fake_read(rel):
            calls.append(rel)
            return {'SKILL.md': '---\nname: fixture-skill\ndescription: "ok"\n---\n\n# x\n'}[rel]

        errors = validate_skill_frontmatter(
            Path('nonexistent') / 'fixture-skill', read_text=fake_read, md_files=['SKILL.md'],
        )
        self.assertEqual(errors, [])
        self.assertIn('SKILL.md', calls)

    def test_unreadable_secondary_md_file_reported_not_raised(self):
        """A staged file `md_files` names but `read_text` can't retrieve (e.g. a
        merge-conflicted file with no stage-0 git index entry -- `git show :path`
        exits non-zero) must surface as a validation error, not propagate as a raw
        exception (code review finding, 2026-07-17: only the SKILL.md read was
        exception-guarded; every other _read(rel) call in the loop was not)."""
        def flaky_read(rel):
            if rel == 'SKILL.md':
                return '---\nname: fixture-skill\ndescription: "ok"\n---\n\n# x\n'
            raise subprocess.CalledProcessError(128, ['git', 'show'])

        errors = validate_skill_frontmatter(
            Path('nonexistent') / 'fixture-skill', read_text=flaky_read,
            md_files=['SKILL.md', 'references/conflicted.md'],
        )
        self.assertTrue(
            any('references/conflicted.md' in e and 'could not read' in e for e in errors),
            f'expected a clean could-not-read error naming the file, got: {errors}',
        )

    def test_unreadable_secondary_md_file_does_not_block_other_findings(self):
        """The unreadable-file error must be appended alongside other real findings,
        not swallow them or short-circuit the scan."""
        def flaky_read(rel):
            if rel == 'SKILL.md':
                return '---\nname: wrong-name\ndescription: "ok"\n---\n\n# x\n'
            raise FileNotFoundError(rel)

        errors = validate_skill_frontmatter(
            Path('nonexistent') / 'fixture-skill', read_text=flaky_read,
            md_files=['SKILL.md', 'references/missing.md'],
        )
        self.assertTrue(any('!= directory name' in e for e in errors))
        self.assertTrue(any('references/missing.md' in e and 'could not read' in e for e in errors))


class FrontmatterYamlValidityGate(unittest.TestCase):
    """2026-08-13 follow-up: package_skills.py validated description *length* via regex
    while blind to whether the frontmatter YAML block actually parses. parcel-data-recovery
    v1.7 shipped a description with an unescaped inner '"' that closed the scalar early --
    the packager printed 'description 966/1024 chars OK' and the platform silently rejected
    the import at packaging time with no main.log line at all.

    A repo-wide sweep (2026-08-13) found the install-blocking defect is narrow: a
    double-quoted description whose first unescaped closing '"' lands BEFORE the end of the
    value, leaving trailing content that corrupts the block mapping (YAML ParserError:
    'expected <block end>, but found <scalar>'). Two other strict-YAML failure modes exist
    in 19 currently-installed skills and must NOT be flagged, since the platform tolerates
    both: an unquoted description containing ': ' (15 skills, e.g. capex-budgeting), and a
    double-quoted description that never closes at all -- missing closing quote entirely (4
    skills, e.g. document-assembly; YAML ScannerError: 'unexpected end of stream'). Gating on
    strict YAML validity alone would flag all 19 and churn working skills to no effect.
    """

    def test_real_prefix_parcel_data_recovery_is_rejected(self):
        # Recovered via `git show d03fe62:parcel-data-recovery/SKILL.md` -- the exact
        # content that shipped in commit d03fe62 and that the platform rejected.
        description = (
            'County-level building SF, market value, year-built, and tax-delinquency '
            'recovery for Oxford Realty Advisors off-market parcel screens. Encodes '
            'verified endpoints (2026-06-11). v1.7 (2026-08-12: tombstoned the dangling '
            '"rent-comp P2" placeholder reference). v1.6 (2026-07-27)'
        )
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / 'fixture-skill'
            skill_dir.mkdir()
            (skill_dir / 'SKILL.md').write_text(
                f'---\nname: fixture-skill\ndescription: "{description}"\n---\n\n# x\n',
                encoding='utf-8',
            )
            errors = validate_skill_frontmatter(skill_dir)
            self.assertTrue(
                any('unescaped' in e and 'fixture-skill' in e for e in errors),
                f'expected an unescaped-inner-quote rejection, got: {errors}',
            )

    def test_fixed_parcel_data_recovery_passes(self):
        # The single-quote fix actually committed (dcdc98e) -- must pass clean.
        description = (
            'County-level building SF recovery. v1.7 (2026-08-12: tombstoned the dangling '
            "'rent-comp P2' placeholder reference). v1.6 (2026-07-27)"
        )
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = _make_skill(Path(tmp), 'fixture-skill', description)
            errors = validate_skill_frontmatter(skill_dir)
            self.assertEqual(errors, [])

    def test_unquoted_description_with_colon_space_is_not_flagged(self):
        """Class B (benign): matches the 15 live skills like capex-budgeting whose
        unquoted description contains ': ' -- strict yaml.safe_load rejects this
        ('mapping values are not allowed here') but the platform installs it fine."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / 'fixture-skill'
            skill_dir.mkdir()
            (skill_dir / 'SKILL.md').write_text(
                '---\nname: fixture-skill\n'
                'description: Use when the user mentions: capex budget, capital plan\n'
                '---\n\n# x\n',
                encoding='utf-8',
            )
            errors = validate_skill_frontmatter(skill_dir)
            self.assertEqual(errors, [])

    def test_unterminated_double_quoted_description_is_not_flagged(self):
        """Class B (benign): matches the 4 live skills like document-assembly whose
        double-quoted description is missing its closing quote entirely -- strict
        yaml.safe_load rejects this ('unexpected end of stream') but the platform
        installs it fine, and there is no trailing garbage corrupting the mapping."""
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / 'fixture-skill'
            skill_dir.mkdir()
            (skill_dir / 'SKILL.md').write_text(
                '---\nname: fixture-skill\n'
                'description: "Automated document generation. v1.3 — changelog in body.\n'
                '---\n\n# x\n',
                encoding='utf-8',
            )
            errors = validate_skill_frontmatter(skill_dir)
            self.assertEqual(errors, [])


class StagedSkillMapping(unittest.TestCase):
    """staged_skill_dirs() takes an explicit `files` list in tests so it never shells
    out to the real `git diff --cached` — a commit touching only non-skill files must
    map to zero skill roots."""

    def test_non_skill_files_are_noop(self):
        roots = staged_skill_dirs(files=['README.md', 'tools/package_skills.py', '_archive/foo.md'])
        self.assertEqual(roots, [])

    def test_skill_file_maps_to_its_root(self):
        roots = staged_skill_dirs(files=['psa-reconciliation/SKILL.md', 'psa-reconciliation/references/x.md'])
        self.assertEqual(roots, [REPO / 'psa-reconciliation'])

    def test_files_none_uses_real_git_staged_diff(self):
        """Exercises the live `git diff --cached` subprocess path (files=None), not just the
        injected-list path every other test uses."""
        result = staged_skill_dirs()
        self.assertIsInstance(result, list)


class CheckStagedLiveGitIndex(unittest.TestCase):
    """check_staged() must validate the STAGED git-index content, not the working tree —
    a stage-then-edit-without-restaging gap found in code review (2026-07-17). Exercises the
    real `git add`/`git show :path`/`git ls-files --cached` machinery against a throwaway
    fixture skill inside THIS worktree's own repo (never the shared main checkout), cleaned
    up in tearDown even on failure.
    """

    FIXTURE_NAME = '_fixture-review-skill'

    def setUp(self):
        self.fixture_dir = REPO / self.FIXTURE_NAME

    def tearDown(self):
        subprocess.run(
            ['git', '-C', str(REPO), 'reset', '--', self.FIXTURE_NAME],
            capture_output=True,
        )
        if self.fixture_dir.is_dir():
            for p in sorted(self.fixture_dir.rglob('*'), reverse=True):
                p.unlink()
            self.fixture_dir.rmdir()

    def _stage(self, description: str) -> None:
        self.fixture_dir.mkdir(exist_ok=True)
        (self.fixture_dir / 'SKILL.md').write_text(
            f'---\nname: {self.FIXTURE_NAME}\ndescription: "{description}"\n---\n\n# x\n',
            encoding='utf-8',
        )
        subprocess.run(
            ['git', '-C', str(REPO), 'add', f'{self.FIXTURE_NAME}/SKILL.md'], check=True,
        )

    def _run_check(self) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stderr(buf):
            rc = check_staged(files=[f'{self.FIXTURE_NAME}/SKILL.md'])
        return rc, buf.getvalue()

    def test_blocks_on_staged_overlength_description(self):
        self._stage('x' * 1100)
        rc, err = self._run_check()
        self.assertEqual(rc, 1)
        self.assertIn('exceeds the 1024-char', err)

    def test_passes_on_staged_valid_description(self):
        self._stage('a short valid description')
        rc, _ = self._run_check()
        self.assertEqual(rc, 0)

    def test_reads_staged_content_not_dirtied_working_tree(self):
        """Stage a GOOD description, then dirty the working tree with a BAD one WITHOUT
        restaging. check_staged() must validate the staged (good) blob, not the dirtied
        (bad) working-tree file — this is the exact gap the code review flagged."""
        self._stage('a short valid description')
        (self.fixture_dir / 'SKILL.md').write_text(
            f'---\nname: {self.FIXTURE_NAME}\ndescription: "{"x" * 1100}"\n---\n\n# x\n',
            encoding='utf-8',
        )
        rc, _ = self._run_check()
        self.assertEqual(rc, 0, 'must validate the staged blob, not the dirtied working tree')


class CheckStaged(unittest.TestCase):
    """check_staged() is what tools/hooks/pre-commit invokes directly."""

    def test_noop_for_non_skill_files(self):
        self.assertEqual(check_staged(files=['README.md']), 0)


class StagedContentEncoding(unittest.TestCase):
    """_staged_content() must decode staged git-index blobs as UTF-8 explicitly, not
    whatever subprocess.run's text=True falls back to (commonly cp1252 on Windows) --
    code review finding, 2026-07-17. Exercises the real git index against a throwaway
    fixture inside THIS worktree's own repo, cleaned up in tearDown even on failure."""

    FIXTURE_PATH = '_fixture-encoding-check.md'

    def tearDown(self):
        subprocess.run(
            ['git', '-C', str(REPO), 'reset', '--', self.FIXTURE_PATH],
            capture_output=True,
        )
        p = REPO / self.FIXTURE_PATH
        if p.is_file():
            p.unlink()

    def test_multibyte_utf8_content_round_trips_exactly(self):
        # Every one of these characters is multi-byte in UTF-8 and would mis-decode
        # (mojibake) or raise UnicodeDecodeError under cp1252, the common Windows
        # locale fallback subprocess.run(text=True) uses without an explicit encoding.
        content = 'café — β 中文 description\n'
        p = REPO / self.FIXTURE_PATH
        p.write_text(content, encoding='utf-8')
        subprocess.run(['git', '-C', str(REPO), 'add', self.FIXTURE_PATH], check=True)

        self.assertEqual(_staged_content(self.FIXTURE_PATH), content)


class ResolveOutdirCollision(unittest.TestCase):
    """Regression tests for the 2026-07-24 register-scheduled-task incident: a swapped
    outdir/skill argument to package_skills.py <outdir> [skill ...] must be caught before
    outdir.mkdir()/package() ever run, not discovered after 15GB of contamination."""

    def test_outdir_matching_skill_dir_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, 'register-scheduled-task', 'ok')
            collision = resolve_outdir_collision(root / 'register-scheduled-task', repo=root)
            self.assertIsNotNone(collision)
            self.assertIn('register-scheduled-task', collision)

    def test_outdir_matching_repo_root_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, 'some-skill', 'ok')
            collision = resolve_outdir_collision(root, repo=root)
            self.assertIsNotNone(collision)
            self.assertIn('repo root', collision)

    def test_genuine_outside_outdir_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / 'repo'
            root.mkdir()
            _make_skill(root, 'some-skill', 'ok')
            outdir = Path(tmp) / 'outputs'
            self.assertIsNone(resolve_outdir_collision(outdir, repo=root))

    def test_skip_listed_dirs_never_collide(self):
        """tools/, _archive/, .git/ are not skills — swapping outdir to one of those is
        a different (and much less dangerous) mistake, not this guard's job."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'tools').mkdir()
            (root / 'tools' / 'SKILL.md').write_text('placeholder', encoding='utf-8')
            self.assertIsNone(resolve_outdir_collision(root / 'tools', repo=root))


class CheckTreeHygiene(unittest.TestCase):
    """Regression tests for the pre-commit Check 3 tripwire: *.skill/*.plugin build
    artifacts (gitignored, so invisible to git status) must never sit inside a skill's
    own source directory, at any size."""

    def test_clean_tree_has_no_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_skill(root, 'some-skill', 'ok')
            self.assertEqual(check_tree_hygiene(repo=root), [])

    def test_small_stray_skill_file_is_still_flagged(self):
        """Presence alone is the signal — a tiny stray file indicates the same class of
        mistake as a 15GB one, just caught earlier."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = _make_skill(root, 'some-skill', 'ok')
            (skill_dir / 'other-skill.skill').write_bytes(b'PK\x03\x04tiny')
            errors = check_tree_hygiene(repo=root)
            self.assertTrue(any('other-skill.skill' in e for e in errors))
            self.assertFalse(any('MB' in e for e in errors), 'small file should not be size-flagged')

    def test_oversized_stray_skill_file_calls_out_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = _make_skill(root, 'some-skill', 'ok')
            big = skill_dir / 'other-skill.skill'
            with big.open('wb') as f:
                f.seek(6 * 1024 * 1024 - 1)
                f.write(b'\0')
            errors = check_tree_hygiene(repo=root, max_bytes=5 * 1024 * 1024)
            self.assertTrue(any('MB' in e and 'other-skill.skill' in e for e in errors))

    def test_stray_plugin_file_is_flagged_same_as_skill(self):
        """build_plugin.py's .plugin output is the identical contamination class one
        level up (same rglob('*') -> is_bundled() source-assembly path) — must be
        caught by the same tripwire, not just the extension the original incident
        happened to produce."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            skill_dir = _make_skill(root, 'some-skill', 'ok')
            (skill_dir / 'some-plugin.plugin').write_bytes(b'PK\x03\x04tiny')
            errors = check_tree_hygiene(repo=root)
            self.assertTrue(any('some-plugin.plugin' in e for e in errors))


class IsBundledExclusions(unittest.TestCase):
    """is_bundled() is the single source of truth for what ships in a .skill.

    The __pycache__/*.pyc rules were added 2026-08-01: .gitignore already keeps
    bytecode out of git, so it is invisible to a repo diff — but the packager walks
    the WORKING TREE, and shipped a stale audit_completeness.cpython-310.pyc into
    deal-execution.skill after its scripts were run locally. A bundled .pyc also makes
    the runtime cache's file count differ from the repo's, which reads as permanent
    drift on every subsequent hash pre-check.
    """

    def test_excludes_pycache_dir_at_any_depth(self):
        self.assertFalse(is_bundled('scripts/__pycache__/audit.cpython-310.pyc'))
        self.assertFalse(is_bundled('__pycache__/x.pyc'))
        self.assertFalse(is_bundled('a/b/__pycache__/c.pyc'))

    def test_excludes_loose_bytecode(self):
        self.assertFalse(is_bundled('scripts/compiled.pyc'))
        self.assertFalse(is_bundled('scripts/compiled.pyo'))

    def test_still_bundles_real_skill_content(self):
        for rel in ('SKILL.md', 'scripts/extract_revisions.py',
                    'references/qc-gate.md', 'templates/loi.docx',
                    'scripts/pycache_helper.py', 'target-markets.json'):
            self.assertTrue(is_bundled(rel), rel)

    def test_prior_exclusions_unchanged(self):
        self.assertFalse(is_bundled('PACKAGING-NOTE.md'))
        self.assertFalse(is_bundled('references/PACKAGING-NOTE.md'))
        self.assertFalse(is_bundled('versions/20260716_snapshot.md'))


class StagingManifest(unittest.TestCase):
    """Regression tests for the 2026-08-15 staging sentinel (Rev 10 remediation): a
    downstream consumer pointed at an outdir this script never wrote to had no way to
    tell "not staged yet" apart from "staged, produced zero packages" or "staged at a
    different path than the one it was told" without a manual tree walk. Tested
    directly against write_staging_manifest() rather than through package() — package()
    reads the module-global REPO constant with no repo= override (unlike
    resolve_outdir_collision/check_tree_hygiene), so it isn't fixture-testable; the
    manifest writer itself takes only Path/list-of-Path arguments and needs no repo."""

    def test_manifest_records_every_package_with_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            a = outdir / 'skill-a.skill'
            a.write_bytes(b'PK\x03\x04' + b'x' * 10)
            b = outdir / 'skill-b.skill'
            b.write_bytes(b'PK\x03\x04' + b'y' * 20)
            sentinel = write_staging_manifest(outdir, [a, b])
            self.assertEqual(sentinel, outdir / '_STAGED.ok')
            self.assertTrue(sentinel.is_file())
            manifest = json.loads(sentinel.read_text(encoding='utf-8'))
            self.assertEqual(manifest['outdir'], str(outdir.resolve()))
            self.assertIn('staged_at', manifest)
            packages = {p['skill']: p for p in manifest['packages']}
            self.assertEqual(set(packages), {'skill-a', 'skill-b'})
            self.assertEqual(packages['skill-a']['file'], 'skill-a.skill')
            self.assertEqual(packages['skill-a']['bytes'], a.stat().st_size)
            self.assertEqual(packages['skill-b']['bytes'], b.stat().st_size)

    def test_empty_batch_still_writes_a_manifest(self):
        """A zero-skill run (e.g. a typo'd skill filter) must still leave a sentinel —
        the whole point is distinguishing 'ran, staged nothing' from 'never ran'."""
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            sentinel = write_staging_manifest(outdir, [])
            self.assertTrue(sentinel.is_file())
            manifest = json.loads(sentinel.read_text(encoding='utf-8'))
            self.assertEqual(manifest['packages'], [])

    def test_staged_at_is_utc_iso8601(self):
        with tempfile.TemporaryDirectory() as tmp:
            sentinel = write_staging_manifest(Path(tmp), [])
            manifest = json.loads(sentinel.read_text(encoding='utf-8'))
            # e.g. 2026-08-15T13:04:22Z — raises ValueError if the format drifts
            datetime.strptime(manifest['staged_at'], '%Y-%m-%dT%H:%M:%SZ')

    def test_second_batch_preserves_first_batchs_entries(self):
        """Regression for the 2026-08-15 same-day fix: a shared outdir (e.g.
        `_staging/<date>/`) routinely collects multiple unrelated packaging runs.
        The manifest must ACCUMULATE, not overwrite — the exact bug that made
        automation-health-monitor.skill invisible to a later downstream freshness
        check after an unrelated insurance-renewal-review + package-and-stage-skill
        batch overwrote its entry out of _STAGED.ok."""
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            first = outdir / 'automation-health-monitor.skill'
            first.write_bytes(b'PK\x03\x04' + b'a' * 10)
            write_staging_manifest(outdir, [first])

            second = outdir / 'insurance-renewal-review.skill'
            second.write_bytes(b'PK\x03\x04' + b'b' * 20)
            third = outdir / 'package-and-stage-skill.skill'
            third.write_bytes(b'PK\x03\x04' + b'c' * 30)
            sentinel = write_staging_manifest(outdir, [second, third])

            manifest = json.loads(sentinel.read_text(encoding='utf-8'))
            packages = {p['skill']: p for p in manifest['packages']}
            self.assertEqual(
                set(packages),
                {'automation-health-monitor', 'insurance-renewal-review', 'package-and-stage-skill'},
            )
            self.assertEqual(packages['automation-health-monitor']['bytes'], first.stat().st_size)

    def test_repackaging_same_skill_refreshes_not_duplicates(self):
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            v1 = outdir / 'daily-brief.skill'
            v1.write_bytes(b'PK\x03\x04' + b'x' * 10)
            write_staging_manifest(outdir, [v1])

            v1.write_bytes(b'PK\x03\x04' + b'x' * 999)  # simulate a repackage in place
            sentinel = write_staging_manifest(outdir, [v1])

            manifest = json.loads(sentinel.read_text(encoding='utf-8'))
            self.assertEqual(len(manifest['packages']), 1)
            self.assertEqual(manifest['packages'][0]['bytes'], v1.stat().st_size)

    def test_last_batch_reflects_only_the_current_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            a = outdir / 'skill-a.skill'
            a.write_bytes(b'PK\x03\x04' + b'a' * 10)
            write_staging_manifest(outdir, [a])

            b = outdir / 'skill-b.skill'
            b.write_bytes(b'PK\x03\x04' + b'b' * 10)
            sentinel = write_staging_manifest(outdir, [b])

            manifest = json.loads(sentinel.read_text(encoding='utf-8'))
            self.assertEqual(manifest['last_batch'], ['skill-b'])
            self.assertEqual({p['skill'] for p in manifest['packages']}, {'skill-a', 'skill-b'})

    def test_corrupt_existing_sentinel_does_not_block_a_fresh_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp)
            (outdir / '_STAGED.ok').write_text('not valid json {{{', encoding='utf-8')
            a = outdir / 'skill-a.skill'
            a.write_bytes(b'PK\x03\x04' + b'a' * 10)
            sentinel = write_staging_manifest(outdir, [a])
            manifest = json.loads(sentinel.read_text(encoding='utf-8'))
            self.assertEqual({p['skill'] for p in manifest['packages']}, {'skill-a'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
