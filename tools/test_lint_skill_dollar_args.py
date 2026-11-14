"""Tests for tools/lint_skill_dollar_args.py (stdlib unittest; synthetic fixtures only)."""
import contextlib
import io
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
        self.assertEqual(L.fix_body("floor $4.00/SF, ask $2,450,000, cap $1.25M\n"),
                         "floor USD 4.00/SF, ask USD 2,450,000, cap USD 1.25M\n")

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

    def test_missing_root(self):
        self.assertEqual(L.main([str(Path(tempfile.mkdtemp()) / "nope")]), 2)


if __name__ == "__main__":
    unittest.main()
