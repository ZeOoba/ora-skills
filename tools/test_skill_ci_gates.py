#!/usr/bin/env python3
"""Tests for tools/skill_ci_gates.py and tools/run_suite.sh's glob arguments (2026-10-03).

Stdlib only -- run with `python tools/test_skill_ci_gates.py` (no pytest).
"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import skill_ci_gates as g  # noqa: E402
from package_skills import REPO, SHARED_ROOT_DEPS, _dep_pair  # noqa: E402


def _skill(root: Path, name: str, body: str = 'x', files: dict | None = None) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: d\n---\n{body}\n', encoding='utf-8')
    for rel, text in (files or {}).items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
    return d


class TempRepo(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)


class SuiteCoverage(TempRepo):
    def test_every_discovered_file_is_gated(self):
        _skill(self.root, 'a', files={'tests/test_a.py': '', 'lib/test_b.py': ''})
        files, errors = g.suite_coverage(self.root)
        self.assertEqual(files, ['a/lib/test_b.py', 'a/tests/test_a.py'])
        self.assertEqual(errors, [])

    def test_ci_exclude_marker_keeps_file_out(self):
        _skill(self.root, 'a', files={'tests/test_a.py': 'CI_EXCLUDE = "linux case folding"\n',
                                      'tests/test_b.py': ''})
        files, errors = g.suite_coverage(self.root)
        self.assertEqual((files, errors), (['a/tests/test_b.py'], []))
        self.assertEqual(g.excluded_suites(self.root), {'a/tests/test_a.py': 'linux case folding'})

    def test_single_quoted_marker_counts(self):
        _skill(self.root, 'a', files={'tests/test_a.py': "CI_EXCLUDE = 'why'\n"})
        self.assertEqual(g.suite_coverage(self.root), ([], []))

    def test_blank_reason_is_an_error_and_not_excluded_silently(self):
        _skill(self.root, 'a', files={'tests/test_a.py': 'CI_EXCLUDE = "   "\n'})
        files, errors = g.suite_coverage(self.root)
        self.assertEqual(files, [])
        self.assertTrue(any('empty reason' in e for e in errors), errors)

    def test_indented_marker_does_not_count(self):
        _skill(self.root, 'a', files={'tests/test_a.py': 'def f():\n    CI_EXCLUDE = "x"\n'})
        self.assertEqual(g.suite_coverage(self.root), (['a/tests/test_a.py'], []))

    def test_archive_and_non_skill_dirs_ignored(self):
        (self.root / '_archive' / 'old' / 'tests').mkdir(parents=True)
        (self.root / '_archive' / 'old' / 'SKILL.md').write_text('x', encoding='utf-8')
        (self.root / '_archive' / 'old' / 'tests' / 'test_x.py').write_text('', encoding='utf-8')
        (self.root / 'notaskill').mkdir()
        (self.root / 'notaskill' / 'test_y.py').write_text('', encoding='utf-8')
        self.assertEqual(g.discover_skill_test_files(self.root), [])

    def test_real_repo_gates_known_suites_and_excludes_parse_replays(self):
        files, errors = g.suite_coverage()
        self.assertEqual(errors, [])
        self.assertIn('lease-form-qc/tests/test_lease_qc.py', files)
        self.assertIn('acquisition-underwriting-eval-harness/lib/test_parse_replays.py',
                      g.excluded_suites())
        self.assertNotIn('acquisition-underwriting-eval-harness/lib/test_parse_replays.py', files)


class ReadmeInventory(TempRepo):
    def test_skill_missing_from_readme_is_flagged(self):
        _skill(self.root, 'a')
        _skill(self.root, 'b')
        (self.root / 'README.md').write_text('- `a` -- listed\n', encoding='utf-8')
        errors = g.skills_missing_from_readme(self.root)
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith('b: not listed in README.md'))

    def test_all_listed_passes(self):
        _skill(self.root, 'a')
        (self.root / 'README.md').write_text('- `a` -- listed\n', encoding='utf-8')
        self.assertEqual(g.skills_missing_from_readme(self.root), [])

    def test_real_repo_every_skill_is_in_the_readme(self):
        self.assertEqual(g.skills_missing_from_readme(REPO), [])


class UndeclaredSharedDeps(TempRepo):
    def test_skill_md_citation_without_declaration_is_flagged(self):
        _skill(self.root, 'a', body='reads target-markets.json at run time')
        errors = g.undeclared_shared_deps(self.root, deps={}, exempt={})
        self.assertEqual(len(errors), 1)
        self.assertIn('a: SKILL.md cites target-markets.json', errors[0])

    def test_declared_citation_passes(self):
        _skill(self.root, 'a', body='reads target-markets.json')
        (self.root / 'target-markets.json').write_text('{}', encoding='utf-8')
        self.assertEqual(g.undeclared_shared_deps(
            self.root, deps={'a': ['target-markets.json']}, exempt={}), [])

    def test_exempt_citation_passes(self):
        _skill(self.root, 'a', body='mentions target-markets.json')
        self.assertEqual(g.undeclared_shared_deps(self.root, deps={}, exempt={'a': 'r'}), [])

    def test_script_import_without_declaration_is_flagged(self):
        _skill(self.root, 'a', files={'scripts/x.py': 'from ora_doc_qc import run_cli\n'})
        errors = g.undeclared_shared_deps(self.root, deps={}, exempt={})
        self.assertEqual(len(errors), 1)
        self.assertIn('a/scripts/x.py import ora_doc_qc', errors[0])

    def test_import_inside_tests_dir_is_not_a_runtime_dependency(self):
        _skill(self.root, 'a', files={'tests/test_x.py': 'import ora_doc_qc\n'})
        self.assertEqual(g.undeclared_shared_deps(self.root, deps={}, exempt={}), [])

    def test_mention_in_a_comment_is_not_an_import(self):
        _skill(self.root, 'a', files={'scripts/x.py': '# ora_doc_qc is shared\nimport os\n'})
        self.assertEqual(g.undeclared_shared_deps(self.root, deps={}, exempt={}), [])

    def test_tuple_declaration_counts(self):
        _skill(self.root, 'a', files={'scripts/x.py': 'import ora_doc_qc\n'})
        (self.root / 'tools').mkdir()
        (self.root / 'tools' / 'ora_doc_qc.py').write_text('', encoding='utf-8')
        deps = {'a': [('tools/ora_doc_qc.py', 'scripts/ora_doc_qc.py')]}
        self.assertEqual(g.undeclared_shared_deps(self.root, deps=deps, exempt={}), [])

    def test_missing_declared_source_and_bad_key_are_flagged(self):
        _skill(self.root, 'a')
        errors = g.undeclared_shared_deps(
            self.root, deps={'a': ['target-markets.json'], 'ghost': ['x.json']}, exempt={})
        self.assertTrue(any('a: declared shared dep target-markets.json does not exist' in e
                            for e in errors), errors)
        self.assertTrue(any("'ghost' is not a skill directory" in e for e in errors), errors)

    def test_real_repo_declares_every_citing_skill(self):
        self.assertEqual(g.undeclared_shared_deps(), [])

    def test_insurance_climate_declares_target_markets(self):
        # Its SKILL.md resolves cluster counties from target-markets.json at run time.
        text = (REPO / 'insurance-climate-risk-comparison' / 'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('target-markets.json', text)
        self.assertIn('target-markets.json',
                      {_dep_pair(d)[0] for d in SHARED_ROOT_DEPS['insurance-climate-risk-comparison']})


class TargetMarketsVersionRule(unittest.TestCase):
    def doc(self, version='1.0', **extra):
        d = {'version': version, **extra}
        return json.dumps(d)

    def test_unchanged_passes(self):
        t = self.doc()
        self.assertIsNone(g.check_target_markets_version(t, t))

    def test_changed_without_bump_fails(self):
        err = g.check_target_markets_version(self.doc(a=1), self.doc(a=2))
        self.assertIn('"version" is still', err)

    def test_changed_with_bump_passes(self):
        self.assertIsNone(g.check_target_markets_version(self.doc('1.0', a=1), self.doc('1.1', a=2)))

    def test_new_file_with_version_passes(self):
        self.assertIsNone(g.check_target_markets_version(None, self.doc()))

    def test_deleted_file_is_not_this_gates_concern(self):
        self.assertIsNone(g.check_target_markets_version(self.doc(), None))

    def test_invalid_json_at_head_fails(self):
        self.assertIn('not valid JSON', g.check_target_markets_version(self.doc(), '{nope'))

    def test_missing_version_at_head_fails(self):
        self.assertIn('no top-level "version"',
                      g.check_target_markets_version(self.doc(), json.dumps({'a': 1})))

    def test_version_only_in_nested_changelog_text_does_not_count(self):
        # The pre-commit grep accepts any added line containing "version"; the CI rule
        # compares the parsed top-level value, so a changelog edit alone cannot pass.
        base = self.doc('1.0', changelog='x')
        head = self.doc('1.0', changelog='"version" bumped to 1.1')
        self.assertIsNotNone(g.check_target_markets_version(base, head))


class ResolveBase(unittest.TestCase):
    def test_explicit_ref_passes_through(self):
        self.assertEqual(g.resolve_base('abc123', env={}), 'abc123')

    def test_main_push_uses_before_sha(self):
        env = {'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_BEFORE': 'f' * 40}
        self.assertEqual(g.resolve_base('auto', env=env), 'f' * 40)

    def test_main_push_with_zero_before_falls_back(self):
        env = {'GITHUB_REF': 'refs/heads/main', 'GITHUB_EVENT_BEFORE': '0' * 40}
        self.assertEqual(g.resolve_base('auto', env=env), 'HEAD~1')

    def test_branch_push_uses_fork_point_with_origin_main(self):
        # Synthetic repo (the real clone may be shallow in tools-tests CI):
        # c1 <- origin/main ; c1 <- c2 <- c3 (HEAD on feature). Fork point = c1.
        root = Path(tempfile.mkdtemp())
        try:
            def git(*a):
                return subprocess.run(
                    ['git', '-C', str(root), '-c', 'user.name=t', '-c', 'user.email=t@example.invalid',
                     '-c', 'core.hooksPath=/dev/null', *a],
                    capture_output=True, text=True, check=True).stdout.strip()
            git('init', '-q')
            for i in (1, 2, 3):
                (root / 'f.txt').write_text(str(i), encoding='utf-8')
                git('add', 'f.txt')
                git('commit', '-q', '-m', f'c{i}')
                if i == 1:
                    c1 = git('rev-parse', 'HEAD')
                    git('update-ref', 'refs/remotes/origin/main', c1)
            base = g.resolve_base('auto', env={'GITHUB_REF': 'refs/heads/feature'}, repo=root)
            self.assertEqual(base, c1)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_branch_push_without_origin_main_falls_back(self):
        root = Path(tempfile.mkdtemp())
        try:
            subprocess.run(['git', '-C', str(root), 'init', '-q'], check=True)
            self.assertEqual(g.resolve_base('auto', env={}, repo=root), 'HEAD~1')
        finally:
            shutil.rmtree(root, ignore_errors=True)


class CliAgainstRealRepo(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(REPO / 'tools' / 'skill_ci_gates.py'), *args],
                              capture_output=True, text=True, encoding='utf-8')

    def test_frontmatter_gate_is_clean(self):
        r = self.run_cli('frontmatter')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertRegex(r.stdout, r'frontmatter: \d+ skills, 0 error\(s\)')

    def test_target_markets_against_head_is_clean(self):
        r = self.run_cli('target-markets', '--base', 'HEAD')
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_target_markets_bad_base_is_usage_error(self):
        r = self.run_cli('target-markets', '--base', 'no-such-ref-xyz')
        self.assertEqual(r.returncode, 2)

    def test_unknown_subcommand_is_usage_error(self):
        self.assertEqual(self.run_cli('nope').returncode, 2)

    def test_packaged_layout_resolves_staged_copies(self):
        r = self.run_cli('packaged-layout')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('lease-form-qc/scripts/lease_qc.py -> lease-form-qc/scripts/ora_doc_qc.py', r.stdout)
        # Staging happened outside the checkout: nothing was copied into the tree.
        self.assertFalse((REPO / 'lease-form-qc' / 'scripts' / 'ora_doc_qc.py').exists())


class StagedImportTargets(TempRepo):
    def test_finds_importers_but_not_the_module_itself(self):
        _skill(self.root, 'a', files={'scripts/x.py': 'from shared import f\n',
                                      'scripts/y.py': 'import os\n',
                                      'scripts/shared.py': 'import shared_other\n'})
        got = g.staged_import_targets('a', self.root, deps={'a': [('tools/shared.py', 'scripts/shared.py')]})
        self.assertEqual([(p.name, m) for p, m in got], [('x.py', 'shared')])

    def test_non_python_deps_are_ignored(self):
        _skill(self.root, 'a', files={'scripts/x.py': 'import json\n'})
        self.assertEqual(g.staged_import_targets('a', self.root, deps={'a': ['target-markets.json']}), [])


class RunSuiteGlobArgs(unittest.TestCase):
    """tools/run_suite.sh's optional GLOB arguments (used by run_skill_suites.sh)."""

    def run_suite(self, *args):
        bash = shutil.which('bash')
        if bash is None:
            self.fail('bash not on PATH')
        return subprocess.run([bash, str(REPO / 'tools' / 'run_suite.sh'), *args],
                              capture_output=True, text=True, encoding='utf-8', cwd=tempfile.gettempdir())

    def test_unmatched_glob_fails(self):
        r = self.run_suite('no-such-skill/tests/test_*.py')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('NOMATCH no-such-skill/tests/test_*.py', r.stdout)

    def test_unmatched_literal_path_fails(self):
        r = self.run_suite('tools/test_does_not_exist.py')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('NOMATCH', r.stdout)

    def test_explicit_glob_runs_only_matching_files_from_any_cwd(self):
        r = self.run_suite('tools/test_reimport_correlate.py')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('files: 1  failed: 0', r.stdout)


if __name__ == '__main__':
    unittest.main()
