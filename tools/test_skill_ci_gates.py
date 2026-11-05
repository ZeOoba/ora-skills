#!/usr/bin/env python3
"""Tests for tools/skill_ci_gates.py and tools/run_suite.sh's glob arguments (2026-10-03).

Stdlib only -- run with `python tools/test_skill_ci_gates.py` (no pytest).
"""
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest import mock

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


def _rmtree(path) -> None:
    """git writes object files read-only, which rmtree cannot unlink on Windows -- with
    ignore_errors=True every git-backed fixture leaked silently into %TEMP%. Clear the bit and
    retry; still best-effort, so a locked file never fails a test. (Same helper as
    tools/test_catch_up_main.py.)"""
    def _retry(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:  # onexc can also hand over os.open/os.close
            pass
    shutil.rmtree(path, onexc=_retry)


class TempRepo(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def tearDown(self):
        _rmtree(self.root)


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

    def test_marker_inside_docstring_does_not_exclude(self):
        _skill(self.root, 'a', files={'tests/test_a.py': '"""Notes.\nCI_EXCLUDE = "x"\n"""\n'})
        self.assertEqual(g.suite_coverage(self.root), (['a/tests/test_a.py'], []))

    def test_empty_triple_quoted_reason_is_an_error(self):
        _skill(self.root, 'a', files={'tests/test_a.py': 'CI_EXCLUDE = """"""\n'})
        files, errors = g.suite_coverage(self.root)
        self.assertEqual(files, [])
        self.assertTrue(any('empty reason' in e for e in errors), errors)

    def test_conditional_expression_marker_stays_gated(self):
        _skill(self.root, 'a', files={'tests/test_a.py': 'CI_EXCLUDE = "x" if False else ""\n'})
        self.assertEqual(g.suite_coverage(self.root), (['a/tests/test_a.py'], []))

    def test_adjacent_string_concat_marker_uses_full_value(self):
        _skill(self.root, 'a', files={'tests/test_a.py': 'CI_EXCLUDE = "" ""\n'})
        files, errors = g.suite_coverage(self.root)
        self.assertEqual(files, [])
        self.assertTrue(any('empty reason' in e for e in errors), errors)

    def test_trailing_comment_marker_excludes_with_reason(self):
        _skill(self.root, 'a', files={'tests/test_a.py': 'CI_EXCLUDE = "why"  # note\n'})
        self.assertEqual(g.suite_coverage(self.root), ([], []))
        self.assertEqual(g.excluded_suites(self.root), {'a/tests/test_a.py': 'why'})

    def test_annotated_and_non_str_and_multi_target_markers_stay_gated(self):
        for i, src in enumerate(['CI_EXCLUDE: str = "x"\n', 'CI_EXCLUDE = 5\n',
                                 'CI_EXCLUDE = other = "x"\n']):
            _skill(self.root, f's{i}', files={'tests/test_a.py': src})
        files, errors = g.suite_coverage(self.root)
        self.assertEqual(files, [f's{i}/tests/test_a.py' for i in range(3)])
        self.assertEqual(errors, [])

    def test_syntax_error_file_stays_gated(self):
        _skill(self.root, 'a', files={'tests/test_a.py': 'CI_EXCLUDE = "x"\ndef (:\n'})
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


class VanishedSuites(unittest.TestCase):
    BASE = {'a/tests/test_a.py', 'b/test_b.py'}

    def test_unchanged_has_no_error(self):
        self.assertEqual(g.vanished_suites(self.BASE, set(self.BASE), set(), set()), [])

    def test_additions_are_fine(self):
        self.assertEqual(g.vanished_suites(self.BASE, self.BASE | {'c/test_c.py'}, set(), set()), [])

    def test_rename_is_reported(self):
        head = {'a/tests/a_test.py', 'b/test_b.py'}
        errs = g.vanished_suites(self.BASE, head, set(), set())
        self.assertEqual(len(errs), 1)
        self.assertIn('a/tests/test_a.py', errs[0])

    def test_delete_is_reported(self):
        errs = g.vanished_suites(self.BASE, {'b/test_b.py'}, set(), set())
        self.assertEqual(len(errs), 1)
        self.assertIn('a/tests/test_a.py', errs[0])

    def test_archived_move_is_allowed(self):
        head = {'b/test_b.py'}
        self.assertEqual(g.vanished_suites(self.BASE, head, {'_archive/a/tests/test_a.py'}, set()), [])
        self.assertEqual(g.vanished_suites(self.BASE, head, {'_archive/2026-11/a/tests/test_a.py'}, set()), [])

    def test_archive_path_with_different_suffix_does_not_count(self):
        errs = g.vanished_suites(self.BASE, {'b/test_b.py'}, {'_archive/xa/tests/test_a.py'}, set())
        self.assertEqual(len(errs), 1)

    def test_retired_dated_archive_form_is_allowed(self):
        head = {'b/test_b.py'}
        self.assertEqual(g.vanished_suites(
            self.BASE, head, {'_archive/a_retired-2026-11-05/tests/test_a.py'}, set()), [])

    def test_malformed_retired_suffix_does_not_count(self):
        errs = g.vanished_suites(
            self.BASE, {'b/test_b.py'}, {'_archive/a_retired-2026-1-5/tests/test_a.py'}, set())
        self.assertEqual(len(errs), 1)

    def test_prefix_sibling_archive_dir_does_not_count(self):
        errs = g.vanished_suites(self.BASE, {'b/test_b.py'}, {'_archive/ab/tests/test_a.py'}, set())
        self.assertEqual(len(errs), 1)

    def test_declared_removed_is_allowed(self):
        self.assertEqual(g.vanished_suites(self.BASE, {'b/test_b.py'}, set(), {'a/tests/test_a.py'}), [])

    def test_report_labels_excused_paths(self):
        errs, excused = g.suite_continuity_report(
            {'a/tests/test_a.py', 'b/test_b.py', 'c/test_c.py'}, {'c/test_c.py'},
            {'_archive/a_retired-2026-11-05/tests/test_a.py'}, {'b/test_b.py'})
        self.assertEqual(errs, [])
        self.assertEqual(excused, {'a/tests/test_a.py': 'archive', 'b/test_b.py': 'Suite-Removed'})


class SuiteContinuityGit(TempRepo):
    def git(self, *a):
        return subprocess.run(
            ['git', '-C', str(self.root), '-c', 'user.name=t', '-c', 'user.email=t@t',
             '-c', 'core.hooksPath=/dev/null', *a],
            capture_output=True, text=True, check=True).stdout.strip()

    def build(self, trailer: str = ''):
        self.git('init', '-q')
        _skill(self.root, 'a', files={'tests/test_a.py': ''})
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        base = self.git('rev-parse', 'HEAD')
        (self.root / 'a' / 'SKILL.md').unlink()
        self.git('add', '-A')
        self.git('commit', '-q', '-m', 'drop skill md' + (f'\n\n{trailer}' if trailer else ''))
        return base

    def run_cmd(self, base):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = g.cmd_suite_continuity(base, repo=self.root)
        return rc, out.getvalue(), err.getvalue()

    def test_base_suite_files_reads_base_tree(self):
        base = self.build()
        self.assertEqual(g.base_suite_files(base, self.root), {'a/tests/test_a.py'})

    def test_deleted_skill_md_is_reported(self):
        base = self.build()
        rc, out, err = self.run_cmd(base)
        self.assertEqual(rc, 1, (out, err))
        self.assertIn('a/tests/test_a.py', err)

    def test_suite_removed_trailer_suppresses(self):
        base = self.build('Suite-Removed: a/tests/test_a.py')
        self.assertEqual(g.declared_removed_suites(base, self.root), {'a/tests/test_a.py'})
        rc, out, err = self.run_cmd(base)
        self.assertEqual(rc, 0, (out, err))
        self.assertIn('excused: a/tests/test_a.py (Suite-Removed)', out)
        self.assertNotIn('all present', out)

    def test_preexisting_archive_copy_does_not_excuse_deletion(self):
        self.git('init', '-q')
        _skill(self.root, 'a', files={'tests/test_a.py': ''})
        old = self.root / '_archive' / 'old' / 'a' / 'tests'
        old.mkdir(parents=True)
        (old / 'test_a.py').write_text('', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        base = self.git('rev-parse', 'HEAD')
        self.git('rm', '-q', 'a/tests/test_a.py')
        self.git('commit', '-q', '-m', 'delete suite')
        rc, out, err = self.run_cmd(base)
        self.assertEqual(rc, 1, (out, err))
        self.assertIn('a/tests/test_a.py', err)

    def test_move_into_archive_in_this_range_passes(self):
        self.git('init', '-q')
        _skill(self.root, 'a', files={'tests/test_a.py': ''})
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        base = self.git('rev-parse', 'HEAD')
        dest = self.root / '_archive' / '2026-11-05' / 'a' / 'tests'
        dest.mkdir(parents=True)
        self.git('mv', 'a/tests/test_a.py', '_archive/2026-11-05/a/tests/test_a.py')
        self.git('commit', '-q', '-m', 'archive suite')
        rc, out, err = self.run_cmd(base)
        self.assertEqual(rc, 0, (out, err))
        self.assertIn('excused: a/tests/test_a.py (archive)', out)

    def _archive_move(self, dest_rel: str):
        self.git('init', '-q')
        _skill(self.root, 'a', files={'tests/test_a.py': ''})
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        base = self.git('rev-parse', 'HEAD')
        (self.root / '_archive').mkdir()
        self.git('mv', 'a', dest_rel)
        self.git('commit', '-q', '-m', 'retire a')
        return self.run_cmd(base)

    def test_standard_retirement_form_passes(self):
        rc, out, err = self._archive_move('_archive/a_retired-2026-11-05')
        self.assertEqual(rc, 0, (out, err))
        self.assertIn('excused: a/tests/test_a.py (archive)', out)

    def test_plain_archive_move_passes(self):
        rc, out, err = self._archive_move('_archive/a')
        self.assertEqual(rc, 0, (out, err))

    def test_malformed_retired_suffix_move_fails(self):
        rc, out, err = self._archive_move('_archive/a_retired-2026-1-5')
        self.assertEqual(rc, 1, (out, err))

    def test_prefix_sibling_archive_move_fails(self):
        rc, out, err = self._archive_move('_archive/ab')
        self.assertEqual(rc, 1, (out, err))

    def test_head_skip_does_not_hide_base_suites(self):
        self.git('init', '-q')
        _skill(self.root, 'a', files={'tests/test_a.py': ''})
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        base = self.git('rev-parse', 'HEAD')
        self.git('commit', '-q', '--allow-empty', '-m', 'head adds a to SKIP')
        with mock.patch.object(g.package_skills, 'SKIP', set(g.package_skills.SKIP) | {'a'}):
            self.assertEqual(g.base_suite_files(base, self.root), {'a/tests/test_a.py'})
            rc, out, err = self.run_cmd(base)
        self.assertEqual(rc, 1, (out, err))
        self.assertIn('a/tests/test_a.py', err)

    def test_rename_of_preexisting_archive_dir_does_not_excuse_deletion(self):
        # With the `-- _archive/` pathspec a rename from OUTSIDE _archive/ shows as A, never R;
        # an R therefore only means a copy that already lived under _archive/ at base.
        self.git('init', '-q')
        _skill(self.root, 'a', files={'tests/test_a.py': ''})
        old = self.root / '_archive' / 'old' / 'a' / 'tests'
        old.mkdir(parents=True)
        (old / 'test_a.py').write_text('', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        base = self.git('rev-parse', 'HEAD')
        self.git('mv', '_archive/old', '_archive/new')
        self.git('rm', '-q', 'a/tests/test_a.py')
        self.git('commit', '-q', '-m', 'rename archive dir and delete suite')
        rc, out, err = self.run_cmd(base)
        self.assertEqual(rc, 1, (out, err))
        self.assertIn('a/tests/test_a.py', err)

    def _commit_package_skills(self, skip_literal: str, msg: str):
        (self.root / 'tools').mkdir(exist_ok=True)
        (self.root / 'tools' / 'package_skills.py').write_text(
            f"SKIP = {skip_literal}\n", encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', msg)
        return self.git('rev-parse', 'HEAD')

    def test_base_skip_filters_base_suites(self):
        # Once a SKIP addition (with its Suite-Removed trailer) has merged, later PRs diffed
        # against that base must not report the skipped skill's suites as vanished.
        self.git('init', '-q')
        _skill(self.root, 'a', files={'tests/test_a.py': ''})
        self._commit_package_skills("{'_archive', 'tools', '.git'}", 'base 0')
        p1 = self._commit_package_skills(
            "{'_archive', 'tools', '.git', 'a'}", 'skip a\n\nSuite-Removed: a/tests/test_a.py')
        (self.root / 'README.md').write_text('x\n', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'readme only')
        # head's imported SKIP also carries 'a' (as the real module would after P1)
        with mock.patch.object(g.package_skills, 'SKIP', set(g.package_skills.SKIP) | {'a'}):
            self.assertEqual(g.base_suite_files(p1, self.root), set())
            rc, out, err = self.run_cmd(p1)
        self.assertEqual(rc, 0, (out, err))

    def test_unreadable_base_skip_falls_back_to_default_set(self):
        self.git('init', '-q')
        _skill(self.root, 'a', files={'tests/test_a.py': ''})
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'no package_skills at base')
        base = self.git('rev-parse', 'HEAD')
        self.assertEqual(g.base_suite_files(base, self.root), {'a/tests/test_a.py'})
        self.root.joinpath('tools').mkdir()
        self.root.joinpath('tools', 'package_skills.py').write_text('SKIP = (((\n', encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'unparseable')
        self.assertEqual(g.base_suite_files(self.git('rev-parse', 'HEAD'), self.root),
                         {'a/tests/test_a.py'})

    def test_base_skip_uses_last_top_level_assignment(self):
        self.git('init', '-q')
        sha = self._commit_package_skills("{'x'}\nSKIP = {'x', 'y'}", 'double assign')
        self.assertEqual(g.base_skip_set(sha, self.root), {'x', 'y'})

    def _consistency_case(self, body: str, imported: set):
        self.git('init', '-q')
        _skill(self.root, 'a', files={'tests/test_a.py': ''})
        (self.root / 'tools').mkdir()
        (self.root / 'tools' / 'package_skills.py').write_text(body, encoding='utf-8')
        self.git('add', '.')
        self.git('commit', '-q', '-m', 'base')
        base = self.git('rev-parse', 'HEAD')
        self.git('commit', '-q', '--allow-empty', '-m', 'head')
        with mock.patch.object(g.package_skills, 'SKIP', imported):
            return self.run_cmd(base)

    def test_skip_mutated_with_add_fails_self_consistency(self):
        rc, out, err = self._consistency_case("SKIP = {'x'}\nSKIP.add('y')\n", {'x', 'y'})
        self.assertEqual(rc, 1, (out, err))
        self.assertIn('SKIP must be a single top-level literal set', err)

    def test_skip_assigned_twice_fails_self_consistency(self):
        # The runtime value is the first assignment's; the AST parse takes the last. They disagree.
        rc, out, err = self._consistency_case("SKIP = {'x'}\nSKIP = {'x', 'z'}\n", {'x'})
        self.assertEqual(rc, 1, (out, err))
        self.assertIn('SKIP must be a single top-level literal set', err)

    def test_consistent_skip_passes(self):
        rc, out, err = self._consistency_case("SKIP = {'x'}\n", {'x'})
        self.assertEqual(rc, 0, (out, err))

    def _failing_git(self, failing: str):
        real = g._git

        def fake(*args, repo=g.REPO):
            if args and args[0] == failing:
                return subprocess.CompletedProcess(['git', *args], 128, '', 'fatal: boom')
            return real(*args, repo=repo)
        return fake

    def test_ls_tree_failure_is_rc2_not_pass(self):
        base = self.build()
        with mock.patch.object(g, '_git', self._failing_git('ls-tree')):
            rc, out, err = self.run_cmd(base)
        self.assertEqual(rc, 2, (out, err))
        self.assertIn('ls-tree', err)

    def test_archive_diff_failure_is_rc2_not_vanished_report(self):
        base = self.build()
        with mock.patch.object(g, '_git', self._failing_git('diff')):
            rc, out, err = self.run_cmd(base)
        self.assertEqual(rc, 2, (out, err))
        self.assertIn('git diff', err)
        self.assertNotIn('no longer discovered', err)

    def test_git_log_failure_is_rc2(self):
        base = self.build()
        with mock.patch.object(g, '_git', self._failing_git('log')):
            rc, out, err = self.run_cmd(base)
        self.assertEqual(rc, 2, (out, err))
        self.assertIn('git log', err)

    def test_bad_base_is_usage_error(self):
        self.build()
        self.assertEqual(self.run_cmd('no-such-ref-xyz')[0], 2)


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
