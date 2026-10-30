"""Fill templates/LOI_ShortForm_Template.docx from a JSON value map (loi-generation v1.15).

Usage: python fill_shortform.py <values.json> <output.docx> [template.docx]

values.json maps token names (without braces) to strings, e.g. {"PROPERTY_CITY": "Columbus", ...}.
- Every {{TOKEN}} in the template must have a key; a missing key is an error (QC #1).
- Resolved text takes the body formatting (Times New Roman, black) — the gold DM Sans styling marks
  only unresolved tokens.
- Optional terms (ZONING_TERM, PURCHASE_OPTION_TERM, TENANT_CONDITIONS_TERM): an empty value deletes the
  whole labeled paragraph. Inline optional tokens (e.g. ENTITY_INTEREST_SENTENCE) may be empty strings;
  include their leading space or punctuation in the value.
- "CONCEALMENT_OVERLAY": true (SKILL.md Rule 0c) removes the IRC §1031 cooperation sentence from Other Conditions
  and "exchange intermediaries" from Confidentiality, rewords Purchase Price's "in exchange for" to "against
  delivery of"; fill fails if "1031", "exchange" or "drop-and-swap" remains.
Requires python-docx.
"""
import json, re, sys
from pathlib import Path
from docx import Document
from docx.shared import RGBColor
from docx.oxml.ns import qn

OPTIONAL_TERMS = {"ZONING_TERM", "PURCHASE_OPTION_TERM", "TENANT_CONDITIONS_TERM"}
TOK = re.compile(r"\{\{([A-Z0-9_]+)\}\}")

vals_path, out = sys.argv[1], sys.argv[2]
tmpl = sys.argv[3] if len(sys.argv) > 3 else str(Path(__file__).with_name("LOI_ShortForm_Template.docx"))
V = json.loads(Path(vals_path).read_text(encoding="utf-8"))
CONCEAL = bool(V.pop("CONCEALMENT_OVERLAY", False))
CONCEAL_EDITS = [(" The parties will cooperate with any IRC \u00a71031 exchange at no cost to the cooperating party.", ""),
                 ("accountants, lenders, and exchange intermediaries", "accountants, and lenders"),
                 ("at Closing in exchange for free and clear title", "at Closing against delivery of free and clear title")]
doc = Document(tmpl)


def all_paragraphs(d):
    yield from d.paragraphs
    for s in d.sections:
        for part in (s.header, s.first_page_header, s.footer, s.first_page_footer):
            yield from part.paragraphs


used, missing = set(), set()
for p in list(all_paragraphs(doc)):
    names = TOK.findall(p.text)
    if not names:
        continue
    # optional labeled term: body is exactly one *_TERM token
    term_tok = [n for n in names if n in OPTIONAL_TERMS]
    if term_tok:
        n = term_tok[0]
        used.add(n)
        if n not in V:
            missing.add(n)
            continue
        if not V[n].strip():
            p._p.getparent().remove(p._p)
            continue
    for r in p.runs:
        m = TOK.fullmatch(r.text)
        if not m:
            if TOK.search(r.text):  # token sharing a run with other text — resolve in place
                r.text = TOK.sub(lambda mm: V.get(mm.group(1), mm.group(0)), r.text)
                for mm in TOK.findall(r.text):
                    missing.add(mm)
            continue
        n = m.group(1)
        used.add(n)
        if n not in V:
            missing.add(n)
            continue
        r.text = V[n]
        r.font.name = "Times New Roman"
        rpr = r._element.get_or_add_rPr()
        rpr.get_or_add_rFonts().set(qn("w:hAnsi"), "Times New Roman")
        r.font.color.rgb = RGBColor(0, 0, 0)

if missing:
    sys.exit("unresolved tokens: " + ", ".join(sorted(missing)))
if CONCEAL:
    hits = 0
    for p in doc.paragraphs:
        for r in p.runs:
            for a, b in CONCEAL_EDITS:
                if a in r.text:
                    r.text, hits = r.text.replace(a, b), hits + 1
    if hits != len(CONCEAL_EDITS):
        sys.exit(f"concealment overlay: expected {len(CONCEAL_EDITS)} edits, made {hits}")
    body = " ".join(p.text for p in doc.paragraphs)
    leaks = [w for w in ("1031", "exchange", "drop-and-swap") if w in body.lower()]
    if leaks:
        sys.exit("concealment overlay leak-check failed: " + ", ".join(leaks))
extra = set(V) - used
if extra:
    print("warning: values not used by the template:", ", ".join(sorted(extra)))
doc.core_properties.title = V.get("PROPERTY_STREET_ADDRESS", "") + " LOI"
doc.save(out)
print("saved", out)
