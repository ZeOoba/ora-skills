"""Migrate saved ora_walk deal JSON files across input-format changes (acquisition-underwriting v4.53 and v4.54).

v4.53 replaced `land_value` (the Ruling 4 dry-land credit, set only once the FEMA determination landed)
with `market_land_value` + `land_comp_count` + `land_flood_cleared`. The solver now refuses the old
field ("Unknown deal fields: ['land_value']").

What this script does, per deal (a single deal object, a list of deals, or {"buildings": [...]}):
  - land_value > 0  -> market_land_value = land_value, land_flood_cleared = true (the old field was only
                       ever non-zero after the FEMA determination cleared the land), land_comp_count left
                       UNSET, so the solver credits 0 and flags [DATA-GAP: land comps] until you add the
                       count of land sale comps (v4.53 needs at least 3). This is deliberate: an assessor
                       land value is not a market land value, so no credit is carried over silently.
  - land_value == 0 -> the field is dropped (no land credit, as before).
It also reports (does not fix) any rollover deal with no `gpr`, which v4.54 now requires.
The original file is kept as <name>.pre-v453.json beside it.

Usage:  python migrate_deal_json.py <file-or-folder> [...] [--dry-run]
        (run from anywhere; it needs only the Python standard library)
"""
import json
import shutil
import sys
from pathlib import Path


def _migrate(deal: dict) -> list:
    notes = []
    if deal.get("lease_expiry_month") is not None and deal.get("gpr") is None:
        notes.append("NEEDS gpr: v4.54 rejects lease_expiry_month without gpr (stabilization-year gross "
                     "potential revenue, base rent plus recoveries); add it by hand")
    if "land_value" not in deal:
        return notes
    v = deal.pop("land_value")
    if v and v > 0:
        deal.setdefault("market_land_value", v)
        deal.setdefault("land_flood_cleared", True)
        notes.append(f"land_value {v:,.0f} -> market_land_value; land_comp_count left unset "
                     "(credit 0 + DATA-GAP until >= 3 land comps are recorded)")
    else:
        notes.append("land_value 0 dropped")
    return notes


def migrate_obj(obj) -> list:
    if isinstance(obj, list):
        return [n for d in obj if isinstance(d, dict) for n in _migrate(d)]
    if isinstance(obj, dict) and isinstance(obj.get("buildings"), list):
        return [n for d in obj["buildings"] if isinstance(d, dict) for n in _migrate(d)]
    if isinstance(obj, dict):
        return _migrate(obj)
    return []


def main(argv) -> int:
    dry = "--dry-run" in argv
    paths = [Path(a) for a in argv if a != "--dry-run"]
    files = [f for p in paths for f in ([p] if p.is_file() else sorted(p.rglob("*.json")))]
    changed = 0
    for f in files:
        if f.name.endswith(".pre-v453.json"):
            continue
        try:
            obj = json.loads(f.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            continue
        notes = migrate_obj(obj)
        if not notes:
            continue
        if all(n.startswith("NEEDS") for n in notes):
            print(f"CHECK {f}: " + "; ".join(notes))
            continue
        changed += 1
        print(f"{'WOULD MIGRATE' if dry else 'MIGRATED'} {f}: " + "; ".join(notes))
        if not dry:
            shutil.copy2(f, f.with_name(f.stem + ".pre-v453.json"))
            f.write_text(json.dumps(obj, indent=2) + "\n", encoding="utf-8")
    print(f"{changed} file(s) {'to migrate' if dry else 'migrated'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
