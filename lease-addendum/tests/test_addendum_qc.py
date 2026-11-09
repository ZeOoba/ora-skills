#!/usr/bin/env python3
"""
Regression tests for addendum_qc.py's retrofit onto the shared ora_doc_qc
module.

Stdlib only (plus reportlab, for regenerating the PDF fixture) — run with
`python lease-addendum/tests/test_addendum_qc.py`. No pytest, matching
lease-form-qc/tests/test_lease_qc.py and tools/test_*.py.

WHY THIS FILE EXISTS
--------------------
addendum_qc.py's pre-retrofit text_of() was unconditional
`zipfile.ZipFile(path)` — no format branch at all. A PDF (or any non-.docx
path) raised an uncaught zipfile.BadZipFile, crashing the whole run at exit
code 1 — indistinguishable, at the exit code, from "found a real
BLOCK-severity defect" (the __main__ block also exits 1 when any_block is
True). There was also no word-count floor: a near-empty .docx ran all 16
checks against a handful of words rather than being flagged as unreadable.

This is the same FAMILY of defect fixed in pma-qc/listing-agreement-qc/
lease-form-qc (no real format detection before applying a format-specific
parser to file bytes) but a DIFFERENT shape: a hard crash rather than a
false-clean or a mojibake false-BLOCK-storm, because addendum_qc.py's
text_of() had no fallback branch to fall through to.

THE PARITY TEST IS THE CENTRE OF THIS FILE
------------------------------------------
_original_text_of() and _ORIGINAL_CHECKS below are FROZEN VERBATIM COPIES of
the pre-retrofit implementation (this worktree, before the ora_doc_qc
retrofit commit). They exist only so the tests can evaluate every one of the
16 original checks the OLD way and the NEW way over the same fixtures and
assert the verdicts match. They are reference oracles for equivalence
testing — never import them from the live script, never let them drift
toward it, and never "fix" them.

Checks 2 and 3 could NOT be mechanically pointed at ctx["t"]: ora_doc_qc.norm()
collapses all whitespace, newlines included, and _rent_rows() depends on each
rent-schedule table cell landing on its own line (the pre-retrofit text_of()
guaranteed this via `<w:tc>`/`<w:p>` -> newline substitution). ctx["t"] would
silently zero out every parsed row — checks 2 and 3 would never fire again on
any real defect, a silent false-negative in exactly the checks that verify
rent-schedule arithmetic. Both are pointed at ctx["raw"] instead (the shared
module's un-normalized body), the same fix lease-form-qc's A2 needed for its
own re.M anchor.

Check 9 (ordinal consistency) previously depended on a `[[CORE_TITLE]] <title>`
marker text_of() spliced onto the body — the same pattern that caused
lease-form-qc's F18 to trip on its own `[[FOOTER]]` marker (this one happened
not to collide with TOKEN_RE, because TOKEN_RE's character class lacks '_',
but that was luck, not design). It now reads a cleanly-extracted
`ctx["core_title"]` instead of re-parsing a marker out of scanned text.
"""

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
ADDENDUM_QC = SCRIPTS / "addendum_qc.py"
PDF_FIXTURE = HERE / "no_text_layer_fixture.pdf"

sys.path.insert(0, str(SCRIPTS))


# --------------------------------------------------------------------------
# Frozen pre-retrofit reference oracle. Do not modify.
# --------------------------------------------------------------------------

def _original_text_of(path):
    """VERBATIM copy of addendum_qc.text_of() as it existed before the
    ora_doc_qc retrofit. Reference only — unconditional zipfile.ZipFile(path),
    no format branch. Raises zipfile.BadZipFile on a non-.docx path; that is
    the defect this retrofit closes, reproduced here on purpose."""
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


_OQ = '["“”‘’\xab\xbb]'


def _orig_defined(t, term):
    return bool(re.search(_OQ + r"\s*" + re.escape(term) + r"\s*" + _OQ + r"\s*(shall\s+)?means?\b", t))


_ORD_RE = r"\b(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth)\b\s+Addendum"

_ORIG_MONEY_RE = re.compile(r"\$[\d,]+\.\d{2}")
_ORIG_PERIOD_LINE_RE = re.compile(r"^\s*\d{1,2}[/-]\d{4}\s*[-–]\s*\d{1,2}[/-]\d{4}\s*$")
_ORIG_BINDING_PHRASES = (
    "in accordance with the following schedule",
    "in accordance with the schedule below",
    "in accordance with the schedule set forth",
    "as set forth in the rent schedule",
)
_ORIG_DATE_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December)"
    r"\s+\d{1,2},\s*(\d{4})"
)


def _orig_rent_rows(t):
    lines = [ln.strip() for ln in t.splitlines()]
    rows = []
    i = 0
    while i < len(lines):
        if _ORIG_PERIOD_LINE_RE.match(lines[i]):
            amounts = []
            for j in range(i + 1, min(i + 5, len(lines))):
                if _ORIG_MONEY_RE.fullmatch(lines[j]):
                    amounts.append(float(lines[j].replace("$", "").replace(",", "")))
                elif amounts or _ORIG_PERIOD_LINE_RE.match(lines[j]):
                    break
            if len(amounts) >= 2:
                rows.append((min(amounts[:2]), max(amounts[:2])))
        i += 1
    return rows


def _orig_has_sig_block(t, name_fragment):
    idx = t.find(name_fragment)
    if idx < 0:
        return False
    window = t[max(0, idx - 200): idx + 200]
    return bool(re.search(r"\bBy:|\bIts:|_{5,}|Signature", window))


# The 16 pre-retrofit (id, sev, label, test(t, ctx)) tuples, verbatim.
_ORIGINAL_CHECKS = [
    ("1", "HIGH", "Circular effective date",
     lambda t, ctx: bool(re.search(r"on or before\s+the\s+(date|Effective Date)\s+of\s+(execution|this Addendum)", t, re.I))),
    ("2", "HIGH", "Rent-table row with no operative clause",
     lambda t, ctx: (len(_orig_rent_rows(t)) >= 2 or "rent schedule" in t.lower())
     and not any(p in t.lower() for p in _ORIG_BINDING_PHRASES)),
    ("3", "HIGH", "Rent arithmetic / compounding verified",
     lambda t, ctx: any(s > 0 and abs(s * 12 - l) > 1.00 for s, l in _orig_rent_rows(t))),
    ("4", "BLOCK", "Party-consent completeness (M3b)",
     lambda t, ctx: ctx["m3b"] and bool(re.findall(r"Tenant\s+shall\s+be\s+([^,\.]+),?\s+d/?b/?a", t, re.I))
     and not _orig_has_sig_block(t, "MLC") and not re.search(r"consent(s)?\s+to\s+(this\s+)?release", t, re.I)),
    ("5", "BLOCK", "Security deposit disposition stated (M3b)",
     lambda t, ctx: ctx["m3b"] and "security deposit" not in t.lower()),
    ("6", "BLOCK", "Entity dropped/added without release or joinder (M3b)",
     lambda t, ctx: ctx["m3b"] and not re.search(
         r"\brelease(d|s)?\b.{0,80}\bTenant\b|\bassum(e|ption|es)\b.{0,80}\bobligations\b", t, re.I | re.S)),
    ("7", "HIGH", "Cumulative term vs. state recordation threshold",
     lambda t, ctx: _orig_term_vs_recordation(t, ctx["overlay"], ctx["state"])),
    ("8", "BLOCK", "Ratification / conflict-control clause present",
     lambda t, ctx: "all other terms of the prime lease will remain in effect" not in t.lower()
     and "remain in full force and effect" not in t.lower()),
    ("9", "MED", "Ordinal consistent: body title vs. document metadata Title",
     lambda t, ctx: _orig_check_ordinal(t)),
    ("10", "MED", "Defined terms match the Prime Lease",
     lambda t, ctx: "Demised Premises" in t and not _orig_defined(t, "Demised Premises") and '"Premises"' in t),
    ("11", "BLOCK", "Insurance condition on tenant change (M3b)",
     lambda t, ctx: ctx["m3b"] and "insurance" not in t.lower()),
    ("12", "BLOCK", "Notice addresses present where a party changed",
     lambda t, ctx: (ctx["m3b"] or ctx["m4"]) and "notice" not in t.lower() and "address" not in t.lower()),
    ("13", "MED", "Counterparts / e-signature clause",
     lambda t, ctx: "counterpart" not in t.lower()),
    ("14", "BLOCK", "Unfilled [TOKEN] on non-template file",
     lambda t, ctx: _orig_check_unfilled_token(t, ctx["allow_tokens"])),
    ("15", "HIGH", "Premises change without recomputed pro-rata share (M4)",
     lambda t, ctx: ctx["m4"] and "pro rata" not in t.lower() and "pro-rata" not in t.lower()
     and "proportionate share" not in t.lower()),
    ("16", "BLOCK", "Guaranty attached where M3b applies",
     lambda t, ctx: ctx["m3b"] and "guaranty" not in t.lower()),
]

_ORIG_TOKEN_RE = re.compile(r"\[[A-Z][A-Z0-9 /,.'&-]{2,}\]")
_ORIG_FORMATTING_MARKERS = ("[SIGNATURE PAGE TO FOLLOW]",)


def _orig_check_unfilled_token(t, allow_tokens):
    if allow_tokens:
        return False
    for m in _ORIG_TOKEN_RE.finditer(t):
        if m.group(0) not in _ORIG_FORMATTING_MARKERS:
            return True
    return False


def _orig_check_ordinal(t):
    m = re.search(r"\[\[CORE_TITLE\]\]\s*(.*)", t)
    core_title = m.group(1).strip() if m else ""
    body_ord = re.search(_ORD_RE, t, re.I)
    title_ord = re.search(_ORD_RE, core_title, re.I)
    if core_title and body_ord and title_ord:
        return body_ord.group(1).lower() != title_ord.group(1).lower()
    return False


def _orig_term_vs_recordation(t, overlay, state):
    if not state or state not in overlay:
        return False
    threshold = overlay[state].get("threshold_years")
    if threshold is None:
        return False
    dates = _ORIG_DATE_RE.findall(t)
    if not dates:
        return False
    years = [int(y) for _, y in dates]
    commencement_match = re.search(r"dated\s+\w+\s+\d{1,2},\s*(\d{4})", t, re.I)
    start_year = int(commencement_match.group(1)) if commencement_match else min(years)
    end_year = max(years)
    return (end_year - start_year) > threshold


def _original_verdicts(path, m3b=False, m4=False, allow_tokens=False, state=None, overlay=None):
    """{id: bool} for all 16 checks, computed the pre-retrofit way."""
    t = _original_text_of(path)
    is_template = "TEMPLATE" in path.upper()
    ctx = {"m3b": m3b, "m4": m4, "allow_tokens": allow_tokens or is_template,
           "state": state, "overlay": overlay or {}}
    return {cid: bool(test(t, ctx)) for cid, _sev, _label, test in _ORIGINAL_CHECKS}


def _new_verdicts(path, m3b=False, m4=False, allow_tokens=False, state=None, overlay=None):
    """{id: bool} for the retrofitted checks, driven through the live module."""
    import addendum_qc
    from ora_doc_qc import extract, norm

    body, meta = extract(path)
    if body is None:
        raise AssertionError(f"fixture {path} extracted as UNREADABLE ({meta['words']} words); pad it past the floor")
    core_title = addendum_qc._docx_title(path) if meta["format"] == "docx" else ""
    is_template = "TEMPLATE" in os.path.basename(path).upper()
    combined = body + (f"\n{core_title}" if core_title else "")
    ctx = {"t": norm(combined), "raw": body, "meta": meta, "core_title": core_title,
           "m3b": m3b, "m4": m4, "state": state, "overlay": overlay or {},
           "allow_tokens": allow_tokens or is_template}
    out = {}
    for cid, _sev, _title, _pos, fn in addendum_qc.CHECKS:
        out[cid] = fn(ctx) not in (None, False)
    return out


# --------------------------------------------------------------------------
# Synthetic DOCX construction
# --------------------------------------------------------------------------

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '</Types>'
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Target="word/document.xml" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>'
    '</Relationships>'
)
_CORE_XML = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
    'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>%s</dc:title></cp:coreProperties>'
)

# ~190 words of neutral addendum-ish filler that deliberately avoids every
# phrase any of the 16 checks tests for (counterpart, guaranty, insurance,
# security deposit, notice, address, pro rata, remain in effect/force,
# rent schedule) so it establishes a clean "nothing fires by accident"
# baseline. extract() drops anything under DEFAULT_MIN_WORDS (150) as
# UNREADABLE, so every synthetic DOCX must clear that floor.
_FILLER = " ".join([
    "This instrument amends certain provisions of an existing tenancy between",
    "the parties identified in the preamble hereto for all purposes stated",
    "herein and for the mutual exchange of value between the parties.",
    "The recitals set forth above are incorporated into the operative",
    "provisions of this instrument by this reference as though fully",
    "restated herein in their entirety for every purpose of construction.",
    "Any capitalized term used but not otherwise given an operative",
    "definition shall carry the meaning ordinarily ascribed to it in",
    "commercial practice among sophisticated parties to similar instruments.",
    "The headings used throughout this instrument are inserted solely for",
    "convenience of reference and shall not affect the construction of",
    "any provision hereof by any court of competent jurisdiction hereafter.",
    "If a provision of this instrument is held invalid or unenforceable by",
    "a court of competent jurisdiction, the remaining provisions shall",
    "continue in effect to the maximum extent permitted by applicable law,",
    "and the parties shall negotiate in good faith a substitute provision",
    "that most nearly achieves the originally intended commercial result.",
    "This instrument sets forth the entire understanding of the parties on",
    "the subject matter addressed herein and supersedes prior discussions.",
])


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _paras(texts):
    return "".join(f'<w:p><w:r><w:t xml:space="preserve">{_esc(x)}</w:t></w:r></w:p>'
                   for x in texts)


def _table_xml(rows):
    """rows: [(period_text, amount_a, amount_b), ...] -> <w:tbl> XML with each
    cell on its own <w:p>, matching a real ORA rent-schedule table."""
    trs = []
    for period, a, b in rows:
        cells = "".join(
            f'<w:tc><w:p><w:r><w:t xml:space="preserve">{_esc(c)}</w:t></w:r></w:p></w:tc>'
            for c in (period, a, b)
        )
        trs.append(f"<w:tr>{cells}</w:tr>")
    return f"<w:tbl>{''.join(trs)}</w:tbl>"


def make_docx(path, body_paras, table_rows=None, core_title=None):
    """Write a minimal but structurally real .docx.

    body_paras: list of paragraph strings (filler is appended automatically
    so the document clears extract()'s 150-word UNREADABLE floor).
    table_rows: optional rent-schedule table, see _table_xml.
    core_title: None omits docProps/core.xml entirely; a string writes dc:title.
    """
    paras = list(body_paras) + [_FILLER]
    body_xml = _paras(paras)
    if table_rows:
        body_xml += _table_xml(table_rows)
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{body_xml}</w:body></w:document>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", doc)
        if core_title is not None:
            z.writestr("docProps/core.xml", _CORE_XML % _esc(core_title))
    return str(path)


def run_cli(*args):
    """Invoke addendum_qc.py as a subprocess. Returns (returncode, stdout+stderr)."""
    p = subprocess.run([sys.executable, str(ADDENDUM_QC), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp(prefix="addendum_qc_test_")
        self.tmp = Path(self._td)

    def tearDown(self):
        shutil.rmtree(self._td, ignore_errors=True)


# --------------------------------------------------------------------------
# 1. Extraction / the UNREADABLE gate — the bug this retrofit exists to close
# --------------------------------------------------------------------------

class TestUnreadableGate(TempDirCase):

    def test_pdf_is_unreadable_not_crashed(self):
        """Pre-retrofit this PDF raised an uncaught zipfile.BadZipFile,
        crashing the run at exit code 1 — the same exit code as 'found a
        real BLOCK-severity defect'. It must now return a clean UNREADABLE
        result at a distinct exit code instead of a traceback."""
        self.assertTrue(PDF_FIXTURE.exists(), "run build_no_text_layer_fixture.py")
        rc, out = run_cli(str(PDF_FIXTURE))
        self.assertEqual(rc, 2, f"expected exit 2 (UNREADABLE), got {rc}\n{out}")
        self.assertIn("UNREADABLE", out)
        self.assertNotIn("Traceback", out)
        self.assertNotIn("BadZipFile", out)

    def test_unreadable_result_is_not_reported_as_clean(self):
        rc, out = run_cli(str(PDF_FIXTURE))
        self.assertNotIn("0 of 16 checks failed", out)
        self.assertNotEqual(rc, 0)

    def test_pdf_is_detected_as_pdf_format(self):
        rc, out = run_cli(str(PDF_FIXTURE))
        self.assertIn("pdf", out.lower(), f"format detection missing:\n{out}")

    def test_missing_file_exits_nonzero_gracefully(self):
        rc, out = run_cli(str(self.tmp / "does_not_exist.docx"))
        self.assertNotEqual(rc, 0)
        self.assertNotIn("Traceback", out)

    def test_near_empty_docx_is_unreadable_not_scored_clean(self):
        """A docx with only a couple of words of real body text (well under
        the 150-word floor) must not silently run all 16 checks and report
        clean — it has essentially nothing for the scanner to have read."""
        path = self.tmp / "tiny.docx"
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("[Content_Types].xml", _CONTENT_TYPES)
            z.writestr("_rels/.rels", _RELS)
            doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                   '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                   '<w:body><w:p><w:r><w:t>Short.</w:t></w:r></w:p></w:body></w:document>')
            z.writestr("word/document.xml", doc)
        rc, out = run_cli(str(path))
        self.assertEqual(rc, 2, f"expected exit 2 (UNREADABLE), got {rc}\n{out}")
        self.assertIn("UNREADABLE", out)


# --------------------------------------------------------------------------
# 2. Check 9 — the [[CORE_TITLE]] marker rewrite
# --------------------------------------------------------------------------

class TestCoreTitleOrdinal(TempDirCase):

    def test_ordinal_mismatch_detected_via_metadata_title(self):
        path = make_docx(self.tmp / "a.docx",
                          ["This Second Addendum amends the Prime Lease."],
                          core_title="Third Addendum to Lease")
        self.assertTrue(_new_verdicts(path)["9"])

    def test_ordinal_match_no_defect(self):
        path = make_docx(self.tmp / "b.docx",
                          ["This Second Addendum amends the Prime Lease."],
                          core_title="Second Addendum to Lease")
        self.assertFalse(_new_verdicts(path)["9"])

    def test_no_title_metadata_no_false_positive(self):
        path = make_docx(self.tmp / "c.docx",
                          ["This Second Addendum amends the Prime Lease."],
                          core_title=None)
        self.assertFalse(_new_verdicts(path)["9"])

    def test_docx_title_helper_handles_missing_core_xml(self):
        import addendum_qc
        path = make_docx(self.tmp / "d.docx", ["Plain body."], core_title=None)
        self.assertEqual(addendum_qc._docx_title(path), "")


# --------------------------------------------------------------------------
# 3. Rent-table checks (2, 3) — the ctx["raw"] vs ctx["t"] pitfall
# --------------------------------------------------------------------------

class TestRentTableParity(TempDirCase):

    def test_clean_rent_table_no_defect_old_and_new_agree(self):
        path = make_docx(
            self.tmp / "clean.docx",
            ["Base Rent shall be payable in accordance with the following schedule:"],
            table_rows=[("1/2024-12/2024", "$500.00", "$6,000.00")],
        )
        old = _original_verdicts(path)
        new = _new_verdicts(path)
        self.assertFalse(old["2"])
        self.assertFalse(old["3"])
        self.assertEqual(old["2"], new["2"])
        self.assertEqual(old["3"], new["3"])

    def test_missing_binding_clause_fires_check_2_old_and_new_agree(self):
        # check_rent_row_no_clause only treats a table as present at >= 2 rows
        # (or a literal "rent schedule" mention) -- a single row is not
        # "has_table" by the check's own definition, in both old and new.
        path = make_docx(
            self.tmp / "no_clause.docx",
            ["Base Rent during the stub period shall be as set forth below."],
            table_rows=[
                ("1/2024-6/2024", "$500.00", "$6,000.00"),
                ("7/2024-12/2024", "$500.00", "$6,000.00"),
            ],
        )
        old = _original_verdicts(path)
        new = _new_verdicts(path)
        self.assertTrue(old["2"])
        self.assertEqual(old["2"], new["2"])

    def test_arithmetic_mismatch_fires_check_3_old_and_new_agree(self):
        path = make_docx(
            self.tmp / "bad_math.docx",
            ["Base Rent shall be payable in accordance with the following schedule:"],
            table_rows=[("1/2024-12/2024", "$500.00", "$5,000.00")],
        )
        old = _original_verdicts(path)
        new = _new_verdicts(path)
        self.assertTrue(old["3"])
        self.assertEqual(old["3"], new["3"])

    def test_multi_row_table_parity(self):
        path = make_docx(
            self.tmp / "multi.docx",
            ["Base Rent shall be payable in accordance with the following schedule:"],
            table_rows=[
                ("1/2024-6/2024", "$400.00", "$4,800.00"),
                ("7/2024-12/2024", "$450.00", "$5,400.00"),
            ],
        )
        old = _original_verdicts(path)
        new = _new_verdicts(path)
        self.assertEqual(old["2"], new["2"])
        self.assertEqual(old["3"], new["3"])
        self.assertFalse(new["3"])


# --------------------------------------------------------------------------
# 3b. Post-audit fixes (cc-audit-army 2026-08-21) — these DELIBERATELY DIVERGE
# from the frozen pre-retrofit oracle above. The oracle proves the retrofit
# didn't change behavior; these prove two real defects the retrofit carried
# forward unchanged were then fixed. Do not add these to the parity sweep.
# --------------------------------------------------------------------------

class TestPartyConsentUsesParsedName(TempDirCase):
    """M06: check 4 used to test a hardcoded 'MLC' signature block regardless of who the
    outgoing party actually was, so any real substitution flagged BLOCK even when the real
    outgoing party's own signature block was present."""

    def test_real_outgoing_party_signature_block_is_recognized(self):
        path = make_docx(
            self.tmp / "real_party.docx",
            [
                "Tenant shall be Acme Industries, d/b/a AI, released from this Lease.",
                "By: Acme Industries Its: President",
            ],
        )
        old = _original_verdicts(path, m3b=True)
        new = _new_verdicts(path, m3b=True)
        # Old (hardcoded "MLC") never finds Acme Industries's own signature block and always
        # fires — a false BLOCK on a genuinely consented substitution.
        self.assertTrue(old["4"], "sanity: the frozen oracle still hardcodes MLC and fires here")
        self.assertFalse(new["4"], "the fixed check must recognize Acme Industries's own signature block")

    def test_missing_outgoing_party_signature_still_fires(self):
        path = make_docx(
            self.tmp / "no_signature.docx",
            ["Tenant shall be Acme Industries, d/b/a AI, released from this Lease."],
        )
        new = _new_verdicts(path, m3b=True)
        self.assertTrue(new["4"], "no signature block for the real outgoing party must still BLOCK")

    # cc-audit-army code-review finding (2026-08-22): all(), not any() -- a multi-party
    # release where only ONE of two outgoing tenants signed must still BLOCK.
    def test_multi_party_release_blocks_when_only_one_party_signed(self):
        # _has_signature_block_for is a crude +/-200-char window around the FIRST
        # occurrence of a name -- padded here so Beta Holdings' window cannot reach
        # Acme's real signature block above it (that's a pre-existing, separate
        # imprecision in the helper itself, not what this test is pinning; the padding
        # keeps the fixture from tripping over it).
        padding = (
            "The parties acknowledge that all other terms and conditions of the Prime "
            "Lease, as previously amended, remain unmodified and in full force and "
            "effect except as expressly set forth in this instrument, and no other "
            "party shall have any claim arising from this substitution whatsoever."
        )
        path = make_docx(
            self.tmp / "multi_party_partial.docx",
            [
                "Tenant shall be Acme Industries, d/b/a AI, released from this Lease.",
                "By: Acme Industries Its: President",
                padding,
                "Tenant shall be Beta Holdings, d/b/a BH, released from this Lease.",
                # Beta Holdings never gets its own signature block.
            ],
        )
        new = _new_verdicts(path, m3b=True)
        self.assertTrue(new["4"], "one of two released parties having no signature block must still BLOCK")

    def test_multi_party_release_clears_when_both_parties_signed(self):
        path = make_docx(
            self.tmp / "multi_party_full.docx",
            [
                "Tenant shall be Acme Industries, d/b/a AI, released from this Lease.",
                "Tenant shall be Beta Holdings, d/b/a BH, released from this Lease.",
                "By: Acme Industries Its: President",
                "By: Beta Holdings Its: Manager",
            ],
        )
        new = _new_verdicts(path, m3b=True)
        self.assertFalse(new["4"], "both released parties having their own signature block must clear")


class TestRentArithmeticUnparsedAndEscalation(TempDirCase):
    """M08: check 3 only tested annual = monthly x 12 within a row (never row-to-row
    escalation/compounding, despite its own label), and silently PASSED when a rent
    schedule was clearly present but no rows parsed — "nothing wrong" and "couldn't check"
    must not read identically."""

    def test_unparsed_table_is_not_a_silent_pass(self):
        # A literal "rent schedule" mention makes has_table True by the same definition
        # check_rent_row_no_clause uses, but the table cells below don't match the
        # period-line/money-amount shape _rent_rows expects, so zero rows parse.
        path = make_docx(
            self.tmp / "unparsed.docx",
            ["Base Rent is payable per the rent schedule attached as Exhibit A."],
            table_rows=[("See Exhibit A", "TBD", "TBD")],
        )
        old = _original_verdicts(path)
        new_raw = None
        import addendum_qc
        from ora_doc_qc import extract, norm
        body, meta = extract(path)
        ctx = {"t": norm(body), "raw": body}
        new_raw = addendum_qc.check_rent_arithmetic(ctx["raw"])
        self.assertFalse(old["3"], "sanity: the frozen oracle silently passes an unparsed table")
        self.assertIsInstance(new_raw, str, "an unparsed-but-present table must return a distinguishing message, not False/True")
        self.assertIn("could NOT be verified", new_raw)

    def test_escalation_mismatch_is_caught(self):
        path = make_docx(
            self.tmp / "bad_escalation.docx",
            [
                "Base Rent shall be payable in accordance with the following schedule, "
                "escalating at 3.00% annually:",
            ],
            table_rows=[
                ("1/2024-12/2024", "$1,000.00", "$12,000.00"),
                # Correct 3% compounding would be $12,360.00; this is wrong.
                ("1/2025-12/2025", "$1,050.00", "$12,600.00"),
            ],
        )
        old = _original_verdicts(path)
        new = _new_verdicts(path)
        self.assertFalse(old["3"], "sanity: the frozen oracle only checks intra-row 12x math, not escalation")
        self.assertTrue(new["3"], "a stated escalation rate the rows don't actually compound to must fire")

    def test_correct_escalation_does_not_fire(self):
        path = make_docx(
            self.tmp / "good_escalation.docx",
            [
                "Base Rent shall be payable in accordance with the following schedule, "
                "escalating at 3.00% annually:",
            ],
            table_rows=[
                ("1/2024-12/2024", "$1,000.00", "$12,000.00"),
                ("1/2025-12/2025", "$1,030.00", "$12,360.00"),
            ],
        )
        new = _new_verdicts(path)
        self.assertFalse(new["3"], "correctly-compounded escalation must not fire")

    # Audit row addendum-escalation-tolerance-50bp (2026-11-08): the compounding check
    # allowed max($1.00, 0.5% of the expected annual), wide enough that a 3.5% step stated
    # as 3% passed. Now cent-level: each row must reproduce from the prior row under
    # (i) annual compounded or (ii) monthly compounded and rounded each year, within
    # $0.01 x 12 months.
    def _escalation_doc(self, name, rows, rate="3.00"):
        return make_docx(
            self.tmp / name,
            ["Base Rent shall be payable in accordance with the following schedule, "
             f"escalating at {rate}% annually:"],
            table_rows=rows,
        )

    def test_3_5_pct_step_stated_as_3_pct_fires(self):
        path = self._escalation_doc("step_35_as_3.docx", [
            ("1/2024-12/2024", "$1,000.00", "$12,000.00"),
            ("1/2025-12/2025", "$1,035.00", "$12,420.00"),
        ])
        self.assertTrue(_new_verdicts(path)["3"], "a 3.5% step under a stated 3% must fail")

    def test_3_25_pct_step_stated_as_3_pct_fires(self):
        path = self._escalation_doc("step_325_as_3.docx", [
            ("1/2024-12/2024", "$1,000.00", "$12,000.00"),
            ("1/2025-12/2025", "$1,032.50", "$12,390.00"),
        ])
        self.assertTrue(_new_verdicts(path)["3"])

    def test_one_dollar_annual_drift_fires(self):
        path = self._escalation_doc("one_dollar_drift.docx", [
            ("1/2024-12/2024", "$1,000.00", "$12,000.00"),
            ("1/2025-12/2025", "$1,030.08", "$12,361.00"),
        ])
        self.assertTrue(_new_verdicts(path)["3"], "a $1.00 annual drift is not a rounding variant")

    def test_annual_compounded_rounding_variant_passes(self):
        # (i) annual x 1.03 rounded to the cent; monthly = annual / 12.
        path = self._escalation_doc("method_i.docx", [
            ("1/2024-12/2024", "$1,234.56", "$14,814.72"),
            ("1/2025-12/2025", "$1,271.60", "$15,259.16"),
            ("1/2026-12/2026", "$1,309.74", "$15,716.93"),
        ])
        self.assertFalse(_new_verdicts(path)["3"])

    def test_monthly_rounded_each_year_variant_passes(self):
        # (ii) monthly x 1.03 rounded each year; annual = monthly x 12.
        path = self._escalation_doc("method_ii.docx", [
            ("1/2024-12/2024", "$1,234.56", "$14,814.72"),
            ("1/2025-12/2025", "$1,271.60", "$15,259.20"),
            ("1/2026-12/2026", "$1,309.75", "$15,717.00"),
        ])
        self.assertFalse(_new_verdicts(path)["3"])

    # REFUTE pass (2026-11-08): whole-dollar and per-SF schedules are legitimate rounding
    # conventions the cent-level check must still recognise.
    def test_whole_dollar_monthly_schedule_passes(self):
        path = self._escalation_doc("whole_dollar.docx", [
            ("1/2024-12/2024", "$1,000.00", "$12,000.00"),
            ("1/2025-12/2025", "$1,030.00", "$12,360.00"),
            ("1/2026-12/2026", "$1,061.00", "$12,732.00"),
        ])
        self.assertFalse(_new_verdicts(path)["3"])

    def _psf_doc(self, name, rows):
        return make_docx(
            self.tmp / name,
            ["Base Rent for the Premises' 10,000 rentable square feet is initially "
             "$8.00 per square foot per year.",
             "Base Rent shall be payable in accordance with the following schedule, "
             "escalating at 3.00% annually:"],
            table_rows=rows,
        )

    def test_per_sf_rounded_schedule_passes_when_rsf_stated(self):
        path = self._psf_doc("per_sf.docx", [
            ("1/2024-12/2024", "$6,666.67", "$80,000.00"),
            ("1/2025-12/2025", "$6,866.67", "$82,400.00"),
            ("1/2026-12/2026", "$7,075.00", "$84,900.00"),
        ])
        self.assertFalse(_new_verdicts(path)["3"])

    def test_per_sf_without_a_stated_rate_is_not_assumed(self):
        path = make_docx(
            self.tmp / "per_sf_no_rate.docx",
            ["The Premises contain 10,000 rentable square feet.",
             "Base Rent shall be payable in accordance with the following schedule, "
             "escalating at 3.00% annually:"],
            table_rows=[("1/2024-12/2024", "$6,666.67", "$80,000.00"),
                        ("1/2025-12/2025", "$6,866.67", "$82,400.00"),
                        ("1/2026-12/2026", "$7,075.00", "$84,900.00")])
        self.assertTrue(_new_verdicts(path)["3"])

    def test_project_rsf_cannot_widen_the_rounding_step(self):
        # REFUTE round 2: first-match RSF picked the 40,000 SF project, so a $400 step
        # let a 3.33% increase pass under a stated 3%.
        path = make_docx(
            self.tmp / "project_rsf.docx",
            ["Tenant's Proportionate Share of the Premises is 5.00%, being 2,000 / 40,000 "
             "rentable square feet. Base Rent for the Premises' 2,000 rentable square feet is "
             "$12.00 per square foot per year.",
             "Base Rent shall be payable in accordance with the following schedule, "
             "escalating at 3.00% annually:"],
            table_rows=[("1/2024-12/2024", "$2,000.00", "$24,000.00"),
                        ("1/2025-12/2025", "$2,066.67", "$24,800.00")])
        self.assertTrue(_new_verdicts(path)["3"])

    def test_per_sf_path_does_not_admit_a_wrong_rate(self):
        # $8.00 -> $8.28/SF is 3.5%, stated 3%.
        path = self._psf_doc("per_sf_wrong.docx", [
            ("1/2024-12/2024", "$6,666.67", "$80,000.00"),
            ("1/2025-12/2025", "$6,900.00", "$82,800.00"),
        ])
        self.assertTrue(_new_verdicts(path)["3"])

    # cc-audit-army code-review finding (2026-08-22): ESCALATION_RATE_RE used to scan the
    # WHOLE document, so an unrelated clause elsewhere could be picked up as the rent
    # escalation rate. Scoped to a window around the rent-schedule anchor instead.
    def test_unrelated_escalation_language_elsewhere_in_document_is_not_used(self):
        path = make_docx(
            self.tmp / "unrelated_escalation.docx",
            [
                # An unrelated clause with its own percentage, well before the rent
                # schedule -- the OLD (whole-document) regex would grab this 5% first.
                "Tenant's share of Operating Expenses shall increase 5% annually under "
                "Section 8 of the Prime Lease, unaffected by this Addendum.",
                "Base Rent shall be payable in accordance with the following schedule, "
                "escalating at 3.00% annually:",
            ],
            table_rows=[
                ("1/2024-12/2024", "$1,000.00", "$12,000.00"),
                # Correct 3% compounding: $12,360.00. Fixture is intentionally correct at
                # 3% -- if the buggy whole-document search grabbed the unrelated 5% clause
                # instead, this would incorrectly FIRE as a false positive.
                ("1/2025-12/2025", "$1,030.00", "$12,360.00"),
            ],
        )
        new = _new_verdicts(path)
        self.assertFalse(
            new["3"],
            "the correctly-3%-compounded table must not fail check 3 just because an "
            "unrelated 5% OpEx clause appears earlier in the document",
        )


# --------------------------------------------------------------------------
# 4. Full parity sweep — every check, several fixtures, several flag combos
# --------------------------------------------------------------------------

class TestEscalationRound3Repros(unittest.TestCase):
    """Pinned from the round-3 REFUTE probe rr3_add.py (2026-11-08): plain-text schedules
    fed straight to check_rent_arithmetic (one table cell per line)."""

    @staticmethod
    def _doc(rows, pre="", rate="3.00"):
        lines = [pre + "Base Rent shall be payable in accordance with the following schedule, "
                 f"escalating at {rate}% annually:"]
        for i, (m, a) in enumerate(rows):
            lines += [f"1/{2024 + i}-12/{2024 + i}", f"${m:,.2f}", f"${a:,.2f}"]
        return chr(10).join(lines)

    @staticmethod
    def _c(x):
        from decimal import Decimal, ROUND_HALF_UP
        return Decimal(x).quantize(Decimal("0.01"), ROUND_HALF_UP)

    def setUp(self):
        import addendum_qc
        self.q = addendum_qc

    def test_building_rsf_without_a_stated_rate_is_not_used(self):
        pre = ("The Premises are located in the 40,000 SF building and contain 2,000 rentable "
               "square feet. ")
        self.assertTrue(self.q.check_rent_arithmetic(
            self._doc([(2000, 24000), (2066.67, 24800)], pre=pre)))

    def test_coincident_operating_cost_rate_cannot_pair_with_project_rsf(self):
        from decimal import Decimal
        for pre in (
            "Tenant's Proportionate Share is 5.00%, being 2,000 / 40,000 rentable square feet; "
            "estimated Operating Costs are $0.60 per square foot. The Premises contain 2,000 "
            "rentable square feet at $12.00 per square foot per year. ",
            "Tenant's Proportionate Share of the Premises is 5.00%, being 2,000 / 40,000 rentable "
            "square feet, and estimated Operating Costs are $0.60 per square foot. ",
        ):
            with self.subTest(pre=pre[:50]):
                doc = self._doc([(2000, 24000), (2066.67, 24800)], pre=pre)
                self.assertNotEqual(self.q._per_sf_rsf(doc, Decimal("24000.00")), Decimal("40000"))
                self.assertTrue(self.q.check_rent_arithmetic(doc))

    def _psf_rows(self, rsf, psf0, years=5):
        from decimal import Decimal
        psf = [Decimal(psf0)]
        for _ in range(years - 1):
            psf.append(self._c(psf[-1] * Decimal("1.03")))
        return [(float(self._c(p * rsf / 12)), float(p * rsf)) for p in psf]

    def test_legit_per_sf_schedule_passes(self):
        pre = "The Premises contain 10,000 rentable square feet at $8.00 per square foot per year. "
        self.assertFalse(self.q.check_rent_arithmetic(self._doc(self._psf_rows(10000, "8.00"), pre=pre)))

    def test_per_sf_schedule_with_wrong_rate_fails(self):
        from decimal import Decimal
        pre = "The Premises contain 10,000 rentable square feet at $8.00 per square foot per year. "
        for wrong in ("3.04", "3.1", "3.25", "3.5"):
            with self.subTest(step=wrong):
                a2 = self._c(Decimal(80000) * (1 + Decimal(wrong) / 100))
                doc = self._doc([(6666.67, 80000), (float(self._c(a2 / 12)), float(a2))], pre=pre)
                self.assertTrue(self.q.check_rent_arithmetic(doc))

    def test_large_rsf_admits_only_the_stated_rate(self):
        from decimal import Decimal
        pre = "The Premises contain 45,000 rentable square feet at $6.00 per square foot per year. "
        passing = []
        for bp in range(250, 360):
            a2 = self._c(Decimal(270000) * (1 + Decimal(bp) / 10000))
            if not self.q.check_rent_arithmetic(
                    self._doc([(22500, 270000), (float(self._c(a2 / 12)), float(a2))], pre=pre)):
                passing.append(bp)
        self.assertEqual(passing, [300])


class TestFullParitySweep(TempDirCase):

    def _assert_all_checks_match(self, path, **kwargs):
        old = _original_verdicts(path, **kwargs)
        new = _new_verdicts(path, **kwargs)
        mismatches = {cid: (old[cid], new[cid]) for cid in old if old[cid] != new[cid]}
        self.assertEqual(old, new, f"parity mismatch on {path}\n{mismatches}")

    def test_plain_filler_only_no_flags(self):
        path = make_docx(self.tmp / "plain.docx", ["A short recital paragraph."])
        self._assert_all_checks_match(path)

    def test_m3b_addendum_missing_everything(self):
        path = make_docx(
            self.tmp / "m3b_bare.docx",
            ["Tenant shall be XYZ Corp, d/b/a Acme, released from this Lease."],
        )
        self._assert_all_checks_match(path, m3b=True)

    def test_m3b_addendum_fully_compliant(self):
        path = make_docx(
            self.tmp / "m3b_full.docx",
            [
                "Tenant shall be XYZ Corp, d/b/a Acme, released from this Lease "
                "and MLC Holdings LLC consents to this release.",
                "A security deposit in the amount of $5,000.00 shall be transferred.",
                "Tenant is released from all obligations and MLC Holdings LLC "
                "assumes the obligations of Tenant under this Lease.",
                "Insurance certificates shall be delivered by the incoming tenant.",
                "Notice addresses for all parties are set forth below.",
                "A guaranty in the form attached as Exhibit A is executed concurrently.",
                "By: MLC Holdings LLC Its: Manager",
            ],
        )
        self._assert_all_checks_match(path, m3b=True)

    def test_m4_addendum(self):
        path = make_docx(
            self.tmp / "m4.docx",
            ["The Premises are expanded to include the adjacent 1,000 square feet."],
        )
        self._assert_all_checks_match(path, m4=True)

    def test_allow_tokens_flag(self):
        path = make_docx(self.tmp / "tokens.docx", ["This references [TENANT NAME] directly."])
        self._assert_all_checks_match(path, allow_tokens=True)

    def test_unfilled_token_present(self):
        path = make_docx(self.tmp / "unfilled.docx", ["This references [TENANT NAME] directly."])
        self._assert_all_checks_match(path)
        self.assertTrue(_new_verdicts(path)["14"])

    def test_template_filename_suppresses_token_check(self):
        path = make_docx(self.tmp / "Lease_Addendum_TEMPLATE.docx",
                          ["This references [TENANT NAME] directly."])
        self._assert_all_checks_match(path)
        self.assertFalse(_new_verdicts(path)["14"])


if __name__ == "__main__":
    unittest.main()
