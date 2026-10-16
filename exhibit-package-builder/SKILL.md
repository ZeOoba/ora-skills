---
name: "exhibit-package-builder"
description: "Build a signature-ready Combined PDF: front instrument + exhibit contents sheet + every source instrument complete, stamped Exhibit A-n of N, verified page-by-page against source."
---

# Exhibit Package Builder

Builds the "Combined PDF" that goes out for signature: the instrument being signed, followed by an exhibit that reproduces each underlying instrument (lease, amendments, guaranty, plans) complete and unaltered. Each exhibit page is stamped so a returned scan identifies itself page by page. Proven on 754 Old State Route 74 (Estoppel V3 Combined, 754C 28 pp / 754B 18 pp, 10/15/2026).

**Use for:** estoppel Exhibit A, SNDA / consent / amendment exhibits, lender or title deliverables that must attach "true and complete copies". **Not for:** drafting the front instrument itself (estoppels → estoppel-request-generation; amendments → lease-addendum; LOIs → loi-generation).

## Inputs

1. **Front instrument PDF.** Always regenerate it from the current .docx first. Never reuse an older Combined PDF's front pages; that is how a stale wording variant got into the 754B package.
2. **Source instruments.** Use the executed scans, in date order. Read the page images, not the OCR, to confirm each one is complete (signature pages, initials, exhibits).
3. **Exhibit scope decision.** If a later instrument attaches and ratifies a copy of an earlier one (e.g. a Reaffirmation whose Exhibit 1 is the lease), reproduce the earlier instrument **once**, through the ratified copy, and say so in `note`. Do not attach a second, different scan of the same lease.

## Procedure

1. Regenerate the front PDF from the current .docx (LibreOffice: `soffice.py --headless --convert-to pdf`).
2. Write `config.json` (schema in the script docstring). Write `desc` lines as they would appear in a recital: instrument name, effective date, any qualifier. Use `within` to point to sub-parts the certificate refers to (e.g. "its Exhibit 1 cover sheet").
3. Save the script below as `build_exhibit_package.py` in a scratch directory (not in the deal folder) and run `python3 build_exhibit_package.py config.json`.
4. The script verifies automatically. It exits non-zero on any FAIL. It checks:
   - the page count is front + 1 + exhibit total;
   - the front pages' text matches the front PDF;
   - every stamp reads correctly;
   - every exhibit page's image fingerprint matches its source page (stamp band masked; threshold 0.01; tested to catch reordered instruments).
5. Visually check the contents sheet and at least one stamped page from each source. Render them to PNG and Read them, particularly any scan stored with `/Rotate`.
6. Deliver with the deal-file naming. Never overwrite a prior version; move superseded files to `/archive/`.

## Known traps (each one hit in practice)

- **Base-14 fonts render em dashes and curly quotes as "?".** The script embeds Liberation Serif. Keep it.
- **Rotated scans.** Pages with `/Rotate 270` take the stamp in unrotated space, so it ends up invisible or sideways. The script maps the point through `page.derotation_matrix` and passes `rotate=page.rotation`.
- **Text checks on extracted PDF text must normalize whitespace** (`" ".join(t.split())`). Otherwise line breaks produce false FAILs.
- **Contents sheet is one page.** The script stops if it overflows; shorten the `desc` text rather than adding a page.
- **Exhibit pages are image-only scans.** They carry no text layer. Flag this in the cover note if a recipient requires searchable exhibits; the front instrument and contents sheet do carry text.
- **Size.** Scans push packages past 10 MB (754C: 14.3 MB). The device commit limit is 20 MB per file. Above that, deliver through SendUserFile only and say so.

## Script

```python
# -*- coding: utf-8 -*-
"""Build a signature package: [front instrument PDF] + [exhibit contents sheet] +
[each source instrument, complete and unaltered, page-stamped "Exhibit X · X-n of N"].

Usage:  python3 build_exhibit_package.py config.json
        python3 build_exhibit_package.py config.json --verify-only

Config (JSON):
{
  "front": "Estoppel V3.pdf",                  # instrument the exhibit attaches to
  "out": "Estoppel V3 Combined.pdf",
  "letter": "A",                                # exhibit letter
  "caption": "to Tenant Estoppel Certificate — Suite 754B",
  "subcaption": "754 Old State Route 74, Cincinnati, Ohio 45245",   # optional
  "intro": "The Lease ... consists of the following instruments, each reproduced complete and as executed:",
  "items": [
    {"path": "Lease.pdf", "desc": "Commercial Lease Agreement dated April 8, 2025"},
    {"path": "Amendment 2.pdf", "desc": "Second Amendment ...",
     "within": [{"from": 5, "to": 5,  "text": "its Exhibit 1 cover sheet"},
                {"from": 6, "to": null, "text": "the lease copy the parties ratified"}]}
  ],
  "note": "optional italic note at the foot of the contents sheet",
  "title": "PDF metadata title", "author": "Oxford Realty Advisors", "subject": "..."
}
"within" page numbers are 1-based pages of THAT source file; "to": null = its last page.
"""
import json
import sys

import fitz  # PyMuPDF

LIB = "/usr/share/fonts/truetype/liberation/"
FONTS = {"lsr": LIB + "LiberationSerif-Regular.ttf",
         "lsb": LIB + "LiberationSerif-Bold.ttf",
         "lsi": LIB + "LiberationSerif-Italic.ttf"}
REG, BOLD, ITAL = "lsr", "lsb", "lsi"


def fonts_on(page):
    # Embedded TTF: base-14 fonts lack em dashes / curly quotes and render "?".
    for name, path in FONTS.items():
        page.insert_font(fontname=name, fontfile=path)


def stamp(page, label, size=8):
    """Top-right of the page AS DISPLAYED. Scans are often stored landscape with
    /Rotate set; map the visible point back to unrotated space and rotate the text
    with the page so it reads upright."""
    fonts_on(page)
    w = fitz.Font(fontfile=FONTS[REG]).text_length(label, fontsize=size)
    pt = fitz.Point(page.rect.width - 36 - w, 24) * page.derotation_matrix
    page.insert_text(pt, label, fontname=REG, fontsize=size,
                     color=(0.25, 0.25, 0.25), rotate=page.rotation)


def contents_sheet(doc, cfg, ranges, counts):
    page = doc.new_page(width=612, height=792)
    fonts_on(page)
    y = [96]
    L = cfg.get("letter", "A")

    def line(text, font=REG, size=12, gap=8, center=False, indent=0):
        rect = fitz.Rect(72 + indent, y[0], 540, y[0] + 400)
        align = fitz.TEXT_ALIGN_CENTER if center else fitz.TEXT_ALIGN_LEFT
        scratch = fitz.open().new_page(width=612, height=792)   # measure height
        fonts_on(scratch)
        rc = scratch.insert_textbox(rect, text, fontname=font, fontsize=size, align=align)
        if rc < 0:
            raise SystemExit("contents sheet overflow: shorten descriptions")
        page.insert_textbox(rect, text, fontname=font, fontsize=size, align=align)
        y[0] += (400 - rc) + gap
        if y[0] > 740:
            raise SystemExit("contents sheet runs past one page: shorten text")

    line(f"EXHIBIT {L}", BOLD, 14, 4, center=True)
    line(cfg["caption"], ITAL, 11, 2 if cfg.get("subcaption") else 22, center=True)
    if cfg.get("subcaption"):
        line(cfg["subcaption"], ITAL, 11, 22, center=True)
    line(cfg["intro"], REG, 12, 14)
    for n, (item, (a, b), cnt) in enumerate(zip(cfg["items"], ranges, counts), 1):
        line(f"{n}.   {item['desc']} — pages {L}-{a} to {L}-{b}.", REG, 12, 4, indent=18)
        parts = []
        for w in item.get("within", []):
            f, t = w["from"], (w["to"] or cnt)
            pa, pb = a + f - 1, a + t - 1
            rng = f"{L}-{pa}" if pa == pb else f"{L}-{pa} to {L}-{pb}"
            parts.append(f"{w['text']} at page{'s' if pa != pb else ''} {rng}")
        if parts:
            line("Within it: " + "; ".join(parts) + ".", REG, 11, 10, indent=40)
    if cfg.get("note"):
        y[0] += 8
        line(cfg["note"], ITAL, 11, 8)


def build(cfg):
    srcs = [fitz.open(i["path"]) for i in cfg["items"]]
    counts = [s.page_count for s in srcs]
    ranges, n = [], 1
    for c in counts:
        ranges.append((n, n + c - 1))
        n += c
    total = n - 1
    L = cfg.get("letter", "A")

    out = fitz.open()
    out.insert_pdf(fitz.open(cfg["front"]))
    front_pages = out.page_count
    contents_sheet(out, cfg, ranges, counts)
    k = 1
    for s in srcs:
        start = out.page_count
        out.insert_pdf(s)
        for i in range(start, out.page_count):
            stamp(out[i], f"Exhibit {L} · {L}-{k} of {total}")
            k += 1
    out.set_metadata({"title": cfg.get("title", ""),
                      "author": cfg.get("author", "Oxford Realty Advisors"),
                      "subject": cfg.get("subject", "")})
    out.save(cfg["out"], garbage=3, deflate=True)
    print(f"built {cfg['out']}: front {front_pages} + contents 1 + Exhibit {L} "
          f"{total} = {out.page_count} pp")


def _fp(page, w=60):
    """Low-res grayscale fingerprint of the displayed page, stamp band masked."""
    z = w / page.rect.width
    pix = page.get_pixmap(matrix=fitz.Matrix(z, z), colorspace=fitz.csGRAY)
    s = pix.samples
    band = max(1, int(pix.height * 0.06))       # top 6% holds the stamp
    return [0 if r < band else s[r * pix.stride + c]
            for r in range(pix.height) for c in range(pix.width)], (pix.width, pix.height)


def verify(cfg):
    out = fitz.open(cfg["out"])
    front = fitz.open(cfg["front"])
    srcs = [fitz.open(i["path"]) for i in cfg["items"]]
    total = sum(s.page_count for s in srcs)
    L = cfg.get("letter", "A")
    fails = []
    exp = front.page_count + 1 + total
    if out.page_count != exp:
        fails.append(f"page count {out.page_count} != {exp}")
    norm = lambda t: " ".join(t.split())
    for i in range(front.page_count):
        if norm(out[i].get_text()) != norm(front[i].get_text()):
            fails.append(f"front page {i+1} text differs from source")
    k, worst = 1, 0.0
    for s in srcs:
        for j in range(s.page_count):
            p = out[front.page_count + k]
            label = f"Exhibit {L} · {L}-{k} of {total}"
            if label not in norm(p.get_text()):
                fails.append(f"stamp missing/wrong on {L}-{k}")
            a, da = _fp(p)
            b, db = _fp(s[j])
            if da != db:
                fails.append(f"{L}-{k} geometry differs from source")
            else:
                d = sum(abs(x - y) for x, y in zip(a, b)) / (255.0 * len(a))
                worst = max(worst, d)
                if d > 0.01:
                    fails.append(f"{L}-{k} content differs from source page (diff {d:.3f})")
            k += 1
    fitz_fonts = {f[3] for pg in out for f in pg.get_fonts()}
    print(f"verify {cfg['out']}: {out.page_count} pp, worst exhibit diff {worst:.3f}, "
          f"fonts {sorted(fitz_fonts)[:6]}")
    for f in fails:
        print("FAIL", f)
    if not fails:
        print("PASS all checks")
    return not fails


if __name__ == "__main__":
    cfg = json.load(open(sys.argv[1], encoding="utf-8"))
    if "--verify-only" not in sys.argv:
        build(cfg)
    sys.exit(0 if verify(cfg) else 1)
```