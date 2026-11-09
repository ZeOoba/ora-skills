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
    r"\b(?:rents?|rental|rentable|prices?|parcels?|lots?|suites?|units?|terms?|deposits?|"
    r"square\s+f(?:ee|oo)t(?:age)?|sq\.?\s*ft|acres?|commencement|expiration|closing|"
    r"effective|consideration|dollars|amounts?|balances?|fees?|premises|address(?:es)?|"
    r"apn|pin|tax\s+id)\b", re.IGNORECASE)
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
    r"^this\s+instrument\s+(?:was\s+)?prepared\s+by:?\s*_{2,}\s*,?\s*"
    r"(?:attorney\s+at\s+law|esq\.?)?\.?$",
    r"^(?:executed|dated|signed)(?:\s+and\s+delivered)?(?:\s+(?:as\s+of|this|on))?"
    r"(?:\s+the)?\s+_{2,}\s+day\s+of\s+_{2,}(?:\s*,?\s*(?:(?:19|20)?_{2,}|\d{4}))?\.?$",
    r"^dated\s+(?:as\s+of\s+)?_{2,}\s*,\s*(?:(?:19|20)_{2,}|\d{4}|_{2,})\.?$",
    r"^receipt\s+(?:is\s+hereby\s+)?acknowledged\s+this\s+_{2,}\s+day\s+of\s+_{2,}"
    r"(?:\s*,?\s*(?:19|20)?_{2,})?\.?$",
)]
# Notary acknowledgment SENTENCES (OH / IN / MD / MO / KS / WI / TN). Their prefixes
# are not end-anchored, so they are exempt only next to a strong notary cue (a Notary
# Public title line, a commission line, a venue / ss / TO WIT line, a notary seal),
# never on their own and never cueing each other. They may run to 900 characters
# (TN TCA 66-22-107 and MD / MO corporate forms exceed 400).
_NOTARY_SENTENCES = [re.compile(x, re.IGNORECASE) for x in (
    r"^(?:the\s+foregoing\s+[a-z ]{0,40}?\s+was\s+|this\s+instrument\s+was\s+)?"
    r"acknowledged\s+before\s+me\b",
    r"^(?:subscribed\s+and\s+)?sworn\s+to\s+(?:and\s+subscribed\s+)?before\s+me\b",
    r"^subscribed\s+and\s+sworn\b",
    r"^before\s+me,?\s.*\bpersonally\s+appeared\b",
    r"^on\s+[^.]{0,80}?\bbefore\s+me\b.*\bappeared\b",
    r"^personally\s+(?:appeared|came)\s+before\s+me\b",
    r"^(?:as\s+)?witness\s+my\s+hand\b", r"^in\s+testimony\s+whereof\b",
    r"^given\s+under\s+my\s+hand\b", r"^i\s+hereby\s+certify\b",
    r"^i\s+affirm,?\s+under\s+the\s+penalties\s+for\s+perjury\b.{0,200}?"
    r"\bsocial\s+security\s+number",
)]
_CONTEXT_FORMS = [re.compile(x, re.IGNORECASE) for x in (
    r"^_{2,},?\s+an?\s+_{2,}(?:\s+" + _ENTITY + r")?\.?$",
    r"^_{2,},?\s+an?\s+[A-Za-z][A-Za-z .-]{0,30}?\s+" + _ENTITY + r"\.?$",
)]
# Cue lines. A SIGNATURE cue is a signature label followed by a blank ("By: ____",
# "Name: ____") or a seal-only line -- prose such as "Its lease expires", "Title
# Company:" or "By-laws" is not a cue, nor is a completed "By: /s/ ...". A NOTARY cue
# is a strong notary marker: a Notary Public title line, a commission / term /
# appointment / county-of-residence line, a venue line ending in ")" or "ss", an MD
# "TO WIT:" venue, or a notary seal -- never an acknowledgment sentence.
_SIG_CUE_RE = re.compile(
    r"^(?:by|name|title|its|signature|print(?:ed)?(?:\s+name)?|authorized\s+signatory)"
    r"\s*:?\s*_{2,}|^_{0,40}\s*\(\s*seal\s*\)\s*_{0,40}$", re.IGNORECASE)
_NOTARY_CUE_RE = re.compile(
    r"^(?:_{2,}\s*,?\s*)?notary\s+public\b|^my\s+commission\s+(?:expires|expiration)"
    r"|^commission\s+(?:no\b|number)|\(\s*notary\s+seal\s*\)|^my\s+(?:term|appointment)\s+"
    r"expires|^(?:my\s+)?county\s+of\s+residence|^\)?\s*ss\b"
    r"|^(?:state|commonwealth|county|parish)\s+of\b[^,]{0,40}(?:\)|\bss\b)"
    r"|,\s*to\s+wit:?\s*$|^_{2,}\s+county\s*\)", re.IGNORECASE)


# Strict context (a data-captioned exhibit, or past the end of a Form-of region;
# merge-gate REFUTE C3 and round-2 R1, 2026-11-08): a bare rule ("________") or an
# unfilled Name: / Title: / Date: label (_GATED_LABEL_RE) is a signature blank only
# inside a signature stack anchored by a STRONG cue. A strong cue is a WHOLE line:
#   - an unfilled By: line ("By: ________");
#   - a filled By: line whose rest is a personal name ("By: Jane Q. Doe[, Manager]"),
#     or that has a Name: / Title: / Its: line directly beside it;
#   - a seal-only line ("________ (SEAL)", "(L.S.)");
#   - a Notary Public title line, a commission expires / number line, or a full
#     venue line ("STATE OF OHIO )", "COUNTY OF FRANKLIN ) ss:");
#   - a signature caption used as a whole label -- (Signature), Signature,
#     Authorized Signatory / Signature, Print(ed) Name -- followed by nothing, a
#     blank or a personal name.
# Mid-prose matches never count ("..., to wit:", 'County of Franklin (the
# "County")', "Monument stamped (SEAL)", "I hereby certify", "Signature Aviation
# LLC", "By: Acme LLC"). Weak labels (Name: / Title: / Its: / Date: / Dated /
# Witness / Attest ...) never anchor a stack, filled or not -- "Name: Acme LLC" and
# "Date: October 31, 2026" are rent-roll data -- but link it: the stack is walked
# outward over at most _STACK_REACH weak-label lines (reach 3 = By / Name / Title /
# Date). A stack holds at most one rule: a rule met during the walk fails it.
_BARE_RULE_RE = re.compile(r"_{2,}")
_WEAK_LABEL_RE = re.compile(
    r"^(?:name(?:\s*(?:and|/)\s*title)?|title|its|date(?:\s+signed)?|witness(?:es)?|"
    r"attest)\s*(?::|_{2,}|$)|^(?:dated|executed|signed)(?:\s*:|\s+_{2,}|"
    r"\s+(?:and\s+delivered\s+)?(?:as\s+of|this|on\s+(?:this|the)|the)\b)",
    re.IGNORECASE)
_STACK_REACH = 3
# Unfilled weak labels that read as data fields in a data exhibit and so need a
# stack (REFUTE C3 case 6). Signature-only words (Its, Attest, Witness, Date
# Signed, Name and Title, Dated as of / Executed this ... day of) stay exempt on
# their own per the 2026-11-06 line-level ruling.
_GATED_LABEL_RE = re.compile(r"^(?:name|title|date)\s*:", re.IGNORECASE)
_NAME_TITLE_ITS_RE = re.compile(r"^(?:name|title|its)\s*:", re.IGNORECASE)
_BY_RE = re.compile(r"^by\s*(?::\s*|(?=_))(?P<rest>.*)$", re.IGNORECASE)
_CAPTION_RE = re.compile(
    r"^\(?\s*(?:signature|authorized\s+signat(?:ory|ure)|print(?:ed)?\s+name)\s*"
    r"(?:\)\s*$|:\s*|(?=_)|$)(?P<rest>.*)$", re.IGNORECASE)
# A personal name: 2-3 words (Unicode letters, inner apostrophes / hyphens), each
# starting upper-case (all-caps allowed), an optional middle initial, and an
# optional ", Title" -- never an entity word or a placeholder word (round 3).
_NAME_WORD_RE = re.compile(r"[^\W\d_](?:[^\W\d_]|['\u2019-](?=[^\W\d_]))*")
_INITIAL_RE = re.compile(r"[^\W\d_]\.")
_PLACEHOLDER_WORD_RE = re.compile(
    r"\b(?:to\s+be|tbd|tba|see|pending|will|provided|follows?|following|deliver(?:ed|y)?|"
    r"list|n/?a|none|unknown|later|yet|available|forthcoming|counsel)\b", re.IGNORECASE)
_ENTITY_WORD_RE = re.compile(
    r"\b(?:llc|l\.l\.c|inc|corp|corporation|co|company|holdings?|trust|partners|"
    r"partnership|lp|llp|ltd|bank|group|properties|realty|associates|industrial|"
    r"park|capital|ventures|enterprises|investments?|fund|management)\b\.?",
    re.IGNORECASE)
# Seal tokens for the seal-only cue line: (SEAL), [SEAL], (Corporate Seal),
# (Notary Seal), (L.S.) / [L.S.].
_SEAL_ANY_RE = re.compile(
    r"[(\[]\s*(?:corporate\s+|notary\s+)?(?:seal|l\.?\s?s\.?)\s*[)\]]", re.IGNORECASE)
_NOTARY_LINE_RE = re.compile(
    r"^(?:_{2,}\s*,?\s*)?notary\s+public\.?(?:\s*[,-]?\s*(?:in\s+and\s+for\s+)?"
    r"(?:the\s+)?(?:state\s+of\s+[a-z ]{1,25}|[a-z ]{1,25}\s+county))?\s*(?:_{2,})?$"
    r"|^my\s+commission\s+(?:expires|expiration)(?:\s+on)?\s*:?\s*(?:_{2,}|"
    r"[a-z]{3,9}\.?\s+\d{1,2},?\s+\d{4}|\d{1,2}/\d{1,2}/\d{2,4})?$"
    r"|^commission\s+(?:no\.?|number)\s*:?\s*(?:_{2,}|[a-z0-9-]{1,20})?$", re.IGNORECASE)


def _norm_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.replace("\u00a0", " ")).strip()


def _words_ok(words: list, lo: int, hi: int, initials: bool) -> bool:
    names = [w for w in words if not (initials and _INITIAL_RE.fullmatch(w))]
    if not lo <= len(names) <= hi or len(words) - len(names) > 1:
        return False
    return all((_NAME_WORD_RE.fullmatch(w) or (initials and _INITIAL_RE.fullmatch(w)))
               and w[0].isupper() for w in words)


def _is_person(rest: str) -> bool:
    if len(rest) > 80 or _ENTITY_WORD_RE.search(rest) or _PLACEHOLDER_WORD_RE.search(rest):
        return False
    name, comma, title = rest.partition(",")
    if not _words_ok(name.split(), 2, 3, True):
        return False
    title = re.sub(r"^\s*its\s+", "", title, flags=re.IGNORECASE).split()
    return not comma or _words_ok(title, 1, 3, False)


def _blank_or_person(rest: str) -> bool:
    rest = _SEAL_ANY_RE.sub(" ", rest).strip()
    rest = re.sub(r"^_{2,}\s*", "", rest).strip()
    if not rest:
        return True
    return _is_person(rest)


def _is_whole_line_cue(t: str) -> bool:
    """A strong cue judged on the line alone (By: handled by the caller)."""
    if "$" in t:
        return False
    if _SEAL_ANY_RE.search(t) and not re.sub(r"[_\s]", "", _SEAL_ANY_RE.sub("", t)):
        return True                                        # seal-only line
    if _NOTARY_LINE_RE.match(t) or _VENUE_RE.match(t):
        return True
    m = _CAPTION_RE.match(t)
    return bool(m) and _blank_or_person(m.group("rest"))


def _is_strong_cue(lst: list, j: int, stream: list) -> bool:
    t = _norm_line(stream[lst[j]][3])
    m = _BY_RE.match(t)
    if m:
        if "$" in t or _VALUE_WORD_RE.search(t):
            return False
        if _blank_or_person(m.group("rest")):
            return True
        return any(0 <= q < len(lst) and
                   _NAME_TITLE_ITS_RE.match(_norm_line(stream[lst[q]][3]))
                   for q in (j - 1, j + 1))
    return _is_whole_line_cue(t)


def _is_weak_link(t: str) -> bool:
    if "$" in t or _VALUE_WORD_RE.search(t):
        return False
    return bool(_WEAK_LABEL_RE.match(t))


def _needs_stack(line: str) -> bool:
    """An exempt-classified line that, in strict context, needs a signature stack:
    a bare rule or an unfilled Name: / Title: / Date: label (never a seal line)."""
    t = _norm_line(line)
    if _SEAL_RE.search(t):
        return False
    return bool(_BARE_RULE_RE.fullmatch(t) or _GATED_LABEL_RE.match(t))


def _in_signature_stack(stream: list, k: int, pos: dict, lists: dict) -> bool:
    """Is line k linked to a strong cue through at most _STACK_REACH adjacent weak-
    label lines (same table cell for a cell line), with no second rule in reach
    before the cue? O(_STACK_REACH)."""
    lst = lists[stream[k][1]]
    i = pos[k]
    found = False
    for step in (-1, 1):
        j = i
        for _ in range(_STACK_REACH):
            j += step
            if j < 0 or j >= len(lst):
                break
            t = _norm_line(stream[lst[j]][3])
            if _BARE_RULE_RE.fullmatch(t):
                return False                     # at most one rule per stack
            if _is_strong_cue(lst, j, stream):
                found = True
                break
            if not _is_weak_link(t):
                break
    return found


def _norm_label(x: str) -> str:
    return re.sub(r"\s+", " ", x).strip().lower()


def _classify_line(line: str, in_table: bool) -> str:
    """'exempt'; 'party' (exempt only with a signature cue on an adjacent line);
    'context' (exempt only with a signature cue within 3 lines); 'notary' (exempt
    only with a notary cue within 3 lines); or 'body'."""
    t = line.replace(" ", " ").strip()
    if len(t) > 900 or "$" in t:
        return "body"
    seal = bool(_SEAL_RE.search(t))
    t = re.sub(r"\s+", " ", _STATUTORY_RE.sub(" ", _SEAL_RE.sub(" ", t))).strip()
    sentence = any(rx.match(t) for rx in _NOTARY_SENTENCES)
    if len(t) > 400 and not sentence:
        return "body"
    if re.fullmatch(r"_{2,}", t):
        return "exempt" if (seal or not in_table) else "context"
    if _VENUE_RE.match(t) or _MD_VENUE_RE.match(t):
        return "exempt"
    if _BARE_VENUE_RE.match(t):
        return "notary"
    m = _LEAD_LABEL_RE.match(t)
    lead = _norm_label(m.group(1)) if m else None
    sig_lead = lead in _CORE_LABELS or lead in _CONTEXT_LABELS
    rest = t[m.end():] if (m and sig_lead) else t
    if _VALUE_WORD_RE.search(rest):
        return "body"
    if sentence:
        return "notary"
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
        return "party" if re.fullmatch(r"\s*_{2,}\s*", rest) else "body"
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
    r"\b(?:rent\s+roll|legal\s+descr|(?:property|premises|land)\s+(?:legal\s+)?description|"
    r"description\s+of\s+(?:the\s+)?(?:property|premises|land|real\s+property)|schedule|"
    r"tenant\s+(?:list|roster|schedule)|list\s+of\s+(?:leases|tenants)|leases?\s+list)",
    re.IGNORECASE)
# Data phrases that a real form can also mention ("Form of Assignment of Service
# Contracts", "... and Assumption of Leases"): data unless a form noun is present.
_WEAK_DATA_RE = re.compile(
    r"\b(?:leases|service\s+contracts?|permitted\s+exceptions?|lease\s+abstracts?|"
    r"personal\s+property\s+(?:list|schedule|inventory))\b", re.IGNORECASE)
_FORM_NOUN_RE = re.compile(
    r"\b(?:deed|assignment|estoppel|bill\s+of\s+sale|notice|letter|certificate|affidavit|"
    r"memorandum|guarant(?:y|ee)|consent|snda|subordination|release|conveyance|"
    r"agreement|assumption)\b", re.IGNORECASE)
_CONTINUATION_RE = re.compile(
    r"^to\s+(?:the\s+)?(?:[a-z]+\s+){0,6}?(?:agreement|contract|psa)\b", re.IGNORECASE)
# A Form-of region ends at ANY block that opens like another exhibit / schedule
# (EXHIBIT / SCHEDULE / ANNEX / APPENDIX / ATTACHMENT / RIDER + an id, whatever
# follows: "SCHEDULE 1 Rent Roll", "Schedule 1 (Rent Roll)", "Exhibit C, Rent Roll",
# "Rider 1") or at a short block carrying a data caption ("RENT ROLL", "SCHEDULE OF
# LEASES"). Ending early fails closed: what follows is judged as data.
_HEADING_LIKE_RE = re.compile(
    r"^\s*(?:exhibit|schedule|annex|appendix|attachment|rider)\s+\S{1,8}", re.IGNORECASE)
# An inline cross-reference ("Legal Description: See Exhibit A attached hereto.")
# inside a form is a field of the form, not a new data heading: it does not end the
# Form-of region (merge-gate REFUTE C2, 2026-11-08). Shape: a short label, a colon or
# dash, then "see / described in / set forth on Exhibit|Schedule <id> attached" or
# "attached as Exhibit|Schedule <id>" -- the target is attached separately, outside
# this exhibit. "see Schedule 1 below / following / herein" points INTO the exhibit
# and still ends the region (round-2 R2: the schedule that follows is data), and so
# does a reference whose target is not an Exhibit with exactly one heading OUTSIDE
# the current exhibit (round-3 X1 / X9 and final refute: "see Schedule 1 attached"
# + a headingless schedule, an unrelated SCHEDULE 1 elsewhere, a duplicate heading).
_XREF_ID = r"[\"'\u201c\u201d]?(?P<{0}>[A-Z0-9]{{1,3}}(?:-\d+)?)[\"'\u201c\u201d]?"
_XREF_NOT_HERE = r"(?!.*\b(?:below|following|herein(?:after)?)\b)"
_INLINE_XREF_RE = re.compile(
    r"^[^:\u2013\u2014]{1,60}?\s*[:\u2013\u2014-]\s*(?:(?:see|as\s+(?:more\s+particularly\s+)?"
    r"(?:described|set\s+forth)\s+(?:in|on)|described\s+(?:in|on))\s+(?:the\s+)?"
    r"(?P<k1>exhibit|schedule)\s+" + _XREF_ID.format("i1") + r"\b" + _XREF_NOT_HERE +
    r"\s*,?\s*attached\b|attached\s+(?:hereto\s+)?as\s+(?P<k2>exhibit|schedule)\s+" +
    _XREF_ID.format("i2") + r"\b" + _XREF_NOT_HERE + r")", re.IGNORECASE)


def _xref_target(t: str):
    """(kind, id) named by an inline cross-reference line, else None."""
    m = _INLINE_XREF_RE.match(t)
    if not m:
        return None
    kind = (m.group("k1") or m.group("k2")).lower()
    return kind, (m.group("i1") or m.group("i2")).upper()


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
    if _WEAK_DATA_RE.search(c) and not _FORM_NOUN_RE.search(c):
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


def _caption_of(blocks: list, start: int, end: int):
    """(caption text, caption block) of the exhibit at heading block `start`: the
    FIRST non-blank block after the heading (spacers, page breaks, DMS stamps and a
    "to Purchase Agreement" heading continuation skipped)."""
    kind, el = blocks[start]
    if kind == "tbl":
        after = False
        for para in el.iter(W + "p"):
            pt = _joined_lines(para)
            if not after:
                after = bool(EXHIBIT_HEAD_RE.match(_text_of(para).strip()))
                continue
            if pt and not _CONTINUATION_RE.match(pt):
                return pt, start
    for j in range(start + 1, end):
        pt = _block_lead_text(*blocks[j])
        if not pt or DMS_STAMP_RE.match(pt) or _CONTINUATION_RE.match(pt):
            continue
        return pt, j
    return None, None


def _is_data_caption(c: str) -> bool:
    c = re.sub(r"\s+", " ", c.replace(" ", " "))
    return bool(_DATA_CAPTION_RE.search(c)) or bool(
        _WEAK_DATA_RE.search(c) and not _FORM_NOUN_RE.search(c))


def _form_info(blocks: list, start: int, end: int, targets=None):
    """(is_form, form_end, is_data) for the exhibit at heading block `start`:
    is it a real "Form of ..." exhibit, where its form region ends (the first
    block after the caption that opens like another exhibit / schedule or carries
    a short data caption, else `end`), and is it captioned as a data exhibit.
    `targets` maps ("exhibit", id) -> heading block indices; an inline cross-
    reference keeps the region open only if it names an Exhibit with exactly one
    heading, outside [start, end)."""
    caption, cap_j = _caption_of(blocks, start, end)
    if caption is None:
        return False, start, False
    is_data = _is_data_caption(caption)
    if not _is_form_caption(caption):
        return False, start, is_data
    for j in range(cap_j + 1, end):
        t = _block_lead_text(*blocks[j])
        if _HEADING_LIKE_RE.match(t):
            return True, j, False
        if len(t) <= 120 and _is_data_caption(t):
            # Keep the region open only for an Exhibit reference whose id has
            # EXACTLY ONE heading, outside this exhibit. A Schedule id has no
            # structural heading (an unrelated "SCHEDULE 1" can sit inside any
            # exhibit) and zero or several headings are ambiguous: both end the
            # region, fail closed (final refute, 2026-11-08).
            tgt = _xref_target(t)
            hits = (targets or {}).get(tgt, ()) if tgt and tgt[0] == "exhibit" else ()
            if not (len(hits) == 1 and not start <= hits[0] < end):
                return True, j, False
    return True, end, False


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


def _has_cue(stream: list, k: int, pos: dict, lists: dict, cue, window: int) -> bool:
    """Is a cue line within `window` non-empty lines of line k -- in the same table
    cell for a cell line, else among the exhibit's paragraph lines? O(window)."""
    key = stream[k][1]
    lst = lists[key]
    i = pos[k]
    for q in lst[max(0, i - window):i] + lst[i + 1:i + 1 + window]:
        if cue.search(stream[q][3]):
            return True
    return False


def _scan_exhibit(stream: list, form_end: int, is_form: bool, is_data: bool):
    """Classify the blanks of one post-signature exhibit. Returns three dicts
    block -> entry: form (exempt template), body (blocking) and signature.
    Context exemptions (party labels, entity lines, bare venue, a bare rule in a
    grid) are off in a data-captioned exhibit and after a form region ends."""
    lists, pos = {}, {}
    for k, (_i, cell, _m, ln) in enumerate(stream):
        if ln:
            lst = lists.setdefault(cell, [])
            pos[k] = len(lst)
            lst.append(k)
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
        strict = is_data or (is_form and i >= form_end)
        verdict = _classify_line(ln, multi)
        if verdict == "exempt" and strict and _needs_stack(ln):
            # A bare rule or weak label in a data exhibit is the missing data unless
            # it sits in a signature stack anchored by a strong cue (REFUTE C3).
            verdict = "exempt" if _in_signature_stack(stream, k, pos, lists) else "body"
        elif verdict == "party":
            verdict = "exempt" if (not strict and
                                   _has_cue(stream, k, pos, lists, _SIG_CUE_RE, 1)) else "body"
        elif verdict == "context":
            verdict = "exempt" if (not strict and
                                   _has_cue(stream, k, pos, lists, _SIG_CUE_RE, 3)) else "body"
        elif verdict == "notary":
            bare_venue = bool(_BARE_VENUE_RE.match(ln.strip()))
            ok = _has_cue(stream, k, pos, lists, _NOTARY_CUE_RE, 3)
            verdict = "exempt" if ok and not (strict and bare_venue) else "body"
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
    # Cross-reference targets: ("exhibit", id) -> heading block indices, from the
    # detected EXHIBIT headings only (round-3 X1 / X9, final refute).
    targets = {}
    for i, letter in heads:
        targets.setdefault(("exhibit", letter), []).append(i)

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
                # Underscore runs are blanks, not content: a grid of rules is EMPTY.
                if not DMS_STAMP_RE.match(tt):
                    chars += len(_BARE_RULE_RE.sub("", tt).strip())
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
            # Underscore runs are blanks, not content: an exhibit that is only a
            # rule is EMPTY, a parcel number plus a rule is THIN.
            n_chars = len(_BARE_RULE_RE.sub("", t).strip())
            chars += n_chars
            prose_chars += n_chars
        # An empty table grid (zero rows, every cell blank) is EMPTY, not populated:
        # Gabriel's ruling, 2026-11-06. A table counts only through its text/images.
        populated = bool(chars or media)
        exhibits.append({
            "letter": letter, "caption": caption, "block": start,
            "text_chars": chars, "images": media, "tables": tables,
            "data_tables": data_tables,
            "form": _form_info(blocks, start, end, targets)[0],
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
        is_form, form_end, is_data = _form_info(blocks, start, end, targets)
        f, b, g = _scan_exhibit(_exhibit_stream(blocks, start, end), form_end, is_form,
                                is_data)
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
