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
live in ora_doc_qc.py (shared with pma-qc and listing-agreement-qc). A copy
ships in this skill's scripts/ directory so lease-form-qc installs and runs
standalone, mirroring pma-qc and listing-agreement-qc. Once
tools/package_skills.py's SHARED_ROOT_DEPS injects it from the repo root, this
in-skill copy should be removed rather than allowed to drift.

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
"""

import re

from ora_doc_qc import bool_check, run_cli

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
    return re.sub(r'[ \t]+', ' ', ctx["raw"])


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
]

# This skill's own token pattern, deliberately NOT the shared module's default
# (which adds '_' to the class and caps the run at 40 chars). Swapping it would
# be an unrequested, unverified change to what counts as an unfilled token, so
# the local regex stays in force. Pinned by
# tests/test_lease_qc.py::test_local_token_regex_is_preserved_not_the_shared_default.
TOKEN_RE = re.compile(r"\[[A-Z][A-Z0-9 /,.'&-]{2,}\]")


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
    toks = sorted(set(TOKEN_RE.findall(hay)))
    if not toks:
        return None
    shown = ", ".join(toks[:6]) + ("..." if len(toks) > 6 else "")
    return f"{len(toks)} unfilled token(s): {shown}"


CHECKS.append(("T1", "BLOCK", "Unfilled template tokens remain", None, _t1))


if __name__ == "__main__":
    run_cli(CHECKS, "ORA lease-form QC gate", want_footer=True,
            ocr_absence_note=("Absence findings (A6, B5, B6a-B6c, B7, C1-C8, "
                              "F10, F11) are PROVISIONAL - OCR text is lossy, "
                              "so confirm against the page images before "
                              "reporting a clause missing."))
