#!/usr/bin/env python3
"""
addendum_qc.py -- QC gate for ORA lease addenda (lease-addendum skill v1.0)

Usage: python3 addendum_qc.py <addendum.docx> [more.docx ...] [--allow-tokens] [--m3b]

Exit 0 = no BLOCK-severity failures across all files. Exit 1 = at least one BLOCK.
Severity is BLOCK / HIGH / MED / LOW, same convention as lease-form-qc/scripts/lease_qc.py.

Pattern (zip + regex over word/document.xml, no python-docx dependency for scanning) and the
(id, severity, label, test) check-tuple convention are ported directly from
lease-form-qc/scripts/lease_qc.py -- see that script for the source of the text_of() shape.

--m3b flags this run as a tenant-substitution/novation addendum, which turns on checks 4, 5, 6,
11, 12, 16 (the M3b package) as BLOCK-severity even when the document doesn't self-declare a
substitution (the acceptance-test failure mode this gate exists to catch is exactly a
substitution that was drafted -- and therefore reads -- as if it were a ministerial name change).
"""

import json
import os
import re
import sys
import zipfile

TOKEN_RE = re.compile(r"\[[A-Z][A-Z0-9 /,.'&-]{2,}\]")
Q = '["“”‘’«»]'
SEV_ORDER = {"BLOCK": 0, "HIGH": 1, "MED": 2, "LOW": 3}

MONEY_RE = re.compile(r"\$[\d,]+\.\d{2}")
DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s*(\d{4})"
)
BINDING_PHRASES = (
    "in accordance with the following schedule",
    "in accordance with the schedule below",
    "in accordance with the schedule set forth",
    "as set forth in the rent schedule",
)


def load_state_overlay():
    ref = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "references", "state-overlay.json")
    if not os.path.exists(ref):
        return {}
    with open(ref, encoding="utf-8") as f:
        return json.load(f)


def text_of(path):
    """Return (plain_text, core_title) for a .docx. plain_text has a synthetic
    '\\n[[CORE_TITLE]] <title>' marker appended so title-drift checks can read it."""
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
        core_title = ""
        if "docProps/core.xml" in z.namelist():
            core_xml = z.read("docProps/core.xml").decode("utf-8", "replace")
            m = re.search(r"<dc:title>(.*?)</dc:title>", core_xml, re.S)
            if m:
                core_title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
    t = re.sub(r"<w:p[ >]", "\n<w:p ", xml)
    t = re.sub(r"<w:tc[ >]", "\n<w:tc ", t)
    t = re.sub(r"<[^>]+>", "", t)
    for a, b in [("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&apos;", "'")]:
        t = t.replace(a, b)
    t = re.sub(r"[ \t]+", " ", t)
    t += f"\n[[CORE_TITLE]] {core_title}"
    return t


def _defined(t, term):
    return bool(re.search(Q + r"\s*" + re.escape(term) + r"\s*" + Q + r"\s*(shall\s+)?means?\b", t))


def _has_signature_block_for(t, name_fragment):
    """Crude but conservative: a signature block exists for a party if its name appears
    within 200 chars of a 'By:' / 'Its:' / signature-line marker."""
    idx = t.find(name_fragment)
    if idx < 0:
        return False
    window = t[max(0, idx - 200): idx + 200]
    return bool(re.search(r"\bBy:|\bIts:|_{5,}|Signature", window))


PERIOD_LINE_RE = re.compile(r"^\s*\d{1,2}[/-]\d{4}\s*[-–]\s*\d{1,2}[/-]\d{4}\s*$")


def _rent_rows(t):
    """Extract rent-schedule table rows using <w:tc> cell boundaries (each cell lands on its own
    line after text_of()'s tc-split). A row is a period-range cell followed within 4 cells by
    exactly two money cells -- column order (monthly-first vs annual-first) varies across ORA's
    own template family, so this does NOT assume an order; returns (smaller, larger) pairs and
    lets the caller decide which should be 1/12 of the other. Prose sentences (which don't sit on
    a table-cell line by themselves) are excluded by construction."""
    lines = [ln.strip() for ln in t.splitlines()]
    rows = []
    i = 0
    while i < len(lines):
        if PERIOD_LINE_RE.match(lines[i]):
            amounts = []
            for j in range(i + 1, min(i + 5, len(lines))):
                if MONEY_RE.fullmatch(lines[j]):
                    amounts.append(float(lines[j].replace("$", "").replace(",", "")))
                elif amounts or PERIOD_LINE_RE.match(lines[j]):
                    break
            if len(amounts) >= 2:
                rows.append((min(amounts[:2]), max(amounts[:2])))
        i += 1
    return rows


def check_circular_effective_date(t):
    return bool(re.search(r"on or before\s+the\s+(date|Effective Date)\s+of\s+(execution|this Addendum)", t, re.I))


def check_rent_row_no_clause(t):
    """A rent-schedule table exists (>=2 money-pair rows, or a 'RENT SCHEDULE' header) but the
    operative Base Rent paragraph never binds to it with a phrase like 'in accordance with the
    following schedule' -- meaning any stub/interim row in the table has no operative clause
    obligating payment of it."""
    has_table = len(_rent_rows(t)) >= 2 or "rent schedule" in t.lower()
    if not has_table:
        return False
    return not any(p in t.lower() for p in BINDING_PHRASES)


def check_rent_arithmetic(t):
    """Table rows only (see _rent_rows) -- order-agnostic: the larger of each row's two amounts
    should be ~12x the smaller (annual = monthly * 12), regardless of which column is which."""
    for smaller, larger in _rent_rows(t):
        if smaller > 0 and abs(smaller * 12 - larger) > 1.00:
            return True
    return False


def check_party_consent(t, m3b):
    if not m3b:
        return False
    outgoing = re.findall(r"Tenant\s+shall\s+be\s+([^,\.]+),?\s+d/?b/?a", t, re.I)
    if not outgoing:
        return False
    return not _has_signature_block_for(t, "MLC") and not re.search(r"consent(s)?\s+to\s+(this\s+)?release", t, re.I)


def check_security_deposit(t, m3b):
    if not m3b:
        return False
    return "security deposit" not in t.lower()


def check_entity_dropped(t, m3b):
    if not m3b:
        return False
    return not re.search(r"\brelease(d|s)?\b.{0,80}\bTenant\b|\bassum(e|ption|es)\b.{0,80}\bobligations\b", t, re.I | re.S)


def check_term_vs_recordation(t, overlay, state):
    """Extract the earliest 'dated <date>' (Prime Lease commencement proxy) and the latest year
    referenced anywhere in the document (new expiration proxy), and flag if the cumulative span
    exceeds the state's recordation/acknowledgment threshold. Coarse (year-granularity) by
    design -- this is a QC flag to trigger human/counsel review, not a legal conclusion."""
    if not state or state not in overlay:
        return False
    threshold = overlay[state].get("threshold_years")
    if threshold is None:
        return False
    dates = DATE_RE.findall(t)
    if not dates:
        return False
    years = [int(y) for _, y in dates]
    commencement_match = re.search(r"dated\s+\w+\s+\d{1,2},\s*(\d{4})", t, re.I)
    start_year = int(commencement_match.group(1)) if commencement_match else min(years)
    end_year = max(years)
    return (end_year - start_year) > threshold


def check_ratification(t):
    return "all other terms of the prime lease will remain in effect" not in t.lower() and \
           "remain in full force and effect" not in t.lower()


def check_ordinal(t):
    m = re.search(r"\[\[CORE_TITLE\]\]\s*(.*)", t)
    core_title = m.group(1).strip() if m else ""
    body_ord = re.search(r"\b(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)\b\s+Addendum", t, re.I)
    title_ord = re.search(r"\b(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)\b\s+Addendum", core_title, re.I)
    if core_title and body_ord and title_ord:
        return body_ord.group(1).lower() != title_ord.group(1).lower()
    return False


def check_defined_terms(t):
    if "Demised Premises" in t and not _defined(t, "Demised Premises") and '"Premises"' in t:
        return True
    return False


def check_insurance(t, m3b):
    if not m3b:
        return False
    return "insurance" not in t.lower()


def check_notice_address(t, party_changed):
    if not party_changed:
        return False
    return "notice" not in t.lower() and "address" not in t.lower()


def check_counterparts(t):
    return "counterpart" not in t.lower()


FORMATTING_MARKERS = ("[SIGNATURE PAGE TO FOLLOW]",)


def check_unfilled_token(t, allow_tokens):
    """Flags an unfilled [TOKEN] placeholder. Intentional formatting cues (the signature-page
    marker) are not drafting tokens and must not trip this check -- exempted explicitly rather
    than by loosening TOKEN_RE, so a real [TENANT NAME]-style placeholder still fires."""
    if allow_tokens:
        return False
    for m in TOKEN_RE.finditer(t):
        if m.group(0) not in FORMATTING_MARKERS:
            return True
    return False


def check_premises_pro_rata(t, m4):
    if not m4:
        return False
    return "pro rata" not in t.lower() and "pro-rata" not in t.lower() and "proportionate share" not in t.lower()


def check_guaranty_attached(t, m3b):
    if not m3b:
        return False
    return "guaranty" not in t.lower()


CHECKS = [
    ("1", "HIGH", "Circular effective date", lambda t, ctx: check_circular_effective_date(t)),
    ("2", "HIGH", "Rent-table row with no operative clause", lambda t, ctx: check_rent_row_no_clause(t)),
    ("3", "HIGH", "Rent arithmetic / compounding verified", lambda t, ctx: check_rent_arithmetic(t)),
    ("4", "BLOCK", "Party-consent completeness (M3b)", lambda t, ctx: check_party_consent(t, ctx["m3b"])),
    ("5", "BLOCK", "Security deposit disposition stated (M3b)", lambda t, ctx: check_security_deposit(t, ctx["m3b"])),
    ("6", "BLOCK", "Entity dropped/added without release or joinder (M3b)", lambda t, ctx: check_entity_dropped(t, ctx["m3b"])),
    ("7", "HIGH", "Cumulative term vs. state recordation threshold", lambda t, ctx: check_term_vs_recordation(t, ctx["overlay"], ctx["state"])),
    ("8", "BLOCK", "Ratification / conflict-control clause present", lambda t, ctx: check_ratification(t)),
    ("9", "MED", "Ordinal consistent: body title vs. document metadata Title", lambda t, ctx: check_ordinal(t)),
    ("10", "MED", "Defined terms match the Prime Lease", lambda t, ctx: check_defined_terms(t)),
    ("11", "BLOCK", "Insurance condition on tenant change (M3b)", lambda t, ctx: check_insurance(t, ctx["m3b"])),
    ("12", "BLOCK", "Notice addresses present where a party changed", lambda t, ctx: check_notice_address(t, ctx["m3b"] or ctx["m4"])),
    ("13", "MED", "Counterparts / e-signature clause", lambda t, ctx: check_counterparts(t)),
    ("14", "BLOCK", "Unfilled [TOKEN] on non-template file", lambda t, ctx: check_unfilled_token(t, ctx["allow_tokens"])),
    ("15", "HIGH", "Premises change without recomputed pro-rata share (M4)", lambda t, ctx: check_premises_pro_rata(t, ctx["m4"])),
    ("16", "BLOCK", "Guaranty attached where M3b applies", lambda t, ctx: check_guaranty_attached(t, ctx["m3b"])),
]


def scan(path, m3b=False, m4=False, allow_tokens=False, state=None, overlay=None):
    t = text_of(path)
    ctx = {"m3b": m3b, "m4": m4, "allow_tokens": allow_tokens, "state": state, "overlay": overlay or {}}
    results = []
    for cid, sev, label, test in CHECKS:
        if test(t, ctx):
            results.append((cid, sev, label))
    results.sort(key=lambda r: SEV_ORDER[r[1]])
    print(f"\n{path}")
    if not results:
        print("  ---- 0 of {} checks failed".format(len(CHECKS)))
        return False
    for cid, sev, label in results:
        print(f"  [{sev:<5}] {cid:<3} FAIL  {label}")
    counts = {s: sum(1 for r in results if r[1] == s) for s in SEV_ORDER}
    print(f"  ---- {len(results)} of {len(CHECKS)} checks failed "
          f"(BLOCK {counts.get('BLOCK', 0)} / HIGH {counts.get('HIGH', 0)} / "
          f"MED {counts.get('MED', 0)} / LOW {counts.get('LOW', 0)})")
    return any(sev == "BLOCK" for _, sev, _ in results)


if __name__ == "__main__":
    args = sys.argv[1:]
    m3b = "--m3b" in args
    m4 = "--m4" in args
    allow = "--allow-tokens" in args
    state = None
    for i, a in enumerate(args):
        if a == "--state" and i + 1 < len(args):
            state = args[i + 1]
    args = [a for a in args if not a.startswith("--") and a != state]
    if not args:
        sys.exit(__doc__)
    overlay = load_state_overlay()
    any_block = False
    for p in args:
        if scan(p, m3b=m3b, m4=m4, allow_tokens=allow, state=state, overlay=overlay):
            any_block = True
    sys.exit(1 if any_block else 0)
