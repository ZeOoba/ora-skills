#!/usr/bin/env python3
"""Example deal-terms registers must be fully synthetic (2026-11-08).

Audit row tenant-pii-in-shipped-example-register: lease-generation shipped a
filled example register built from a real deal, tenant identity included. It was
replaced by a synthetic register and untracked (no history rewrite). This gate
keeps a real register from coming back under any example-register filename.

Positive-marker check, so it never needs to hold the real data it guards against:
every `*example*register*.json` outside `_archive/` must
  - carry `"_synthetic": true`,
  - use a deal_id starting `EXAMPLE-`,
  - mark every party/person field (landlord, tenant, co-tenants, signatories,
    copy-to, broker firm and agents) with "example" or "fictional",
  - put every address on an "Example" street,
  - use only example.com / *.example email addresses, if any.

Stdlib only -- run with `python tools/test_example_registers_synthetic.py`.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_SKIP_DIRS = {".git", "_archive", "node_modules", ".pytest_cache", "_staging", ".claude", ".worktrees"}
_MARK = re.compile(r"example|fictional", re.I)
_EMAIL_OK = re.compile(r"@(?:[\w-]+\.)*example(?:\.com)?$", re.I)

PARTY_PATHS = (
    ("landlord", "entity"), ("landlord", "signatory"), ("landlord", "copy_to"),
    ("tenant", "entity"), ("tenant", "signatory"), ("tenant", "business_description"),
    ("broker", "firm"), ("broker", "landlord_agent"), ("broker", "tenant_agent"),
    ("premises", "project_name"),
)
ADDRESS_PATHS = (("landlord", "notice_address"), ("tenant", "notice_address"), ("premises", "address"))
EMAIL_PATHS = (("tenant", "notice_email"),)


def find_example_registers(root):
    out = []
    for p in sorted(root.rglob("*.json")):
        rel = p.relative_to(root)
        if any(part in _SKIP_DIRS for part in rel.parts[:-1]):
            continue
        name = p.name.lower()
        if "example" in name and "register" in name:
            out.append(p)
    return out


def _get(d, path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def problems(reg):
    """List of non-synthetic markers found in one parsed register (empty = clean)."""
    if not isinstance(reg, dict):
        return ["register is not a JSON object"]
    found = []
    if reg.get("_synthetic") is not True:
        found.append('missing "_synthetic": true')
    if not str(reg.get("deal_id", "")).startswith("EXAMPLE-"):
        found.append("deal_id does not start with EXAMPLE-")
    for path in PARTY_PATHS:
        v = _get(reg, path)
        if isinstance(v, str) and v and not _MARK.search(v):
            found.append(f"{'.'.join(path)} lacks an example/fictional marker")
    for i, v in enumerate(_get(reg, ("tenant", "co_tenants")) or []):
        if not (isinstance(v, str) and _MARK.search(v)):
            found.append(f"tenant.co_tenants[{i}] lacks an example/fictional marker")
    for path in ADDRESS_PATHS:
        v = _get(reg, path)
        if isinstance(v, str) and v and "example" not in v.lower():
            found.append(f"{'.'.join(path)} is not an Example address")
    for path in EMAIL_PATHS:
        v = _get(reg, path)
        if isinstance(v, str) and v and not _EMAIL_OK.search(v.strip()):
            found.append(f"{'.'.join(path)} is not an example.com address")
    return found


class TestShippedExampleRegisters(unittest.TestCase):
    def test_at_least_one_example_register_is_checked(self):
        # A rename that slipped past the glob must not turn this gate into a no-op.
        self.assertTrue(find_example_registers(REPO), "no example register found to check")

    def test_every_example_register_is_synthetic(self):
        for p in find_example_registers(REPO):
            with self.subTest(path=str(p.relative_to(REPO))):
                reg = json.loads(p.read_text(encoding="utf-8"))
                # Report field paths only, never the values (they may be the PII).
                self.assertEqual(problems(reg), [])

    def test_retired_real_register_is_not_back(self):
        old = REPO / "lease-generation" / "references" / "example-register-northwood-15a.json"
        self.assertFalse(old.exists(), "the retired real-data example register is back in references/")


class TestCheckerCatchesRealLookingData(unittest.TestCase):
    def _synthetic(self):
        return {
            "_synthetic": True, "deal_id": "EXAMPLE-1-ZEPHYR-2026-01",
            "landlord": {"entity": "Example Holdings, LLC (fictional)",
                         "notice_address": "1 Example Way, Anytown, OH 43000"},
            "tenant": {"entity": "Zephyr Example Corp", "co_tenants": ["Example Principal"],
                       "notice_email": "notices@zephyr.example"},
            "premises": {"address": "1 Example Way"},
            "broker": {"firm": "Example Brokerage"},
        }

    def test_clean_synthetic_register_passes(self):
        self.assertEqual(problems(self._synthetic()), [])

    def test_each_real_looking_field_is_flagged(self):
        cases = {
            ("_synthetic",): False,
            ("deal_id",): "ZEPHYR-1-2026-01",
            ("tenant", "entity"): "Zephyr Corp LLC",
            ("landlord", "notice_address"): "1 Main Street, Anytown, OH 43000",
            ("premises", "address"): "1 Main Street",
            ("tenant", "notice_email"): "owner@zephyrcorp.com",
            ("broker", "firm"): "Acme Realty",
        }
        for path, bad in cases.items():
            with self.subTest(path=path):
                reg = self._synthetic()
                node = reg
                for k in path[:-1]:
                    node = node[k]
                node[path[-1]] = bad
                self.assertTrue(problems(reg), f"{path} = {bad!r} was not flagged")

    def test_real_looking_co_tenant_is_flagged(self):
        reg = self._synthetic()
        reg["tenant"]["co_tenants"] = ["Jordan Smith"]
        self.assertTrue(problems(reg))

    def test_discovery_skips_archive_and_finds_nested(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "skill" / "references").mkdir(parents=True)
            (root / "_archive" / "old").mkdir(parents=True)
            (root / "skill" / "references" / "example-register-x.json").write_text("{}", encoding="utf-8")
            (root / "_archive" / "old" / "example-register-y.json").write_text("{}", encoding="utf-8")
            names = [p.name for p in find_example_registers(root)]
            self.assertEqual(names, ["example-register-x.json"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
