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
The original file is kept as <name>.pre-v453.json beside it, and the new content is swapped in atomically,
so a failed write leaves the original intact.
Anything it cannot handle is printed as a SKIP line and counted in the summary, never dropped silently:
an unreadable file, a folder it cannot list (on Windows, a folder past the 260-character path limit), a
path that does not exist, a file that is not UTF-8 JSON, a non-numeric land_value, or a failed write.
A SKIP never stops the run. Exit code is 0 either way (2 only when no path is given), so read the summary line.
Folders are walked recursively; Windows junctions are followed but each real folder is visited once.
A symlinked deal file is migrated through its target (the link stays a link); a directory symlink is not
followed and is a SKIP; a file with more than one hard link is a SKIP, because the atomic swap would split
the links. Output lists each folder's files before its subfolders.
A UTF-8 file with a byte-order mark is read and written back without it. The backup's timestamp is the time
of the run, not the original's.

Usage:  python migrate_deal_json.py <file-or-folder> [...] [--dry-run]
        (run from anywhere; it needs only the Python standard library)
"""
import json
import math
import os
import shutil
import stat
import sys
from pathlib import Path

class BadDeal(ValueError):
    """A deal field the migration cannot interpret; the whole file is left untouched."""


def _real(p) -> str:
    try:
        return os.path.normcase(os.path.realpath(p))
    except (OSError, ValueError):
        return os.path.normcase(os.path.abspath(p))


def _collect(paths):
    """Return (json files, skip messages). Unlike Path.rglob, a folder that cannot be listed (a subfolder
    past Windows MAX_PATH, a permission error) is reported instead of silently ignored. Windows junctions
    are followed, as rglob did, but each real folder and file is visited once, so a junction loop or two
    overlapping arguments cannot repeat a file."""
    files, skips, seen_dirs, seen_files = [], [], set(), set()

    def add(f):
        r = _real(f)
        if r not in seen_files:
            seen_files.add(r)
            # a symlink is migrated through its target: os.replace on the link path would turn the link into a
            # plain file and leave the real deal file unmigrated
            files.append(Path(os.path.realpath(f)) if os.path.islink(f) else f)

    for p in paths:
        try:
            is_file, is_dir = p.is_file(), p.is_dir()
        except OSError as e:  # access denied on the path itself
            skips.append(f"SKIP {p}: cannot open ({type(e).__name__}: {e.strerror or e})")
            continue
        if is_file:
            add(p)
        elif is_dir:
            def onerror(e, root=p):
                skips.append(f"SKIP {e.filename or root}: cannot list folder ({type(e).__name__}: "
                             f"{e.strerror or e}); any deal files inside were NOT checked")
            for root, dirs, names in os.walk(p, onerror=onerror):
                r = _real(root)
                if r in seen_dirs:      # reached again through a junction: already walked
                    dirs[:] = []
                    continue
                seen_dirs.add(r)
                for d in dirs:  # os.walk never descends directory symlinks (nor did rglob): say so, not silence
                    if os.path.islink(os.path.join(root, d)):
                        skips.append(f"SKIP {os.path.join(root, d)}: directory symlink not followed; "
                                     "pass its target as an argument to check it")
                dirs.sort()
                for n in sorted(names):
                    if n.lower().endswith(".json"):
                        add(Path(root) / n)
        else:
            skips.append(f"SKIP {p}: not found, or path too long for Windows to open")
    return files, skips


def _replace(f: Path, text: str) -> None:
    """Back up f, then swap in the migrated text atomically: a failure leaves the original intact."""
    tmp = f.with_name(f.name + ".migrating.tmp")

    def clear_tmp():
        try:
            if tmp.exists():
                os.chmod(tmp, stat.S_IREAD | stat.S_IWRITE)   # a read-only stale temp file too
                tmp.unlink()
        except OSError:
            pass

    clear_tmp()                                                   # leftover from a crashed earlier run
    shutil.copyfile(f, f.with_name(f.stem + ".pre-v453.json"))   # copyfile: backup never inherits read-only
    try:
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, f)
    except OSError as e:
        e.filename, e.filename2 = str(f), None   # name the deal file, never the (deleted) temp file
        raise
    finally:
        clear_tmp()


def _migrate(deal: dict) -> list:
    notes = []
    if deal.get("lease_expiry_month") is not None and deal.get("gpr") is None:
        notes.append("NEEDS gpr: v4.54 rejects lease_expiry_month without gpr (stabilization-year gross "
                     "potential revenue, base rent plus recoveries); add it by hand")
    if "land_value" not in deal:
        return notes
    v = deal["land_value"]
    if v is not None:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise BadDeal(f"land_value {v!r} is not a number; fix it by hand")
        try:
            ok = math.isfinite(float(v)) and v >= 0
        except OverflowError:
            ok = False
        if not ok:
            raise BadDeal(f"land_value {str(v)[:30]} is negative, infinite, NaN or out of range; fix it by hand")
    deal.pop("land_value")
    if v and v > 0:
        if "market_land_value" in deal:
            notes.append(f"land_value {v:,.0f} dropped; existing market_land_value "
                         f"{repr(deal['market_land_value'])[:30]} kept unchanged")
        else:
            deal["market_land_value"] = v
            notes.append(f"land_value {v:,.0f} -> market_land_value; land_comp_count left unset "
                         "(credit 0 + DATA-GAP until >= 3 land comps are recorded)")
        deal.setdefault("land_flood_cleared", True)
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
    try:  # piped output on Windows is cp1252; an unencodable path or value must not crash print() mid-run
        sys.stdout.reconfigure(errors="backslashreplace")
    except (AttributeError, ValueError):
        pass
    dry = "--dry-run" in argv
    args = [a for a in argv if a != "--dry-run"]
    if not args:
        print("Usage: python migrate_deal_json.py <file-or-folder> [...] [--dry-run]")
        return 2
    # Path("") is the current folder: an unset shell variable must not migrate wherever the shell happens to be
    blank = [a for a in args if not a.strip()]
    files, skips = _collect([Path(a) for a in args if a.strip()])
    skips = [f"SKIP {a!r}: empty path argument (unset variable?); nothing checked for it" for a in blank] + skips
    for s in skips:
        print(s)
    changed, skipped = 0, len(skips)
    for f in files:
        if f.name.lower().endswith(".pre-v453.json"):
            continue
        try:
            # utf-8-sig: PowerShell 5.1 `Set-Content -Encoding UTF8` writes a BOM; plain utf-8 would reject it
            obj = json.loads(f.read_text(encoding="utf-8-sig"))
        except OSError as e:  # path too long, permission, locked: report, keep going
            skipped += 1
            print(f"SKIP {f}: cannot read ({type(e).__name__}: {e.strerror or e})")
            continue
        except (ValueError, RecursionError) as e:  # not UTF-8, not JSON, or nested too deep: report, keep going
            skipped += 1
            print(f"SKIP {f}: not valid UTF-8 JSON ({type(e).__name__})")
            continue
        try:
            notes = migrate_obj(obj)
        except BadDeal as e:  # file left untouched; nothing written
            skipped += 1
            print(f"SKIP {f}: {e}")
            continue
        if not notes:
            continue
        if all(n.startswith("NEEDS") for n in notes):
            print(f"CHECK {f}: " + "; ".join(notes))
            continue
        try:  # serialize before any backup is taken, in dry-run too, so both report the same SKIPs
            text = json.dumps(obj, indent=2) + "\n"
        except (ValueError, RecursionError) as e:
            skipped += 1
            print(f"SKIP {f}: cannot serialize the migrated deal ({type(e).__name__}); nothing written")
            continue
        try:
            links = os.stat(f).st_nlink
        except OSError:
            links = 1
        if links > 1:  # os.replace would split the links: the other names would keep the old content
            skipped += 1
            print(f"SKIP {f}: has {links} hard links; migrate a copy by hand and relink. Nothing written")
            continue
        if not dry:
            try:
                _replace(f, text)
            except OSError as e:  # read-only, locked (e.g. OneDrive sync) or disk full: original intact
                skipped += 1
                print(f"SKIP {f}: cannot write {e.filename or f} ({type(e).__name__}: {e.strerror or e}); "
                      "NOT migrated, original unchanged")
                continue
        changed += 1
        print(f"{'WOULD MIGRATE' if dry else 'MIGRATED'} {f}: " + "; ".join(notes))
    print(f"{changed} file(s) {'to migrate' if dry else 'migrated'}"
          + (f"; {skipped} file(s) skipped, see SKIP lines" if skipped else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
