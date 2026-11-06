#!/usr/bin/env python3
"""Audit a contract .docx for the defects that survive human proofreading.

Why this exists
---------------
The quality gate asked whether exhibits were "attached." That is the wrong question.
An exhibit can be present, referenced, correctly titled, and completely EMPTY — and
because reviewers read the body and skim the back matter, an empty exhibit survives
round after round while the body increasingly depends on it.

    Origin: 2026-08-01, 754 Old State Route 74. Exhibit B (Rent Roll) was a heading
    and nothing else — no table, no image, no text — across four drafting rounds and
    two law firms. Meanwhile §7 defined "Leases" by reference to it, and §15.1.2
    confirmed the absence of renewal/purchase options "except as expressly set forth
    on the rent roll attached as Exhibit B." The single provision protecting the
    deal's value thesis pointed at a blank page. Exhibit A carried a parcel number
    but no legal description; §15.1's knowledge-party definition was an open blank.

Four checks, all mechanical:
  1. EXHIBIT POPULATION  — does each exhibit contain anything at all?
  2. CROSS-REFERENCES    — every exhibit cited in the body exists, and vice versa;
                           every section cross-reference resolves.
  3. UNFILLED BLANKS     — placeholder runs, [TBD], and open definitions, split into
                           body blanks (defects) and signature-block blanks (expected).
                           Inside an exhibit that follows the signature page only
                           genuine signature / notary lines are signature blanks
                           (Gabriel's ruling, 2026-11-06).
  4. KNOWLEDGE PARTY     — the definition that silently voids or unbounds every
                           knowledge-qualified representation when left blank.

Usage
-----
    python audit_completeness.py CONTRACT.docx
    python audit_completeness.py CONTRACT.docx --json

Exit codes
----------
    0  no blocking defects
    1  blocking defects found
    3  usage / read error

Stdlib only. Python 3.8+.
"""
from __future__ import annotations

import json
import re
import sys
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
A_BLIP = "{http://schemas.openxmlformats.org/drawingml/2006/main}blip"
V_IMAGE = "{urn:schemas-microsoft-com:vml}imagedata"

SUMMARY_MARKERS = (
    "summary report", "litera compare", "workshare compare", "deltaview",
    "change-pro", "document comparison done on",
)
# "signature page" alone also matches the Counterparts boilerplate ("…signature pages
# may be delivered by email") in mid-document, which would silently downgrade every
# later body blank — including an open Purchase Price — to an expected signature blank.
SIGNATURE_START_RE = re.compile(
    r"in\s+witness\s+whereof|^\s*\[?signature\s+(page|and\s+exhibit\s+pages)\s+"
    r"(follows?|to\s+follow)", re.IGNORECASE)

EXHIBIT_HEAD_RE = re.compile(r"^\s*EXHIBIT\s+([A-Z](?:-\d+)?)\b\s*$", re.IGNORECASE)
# "Exhibit A" and also "Exhibits A, B and C"
EXHIBIT_REF_RE = re.compile(r"\bExhibits?\s+((?:[A-Z](?:-\d+)?)(?:\s*,\s*(?:and\s+)?"
                            r"[A-Z](?:-\d+)?|\s+and\s+[A-Z](?:-\d+)?)*)\b")
EXHIBIT_LETTER_RE = re.compile(r"[A-Z](?:-\d+)?")
SECTION_REF_RE = re.compile(r"(?:Section|Paragraph|Article|§)\s*(\d+(?:\.\d+)*)")
SECTION_HEAD_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)\s*[.—-]?\s*[A-Z(]")

# Law-firm DMS stamps ("15744530.v2", or two concatenated by a compare tool) are the
# only content in many otherwise-empty exhibit ranges. Counting them as content
# downgrades a BLOCKING empty exhibit to advisory THIN — and every iManage document
# carries one.
DMS_STAMP_RE = re.compile(r"^(?:\d{6,}\.v\d+\s*)+$")

# Statutory citations look exactly like internal cross-references ("Section 1445",
# "§§ 6901", "R.C. § 5302.07", "Section 1031 of the Code"). Suppress ONLY on a
# positive statute signal — never on "the number looks too big," which silently
# swallows the real dangling references this check exists to find.
STATUTE_BEFORE_RE = re.compile(
    r"(?:U\.?\s?S\.?\s?C|C\.?\s?F\.?\s?R|\bR\.?C\.?|O\.?R\.?C|I\.?R\.?C|Revenue Code"
    r"|Internal Revenue|Ohio Revised|Public Law|Stat\.|U\.S\.C\.A|§§).{0,45}$",
    re.IGNORECASE)
STATUTE_AFTER_RE = re.compile(
    r"^\s*(?:\([a-z0-9)(]+\)\s*)?(?:et\s+seq|of\s+the\s+(?:Internal\s+Revenue\s+)?Code"
    r"|of\s+the\s+Ohio\s+Revised|U\.?\s?S\.?\s?C|of\s+Title\s+\d)", re.IGNORECASE)
# Above this, a reference is reported as a LIKELY CITATION (advisory) rather than a
# dangling internal reference — reported either way, never silently dropped.
MAX_PLAUSIBLE_SECTION = 100

BLANK_PATTERNS = [
    (re.compile(r"_{3,}"), "underscore placeholder"),
    (re.compile(r"\[\s*(?:TBD|TBA|XXX+|insert|to come|•)\s*\]", re.I), "bracket placeholder"),
    (re.compile(r"\bTBD\b"), "TBD"),
    (re.compile(r"\$\s*_{2,}"), "open dollar amount"),
    (re.compile(r"\[\s*\]"), "empty bracket"),
]
# Inside an exhibit that follows the signature page, a blank is a BODY blank
# (blocking) unless its LINE is a genuine signature, notary or recording-form line
# (Gabriel's rulings, 2026-11-06). Paragraphs are split on w:br / w:cr first and
# each line is classified by _classify_line:
#   exempt  -- signature labels with nothing but the blank (By:, Name:, Title:,
#              Its:, Date:, Authorized Signatory:, Attest: ...), a bare rule, a
#              (SEAL) line, venue lines in venue shape ("STATE OF OHIO ) ss:",
#              "____ COUNTY )", MD "..., TO WIT:"), and the notary acknowledgment
#              forms used in OH / IN / MD / MO / KS / WI / TN
#   context -- exempt only inside a signature block (a By:/Name:/notary/venue cue
#              within 3 lines, or in the same table cell): party labels (Tenant:,
#              Seller:, Grantee:, Return to: ...) with nothing after the blank,
#              entity lines ("____, a ____ limited liability company"), a bare
#              "COUNTY OF ____", and a bare rule in a multi-cell table
#   body    -- everything else: any line with "$", a value word (rent, price,
#              parcel, lot, suite, term, deposit ...) after its signature label, a
#              second non-signature label, or a non-seal parenthetical.
# Lines over 400 characters are never exempt. Every pattern is anchored and bounded
# (no nested quantifiers): a 10k-character line is judged in microseconds.
_SEAL_RE = re.compile(r"\(\s*(?:notary\s+)?(?:seal|l\.?\s?s\.?)\s*\)", re.IGNORECASE)
_STATUTORY_RE = re.compile(
    r"\(\s*(?:date|state|name|title|name\s+of\s+(?:officer|company|entity|corporation|"
    r"partnership|limited\s+liability\s+company|llc|signer|acknowledger)|"
    r"title\s+of\s+(?:officer|signer))\s*\)", re.IGNORECASE)   # OH statutory short form
_LABEL_RE = re.compile(r"([A-Za-z][A-Za-z.'/ ]{0,40}?)\s*:")
_LEAD_LABEL_RE = re.compile(r"^([A-Za-z][A-Za-z.'/ ]{0,40}?)\s*:")
_CORE_LABELS = frozenset("""
by|name|title|its|date|dated|signature|signed|print|print name|printed name|witness|
witnesses|attest|authorized signatory|authorized signature|name and title|name/title|
date signed|notary|notary public|signature of notary public|my commission expires|
commission expires|my commission expiration|commission expiration|my term expires|
my appointment expires|my county of residence|county of residence|commission no.|
commission no|commission number|printed name of notary|notary printed name|notary name|
this instrument prepared by|prepared by|ss|ss.""".replace("\n", "").split("|"))
_CONTEXT_LABELS = frozenset("""
grantor|grantee|seller|purchaser|buyer|landlord|tenant|assignor|assignee|return to|
after recording return to|send tax statements to|tax statements to|
mail tax statements to""".replace("\n", "").split("|"))
_VALUE_WORD_RE = re.compile(
    r"\b(?:rents?|price|parcels?|lots?|suites?|terms?|deposits?|square\s+f(?:ee|oo)t|"
    r"sq\.?\s*ft|acres?|commencement|expiration|closing|effective|consideration|"
    r"dollars|amount|fees?|apn)\b", re.IGNORECASE)
_V1 = r"(?:state|commonwealth|county|parish)\s+of\s+[^,:()]{1,30}?\s*(?:\)\s*(?:ss\.?:?)?|ss\.?:?)"
_V2 = r"_{2,}\s+county\s*\)"
_VENUE_RE = re.compile(r"^(?:{0}|{1})(?:\s*(?:{0}|{1}))?\s*$".format(_V1, _V2), re.IGNORECASE)
_MD_VENUE_RE = re.compile(
    r"^state\s+of\s+[a-z ]{1,30},\s*(?:city|county)\s+of\s+[^,]{1,30},\s*to\s+wit:?$",
    re.IGNORECASE)
_BARE_VENUE_RE = re.compile(r"^(?:state|commonwealth|county|parish)\s+of\s+_{2,}$", re.IGNORECASE)
_ENTITY = (r"(?:limited\s+liability\s+company|corporation|limited\s+partnership|"
           r"general\s+partnership|partnership|trust|company|llc|l\.l\.c\.)")
_FORMS = [re.compile(x, re.IGNORECASE) for x in (
    r"^(?:by|its|witness|signature|print|attest)\s+_{2,}$",
    r"^notary\s+public\s*_{2,}$", r"^_{2,}\s*,?\s*notary\s+public\.?$",
    r"^notary\s+public\s*,?\s+_{2,}\s+county\s*,?\s*[a-z ]{0,20}$",
    r"^notary\s+public\s*[-,]\s*state\s+of\s+[a-z ]{1,20}\s*_{2,}$",
    r"^_{2,}\s*,?\s*notary\s+public\s*,?\s*my\s+commission\s+expires:?\s*_{2,}$",
    r"^my\s+commission\s+expires:?\s*_{2,}$",
    r"^my\s+commission\s*\(\s*is\s+permanent\s*\)\s*\(\s*expires:?\s*_{2,}\s*\)$",
    r"^(?:the\s+foregoing\s+[a-z ]{0,40}?\s+was\s+|this\s+instrument\s+was\s+)?"
    r"acknowledged\s+before\s+me\b",
    r"^(?:subscribed\s+and\s+)?sworn\s+to\s+(?:and\s+subscribed\s+)?before\s+me\b",
    r"^subscribed\s+and\s+sworn\b",
    r"^before\s+me,?\s.*\bpersonally\s+appeared\b",
    r"^on\s+[^.]{0,80}?\bbefore\s+me\b.*\bappeared\b",
    r"^personally\s+(?:appeared|came)\s+before\s+me\b",
    r"^(?:as\s+)?witness\s+my\s+hand\b", r"^in\s+testimony\s+whereof\b",
    r"^given\s+under\s+my\s+hand\b", r"^i\s+hereby\s+certify\b",
    r"^this\s+instrument\s+(?:was\s+)?prepared\s+by:?\s*_{2,}\s*,?\s*"
    r"(?:attorney\s+at\s+law|esq\.?)?\.?$",
    r"^i\s+affirm,?\s+under\s+the\s+penalties\s+for\s+perjury\b.{0,200}?"
    r"\bsocial\s+security\s+number",
    r"^(?:executed|dated|signed)(?:\s+and\s+delivered)?(?:\s+(?:as\s+of|this|on))?"
    r"(?:\s+the)?\s+_{2,}\s+day\s+of\s+_{2,}(?:\s*,?\s*(?:(?:19|20)?_{2,}|\d{4}))?\.?$",
    r"^dated\s+(?:as\s+of\s+)?_{2,}\s*,\s*(?:(?:19|20)_{2,}|\d{4}|_{2,})\.?$",
    r"^receipt\s+(?:is\s+hereby\s+)?acknowledged\s+this\s+_{2,}\s+day\s+of\s+_{2,}"
    r"(?:\s*,?\s*(?:19|20)?_{2,})?\.?$",
)]
_CONTEXT_FORMS = [re.compile(x, re.IGNORECASE) for x in (
    r"^_{2,},?\s+an?\s+_{2,}(?:\s+" + _ENTITY + r")?\.?$",
    r"^_{2,},?\s+an?\s+[A-Za-z][A-Za-z .-]{0,30}?\s+" + _ENTITY + r"\.?$",
)]
# A neighbouring line that marks a signature / notary block.
_SIG_CUE_RE = re.compile(
    r"^(?:by|name|title|its|signature|authorized\s+signatory|printed\s+name)\b\s*:?"
    r"|^_{2,}\s*(?:\(\s*seal\s*\))?$|\(\s*(?:notary\s+)?seal\s*\)|notary\s+public"
    r"|acknowledged\s+before\s+me|personally\s+(?:appeared|came)|sworn\s+to"
    r"|^\)?\s*ss\b|^(?:state|commonwealth|county|parish)\s+of\b[^,]{0,40}(?:\)|\bss\b)",
    re.IGNORECASE)


def _norm_label(x: str) -> str:
    return re.sub(r"\s+", " ", x).strip().lower()


def _classify_line(line: str, in_table: bool) -> str:
    """'exempt', 'context' (exempt only inside a signature block) or 'body'."""
    t = line.replace(" ", " ").strip()
    if len(t) > 400 or "$" in t:
        return "body"
    seal = bool(_SEAL_RE.search(t))
    t = re.sub(r"\s+", " ", _STATUTORY_RE.sub(" ", _SEAL_RE.sub(" ", t))).strip()
    if re.fullmatch(r"_{2,}", t):
        return "exempt" if (seal or not in_table) else "context"
    if _VENUE_RE.match(t) or _MD_VENUE_RE.match(t):
        return "exempt"
    if _BARE_VENUE_RE.match(t):
        return "context"
    m = _LEAD_LABEL_RE.match(t)
    lead = _norm_label(m.group(1)) if m else None
    sig_lead = lead in _CORE_LABELS or lead in _CONTEXT_LABELS
    rest = t[m.end():] if (m and sig_lead) else t
    if _VALUE_WORD_RE.search(rest):
        return "body"
    if any(rx.match(t) for rx in _FORMS):
        return "exempt"
    if any(rx.match(t) for rx in _CONTEXT_FORMS):
        return "context"
    if "(" in t or ")" in t or not sig_lead:
        return "body"
    if any(_norm_label(x.group(1)) not in _CORE_LABELS and
           _norm_label(x.group(1)) not in _CONTEXT_LABELS for x in _LABEL_RE.finditer(t)):
        return "body"
    if lead in _CONTEXT_LABELS:
        return "context" if re.fullmatch(r"\s*_{2,}\s*", rest) else "body"
    return "exempt"


def _is_signature_line(line: str, in_table: bool) -> bool:
    """True if the line is exempt on its own (no signature-block context needed)."""
    return _classify_line(line, in_table) == "exempt"


# Gabriel's rulings, 2026-11-06: an exhibit captioned "Form of ..." (form of deed,
# assignment, estoppel, bill of sale, notice letter ...) is a template completed at
# closing; its blanks never block -- but a DATA caption (rent roll, legal
# description, property description, schedule / list of leases, "leases" without a
# form noun) overrides the exemption. The caption is the FIRST non-blank block after
# the heading (spacers, page breaks and a "to Purchase Agreement" heading
# continuation skipped; soft breaks joined). Accepted shapes: "Form of X",
# "(Form of X)", "[FORM OF] X", "X (Form)", "Exhibit B - Form of X",
# "Exhibit B to Purchase Agreement: Form of X". Rejected: bare "Form of", a caption
# that says "attached", a body-text colon after "Form of", a caption with a blank.
FORM_CAPTION_RE = re.compile(
    r"^\(?\s*(?:exhibit\s+[\"'“”]?[A-Z0-9]{1,3}(?:-\d+)?[\"'“”]?"
    r"(?:\s+to\s+[^:–—]{1,80}?)?\s*[-–—:.]\s*)?"
    r"\[?\s*form\s+of\s*\]?\s+(?P<rest>\S.*)$", re.IGNORECASE)
_FORM_SUFFIX_RE = re.compile(r"\(\s*form\s*\)\s*$", re.IGNORECASE)
_DATA_CAPTION_RE = re.compile(
    r"\b(?:rent\s+roll|legal\s+description|property\s+description|description\s+of\s+"
    r"(?:the\s+)?(?:property|premises|land|real\s+property)|schedule\s+of\s+leases|"
    r"lease\s+schedule|list\s+of\s+leases|leases?\s+list)\b", re.IGNORECASE)
_FORM_NOUN_RE = re.compile(
    r"\b(?:deed|assignment|estoppel|bill\s+of\s+sale|notice|letter|certificate|affidavit|"
    r"memorandum|guarant(?:y|ee)|consent|snda|subordination|release|conveyance|"
    r"agreement|assumption)\b", re.IGNORECASE)
_CONTINUATION_RE = re.compile(
    r"^to\s+(?:the\s+)?(?:[a-z]+\s+){0,6}?(?:agreement|contract|psa)\b", re.IGNORECASE)
# Any block that reads like the start of another exhibit / schedule ends a Form-of
# region, recognised heading or not (EXHIBIT "D", EXHIBIT D:, SCHEDULE 1 - Rent Roll).
_HEADING_LIKE_RE = re.compile(
    r"^\s*(?:exhibit|schedule|annex|appendix|attachment)\s+[\"'“”]?[A-Z0-9]{1,3}"
    r"(?:-\d+)?[\"'“”]?\s*(?:[:.\-–—]\s*.{0,80})?$", re.IGNORECASE)


def _is_form_caption(c: str) -> bool:
    c = re.sub(r"\s+", " ", c.replace(" ", " ")).strip()
    if not c or len(c) > 150 or re.search(r"\battached\b", c, re.IGNORECASE):
        return False
    if any(rx.search(c) for rx, _ in BLANK_PATTERNS):
        return False
    m = FORM_CAPTION_RE.match(c)
    if m:
        if ":" in m.group("rest"):
            return False                 # "Form of payment: wire transfer"
    elif not _FORM_SUFFIX_RE.search(c):
        return False
    if _DATA_CAPTION_RE.search(c):
        return False                     # data caption overrides (ruling 2026-11-06)
    if re.search(r"\bleases\b", c, re.IGNORECASE) and not _FORM_NOUN_RE.search(c):
        return False
    return True


KNOWLEDGE_DEF_RE = re.compile(
    r"(?:to\s+(?:the\s+)?(?:Seller|Purchaser|Buyer)(?:'s|’s)?\s+(?:actual\s+)?knowledge"
    r"|knowledge\s+of\s+(?:the\s+)?(?:Seller|Purchaser|Buyer))", re.IGNORECASE)


def _load(path: Path) -> ET.Element:
    with zipfile.ZipFile(path) as z:
        if "word/document.xml" not in z.namelist():
            raise KeyError("word/document.xml")
        return ET.fromstring(z.read("word/document.xml"))


def _text_of(el: ET.Element, include_deleted: bool = False) -> str:
    """Visible text. Deleted text is EXCLUDED by default — text the counterparty
    struck must not count toward exhibit population or trip blank detection (a
    struck '____' replaced by a real value is not an unfilled blank)."""
    out = []
    for n in el.iter():
        if n.tag == W + "t":
            out.append(n.text or "")
        elif n.tag == W + "delText" and include_deleted:
            out.append(n.text or "")
        elif n.tag == W + "tab":
            out.append(" ")
    return "".join(out)


def _is_placeholder(n: ET.Element) -> bool:
    return n.tag == W + "sdt" and n.find(W + "sdtPr/" + W + "showingPlcHdr") is not None


def _content_text(el: ET.Element) -> str:
    """Visible text for exhibit POPULATION of a table: deleted text and the prompt
    text of an empty content control ("Click or tap here ...") do not count."""
    out = []
    stack = [el]
    while stack:
        n = stack.pop()
        if _is_placeholder(n):
            continue
        if n.tag == W + "t":
            out.append(n.text or "")
        elif n.tag == W + "tab":
            out.append(" ")
        stack.extend(reversed(list(n)))
    return "".join(out)


def _para_lines(el: ET.Element) -> list:
    """Visible text of a paragraph split into lines at soft breaks (w:br / w:cr)."""
    out = []
    for n in el.iter():
        if n.tag == W + "t":
            out.append(n.text or "")
        elif n.tag == W + "tab":
            out.append(" ")
        elif n.tag in (W + "br", W + "cr"):
            out.append("\n")
    return "".join(out).split("\n")


def _count_media(el: ET.Element) -> int:
    return sum(1 for n in el.iter() if n.tag in (A_BLIP, V_IMAGE))


_ROW_WRAPPERS = (W + "sdt", W + "sdtContent", W + "customXml")


def _table_rows(tbl: ET.Element) -> list:
    """This table's own rows, including rows wrapped in content controls (w:sdt)
    or custom XML -- not rows of tables nested inside its cells. Iterative: wrapper
    nesting depth is attacker/tool controlled and must not hit the recursion limit."""
    rows = []
    stack = list(reversed(list(tbl)))
    while stack:
        ch = stack.pop()
        if ch.tag == W + "tr":
            rows.append(ch)
        elif ch.tag in _ROW_WRAPPERS:
            stack.extend(reversed(list(ch)))
    return rows


_DIGIT_RUN = re.compile(r"\d{3,}")


def _row_cells(tr: ET.Element) -> list:
    return tr.findall(W + "tc") + tr.findall(W + "sdt/" + W + "sdtContent/" + W + "tc")


def _is_label_row(tr: ET.Element) -> bool:
    """A column-header row: 2+ non-empty cells, each a short label (<= 40 chars)
    with no run of 3+ digits. A single-cell row, a long cell or a value such as a
    parcel number is content, not a header."""
    filled = [t for t in (_text_of(tc).strip() for tc in _row_cells(tr)) if t]
    return len(filled) >= 2 and all(len(t) <= 40 and not _DIGIT_RUN.search(t)
                                    for t in filled)


def _grid_span(tc: ET.Element) -> int:
    span = tc.find(W + "tcPr/" + W + "gridSpan")
    if span is None:
        return 1
    try:
        return int(span.get(W + "val", ""))
    except (TypeError, ValueError):  # "", "x", "²", "①" ... -> unmerged
        return 1


def _header_rows(rows: list) -> int:
    """Number of leading header rows. Normally one, and only if that row reads as
    column labels. More when unambiguous: a run of rows marked as repeating headers
    (w:tblHeader -- ignored when EVERY row carries it), or, in a table of 3+ rows,
    a first row that is one cell merged across columns (a title) followed by the
    column-label row."""
    if not rows:
        return 0
    marked = [tr.find(W + "trPr/" + W + "tblHeader") is not None for tr in rows]
    n = 1
    if not all(marked):
        while n < len(rows) and marked[n] and marked[n - 1]:
            n += 1
    if len(rows) > 2:
        cells = rows[0].findall(W + "tc")
        if len(cells) == 1 and _grid_span(cells[0]) > 1:
            n = max(n, 2)
    if not _is_label_row(rows[n - 1]):
        n -= 1  # the would-be column header is itself content
    return n


def _table_has_data(tbl: ET.Element) -> bool:
    """True if any row after the header row(s) carries visible text (deleted text
    excluded), in this table or in any table nested inside it. Each table in the
    subtree is examined once (tbl.iter includes tbl itself), so the cost is linear
    in the number of nested tables rather than exponential in their depth."""
    for t in tbl.iter(W + "tbl"):
        rows = _table_rows(t)
        if any(_text_of(tr).strip() for tr in rows[_header_rows(rows):]):
            return True
    return False


def _blocks(root: ET.Element) -> list:
    body = root.find(W + "body")
    if body is None:
        return []
    out = []
    for el in body:
        tag = el.tag.split("}")[-1]
        out.append((tag if tag in ("p", "tbl") else "other", el))
    return out


def _exhibit_heading(kind: str, el: ET.Element, text: str):
    """Exhibit letter if this block is an exhibit heading, else None. A heading placed
    inside a table is still a heading."""
    m = EXHIBIT_HEAD_RE.match(text.strip())
    if m:
        return m.group(1).upper()
    if kind == "tbl":
        for p in el.iter(W + "p"):
            m = EXHIBIT_HEAD_RE.match(_text_of(p).strip())
            if m:
                return m.group(1).upper()
    return None


def _first_blank(t: str):
    for rx, label in BLANK_PATTERNS:
        m = rx.search(t)
        if m:
            lo, hi = max(0, m.start() - 70), min(len(t), m.end() + 70)
            return label, t[lo:hi].strip().replace("\n", " ")
    return None


def _joined_lines(el: ET.Element) -> str:
    return " ".join(x.strip() for x in _para_lines(el) if x.strip())


def _block_lead_text(kind: str, el: ET.Element) -> str:
    """A block's text for caption / heading-like tests: a paragraph's joined lines,
    or a table's first non-empty paragraph."""
    if kind == "tbl":
        for para in el.iter(W + "p"):
            t = _joined_lines(para)
            if t:
                return t
        return ""
    return _joined_lines(el)


def _form_info(blocks: list, start: int, end: int):
    """(is_form, form_end): is the exhibit at heading block `start` captioned as a
    real "Form of ..." exhibit, and where its form region ends (the first
    heading-like block after the caption, else `end`)."""
    caption, cap_j = None, None
    kind, el = blocks[start]
    if kind == "tbl":
        after = False
        for para in el.iter(W + "p"):
            pt = _joined_lines(para)
            if not after:
                after = bool(EXHIBIT_HEAD_RE.match(_text_of(para).strip()))
                continue
            if pt and not _CONTINUATION_RE.match(pt):
                caption, cap_j = pt, start
                break
    if caption is None:
        for j in range(start + 1, end):
            pt = _block_lead_text(*blocks[j])
            if not pt or DMS_STAMP_RE.match(pt) or _CONTINUATION_RE.match(pt):
                continue
            caption, cap_j = pt, j
            break
    if caption is None or not _is_form_caption(caption):
        return False, start
    for j in range(cap_j + 1, end):
        if _HEADING_LIKE_RE.match(_block_lead_text(*blocks[j])):
            return True, j
    return True, end


def _exhibit_stream(blocks: list, start: int, end: int) -> list:
    """Lines of a post-signature exhibit, in order: (block, cell, multi_cell, line).
    `cell` identifies the table cell a line sits in (None for a paragraph line);
    `multi_cell` is True for a line in a table of more than one cell. The EXHIBIT X
    paragraph of a heading block is skipped."""
    out = []
    for i in range(start, end):
        kind, el = blocks[i]
        if i == start and kind != "tbl":
            continue
        if kind != "tbl":
            paras = [el] if kind == "p" else (list(el.iter(W + "p")) or [el])
            for para in paras:
                for ln in _para_lines(para):
                    out.append((i, None, False, ln.strip()))
            continue
        owner = {}
        cells = list(el.iter(W + "tc"))
        for tc in cells:
            for para in tc.iter(W + "p"):
                owner[para] = tc      # innermost cell wins (document order)
        multi = len(cells) > 1
        for para in el.iter(W + "p"):
            if i == start and EXHIBIT_HEAD_RE.match(_text_of(para).strip()):
                continue
            cell = owner.get(para)
            for ln in _para_lines(para):
                out.append((i, id(cell) if cell is not None else None, multi, ln.strip()))
    return out


def _in_signature_block(stream: list, k: int, by_cell: dict, para_pos: dict) -> bool:
    """Is line k next to a signature / notary cue (same table cell, else within
    three non-empty paragraph lines)?"""
    i, cell, _multi, _line = stream[k]
    if cell is not None:
        return any(_SIG_CUE_RE.search(stream[x][3]) for x in by_cell[cell] if x != k)
    pos = para_pos[k]
    plines = para_pos["order"]
    for q in plines[max(0, pos - 3):pos] + plines[pos + 1:pos + 4]:
        if _SIG_CUE_RE.search(stream[q][3]):
            return True
    return False


def _scan_exhibit(stream: list, form_end: int, is_form: bool):
    """Classify the blanks of one post-signature exhibit. Returns three dicts
    block -> entry: form (exempt template), body (blocking) and signature."""
    by_cell, order = {}, []
    for k, (_i, cell, _m, ln) in enumerate(stream):
        if not ln:
            continue
        if cell is not None:
            by_cell.setdefault(cell, []).append(k)
        else:
            order.append(k)
    para_pos = {k: n for n, k in enumerate(order)}
    para_pos["order"] = order
    form, body, sig = {}, {}, {}
    for k, (i, cell, multi, ln) in enumerate(stream):
        if not ln or DMS_STAMP_RE.match(ln):
            continue
        hit = _first_blank(ln)
        if not hit:
            continue
        entry = {"block": i, "kind": hit[0], "context": hit[1]}
        if is_form and i < form_end:
            form.setdefault(i, entry)
            continue
        verdict = _classify_line(ln, multi)
        if verdict == "context":
            verdict = "exempt" if _in_signature_block(stream, k, by_cell, para_pos) else "body"
        if verdict == "body":
            body.setdefault(i, entry)
        else:
            sig.setdefault(i, entry)
    return form, body, sig


def audit(path: Path) -> dict:
    root = _load(path)
    blocks = _blocks(root)
    texts = [_text_of(el) for _, el in blocks]

    chrome_at = len(blocks)
    for i, t in enumerate(texts):
        if any(m in t.strip().lower() for m in SUMMARY_MARKERS):
            chrome_at = i
            break
    limit = chrome_at

    sig_at = limit
    for i in range(limit):
        if SIGNATURE_START_RE.search(texts[i].strip()):
            sig_at = i
            break

    # ---- 1. exhibit population -------------------------------------------
    heads = []
    for i in range(limit):
        letter = _exhibit_heading(blocks[i][0], blocks[i][1], texts[i])
        if letter:
            heads.append((i, letter))

    exhibits = []
    for n, (start, letter) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else limit
        chars = media = tables = 0
        data_tables = prose_chars = 0
        caption = ""
        for j in range(start + 1, end):
            kind, el = blocks[j]
            t = texts[j].strip()
            media += _count_media(el)
            if kind == "tbl":
                tables += 1
                # Population counts visible text only: a DMS stamp or an empty
                # content-control prompt is not content (2026-11-06 ruling, LOW).
                tt = _content_text(el).strip()
                if not DMS_STAMP_RE.match(tt):
                    chars += len(tt)
                # A header row with no non-blank row after it (a skeleton rent roll
                # or schedule) is populated but says nothing: advisory THIN only.
                if _table_has_data(el):
                    data_tables += 1
                continue
            if DMS_STAMP_RE.match(t):
                continue  # law-firm document stamp, not exhibit content
            if not caption and t and (t.startswith("(") or len(t) < 40) \
                    and j <= start + 2:
                caption = t
                continue
            chars += len(t)
            prose_chars += len(t)
        # An empty table grid (zero rows, every cell blank) is EMPTY, not populated:
        # Gabriel's ruling, 2026-11-06. A table counts only through its text/images.
        populated = bool(chars or media)
        exhibits.append({
            "letter": letter, "caption": caption, "block": start,
            "text_chars": chars, "images": media, "tables": tables,
            "data_tables": data_tables,
            "form": _form_info(blocks, start, end)[0],
            "populated": populated,
            "thin": populated and ((chars < 60 and not tables)
                                   or (tables and not data_tables
                                       and prose_chars < 60)),
        })

    # ---- 2. cross-references ---------------------------------------------
    body_limit = heads[0][0] if heads else limit
    referenced = {}
    for i in range(body_limit):
        for m in EXHIBIT_REF_RE.finditer(texts[i]):
            for letter in EXHIBIT_LETTER_RE.findall(m.group(1)):
                referenced[letter] = referenced.get(letter, 0) + 1
    present = {e["letter"] for e in exhibits}
    dangling_exhibit = sorted(set(referenced) - present)
    orphan_exhibit = sorted(present - set(referenced))

    section_heads = set()
    for i in range(body_limit):
        m = SECTION_HEAD_RE.match(texts[i].strip())
        if m:
            section_heads.add(m.group(1))
            # A heading "9.2" also establishes that article 9 exists.
            parts = m.group(1).split(".")
            for k in range(1, len(parts)):
                section_heads.add(".".join(parts[:k]))

    dangling_section, likely_citations = [], []
    seen = set()
    for i in range(body_limit):
        t = texts[i]
        for m in SECTION_REF_RE.finditer(t):
            ref = m.group(1)
            if ref in seen or ref in section_heads:
                continue
            if STATUTE_BEFORE_RE.search(t[max(0, m.start() - 60):m.start()]):
                continue
            if STATUTE_AFTER_RE.match(t[m.end():m.end() + 45]):
                continue
            seen.add(ref)
            head = int(ref.split(".")[0])
            (likely_citations if head > MAX_PLAUSIBLE_SECTION
             else dangling_section).append(ref)
    dangling_section.sort(key=lambda x: [int(p) for p in x.split(".")])
    likely_citations.sort(key=lambda x: [int(p) for p in x.split(".")])

    # ---- 3. unfilled blanks ----------------------------------------------
    body_blanks, sig_blanks, form_blanks = [], [], []
    # Exhibit ranges after the signature page, built ONLY from headings at or after
    # IN WITNESS WHEREOF (an exhibit list or an exhibit placed before it must not
    # swallow the signature page). The heading block is in range (a heading table
    # can hold the exhibit's rows). Each exhibit is scanned line by line once.
    region = [None] * limit
    verdicts = {}
    for n, (start, _letter) in enumerate(heads):
        if start < sig_at:
            continue
        end = heads[n + 1][0] if n + 1 < len(heads) else limit
        is_form, form_end = _form_info(blocks, start, end)
        f, b, g = _scan_exhibit(_exhibit_stream(blocks, start, end), form_end, is_form)
        for j in range(start, end):
            region[j] = n
            if j in b:
                verdicts[j] = ("body", b[j])
            elif j in g:
                verdicts[j] = ("sig", g[j])
            elif j in f:
                verdicts[j] = ("form", f[j])
    for i in range(limit):
        t = texts[i]
        if not t.strip() or DMS_STAMP_RE.match(t.strip()):
            continue
        if region[i] is not None:
            if i in verdicts:
                kind_, entry = verdicts[i]
                {"body": body_blanks, "sig": sig_blanks, "form": form_blanks}[kind_].append(entry)
            continue
        for rx, label in BLANK_PATTERNS:
            m = rx.search(t)
            if not m:
                continue
            lo, hi = max(0, m.start() - 70), min(len(t), m.end() + 70)
            entry = {"block": i, "kind": label,
                     "context": t[lo:hi].strip().replace("\n", " ")}
            (sig_blanks if i >= sig_at else body_blanks).append(entry)
            break

    # ---- 4. knowledge party ----------------------------------------------
    knowledge = {"found": False, "unfilled": False, "context": ""}
    for i in range(min(sig_at, limit)):
        t = texts[i]
        if not KNOWLEDGE_DEF_RE.search(t):
            continue
        if re.search(r"shall\s+mean|means|refers\s+to", t, re.I):
            knowledge["found"] = True
            if re.search(r"_{3,}", t):
                knowledge["unfilled"] = True
                knowledge["context"] = t.strip()[:260]
            break

    empty = [e for e in exhibits if not e["populated"]]
    blocking = bool(empty or dangling_exhibit or dangling_section
                    or body_blanks or knowledge["unfilled"])

    return {
        "file": path.name,
        "blocks": len(blocks),
        "exhibits": exhibits,
        "empty_exhibits": [e["letter"] for e in empty],
        "thin_exhibits": [e["letter"] for e in exhibits if e["thin"]],
        "exhibit_refs": referenced,
        "dangling_exhibit_refs": dangling_exhibit,
        "unreferenced_exhibits": orphan_exhibit,
        "dangling_section_refs": dangling_section,
        "likely_statutory_citations": likely_citations,
        "body_blanks": body_blanks,
        "signature_blanks": sig_blanks,
        "form_exhibits": [e["letter"] for e in exhibits
                          if e["form"] and e["block"] >= sig_at],
        "form_blanks": form_blanks,
        "knowledge_party": knowledge,
        "blocking": blocking,
    }


def render(r: dict) -> str:
    L = []
    add = L.append
    add("=" * 78)
    add("COMPLETENESS AUDIT — {}".format(r["file"]))
    add("=" * 78)

    add("")
    add("-- 1. EXHIBIT POPULATION " + "-" * 52)
    if not r["exhibits"]:
        add("   no exhibit headings found")
    for e in r["exhibits"]:
        flag = ("EMPTY   <-- BLOCKING" if not e["populated"]
                else "THIN    <-- verify sufficiency" if e["thin"] else "ok")
        cap = " {}".format(e["caption"]) if e["caption"] else ""
        add("   Exhibit {}{:<30} chars={:<6} img={} tbl={}  {}".format(
            e["letter"], cap, e["text_chars"], e["images"], e["tables"], flag))
    if r["empty_exhibits"]:
        add("")
        add("   !! EMPTY: {} — an exhibit the body relies on is a blank page.".format(
            ", ".join(r["empty_exhibits"])))
        add("   !! Trace what depends on it before signing: definitions,")
        add("   !! representation carve-outs and delivery obligations commonly")
        add("   !! hang off exhibits and fail silently when they are blank.")
    skeleton = [e["letter"] for e in r["exhibits"]
                if e["thin"] and e["tables"] and not e.get("data_tables")]
    prose_thin = [x for x in r["thin_exhibits"] if x not in skeleton]
    if prose_thin:
        add("   ?  THIN: {} — ask whether a third party could draft from it. A "
            "recordable".format(", ".join(prose_thin)))
        add("      instrument cannot be prepared from an aerial markup, nor a deed "
            "from a parcel number.")
    if skeleton:
        add("   ?  THIN: {} — table has a header row and no data rows (skeleton "
            "rent roll".format(", ".join(skeleton)))
        add("      or schedule). Anything defined by reference to it is empty; "
            "populate it or")
        add("      confirm it is intentionally blank.")

    add("")
    add("-- 2. CROSS-REFERENCES " + "-" * 54)
    add("   exhibits referenced in body : {}".format(
        ", ".join("{}({})".format(k, v)
                  for k, v in sorted(r["exhibit_refs"].items())) or "—"))
    if r["dangling_exhibit_refs"]:
        add("   !! REFERENCED BUT ABSENT   : {}".format(
            ", ".join(r["dangling_exhibit_refs"])))
    if r["unreferenced_exhibits"]:
        add("   ?  present but never cited : {}".format(
            ", ".join(r["unreferenced_exhibits"])))
    if r["dangling_section_refs"]:
        add("   !! SECTION REFS THAT DO NOT RESOLVE: {}".format(
            ", ".join(r["dangling_section_refs"])))
    if r["likely_statutory_citations"]:
        add("   ?  probable statute cites (advisory): {}".format(
            ", ".join(r["likely_statutory_citations"])))
    if not (r["dangling_exhibit_refs"] or r["dangling_section_refs"]):
        add("   all exhibit and section cross-references resolve")

    add("")
    add("-- 3. UNFILLED BLANKS " + "-" * 55)
    if not r["body_blanks"]:
        add("   none in the body")
    for b in r["body_blanks"]:
        add("   !! [block {}] {}".format(b["block"], b["kind"]))
        add("      …{}…".format(b["context"]))
    if r.get("form_blanks"):
        add("   ({} blank(s) in form exhibit(s) {} -- templates completed at closing,"
            .format(len(r["form_blanks"]), ", ".join(r["form_exhibits"])))
        add("    not blocking)")
    if r["signature_blanks"]:
        add("   ({} blank(s) in the signature block — expected, but must be "
            "completed".format(len(r["signature_blanks"])))
        add("    consistently at execution)")

    add("")
    add("-- 4. KNOWLEDGE PARTY " + "-" * 55)
    k = r["knowledge_party"]
    if not k["found"]:
        add("   no knowledge-party definition located (confirm by eye if the")
        add("   representations are knowledge-qualified)")
    elif k["unfilled"]:
        add("   !! UNFILLED — every knowledge-qualified representation in this")
        add("   !! document is unbounded or void until a named individual and")
        add("   !! title are inserted. Signing blocker.")
        add("      …{}…".format(k["context"]))
    else:
        add("   defined")

    add("")
    add("=" * 78)
    add("BLOCKING DEFECTS PRESENT" if r["blocking"] else "NO BLOCKING DEFECTS")
    add("=" * 78)
    return "\n".join(L)


KNOWN_FLAGS = {"--json"}


def main(argv: list) -> int:
    args = [a for a in argv[1:] if not a.startswith("--")]
    flags = {a for a in argv[1:] if a.startswith("--")}
    unknown = flags - KNOWN_FLAGS
    if unknown:
        print("error: unknown flag(s): {}".format(", ".join(sorted(unknown))),
              file=sys.stderr)
        return 3
    if not args:
        print(__doc__)
        return 3
    path = Path(args[0])
    if not path.exists():
        print("error: no such file: {}".format(path), file=sys.stderr)
        return 3
    try:
        r = audit(path)
    except (zipfile.BadZipFile, KeyError, ET.ParseError, OSError,
            ValueError, RecursionError) as exc:
        print("error: could not read {} as a .docx: {}".format(path.name, exc),
              file=sys.stderr)
        return 3
    print(json.dumps(r, indent=2) if "--json" in flags else render(r))
    return 1 if r["blocking"] else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
