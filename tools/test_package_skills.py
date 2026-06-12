#!/usr/bin/env python3
"""Regression tests for package_skills.check_named_counts.

Stdlib only — run with `python tools/test_package_skills.py` (no pytest).
Guards the named-count drift gate, including the 2026-06-11 follow-up that
taught it to count Markdown TABLE rows (e.g. loi-generation/references/
qc-gate.md presents its gate as a numbered table, not a checkbox list).
"""
import io
import unittest
from contextlib import redirect_stdout

from package_skills import check_named_counts


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


if __name__ == '__main__':
    unittest.main(verbosity=2)
