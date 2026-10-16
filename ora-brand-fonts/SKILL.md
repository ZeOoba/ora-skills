---
name: "ora-brand-fonts"
description: "Install ORA brand fonts (EB Garamond, DM Sans, IBM Plex Mono) before rendering any DOCX/XLSX/PPTX to PDF, so institutional PDFs embed brand fonts instead of fallbacks. Use before any PDF conversion, or when pdffonts shows DejaVu/Liberation."
---

# ORA Brand Fonts

The ORA Institutional Style Guide sets EB Garamond (body), DM Sans (headings) and IBM Plex Mono (tables/metadata). Cloud Cowork containers ship with none of them, so LibreOffice silently substitutes DejaVu and every PDF fails the style guide while looking fine to the eye. Verified 2026-09-29: before this step `fc-list` returned 0 brand faces; after it, the IC memo PDF embedded DMSans-Bold, EBGaramond-Regular/Bold and IBMPlexMono-Regular.

## When

- **Before the first `soffice --convert-to pdf`** (or docx2pdf / any LibreOffice render) in a session. Install once per session; the container does not keep fonts between sessions.
- Whenever a rendered PDF's `pdffonts` output lists DejaVu, Liberation or another fallback for a brand face.

## Install (Linux / cloud container)

All three are SIL Open Font License faces served by Google Fonts. The CSS API returns direct TTF links when called with a non-browser user agent (github.com raw URLs return 403 through the sandbox proxy; fonts.googleapis.com and fonts.gstatic.com work).

```bash
mkdir -p ~/.fonts
curl -sS -A "curl/8" "https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=DM+Sans:wght@400;500;700&family=IBM+Plex+Mono:wght@400;700" \
  | grep -o 'https://fonts.gstatic.com[^)]*' > /tmp/ora_font_urls.txt
i=0; while read -r u; do i=$((i+1)); curl -sS -o ~/.fonts/ora_brand_$i.ttf "$u"; done < /tmp/ora_font_urls.txt
fc-cache -f >/dev/null
fc-list | grep -i -E 'EB Garamond|DM Sans|IBM Plex Mono' | wc -l   # expect >= 8
```

If the network step fails, say so in the deliverable note and do NOT present the PDF as style-guide compliant.

## Windows (Claude Code on the laptop)

Check `C:\Windows\Fonts` and `%LOCALAPPDATA%\Microsoft\Windows\Fonts` for the three families. If any is missing, download the same TTFs and install per-user; Word and LibreOffice both pick them up after restart.

## Verify (part of the QC Gate for any PDF)

```bash
pdffonts <file>.pdf | tail -n +3 | awk '{print $1}' | sort -u
```

Pass = every face is an EBGaramond / DMSans / IBMPlexMono subset (OpenSymbol for bullets is fine). Any DejaVu / Liberation face = FAIL: install, re-render, re-check. Also confirm the text layer with `pdftotext` (Microsoft Print to PDF stays prohibited).

## Notes

- Rendering changes fonts only; it does not change content. A re-rendered PDF keeps its version number; move the fallback-font copy to `archive/` rather than deleting it.
- This skill installs fonts. Typographic rules (which face where, sizes, colors) live in the ORA Institutional Style Guide.