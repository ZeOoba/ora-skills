---
name: "artifact-to-docx-report"
description: "Turn a published Claude artifact (dashboard or review page with embedded data) into an ORA-styled Word report with charts, KPI tiles and an action plan. Use when Gabriel gives a claude.ai/artifact link and asks for a Word document, report or board-ready write-up built from it."
---

# Artifact to Word report

Use when Gabriel gives a claude.ai/artifact link (for example Property Financials Review) and asks for a professional, visual Word document. Word is explicit here, so build a .docx, not a Docs artifact. Code lives beside this file: `scripts/`, `lib/`, `examples/property_financials/`; `README.md` has the layout and the adapt-to-a-new-artifact steps.

## Pipeline

1. **Read the artifact in full.** `Artifact action:read url:<link>` returns only the first ~16K characters. Call it again with `path: index.html` to save the whole page locally.
2. **Extract the data.** `python3 -I scripts/extract_artifact_data.py index.html data.json` pulls the `<script type="application/json" id="data">` payload and prints the schema. Read every insight, lease, data-quality note and table before designing anything.
3. **Compute, never retype.** Derive totals, percentages and deltas in code from the raw periods. Do not reuse the artifact's pre-rounded `pct` fields (0.08 vs 7.9%); compute `current/prior - 1` (`chg()` in `lib/docx_helpers.js`). Check ratios against their stated definition (reimbursements / pool = recovery ratio).
4. **Charts.** `lib/ora_chart_style.py` carries the palette (Navy 1B2A4A, Gold C9A96E, Red A62525, Green 1B7A4B), rcParams and `$K` formatters. White background, no top/right spines, value labels on bars, a reference line where a governor or threshold exists (40% LTV, 1.25x DSCR, 100% recovery). Write each image's pixel size to `dims.json` so docx sizing keeps the aspect ratio. Truncated axes (waterfall) need a caption saying where the axis starts.
5. **Build with docx-js.** Read `/mnt/skills/public/docx/SKILL.md` first. `lib/docx_helpers.js` exports `H1/H2/H3`, `lede`, `bullet`, `table`, `tiles`, `callout`, `img`, `cap`, the palette and formatters; call `init(chartsDir)` before `img()`. US Letter, content width 9720 DXA. Fonts: EB Garamond headings, DM Sans body.
6. **Structure that worked:** Cover, Executive summary (lede, KPI tiles, five findings, bottom-line callout), Portfolio performance, Asset scorecard, Value-creation levers, Lease rollover and rent upside, Capital structure and risk watch, 90-day action plan, Appendix (findings register, data-quality notes, sources).
7. **Render and look.** `bash scripts/render_check.sh out.docx` renders to PDF, builds contact sheets and runs the XSD validator. Read the sheets. Fix orphaned callouts (shrink the preceding figure to 500-540 px), tables split across pages (give the H2 `pageBreakBefore`), and headings stranded at page bottoms.
8. **Deliver** with SendUserFile. Name per the session-output schema: `YYYY-MM-DD_[Topic]_Report_v##.docx`. Close with two or three sentences of findings and one next step.

One command for the whole chain: `bash scripts/run_pipeline.sh index.html examples/<name> out.docx`.

## Accuracy rules

- Keep the artifact's evidence-basis tags (ACTUAL, ESTIMATE, SENSITIVITY, SPECULATIVE, upper bound) on every dollar figure and say that mixed bases are not additive. Capitalized-value figures use an illustrative cap rate and are tagged [FORECAST].
- Leasable SF = total SF minus common-area SF (Broadway 500, Northwood 400). Do not back into SF from a rounded occupancy percentage.
- Treat insurance-tracker statuses as tracker data that may lag renewals; phrase as verify, not as lapsed.
- Respect cash-basis timing: flag tax, insurance and snow swings as possible timing before presenting them as run-rate.
- Label the report internal. Do not name active confidential deals; check the roster first if any appear in the data.
- Do not state market claims (current rates, today's pricing) that are not in the source; tag them [FORECAST] or omit them.

## Pitfalls

- Use `ShadingType.CLEAR`, never SOLID. Do not use tables as rules. `PageBreak` only inside a Paragraph.
- A `keepNext` figure with its caption can jump a whole page; budget about 3 inches of vertical space for a 500 px wide chart.
- Fonts may be absent in the render environment, and Word can shift the page count by one; leave slack at page bottoms.
