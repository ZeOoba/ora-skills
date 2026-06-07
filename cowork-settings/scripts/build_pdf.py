#!/usr/bin/env python3
"""
build_pdf.py — produce a brand-styled ORA Cowork Global Settings PDF from a
versioned markdown file.

Usage:
    python build_pdf.py <settings_version.md> [--out OUTPUT.pdf]

Design:
    Reads the fenced settings block + the rationale markdown, renders to PDF
    with EB Garamond / DM Sans / IBM Plex Mono, Oxford Navy masthead, Gold
    hairline, Parchment settings panel, extractable text layer. Fonts are
    fetched from Google Fonts on first run and cached under ./fonts/.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.platypus import (
    BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    Preformatted, PageBreak, Table, TableStyle
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- Brand tokens (ORA Style Guide v1.0) ---
OXFORD_NAVY = HexColor("#1B2A4A")
GOLD        = HexColor("#C9A96E")
PARCHMENT   = HexColor("#F5F3EF")
INK         = HexColor("#1A1A1A")
MUTED       = HexColor("#5A5A5A")
HAIRLINE    = HexColor("#D4CFC4")

FONT_URLS = {
    "EBGaramond-Regular.ttf":
        "https://github.com/google/fonts/raw/main/ofl/ebgaramond/EBGaramond%5Bwght%5D.ttf",
    "EBGaramond-Italic.ttf":
        "https://github.com/google/fonts/raw/main/ofl/ebgaramond/EBGaramond-Italic%5Bwght%5D.ttf",
    "DMSans-Regular.ttf":
        "https://github.com/google/fonts/raw/main/ofl/dmsans/DMSans%5Bopsz%2Cwght%5D.ttf",
    "IBMPlexMono-Regular.ttf":
        "https://github.com/google/fonts/raw/main/ofl/ibmplexmono/IBMPlexMono-Regular.ttf",
}


def ensure_fonts(font_dir: Path) -> None:
    font_dir.mkdir(parents=True, exist_ok=True)
    for name, url in FONT_URLS.items():
        p = font_dir / name
        if not p.exists():
            subprocess.check_call(["curl", "-sL", "-o", str(p), url])
    pdfmetrics.registerFont(TTFont("EBGaramond",    str(font_dir / "EBGaramond-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("EBGaramond-It", str(font_dir / "EBGaramond-Italic.ttf")))
    pdfmetrics.registerFont(TTFont("DMSans",        str(font_dir / "DMSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont("PlexMono",      str(font_dir / "IBMPlexMono-Regular.ttf")))


def parse_markdown(md_path: Path) -> dict:
    """Extract governance metadata + the fenced settings block."""
    text = md_path.read_text(encoding="utf-8")
    meta = {}
    meta["version"] = (re.search(r"\*\*Version:\*\*\s*(\S+)", text) or [None, "?"])[1]
    meta["effective"] = (re.search(r"\*\*Effective Date:\*\*\s*(.+)", text) or [None, "?"])[1].strip()
    meta["owner"] = (re.search(r"\*\*Owner:\*\*\s*(.+)", text) or [None, "?"])[1].strip()
    meta["review"] = (re.search(r"\*\*Review Cadence:\*\*\s*(.+)", text) or [None, "?"])[1].strip()
    meta["supersedes"] = (re.search(r"\*\*Supersedes:\*\*\s*(.+)", text) or [None, "?"])[1].strip()

    block_m = re.search(r"```\n(# IDENTITY.*?)\n```", text, re.DOTALL)
    meta["settings_block"] = block_m.group(1) if block_m else ""
    return meta


def build_styles():
    return dict(
        h1=ParagraphStyle("H1", fontName="DMSans", fontSize=20, leading=24,
                          textColor=OXFORD_NAVY, spaceAfter=4),
        h2=ParagraphStyle("H2", fontName="DMSans", fontSize=12, leading=16,
                          textColor=OXFORD_NAVY, spaceBefore=16, spaceAfter=6),
        meta=ParagraphStyle("Meta", fontName="DMSans", fontSize=8.5,
                            leading=12, textColor=MUTED),
        body=ParagraphStyle("Body", fontName="EBGaramond", fontSize=10.5,
                            leading=15, textColor=INK, spaceAfter=6),
        code=ParagraphStyle("Code", fontName="PlexMono", fontSize=7.8,
                            leading=10.5, textColor=INK, leftIndent=8,
                            rightIndent=8, spaceBefore=4, spaceAfter=4,
                            backColor=PARCHMENT, borderPadding=(6,6,6,6)),
        foot=ParagraphStyle("Foot", fontName="DMSans", fontSize=7.5,
                            leading=10, textColor=MUTED),
    )


def make_page_decorator(version: str, effective: str):
    def draw(canvas, doc):
        canvas.saveState()
        w, h = LETTER
        canvas.setStrokeColor(GOLD)
        canvas.setLineWidth(1.2)
        canvas.line(0.75*inch, h - 0.45*inch, w - 0.75*inch, h - 0.45*inch)
        canvas.setFont("DMSans", 8.5)
        canvas.setFillColor(OXFORD_NAVY)
        canvas.drawString(0.75*inch, h - 0.32*inch, "OXFORD REALTY ADVISORS")
        canvas.setFillColor(MUTED)
        canvas.drawRightString(
            w - 0.75*inch, h - 0.32*inch,
            f"Claude Cowork Global Settings  ·  v{version}  ·  {effective}")
        canvas.setStrokeColor(HAIRLINE)
        canvas.setLineWidth(0.5)
        canvas.line(0.75*inch, 0.55*inch, w - 0.75*inch, 0.55*inch)
        canvas.setFont("DMSans", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(0.75*inch, 0.38*inch,
                          "CONFIDENTIAL — Internal Governance Document")
        canvas.drawRightString(w - 0.75*inch, 0.38*inch, f"Page {doc.page}")
        canvas.restoreState()
    return draw


def build_pdf(md_path: Path, out_path: Path, font_dir: Path) -> None:
    ensure_fonts(font_dir)
    meta = parse_markdown(md_path)
    styles = build_styles()

    doc = BaseDocTemplate(
        str(out_path), pagesize=LETTER,
        leftMargin=0.85*inch, rightMargin=0.85*inch,
        topMargin=0.75*inch, bottomMargin=0.75*inch,
        title=f"ORA Claude Cowork Global Settings v{meta['version']}",
        author=meta.get("owner", "Oxford Realty Advisors"),
        subject="Internal governance — Claude Cowork preferences",
        creator="Oxford Realty Advisors")
    frame = Frame(doc.leftMargin, doc.bottomMargin,
                  doc.width, doc.height, id="main",
                  leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(
        id="default", frames=[frame],
        onPage=make_page_decorator(meta["version"], meta["effective"]))])

    story = []
    story.append(Spacer(1, 0.15*inch))
    story.append(Paragraph("Claude Cowork Global Settings", styles["h1"]))
    story.append(Paragraph(
        "Oxford Realty Advisors — Internal Governance Document", styles["meta"]))
    story.append(Spacer(1, 0.05*inch))

    meta_rows = [
        ["Version",    meta["version"]],
        ["Effective",  meta["effective"]],
        ["Owner",      meta["owner"]],
        ["Review",     meta["review"]],
        ["Supersedes", meta["supersedes"]],
    ]
    meta_tbl = Table(
        [[Paragraph(f"<b>{k}</b>", styles["meta"]),
          Paragraph(v, styles["body"])] for k, v in meta_rows],
        colWidths=[1.1*inch, 5.5*inch])
    meta_tbl.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "TOP"),
        ("LEFTPADDING", (0,0), (-1,-1), 0),
        ("RIGHTPADDING", (0,0), (-1,-1), 4),
        ("TOPPADDING", (0,0), (-1,-1), 2),
        ("BOTTOMPADDING", (0,0), (-1,-1), 2),
    ]))
    story.append(meta_tbl)
    story.append(Spacer(1, 0.15*inch))

    divider = Table([[""]], colWidths=[6.8*inch], rowHeights=[1.2])
    divider.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,-1), GOLD)]))
    story.append(divider)
    story.append(Spacer(1, 0.15*inch))

    story.append(Paragraph("Settings Block", styles["h2"]))
    story.append(Paragraph(
        "Paste the block below into Cowork → Settings → User Preferences, "
        "replacing the current block in full.", styles["body"]))

    for section in meta["settings_block"].split("\n\n"):
        story.append(Preformatted(section, styles["code"]))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph(
        f"File: {out_path.name}  ·  Generated by cowork-settings skill",
        styles["foot"]))
    doc.build(story)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("markdown")
    p.add_argument("--out", default=None)
    p.add_argument("--font-dir", default="fonts")
    args = p.parse_args()

    md_path = Path(args.markdown).resolve()
    out_path = Path(args.out) if args.out else md_path.with_suffix(".pdf")
    build_pdf(md_path, out_path, Path(args.font_dir).resolve())
    print(f"Built: {out_path}")


if __name__ == "__main__":
    main()
