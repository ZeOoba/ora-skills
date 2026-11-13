#!/usr/bin/env python3
"""ORA IC Memo <-> Model Tie-Out Gate.

Deterministically ties every figure stated in an IC memo (.docx) to a cell in the
paired underwriting model (.xlsx). Read-only: it never edits either file, and it
refuses an --out/--json path that is the memo, the model, or any Office file.

Each memo figure ($, %, x, SF) is classified:
  TIED      - a model cell matches within the memo's own display rounding
  NEAR      - a model cell is within --near-pct (default 0.5%) but outside rounding
  CONFLICT  - the figure carries a metric (DSCR, NOI, cap rate ...) and the model's
              cells with that metric in their label hold a different value
  UNTIED    - no model cell supports the figure

No false pass: when the memo names a metric and the model has cells labelled with it,
ONLY those cells can tie the figure; a coincidental equal value elsewhere is a note,
never a TIED. Threshold cells (Min DSCR, Max LTV, floor, covenant, target ...) tie only
a memo figure that is itself stated as a threshold. Count and year cells (tenant count,
analysis year, hold years) never tie a $, % or x figure by value alone.

Exit codes: 0 = no CONFLICT/UNTIED (NEAR is reported, never fails) · 1 = CONFLICT/UNTIED
present · 2 = input error: missing or unreadable file, a memo with no figures, an output
path that would overwrite an input, or ANY formula cell without a cached value (a model
saved by a script; open and save it in Excel first). --allow-uncached downgrades the
last to a warning. A verified null beats an inferred null.

Usage:
  python memo_tieout.py MEMO.docx MODEL.xlsx [--out report.md] [--json report.json]
                        [--near-pct 0.5] [--ignore-pattern REGEX ...] [--allow-uncached]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from xml.etree import ElementTree as ET

W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

# Metric vocabulary: canonical key -> regex matched against memo context and model labels.
METRICS: dict[str, str] = {
    "dscr": r"\bdscr\b|\bdcr\b|debt service coverage|debt coverage|coverage ratio|\bcoverage\b",
    "ltv": r"\bltv\b|loan[- ]to[- ]value|\bleverage\b",
    "cap_rate": r"cap(?:italization)?\.? rate|(?<!rate )\bcap\b(?!\s*strike)",  # not an interest-rate cap
    "irr": r"\birr\b|internal rate of return",
    "noi": r"\bnoi\b|net operating income",
    "price": r"purchase price|\bprice\b|\bbid\b|offer|acquisition cost|basis",
    "equity_multiple": r"equity multiple|\bmoic\b|\bem\b",
    "cash_on_cash": r"cash[- ]on[- ]cash|\bcoc\b",
    "yield_on_cost": r"yield on cost|\byoc\b",
    "debt_yield": r"debt yield",
    "loan": r"loan amount|\bloan\b|debt proceeds|mortgage",
    "equity": r"\bequity\b",
    "rent_psf": r"\brent\b|\bnnn\b",
    "occupancy": r"occupan|vacan|leased",
    "replacement_cost": r"replacement cost",
    "sf": r"\bsf\b|square feet|sq\.? ?ft|rentable|\bnra\b|\bgla\b",
}
METRIC_RE = {k: re.compile(v, re.I) for k, v in METRICS.items()}
# Which figure kinds a metric can describe: "exit cap" next to "$2.26M" is not a cap-rate claim.
METRIC_KINDS = {
    "dscr": {"mult"}, "equity_multiple": {"mult"},
    "ltv": {"pct"}, "cap_rate": {"pct"}, "irr": {"pct"}, "cash_on_cash": {"pct"},
    "yield_on_cost": {"pct"}, "debt_yield": {"pct"}, "occupancy": {"pct"},
    "noi": {"money"}, "price": {"money"}, "loan": {"money"}, "equity": {"money"},
    "rent_psf": {"money"}, "replacement_cost": {"money"}, "sf": {"sf"},
}
# A threshold, limit or target rather than a computed result (model label or memo context).
THRESH_RE = re.compile(r"\b(?:min(?:imum)?|max(?:imum)?|floor|ceiling|covenant|hurdle|target|"
                       r"required|requirement|threshold|limit)\b", re.I)
# After the figure only an unambiguous limit word makes it a threshold ("1.25x minimum");
# "1.25x lender-underwritten" reports a result.
NEXT_THRESH_RE = re.compile(r"\s{0,2}(?:min(?:imum)?|max(?:imum)?|floor|ceiling|limit)\b", re.I)
# Area types: "rentable area of 24,500 SF" must tie a rentable-SF cell, not land area.
SF_TYPE_RE = re.compile(r"\b(rentable|building|land|site|lot|warehouse|office|mezzanine|nra|gla)\b", re.I)
# Count, period and year cells: never a $, % or x figure's support by value alone.
COUNT_RE = re.compile(r"\b(?:years?|yrs?|months?|period|count|number|units|tenants|buildings|hold|term)\b|#",
                      re.I)
# Qualifiers that split one metric into different figures ("going-in" vs "exit" cap rate).
QUALIFIERS = {
    "going_in": r"going[- ]in|\bentry\b|in[- ]place", "exit": r"\bexit\b|terminal|reversion",
    "levered": r"(?<!un)\blevered\b", "unlevered": r"\bunlevered\b", "stabilized": r"stabili[sz]ed",
    "base": r"\bbase\b", "bear": r"\bbear\b|downside", "bull": r"\bbull\b|upside",
    "pre_tax": r"pre[- ]tax", "after_tax": r"after[- ]tax|post[- ]tax",
}
QUALIFIER_RE = {k: re.compile(v, re.I) for k, v in QUALIFIERS.items()}
YEAR_TOKEN_RE = re.compile(r"\b(?:year|yr)[\s-]?(\d{1,2})\b", re.I)
ERROR_VALUES = {"#DIV/0!", "#REF!", "#VALUE!", "#N/A", "#NAME?", "#NUM!", "#NULL!"}
# A cell that stores a whole-number percent (3.0 meaning 3%) says so in its label.
PCT_LABEL_RE = re.compile(r"%|percent|\brate\b|growth|yield|vacan|occupan|escalat|\birr\b|\bltv\b|"
                          r"\bcap\b|return|margin", re.I)

FAILING = ("CONFLICT", "AMBIGUOUS", "UNTIED")  # statuses that fail the gate (exit 1)

SCALE = {"k": 1e3, "thousand": 1e3, "m": 1e6, "mm": 1e6, "million": 1e6, "b": 1e9, "billion": 1e9}

# Order matters: money before bare percent/multiple; SF last.
CLAIM_RE = re.compile(
    r"(?P<money>\$\s?(?P<mparen>\()?(?P<mnum>\d[\d,]*(?:\.\d+)?)\s*(?P<mscale>billion|million|thousand|mm|[kmb])?"
    r"(?![a-z]))"
    r"|(?P<pct>(?<![\w.])(?P<pnum>-?\d+(?:\.\d+)?)\s?%)"
    r"|(?P<mult>(?<![\w.$])(?P<xnum>\d+(?:\.\d+)?)\s?x(?![a-z])(?!\s*\d))"
    r"|(?P<sf>(?<![\w.$])(?P<snum>\d[\d,]*(?:\.\d+)?)\s?(?P<sk>k)?\s?-?\s?"
    r"(?:rsf|sf|s\.f\.|sq\.?\s?ft\.?|square feet)(?![a-z]))",
    re.I,
)
_UNIT = r"(?:%|x|/sf|[kmb]|mm|million|thousand)?"
# A figure that is one end of a range ("$9.00–$9.60", "$1.1M–$1.2M", "14–17%", "8 to 10%").
RANGE_PRE = re.compile(r"\d" + _UNIT + r"\s*[–—-]\s*\$?$|\d" + _UNIT + r"\s+to\s+\$?$", re.I)
RANGE_POST = re.compile(r"\s*[–—-]\s*\$?\d|\s+to\s+\$?\d")
BETWEEN_PRE = re.compile(r"\bbetween\b(?:(?!\.\s)[^;:]){0,30}$", re.I)  # stops at a sentence end, not a decimal point
APPROX_PRE = re.compile(r"(?:[~≈]|\bapprox(?:imately|\.)?|\babout|\broughly|\bcirca|"
                        r"\bestimated(?:\s+at)?|\best\.)\s*\$?$", re.I)


@dataclass
class Claim:
    text: str
    kind: str          # money | pct | mult | sf
    value: float       # in model units: money in $, pct as fraction, mult raw, sf raw
    half_unit: float   # display rounding half-step, in the same units as value
    context: str
    metric: str | None
    paragraph: int
    in_range: bool = False
    digits: str = ""      # the figure's numeric text as printed, for transposition checks
    approx: bool = False  # "~$100K", "estimated at 1.5x": a narrative estimate, never a CONFLICT
    threshold: bool = False  # stated as a floor/limit/target, so it may tie a threshold cell
    bound: bool = False   # metric keyword adjacent to the figure (CONFLICT is reserved for these)
    year: str | None = None  # "Year 1 DSCR": prefer cells labelled for the same year
    quals: list[str] = field(default_factory=list)  # going-in / exit / levered / stabilized ...
    sf_type: str | None = None  # rentable / land / building ... for SF figures


@dataclass
class Cell:
    sheet: str
    ref: str
    value: float
    is_pct_fmt: bool
    label: str


@dataclass
class Result:
    claim: Claim
    status: str
    cell: str | None = None
    cell_value: float | None = None
    cell_label: str | None = None
    note: str = ""
    candidates: list[str] = field(default_factory=list)


# ---------------------------------------------------------------- memo parsing
def read_docx_paragraphs(path: Path) -> list[str]:
    """Body plus footnotes/endnotes. Raises ValueError on anything that is not a readable .docx."""
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "word/document.xml" not in names:
                raise ValueError(f"{path.name} is not a Word document (no word/document.xml)")
            parts = ["word/document.xml"] + sorted(
                n for n in names if re.match(r"word/(footnotes|endnotes)\.xml$", n))
            paras: list[str] = []
            for part in parts:
                root = ET.fromstring(z.read(part))
                for p in root.iter(f"{W_NS}p"):
                    txt = "".join(
                        (t.text or "") if t.tag == f"{W_NS}t" else "\t"
                        for t in p.iter()
                        if t.tag in (f"{W_NS}t", f"{W_NS}tab")
                    ).strip()
                    if txt:
                        paras.append(txt)
    except zipfile.BadZipFile as e:
        raise ValueError(f"{path.name} is not a readable .docx: {e}") from e
    except ET.ParseError as e:
        raise ValueError(f"{path.name} has malformed XML: {e}") from e
    return paras


def _decimals(num: str) -> int:
    return len(num.split(".")[1]) if "." in num else 0


def _kind_of(m: re.Match) -> str:
    return next(k for k in ("money", "pct", "mult", "sf") if m.group(k))


def _metric_for(before: str, after: str, kind: str) -> tuple[str | None, int]:
    """(metric, chars between keyword and figure). A metric word right after the figure
    ("65% LTV") wins at distance 0; else the nearest one before it."""
    trailing = None
    for key, rx in METRIC_RE.items():
        if kind not in METRIC_KINDS[key]:
            continue
        m = rx.search(after)
        if m and m.start() <= 3 and (trailing is None or m.start() < trailing[1]):
            trailing = (key, m.start())
    if trailing:
        return trailing[0], 0
    best, best_pos, best_start = None, -1, -1
    for key, rx in METRIC_RE.items():
        if kind not in METRIC_KINDS[key]:
            continue
        for m in rx.finditer(before):
            if m.end() > best_pos:
                best, best_pos, best_start = key, m.end(), m.start()
    # The keyword already belongs to another figure when one sits between it and this figure
    # ("LTV 65%, 6.0%") or a figure trails into it ("65% LTV, 6.0%"). A bare number does not
    # count: in "Year 3 DSCR of 1.40x" the year number does not steal DSCR from the figure.
    if best:
        ok = METRIC_KINDS[best]
        between = [m for m in CLAIM_RE.finditer(before[best_pos:]) if _kind_of(m) in ok]
        trailing = [m for m in CLAIM_RE.finditer(before[:best_start])
                    if best_start - 2 <= m.end() <= best_start and _kind_of(m) in ok]
        if between or trailing:  # only a figure of a kind the metric describes can own it
            return None, 999
    return best, (len(before) - best_pos if best else 999)


# A keyword this close binds the figure to its metric ("DSCR of 1.25x", "NOI: $250,000").
BIND_DISTANCE = 15


def extract_claims(paragraphs: list[str], ignore: list[re.Pattern]) -> list[Claim]:
    claims: list[Claim] = []
    for pi, para in enumerate(paragraphs):
        # Short paragraphs are usually table cells: borrow the previous cell as label context.
        prev = paragraphs[pi - 1] if pi and len(para) < 30 else ""
        for m in CLAIM_RE.finditer(para):
            raw = m.group(0).strip()
            if any(rx.search(raw) for rx in ignore):
                continue
            s, e = m.start(), m.end()
            lead = (prev[-48:] + " / ") if prev else ""
            before = lead + para[max(0, s - 48): s]
            after = para[e: e + 16]
            ctx = (lead + para[max(0, s - 70): e + 40]).replace("\n", " ")
            in_range = bool(RANGE_PRE.search(para[max(0, s - 12): s]) or RANGE_POST.match(para[e: e + 8])
                            or BETWEEN_PRE.search(para[max(0, s - 40): s]))
            approx = bool(APPROX_PRE.search(para[max(0, s - 16): s]))
            # Only a threshold word hugging the figure ("floor of 1.25x", "1.25x minimum") makes it a
            # threshold statement; "against the lender's minimum, DSCR is 1.25x" reports a result.
            threshold = bool(re.search(THRESH_RE.pattern + r"\s*(?:of|at|is|:)?\s*\$?$", para[max(0, s - 24): s], re.I)
                             or NEXT_THRESH_RE.match(para[e: e + 16]))
            # Qualifiers and area types come only from text after the previous figure, so
            # "Exit cap 8.0%; going-in cap 8.0%" does not leak "exit" into the second figure.
            own = before[-40:]
            prior = list(CLAIM_RE.finditer(own))
            own = own[prior[-1].end():] if prior else own
            quals = {k for k, rx in QUALIFIER_RE.items() if rx.search(own)}
            sf_type = SF_TYPE_RE.findall(own)
            ym = YEAR_TOKEN_RE.findall(before[-30:])
            if m.group("money"):
                num = m.group("mnum").replace(",", "")
                scale = SCALE.get((m.group("mscale") or "").lower(), 1.0)
                lead_ch = para[s - 1] if s else ""
                closes = para[e: e + 1] == ")"
                negative = ((lead_ch == "(" or m.group("mparen")) and closes) or (
                    lead_ch in ("-", "−") and not re.search(r"\d(?:%|x|mm|[kmb])?\s*$", para[: s - 1], re.I))
                val = float(num) * scale * (-1 if negative else 1)
                half = 0.5 * 10 ** (-_decimals(num)) * scale
                kind = "money"
            elif m.group("pct"):
                num = m.group("pnum")
                val = float(num) / 100
                half = 0.5 * 10 ** (-_decimals(num)) / 100
                kind = "pct"
            elif m.group("mult"):
                num = m.group("xnum")
                val = float(num)
                half = 0.5 * 10 ** (-_decimals(num))
                kind = "mult"
            else:
                num = m.group("snum").replace(",", "")
                scale = 1e3 if m.group("sk") else 1.0
                val = float(num) * scale
                half = 0.5 * 10 ** (-_decimals(num)) * scale
                kind = "sf"
            metric, dist = ("sf", 999) if kind == "sf" else _metric_for(before, after, kind)
            claims.append(Claim(raw, kind, val, half, ctx, metric, pi + 1, in_range, num, approx, threshold,
                                bound=bool(metric) and kind != "sf" and dist <= BIND_DISTANCE,
                                year=ym[-1] if ym else None, quals=sorted(quals),
                                sf_type=sf_type[-1].lower() if kind == "sf" and sf_type else None))
    return claims


# --------------------------------------------------------------- model parsing
def _row_label(ws, row: int, col: int) -> str:
    parts = []
    for c in range(col - 1, max(0, col - 6), -1):
        v = ws.cell(row=row, column=c).value
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
            break
    for r in range(row - 1, max(0, row - 3), -1):
        v = ws.cell(row=r, column=col).value
        if isinstance(v, str) and v.strip():
            parts.append(v.strip())
            break
    return " | ".join(parts)


def read_model_cells(path: Path) -> tuple[list[Cell], int]:
    """Return numeric cells with cached values, and the count of formula cells lacking one."""
    import openpyxl  # local import: keeps --help usable without openpyxl

    try:
        wb_vals = openpyxl.load_workbook(path, data_only=True, read_only=False)
        wb_form = openpyxl.load_workbook(path, data_only=False, read_only=False)
    except Exception as e:  # InvalidFileException, BadZipFile, encrypted CFB, corrupt parts
        raise ValueError(f"{path.name} is not a readable workbook: {type(e).__name__}: {e}") from e
    cells: list[Cell] = []
    uncached = 0
    for ws in wb_vals.worksheets:
        wf = wb_form[ws.title]
        for row in ws.iter_rows():
            for c in row:
                v = c.value
                f = wf.cell(row=c.row, column=c.column).value
                if v is None and isinstance(f, str) and f.startswith("="):
                    uncached += 1
                    continue
                if isinstance(v, bool) or not isinstance(v, (int, float)):
                    continue
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    continue
                fmt = c.number_format or ""
                cells.append(Cell(ws.title, c.coordinate, float(v), "%" in fmt,
                                  _row_label(ws, c.row, c.column)))
    return cells, uncached


# --------------------------------------------------------------------- matching
def _labelled(cell: Cell, metric: str | None) -> bool:
    return bool(metric) and bool(METRIC_RE[metric].search(cell.label))


def _is_threshold(cell: Cell) -> bool:
    return bool(THRESH_RE.search(cell.label))


def _is_count(cell: Cell) -> bool:
    # Counts, terms and calendar years are small integers; an $11M price under a "Year" header is not one.
    if not float(cell.value).is_integer() or abs(cell.value) > 2200 or not COUNT_RE.search(cell.label):
        return False
    # "Year 1 NOI" names a metric, so it is not a count cell.
    return not any(rx.search(cell.label) for k, rx in METRIC_RE.items() if k != "sf")


def _candidate_values(claim: Claim, cell: Cell) -> list[float]:
    """Model value(s) expressed in the claim's units; [] when the cell cannot support the claim."""
    if claim.kind == "pct":
        if cell.is_pct_fmt:
            return [cell.value]
        # A whole-number percent (6.85 meaning 6.85%) only from a cell whose label says percent.
        return [cell.value, cell.value / 100] if PCT_LABEL_RE.search(cell.label) else [cell.value]
    return [] if cell.is_pct_fmt else [cell.value]


def _eligible(claim: Claim, cell: Cell) -> bool:
    if _is_threshold(cell) and not claim.threshold:
        return False
    if claim.kind != "sf" and _is_count(cell) and not _labelled(cell, claim.metric):
        return False
    return True


def transposition_hint(claim: Claim, cells: list[Cell]) -> str:
    """Find a model cell whose printed digits are the memo's digits with two swapped."""
    d = claim.digits
    if not d or float(d) == 0:
        return ""
    dec = _decimals(d)
    key = d.replace(".", "").lstrip("-")
    if len(key.strip("0")) < 4:  # "520" vs "250" is coincidence, not a typo signal
        return ""
    unit = abs(claim.value / float(d))  # model units per printed unit (1e6 for "$1.15M", 0.01 for "%")
    for cell in cells:
        for cv in _candidate_values(claim, cell):
            s = f"{abs(cv / unit):.{dec}f}".replace(".", "")
            if len(s) == len(key) and s != key and sorted(s) == sorted(key):
                if sum(a != b for a, b in zip(s, key)) == 2:
                    return f"possible digit transposition: {cell.sheet}!{cell.ref} = {cv / unit:,.{dec}f}"
    return ""


def _match(claim: Claim, pool: list[Cell], near_pct: float):
    tol = claim.half_unit * 1.0001 + 1e-9
    exact, near = [], []
    for cell in pool:
        for cv in _candidate_values(claim, cell):
            d = abs(cv - claim.value)
            if d <= tol:
                exact.append((cell, cv))
            elif claim.value and d / abs(claim.value) <= near_pct / 100:
                near.append((cell, cv, d))
    exact.sort(key=lambda t: (t[0].sheet, t[0].ref))
    near.sort(key=lambda t: (t[2], t[0].sheet, t[0].ref))
    return exact, near


def _soft(cl: Claim) -> str:
    return ("range endpoint — " if cl.in_range else "") + ("approximate figure — " if cl.approx else "")


def tie(claims: list[Claim], cells: list[Cell], near_pct: float) -> list[Result]:
    results: list[Result] = []
    for cl in claims:
        eligible = [c for c in cells if _eligible(cl, c)]
        labelled = [c for c in eligible if _labelled(c, cl.metric)]
        # No false pass: a figure the memo attaches to a metric ties ONLY to a cell labelled with that
        # metric. With no such cell it is UNTIED, never tied to an equal value somewhere else.
        strict = bool(cl.metric) and cl.kind != "sf"  # SF breakdowns are matched by value...
        if cl.kind == "sf" and cl.sf_type:  # ...unless the memo names the area type
            typed = [c for c in eligible if re.search(rf"\b{cl.sf_type}\b", c.label, re.I)]
            if typed:
                labelled, strict = typed, True
        if strict and cl.kind != "sf":
            labelled = [c for c in cells if _labelled(c, cl.metric)]  # threshold split happens below
        pool = labelled if strict else eligible
        if strict and cl.year:  # "Year 1 DSCR 1.10x" must tie the Year 1 cell, not Year 5
            pool = [c for c in pool if any(y == cl.year for y in YEAR_TOKEN_RE.findall(c.label))]
        if strict:
            for q in cl.quals:  # "going-in cap" ties only going-in cells when the model labels them
                narrowed = [c for c in pool if QUALIFIER_RE[q].search(c.label)]
                if narrowed:
                    pool = narrowed
        # Threshold statements compete only with threshold cells (Min DSCR, Max LTV), results only
        # with result cells. Threshold labels are the narrow limit vocabulary, so "Lender DSCR" or
        # "DSCR (lender test)" is a result and competes for AMBIGUOUS.
        if strict and cl.threshold:
            pool = [c for c in pool if _is_threshold(c)] or pool
        elif strict:
            pool = [c for c in pool if not _is_threshold(c)]
        amb_pool = pool
        exact, near = _match(cl, pool, near_pct)
        if exact:
            cell, cv = exact[0]
            # Same quantity = same sign and within 3x of the memo figure; "Vacancy loss -$50,800"
            # next to a vacancy % is a different quantity, not a competing reading.
            # Each competitor is read in the claim's units (a whole-percent cell 72 is 0.72), and a
            # zero counts: "Year 1 CoC 0.0%" competes with a 2.0% pro forma cell.
            def _closest(c: Cell) -> float | None:
                vals = _candidate_values(cl, c)
                return min(vals, key=lambda v: abs(v - cl.value)) if vals else None

            differing = sorted({fmt_val(cl, v) for c in amb_pool if c is not cell
                                for v in [_closest(c)] if v is not None
                                and abs(v - cl.value) > cl.half_unit * 1.0001
                                and (v == 0 or (v * cl.value > 0 and 1 / 5 <= v / cl.value <= 5))})
            if strict and differing:
                # Several cells carry this metric and the memo does not say which one it means.
                results.append(Result(cl, "AMBIGUOUS", f"{cell.sheet}!{cell.ref}", cv, cell.label,
                                      f"ambiguous: ties {cell.sheet}!{cell.ref} but other '{cl.metric}' cells "
                                      f"hold {', '.join(differing[:3])}; name the year or case in the memo"))
                continue
            results.append(Result(cl, "TIED", f"{cell.sheet}!{cell.ref}", cv, cell.label, "",
                                  [f"{c.sheet}!{c.ref}" for c, _ in exact[:5]]))
            continue
        if near:
            cell, cv, _ = near[0]
            results.append(Result(cl, "NEAR", f"{cell.sheet}!{cell.ref}", cv, cell.label,
                                  "within tolerance but outside the memo's display rounding"))
            continue
        elsewhere = ""
        if strict:
            others, _ = _match(cl, [c for c in eligible if c not in labelled], near_pct)
            if others:
                c, _ = others[0]
                elsewhere = (f"; the same value sits at {c.sheet}!{c.ref} ('{c.label[:40]}'), "
                             f"which is not a '{cl.metric}' cell")
        vals = sorted(((c, v) for c in pool for v in _candidate_values(cl, c)), key=lambda t: abs(t[1] - cl.value))
        if strict and cl.bound and vals and not (cl.in_range or cl.approx or cl.threshold):
            c, v = vals[0]
            results.append(Result(cl, "CONFLICT", f"{c.sheet}!{c.ref}", v, c.label,
                                  f"memo states {cl.text}; nearest '{cl.metric}'-labelled model cell holds "
                                  f"{fmt_val(cl, v)}{elsewhere}",
                                  [f"{x.sheet}!{x.ref}={fmt_val(cl, y)}" for x, y in vals[:4]]))
            continue
        why = (f"no '{cl.metric}'-labelled model cell matches" if strict and vals
               else f"the model has no usable '{cl.metric}'-labelled cell" if strict
               else "no model cell supports this figure")
        results.append(Result(cl, "UNTIED", note=_soft(cl) + why + elsewhere))
    for r in results:
        if r.status != "TIED":
            hint = transposition_hint(r.claim, cells)
            if hint:
                r.note = f"{hint}; {r.note}"
    return results


# ---------------------------------------------------------------------- report
def fmt_val(cl: Claim, v: float) -> str:
    if cl.kind == "money":
        return f"${v:,.0f}" if abs(v) >= 10_000 else f"${v:,.2f}"
    if cl.kind == "pct":
        return f"{v * 100:.2f}%" if abs(v) < 5 else f"{v:.2f}"
    if cl.kind == "mult":
        return f"{v:.2f}x"
    return f"{v:,.0f}"


def _version(name: str) -> str | None:
    m = re.search(r"v(\d+(?:\.\d+)?)", name, re.I)
    return m.group(1) if m else None


def render_md(memo: Path, model: Path, results: list[Result], uncached: int, warnings: list[str]) -> str:
    counts = {s: sum(r.status == s for r in results) for s in ("TIED", "NEAR", *FAILING)}
    total = len(results) or 1
    lines = [
        "# IC Memo ↔ Model Tie-Out",
        "",
        f"- **Memo:** `{memo.name}`",
        f"- **Model:** `{model.name}`",
        f"- **Figures checked:** {len(results)} · TIED {counts['TIED']} · NEAR {counts['NEAR']} · "
        f"CONFLICT {counts['CONFLICT']} · AMBIGUOUS {counts['AMBIGUOUS']} · UNTIED {counts['UNTIED']} · "
        f"tie rate {counts['TIED'] / total:.0%}",
        f"- **Verdict:** {'PASS' if not any(counts[s] for s in FAILING) else 'FAIL'}",
    ]
    for w in warnings:
        lines.append(f"- ⚠ {w}")
    if uncached:
        lines.append(f"- ⚠ {uncached} formula cell(s) had no cached value and were skipped (--allow-uncached)")
    for status, title in (("CONFLICT", "Conflicts — memo contradicts the model"),
                          ("AMBIGUOUS", "Ambiguous — several model cells carry this metric; name the year or case"),
                          ("UNTIED", "Untied — no model support"),
                          ("NEAR", "Near — rounding/presentation drift")):
        rows = [r for r in results if r.status == status]
        if not rows:
            continue
        lines += ["", f"## {title} ({len(rows)})", "",
                  "| ¶ | Memo figure | Metric | Model cell | Model value | Note | Context |",
                  "|---|---|---|---|---|---|---|"]
        for r in rows:
            cv = fmt_val(r.claim, r.cell_value) if r.cell_value is not None else "—"
            ctx = r.claim.context.replace("|", "/")
            lines.append(f"| {r.claim.paragraph} | {r.claim.text} | {r.claim.metric or '—'} | "
                         f"{r.cell or '—'} | {cv} | {r.note.replace('|', '/')} | …{ctx}… |")
    tied = [r for r in results if r.status == "TIED"]
    if tied:
        lines += ["", f"## Tied ({len(tied)})", "", "| ¶ | Memo figure | Model cell | Label | Note |", "|---|---|---|---|---|"]
        for r in tied:
            lines.append(f"| {r.claim.paragraph} | {r.claim.text} | {r.cell} | "
                         f"{(r.cell_label or '').replace('|', '/')[:60]} | {r.note} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------ main
def run(memo: Path, model: Path, near_pct: float = 0.5, ignore: list[str] | None = None,
        allow_uncached: bool = False):
    for p, exts in ((memo, (".docx",)), (model, (".xlsx", ".xlsm"))):
        if not p.is_file():
            raise FileNotFoundError(f"not found: {p}")
        if p.suffix.lower() not in exts:
            raise ValueError(f"unexpected file type: {p.name}")
    paras = read_docx_paragraphs(memo)
    claims = extract_claims(paras, [re.compile(x, re.I) for x in (ignore or [])])
    if not claims:
        raise ValueError(f"no $, %, x or SF figures found in {memo.name} — wrong file or unreadable memo")
    cells, uncached = read_model_cells(model)
    if uncached and not allow_uncached:
        raise RuntimeError(f"{uncached} formula cell(s) in {model.name} have no cached value (saved by a "
                           "script, not Excel); open and save it in Excel, then re-run, or pass --allow-uncached")
    if not cells:
        raise RuntimeError(f"{model.name} has no numeric cells with values")
    warnings = []
    mv, xv = _version(memo.name), _version(model.name)
    if mv and xv and mv != xv:
        warnings.append(f"version mismatch: memo v{mv} vs model v{xv}")
    return tie(claims, cells, near_pct), uncached, warnings


def _guard_outputs(memo: Path, model: Path, outs: list[Path | None]) -> None:
    import os

    inputs = {memo.resolve(), model.resolve()}
    for out in outs:
        if out is None:
            continue
        if ":" in out.name:  # NTFS alternate data stream ("model.xlsx:ads") writes into the input file
            raise ValueError(f"refusing to write a report to {out.name}: ':' in a file name")
        if out.resolve() in inputs or out.suffix.lower() in (".docx", ".xlsx", ".xlsm", ".xls", ".doc"):
            raise ValueError(f"refusing to write a report to {out.name}: it is an input or an Office file")
        if out.exists() and any(p.exists() and os.path.samefile(out, p) for p in (memo, model)):
            raise ValueError(f"refusing to write a report to {out.name}: it is a link to an input")
        if not out.resolve().parent.is_dir():
            raise ValueError(f"report directory does not exist: {out.resolve().parent}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("memo", type=Path)
    ap.add_argument("model", type=Path)
    ap.add_argument("--out", type=Path, help="write Markdown report here (default: stdout)")
    ap.add_argument("--json", type=Path, help="also write machine-readable JSON")
    ap.add_argument("--near-pct", type=float, default=0.5)
    ap.add_argument("--ignore-pattern", action="append", default=[], help="regex; matching memo figures are skipped")
    ap.add_argument("--allow-uncached", action="store_true",
                    help="warn instead of failing when formula cells have no cached value")
    a = ap.parse_args(argv)
    try:
        _guard_outputs(a.memo, a.model, [a.out, a.json])
        results, uncached, warnings = run(a.memo, a.model, a.near_pct, a.ignore_pattern, a.allow_uncached)
    except (FileNotFoundError, ValueError, RuntimeError, KeyError, re.error) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    md = render_md(a.memo, a.model, results, uncached, warnings)
    if a.out:
        a.out.write_text(md, encoding="utf-8")
    else:
        sys.stdout.reconfigure(encoding="utf-8")
        print(md)
    if a.json:
        a.json.write_text(json.dumps({"warnings": warnings, "uncached": uncached,
                                      "results": [asdict(r) for r in results]}, indent=2), encoding="utf-8")
    counts = {s: sum(r.status == s for r in results) for s in FAILING}
    print(f"RESULT_JSON={json.dumps({'figures': len(results), **counts, 'near': sum(r.status == 'NEAR' for r in results)})}",
          file=sys.stderr)
    return 1 if any(counts.values()) else 0


if __name__ == "__main__":
    sys.exit(main())
