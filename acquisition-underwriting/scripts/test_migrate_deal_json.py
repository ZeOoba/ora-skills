"""Tests for migrate_deal_json.py: saved walk-solver deal files across the v4.53 / v4.54 input changes.

The migrated output must be accepted by the current solver (no "Unknown deal fields"), carry no land credit
until land comps are recorded, and every rollover deal without gpr must be reported, not guessed.
Run: python test_migrate_deal_json.py
"""
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import migrate_deal_json as M  # noqa: E402
from ora_walk.solver import Deal  # noqa: E402

OLD = {"name": "Old deal", "sf": 20000, "market": "Columbus OH", "year_built": 1995,
       "construction_type": "tilt-up", "stabilized_noi": 150000, "land_value": 300000}


def _run(*args):
    buf = io.StringIO()
    with redirect_stdout(buf):
        code = M.main([str(a) for a in args])
    return code, buf.getvalue()


class Migrate(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())

    def _write(self, name, obj):
        p = self.dir / name
        p.write_text(json.dumps(obj), encoding="utf-8")
        return p

    def test_land_value_becomes_market_land_value_with_no_comps(self):
        p = self._write("a.json", OLD)
        code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        d = json.loads(p.read_text(encoding="utf-8"))
        self.assertNotIn("land_value", d)
        self.assertEqual(d["market_land_value"], 300000)
        self.assertTrue(d["land_flood_cleared"])
        self.assertNotIn("land_comp_count", d)       # no credit until >= 3 comps are recorded by hand
        Deal(**d)                                     # the current solver accepts every migrated field
        self.assertTrue((self.dir / "a.pre-v453.json").exists())
        self.assertIn("land_value", json.loads((self.dir / "a.pre-v453.json").read_text(encoding="utf-8")))

    def test_zero_land_value_dropped(self):
        p = self._write("z.json", dict(OLD, land_value=0))
        _run(p)
        d = json.loads(p.read_text(encoding="utf-8"))
        self.assertNotIn("land_value", d)
        self.assertNotIn("market_land_value", d)

    def test_dry_run_changes_nothing(self):
        p = self._write("a.json", OLD)
        before = p.read_text(encoding="utf-8")
        code, out = _run(p, "--dry-run")
        self.assertEqual(code, 0)
        self.assertIn("WOULD MIGRATE", out)
        self.assertEqual(p.read_text(encoding="utf-8"), before)
        self.assertFalse((self.dir / "a.pre-v453.json").exists())

    def test_rollover_without_gpr_is_reported_not_guessed(self):
        p = self._write("r.json", dict(OLD, lease_expiry_month=60))
        code, out = _run(p)
        self.assertIn("NEEDS gpr", out)
        self.assertNotIn("gpr", json.loads(p.read_text(encoding="utf-8")))
        q = self._write("r2.json", {k: v for k, v in dict(OLD, lease_expiry_month=60).items() if k != "land_value"})
        code, out = _run(q)
        self.assertIn("CHECK", out)                   # nothing to migrate, but the gap is still reported
        self.assertFalse((self.dir / "r2.pre-v453.json").exists())

    def test_portfolio_and_list_shapes(self):
        p = self._write("p.json", {"buildings": [OLD, dict(OLD, name="B", land_value=0)]})
        l = self._write("l.json", [OLD])
        _run(self.dir)
        b = json.loads(p.read_text(encoding="utf-8"))["buildings"]
        self.assertEqual(b[0]["market_land_value"], 300000)
        self.assertNotIn("land_value", b[1])
        self.assertEqual(json.loads(l.read_text(encoding="utf-8"))[0]["market_land_value"], 300000)

    def test_backups_and_non_deal_json_skipped(self):
        self._write("x.pre-v453.json", OLD)
        self._write("other.json", {"hello": "world"})
        (self.dir / "broken.json").write_text("{not json", encoding="utf-8")
        code, out = _run(self.dir)
        self.assertEqual(code, 0, out)
        self.assertIn("0 file(s) migrated", out)


if __name__ == "__main__":
    unittest.main()
