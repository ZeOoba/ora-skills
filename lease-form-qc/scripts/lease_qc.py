#!/usr/bin/env python3
"""
lease_qc.py - Oxford Realty Advisors lease-form QC scanner.
Companion to the `lease-form-qc` skill. Scans a lease drafted on ORA paper for
the systemic defect classes documented in that skill.

Usage:
    python3 lease_qc.py <lease.docx|pdf|txt> [more ...] [--allow-tokens]
                        [--no-ocr] [--json]

Exit codes: 0 = all PASS, 1 = one or more FAIL,
            2 = usage / extraction / UNREADABLE error.

Severity: BLOCK (do not execute) / HIGH / MED / LOW.
Checks are written to FAIL on the DEFECT; a check that does not fire means the
protective language was found.

Extraction, the OCR fallback, the UNREADABLE gate, and the report/CLI harness
live in ora_doc_qc.py (shared with pma-qc and listing-agreement-qc).
ora_doc_qc.py itself is NOT vendored inside this skill's scripts/ directory —
it fans out from the repo-root tools/ora_doc_qc.py via package_skills.py's
SHARED_ROOT_DEPS (the same pattern target-markets.json already uses for four
other skills), landing at scripts/ora_doc_qc.py inside the packaged .skill so
this skill installs and runs standalone, mirroring pma-qc and
listing-agreement-qc. In a raw repo/worktree checkout (where nothing has been
packaged yet), the sys.path shim below falls back to the repo-root tools/
directory so `python lease-form-qc/scripts/lease_qc.py ...` still works for
local development.

WHAT THE 2026-08-17 RETROFIT CHANGED
------------------------------------
This file's former text_of() branched on `.docx` and sent everything else -
including PDFs - to open(path, encoding='utf-8', errors='replace').read(),
reading a PDF's binary container as prose. Measured on
tests/no_text_layer_fixture.pdf beforehand: 16 of 51 checks "FAILED", 2 of them
BLOCK, exit 1 - a damning verdict on a document the scanner never read, with
nothing in the output admitting it. That is the same root cause as the
false-clean bug ora_doc_qc.py was extracted to fix, in a different disguise.
extract() now does real format detection, tries pdftotext then OCR, and
returns UNREADABLE (exit 2) for anything that will not yield enough words to
be scanned. Intentional behavior changes, all documented in
tests/test_lease_qc.py:

  * exit 2 is new. There was previously no distinct code for "could not read
    this document"; the whole point of the retrofit is that such a document
    now gets no QC verdict at all instead of a fabricated one.
  * the printed report is ora_doc_qc.print_report()'s fuller
    FILE/EXTRACTION/ENC/RESULT block. Nothing in the repo parses this script's
    stdout - masterlease-revision-cycle and masterlease-jurisdiction-rebase
    gate on the "0 failures" exit code, which is unchanged.
  * T1 is a registered check rather than a finding synthesized inside the old
    scan(), so it participates in --json and the checks_run total (52, not 51).
    It reads BODY + meta["footer"] (see _t1) - the footer half is not optional
    coverage, ORA's own master carries real tokens down there.
  * F18 reads meta["footer"] instead of parsing a '[[FOOTER]]' marker that
    text_of() spliced onto the body. That splice also leaked footer
    boilerplate into every other check's body text; it is gone.

WHY THREE CHECKS ARE NOT bool_check()-WRAPPED
---------------------------------------------
bool_check() feeds a check ctx["t"], which is ora_doc_qc.norm()'d: \\s+
collapsed to single spaces, curly quotes and dashes folded to ASCII, \\xa0
rewritten to a plain space. Three checks test signals norm() destroys, so they
take ctx directly. Each is pinned by a parity test against a frozen copy of
the pre-retrofit logic in tests/test_lease_qc.py.

  A2  anchors with '^' under re.M to prove a section HEADING exists. norm()
      erases every newline, so '^' can only match offset 0 and A2 fires on any
      lease that merely mentions the section. Measured on the real v2.6
      master: old = pass, naively-wrapped = FAIL (HIGH). It reads _linewise().
  F9  tests for '\\xa0' literally. norm() rewrites \\xa0 to a space, so a
      wrapped F9 could never fire again - a silent false negative in a gate
      that exists to catch what silently passes. It reads ctx["raw"].
  F18 needs ctx["meta"], not text at all.

ctx["raw"] is not a second extraction path: ora_doc_qc.scan() populates it
from the same extract() call that produces ctx["t"], and the shared
unfilled_token_check() reads it the same way.

A2b / A3 / A9 DELIBERATELY WIDEN. They match an ASCII '"' character class
against document text. Word emits curly quotes, so pre-retrofit they silently
missed every smart-quoted dead cross-reference; norm() folds the quotes and
they now catch those. That is the check working as written. Neither fires on
the current v2.6 master, so ORA's own paper is unaffected.

TWO ADDITIONS FOR lease-generation's HANDOFF (added post-v2.5.1)
------------------------------------------------------------------
lease-generation's SKILL.md documents two handoffs to this scanner:

  * T2 -- a footer FILENAME/DOCPROPERTY field that resolves to a tenant name
    other than this lease's own defined Tenant, the cross-contamination
    failure mode this skill exists to catch generally (see "Why this
    exists" in SKILL.md), specific to a footer field left over from cloning
    a different tenant's executed lease. Registered in CHECKS like any other
    check; see its own comment block for why it is ctx-aware rather than
    bool_check()-wrapped, and for the real, documented limit on which kind
    of Word field it can see.
  * `--loi-conformance <deal-terms-register.json>` -- a second CLI mode
    (dispatched in main() before CHECKS/run_cli() ever runs) that replays
    lease-generation's own "LOI conformance matrix" gate (SKILL.md "3.
    Gates", item 4) as a scanner-owned, testable CONFORMS / CONFORMS+ /
    PARTIAL / MISSING / CONFLICT matrix instead of a manual judgment call.
    See the "--loi-conformance mode" section near the bottom of this file.

Both are additive: CHECKS keeps every existing entry, ID, and severity
unchanged.

FORM MODES + POWER-RIGHTS STANDARD (v2.10, 2026-10-15)
------------------------------------------------------
    python3 -I lease_qc.py <files> [--form v2.7|v3.0] [--power-rights] ...

The default CLI no longer calls ora_doc_qc.run_cli() directly: main() runs
_run_scan_cli(), which resolves each file's form line (footer tag ->
structure -> legacy v2.7 default), builds that file's registry
(build_registry), and then calls the same ora_doc_qc.scan()/print_report()
with the same flags and exit codes, appending FORM / N/A / PENDING lines
(and form/na/pending keys in --json). A v2.x document with no form conflict
is scanned with the CHECKS list object itself -- same 60 checks, same
result. v3.x documents get the v3.0 registry (re-anchors, F16 N/A, F0,
F22-F26); FP1-FP8 (power-rights standard) are enforced only on >= v2.8 /
>= v3.1 forms or with --power-rights, and are otherwise reported PENDING.
See the FORM MODES section below CHECKS and SKILL.md Classes 5f/5g.
"""

import argparse
import functools
import json
import os
import re
import sys
import zipfile
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

# Dev-checkout fallback: Python already puts this script's own directory at
# sys.path[0] on startup, so append (not insert) the repo-root tools/
# directory as a lower-priority fallback — a packaged .skill ships
# ora_doc_qc.py alongside this script (via SHARED_ROOT_DEPS, see module
# docstring above), so that co-located copy is always tried first,
# structurally, regardless of what does or doesn't exist under an install
# root's own tools/ directory. A raw repo/worktree checkout has no such
# co-located copy, so the appended repo-root tools/ path is what resolves
# ora_doc_qc there. Verified 2026-08-17 against both a raw worktree checkout
# and a real extracted .skill (see task-4-fix-report.md).
sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'tools'))
# `python3 -I` (isolated mode, the ORA standard for running scripts) does NOT
# put the script's own directory on sys.path, so the co-located
# ora_doc_qc.py was unimportable under -I (ModuleNotFoundError, measured
# 2026-10-15 on the unmodified v2.9 script). Put it first explicitly -- the
# same precedence plain `python3 lease_qc.py` already gives it.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from ora_doc_qc import (bool_check, run_cli, extract, norm, scan, print_report,  # noqa: E402
                        build_cli, run_checks)

Q = '["“”‘’«»]'


def _defined(t, term):
    """True if `term` is given an operative definition, in any quote style."""
    return bool(re.search(Q + r'\s*' + term + r'\s*' + Q + r'\s*(shall\s+)?means?\b', t))


def _linewise(ctx):
    """ctx["raw"] with runs of spaces/tabs collapsed but LINE BREAKS KEPT.

    This is exactly the normalization the pre-retrofit text_of() applied
    (`re.sub(r'[ \\t]+', ' ', tag_stripped_text)`), and it is what a check
    using re.MULTILINE needs. ctx["t"] cannot serve: ora_doc_qc.norm()
    collapses \\s+, newlines included. Only A2 uses this.
    """
    return _linewise_of(ctx["raw"])


@functools.lru_cache(maxsize=16)
def _linewise_of(raw):
    return re.sub(r'[ \t]+', ' ', raw)


def _a2(ctx):
    """Dead cross-reference: the lease points at a 'RIGHTS RESERVED BY
    LANDLORD' section that does not exist as a heading. Body identical to the
    pre-retrofit lambda; only the text channel differs (see _linewise)."""
    t = _linewise(ctx)
    if 'RIGHTS RESERVED BY LANDLORD' not in t.upper():
        return None
    if re.search(r'^\s*RIGHTS RESERVED BY LANDLORD\.', t, re.M | re.I):
        return None
    return True


def _f9(ctx):
    """Non-breaking-space artifacts. Must read raw - norm() strips them."""
    return True if '\xa0' in ctx["raw"] else None


def _f18(ctx):
    """Footer lacks the ORA Master Lease form-version tag.

    Pre-retrofit this was:
        '[[FOOTER]]' in t and 'ORA Master Lease v' not in t.split('[[FOOTER]]')[1]
    where text_of() appended '\\n[[FOOTER]] ' + footer_text UNCONDITIONALLY to
    every .docx and never to anything else. Hand-derived truth table:
        docx, footer carries the tag  -> pass  (tail contains it)
        docx, footer lacks the tag    -> FAIL
        docx, no footer part at all   -> FAIL  (tail is empty; empty lacks it)
        non-docx                      -> pass  (no marker was ever appended)
    meta["footer"] defaults to "" when there is no footer part, and "" does not
    contain the tag, so the format guard plus a plain containment test
    reproduces all four rows. All four are asserted in
    tests/test_lease_qc.py::TestF18FooterRewrite, each against a frozen copy of
    the original logic rather than against this comment.
    """
    if ctx["meta"]["format"] != "docx":
        return None
    return None if 'ORA Master Lease v' in ctx["meta"]["footer"] else True


# --------------------------------------------------------------------------
# T2 -- footer FILENAME/DOCPROPERTY field names a different tenant
# --------------------------------------------------------------------------
# lease-generation's SKILL.md hands this scanner a second job: a lease
# cloned from a DIFFERENT tenant's executed lease as a drafting shortcut
# (rather than the property template -- see "Why this exists" above) can
# leave a Word FILENAME or DOCPROPERTY field in the footer that still
# resolves to the OLD tenant's name, even after every [BRACKETED] token in
# the body and footer has been filled. T1 cannot catch this: a field's
# cached result is not a token, it is ordinary-looking text that happens to
# be wrong.
#
# T2 is registered like any other check but, like A2/F9/F18, is NOT
# bool_check()-wrapped: it needs ctx["meta"]["footer"] (T1/F18's channel)
# and ctx["raw"] (the un-normalized body, for a reliable defined-Tenant
# quote match), not the norm()'d ctx["t"].

_ENTITY_SUFFIX_RE = re.compile(
    r'\b(l\.?\s?l\.?\s?c\.?|inc\.?|incorporated|corp\.?|corporation|company|'
    r'co\.?|ltd\.?|limited|l\.?\s?p\.?|limited\s+partnership|'
    r'limited\s+liability\s+compan(?:y|ies))\b', re.I)


def _normalize_entity_name(name):
    """Case/punctuation/whitespace/entity-suffix-insensitive form of an
    entity or individual name, for comparing a footer field's resolved
    value against the lease's own defined Tenant name(s). Squashes ALL
    remaining whitespace (not just runs of it) so 'Acme Holdings LLC' and a
    filename-derived 'AcmeHoldings' compare equal -- a FILENAME field's
    cached value is routinely word-concatenated, and a footer field is
    never going to be spaced exactly like the body's prose."""
    if not name:
        return ""
    n = name.lower().replace("&", " and ")
    n = re.sub(r'[.,]', ' ', n)
    n = _ENTITY_SUFFIX_RE.sub(' ', n)
    return re.sub(r'[^a-z0-9]+', '', n)


_TENANT_QUOTE_RE = re.compile(Q + r'\s*(?:the\s+)?Tenant\s*' + Q, re.I)
_LANDLORD_ANCHOR_RE = re.compile(Q + r'\s*Landlord\s*' + Q + r'\s*\)?', re.I)
_TRAILING_COLLECTIVE_RE = re.compile(
    r'\(?\s*(?:individually\s+and\s+collectively|collectively|'
    r'jointly\s+and\s+severally)\s*,?\s*\)?\s*$', re.I)

_TENANT_NAME_STOPWORDS = {
    "the", "by", "between", "and", "made", "this", "lease", "agreement", "is",
    "collectively", "individually", "jointly", "severally", "referred", "to",
    "as", "hereinafter", "landlord", "tenant", "a", "an", "of", "for", "with",
}


def _extract_tenant_names(text):
    """Best-effort name(s) bound to the lease's own defined "Tenant" term,
    read from its parties clause (e.g. '... 2203 Northwood, LLC
    ("Landlord") and REDACTED-T01 and REDACTED-T02,
    individually (individually and collectively, "Tenant")' -> ["REDACTED-T01", "REDACTED-T02"]).

    Anchors on the LANDLORD's own defined-term parenthetical (a reliable
    landmark in ORA's standard preamble: '<Landlord entity> ("Landlord")
    and <Tenant name(s)> ("Tenant")'), not on the first bare "and" in the
    sentence -- a naive '\\band\\s+' anchor matches whichever "and" comes
    first ("made AND entered into by AND between ...") and captures
    everything from there to the Tenant quote, including the Landlord's own
    name. Falls back to a bounded lookback window when no Landlord anchor
    is found (still conservative -- see below).

    Returns every name in a co-tenant list, not just one -- ratified
    position 2 (individuals joined as joint-and-several co-tenants, never a
    guaranty) means "the Tenant" routinely IS a list, and T2 must check a
    footer field against ALL of them before calling it a mismatch (a field
    correctly naming any one listed co-tenant is not stale boilerplate).

    Deliberately conservative: returns [] rather than guess whenever no
    confident "'Tenant'" quote is found at all. T2 must never fire on a
    Tenant name it is not sure of -- a false BLOCK on a signature-ready
    lease is the worst failure mode for a pre-execution gate.
    """
    window_text = text[:4000]
    names = []
    for qm in _TENANT_QUOTE_RE.finditer(window_text):
        anchor_end = None
        for lm in _LANDLORD_ANCHOR_RE.finditer(window_text[:qm.start()]):
            anchor_end = lm.end()          # nearest Landlord anchor before this quote
        start = anchor_end if anchor_end is not None else max(0, qm.start() - 300)
        prefix = window_text[start:qm.start()]
        prefix = _TRAILING_COLLECTIVE_RE.sub('', prefix).rstrip()
        prefix = re.sub(r'^\s*and\s+', '', prefix, flags=re.I)
        for piece in re.split(r'\s*(?:,\s*(?:and\s+)?|\s+and\s+|&)\s*', prefix):
            piece = piece.strip(' ,.\'"()')
            piece = re.sub(r',?\s*individually\s*$', '', piece, flags=re.I).strip()
            if not piece or piece.lower() in _TENANT_NAME_STOPWORDS:
                continue
            if not piece[:1].isalpha() or not piece[:1].isupper():
                continue
            words = piece.split()
            # Reject if ANY word is a sentence stopword, not just when the
            # WHOLE piece is one -- without this, the no-anchor fallback
            # window (used when no ("Landlord") parenthetical precedes the
            # Tenant quote) can capture a verb-phrase fragment like "This
            # Lease is made by" as if it were a party name; caught in
            # independent review. A real entity/person name never contains
            # "is", "made", "by", "the", ... as one of its own words.
            if any(w.lower().strip('.,') in _TENANT_NAME_STOPWORDS for w in words):
                continue
            names.append(piece)
    seen, out = set(), []
    for n in names:
        k = n.lower()
        if k not in seen:
            seen.add(k)
            out.append(n)
    return out


_FIELD_HEAD_RE = re.compile(r'\b(FILENAME|DOCPROPERTY)\b')
_SWITCH_NOISE_RE = re.compile(r'\\\*\s*MERGEFORMAT|\\[a-zA-Z]\b\s*', re.I)


def _footer_field_candidates(footer_text):
    """(kind, prop, result) for every FILENAME/DOCPROPERTY field visible in
    the STRIPPED footer text ora_doc_qc.extract() already produced.

    This is a real, documented limit, not an oversight: Word encodes a
    field two ways. A SIMPLE field (<w:fldSimple w:instr="...">...
    </w:fldSimple>) carries its instruction in a tag ATTRIBUTE, which
    ora_doc_qc._strip_xml() discards along with every other tag --
    invisible here, and there is no way to recover it from ctx (no file
    path, no raw-XML channel). A COMPLEX field (<w:fldChar .../> begin,
    <w:instrText>...</w:instrText>, another fldChar "separate", the cached
    result run(s), a final fldChar "end") keeps its instruction as ELEMENT
    TEXT, which _strip_xml() does NOT remove -- Word's own document order
    puts the instruction immediately before the cached result in the
    stripped stream, which is what this function anchors on. Widening this
    to catch fldSimple too is a change to the shared extraction module (ctx
    would need a raw-XML or file-path channel it does not carry today) --
    out of reach here: lease_qc.py must not regain its own zipfile-based
    extraction path (tests/test_lease_qc.py's
    test_module_imports_nothing_from_a_local_extraction_path pins that),
    and this file must not touch ora_doc_qc.py, shared with pma-qc and
    listing-agreement-qc.
    """
    text = re.sub(r'[ \t]+', ' ', footer_text or "")
    out = []
    for m in _FIELD_HEAD_RE.finditer(text):
        kind = m.group(1).upper()
        tail = text[m.end():]
        nl = tail.find('\n')
        if nl != -1:
            tail = tail[:nl]
        prop = None
        pm = re.match(r'\s*"([^"]*)"', tail)
        if pm:
            prop = pm.group(1)
            tail = tail[pm.end():]
        elif kind == "DOCPROPERTY":
            # Word writes a custom property name TWO ways: quoted
            # (' DOCPROPERTY "TenantName" \* MERGEFORMAT ') and, just as
            # commonly for a single-token name, unquoted
            # (' DOCPROPERTY  TenantName  \* MERGEFORMAT '). The
            # quoted-only parse above silently never matched the unquoted
            # form -- caught in independent review -- which left the
            # _TENANT_PROP_RE gate below unreachable for what is likely
            # the MORE common real-world encoding.
            pm2 = re.match(r'\s*([A-Za-z_][A-Za-z0-9_]*)\b', tail)
            if pm2:
                prop = pm2.group(1)
                tail = tail[pm2.end():]
        tail = _SWITCH_NOISE_RE.sub(' ', tail)
        # _strip_xml() leaves no delimiter where the field's own
        # <w:fldChar fldCharType="end"/> used to be, so an EMPTY field
        # (never refreshed) or a short one runs straight into whatever
        # footer text follows on the same line with nothing marking the
        # boundary between them -- caught in review: an empty field
        # immediately followed by page-numbering text on the same <w:p>
        # was captured as the field's "result" (e.g. "Page 1 of 12"). Cut
        # at ORA's own footer segment separators (bullet/pipe, or a dash
        # introducing "Page N") and at a bare "Page N" run even with no
        # separator, so a segment that was never part of THIS field never
        # gets treated as its cached value.
        tail = re.split(r'\s*[•|]\s*', tail, maxsplit=1)[0]
        tail = re.split(r'\s+-\s+(?=Page\s+\d)', tail, maxsplit=1, flags=re.I)[0]
        tail = re.split(r'\bPage\s+\d', tail, maxsplit=1, flags=re.I)[0]
        tail = tail.strip()
        if tail:
            out.append((kind, prop, tail))
    return out


_FILENAME_NOISE_RE = re.compile(
    r'^(?:lease|suite|redline|draft|vs|final|executed|clean|amendment|'
    r'addendum|v\d+[a-z]?|\d{1,8})$', re.I)

# A DOCPROPERTY field's custom property NAME must itself read as a
# tenant/party field before its value is trusted as a tenant claim -- see
# _entity_name_from_field()'s docstring for why an unfiltered value produced
# false BLOCKs on ordinary metadata fields ("Company", "Manager", "Title",
# a doc-ID) in review.
_TENANT_PROP_RE = re.compile(r'tenant|lessee', re.I)


def _entity_name_from_field(kind, prop, result):
    """The candidate entity/tenant name embedded in one field's cached
    result, or "" if the field does not plausibly carry a tenant claim at
    all -- T2 must never guess.

    DOCPROPERTY: used only when the property NAME itself is tenant/lessee-
    labeled (e.g. 'TenantName'); a custom document property can hold
    anything (a doc ID, ORA's own company name, a manager, a title), and
    treating an arbitrary property's value as a tenant claim produced real
    false BLOCKs in review. An untagged property returns "" -- not a
    guess, not a comparison.

    FILENAME: ORA's naming convention places the tenant token after a
    literal 'Lease' marker ('<Address> Suite <X> Lease <Tenant> <MM-YYYY>
    v0N.docx', or the test-fixture-style 'Lease_TenantName_MMDDYYYY.docx').
    Only tokens AFTER that marker are ever treated as a tenant claim --
    scanning the whole filename (address, suite, dates) reads unrelated
    tokens as "the tenant" whenever a filename happens to carry no real
    tenant name at all (an address-only filename, or a bare version tag
    after 'Lease'), which was the review's other reproduced false BLOCK.
    A filename with no 'Lease' marker returns "".
    """
    result = re.sub(r'\.(docx?|pdf)$', '', (result or "").strip(), flags=re.I)
    if kind == "DOCPROPERTY":
        if not prop or not _TENANT_PROP_RE.search(prop):
            return ""
        return result
    if kind == "FILENAME":
        m = re.search(r'\bLease[_\s]+(.*)$', result, re.I)
        if not m:
            return ""
        tokens = [t for t in re.split(r'[_\-\s]+', m.group(1)) if t]
        keep = [t for t in tokens if not _FILENAME_NOISE_RE.match(t)]
        return " ".join(keep)
    return ""


def _t2(ctx):
    """Footer FILENAME/DOCPROPERTY field resolves to a tenant name other
    than this lease's own defined Tenant. See _footer_field_candidates()
    for why only COMPLEX fields (fldChar+instrText) are detectable this
    way, and _extract_tenant_names() for why a co-tenant list is checked as
    a whole, never just its first name. No field in the footer at all --
    lease-generation's own output, which replaces the field with static
    text -- passes cleanly by design: the very first check below is the
    whole gate for that case."""
    if ctx["meta"]["format"] != "docx":
        return None
    fields = _footer_field_candidates(ctx["meta"].get("footer", ""))
    if not fields:
        return None
    tenant_names = _extract_tenant_names(ctx["raw"])
    if not tenant_names:
        return None
    norm_tenants = {n for n in (_normalize_entity_name(t) for t in tenant_names) if n}
    if not norm_tenants:
        return None
    for kind, prop, result in fields:
        candidate = _entity_name_from_field(kind, prop, result)
        norm_candidate = _normalize_entity_name(candidate)
        if not norm_candidate:
            continue
        if any(norm_candidate == nt or norm_candidate in nt or nt in norm_candidate
               for nt in norm_tenants):
            continue
        label = f'{kind} "{prop}"' if prop else kind
        return (f'footer {label} field resolves to "{candidate}", which does not '
                f'match this lease\'s defined Tenant ({", ".join(tenant_names)}) -- '
                f'verify this was not cloned from a different tenant\'s executed '
                f'lease and left as stale boilerplate.')
    return None


# (id, severity, label, position, fn(ctx)) -- fn returns None to PASS, True to
# FAIL with the label as the detail. Test bodies are verbatim from the
# pre-retrofit file; bool_check() adapts `lambda t: <bool>` to the shared
# ctx-based calling convention with no change to what is tested.
# position is None throughout: lease-form-qc has no standing-positions
# document to cross-reference the way pma-qc (PM-*) and
# listing-agreement-qc (SP-*) do.
CHECKS = [
    bool_check("A1", "BLOCK", "ZIP/address conflict between Sec.1 premises and Sec.4 building block",
               lambda t: len({z for z in re.findall(r'\b4\d{4}\b', t)} - {'43215'}) > 1),
    bool_check("A6", "BLOCK", "Operating-cost pass-through has no billing/reconciliation machinery",
               lambda t: not re.search(r'reconcil', t, re.I)),
    bool_check("A7", "BLOCK", "'net base rent' label on a base-year expense stop (NNN vs gross conflict)",
               lambda t: bool(re.search(r'net base rent', t, re.I)) and bool(re.search(r'increase over base year', t, re.I))),
    bool_check("A11", "BLOCK", "Audited CPA financial statements demanded of a small tenant",
               lambda t: bool(re.search(r'audited by a certified public accountant', t, re.I))),
    bool_check("B7", "BLOCK", "Tenant notice address is the Premises only (fails pre-occupancy/post-abandonment)",
               lambda t: not re.search(r'TENANT NOTICE ADDRESS|Tenant.{0,40}notice address', t, re.I)),
    # A2 is ctx-aware: it needs line breaks for its re.M anchor. See _a2.
    ("A2", "HIGH", "Dead cross-reference: 'RIGHTS RESERVED BY LANDLORD' section does not exist",
     None, _a2),
    bool_check("A2b", "HIGH", "Dead cross-reference: 'INSPECTIONS...' missing the leading 'ENTRY FOR'",
               lambda t: bool(re.search(r'entitled[,]?\s*[""]?\s*INSPECTIONS,\s*REPAIRS', t, re.I))
               or bool(re.search(r'REPAIRS AND INSTALLATION[,""]', t))),
    bool_check("A3", "HIGH", "Dead cross-reference: section 'ALL RISK PROPERTY INSURANCE' does not exist",
               lambda t: bool(re.search(r'entitled[,]?\s*[""]?\s*ALL RISK PROPERTY INSURANCE', t, re.I))),
    bool_check("A9", "HIGH", "Prevailing-party carve-out cites DEFAULT OF TENANT; fee rule lives in REMEDIES",
               lambda t: bool(re.search(r'Except as set forth in the section of this Lease entitled\s*[""]?DEFAULT OF TENANT', t, re.I))),
    bool_check("A5a", "HIGH", "'Project' used but never defined",
               lambda t: 'Project' in t and not _defined(t, 'Project')),
    bool_check("A5b", "HIGH", "'Building' used but never defined",
               lambda t: 'Building' in t and not _defined(t, 'Building')),
    bool_check("A5c", "HIGH", "'Business Day' used but never defined",
               lambda t: 'Business Day' in t and not _defined(t, 'Business Days?')),
    bool_check("A4a", "HIGH", "CERCLA miscited as 42 U.S.C. 9061 (correct: 9601)",
               lambda t: '9061' in t),
    bool_check("A4b", "HIGH", "HMTA cited at obsolete 49 U.S.C. 1802 (recodified 1994 at 5101)",
               lambda t: bool(re.search(r'49 U\.?\s?S\.?\s?C\.?\s*(Section|§)?\s*1802', t))),
    bool_check("A8", "HIGH", "Authority clause limited to corporations (tenants are LLCs/individuals)",
               lambda t: bool(re.search(r'If Tenant is or will be a corporation', t, re.I))),
    bool_check("A10", "HIGH", "'Delay in Commencement' circular against a fixed Commencement Date",
               lambda t: bool(re.search(r'Delay in Commencement', t, re.I))),
    bool_check("B2", "HIGH", "Mitigation disclaimer unqualified (Frenchtown v. Lemstone exposure)",
               lambda t: bool(re.search(r'no obligation to relet', t, re.I))
               and not re.search(r'required by applicable law', t, re.I)),
    bool_check("B3", "MED", "Acceleration without credit for reletting proceeds / fair rental value",
               lambda t: bool(re.search(r'accelerate and recover', t, re.I))
               and not re.search(r'net proceeds of any reletting|fair rental value', t, re.I)),
    bool_check("B4", "MED", "Holdover formula ambiguous (200% applied to accrued arrears)",
               lambda t: bool(re.search(r'two hundred percent \(200%\) of the amount of \(a\)', t, re.I))),
    bool_check("B5", "MED", "HVAC replacement responsibility never affirmatively allocated",
               lambda t: not re.search(r'responsible for replacement of the heating', t, re.I)),
    bool_check("B6a", "MED", "CGL general aggregate limit not stated",
               lambda t: not re.search(r'general aggregate', t, re.I)),
    bool_check("B6b", "MED", "Employer's Liability limit not stated",
               lambda t: not re.search(r"Employer.s Liability", t, re.I)),
    bool_check("B6c", "MED", "No annual COI delivery obligation (certificates only pre-possession)",
               lambda t: not re.search(r'renewal certificates|annually during the Lease Term', t, re.I)),
    bool_check("B8", "MED", "Water supplied 'at Tenant's expense' with no billing mechanism",
               lambda t: bool(re.search(r'water sufficient for drinking', t, re.I))
               and not re.search(r'flat rate of \$', t, re.I)),
    bool_check("B11", "MED", "Guarantor/co-tenant mismatch: 'any guarantor' language with no guaranty and no co-tenant conform",
               lambda t: bool(re.search(r'any guarantor of this Lease', t, re.I))
               and not re.search(r'Guaranty of Lease|GUARANTY', t)
               and not re.search(r'any person or entity comprising Tenant', t, re.I)),
    bool_check("C1", "MED", "No no-recording clause",
               lambda t: not re.search(r'shall not record this Lease', t, re.I)),
    bool_check("C2", "MED", "No Landlord default notice-and-cure standard",
               lambda t: not re.search(r'Landlord shall not be in default', t, re.I)),
    bool_check("C3", "MED", "No force majeure clause",
               lambda t: not re.search(r'force majeure', t, re.I)),
    bool_check("C4", "LOW", "No OFAC / sanctions representation",
               lambda t: not re.search(r'Foreign Assets Control|OFAC', t, re.I)),
    bool_check("C5", "MED", "No counterparts / electronic signature clause",
               lambda t: not re.search(r'counterpart', t, re.I)),
    bool_check("C6", "LOW", "No 'time is of the essence' clause",
               lambda t: not re.search(r'[Tt]ime is of the essence', t)),
    bool_check("C7", "LOW", "No personal property tax allocation to Tenant",
               lambda t: not re.search(r'taxes and assessments levied on Tenant', t, re.I)),
    bool_check("C8", "HIGH", "No Exhibit A premises depiction / stipulated square footage",
               lambda t: not re.search(r'Exhibit A', t)),
    bool_check("F1", "LOW", "'his agents' - Landlord is an LLC",
               lambda t: 'his agents, employees and invitees' in t),
    bool_check("F2", "LOW", "'succeeding Lease or succeeding tenant'",
               lambda t: bool(re.search(r'succeeding Lease or succeeding tenant', t, re.I))),
    bool_check("F3", "LOW", "'a comparable publications'",
               lambda t: 'a comparable publications' in t),
    bool_check("F4", "LOW", "'Interior lighting' stray mid-sentence capital",
               lambda t: 'Interior lighting' in t),
    bool_check("F5", "LOW", "'under seal' - Ohio abolished private seals",
               lambda t: bool(re.search(r'under seal', t, re.I))),
    bool_check("F7", "HIGH", "Fragile numeric self-reference ('this Section N') — breaks when sections shift",
               lambda t: bool(re.search(r'this Section \d+', t))),
    bool_check("F8", "LOW", "Default interest lacks usury savings clause (lesser-of max lawful rate)",
               lambda t: bool(re.search(r'eighteen percent \(18%\) per annum', t))
               and not re.search(r'maximum rate permitted by', t, re.I)),
    # F9 is ctx-aware: norm() would have stripped the very character it looks
    # for. See _f9.
    ("F9", "LOW", "Non-breaking-space artifacts in operative text", None, _f9),
    bool_check("F10", "MED", "No venue clause (courts of the county where the Project is located) — v2.5 standard",
               lambda t: 'Venue for any action' not in t),
    bool_check("F11", "HIGH", "Indemnity lacks waiver-of-subrogation carve-out (insurer can bypass the mutual waiver) — v2.5 standard",
               lambda t: 'waived pursuant to the waiver of subrogation' not in t),
    bool_check("F12", "MED", "'Governmental Agency' or 'Building Standard' used but undefined — v2.5 standard",
               lambda t: (('Governmental Agency' in t and not _defined(t, 'Governmental Agency'))
                          or (re.search(r'[Bb]uilding [Ss]tandard', t) and not _defined(t, 'Building Standard')))),
    bool_check("F13", "MED", "Operating Costs lack separate-billing exclusion (flat-fee water double-recovery risk) — v2.5 standard",
               lambda t: 'increase over base year' in t and 'shall not include amounts separately billed' not in t),
    bool_check("F6", "LOW", "Late fee runs on Business Days, cure on calendar days, and 'Business Day' is undefined",
               lambda t: bool(re.search(r'five \(5\) Business Days following the date when due', t, re.I))
               and not _defined(t, 'Business Days?')),
    bool_check("F14", "MED", "Insurance not modernized: 'All Risk' without '(Special Form)' — v2.6 standard",
               lambda t: 'All Risk' in t and '(Special Form)' not in t),
    bool_check("F15", "MED", "Landlord exculpation lacks manager/member/officer/agent enumeration — v2.6 standard",
               lambda t: 'No other person or entity shall be liable' in t
               and 'manager, member, officer, employee or agent of Landlord' not in t),
    bool_check("F16", "MED", "Assignment/sublease lacks excess-rent (profit) capture — v2.6 standard",
               lambda t: bool(re.search(r'assign or otherwise transfer this Lease', t, re.I))
               and 'of such excess' not in t),
    bool_check("F17", "MED", "HVAC servicing without continuous annual preventative-maintenance contract — v2.6 standard",
               lambda t: bool(re.search(r'serviced on a semiannual basis', t, re.I))
               and 'preventative-maintenance contract' not in t),
    # F18 is ctx-aware: it reads meta["footer"], not body text. See _f18.
    ("F18", "LOW", "Footer lacks the ORA Master Lease form-version tag — v2.6 standard",
     None, _f18),
    # v2.7 standards (2026-10-06). B7 passes as soon as ANY Tenant notice-address
    # paragraph exists, so it never saw the NOTICES (B) clause still routing
    # Tenant notices to the Demised Premises only — F19 closes that gap.
    bool_check("F19", "HIGH", "NOTICES (B) sends Tenant notices to the Demised Premises only, overriding the Tenant notice address — v2.7 standard",
               lambda t: bool(re.search(r'if to Tenant,\s+at the Demised Premises\s*[.;]', t, re.I))),
    bool_check("F20", "MED", "Escalating rent with no controlling rent schedule — v2.7 standard (schedule mandatory)",
               lambda t: bool(re.search(r'second Lease Year', t, re.I))
               and (('[OPTIONAL: ATTACH RENT SCHEDULE' in t)
                    or not re.search(r'set forth in the following schedule|RENT SCHEDULE', t, re.I))),
    bool_check("F21", "MED", "No late-signing commencement clause (Commencement Date fixed regardless of execution date) — v2.7 standard",
               lambda t: 'Commencement Date' in t
               and not re.search(r'has not been fully executed and delivered by Landlord and Tenant on or before', t, re.I)),
]

# This skill's own token pattern, deliberately NOT the shared module's default
# (which adds '_' to the class and caps the run at 40 chars). Swapping it would
# be an unrequested, unverified change to what counts as an unfilled token, so
# the local regex stays in force. Pinned by
# tests/test_lease_qc.py::test_local_token_regex_is_preserved_not_the_shared_default.
TOKEN_RE = re.compile(r"\[[A-Z][A-Z0-9 /,.'&-]{2,}\]")


# The one bracketed drafting note that is REQUIRED to survive into an execution copy:
# FP8 demands it in the optional TENANT BACKUP POWER AND ENERGY STORAGE module, so T1
# must not read it as an unfilled token (Gabriel, 2026-10-17: exempt this exact note
# from T1). Exact match only -- any other bracketed token still trips T1.
T1_EXEMPT_TOKENS = frozenset({"[COUNSEL REVIEW REQUIRED BEFORE FIRST USE]"})


def _t1(ctx):
    """Unfilled template tokens remain — scanned in the BODY *and* the FOOTER.

    T1 was previously synthesized ad hoc inside the old scan() only when tokens
    were found; it is now registered once and evaluated like every other check,
    so it appears in --json and in the checks_run denominator.

    It is NOT registered via ora_doc_qc.unfilled_token_check(), for one reason:
    that helper scans ctx["raw"] alone, and extract(want_footer=True) routes
    footer text to ctx["meta"]["footer"], a channel the helper never reads. The
    pre-retrofit text_of() covered the footer by splicing it onto the body; the
    splice is gone (it caused its own false BLOCK — see the module docstring),
    so the footer must be scanned explicitly or the coverage silently vanishes.
    That is not hypothetical: ORA's own v2.6 master carries
    '[PREMISES ADDRESS]' and '[TENANT ENTITY]' in word/footer2.xml and
    word/footer3.xml, so a lease drafted from it with the body filled and the
    footer left untouched would clear a body-only T1 and go out for signature
    with both tokens printed on every page — the exact failure this BLOCK
    exists to prevent. Pinned by
    tests/test_lease_qc.py::TestTokenGate::test_unfilled_footer_tokens_block_a_filled_body_lease.

    The two gates ('_TEMPLATE' in the filename, --allow-tokens), the BLOCK
    severity, and the detail-string shape are reproduced from the shared helper
    verbatim; only the scanned text differs.
    """
    if ctx.get("is_template") or ctx.get("allow_tokens"):
        return None
    hay = ctx["raw"] + "\n" + ctx["meta"].get("footer", "")
    toks = sorted(set(TOKEN_RE.findall(hay)) - T1_EXEMPT_TOKENS)
    if not toks:
        return None
    shown = ", ".join(toks[:6]) + ("..." if len(toks) > 6 else "")
    return f"{len(toks)} unfilled token(s): {shown}"


CHECKS.append(("T1", "BLOCK", "Unfilled template tokens remain", None, _t1))
CHECKS.append(("T2", "BLOCK", "Footer FILENAME/DOCPROPERTY field names a different tenant",
               None, _t2))


# ==========================================================================
# Class 5d -- INTERNAL CONSISTENCY / EXECUTION READINESS (added v2.8)
# ==========================================================================
# T3 / T4 / D1 / D2 read only what extract(want_footer=True) already
# provides (ctx["raw"], ctx["t"], ctx["meta"]["footer"], ctx["name"]);
# tools/ora_doc_qc.py is untouched. (The v2.8 brief called the last two
# "C1"/"C2"; those IDs already exist at v2.6 -- Class 6 no-recording and
# default-cure -- so they ship as D1/D2 and no existing ID changes.)

# ctx carries only the file's BASENAME (ctx["name"]), so T4's embedded-drawing
# test (word/media/ count) cannot open the docx from ctx alone. main() and
# --loi-audit register each scanned path here first; a check that finds no
# entry degrades to its phrase-only behavior (documented in T4).
_SCAN_PATHS = {}


def register_scan_path(path):
    _SCAN_PATHS[os.path.basename(str(path))] = str(path)


def _docx_media_count(ctx):
    path = _SCAN_PATHS.get(ctx.get("name"))
    if not path or ctx["meta"].get("format") != "docx":
        return None
    try:
        with zipfile.ZipFile(path) as z:
            return sum(1 for n in z.namelist()
                       if n.startswith("word/media/") and not n.endswith("/"))
    except Exception:                                               # noqa: BLE001
        return None


_BLANK_RE = re.compile(r"_{5,}")
# Signing-time labels. `Date:`/`Name:` must not be preceded by another word
# ("Commencement Date: ____" is an operative blank, not a signing line).
_SIGN_LABEL_RE = re.compile(
    r"Signature|\bSigned\b|\bBy\s*:|(?<![A-Za-z]\s)Date\s*:|Print\s+Name|"
    r"(?<![A-Za-z]\s)Name\s*:|\bTitle\s*:|\bIts\s*:|\bInitials\b|\bWitness|"
    r"\bNotary\b|commission\s+expires|\bday\s+of\b|,\s*20_|\(SEAL\)",
    re.I)


_DAY_OF_RE = re.compile(r"\bday\s+of\b", re.I)
_OPERATIVE_RE = re.compile(r"\b(?:rent|commenc|expir|term|deposit)", re.I)


def _t3(ctx):
    """Unfilled underscore blanks in an execution copy (body + footer).

    Severity is HIGH, not BLOCK: a blank tenant `ATTN:` line is a notice
    defect a party can cure by hand, not a fabricated-verdict risk like an
    unfilled [TOKEN] (T1, BLOCK). Execution copies legitimately carry blank
    signature/date lines, so a run of underscores is exempt when its line --
    or, for a bare rule line, the line above it -- carries a signing-time
    label (Signature, Signed, By:, Date:, Print Name, Name:, Title:, Its:,
    'day of', ', 20__', (SEAL)). Everything else (ATTN:, Email:, notice
    addresses, a rent/deposit/SF/parcel/commencement blank) fires.
    Gated like T1: silent on `_TEMPLATE` files and under --allow-tokens.
    """
    if ctx.get("is_template") or ctx.get("allow_tokens"):
        return None
    hits = []
    for hay in (ctx["raw"], ctx["meta"].get("footer", "")):
        lines = hay.replace("\xa0", " ").split("\n")
        for i, line in enumerate(lines):
            for m in _BLANK_RE.finditer(line):
                pre = line[:m.start()]
                # Judge THIS blank by the label nearest it: the 40 chars
                # before, plus (for a bare rule line) the line above and the
                # caption after ("_____ Signature"). A label elsewhere on the
                # line does not excuse it ("Email: ____  By: ____").
                scope = pre[-40:]
                if not pre.strip():
                    scope = ((lines[i - 1][-40:] if i > 0 else "") + " "
                             + line[m.end():m.end() + 25] + " "
                             + (lines[i + 1][:30] if i + 1 < len(lines) else ""))
                if _SIGN_LABEL_RE.search(scope):
                    continue
                if (_DAY_OF_RE.search(line)
                        and not _OPERATIVE_RE.search(line)
                        and line[m.end():m.end() + 12].lstrip("_ ,").startswith("20")):
                    continue                     # ', 20__' tail of a date-fill line
                lead = re.sub(r"\s+", " ", _BLANK_RE.sub("", pre))[-30:].strip()
                hits.append(f'"{lead} {m.group(0)[:8]}..."'.replace('" ', '"', 1) if lead
                            else f'"{m.group(0)[:8]}..."')
    if not hits:
        return None
    shown = "; ".join(hits[:6]) + ("..." if len(hits) > 6 else "")
    return f"{len(hits)} unfilled blank(s): {shown}"


_STUB_PHRASE_RE = re.compile(
    r"TO BE ATTACHED|TO BE INSERTED|TO BE PROVIDED|\[ATTACH|PLACEHOLDER", re.I)
_EXHIBIT_HEAD_RE = re.compile(
    r"^\s*((?:EXHIBIT\s+[A-Z]\b|SCHEDULE\s+[A-Z](?:-?\d+)?\b)[^\n]{0,60})$", re.I)


def _t4(ctx):
    """Exhibit / schedule stubs left in an execution copy (BLOCK).

    Fires on a stub phrase (TO BE ATTACHED [PRIOR TO EXECUTION], TO BE
    INSERTED, TO BE PROVIDED, [ATTACH..., PLACEHOLDER) anywhere in body or
    footer, and on an EXHIBIT X / SCHEDULE X[-n] heading whose text (to the
    next such heading or end of document) is under 40 words -- unless the
    docx embeds a drawing (word/media/). The media count needs the file path,
    which ctx does not carry; main()/--loi-audit register it via
    register_scan_path(). Without a registered path (e.g. a caller running
    CHECKS through ora_doc_qc.scan() directly) the heading-stub test is
    skipped and only the phrase test runs. Templates pass by design."""
    if ctx.get("is_template"):
        return None
    hay = (ctx["raw"] + "\n" + ctx["meta"].get("footer", "")).replace("\xa0", " ")
    hay = re.sub(r"[ \t]+", " ", hay)
    m = _STUB_PHRASE_RE.search(re.sub(r"\s+", " ", hay))
    if m:
        letter = ""
        pre = re.sub(r"\s+", " ", hay)[:m.start()]
        heads = re.findall(r"(EXHIBIT\s+[A-Z]\b|SCHEDULE\s+[A-Z](?:-?\d+)?\b)", pre, re.I)
        if heads:
            letter = f"{heads[-1].upper()}: "
        return f'{letter}stub phrase "{m.group(0)}" remains'
    media = _docx_media_count(ctx)
    if media is None or media > 0:
        return None
    lines = ctx["raw"].replace("\xa0", " ").split("\n")
    heads = [(i, hm.group(1).strip()) for i, ln in enumerate(lines)
             if len(ln.split()) <= 10 and (hm := _EXHIBIT_HEAD_RE.match(ln))]
    for n, (i, title) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        words = len(" ".join(lines[i + 1:end]).split())
        if words == 0 and n + 1 < len(heads) and not any(lines[i + 1:heads[n + 1][0]]):
            continue                             # exhibit LIST / TOC, not a stub
        if words < 40:
            return f"{title.upper()}: heading with only {words} word(s) of content and no embedded drawing"
    return None


# ---- D1: BASIC LEASE INFORMATION <-> body drift ---------------------------

_UTIL_WORDS = {"electric": "electric", "electricity": "electric", "gas": "gas",
               "water": "water", "sewer": "sewer", "trash": "trash"}


def _bli_block(raw):
    """(bli_lines, rest_text). The block runs from the BASIC LEASE INFORMATION
    heading to the first blank line after >=3 'Label: value' lines, or to a
    'This Basic Lease Information' / 'THIS LEASE' line."""
    text = raw.replace("\xa0", " ")
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines)
                  if re.match(r"\s*BASIC LEASE INFORMATION\s*$", ln, re.I)), None)
    if start is None:
        return None, text
    block, end = [], len(lines)
    for j in range(start + 1, len(lines)):
        ln = lines[j]
        if re.match(r"\s*(This Basic Lease Information|THIS LEASE\b)", ln):
            end = j + 1
            break
        if not ln.strip():
            if len(block) >= 3:
                end = j
                break
            continue
        block.append(ln)
    return block, "\n".join(lines[end:])


def _bli_values(block):
    out = {}
    for ln in block:
        m = re.match(r"\s*([A-Za-z][A-Za-z '’/()0-9-]*?)\s*:\s*(.+)$", ln)
        if m:
            out[re.sub(r"\s+", " ", m.group(1)).lower().replace("’", "'")] = m.group(2).strip()
    return out


def _bli_get(vals, *prefixes):
    for k, v in vals.items():
        if any(k.startswith(p) for p in prefixes):
            return v
    return None


def _money(s):
    m = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", s or "")
    return float(m.group(1).replace(",", "")) if m else None


def _pct(s):
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", s or "")
    return float(m.group(1)) if m else None


def _money_matches(text, pattern):
    return [m.group(0) for m in re.finditer(pattern, text, re.I | re.S)]


def _d1(ctx):
    """BASIC LEASE INFORMATION values that disagree with the body (MED).

    Applies only when a BASIC LEASE INFORMATION block exists (v2.5+ paper).
    For each label the BLI states, the body is searched for the matching
    statement; a label drifts only when the body states a value for it and
    none equals the BLI value (an absent body statement or a token-valued BLI
    line is silent -- absence is Class 6's job, tokens are T1's). Dollars are
    compared to the cent via _find_dollar_amount."""
    block, rest = _bli_block(ctx["raw"])
    if not block:
        return None
    vals = _bli_values(block)
    body = re.sub(r"\s+", " ", rest.replace("\xa0", " "))
    drifts = []

    def money_label(label, bli_v, pat):
        amt = _money(bli_v)
        if amt is None or "[" in (bli_v or ""):
            return
        spans = _money_matches(body, pat)
        if not spans or any(_find_dollar_amount(s, amt) for s in spans):
            return
        found = re.search(r"\$\s*[\d,]+(?:\.\d+)?", spans[0]).group(0)
        drifts.append(f"{label}: BLI ${amt:,.2f} vs body {found}")

    def pct_label(label, bli_v, pat):
        want = _pct(bli_v)
        if want is None or "[" in (bli_v or ""):
            return
        got = [float(x) for x in re.findall(pat, body, re.I | re.S)]
        if got and want not in got:
            drifts.append(f"{label}: BLI {want:g}% vs body {got[0]:g}%")

    money_label("Security Deposit", _bli_get(vals, "security deposit"),
                r"security\s+deposit[^.$]{0,120}\$\s*[\d,]+(?:\.\d+)?")
    money_label("Monthly Rent", _bli_get(vals, "monthly rent", "monthly base rent"),
                r"monthly\s+(?:base\s+)?rent[^.$]{0,80}\$\s*[\d,]+(?:\.\d+)?")
    money_label("Annual Base Rent", _bli_get(vals, "annual base rent"),
                r"annual\s+base\s+rent[^.$]{0,80}\$\s*[\d,]+(?:\.\d+)?")
    pct_label("Tenant's Proportionate Share", _bli_get(vals, "tenant's proportionate share"),
              r"proportionate\s+share[^.%]{0,120}?(\d+(?:\.\d+)?)\s*%")
    pct_label("Late Fee", _bli_get(vals, "late fee"),
              r"late\s+(?:fee|charge)[^.%]{0,120}?(\d+(?:\.\d+)?)\s*%")
    pct_label("Default Interest", _bli_get(vals, "default interest"),
              r"(?:default\s+)?interest[^.%]{0,80}?(\d+(?:\.\d+)?)\s*%\s*"
              r"(?:per\s+annum|per\s+year|annually|a\s+year)")
    pct_label("Escalation", _bli_get(vals, "escalation"),
              r"(?:escalat|annual\s+increase)[^.%]{0,100}?(\d+(?:\.\d+)?)\s*%")

    parking = _bli_get(vals, "parking")
    pm = re.search(r"\d+", parking or "")
    if pm and "[" not in parking:
        want = int(pm.group(0))
        got = [int(x) for x in re.findall(
            r"(\d+)\)?\s*(?:overnight\s+)?(?:vehicles?|parking\s+spaces?)", body, re.I)]
        if got and want not in got:
            drifts.append(f"Parking: BLI {want} vs body {got[0]}")

    util = _bli_get(vals, "utilities")
    if util and "[" not in util:
        bli_set = {v for k, v in _UTIL_WORDS.items()
                   if re.search(r"\b" + k + r"\b", util, re.I)}
        sec = re.search(r"^\s*SERVICES AND UTILITIES\.?\s*$(.*?)(?=^\s*[A-Z][A-Z ,&'-]{6,}\.?\s*$|\Z)",
                        rest.replace("\xa0", " "), re.M | re.S)
        if bli_set and sec:
            sents = [s for s in re.split(r"(?<=[.;])\s+", sec.group(1))
                     if re.search(r"\b(pay|paid|bill|billed|charge|charged|cost|responsible)\b", s, re.I)]
            body_set = {v for s in sents for k, v in _UTIL_WORDS.items()
                        if re.search(r"\b" + k + r"\b", s, re.I)}
            if body_set and body_set != bli_set:
                drifts.append("Utilities: BLI {" + ", ".join(sorted(bli_set)) +
                              "} vs body {" + ", ".join(sorted(body_set)) + "}")
    if not drifts:
        return None
    return f"{len(drifts)} drifted label(s): " + "; ".join(drifts)


# ---- D2: rent-schedule arithmetic ----------------------------------------

_AMT = r"\$\s*[\d,]+(?:\.\d+)?"
_ROW_RE = re.compile(
    r"((?:Lease\s+)?Years?\s*\d+(?:\s*-\s*\d+)?|Months?\s*\d+\s*-\s*\d+|"
    r"\d{1,2}/\d{1,2}/\d{2,4}\s*-\s*\d{1,2}/\d{1,2}/\d{2,4})\s*[|:]?\s*"
    r"((?:" + _AMT + r")(?:\s*\|?\s*(?:per\s+year\s*)?(?:" + _AMT + r")){1,3})", re.I)


def _cents(x):
    return Decimal(str(x)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _d2(ctx):
    """Rent-schedule arithmetic (HIGH). Skips silently when no schedule table
    is found (legacy paper -- Class 6 flags the missing table).

    Year 1: round(PSF x RSF, 2) must equal the row-1 annual (within the
    half-cent-per-SF a 2-dp PSF can hide) and round(annual/12, 2) the row-1
    monthly. Later rows: every row must reproduce under ONE method to the
    cent -- (i) annual x (1+e), monthly = annual/12; (ii) monthly x (1+e)
    rounded each year, annual = monthly x 12. A row matching neither method,
    or rows that each match a method but not the same one, FAIL (the mixed
    case is excused only by a 'schedule controls' clause). PSF/RSF/e come from
    the BLI or the RENT text; any missing input skips just the test that
    needs it."""
    t = ctx["t"]
    rows = []
    for m in _ROW_RE.finditer(t):
        per = m.group(1)
        rng = re.search(r"(\d+)\s*-\s*(\d+)", per)
        if rng and re.match(r"(?:Lease\s+)?Years", per, re.I) and int(rng.group(2)) > int(rng.group(1)):
            break                            # multi-year row: verify only the rows before it
        # A PSF column may sit beside annual and monthly, in either order:
        # the two LARGEST amounts are annual (max) and monthly (min).
        amts = sorted((_cents(a.replace("$", "").replace(",", "").strip())
                       for a in re.findall(_AMT, m.group(2))), reverse=True)[:2]
        if len(amts) == 2 and amts[1] * 50 < amts[0]:
            amts = [amts[0], _cents(amts[0] / 12)]      # small figure is a PSF, not monthly
        rows.append((re.sub(r"\s+", " ", per), amts[0], amts[-1]))
    if not rows:
        return None

    e = None
    for pat in (r"escalat\w*[^.%]{0,100}?(\d+(?:\.\d+)?)\s*%",
                r"(\d+(?:\.\d+)?)\s*%[^.]{0,60}(?:escalat|annual(?:ly)?\s+increase|per\s+lease\s+year)"):
        em = re.search(pat, t, re.I)
        if em:
            e = Decimal(em.group(1)) / 100
            break
    # PSF must sit in a rent sentence: a TI allowance "$5.00 per square foot"
    # elsewhere in the lease is not the rental rate.
    psf = re.search(r"rent[^.$]{0,100}?\$\s*(\d+(?:\.\d+)?)\s*(?:per|/)\s*(?:rentable\s+)?"
                    r"(?:square\s+foot|square\s+feet|RSF|SF)\b", t, re.I)
    rsf = re.search(r"Premises[^.]{0,200}?([\d,]{3,7})\s*(?:rentable\s+)?"
                    r"(?:square\s+feet|RSF|SF)\b", t, re.I)
    problems = []
    name1, a1, m1 = rows[0]
    if psf and rsf:
        rsf_n = Decimal(rsf.group(1).replace(",", ""))
        exp = _cents(Decimal(psf.group(1)) * rsf_n)
        tol = Decimal("0.005") * rsf_n
        if abs(exp - a1) > tol:
            problems.append(f"{name1} annual ${a1:,} != PSF ${psf.group(1)} x {rsf_n:,} RSF = ${exp:,}")
    if _cents(a1 / 12) != m1:
        problems.append(f"{name1} monthly ${m1:,} != annual/12 = ${_cents(a1 / 12):,}")

    later = rows[1:]
    if later:
        if e is None or e == 0:
            if e == 0 and any((a, m) != (a1, m1) for _, a, m in later):
                bad = next(r for r in later if (r[1], r[2]) != (a1, m1))
                problems.append(f"flat schedule (0% escalation) but {bad[0]} is "
                                f"${bad[1]:,} / ${bad[2]:,}, not ${a1:,} / ${m1:,}")
            elif e is None and all((a, m) == (a1, m1) for _, a, m in later):
                pass
            # e absent and rows differ: escalation unknown -- cannot verify.
        else:
            controls = bool(re.search(r"schedule\s+(?:shall\s+)?control", t, re.I))
            sets, exp_i, exp_ii = [], [], []
            pa, pm_, ca = a1, m1, a1
            for n, (name, a, m) in enumerate(later, start=1):
                pa = _cents(pa * (1 + e))                       # (i) chained annual
                closed = _cents(ca * (1 + e) ** n)              # (i) closed-form
                mi = _cents(pa / 12)
                pm_ = _cents(pm_ * (1 + e))                     # (ii) monthly
                ai_i = _cents(pm_ * 12)
                ok_i = (a, m) == (pa, mi) or (a, m) == (closed, _cents(closed / 12))
                ok_ii = (a, m) == (ai_i, pm_)
                sets.append(({"i"} if ok_i else set()) | ({"ii"} if ok_ii else set()))
                exp_i.append((name, pa, mi))
                exp_ii.append((name, ai_i, pm_))
            bad = next((k for k, s in enumerate(sets) if not s), None)
            if bad is not None:
                name, a, m = later[bad]
                problems.append(
                    f"{name} found ${a:,} / ${m:,}; expected (i annual-compounded) "
                    f"${exp_i[bad][1]:,} / ${exp_i[bad][2]:,}, (ii monthly-rounded) "
                    f"${exp_ii[bad][1]:,} / ${exp_ii[bad][2]:,}")
            elif not (set.intersection(*sets)) and not controls:
                k = next(k for k in range(1, len(sets)) if not (sets[0] & sets[k]))
                name, a, m = later[k]
                problems.append(f"{name} follows a different rounding method than "
                                f"{later[0][0]} (found ${a:,} / ${m:,}; the two methods "
                                f"diverge and the lease has no 'schedule controls' clause)")
    if not problems:
        return None
    return "; ".join(problems)


CHECKS.append(("T3", "HIGH", "Unfilled underscore blanks remain in an execution copy",
               None, _t3))
CHECKS.append(("T4", "BLOCK", "Exhibit/schedule stub or placeholder remains",
               None, _t4))
CHECKS.append(("D1", "MED", "Basic Lease Information value drifts from the body",
               None, _d1))
CHECKS.append(("D2", "HIGH", "Rent schedule arithmetic does not reproduce",
               None, _d2))


# ==========================================================================
# FORM MODES -- v2.7 long-form NNN line vs v3.0 short-form MG line (v3.0)
# ==========================================================================
# CHECKS above is the v2.7 registry and is NOT modified by anything below: a
# document resolved to the v2.7 family with no form conflict is scanned with
# exactly CHECKS (same 60 checks, same IDs, same severities, same output).
#
# The v3.0 master (ORA_MasterLease_ShallowBay_MultiTenantMG_v3.0) is a
# ~6,500-word rewrite, not an edit of v2.7. Measured 2026-10-15: the
# unmodified v2.7 scanner already reported "0 of 60" on the v3.0 master and
# all four v3.0 property templates -- that is the "lease_qc 0/60" in the
# 2026-10-08 v3.0 run memo -- but eleven of those passes were VACUOUS: the
# check's v2.7 trigger phrase does not occur in v3.0 wording, so the check
# never looked at the v3.0 provision at all (A7, B2, B3, B8, F6, F13, F14,
# F15, F16, F17, F20). v3.0 mode re-anchors each of those to v3.0 wording
# (same ID, label suffixed "-- v3.0 anchor"), marks F16 N/A because v3.0
# deliberately removed the provision it requires, and adds v3.0-only form
# checks F0 and F22-F26.

FORM_FAMILIES = ("v2.7", "v3.0")
_FOOTER_VER_RE = re.compile(r"ORA Master Lease v(\d+)\.(\d+)")

# Section headings that exist in one line and not the other (re.M on
# _linewise text). Two or more hits on one side, and fewer than two on the
# other, decides the structural family.
_STRUCT_MARKERS = {
    "v3.0": (r"^\s*ENTRY AND LANDLORD.S RIGHTS\.",
             r"^\s*SUBORDINATION, ATTORNMENT AND ESTOPPEL\.",
             r"^\s*EXHIBIT B\s*\n\s*RULES AND REGULATIONS\s*$",
             r"^\s*Definitions\.\s+In this Lease:"),
    "v2.7": (r"^\s*RIGHTS RESERVED BY LANDLORD\.",
             r"^\s*FINANCIAL STATEMENTS\.",
             r"^\s*ESTOPPEL CERTIFICATES\.",
             r"^\s*ENTRY FOR INSPECTIONS"),
}


def _family_of(ver):
    if ver is None:
        return None
    return {2: "v2.7", 3: "v3.0"}.get(ver[0])


def detect_form(raw, footer):
    """Read the form line from the footer tag and, independently, from the
    document's section structure. Returns a dict; never guesses a family the
    evidence does not support (None = not determinable)."""
    m = _FOOTER_VER_RE.search(footer or "")
    ver = (int(m.group(1)), int(m.group(2))) if m else None
    lw = re.sub(r"[ \t]+", " ", raw or "")
    hits = {fam: sum(1 for p in pats if re.search(p, lw, re.M))
            for fam, pats in _STRUCT_MARKERS.items()}
    struct = None
    if hits["v3.0"] >= 2 and hits["v2.7"] < 2:
        struct = "v3.0"
    elif hits["v2.7"] >= 2 and hits["v3.0"] < 2:
        struct = "v2.7"
    return {"version": f"v{ver[0]}.{ver[1]}" if ver else None, "version_tuple": ver,
            "footer_family": _family_of(ver), "structure_family": struct,
            "structure_hits": hits}


def resolve_form(det, declared=None):
    """(family, conflict_detail_or_None, include_F0).

    Explicit --form: the declared family is scanned, and F0 FAILS (BLOCK) if
    the footer tag or the structure contradicts it, or if neither confirms it.
    Auto: footer family, else structure family, else the legacy v2.7 default
    (preserves every pre-v3.0 result, e.g. a non-lease Exhibit B file); F0 is
    registered only if footer and structure disagree with each other."""
    ff, sf = det["footer_family"], det["structure_family"]
    if declared:
        bad = []
        if ff and ff != declared:
            bad.append(f"footer tag says ORA Master Lease {det['version']} ({ff} line)")
        if sf and sf != declared:
            bad.append(f"section structure is the {sf} line")
        if not ff and not sf:
            bad.append("no ORA Master Lease footer tag and no recognizable form structure")
        detail = (f"--form {declared} declared but " + "; ".join(bad) +
                  " -- this document is not a " + declared + " form; rescan with the "
                  "correct --form (or none, to auto-detect).") if bad else None
        return declared, detail, True
    if ff and sf and ff != sf:
        return ff, (f"footer tag says {det['version']} ({ff} line) but the section "
                    f"structure is the {sf} line -- vintage/footer forensics: the footer "
                    f"was carried onto a different form."), True
    return ff or sf or "v2.7", None, False


def _f0_check(detail):
    def fn(ctx):
        return detail
    return ("F0", "BLOCK", "Form/mode mismatch -- the scan mode does not match this document's form line",
            None, fn)


@functools.lru_cache(maxsize=16)
def _sentences(t):
    """Sentence split of the norm()'d text. Memoised (pure function of `t`): the
    power-rights and v3.0 checks call it ~15 times per scan on the same text."""
    return tuple(re.split(r"(?<=[.;])\s+(?=[A-Z(\[])", t))


def _sent_all(t, *pats):
    """True if ONE sentence matches every pattern (case-insensitive)."""
    return any(all(re.search(p, s, re.I) for p in pats) for s in _sentences(t))


# ---- v3.0 re-anchors of v2.7 checks (same ID, v3.0 wording) --------------

_V3_BASE_YEAR = r"exceed those for the Base Year|over (?:those for )?the Base Year|increase over base year"


def _v3_a7(t):
    if not re.search(_V3_BASE_YEAR, t, re.I):
        return True                     # MG form with no base-year stop at all
    return bool(re.search(r"net base rent|triple[- ]net|\bNNN\b", t, re.I))


def _v3_b2(t):
    for s in _sentences(t):
        if re.search(r"no (?:duty|obligation) to relet", s, re.I) and \
                not re.search(r"required by (?:applicable )?law", s, re.I):
            return True
    return False


def _v3_b3(t):
    for clause in re.split(r";", t):
        if re.search(r"Rent for the (?:rest|remainder|balance) of the Lease Term|accelerate and recover",
                     clause, re.I) and \
                not re.search(r"less the (?:net proceeds of any reletting|fair rental value)|"
                              r"net proceeds of any reletting|fair rental value", clause, re.I):
            return True
    return False


def _v3_b8(t):
    if not re.search(r"Landlord (?:provides|shall provide|furnishes) water|water[^.]{0,60}drinking", t, re.I):
        return False
    return not (_sent_all(t, r"reimburse Landlord|pay Landlord", r"invoice|bill")
                and re.search(r"sub-?meter|Proportionate Share of the (?:Building|Project).s charges|"
                              r"equitable allocation|flat rate of \$", t, re.I))


def _v3_f6(t):
    return bool(re.search(r"\(5\) Business Days (?:following the date when due|after it is due|late)", t, re.I)) \
        and not _defined(t, "Business Days?")


def _v3_f13(t):
    return bool(re.search(_V3_BASE_YEAR, t, re.I)) and not re.search(
        r"excluding (?:any )?costs billed directly to (?:any )?tenant|shall not include amounts separately billed|"
        r"excluding (?:any )?amounts? separately billed", t, re.I)


def _v3_f14(t):
    if not re.search(r"all risks? of physical loss|special form|all risk", t, re.I):
        return True                     # no property-insurance standard at all
    return bool(re.search(r"all risk", t, re.I)) and not re.search(r"special form", t, re.I)


def _v3_f15(t):
    return not (re.search(r"(?:only|solely) out of Landlord.s interest in the (?:Project|Building)", t, re.I)
                and "member, manager, officer, employee or agent of Landlord" in t)


def _v3_f17(t):
    return not re.search(r"preventi(?:ve|ative)[- ]maintenance contract[^.]{0,80}(?:HVAC|heating)|"
                         r"HVAC[^.]{0,80}preventi(?:ve|ative)[- ]maintenance contract", t, re.I)


def _v3_f19(t):
    return bool(re.search(r"if to Tenant,\s+at the (?:Demised )?Premises\s*[.;]|"
                          r"to Tenant only at the (?:Demised )?Premises", t, re.I)) \
        or not re.search(r"TENANT NOTICE ADDRESS:", t)


def _v3_f20(t):
    if not re.search(r"Lease Year after the first|second Lease Year|escalation percentage|"
                     r"per Lease Year, compounded", t, re.I):
        return False
    return ("[OPTIONAL: ATTACH RENT SCHEDULE" in t
            or not re.search(r"set (?:out|forth) in the following schedule", t, re.I)
            or not re.search(r"Rent Schedule controls|schedule (?:shall )?control", t, re.I))


V30_REANCHOR = {
    "A7": ("BLOCK", "Base-year MG form lacks its base-year expense stop, or carries a 'net' label — v3.0 anchor", _v3_a7),
    "B2": ("HIGH", "'No duty to relet' not qualified by 'except to the extent required by law' in the same sentence — v3.0 anchor", _v3_b2),
    "B3": ("MED", "Rent-for-the-rest-of-the-Term remedy without credit for reletting proceeds / fair rental value — v3.0 anchor", _v3_b3),
    "B4": ("MED", "Holdover multiplier applied to accrued arrears ('N% of the amount of (a)') — v3.0 anchor", lambda t: bool(re.search(r"percent \(\d+%\) of the amount of \(a\)", t, re.I))),
    "B8": ("MED", "Landlord-provided water with no invoice reimbursement + measurement mechanism — v3.0 anchor", _v3_b8),
    "F6": ("LOW", "Late fee runs on Business Days and 'Business Day' is undefined — v3.0 anchor", _v3_f6),
    "F13": ("MED", "Operating Costs lack the directly-billed-costs exclusion (double-recovery risk) — v3.0 anchor", _v3_f13),
    "F14": ("MED", "Property insurance not on an all-risk (special form) basis — v3.0 anchor", _v3_f14),
    "F15": ("MED", "Landlord exculpation (interest-in-Project cap + manager/member/officer/employee/agent enumeration) missing — v3.0 anchor", _v3_f15),
    "F17": ("MED", "No continuous HVAC preventive-maintenance contract — v3.0 anchor", _v3_f17),
    "F19": ("HIGH", "Tenant notices routed to the Premises only / no TENANT NOTICE ADDRESS — v3.0 anchor", _v3_f19),
    "F20": ("MED", "Escalating rent without a mandatory, controlling Rent Schedule — v3.0 anchor", _v3_f20),
}

# Checks that are deliberately NOT run in v3.0 mode: the provision they require
# was removed from the v3.0 master by ratified firm-wide position (2026-10-08
# run memo, "Firm-wide positions now set by the master"). Reported as N/A,
# never as a pass and never as a failure.
V30_NA = {
    "F16": "v3.0 deliberately has no excess-rent/profit capture: assignment is sole-discretion "
           "consent with cost reimbursement only (no recapture, profit share or transfer fee) "
           "-- ratified v3.0 position, 2026-10-08 run memo.",
}


# ---- v3.0-only form checks (F22-F26) ---------------------------------------

_V3_XREF_RE = re.compile(r"\bthe ((?:[A-Z][A-Za-z']+)(?: (?:and|of|[A-Z][A-Za-z']+))*) section\b")
_HEAD_CAPS_RE = re.compile(r"^\s*([A-Z][A-Z0-9 ;,&'’-]{2,}?)\.(?:\s|$)", re.M)
_HEAD_RUNIN_RE = re.compile(r"^\s*([A-Z][A-Za-z'’]+(?:[ ;,]+[A-Za-z'’]+){0,6})\.\s{1,3}\S", re.M)


def _v3_f22(ctx):
    """Dead 'the <Name> section' cross-reference (v3.0 refers to sections by
    NAME, never by number). Every name must resolve to a caps heading or a
    run-in sub-heading. Catches, among others, a Specialized Equipment module
    deleted without deleting the references to it."""
    lw = _linewise(ctx).replace("’", "'")
    heads = {h.strip().upper().replace("’", "'") for h in _HEAD_CAPS_RE.findall(lw)}
    heads |= {h.strip().upper() for h in _HEAD_RUNIN_RE.findall(lw)}
    parts = set()
    for h in heads:
        parts |= {p.strip() for p in re.split(r";", h)}
    dead = []
    for name in _V3_XREF_RE.findall(ctx["t"]):
        if name.upper() not in heads and name.upper() not in parts:
            dead.append(name)
    if not dead:
        return None
    return "no heading for: " + ", ".join(f"'the {n} section'" for n in sorted(set(dead)))


_RELOCATION_RE = (r"\brelocat\w*\b[^.]{0,160}\b(?:Premises|space|tenant)\b|right to relocate|"
                  r"substitute premises|Relocation Premises")


def _v3_f25(ctx):
    lines = ctx["raw"].replace("\xa0", " ").split("\n")
    for i, ln in enumerate(lines):
        if re.match(r"\s*EXHIBIT B\s*$", ln) and any(
                re.match(r"\s*RULES AND REGULATIONS\s*$", x) for x in lines[i + 1:i + 3]):
            words = len(" ".join(lines[i + 1:]).split())
            return None if words >= 150 else f"Exhibit B heading has only {words} word(s) of rules"
    return True


def _v3_f26(ctx):
    t = ctx["t"]
    has_head = bool(re.search(r"^\s*SPECIALIZED EQUIPMENT\.", _linewise(ctx), re.M))
    refs = re.findall(r"Specialized Equipment|Approved Consumables|Dedicated Circuit", t)
    if refs and not has_head:
        return (f"Specialized Equipment module deleted but {len(refs)} reference(s) to it remain "
                f"(module deletion note: delete the section, the Approved Consumables reference in "
                f"ENVIRONMENTAL MATTERS and the 'Except as provided in the Specialized Equipment "
                f"section' words in MAINTENANCE AND REPAIRS)")
    if has_head and not ctx.get("is_template") and "[OPTIONAL MODULE" in t:
        return "Specialized Equipment module kept but its [OPTIONAL MODULE ...] drafting instruction remains"
    return None


V30_EXTRA = [
    ("F22", "HIGH", "Dead 'the <Name> section' cross-reference — v3.0 standard", None, _v3_f22),
    bool_check("F23", "HIGH", "Relocation right present (v3.0 firm-wide position: no relocation right) — v3.0 standard",
               lambda t: bool(re.search(_RELOCATION_RE, t, re.I))),
    bool_check("F24", "MED", "Financial-statements demand present (v3.0 firm-wide position: no financial-statements section) — v3.0 standard",
               lambda t: bool(re.search(r"financial statements?", t, re.I))),
    ("F25", "MED", "Exhibit B Rules and Regulations not embedded (v3.0 carries its own one-page Exhibit B) — v3.0 standard",
     None, _v3_f25),
    ("F26", "HIGH", "Optional Specialized Equipment module half-deleted or instruction left in an execution copy — v3.0 standard",
     None, _v3_f26),
]


# ==========================================================================
# POWER-RIGHTS STANDARD (FP1-FP8) -- next-build energy provisions
# ==========================================================================
# F-class form standard keyed to the NEXT builds: v2.8 (NNN long-form line)
# and v3.1 (MG short-form line). Off by default: on any form older than
# that it is evaluated and REPORTED AS PENDING (provision present/absent),
# never counted as a failure, so today's v2.7/v3.0 paper is unaffected.
# Enforced (normal failures) when the footer declares >= v2.8 / >= v3.1, or
# when --power-rights forces it on (pre-release drafting of v2.8/v3.1).
# Anchors are keyword co-occurrence (one sentence, or one section window),
# not exact sentences: final wording is not settled.

POWER_MIN = {2: 8, 3: 1}


def power_active(ver):
    if ver is None:
        return False
    major, minor = ver
    return minor >= POWER_MIN[major] if major in POWER_MIN else major > max(POWER_MIN)


def _paras(ctx):
    return _paras_of(ctx["raw"])


@functools.lru_cache(maxsize=16)
def _paras_of(raw):
    """Normalised non-empty paragraphs of `raw` (memoised; pure function)."""
    return tuple(re.sub(r"\s+", " ", norm(p)).strip()
                 for p in raw.replace("\xa0", " ").split("\n") if p.strip())


def _window(ctx, *must, span=4):
    """Text of each paragraph matching all `must` patterns plus the next
    `span`-1 paragraphs (one provision can run over several subsections)."""
    ps = _paras(ctx)
    out = []
    for i, p in enumerate(ps):
        if all(re.search(m, p, re.I) for m in must):
            out.append(" ".join(ps[i:i + span]))
    return out


_ENERGY = r"solar|photovoltaic|energy (?:storage|equipment|system|facilit|generation)|batter(?:y|ies)|Energy Equipment"  # +generation: Phase 1 v2.8/v3.1 wording "energy generation, storage, ..."


def _fp1(ctx):
    wins = _window(ctx, r"reserv", r"roof")
    if not wins:
        return "no Landlord reservation of roof/exterior rights found"
    w = " ".join(wins)
    miss = [label for label, pat in (
        ("solar", r"solar|photovoltaic"),
        ("energy storage", r"storage|batter(?:y|ies)"),
        ("EV charging", r"electric[- ]vehicle|\bEV\b"),   # hyphenated form: Phase 1 v2.8/v3.1 wording
        ("telecom", r"telecom|antenna|wireless|communications"),
        ("exterior", r"exterior"),
        ("revenue belongs to Landlord",
         r"(?:revenue|income|rent|payments?|proceeds|credits|incentives)[^.]{0,160}(?:belong|inure|accrue|payable|retained)[^.]{0,30}(?:solely |exclusively )?to Landlord|"
         r"Landlord[^.]{0,60}(?:entitled to|retain|keep)[^.]{0,60}(?:all )?(?:revenue|income|proceeds)"),
        ("no abatement",
         r"without (?:any )?(?:abatement|reduction) (?:of|in) Rent|no abatement|Rent (?:shall )?(?:does )?not abate|not (?:be an eviction or )?entitle Tenant to (?:any )?abatement|without liability or abatement"),  # +"not be an eviction or entitle": Phase 1 wording
    ) if not re.search(pat, w, re.I)]
    if ctx.get("_form_family") == "v3.0" and re.search(_RELOCATION_RE, ctx["t"], re.I):
        miss.append("NO relocation right (v3.x) -- a relocation right is present")
    return ("roof/exterior/energy reservation lacks: " + ", ".join(miss)) if miss else None


def _fp2(ctx):
    t, miss = ctx["t"], []
    if not _sent_all(t, r"easements?", r"utilit|interconnect"):
        miss.append("utility/interconnection easements")
    if not _sent_all(t, r"shut-?downs?|shut-?offs?|outages?|interruptions?",
                     r"electric|power", r"twenty-four \(24\) hours|\b24 hours"):
        miss.append("planned electrical shutdowns on >= twenty-four (24) hours' notice")
    return ("lacks: " + "; ".join(miss)) if miss else None


def _fp3(ctx):
    t, miss = ctx["t"], []
    if not _sent_all(t, r"Tenant (?:shall|may) not|Tenant shall have no right", r"utility|utilities",
                     r"(?:new|upgraded|additional|increased|upgrade)[^.]{0,40}(?:electric|service|capacity)|interconnect",
                     r"consent|approval"):
        miss.append("no tenant utility application (new/upgraded service or interconnection) without consent")
    if not _sent_all(t, r"capacity|service upgrade|electrical (?:service|infrastructure)",
                     r"part of the (?:Project|Building|Premises)|Landlord.s (?:sole )?property|property of Landlord|belong(?:s)? to Landlord"):
        miss.append("added electrical capacity is part of the Project")
    if not _sent_all(t, r"capacity|electrical (?:service|infrastructure|upgrade)",
                     r"(?:not|never) (?:be )?(?:required|obligated) to remove|need not remove|shall not (?:be required to )?remove|"
                     r"excluded from[^.]{0,40}(?:removal|restoration)|not subject to[^.]{0,40}remov|carve|notwithstanding[^.]{0,80}remov"):
        miss.append("added capacity carved out of Tenant's removal obligations")
    return ("lacks: " + "; ".join(miss)) if miss else None


def _fp4(ctx):
    miss = []
    wins = _window(ctx, r"Operating Costs", _ENERGY, span=2)
    w = " ".join(wins)
    if not (wins and re.search(r"exclu|not include|not be included|not credited|shall not reduce", w, re.I)
            and re.search(r"\bcosts?\b", w, re.I) and re.search(r"revenues?|income", w, re.I)):
        miss.append("Operating Costs exclusion of BOTH costs and revenues of Landlord energy equipment")
    if not _sent_all(ctx["t"], r"roof", r"repair|replace", r"Operating Costs|included|not (?:be )?excluded",
                     r"merely|solely|only because|by reason of|even (?:if|though)|notwithstanding|presence|located on"):
        miss.append("roof repair/replacement not excluded merely because energy equipment is on the roof")
    return ("lacks: " + "; ".join(miss)) if miss else None


def _fp5(ctx):
    ok = _sent_all(ctx["t"], r"(?:utility|energy|consumption|usage|meter|interval|billing)[^.]{0,30}(?:data|information|records)|data[^.]{0,30}(?:utility|energy)",
                   r"authori[sz]", r"ten \(10\) (?:Business )?days|\b10 days")
    return None if ok else "no Tenant utility-data authorization within ten (10) days"


def _fp6(ctx):
    ok = _sent_all(ctx["t"], r"estoppel|acknowledg", r"lessee|licensee",
                   r"energy|solar|Energy Provider|Energy Equipment", r"financ|lender|tax equity|secured part")
    return None if ok else "no estoppel/acknowledgment to energy-provider lessees/licensees and their financing parties"


def _single_tenant_exclusive_parking(t):
    """Single-tenant form: Tenant has EXCLUSIVE parking and the lease defines no
    parking allocation/share at all (OH-SingleTenant-NNN conversion). Both halves
    are required, so a multi-tenant lease never takes FP7's single-tenant branch."""
    return bool(re.search(r"(?<!non-)(?<!non)exclusive right to use the parking areas", t, re.I)) and not re.search(
        r"Tenant.s Allocation|parking allocation|share of the (?:unreserved )?parking spaces|"
        r"non-exclusive right to use the unreserved parking", t, re.I)


def _fp7(ctx):
    t, miss = ctx["t"], []
    if not _sent_all(t, r"Landlord may", r"install|operate|construct", r"electric[- ]vehicle|\bEV\b", r"charg"):  # hyphenated form: Phase 1
        miss.append("Landlord right to install EV charging")
    if _single_tenant_exclusive_parking(t):
        # Single-tenant paper (entire building, exclusive parking, no parking allocation
        # to exclude spaces from): the allocation sentence is dropped by design
        # (Gabriel, 2026-10-15, "Drop allocation sentence"), so only the designation
        # right itself is required here; the reasonable-access proviso below still is.
        if not _sent_all(t, r"charging", r"spaces?", r"designat"):
            miss.append("Landlord right to designate charging spaces (single-tenant form)")
    elif not _sent_all(t, r"charging", r"spaces?", r"designat",
                       r"exclu|not (?:count|be included|form part)|reduc"):
        miss.append("designated charging spaces excluded from Tenant's parking allocation")
    if not _sent_all(t, r"reasonable access", r"Tenant", r"operations|business|loading|Premises"):
        miss.append("Tenant keeps reasonable access for its operations")
    return ("lacks: " + "; ".join(miss)) if miss else None


def _fp8(ctx):
    lw = _linewise(ctx)
    m = re.search(r"^\s*TENANT BACKUP POWER AND ENERGY STORAGE\b.*$", lw, re.M | re.I)
    if not m:
        return None                    # optional module not included: nothing to verify
    rest = lw[m.start():]
    nxt = re.search(r"\n\s*[A-Z][A-Z ;,&'’-]{5,}\.(?:\s|$)", rest[len(m.group(0)):])
    mod = norm(rest[:len(m.group(0)) + (nxt.start() if nxt else len(rest))])
    miss = [label for label, pat in (
        ("bracketed include-only-if instruction", r"\[[^\]]*INCLUDE ONLY IF"),
        ("counsel-review note", r"counsel[^.\]]{0,80}review|review[^.\]]{0,80}counsel"),
        ("UL 9540", r"UL 9540(?!A)"),
        ("UL 9540A", r"UL 9540A"),
        ("NFPA 855", r"NFPA 855"),
        ("NFPA 37", r"NFPA 37\b"),
        ("NFPA 110", r"NFPA (?:37\s*(?:/|and|,)\s*)?110\b"),
        ("transfer switch", r"transfer switch"),
        ("no back-feed", r"(?:no|not|never|prevent\w*|without|prohibit\w*)[^.]{0,80}back-?feed"),
    ) if not re.search(pat, mod, re.I)]
    return ("TENANT BACKUP POWER AND ENERGY STORAGE module lacks: " + ", ".join(miss)) if miss else None


POWER_CHECKS = [
    ("FP1", "HIGH", "Landlord reserved roof/exterior/energy rights (solar, storage, EV, telecom; revenue to Landlord; no abatement) — power-rights standard", None, _fp1),
    ("FP2", "HIGH", "Utility/interconnection easements and planned electrical shutdowns on 24 hours' notice — power-rights standard", None, _fp2),
    ("FP3", "HIGH", "No tenant utility application without consent; added capacity is Project property, carved out of removal — power-rights standard", None, _fp3),
    ("FP4", "MED", "Operating Costs exclude energy-equipment costs and revenues; roof repair not excluded merely because equipment is on the roof — power-rights standard", None, _fp4),
    ("FP5", "MED", "Tenant utility-data authorization within ten (10) days — power-rights standard", None, _fp5),
    ("FP6", "MED", "Estoppel/acknowledgment to energy-provider lessees/licensees and their financing parties — power-rights standard", None, _fp6),
    ("FP7", "MED", "Landlord EV charging; charging spaces excluded from Tenant's parking allocation; Tenant keeps reasonable access — power-rights standard", None, _fp7),
    ("FP8", "HIGH", "Optional TENANT BACKUP POWER AND ENERGY STORAGE module incomplete (bracket, counsel note, UL 9540/9540A, NFPA 855/37/110, transfer switch, no back-feed) — power-rights standard", None, _fp8),
]


def _with_family(checks, family):
    """Give ctx-aware checks the resolved family (FP1's v3.x relocation rule)
    without touching ora_doc_qc.scan()'s ctx construction."""
    out = []
    for cid, sev, title, pos, fn in checks:
        def wrapped(ctx, _fn=fn):
            ctx["_form_family"] = family
            return _fn(ctx)
        out.append((cid, sev, title, pos, wrapped))
    return out


def build_registry(family, f0_detail=None, include_f0=False, power=False):
    """(checks, na) for one scan. The v2.7 family with no F0 and no power
    checks returns CHECKS itself, unchanged (identity, not a copy)."""
    na = []
    if family == "v3.0":
        checks = []
        for c in CHECKS:
            cid = c[0]
            if cid in V30_NA:
                na.append({"id": cid, "title": c[2], "reason": V30_NA[cid]})
            elif cid in V30_REANCHOR:
                sev, label, test = V30_REANCHOR[cid]
                checks.append(bool_check(cid, sev, label, test))
            else:
                checks.append(c)
        checks += V30_EXTRA
        include_f0 = True
    else:
        checks = CHECKS
    extra = []
    if include_f0:
        extra.append(_f0_check(f0_detail))
    if power:
        extra += _with_family(POWER_CHECKS, family)
    if extra:
        checks = list(checks) + extra
    return checks, na


def plan_scan(path, declared=None, force_power=False, allow_ocr=True):
    """Resolve form + registry for one file before scanning it. Extraction
    errors fall back to the legacy registry so scan() reports them itself."""
    try:
        body, meta = extract(path, allow_ocr=allow_ocr, want_footer=True)
    except Exception:                                               # noqa: BLE001
        body, meta = None, {"footer": ""}
    return plan_from_text(body, meta, declared, force_power)


def plan_from_text(body, meta, declared=None, force_power=False):
    """plan_scan() on already-extracted text: the single place a (body, footer)
    pair is resolved to a form line + registry. The mutation suite
    (tests/test_lease_qc_mutations.py) plans every in-memory mutant through
    this exact function, so a mutant is scanned with the registry the CLI
    would use on the same document."""
    det = detect_form(body or "", meta.get("footer", ""))
    family, f0_detail, include_f0 = resolve_form(det, declared)
    ver = det["version_tuple"]
    if declared and det["footer_family"] != declared:
        ver = None                      # a contradicted version tag cannot switch power on
    active = force_power or power_active(ver)
    checks, na = build_registry(family, f0_detail, include_f0, power=active)
    return {"form": {"declared": declared, "resolved": family, "version": det["version"],
                     "footer_family": det["footer_family"],
                     "structure_family": det["structure_family"],
                     "mismatch": f0_detail,
                     "power_rights": ("ENFORCED" + (" (--power-rights)" if force_power and not power_active(ver) else ""))
                     if active else "PENDING"},
            "checks": checks, "na": na, "body": body, "meta": meta,
            "power_active": active, "family": family}


def pending_power(plan, path, allow_tokens=False):
    """Evaluate FP1-FP8 without enforcing them (form older than v2.8/v3.1)."""
    if plan["power_active"] or plan["body"] is None:
        return []
    name = os.path.basename(path)
    ctx = {"t": norm(plan["body"]), "raw": plan["body"], "meta": plan["meta"], "name": name,
           "allow_tokens": allow_tokens, "is_template": "_TEMPLATE" in name.upper()}
    fails = {f["id"]: f["detail"] for f in run_checks(ctx, _with_family(POWER_CHECKS, plan["family"]))}
    return [{"id": cid, "title": title,
             "status": "absent" if cid in fails else ("not included (optional)" if cid == "FP8" else "present"),
             "detail": fails.get(cid)} for cid, _sev, title, _pos, _fn in POWER_CHECKS]


def print_mode_block(r):
    f = r.get("form") or {}
    print(f"FORM       resolved {f.get('resolved')}"
          + (f" (declared --form {f['declared']})" if f.get("declared") else " (auto)")
          + f"; footer tag {f.get('version') or 'none'}; structure {f.get('structure_family') or 'undetermined'}"
          + f"; power-rights {f.get('power_rights')}")
    if f.get("mismatch"):
        print("!" * 78)
        print("FORM MISMATCH - F0 BLOCK: " + f["mismatch"])
        print("!" * 78)
    for x in r.get("na", []):
        print(f"[N/A  ] {x['id']:<5} {x['title']}")
        for line in re.findall(r".{1,70}(?:\s|$)", x["reason"]):
            print(f"           {line.strip()}")
    pend = r.get("pending") or []
    if pend:
        n = sum(1 for p in pend if p["status"] == "present" and p["id"] != "FP8")
        print(f"PENDING    power-rights standard not enforced on this form (needs >= v2.8 NNN / "
              f">= v3.1 MG); {n} of 7 required provisions already present:")
        for p in pend:
            print(f"  [PEND ] {p['id']:<4} {p['status']:<24} {p['title'][:44]}")
    print()


# ==========================================================================
# --loi-conformance mode -- deal-terms register vs. drafted lease
# ==========================================================================
# lease-generation's SKILL.md ("3. Gates", item 4) hands this skill a second
# job: replicate its "LOI conformance matrix" as a scanner-owned, testable
# output instead of the manual judgment call lease-generation currently
# makes by hand. Field categories and the status vocabulary (CONFORMS /
# CONFORMS+ / PARTIAL / MISSING / CONFLICT) come from that SKILL.md section
# and from references/deal-terms-register.schema.json's top-level deal-fact
# groups (16 of them, excluding pure metadata: deal_id, source_documents,
# template, ratified_position_departures, decision_gates, open_items).
#
# Deliberately a SEPARATE code path from CHECKS/run_checks() above: it
# answers "does the drafted lease match THIS DEAL's negotiated terms", not
# "does ORA's paper carry its known systemic defects" -- a different
# question, against a different source of truth (a per-deal JSON register,
# not the fixed defect registry), with a different output shape (a matrix,
# not BLOCK/HIGH/MED/LOW findings). It reuses ora_doc_qc.extract()/norm()
# for text, unchanged, and touches no shared aggregation code.

_MONEY_RE_CACHE = {}


def _find_dollar_amount(text, amount):
    """A dollar figure equal to `amount`, matched to the EXACT CENT, written
    with comma grouping and either no decimal (a whole-dollar amount) or the
    matching '.NN'. Returns None on any other cents (including a bare
    integer prefix of a different figure, e.g. amount=2000 must NOT match
    "$2,000.50" in the text -- register rents are routinely rsf * rate / 12
    and essentially never land on a whole dollar, so truncating to int()
    before matching silently treated a genuinely CONFLICTing cents figure
    as a match; caught in independent review)."""
    if amount is None:
        return None
    cents = round(float(amount) * 100)
    pat = _MONEY_RE_CACHE.get(cents)
    if pat is None:
        whole, frac = divmod(cents, 100)
        num = f'{whole:,}' + (f'.{frac:02d}' if frac else r'(?:\.00)?')
        # (?!\d)(?!\.\d): a following digit, or a decimal point introducing
        # a DIFFERENT cents figure, both fail the match -- \b alone sits
        # right after the whole-dollar digits regardless of what follows,
        # so it would otherwise also match e.g. "$2,000.50" against a
        # whole-dollar 2000 register figure.
        pat = re.compile(r'\$\s*' + num + r'(?!\d)(?!\.\d)')
        _MONEY_RE_CACHE[cents] = pat
    m = pat.search(text)
    return m.group(0) if m else None


def _num_pattern(n):
    """Word-boundary pattern matching `n` written with or without comma
    grouping (e.g. 2400 or 2,400)."""
    n = int(n)
    variants = sorted({str(n), f'{n:,}'}, key=len, reverse=True)
    return r'\b(?:' + '|'.join(re.escape(v) for v in variants) + r')\b'


def _phrase_present(phrase, text, window=200, threshold=1.0):
    """True if `phrase`'s words are found in `text`, at the given
    `threshold` fraction (default 1.0 = every word).

    threshold=1.0 (the enum-value mode -- utilities): every word of
    `phrase` (underscores treated as spaces) must appear in `text` within
    `window` characters of the phrase's first word. Looser than a literal
    substring match, which real lease prose almost never produces verbatim
    from a register enum value, but still specific enough that unrelated
    text does not satisfy it.

    threshold<1.0 (the free-text-description mode -- landlord_work items,
    signage): register text here is a HUMAN-WRITTEN sentence
    ('one exterior sign over entrance + entry door signage,
    Landlord-approved'), not a fixed enum value a drafting engine copies
    verbatim -- requiring literal presence of every word (including a
    stray '+' or a hyphenated 'Landlord-approved') made these rows
    essentially unfailable to CONFORM against ORA's own canonical example
    register, which independent review flagged as a gate that degrades
    into permanent noise. This mode instead requires `threshold` of the
    phrase's SIGNIFICANT words (>=5 chars, surrounding punctuation
    stripped) to appear anywhere in `text` (no window/proximity
    requirement -- a work-item description and its lease implementation
    are not reliably adjacent). The 5-char floor specifically excludes
    short, generic words ('over', 'door', 'sign') that would otherwise
    make an UNRELATED lease register a false hit almost as often as a
    real one.
    """
    raw_words = [w for w in re.split(r'[\s_]+', phrase or "") if w]
    if threshold >= 1.0:
        if not raw_words:
            return False
        for m in re.finditer(re.escape(raw_words[0]), text, re.I):
            seg = text[m.start():m.start() + window]
            if all(re.search(re.escape(w), seg, re.I) for w in raw_words[1:]):
                return True
        return False
    words = [re.sub(r'^\W+|\W+$', '', w) for w in raw_words]
    sig = [w for w in words if len(w) >= 5]
    if not sig:
        return False
    hits = sum(1 for w in sig if re.search(re.escape(w), text, re.I))
    return (hits / len(sig)) >= threshold


def _find_entity_in_text(entity_name, text):
    if not entity_name:
        return None
    return entity_name if re.search(re.escape(entity_name), text, re.I) else None


_SECTION_HINTS = {
    "landlord": "PARTIES / BASIC LEASE INFORMATION",
    "tenant": "PARTIES / BASIC LEASE INFORMATION",
    "co_tenants": "PARTIES (co-tenant joinder, ratified position 2)",
    "premises": "DEMISED PREMISES",
    "use": "USE OF PREMISES",
    "term": "TERM",
    "options": "OPTIONS TO EXTEND",
    "rent": "RENT",
    "expense_structure": "OPERATING COSTS / RENT",
    "utilities": "UTILITIES",
    "security_deposit": "SECURITY DEPOSIT",
    "parking": "PARKING",
    "landlord_work": "LANDLORD'S WORK / EXHIBIT B",
    "maintenance": "MAINTENANCE AND REPAIRS",
    "insurance": "INSURANCE",
    "broker": "BROKER",
    "signage": "SIGNAGE",
    "open_items": "DEAL-TERMS REGISTER open_items",
}


def _check_landlord(reg, text):
    entity = (reg.get("landlord") or {}).get("entity")
    if not entity:
        return {"status": "MISSING", "detail": "register has no landlord.entity"}
    if _find_entity_in_text(entity, text):
        return {"status": "CONFORMS", "detail": f"landlord entity '{entity}' found in lease text"}
    return {"status": "MISSING", "detail": f"landlord entity '{entity}' not found in lease text"}


def _check_tenant(reg, text):
    entity = (reg.get("tenant") or {}).get("entity")
    if not entity:
        return {"status": "MISSING", "detail": "register has no tenant.entity"}
    if _find_entity_in_text(entity, text):
        return {"status": "CONFORMS", "detail": f"tenant entity '{entity}' found in lease text"}
    return {"status": "MISSING", "detail": f"tenant entity '{entity}' not found in lease text"}


def _check_co_tenants(reg, text):
    co_tenants = (reg.get("tenant") or {}).get("co_tenants") or []
    if not co_tenants:
        return {"status": "CONFORMS", "detail": "register lists no co-tenants"}
    hits = [n for n in co_tenants if _find_entity_in_text(n, text)]
    if len(hits) == len(co_tenants):
        if re.search(r'joint(?:ly)? and several(?:ly)?', text, re.I):
            return {"status": "CONFORMS",
                    "detail": f"co-tenant(s) {', '.join(co_tenants)} found, with "
                              f"joint-and-several language (ratified position 2)"}
        return {"status": "PARTIAL",
                "detail": "co-tenant(s) named but no joint-and-several language found "
                          "(ratified position 2 -- co-tenancy, never a guaranty)"}
    if not hits:
        return {"status": "MISSING",
                "detail": f"none of the register's co-tenant(s) {', '.join(co_tenants)} found"}
    return {"status": "PARTIAL",
            "detail": f"only {len(hits)} of {len(co_tenants)} co-tenant(s) found"}


def _check_premises(reg, text):
    p = reg.get("premises") or {}
    fields = [
        ("address", p.get("address"), lambda v: re.escape(v)),
        # Word-boundary anchored: an un-anchored suite match (e.g. suite
        # "1") matched somewhere inside virtually every lease regardless of
        # whether the real suite was mentioned at all -- caught in
        # independent review.
        ("suite", p.get("suite"), lambda v: r'\b' + re.escape(str(v)) + r'\b'),
        ("rsf", p.get("rsf"), lambda v: _num_pattern(v)),
    ]
    total = [f for f in fields if f[1] not in (None, "")]
    if not total:
        return {"status": "MISSING", "detail": "register has no premises fields"}
    missing = [label for label, val, patfn in total
               if not re.search(patfn(val), text, re.I)]
    if not missing:
        return {"status": "CONFORMS", "detail": "address/suite/RSF all found in lease text"}
    if len(missing) == len(total):
        return {"status": "MISSING", "detail": "none of address/suite/RSF found in lease text"}
    return {"status": "PARTIAL", "detail": f"missing: {', '.join(missing)}"}


def _check_use(reg, text):
    use = (reg.get("use") or {}).get("permitted_use")
    if not use:
        return {"status": "CONFORMS", "detail": "register specifies no restricted permitted use"}
    if re.search(re.escape(use), text, re.I):
        return {"status": "CONFORMS", "detail": f"permitted use '{use}' found"}
    return {"status": "MISSING", "detail": f"permitted use '{use}' not found in lease text"}


def _check_term(reg, text):
    term = reg.get("term") or {}
    months = term.get("months")
    if months is None:
        return {"status": "MISSING", "detail": "register has no term.months"}
    months_found = bool(re.search(_num_pattern(months) + r'\s*\)?\s*months?', text, re.I))
    # CONFORMS+ is grounded in the register's OWN term.early_access field,
    # not a bare text search for "early access" -- a text-only search
    # cannot tell "the register requires this and the lease has it" (plain
    # CONFORMS) from "the lease grants something the register never asked
    # for" (CONFORMS+), and mislabeled the former as the latter; caught in
    # independent review.
    early_access_required = bool(term.get("early_access"))
    early_access_found = bool(re.search(r'early access|early entry', text, re.I))
    if months_found:
        if early_access_required:
            if early_access_found:
                return {"status": "CONFORMS",
                        "detail": f"{months}-month term and the register's required "
                                  f"early access both found"}
            return {"status": "PARTIAL",
                    "detail": f"{months}-month term found, but the register's required "
                              f"early access ('{term['early_access']}') was not"}
        if early_access_found:
            return {"status": "CONFORMS+",
                    "detail": f"{months}-month term found, plus an early-access grant "
                              f"the register does not require"}
        return {"status": "CONFORMS", "detail": f"{months}-month term found"}
    m = re.search(r'[Tt]erm[^.]{0,60}?(\d{1,3})\s*\)?\s*months?', text)
    if m and int(m.group(1)) != int(months):
        return {"status": "CONFLICT",
                "detail": f"lease states {m.group(1)} months vs register's {months}"}
    return {"status": "MISSING", "detail": f"no {months}-month term language found"}


def _check_options(reg, text):
    opts = reg.get("options") or []
    if not opts:
        return {"status": "CONFORMS",
                "detail": "register specifies no options (ORA ratified position 6 default)"}
    hits = 0
    for o in opts:
        m = o.get("months")
        if m is None:
            continue
        pat = _num_pattern(m) + r'\s*\)?\s*months?'
        if (re.search(pat + r'.{0,80}option', text, re.I | re.S)
                or re.search(r'option.{0,80}' + pat, text, re.I | re.S)):
            hits += 1
    if hits == len(opts):
        return {"status": "CONFORMS", "detail": f"{hits} of {len(opts)} option(s) found"}
    if hits == 0:
        return {"status": "MISSING", "detail": "no option-term language found"}
    return {"status": "PARTIAL", "detail": f"only {hits} of {len(opts)} option(s) found"}


# Escalation verbs. Deliberately NOT 'annual'/'per annum'/'Lease Year' on
# their own: 'Annual Base Rent' is a defined term and the default-rate clause
# reads 'eighteen percent (18%) per annum', so those words do not mark a
# percentage as a rent escalation.
_ESC_CONTEXT_RE = re.compile(
    r'\b(?:escalat\w*|increas\w*|anniversar\w*|step(?:s|ped)?\s+up|bumps?)\b',
    re.I)
# 'adjust-' is deliberately absent (REFUTE round 3): ORA's master form has a
# condemnation clause in which Rent is 'adjusted' beside a 25% taking
# threshold, which made every master-form lease CONFLICT.
_RENT_TERM_RE = re.compile(r'\brent\b', re.I)
# Sentence/clause boundary: '.', ';', '!' or '?' followed by whitespace (a
# decimal point inside '3.5%' has no whitespace after it, so it never
# splits). NOT ':' -- 'Base Rent: ... 3.0%' must stay one clause.
_CLAUSE_SPLIT_RE = re.compile(r'(?<=[.;!?])\s+')

# Any stated percentage. Anchored: the lookbehind rejects a digit, a decimal
# point or a fraction slash, so '13%', '3.5%' and '2-1/2%' never yield a bare
# '3%' / '5%' / '2%' (audit row leaseqc-checkrent-escalation-failopen,
# 2026-11-08, plus the REFUTE pass on it: re.escape('3%') matched inside '13%').
_PCT_RE = re.compile(r'(?<![\d./])(\d+(?:\.\d+)?)\s*(?:%|percent\b)', re.I)


def _escalation_pcts(text):
    """Every percentage stated in a rent-escalation clause: a sentence/clause
    that names rent AND carries an escalation verb. A 3% proportionate share,
    management fee or expense cap elsewhere never qualifies (REFUTE pass,
    2026-11-08: a 'nearest percentage to any keyword' rule let ORA's own 3.00%
    proportionate-share clause satisfy a 3% register next to a 3.5% rent
    escalation). A clause with an escalation verb that directly FOLLOWS a
    clause naming rent also qualifies ('Base Rent for Lease Year 1 is $X.
    Thereafter, it shall increase by 3.5% annually.'), since the step clause
    need not repeat the word.

    Within a qualifying clause, each escalation keyword contributes only the
    percentage NEAREST to it, within _ESC_PCT_GAP characters, searched in the
    full text so an abbreviation such as 'Sec. 4)' cannot split the keyword
    from its rate. A late-charge or default-rate percentage further along an
    unpunctuated Basic Lease Information block is therefore not read as an
    escalation (REFUTE round 3).

    Round 4: the backward search stays inside the clause (a 3% share in the
    PREVIOUS sentence is never a step); the forward search may run into the
    next clause ('Sec. 4) by 3.5%'). A qualifying clause with an escalation
    verb but no percentage within _ESC_PCT_GAP contributes EVERY percentage in
    it ('increase ... by an amount equal to three and one-half percent
    (3.5%)'). The chain runs forward through consecutive escalation-verb
    clauses ('Notwithstanding the foregoing, ... the increase shall be 3.5%'),
    but never into a clause whose subject is an expense term and that does not
    name rent ('The Operating Costs shall not increase by more than 5%').

    Returns (pcts, indexed): indexed is True when a qualifying clause ties the
    step to CPI / a price index, which a fixed % cannot verify."""
    pcts_all = [(m.start(), m.end(), float(m.group(1))) for m in _PCT_RE.finditer(text)]
    spans, pos = [], 0
    for sep in list(_CLAUSE_SPLIT_RE.finditer(text)) + [None]:
        end = sep.start() if sep else len(text)
        spans.append((pos, end))
        pos = sep.end() if sep else len(text)
    out, indexed = [], False
    chain = False
    for i, (cs, ce) in enumerate(spans):
        clause = text[cs:ce]
        names_rent = bool(_RENT_TERM_RE.search(clause))
        has_esc = bool(_ESC_CONTEXT_RE.search(clause))
        expense_subject = (not names_rent) and bool(_EXPENSE_SUBJECT_RE.match(clause))
        qualifies = names_rent or (chain and not expense_subject)
        if qualifies and has_esc:
            fwd_end = spans[i + 1][1] if i + 1 < len(spans) else ce
            got_any = False
            for k in _ESC_CONTEXT_RE.finditer(clause):
                ks, ke = cs + k.start(), cs + k.end()
                best = None
                for s, e, v in pcts_all:
                    if s >= ke:
                        gap = s - ke
                        ok = gap <= _ESC_PCT_GAP and e <= fwd_end
                    else:
                        gap = ks - e
                        ok = 0 <= gap <= _ESC_PCT_GAP and s >= cs
                    if ok and (best is None or gap < best[0]):
                        best = (gap, v)
                if best is not None:
                    out.append(best[1])
                    got_any = True
            if not got_any and len(clause) <= _READ_ALL_MAX_CLAUSE:
                # Only for sentence-sized clauses: an unpunctuated Basic Lease
                # Information block runs thousands of characters and holds the
                # late-charge and default-rate percentages.
                out.extend(v for s, e, v in pcts_all if s >= cs and e <= ce)
            if _INDEX_RE.search(clause):
                indexed = True
        # The chain starts at a clause naming rent and continues through
        # consecutive qualifying escalation-verb clauses.
        chain = names_rent or (qualifies and has_esc)
    return out, indexed


_ESC_PCT_GAP = 50
_READ_ALL_MAX_CLAUSE = 400
_EXPENSE_SUBJECT_RE = re.compile(
    r"\W*(?:the\s+)?(?:tenant'?s\s+(?:proportionate\s+)?share\s+of\s+(?:the\s+)?)?"
    r"(?:operating\s+(?:costs?|expenses?)|common\s+area|CAM\b|(?:real\s+estate\s+)?taxes"
    r"|insurance|expenses?)",
    re.I)
_INDEX_RE = re.compile(r'\b(?:CPI|consumer\s+price\s+index|price\s+index)\b', re.I)


def _find_escalation_pct(text, value):
    """(found, conflicting, indexed): found when some rent-escalation keyword's
    nearest percentage is the register's fixed %; conflicting = the other
    percentages read that way. Any conflicting percentage blocks CONFORMS, even
    when the register value also appears (e.g. a 3% option-term step beside a
    3.5% primary-term step against a 3% register). indexed: the clause ties the
    step to CPI ('greater of 3% or CPI'), which a fixed % cannot confirm."""
    target = float(value)
    pcts, indexed = _escalation_pcts(text)
    found = any(abs(p - target) < 1e-9 for p in pcts)
    conflicting = sorted({p for p in pcts if abs(p - target) >= 1e-9})
    return found, conflicting, indexed


def _check_rent(reg, text):
    schedule = ((reg.get("rent") or {}).get("schedule")) or []
    if not schedule:
        return {"status": "MISSING", "detail": "register has no rent.schedule"}
    monthly = schedule[0].get("monthly")
    found_rent = _find_dollar_amount(text, monthly) if monthly is not None else None
    esc = (reg.get("rent") or {}).get("escalation") or {}
    esc_type = esc.get("type")
    esc_found = False
    esc_label = None
    esc_value = esc.get("value")
    if esc and (esc_type not in ("none", "fixed_pct", "cpi", "fixed_amount")
                or (esc_type == "fixed_pct"
                    and (isinstance(esc_value, bool)
                         or not isinstance(esc_value, (int, float))
                         or esc_value != esc_value))):
        # The register HAS an escalation block, but one this checker cannot
        # verify: a missing/unknown type, or fixed_pct with no usable value.
        # Used to leave esc_label=None and fall through to CONFORMS on the
        # Year-1 rent alone (audit row leaseqc-checkrent-escalation-failopen,
        # 2026-11-08). PARTIAL is blocking, so the gate now fails.
        why = (f"fixed_pct escalation with no usable value ({esc_value!r})"
               if esc_type == "fixed_pct"
               else f"escalation block with missing/unknown type ({esc_type!r})")
        if found_rent:
            return {"status": "PARTIAL",
                    "detail": f"Year-1 rent {found_rent} found; the register's {why} "
                              f"could not be verified -- fix the register or verify by hand"}
        return {"status": "MISSING",
                "detail": f"Year-1 rent figure not found; the register's {why} "
                          f"could not be verified either"}
    if esc_type == "fixed_pct":
        esc_label = f"{esc_value:g}%"
        esc_found, esc_conflicts, esc_indexed = _find_escalation_pct(text, esc_value)
        if esc_indexed and not esc_conflicts:
            return {"status": "PARTIAL",
                    "detail": f"rent escalation clause ties the step to a price index (CPI); "
                              f"the register's fixed {esc_label} cannot be confirmed -- verify by hand"}
        if esc_conflicts:
            stated = ", ".join(f"{p:g}%" for p in esc_conflicts)
            return {"status": "CONFLICT",
                    "detail": f"rent escalation clause(s) state {stated} vs the register's "
                              f"{esc_label}"
                              + (f" (the register's {esc_label} also appears)" if esc_found else "")}
    elif esc_type == "none":
        esc_found = True
        esc_label = "flat (no escalation)"
    elif esc_type in ("cpi", "fixed_amount"):
        # NOT verified by this checker: a CPI-indexed or fixed-dollar-step
        # escalation cannot be confirmed from a single text search the way
        # a flat percentage can (there is no one string to look for). Was
        # silently falling through to the "no escalation info" CONFORMS
        # branch below -- a false CONFORMS for coverage never actually
        # performed. Caught in independent re-review.
        if found_rent:
            return {"status": "PARTIAL",
                    "detail": f"Year-1 rent {found_rent} found; the register's "
                              f"'{esc_type}' escalation requires manual verification "
                              f"(not text-matchable)"}
        return {"status": "MISSING",
                "detail": f"Year-1 rent figure not found; register also specifies a "
                          f"'{esc_type}' escalation requiring manual verification"}
    if found_rent and (esc_found or esc_label is None):
        return {"status": "CONFORMS",
                "detail": f"Year-1 rent {found_rent} found"
                          + (f" with {esc_label} escalation" if esc_found and esc_label else "")}
    if found_rent and not esc_found:
        return {"status": "PARTIAL",
                "detail": f"Year-1 rent {found_rent} found, but the register's "
                          f"{esc_label or 'escalation'} was not found in the lease text"}
    if not found_rent and esc_found:
        return {"status": "PARTIAL",
                "detail": "escalation language found but the Year-1 rent figure was not"}
    return {"status": "MISSING", "detail": "neither Year-1 rent nor escalation language found"}


_EXPENSE_PHRASES = {
    # Anchored to RENT/expense-structure phrasing, not the bare word
    # "gross" -- every ORA lease's exculpation/indemnity clause contains
    # "gross negligence", which a bare \bgross\b match fires on regardless
    # of expense structure, producing both a false CONFORMS (any lease,
    # any structure) and a false CONFLICT against a genuine NNN lease with
    # no "gross" rent language at all. Caught in independent review.
    "gross": r'(?:full[\s-]service\s+gross|gross\s+(?:basis|rent|lease)|'
             r'rent\s+(?:is|shall\s+be|are)\s+(?:calculated\s+)?(?:on\s+a\s+)?gross)',
    "modified_gross_base_year": r'base\s+year',
    "nnn": r'\btriple\s+net\b|\bNNN\b',
}


def _check_expense_structure(reg, text):
    t = (reg.get("expense_structure") or {}).get("type")
    if not t:
        return {"status": "MISSING", "detail": "register has no expense_structure.type"}
    pat = _EXPENSE_PHRASES.get(t)
    if pat and re.search(pat, text, re.I):
        return {"status": "CONFORMS", "detail": f"expense structure '{t}' language found"}
    for other_t, other_pat in _EXPENSE_PHRASES.items():
        if other_t != t and re.search(other_pat, text, re.I):
            return {"status": "CONFLICT",
                    "detail": f"lease reads as '{other_t}' but register specifies '{t}'"}
    return {"status": "MISSING", "detail": f"no '{t}' expense-structure language found"}


def _check_utilities(reg, text):
    u = reg.get("utilities") or {}
    total, hits, missing = 0, 0, []
    for key in ("electric", "water_sewer"):
        val = u.get(key)
        if not val:
            continue
        total += 1
        # NOT `or _phrase_present(key, text)` -- falling back to the bare
        # field NAME ("electric") made the row effectively unfailable
        # (almost every lease mentions "electric" somewhere) regardless of
        # what the register's actual enum VALUE says (e.g. who pays, or on
        # what basis); caught in independent review.
        if _phrase_present(val, text):
            hits += 1
        else:
            missing.append(key)
    if total == 0:
        return {"status": "CONFORMS", "detail": "register specifies no utilities detail"}
    if hits == total:
        return {"status": "CONFORMS", "detail": "utilities allocation language found"}
    if hits == 0:
        return {"status": "MISSING", "detail": "no utilities allocation language found"}
    return {"status": "PARTIAL", "detail": f"missing: {', '.join(missing)}"}


def _check_security_deposit(reg, text):
    sd = reg.get("security_deposit") or {}
    amount = sd.get("amount")
    if amount is None:
        return {"status": "MISSING", "detail": "register has no security_deposit.amount"}
    found = _find_dollar_amount(text, amount)
    if found:
        return {"status": "CONFORMS",
                "detail": f"lease states {found}, matching register's ${amount:,.2f}"}
    m = re.search(r'[Ss]ecurity\s+[Dd]eposit[^.$]{0,80}\$\s*[\d,]+(?:\.\d{2})?', text)
    if m:
        stated = re.search(r'\$\s*[\d,]+(?:\.\d{2})?', m.group(0)).group(0)
        return {"status": "CONFLICT",
                "detail": f"lease states {stated} vs register's ${amount:,.2f}"}
    return {"status": "MISSING",
            "detail": f"no Security Deposit dollar figure of ${amount:,.2f} found"}


def _check_parking(reg, text):
    count = (reg.get("parking") or {}).get("overnight_vehicles")
    if count is None:
        return {"status": "CONFORMS", "detail": "register specifies no overnight-vehicle allowance"}
    pat = _num_pattern(count)
    if (re.search(pat + r'.{0,40}(?:overnight|vehicle)', text, re.I)
            or re.search(r'(?:overnight|vehicle).{0,40}' + pat, text, re.I)):
        return {"status": "CONFORMS", "detail": f"{count} overnight vehicle(s) found"}
    return {"status": "MISSING",
            "detail": f"no overnight-parking allowance of {count} vehicle(s) found"}


def _check_landlord_work(reg, text):
    items = ((reg.get("landlord_work") or {}).get("items")) or []
    if not items:
        return {"status": "CONFORMS", "detail": "register specifies no landlord work items"}
    # threshold=0.5 (majority-of-significant-words, see _phrase_present):
    # these are free-text prose descriptions, not fixed enum values, and
    # requiring every word verbatim made this row essentially unfailable
    # to CONFORM against ORA's own canonical example register -- caught
    # in independent review.
    hits = sum(1 for item in items if _phrase_present(item, text, threshold=0.5))
    if hits == len(items):
        return {"status": "CONFORMS", "detail": f"all {len(items)} landlord-work item(s) referenced"}
    if hits == 0:
        return {"status": "MISSING",
                "detail": f"none of the {len(items)} register landlord-work item(s) found"}
    return {"status": "PARTIAL", "detail": f"only {hits} of {len(items)} landlord-work item(s) found"}


def _check_maintenance(reg, text):
    alloc = (reg.get("maintenance") or {}).get("allocation")
    if not alloc:
        return {"status": "MISSING", "detail": "register has no maintenance.allocation"}
    if alloc == "LOI_landlord_hvac_and_major_mechanicals":
        ok = bool(re.search(r'Landlord.{0,60}(?:responsible|maintain)\w*.{0,60}HVAC', text, re.I | re.S))
        return ({"status": "CONFORMS", "detail": "Landlord-HVAC maintenance allocation found"} if ok else
                {"status": "MISSING", "detail": "no Landlord-HVAC maintenance allocation language found"})
    if alloc == "ORA_form_default_tenant_hvac":
        ok = bool(re.search(r'Tenant.{0,60}(?:responsible|maintain)\w*.{0,60}HVAC', text, re.I | re.S))
        return ({"status": "CONFORMS", "detail": "Tenant-HVAC maintenance allocation (ORA default) found"} if ok else
                {"status": "MISSING", "detail": "no Tenant-HVAC maintenance allocation language found"})
    return {"status": "PARTIAL",
            "detail": f"custom maintenance.allocation ('{alloc}') requires manual verification"}


def _check_insurance(reg, text):
    agg = (reg.get("insurance") or {}).get("cgl_aggregate")
    if agg is None:
        return {"status": "CONFORMS", "detail": "register specifies no insurance limits"}
    found = _find_dollar_amount(text, agg)
    if found:
        return {"status": "CONFORMS", "detail": f"CGL aggregate {found} matches register"}
    m = re.search(r'general\s+aggregate[^.$]{0,40}\$\s*[\d,]+', text, re.I)
    if m:
        stated = re.search(r'\$\s*[\d,]+', m.group(0)).group(0)
        return {"status": "CONFLICT",
                "detail": f"lease states {stated} vs register's ${agg:,.0f} CGL aggregate"}
    return {"status": "MISSING", "detail": f"no ${agg:,.0f} CGL aggregate figure found"}


def _check_broker(reg, text):
    dual = (reg.get("broker") or {}).get("dual_agency")
    if not dual:
        return {"status": "CONFORMS", "detail": "register does not require dual-agency disclosure"}
    if re.search(r'dual\s+agen', text, re.I):
        return {"status": "CONFORMS", "detail": "dual-agency disclosure language found"}
    return {"status": "MISSING",
            "detail": "register flags dual agency but no dual-agency language found in lease"}


def _check_signage(reg, text):
    signage = reg.get("signage")
    if not signage:
        return {"status": "CONFORMS", "detail": "register specifies no signage right"}
    # threshold=0.5, same rationale as _check_landlord_work: signage is a
    # free-text grant description, not an enum value.
    if _phrase_present(signage, text, threshold=0.5):
        return {"status": "CONFORMS", "detail": "signage right language found"}
    if re.search(r'\bsignage\b', text, re.I):
        return {"status": "PARTIAL",
                "detail": "lease addresses signage but not matching the register's grant"}
    return {"status": "MISSING",
            "detail": "register grants a signage right not found in the lease text"}


def _check_open_items(reg, text):
    """Carry-through of the register's open_items. String items (v1.0 shape)
    are unresolved by definition; object items are resolved only when
    `resolution` is non-null AND the `lease_clause` phrase is present in the
    lease (a resolution with no clause to verify stays unresolved -- the
    conservative call for a pre-signature gate). Returns None (row omitted,
    NOT CONFORMS) when the array is empty or absent."""
    items = reg.get("open_items") or []
    if not items:
        return None
    unresolved, resolved = [], 0
    for it in items:
        if isinstance(it, str):
            unresolved.append(it)
            continue
        label = it.get("item") or "(unnamed item)"
        clause = it.get("lease_clause")
        if (it.get("resolution") is not None and clause
                and _phrase_present(clause, text, threshold=0.6)):
            resolved += 1
        else:
            unresolved.append(label)
    if not unresolved:
        return {"status": "CONFORMS",
                "detail": f"all {resolved} open item(s) resolved and carried into the lease"}
    status = "PARTIAL" if resolved else "MISSING"
    return {"status": status,
            "detail": f"{len(unresolved)} unresolved of {len(items)}: " + "; ".join(unresolved)}


_CONFORMANCE_CHECKERS = [
    ("landlord", _check_landlord),
    ("tenant", _check_tenant),
    ("co_tenants", _check_co_tenants),
    ("premises", _check_premises),
    ("use", _check_use),
    ("term", _check_term),
    ("options", _check_options),
    ("rent", _check_rent),
    ("expense_structure", _check_expense_structure),
    ("utilities", _check_utilities),
    ("security_deposit", _check_security_deposit),
    ("parking", _check_parking),
    ("landlord_work", _check_landlord_work),
    ("maintenance", _check_maintenance),
    ("insurance", _check_insurance),
    ("broker", _check_broker),
    ("signage", _check_signage),
    ("open_items", _check_open_items),
]
# Deliberately NOT covered by a row: `special_provisions` (a heterogeneous
# array of ad-hoc title/text/placement clauses with no fixed shape to match
# against -- generic text-presence matching against arbitrary custom clause
# text is unreliable enough to be worse than no row at all) and the
# sub-fields of already-covered categories not independently checked here
# (e.g. utilities.gas/.trash, parking.allocation/.vehicle_class_cap). Flag
# these for manual review in the memo per lease-generation's SKILL.md
# rather than reporting a false CONFORMS for coverage this mode does not
# actually verify.


def build_conformance_matrix(register, text):
    """One row per deal-terms-register field category (see
    _CONFORMANCE_CHECKERS), each a CONFORMS / CONFORMS+ / PARTIAL / MISSING
    / CONFLICT verdict against the drafted lease's extracted text -- the
    SKILL.md 'LOI conformance matrix' gate, as a scanner-owned, testable
    output instead of a manual judgment call."""
    rows = []
    for category, fn in _CONFORMANCE_CHECKERS:
        try:
            result = fn(register, text)
            if result is None:          # row omitted (e.g. open_items empty)
                continue
        except Exception as e:                                      # noqa: BLE001
            # One malformed register field (wrong type, missing nested
            # key) must not crash the whole matrix -- mirrors
            # run_checks()'s "a broken check degrades, it never blinds the
            # report" posture (ora_doc_qc.py). MISSING (a blocking status)
            # rather than silently dropped: an uncheckable field reads as
            # "not verified", the conservative call for a pre-signature
            # gate. Caught in independent review.
            result = {"status": "MISSING", "detail": f"could not evaluate: {e}"}
        rows.append({"category": category,
                     "section": _SECTION_HINTS.get(category, ""),
                     "status": result["status"],
                     "detail": result["detail"]})
    return rows


def _conformance_summary(rows):
    counts = {}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return counts


def _print_conformance_report(report):
    print("=" * 78)
    print(f"REGISTER   {report['register']}")
    print(f"LEASE      {report['lease_file']}")
    print("-" * 78)
    for r in report["rows"]:
        print(f"[{r['status']:<9}] {r['category']:<16} {r['section']}")
        print(f"            {r['detail']}")
    print("-" * 78)
    tally = " · ".join(f"{v} {k}" for k, v in sorted(report["summary"].items()))
    print(f"SUMMARY    {tally}")
    blocking = [r for r in report["rows"] if r["status"] in ("PARTIAL", "MISSING", "CONFLICT")]
    if blocking:
        print(f"GATE       {len(blocking)} row(s) not clear to ship without a resolved "
              f"gate (SKILL.md '3. Gates' item 4): " + ", ".join(r["category"] for r in blocking))
    else:
        print("GATE       clean -- every row CONFORMS or CONFORMS+")
    print()


def _run_loi_conformance(argv):
    ap = argparse.ArgumentParser(
        description="ORA LOI-conformance matrix: deal-terms register vs. a drafted lease")
    ap.add_argument("--loi-conformance", metavar="REGISTER_JSON", required=True,
                    help="deal-terms-register.json (see lease-generation/references/"
                         "deal-terms-register.schema.json)")
    ap.add_argument("lease_file", help="the drafted lease DOCX to check against the register")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    try:
        with open(a.loi_conformance, encoding="utf-8") as f:
            register = json.load(f)
    except Exception as e:                                          # noqa: BLE001
        print(f"ERROR: could not read register {a.loi_conformance}: {e}", file=sys.stderr)
        return 2
    if not isinstance(register, dict):
        print(f"ERROR: {a.loi_conformance} is not a JSON object -- a deal-terms "
              f"register must be a top-level object.", file=sys.stderr)
        return 2

    # Mirrors ora_doc_qc.scan()'s own guards (missing file, extraction
    # exception) so a bad --loi-conformance invocation gets exit 2 (usage/
    # data error), never exit 1 -- exit 1 means "the matrix was computed
    # and at least one row blocks", and collapsing an operational failure
    # into that code let an automated caller read a crash as a real
    # conformance verdict. Caught in independent review.
    if not os.path.exists(a.lease_file):
        print(f"ERROR: no such file: {a.lease_file}", file=sys.stderr)
        return 2
    try:
        body, meta = extract(a.lease_file, want_footer=True)
    except Exception as e:                                          # noqa: BLE001
        print(f"ERROR: extraction failed on {a.lease_file}: {e}", file=sys.stderr)
        return 2
    if body is None:
        print(f"ERROR: {a.lease_file} is UNREADABLE ({meta['words']} words) -- "
              f"no conformance result.", file=sys.stderr)
        return 2

    rows = build_conformance_matrix(register, norm(body))
    report = {"register": os.path.basename(a.loi_conformance),
              "lease_file": os.path.basename(a.lease_file),
              "rows": rows, "summary": _conformance_summary(rows)}

    if a.json:
        print(json.dumps(report, indent=2))
    else:
        _print_conformance_report(report)

    blocking = any(r["status"] in ("PARTIAL", "MISSING", "CONFLICT") for r in rows)
    return 1 if blocking else 0


# ==========================================================================
# --loi-audit mode -- standard scan + conformance matrix, one call (v2.8)
# ==========================================================================
# Composition only: no new check logic lives here. It runs ora_doc_qc.scan()
# over CHECKS (T3/T4/D1/D2 included) and build_conformance_matrix(), prints
# both, and exits with the max of the two component codes (2 > 1 > 0).

def _run_loi_audit(argv):
    ap = argparse.ArgumentParser(
        description="ORA LOI-Lease Audit: full scan + register-vs-lease conformance matrix")
    ap.add_argument("--loi-audit", metavar="REGISTER_JSON", required=True)
    ap.add_argument("lease_file")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--allow-tokens", action="store_true")
    ap.add_argument("--no-ocr", action="store_true")
    _add_mode_args(ap)
    a = ap.parse_args(argv)

    try:
        with open(a.loi_audit, encoding="utf-8") as f:
            register = json.load(f)
    except Exception as e:                                          # noqa: BLE001
        print(f"ERROR: could not read register {a.loi_audit}: {e}", file=sys.stderr)
        return 2
    if not isinstance(register, dict):
        print(f"ERROR: {a.loi_audit} is not a JSON object -- a deal-terms "
              f"register must be a top-level object.", file=sys.stderr)
        return 2

    register_scan_path(a.lease_file)
    # v3.0: same form resolution as the standard scan (a v2.7 document with no
    # conflict still gets exactly CHECKS).
    plan = plan_scan(a.lease_file, a.form, a.power_rights, allow_ocr=not a.no_ocr)
    scan_report = scan(a.lease_file, plan["checks"], a.allow_tokens, allow_ocr=not a.no_ocr,
                       want_footer=True)
    if scan_report is None:
        return 2                        # scan() already printed the reason
    scan_report["form"], scan_report["na"] = plan["form"], plan["na"]
    scan_report["pending"] = (pending_power(plan, a.lease_file, a.allow_tokens)
                              if not scan_report["unreadable"] else [])
    if scan_report["unreadable"]:
        if a.json:
            print(json.dumps({"scan": [scan_report], "matrix": None, "exit": 2}, indent=2))
        else:
            print_report(scan_report)
            print("AUDIT: unreadable lease -- no scan or matrix result - exit 2")
        return 2

    body, _meta = extract(a.lease_file, allow_ocr=not a.no_ocr, want_footer=True)
    rows = build_conformance_matrix(register, norm(body))
    matrix = {"register": os.path.basename(a.loi_audit),
              "lease_file": os.path.basename(a.lease_file),
              "rows": rows, "summary": _conformance_summary(rows)}
    failures = scan_report["failures"]
    n_block = sum(1 for f in failures if f["severity"] == "BLOCK")
    bad_rows = [r for r in rows if r["status"] in ("PARTIAL", "MISSING", "CONFLICT")]
    code = max(1 if failures else 0, 1 if bad_rows else 0)

    if a.json:
        print(json.dumps({"scan": [scan_report], "matrix": matrix, "exit": code}, indent=2))
    else:
        print_report(scan_report)
        print_mode_block(scan_report)
        print("=" * 78)
        _print_conformance_report(matrix)
        print(f"AUDIT: {len(failures)} scan failure(s) [{n_block} BLOCK] · "
              f"{len(bad_rows)} matrix row(s) · exit {code}")
    return code


def main():
    argv = sys.argv[1:]
    # Matches both the space form ("--loi-conformance reg.json") and
    # argparse's own "=" form ("--loi-conformance=reg.json") -- a plain
    # `in argv` membership test missed the latter, silently falling through
    # to the standard scan mode's build_cli(), which does not know the flag
    # and dies with a misleading "unrecognized arguments" usage error.
    if any(a == "--loi-audit" or a.startswith("--loi-audit=") for a in argv):
        sys.exit(_run_loi_audit(argv))
    if any(a == "--loi-conformance" or a.startswith("--loi-conformance=") for a in argv):
        sys.exit(_run_loi_conformance(argv))
    sys.exit(_run_scan_cli(argv))


OCR_ABSENCE_NOTE = ("Absence findings (A6, B5, B6a-B6c, B7, C1-C8, "
                    "F10, F11) are PROVISIONAL - OCR text is lossy, "
                    "so confirm against the page images before "
                    "reporting a clause missing.")


def _add_mode_args(ap):
    ap.add_argument("--form", choices=FORM_FAMILIES, default=None,
                    help="scan as this form line (v2.7 long-form NNN, v3.0 short-form MG). "
                         "Default: auto-detect from the footer tag, then structure. A "
                         "declared form the document contradicts FAILS (F0 BLOCK).")
    ap.add_argument("--power-rights", action="store_true",
                    help="enforce the power-rights standard (FP1-FP8) even on a form "
                         "older than v2.8 / v3.1 (pre-release drafting).")
    return ap


def _run_scan_cli(argv):
    """ora_doc_qc.run_cli() equivalent with form resolution per file. Same
    flags, same report block, same exit codes (0 clean, 1 failures, 2
    usage/extraction/unreadable); adds a FORM line, N/A lines and the
    PENDING power-rights block after each report (and the same keys in
    --json)."""
    a = _add_mode_args(build_cli("ORA lease-form QC gate")).parse_args(argv)
    reports, bad = [], 0
    for f in a.files:
        if os.path.exists(f):
            register_scan_path(f)
        plan = plan_scan(f, a.form, a.power_rights, allow_ocr=not a.no_ocr)
        r = scan(f, plan["checks"], a.allow_tokens, allow_ocr=not a.no_ocr, want_footer=True)
        if r is None:
            bad = 2
            continue
        r["form"], r["na"] = plan["form"], plan["na"]
        r["pending"] = pending_power(plan, f, a.allow_tokens) if not r["unreadable"] else []
        reports.append(r)
        if r["unreadable"]:
            bad = 2
    if a.json:
        print(json.dumps(reports, indent=2))
    else:
        for r in reports:
            print_report(r, ocr_absence_note=OCR_ABSENCE_NOTE)
            if not r["unreadable"]:
                print_mode_block(r)
    if any(r["failures"] for r in reports):
        return 1
    return bad


if __name__ == "__main__":
    main()
