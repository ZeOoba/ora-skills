"""Tests for lint_skill_dollar_args (2026-11-14).

A dollar sign followed by a digit in a SKILL.md body is replaced by a skill-argument token when
the skill is invoked with arguments. The fixer rewrites money figures to "USD n" and leaves code
(fenced blocks, inline spans, spreadsheet references) and frontmatter alone.

Run: python tools/test_lint_skill_dollar_args.py
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lint_skill_dollar_args as L  # noqa: E402

D = "$"  # built up so this file never holds a literal dollar-digit pair the reader could mistake


class FixBody(unittest.TestCase):
    def test_money_rewritten(self):
        self.assertEqual(L.fix_body("floor " + D + "4.00/SF and " + D + "2,450,000\n"),
                         "floor USD 4.00/SF and USD 2,450,000\n")

    def test_inline_code_left_alone(self):
        line = "label `GL limits " + D + "2m/4m` and " + D + "8 TI\n"
        self.assertEqual(L.fix_body(line), "label `GL limits " + D + "2m/4m` and USD 8 TI\n")

    def test_fenced_code_left_alone(self):
        body = "```\nx = " + D + "5\n```\n" + D + "5 cash\n"
        self.assertEqual(L.fix_body(body), "```\nx = " + D + "5\n```\nUSD 5 cash\n")

    def test_spreadsheet_reference_left_alone(self):
        line = "=B5*(1+" + D + "B" + D + "6)\n"
        self.assertEqual(L.fix_body(line), line)

    def test_no_dollar_unchanged(self):
        self.assertEqual(L.fix_body("USD 4.00/SF\n"), "USD 4.00/SF\n")


class SplitFrontmatter(unittest.TestCase):
    def test_frontmatter_separated(self):
        fm, body = L.split_frontmatter("---\nname: x\n---\n\nbody " + D + "1\n")
        self.assertEqual(fm, "---\nname: x\n---\n")
        self.assertEqual(body, "\nbody " + D + "1\n")

    def test_no_frontmatter(self):
        self.assertEqual(L.split_frontmatter("body\n"), ("", "body\n"))


class ScanAndFix(unittest.TestCase):
    def _skill(self, root, name, text):
        d = Path(root) / name
        d.mkdir()
        (d / "SKILL.md").write_text(text, encoding="utf-8")
        return d / "SKILL.md"

    def test_scan_counts_and_skips_archive_depth(self):
        with tempfile.TemporaryDirectory() as root:
            self._skill(root, "a", "---\nname: a\n---\n" + D + "4.00 and " + D + "8\n")
            self._skill(root, "b", "---\nname: b\n---\nclean\n")
            arch = Path(root) / "_archive" / "old"
            arch.mkdir(parents=True)
            (arch / "SKILL.md").write_text(D + "9\n", encoding="utf-8")
            hits = L.scan(Path(root))
            self.assertEqual({p.parent.name: n for p, n in hits.items()}, {"a": (2, 0)})

    def test_fix_is_idempotent_and_keeps_frontmatter(self):
        with tempfile.TemporaryDirectory() as root:
            text = "---\nname: a\ndescription: costs " + D + "1\n---\n" + D + "4.00/SF\n"
            p = self._skill(root, "a", text)
            fm, body = L.split_frontmatter(text)
            p.write_text(fm + L.fix_body(body), encoding="utf-8")
            once = p.read_text(encoding="utf-8")
            self.assertTrue(once.endswith("USD 4.00/SF\n"))
            self.assertIn("costs " + D + "1", once)
            fm2, body2 = L.split_frontmatter(once)
            self.assertEqual(fm2 + L.fix_body(body2), once)


if __name__ == "__main__":
    unittest.main()
