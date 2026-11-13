"""RCT v03 replacement-cost table: private runtime file, loaded and validated here.

ora-skills is a PUBLIC repo, and the ratified RCT table is governor-level data (Hard Invariant 4), so the
table is not in source. It lives in a gitignored file, `rct-table.local.json`, at the repo root. The
packager (`tools/package_skills.py`, PRIVATE_LOCAL_DEPS) copies it into every installed skill that reads
RCT values, on Code, Cowork and claude.ai alike, so the installed skill finds it beside its SKILL.md.
Format and the steps for changing a value: `tools/RCT_TABLE.md`.

Fail closed: anything wrong with the file raises RctTableUnavailable. Callers produce no basis floor,
Basis score or walk price without it. They never substitute a figure.

Never put a real figure in this file, in a test, or in any other tracked file. The leak test
(`tools/test_rct_public_leak.py`) fails if one comes back.
"""
from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

FILE_NAME = "rct-table.local.json"
ENV_VAR = "ORA_RCT_TABLE"            # optional explicit path (a synthetic file is still refused)
RCT_VERSION = "RCT v03"              # the version SKILL.md cites; a copy of any other version is refused
SYNTHETIC_VERSION = "synthetic-test-fixture"

# Market keys in solver form, in SKILL.md row order. The set must match exactly: a missing or extra row
# means the copy is not the ratified table.
RCT_MARKETS = (
    "Columbus OH", "Cincinnati OH", "Kansas City MO", "Indianapolis IN", "Madison WI", "Mid-Atlantic",
    "Grand Rapids MI", "Richmond VA", "Des Moines IA", "Louisville KY", "Chicago-Cook IL",
)

PSF_MIN, PSF_MAX = 50.0, 1000.0      # sanity bounds on every $/SF figure
BAND = 0.10                          # LOW = 0.90 x POINT, HIGH = 1.10 x POINT (table method)
BAND_TOLERANCE = 0.02                # $/SF: the table rounds to the cent, one row re-derives +-0.01

_HERE = Path(__file__).resolve()
# scripts/ora_walk/rct_table.py -> skill root is parents[2]; a repo checkout keeps the file one level up.
_SKILL_ROOT = _HERE.parents[2]
DEFAULT_PATHS = (_SKILL_ROOT / FILE_NAME, _SKILL_ROOT.parent / FILE_NAME)


class RctTableUnavailable(RuntimeError):
    """The private RCT table is missing, malformed, synthetic, or not the ratified version."""


def _num(v, where: str, lo: float = PSF_MIN, hi: float = PSF_MAX) -> float:
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise RctTableUnavailable(f"{where} is not a finite number")
    if not lo <= v <= hi:
        raise RctTableUnavailable(f"{where} is outside {lo:g}..{hi:g}")
    return float(v)


MD_HEADER = "| Market | LOW $/SF | POINT $/SF | HIGH $/SF | C&W hard (source) |"
MD_RULE = "|---|---|---|---|---|"
_NOTE_FIGURE = re.compile(r"(?<![\w.])(\d{2,4}\.\d{1,2})(?![\d])|\$(\d{2,4})(?![\d.,])|(?<![\w.$])(\d{2,4})\s?/\s?SF")


def _check_note(name: str, m: dict) -> None:
    """A $/SF-scale decimal inside cwNote must be one of the row's own figures (to a cent of rounding),
    so free text can never carry a number the numeric fields and the authoritative tie do not bind."""
    own = (m["low"], m["point"], m["high"], m["cwHard"])
    for groups in _NOTE_FIGURE.findall(m.get("cwNote", "")):
        v = float(next(g for g in groups if g))
        if PSF_MIN <= v <= PSF_MAX and not any(abs(v - o) <= 0.011 for o in own):
            raise RctTableUnavailable(f"{name}.cwNote carries a figure that is not one of the row's own")


_CELL = re.compile(r"\$?(\d{1,4}(?:\.\d{1,2})?)")
_HARD_CELL = re.compile(r"\$?(\d{1,4}(?:\.\d{1,2})?)(?: (\S.*))?")


def validate(table, *, allow_synthetic: bool = False) -> dict:
    """Return the table if it is a well-formed ratified copy, else raise RctTableUnavailable.

    `allow_synthetic` is for tests only and is reachable from code, never from the environment.
    """
    if not isinstance(table, dict):
        raise RctTableUnavailable("table is not a JSON object")
    synthetic = table.get("_synthetic") is True or table.get("rctVersion") == SYNTHETIC_VERSION
    if synthetic and not allow_synthetic:
        raise RctTableUnavailable("table is the synthetic test fixture, not the ratified RCT")
    if not synthetic and table.get("rctVersion") != RCT_VERSION:
        raise RctTableUnavailable(f"rctVersion is not {RCT_VERSION!r} (stale or wrong copy)")
    markets = table.get("markets")
    if not isinstance(markets, dict):
        raise RctTableUnavailable("markets is missing or not an object")
    if tuple(markets) != RCT_MARKETS:
        raise RctTableUnavailable("market rows do not match the ratified market list and order")
    for name, m in markets.items():
        if not isinstance(m, dict):
            raise RctTableUnavailable(f"markets[{name}] is not an object")
        low = _num(m.get("low"), f"{name}.low")
        point = _num(m.get("point"), f"{name}.point")
        high = _num(m.get("high"), f"{name}.high")
        _num(m.get("cwHard"), f"{name}.cwHard")
        if not low < point < high:
            raise RctTableUnavailable(f"{name}: LOW < POINT < HIGH does not hold")
        if abs(low - (1 - BAND) * point) > BAND_TOLERANCE or abs(high - (1 + BAND) * point) > BAND_TOLERANCE:
            raise RctTableUnavailable(f"{name}: LOW/HIGH are not POINT -/+10% (a mistyped column)")
        if not isinstance(m.get("label"), str) or not m["label"].strip():
            raise RctTableUnavailable(f"{name}.label is missing")
        if not isinstance(m.get("cwNote", ""), str):
            raise RctTableUnavailable(f"{name}.cwNote is not a string")
    d = table.get("derivation")  # the build parameters (rule 11); private like the figures they produce
    if not isinstance(d, dict):
        raise RctTableUnavailable("derivation block is missing")
    ref = d.get("referenceSf")
    if isinstance(ref, bool) or not isinstance(ref, int) or not 5_000 <= ref <= 109_200:
        raise RctTableUnavailable("derivation.referenceSf is not an integer SF below the C&W small tier")
    _num(d.get("softCostMultiplier"), "derivation.softCostMultiplier", 1.0, 2.0)
    _num(d.get("escalation"), "derivation.escalation", 1.0, 1.5)
    for k in ("softCostNote", "escalationNote", "sizePremiumNote", "formula"):
        if not isinstance(d.get(k), str) or not d[k].strip():
            raise RctTableUnavailable(f"derivation.{k} is missing")
    md = table.get("markdownTable")
    if not isinstance(md, str):
        raise RctTableUnavailable("markdownTable is missing")
    lines = md.strip().split("\n")
    # The whole text is the table and nothing else: the exact header and rule, then one row per market.
    # A swapped header (LOW <-> HIGH) or a stray line ("corrected POINT: ...") is an unbound figure.
    if lines[:2] != [MD_HEADER, MD_RULE] or any(not ln.startswith("|") for ln in lines):
        raise RctTableUnavailable("markdownTable header, rule or line structure is not the ratified layout")
    rows = lines[2:]
    if len(rows) != len(RCT_MARKETS):
        raise RctTableUnavailable("markdownTable does not have one row per market")
    for row, name in zip(rows, RCT_MARKETS):
        m = markets[name]
        cells = [c.strip() for c in row.strip().strip("|").split("|")]
        if cells[0] != m["label"]:
            raise RctTableUnavailable(f"markdownTable row for {name} is out of order or mislabelled")
        # Every figure an agent can read in the row is bound: LOW/POINT/HIGH cells are exactly one number,
        # and the hard cell is its number followed by the stored cwNote verbatim (nothing else).
        if len(cells) != 5:
            raise RctTableUnavailable(f"markdownTable row for {name} does not have 5 cells")
        for cell, key in zip(cells[1:4], ("low", "point", "high")):
            hit = _CELL.fullmatch(cell)
            if not hit or float(hit.group(1)) != float(m[key]):
                raise RctTableUnavailable(f"markdownTable row for {name} disagrees with its numeric fields")
        _check_note(name, m)
        hit = _HARD_CELL.fullmatch(cells[4])
        if (not hit or float(hit.group(1)) != float(m["cwHard"])
                or (hit.group(2) or "") != m.get("cwNote", "")):
            raise RctTableUnavailable(f"markdownTable row for {name} disagrees with its numeric fields")
    return table


def load(path: os.PathLike | str | None = None, *, allow_synthetic: bool = False) -> dict:
    """Load and validate the table. Search order: `path`, $ORA_RCT_TABLE, skill root, repo root."""
    candidates = [Path(path)] if path else []
    env = os.environ.get(ENV_VAR, "").strip()
    if env and not path:
        candidates.append(Path(env))
    if not path:
        candidates.extend(DEFAULT_PATHS)
    for p in candidates:
        if p.is_file():
            try:
                table = json.loads(p.read_text(encoding="utf-8-sig"))
            except (OSError, ValueError) as e:
                raise RctTableUnavailable(f"{p.name} is unreadable or not JSON ({type(e).__name__})") from None
            return validate(table, allow_synthetic=allow_synthetic)
    raise RctTableUnavailable(
        f"{FILE_NAME} not found. It ships inside the installed skill; in a repo checkout it is the "
        "gitignored repo-root copy (see tools/RCT_TABLE.md). No basis floor, Basis score or walk "
        "price can be produced without it.")


CW_SMALL_RSF, CW_MEDIUM_RSF = 109_200, 476_400   # C&W 2025 guide tier sizes (public)
DERIVATION_TOLERANCE = 0.011                     # $/SF: the ratified rows reproduce to the cent


def derivation_mismatches(table: dict, cw: dict) -> list[str]:
    """Market names (never figures) whose POINT the table's own `derivation` parameters do NOT reproduce
    from the public C&W tiers (`references/cw-2025-construction-costs.json`): POINT = small x
    (small_rsf / referenceSf)^b x softCostMultiplier x escalation, b = ln(small/med) / ln(med_rsf/small_rsf).
    The C&W market is the one whose small tier equals the row's cwHard (a proxy row uses its proxy's tiers).
    This ties the private parameters to the private figures without any second file."""
    d = table["derivation"]
    out = []
    for name, m in table["markets"].items():
        best = None
        for tiers in (cw or {}).values():
            if not isinstance(tiers, dict):
                continue
            small, med = tiers.get("small25"), tiers.get("med25")
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0 for x in (small, med)):
                continue
            if abs(small - m["cwHard"]) > 1e-9:
                continue
            b = math.log(small / med) / math.log(CW_MEDIUM_RSF / CW_SMALL_RSF)
            point = small * (CW_SMALL_RSF / d["referenceSf"]) ** b * d["softCostMultiplier"] * d["escalation"]
            err = abs(point - m["point"])
            best = err if best is None else min(best, err)
        if best is None or best > DERIVATION_TOLERANCE:
            out.append(name)
    return out


_override: dict | None = None


def use(table: dict | None) -> None:
    """Tests only: make `current()` return this table (synthetic allowed). None restores file loading."""
    global _override
    _override = None if table is None else validate(table, allow_synthetic=True)


def current() -> dict:
    """The table the solver uses: a test override, else the private file (loaded on every call)."""
    return _override if _override is not None else load()


def points(table: dict) -> dict:
    """{solver market key: POINT $/SF} in RCT_MARKETS order."""
    return {k: float(table["markets"][k]["point"]) for k in RCT_MARKETS}
