import os
import sys
import unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from daycount import VARIANTS, days_30_360


class TestDays30360(unittest.TestCase):
    def test_cross_year_has_year_term(self):
        # Regression for SKILL.md A3 old formula: (m2-m1)*30+(d2-d1) gave -316.
        self.assertEqual(days_30_360(date(2025, 12, 1), date(2026, 1, 15), "bond_basis"), 44)

    def test_same_date_is_zero(self):
        for v in VARIANTS:
            self.assertEqual(days_30_360(date(2025, 6, 15), date(2025, 6, 15), v), 0)

    def test_bond_basis_day_31_rules(self):
        self.assertEqual(days_30_360(date(2025, 1, 31), date(2025, 3, 1), "bond_basis"), 31)
        self.assertEqual(days_30_360(date(2025, 1, 31), date(2025, 3, 31), "bond_basis"), 60)
        self.assertEqual(days_30_360(date(2025, 1, 30), date(2025, 3, 31), "bond_basis"), 60)
        # D2=31 stays 31 when D1 < 30
        self.assertEqual(days_30_360(date(2025, 1, 15), date(2025, 3, 31), "bond_basis"), 76)

    def test_e360_clamps_every_31(self):
        self.assertEqual(days_30_360(date(2025, 1, 15), date(2025, 3, 31), "e360"), 75)

    def test_us_eom_february_rules(self):
        self.assertEqual(days_30_360(date(2025, 2, 28), date(2025, 3, 31), "us_eom"), 30)
        self.assertEqual(days_30_360(date(2025, 2, 28), date(2025, 3, 31), "bond_basis"), 33)
        self.assertEqual(days_30_360(date(2025, 2, 28), date(2025, 3, 1), "us_eom"), 1)
        self.assertEqual(days_30_360(date(2025, 2, 28), date(2025, 3, 1), "bond_basis"), 3)
        self.assertEqual(days_30_360(date(2024, 2, 29), date(2024, 3, 31), "us_eom"), 30)  # leap year

    def test_anniversaries_are_360_multiples(self):
        for v in VARIANTS:
            self.assertEqual(days_30_360(date(2024, 5, 10), date(2026, 5, 10), v), 720)

    def test_month_end_sweep_never_negative(self):
        import calendar
        ends = [date(y, m, calendar.monthrange(y, m)[1]) for y in range(2023, 2027) for m in range(1, 13)]
        for v in VARIANTS:
            for a in ends:
                for b in ends:
                    if b >= a:
                        self.assertGreaterEqual(days_30_360(a, b, v), 0, (v, a, b))

    def test_rejects_bad_input(self):
        with self.assertRaises(ValueError):
            days_30_360(date(2025, 2, 1), date(2025, 1, 1), "bond_basis")
        with self.assertRaises(ValueError):
            days_30_360(date(2025, 1, 1), date(2025, 2, 1), "nasd")
        with self.assertRaises(ValueError):
            days_30_360(date(2025, 1, 1), date(2025, 2, 1), "")


if __name__ == "__main__":
    unittest.main()
