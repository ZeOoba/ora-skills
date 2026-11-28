"""Tests for tools/lint_skill_dollar_args.py (stdlib unittest; synthetic fixtures only)."""
import contextlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lint_skill_dollar_args as L  # noqa: E402

FM = '---\nname: "x"\ndescription: "Use when x."\n---\n'


def _run(root, *args):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = L.main([str(root), *args])
    return code, out.getvalue()


class FixBody(unittest.TestCase):
    def test_money_rewritten(self):
        self.assertEqual(L.fix_body("floor $4.00/SF, ask $2,500,000, cap $1.25M\n"),
                         "floor USD 4.00/SF, ask USD 2,500,000, cap USD 1.25M\n")

    def test_negative_and_parenthesised(self):
        self.assertEqual(L.fix_body("(-$5) and ($3K)\n"), "(-USD 5) and (USD 3K)\n")

    def test_money_glued_to_a_word_gets_a_space(self):
        self.assertEqual(L.fix_body("Amortizing$16,304.46 and Only$125.23\n"),
                         "Amortizing USD 16,304.46 and Only USD 125.23\n")

    def test_spreadsheet_references_left_alone(self):
        for ref in ("=$B$5*2", "=SUM(A$1:A$9)", "=$AB$12", "=C$3", "Inputs!$B$38", "range B$2:B$9"):
            self.assertEqual(L.fix_body(ref + "\n"), ref + "\n", ref)

    def test_capitals_before_money_are_not_cell_references(self):
        self.assertEqual(L.fix_body("Price US$5M deal; TI$4/SF; NNN$8.08\n"),
                         "Price USD 5M deal; TI USD 4/SF; NNN USD 8.08\n")
        for prose, fixed in (("Allowance (TI$4/SF) typical", "Allowance (TI USD 4/SF) typical"),
                             ("LC/TI$4/SF", "LC/TI USD 4/SF"),
                             ("NNN-CAM$1.25/SF", "NNN-CAM USD 1.25/SF"),
                             ("Rent (NNN$8.08), CAM+TI$2", "Rent (NNN USD 8.08), CAM+TI USD 2")):
            self.assertEqual(L.fix_body(prose + "\n"), fixed + "\n", prose)

    def test_code_fence_and_inline_span_left_alone(self):
        body = "```\nx = '$4.00'\n```\nsee `$8.00/SF` here, prose $9\n~~~\nrent $4.00\n~~~\n"
        self.assertEqual(L.fix_body(body),
                         "```\nx = '$4.00'\n```\nsee `$8.00/SF` here, prose USD 9\n~~~\nrent $4.00\n~~~\n")

    def test_no_digit_after_dollar_untouched(self):
        self.assertEqual(L.fix_body("$ARGUMENTS and $x and US$\n"), "$ARGUMENTS and $x and US$\n")

    def test_crlf_preserved(self):
        self.assertEqual(L.fix_body("a $1\r\nb\r\n"), "a USD 1\r\nb\r\n")


    def test_edge_inputs_not_mangled(self):  # merge-gate F-013 / F-020
        D = "$"
        cases = {
            "\\" + D + "5 literal": "\\" + D + "5 literal",                 # escaped dollar sign: left
            "fee A" + D + "5M": "fee AUD 5M",                               # non-US currency keeps its code
            "NZ" + D + "2 and HK" + D + "3": "NZD 2 and HKD 3",
            "x ``a " + D + "5 b`` y": "x ``a " + D + "5 b`` y",             # double-backtick code span
            "rows " + D + "5:" + D + "9": "rows " + D + "5:" + D + "9",     # whole-row range
            "=A1+B" + D + "2": "=A1+B" + D + "2",                           # formula context via '+'
            "=SUM(A1,B" + D + "2)": "=SUM(A1,B" + D + "2)",                 # via ','
            "=A1-B" + D + "2": "=A1-B" + D + "2",                           # via '-'
            "=ABCD" + D + "5": "=ABCD USD 5",                               # 4 capitals: not a column
            "Sheet!B" + D + "5": "Sheet!B" + D + "5",                       # via '!'
            "(TI" + D + "4/SF)": "(TI USD 4/SF)",                           # prose: rewritten
            "prose " + D + "0 fee": "prose USD 0 fee",
            "C" + D + "5 and S" + D + "5": "CAD 5 and SGD 5",
            "EPIC" + D + "5M": "EPIC USD 5M",                               # glued capitals: not a currency
            "MOS" + D + "3": "MOS USD 3",
            "x ``a " + D + "5 b `c` y": "x ``a USD 5 b `c` y",              # unmatched `` is literal text
        }
        for src, want in cases.items():
            self.assertEqual(L.fix_body(src + "\n"), want + "\n", src)

    def test_mismatched_fence_marker_does_not_close(self):
        D = "$"
        body = "```\n~~~\nx " + D + "4\n```\nafter " + D + "4\n"
        self.assertEqual(L.fix_body(body), "```\n~~~\nx " + D + "4\n```\nafter USD 4\n")
        body = "  ~~~\nx " + D + "4\n  ~~~\n"                     # indented fence is still a fence
        self.assertEqual(L.fix_body(body), body)


class Frontmatter(unittest.TestCase):
    def test_split(self):
        fm, body = L.split_frontmatter(FM + "# T\n$5\n")
        self.assertEqual(fm, FM)
        self.assertEqual(body, "# T\n$5\n")

    def test_no_frontmatter(self):
        self.assertEqual(L.split_frontmatter("# T\n"), ("", "# T\n"))


class Cli(unittest.TestCase):
    def _tree(self, files):
        d = Path(tempfile.mkdtemp())
        for rel, text in files.items():
            p = d / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(text.encode("utf-8"))
        return d

    def test_report_fails_then_fix_passes_and_is_idempotent(self):
        d = self._tree({"a/SKILL.md": FM + "# A\nTI $8.00/SF\r\n", "b/SKILL.md": FM + "# B\nno money\n"})
        code, out = _run(d)
        self.assertEqual(code, 1)
        self.assertIn("FAIL", out)
        code, out = _run(d, "--fix")
        self.assertEqual(code, 0, out)
        self.assertIn("FIXED", out)
        self.assertIn("0 files, 0 body occurrences", out)      # the post-fix rescan, not the pre-fix scan
        self.assertNotIn("WARN", out)
        self.assertEqual((d / "a/SKILL.md").read_bytes().decode(), FM + "# A\nTI USD 8.00/SF\r\n")
        before = (d / "a/SKILL.md").read_bytes()
        _run(d, "--fix")
        self.assertEqual((d / "a/SKILL.md").read_bytes(), before)

    def test_code_only_is_warn_exit_zero(self):
        d = self._tree({"a/SKILL.md": FM + "# A\n`$4.00` and =$B$5\n"})
        code, out = _run(d)
        self.assertEqual(code, 0, out)
        self.assertIn("WARN(code-only)", out)

    def test_glued_money_is_fail_not_code_only(self):
        d = self._tree({"a/SKILL.md": FM + "# A\nInt Only$1,365.00\n"})
        code, out = _run(d)
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)

    def test_dry_run_writes_nothing(self):
        d = self._tree({"a/SKILL.md": FM + "# A\n$4\n"})
        code, out = _run(d, "--fix", "--dry-run")
        self.assertIn("+USD 4", out)
        self.assertEqual((d / "a/SKILL.md").read_text(encoding="utf-8"), FM + "# A\n$4\n")

    def test_vendor_and_nested_skills_skipped(self):
        d = self._tree({"xlsx/SKILL.md": FM + "$5\n", "_archive/old/SKILL.md": FM + "$5\n"})
        code, _ = _run(d)
        self.assertEqual(code, 0)

    def test_frontmatter_figure_is_reported_not_rewritten(self):
        fm = '---\nname: "x"\ndescription: "Use when sub-$10M."\n---\n'
        d = self._tree({"a/SKILL.md": fm + "# A\n"})
        code, out = _run(d, "--fix")
        self.assertEqual((d / "a/SKILL.md").read_text(encoding="utf-8"), fm + "# A\n")
        self.assertIn("1 in frontmatter", out)

    def _git(self, d, *args):
        env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t",
                   GIT_COMMITTER_EMAIL="t@t")
        subprocess.run(["git", *args], cwd=d, check=True, capture_output=True, env=env)

    def test_fix_skips_uncommitted_files_unless_asked(self):  # merge-gate F-011
        d = self._tree({"a/SKILL.md": FM + "# A\nok\n", "b/SKILL.md": FM + "# B\nTI $8/SF\n"})
        self._git(d, "init", "-q")
        self._git(d, "add", "a/SKILL.md", "b/SKILL.md")
        self._git(d, "commit", "-qm", "base")
        (d / "a/SKILL.md").write_text(FM + "# A\nWIP from another session: budget $750K\n", encoding="utf-8")
        code, out = _run(d, "--fix")
        self.assertEqual(code, 1, out)
        self.assertIn("SKIPPED(uncommitted changes)", out)
        self.assertIn("budget $750K", (d / "a/SKILL.md").read_text(encoding="utf-8"))   # untouched
        self.assertIn("TI USD 8/SF", (d / "b/SKILL.md").read_text(encoding="utf-8"))   # committed: fixed
        code, out = _run(d, "--fix", "--include-dirty")
        self.assertEqual(code, 0, out)
        self.assertIn("budget USD 750K", (d / "a/SKILL.md").read_text(encoding="utf-8"))

    def test_fix_refuses_a_file_changed_during_the_fix(self):  # merge-gate F-012
        d = self._tree({"a/SKILL.md": FM + "# A\nTI $8/SF\n"})
        real = L.fix_body

        def racing(body):
            (d / "a/SKILL.md").write_text(FM + "# A\nTI $8/SF\nB's line\n", encoding="utf-8")
            return real(body)
        L.fix_body = racing
        try:
            code, out = _run(d, "--fix")
        finally:
            L.fix_body = real
        self.assertEqual(code, 1, out)
        self.assertIn("SKIPPED(changed during fix)", out)
        self.assertIn("B's line", (d / "a/SKILL.md").read_text(encoding="utf-8"))
        self.assertEqual([p.name for p in (d / "a").iterdir()], ["SKILL.md"])   # no temp file left

    def test_fix_keeps_file_mode(self):  # mkstemp creates 0600; the rewritten SKILL.md must keep its mode
        d = self._tree({"a/SKILL.md": FM + "# A\nTI $8/SF\n"})
        os.chmod(d / "a/SKILL.md", 0o644)
        code, out = _run(d, "--fix")
        self.assertEqual(code, 0, out)
        self.assertEqual((d / "a/SKILL.md").stat().st_mode & 0o777, 0o644)

    def test_dirty_check_takes_no_index_lock(self):
        from unittest import mock
        seen = []

        def fake_run(argv, **kw):
            seen.append(argv)
            return subprocess.CompletedProcess(argv, 0, "", "")
        with mock.patch.object(L.subprocess, "run", fake_run):
            L._dirty(Path(__file__))
        self.assertEqual(seen[0][:3], ["git", "--no-optional-locks", "status"])

    def test_temp_file_is_ignored_and_never_packaged(self):
        root = Path(__file__).resolve().parent.parent
        self.assertIn(".lintfix-*.tmp", (root / ".gitignore").read_text(encoding="utf-8").splitlines())
        sys.path.insert(0, str(root / "tools"))
        import package_skills
        self.assertFalse(package_skills.is_bundled(".lintfix-abc123.tmp"))
        self.assertTrue(package_skills.is_bundled("SKILL.md"))


    def test_missing_root(self):
        self.assertEqual(L.main([str(Path(tempfile.mkdtemp()) / "nope")]), 2)


class RepoTree(unittest.TestCase):
    def test_repo_skill_bodies_have_no_rewritable_dollar_figures(self):  # the lint, in the local gate (F-015)
        root = Path(__file__).resolve().parent.parent
        code, out = _run(root)
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
