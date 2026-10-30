"""Regression tests for the 2026-10-30 cache-ahead false positives.

Two skills read as "installed copy is newer than the repo" when the installed copies
were in fact OLDER, which pointed toward committing them back (a downgrade):
  * acquisition-underwriting-eval-harness -> REPO-MISSING on 15 git-ignored runtime
    files (runs/*.json, .pytest_cache) the harness had written into its installed dir.
  * county-parcel-screen -> DIVERGENT because the platform re-serializes SKILL.md
    frontmatter on install: it flattens a `description: >` block into one
    double-quoted line, escaping inner quotes and the clipped trailing newline.
Also: reimport_correlate precheck read a block-scalar description as 1/1024 while
the packager read 641/1024.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import package_skills as ps  # noqa: E402
import reimport_correlate as rc  # noqa: E402
import repo_first_check as rfc  # noqa: E402
from skill_md_normalize import normalize_skill_md_text as N  # noqa: E402
from test_repo_first_check import FixtureTestCase, _commit, _write  # noqa: E402

BLOCK = ("---\nname: demo-skill\ndescription: >\n  Use when the user says \"go\": run it,\n"
         "  then report.\nlicense: X\n---\n\n# demo\nbody\n")
# Exactly what the platform stored for county-parcel-screen: quoted name, the block
# flattened to one double-quoted line, inner quotes escaped, trailing \n kept as an escape.
FLAT = ('---\nname: "demo-skill"\ndescription: "Use when the user says \\"go\\": run it, then report.\\n"\n'
        'license: X\n---\n\n# demo\nbody\n')


class NormalizerTreatsSerializationAsSame(unittest.TestCase):
    def test_block_scalar_equals_platform_flattened_form(self):
        self.assertEqual(N(BLOCK), N(FLAT))

    def test_changed_word_still_differs(self):
        self.assertNotEqual(N(BLOCK), N(FLAT.replace("then report", "then stop")))

    def test_literal_backslash_n_is_not_a_newline(self):
        a = '---\nname: x\ndescription: "path a\\\\nb"\n---\nbody\n'   # YAML: a backslash then n
        b = '---\nname: x\ndescription: path a\nb\n---\nbody\n'
        self.assertNotEqual(N(a), N(b))

    def test_literal_block_keeps_line_breaks(self):
        lit = '---\nname: x\ndescription: |\n  step 1\n  step 2\n---\nbody\n'
        one = '---\nname: x\ndescription: step 1 step 2\n---\nbody\n'
        self.assertNotEqual(N(lit), N(one))

    def test_only_description_is_folded_or_collapsed(self):
        a = '---\nname: x\nmetadata: >\n  owner: a\n---\nbody\n'
        b = '---\nname: x\nmetadata: owner: a\n---\nbody\n'
        self.assertNotEqual(N(a), N(b))
        self.assertNotEqual(N('---\nname: x\nlicense: "a  b"\n---\nb\n'), N('---\nname: x\nlicense: a b\n---\nb\n'))

    def test_body_text_untouched(self):
        self.assertNotEqual(N(BLOCK), N(BLOCK.replace("body\n", "body  changed\n")))


class ClassifyIgnoresRuntimeStateAndFormatting(FixtureTestCase):
    def test_git_ignored_cache_only_files_are_skipped(self):
        _commit(self.repo, '.gitignore', 'demo-skill/runs/\n.pytest_cache/\n', 'ignore')
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'runs' / '2026-10-30T000000Z_poll.json', '{}\n')
        _write(self.cache / 'demo-skill' / '.pytest_cache' / 'README.md', 'x\n')
        verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)
        self.assertEqual(verdict, 'IN-SYNC')
        # excused files stay VISIBLE as RUNTIME-STATE, never silently dropped
        self.assertEqual(sorted(per_file), [('.pytest_cache/README.md', 'RUNTIME-STATE'), ('SKILL.md', 'IN-SYNC'),
                                            ('runs/2026-10-30T000000Z_poll.json', 'RUNTIME-STATE')])

    def test_ignored_file_outside_runtime_dirs_is_still_flagged(self):
        # a broad ignore rule must not excuse a genuinely new reference file (review 2026-10-30)
        _commit(self.repo, '.gitignore', '*.xlsx\ndata/\n', 'ignore')
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'references' / 'rates.xlsx', 'x\n')
        verdict, _ = rfc.classify_skill('demo-skill', self.repo, self.cache)
        self.assertEqual(verdict, 'REPO-MISSING')

    def test_unignored_cache_only_file_is_still_flagged(self):
        _commit(self.repo, '.gitignore', 'demo-skill/runs/\n', 'ignore')
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'new_tool.py', 'print(1)\n')
        verdict, _ = rfc.classify_skill('demo-skill', self.repo, self.cache)
        self.assertEqual(verdict, 'REPO-MISSING')

    def test_platform_flattened_frontmatter_reads_in_sync(self):
        _commit(self.repo, 'demo-skill/SKILL.md', BLOCK, 'init')
        _write(self.cache / 'demo-skill' / 'SKILL.md', FLAT)
        verdict, _ = rfc.classify_skill('demo-skill', self.repo, self.cache)
        self.assertEqual(verdict, 'IN-SYNC')

    def test_older_flattened_copy_reads_repo_ahead_not_divergent(self):
        _commit(self.repo, 'demo-skill/SKILL.md', BLOCK, 'v1')
        _commit(self.repo, 'demo-skill/SKILL.md', BLOCK.replace("body\n", "body v2\n"), 'v2')
        _write(self.cache / 'demo-skill' / 'SKILL.md', FLAT)
        verdict, _ = rfc.classify_skill('demo-skill', self.repo, self.cache)
        self.assertEqual(verdict, 'REPO-AHEAD')


class PrecheckMeasuresDescriptionLikeThePackager(unittest.TestCase):
    def test_block_scalar_length_matches_packager(self):
        fm = BLOCK.split('---', 2)[1]
        expect = len(ps.frontmatter_description(fm))
        self.assertGreater(expect, 1)
        self.assertEqual(len(rc._fm_fields(BLOCK)[1]), expect)

    def test_quoted_and_plain_unchanged(self):
        for fmline, val in (('description: "abc"', 'abc'), ('description: abc', 'abc')):
            text = f'---\nname: demo-skill\n{fmline}\n---\nbody\n'
            self.assertEqual(rc._fm_fields(text), ('demo-skill', val))


if __name__ == '__main__':
    unittest.main()
