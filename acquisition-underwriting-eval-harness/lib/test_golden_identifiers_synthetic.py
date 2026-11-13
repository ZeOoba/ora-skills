"""Golden-set identifiers must stay pseudonymized (2026-11-12).

Egress audit row eval-golden-set-real-pipeline-public: the public repo published the
golden deals' real addresses, parcel IDs and counterparty names. They were aliased to
GS-A..GS-F with every number left untouched. This gate keeps a real street address,
ZIP, parcel-number shape or non-alias deal_id from coming back. It reports the JSON
path only, never the value.
"""
import json
import re
import tempfile
import unittest
from pathlib import Path

GOLDEN_DIR = Path(__file__).resolve().parent.parent / "golden_set"

_STREET = re.compile(
    r"\b\d{1,6}(?:-\d{1,6})?,?\s+(?:[NSEW]\.?\s+)?(?:[A-Z][\w.']*\s+){1,4}"
    r"(?:St|Street|Rd|Road|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Way|Pkwy|Parkway|Ln|Lane|Ct|Court|Pike|Hwy)\b")
_ZIP = re.compile(r"\b(?:OH|MI|IN|KY|MD|MO|KS|TN|WI|IL|IA|PA|VA|WV)\s+\d{5}(?:[-/]\d{4,5})?\b")
_PARCEL = re.compile(r"\b\d{3}-\d{5,6}(?:-\d{2})?\b")


def _strings(node, path="$"):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from _strings(v, f"{path}.{k}")
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from _strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def identity_problems(golden, stem):
    found = []
    deal_id = str(golden.get("deal_id", ""))
    if not re.fullmatch(r"gs-[a-z]-[a-z0-9-]+", deal_id):
        found.append("deal_id is not a gs-<letter>-... alias")
    if deal_id != stem:
        found.append("deal_id does not match the file name")
    for key in ("deal_name",):
        if not str(golden.get(key, "")).startswith("GS-"):
            found.append(f"{key} does not start with a GS- alias")
    addr = (golden.get("inputs") or {}).get("address")
    if not (isinstance(addr, str) and addr.startswith("GS-") and "synthetic alias" in addr):
        found.append("inputs.address is not a GS- synthetic alias")
    for path, s in _strings(golden):
        if _STREET.search(s):
            found.append(f"{path}: street-address shape")
        if _ZIP.search(s):
            found.append(f"{path}: state + ZIP shape")
        if _PARCEL.search(s):
            found.append(f"{path}: parcel-number shape")
    return found


class TestShippedGoldensArePseudonymized(unittest.TestCase):
    def test_goldens_exist(self):
        self.assertTrue(sorted(GOLDEN_DIR.glob("*.json")), "no golden_set/*.json found")

    def test_every_golden_is_pseudonymized(self):
        for p in sorted(GOLDEN_DIR.glob("*.json")):
            with self.subTest(golden=p.name):
                self.assertEqual(identity_problems(json.loads(p.read_text(encoding="utf-8")), p.stem), [])


class TestCheckerCatchesRealLookingData(unittest.TestCase):
    def _clean(self):
        return {
            "deal_id": "gs-z-flex-anytown-oh",
            "deal_name": "GS-Z (street address withheld -- synthetic alias), Anytown OH",
            "inputs": {"address": "GS-Z (street address withheld -- synthetic alias), Anytown OH",
                       "noi_annual": 100000, "other_facts": "Vacant flex box."},
        }

    def test_clean_passes(self):
        self.assertEqual(identity_problems(self._clean(), "gs-z-flex-anytown-oh"), [])

    def test_real_looking_values_are_flagged(self):
        cases = [
            ("deal_id", "100-main-st-anytown-oh"),
            ("deal_name", "100 Main St, Anytown OH"),
        ]
        for key, bad in cases:
            with self.subTest(key=key):
                g = self._clean()
                g[key] = bad
                self.assertTrue(identity_problems(g, "gs-z-flex-anytown-oh"))
        for bad in ("100 Main St, Anytown, OH 43000", "Anytown OH 43000",
                    "parcel 010-123456-00", "1200 W. Commerce Blvd"):
            with self.subTest(other_facts=bad):
                g = self._clean()
                g["inputs"]["other_facts"] = bad
                self.assertTrue(identity_problems(g, "gs-z-flex-anytown-oh"))

    def test_numbers_are_never_inspected(self):
        g = self._clean()
        g["inputs"]["building_sf"] = 43000
        self.assertEqual(identity_problems(g, "gs-z-flex-anytown-oh"), [])

    def test_file_name_must_match_alias(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "100-main-st.json"
            p.write_text(json.dumps(self._clean()), encoding="utf-8")
            self.assertIn("deal_id does not match the file name",
                          identity_problems(json.loads(p.read_text(encoding="utf-8")), p.stem))


if __name__ == "__main__":
    unittest.main(verbosity=2)
