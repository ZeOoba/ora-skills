"""Public-surface leak test for the RCT replacement-cost table. Run: python tools/test_rct_public_leak.py

ora-skills is PUBLIC. The ratified RCT table (governor-level, Hard Invariant 4) lives only in the gitignored
rct-table.local.json (tools/RCT_TABLE.md). Its figures are still in git history from before 2026-11-13 (no
rewrite approved); this test stops them coming BACK into the tree.

Two layers:
  1. Structural checks that always run (CI included): the real file is gitignored and untracked, no tracked
     file is a non-synthetic RCT table, and the walk solver carries no literal RCT_POINT table.
  2. A value scan that needs the REAL table, which is never committed: $ORA_RCT_TABLE, the repo-root copy, or
     the master copy (same resolution as the packager). Without one it SKIPS and says why (an allowed skip in
     tools/run_suite.sh). It scans every tracked or untracked-but-not-ignored file for any LOW, POINT or HIGH
     figure. It reports file and count only, never a figure.

Never commit hashes of individual values: a plain hash confirms a guess and the history already holds the values.
"""
import json
import math
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import package_skills  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NAME = package_skills.RCT_TABLE_FILE
SELF = Path(__file__).resolve().relative_to(ROOT).as_posix()


def surface_files():
    out = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'],
                         capture_output=True, check=True).stdout.decode('utf-8')
    return sorted({f for f in out.split('\0') if f and (ROOT / f).is_file()})


def read_text(rel):
    data = (ROOT / rel).read_bytes()
    if b'\0' in data:
        return None  # binary (fonts, images); a figure is not meaningfully "in" them
    return data.decode('utf-8', errors='replace')


def figure_regex(n):
    """123.4 matches '123.4' and '123.40' but not '1123.4', '123.45' or '123.401'."""
    whole, frac = f'{n:.2f}'.split('.')
    frac = frac.rstrip('0')
    frac_part = rf'\.{frac}0*' if frac else r'(?:\.0+)?'
    return re.compile(rf'(?<![\d.]){whole}{frac_part}(?!\d)')


def one_decimal_regex(n):
    """The one-decimal rounding of n as a standalone number: 123.45 -> '123.5', not '1123.5' or '123.51'."""
    whole, frac = f'{round(n, 1):.1f}'.split('.')
    return rf'(?<![\d.]){whole}\.{frac}(?!\d)'


def load_real_table():
    src = package_skills.private_dep_path(NAME, ROOT)
    if src is None:
        return None, f'no real RCT table available (${package_skills.RCT_TABLE_ENV}, {NAME} or the master copy)'
    rct = package_skills._rct_module()
    try:
        table = json.loads(src.read_bytes().decode('utf-8-sig'))
    except ValueError:
        raise AssertionError(f'{src} is not JSON')
    if table.get('_synthetic') is True or table.get('rctVersion') == rct.SYNTHETIC_VERSION:
        return None, f'{src} holds the synthetic fixture, not the real table'
    rct.validate(table)
    return table, str(src)


class Structural(unittest.TestCase):
    def test_real_file_is_gitignored_everywhere_it_could_land(self):
        for rel in (NAME, f'acquisition-underwriting/{NAME}', f'parcel-data-recovery/{NAME}'):
            r = subprocess.run(['git', '-C', str(ROOT), 'check-ignore', '-q', rel])
            self.assertEqual(r.returncode, 0, f'{rel} must be gitignored')
        tracked = subprocess.run(['git', '-C', str(ROOT), 'ls-files', f'*{NAME}*'], capture_output=True,
                                 text=True, check=True).stdout.split()
        self.assertEqual(tracked, [], f'{NAME} must never be tracked')

    def test_no_tracked_file_is_a_real_rct_table(self):
        offenders = []
        for rel in surface_files():
            if not rel.endswith('.json'):
                continue
            text = read_text(rel)
            if text is None or '"markdownTable"' not in text:
                continue
            try:
                t = json.loads(text)
            except ValueError:
                offenders.append(rel)
                continue
            if not (isinstance(t, dict) and (t.get('_synthetic') is True)):
                offenders.append(rel)
        self.assertEqual(offenders, [], 'only the synthetic fixture may look like an RCT table in the tree')

    def test_solver_has_no_literal_rct_table(self):
        doctrine = (ROOT / 'acquisition-underwriting/scripts/ora_walk/doctrine.py').read_text(encoding='utf-8')
        self.assertNotRegex(doctrine, r'RCT_POINT\s*=\s*\{', 'RCT POINT figures are runtime config, not source')

    def test_figure_regex(self):
        # Invented figure; never use a real RCT value here (this file is scanned too).
        r = figure_regex(123.4)
        for s in ('123.4', '123.40', '$123.40/SF', '"x": 123.4,'):
            self.assertRegex(s, r)
        for s in ('1123.4', '123.45', '123.401', '23.4'):
            self.assertNotRegex(s, r)
        self.assertRegex('x 200 y', figure_regex(200))
        self.assertRegex('200.00', figure_regex(200))
        self.assertNotRegex('2000', figure_regex(200))
        r1 = re.compile(one_decimal_regex(123.45))  # invented
        for s in ('123.5', '$123.5/SF'):
            self.assertRegex(s, r1)
        for s in ('1123.5', '123.51', '123.4', '12305'):
            self.assertNotRegex(s, r1)


class ValueScan(unittest.TestCase):
    def test_real_figures_appear_nowhere_in_the_tree(self):
        table, source = load_real_table()
        if table is None:
            self.skipTest(source)
        figures = sorted({float(m[k]) for m in table['markets'].values() for k in ('low', 'point', 'high')})
        # One alternation, one pass per file; each figure is its own group, so distinct figures are counted.
        # Rounded forms too (adversarial review 2026-11-13): a one-decimal rounding anywhere, and a whole-dollar
        # rounding written as money ("$N", "$N/SF", "N/SF" at the end of a "$A-N" range).
        ints = sorted({math.floor(f) for f in figures} | {round(f) for f in figures})
        whole = '|'.join(str(i) for i in ints)
        patterns = [figure_regex(f).pattern for f in figures]
        patterns += [one_decimal_regex(f) for f in figures]
        patterns += [rf'\$\s?(?:{whole})(?![\d.,KkMmB])', rf'[–-]\s?\$?(?:{whole})\s?/\s?SF']
        # The escalation parameter (derivation block) as a multiplier and as a percentage. The soft-cost
        # multiplier and reference SF are too common as bare numbers to scan without false positives.
        esc = float(table['derivation']['escalation'])
        pct = f'{(esc - 1) * 100:.2f}'.rstrip('0').rstrip('.')
        patterns += [rf'(?<![\d.]){re.escape(f"{esc:.4f}".rstrip("0"))}(?!\d)', rf'(?<![\d.]){re.escape(pct)}\s?%']
        combined = re.compile('|'.join(f'({p})' for p in patterns))
        findings = []
        for rel in surface_files():
            if rel == SELF:
                continue
            text = read_text(rel)
            if text is None:
                continue
            hit = {m.lastindex for m in combined.finditer(text)}
            if hit:
                findings.append(f'{rel}: {len(hit)} RCT figure pattern(s)')
        self.maxDiff = None
        self.assertEqual(findings, [], f'RCT figures (from {os.path.basename(source)}) are back in the public '
                                       'tree. Remove them; the table lives only in rct-table.local.json.')


if __name__ == '__main__':
    unittest.main()
