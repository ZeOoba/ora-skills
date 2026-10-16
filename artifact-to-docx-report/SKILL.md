---
name: "artifact-to-docx-report"
description: "Turn a published Claude artifact (dashboard or review page with embedded data) into an ORA-styled Word report with charts, KPI tiles and an action plan."
---

# Artifact to Word report

Use when Gabriel gives a claude.ai/artifact link (e.g. Property Financials Review) and asks for a professional, visual Word document. Word is explicit here, so build a .docx, not a Docs artifact.

## Pipeline

1. **Read the artifact in full.** `Artifact action:read url:<link>` returns only the first ~16K characters. Call it again with `path: index.html` to save the whole page locally.
2. **Extract the data.** Dashboards embed their data as `<script type="application/json" id="data">`. Pull it with a regex and `json.loads` (run Python with `-I`), dump to `data.json`, then print the top-level keys and one sample record per structure before designing anything. Read every insight, lease, data-quality note and table the page carries.
3. **Compute, never retype.** Derive totals, percentages and deltas in code from the raw periods. Do not reuse the artifact's pre-rounded `pct` fields (0.08 vs 7.9%); compute `current/prior - 1`. Check ratios against their stated definition (for example reimbursements / pool = recovery ratio).
4. **Charts (matplotlib, PNG at 200 dpi).** Palette: Navy 1B2A4A, Gold C9A96E, Parchment F5F3EF, Red A62525, Green 1B7A4B. White background, no top/right spines, value labels on bars, a reference line where a governor or threshold exists (40% LTV, 1.25x DSCR, 100% recovery). Typical set: NOI by asset, NOI bridge (waterfall), expense change by category, recovery ratio, occupancy, lease expiry ladder, dollar impact by finding, debt LTV and DSCR, quarterly trend. Write each image's pixel size to `dims.json` so docx sizing keeps the aspect ratio. Truncated axes (waterfall) need a caption saying where the axis starts.
5. **Build with docx-js** (`require('docx')`, preinstalled; read `/mnt/skills/public/docx/SKILL.md` first). US Letter, content width 9720 DXA, margins 1260. Fonts: EB Garamond headings, DM Sans body. Helpers to write once: `H1` (pageBreakBefore, gold bottom border), `H2`, `lede`, `bullet` (numbering config, never literal bullets), `table` (navy header row, zebra rows, dual column widths, cantSplit rows, repeat header), `tiles` (KPI cells with colored top border), `callout` (parchment single cell with gold left border), `img` (ImageRun with `type:'png'`), `cap` (italic caption). Cover is a full-width navy table cell with a gold bottom border; use `titlePage:true` with empty first header and footer.
6. **Structure that worked:** Cover, Executive summary (lede, 8 KPI tiles, five findings, bottom-line callout), Portfolio performance, Asset scorecard, Value-creation levers (impact chart plus one table per lever), Lease rollover and rent upside, Capital structure and risk watch, 90-day action plan, Appendix (findings register, data-quality and method notes, sources).
7. **Render and look.** `python /mnt/skills/public/docx/scripts/office/soffice.py --headless --convert-to pdf`, `pdftoppm -jpeg -r 55`, tile pages into contact sheets and Read them. Then run `scripts/office/validate.py` on the docx. Fix: orphaned callouts (shrink the preceding figure to 500-540 px), tables split across pages (move the H2 to its own page with `pageBreakBefore`), and headings stranded at page bottoms.
8. **Deliver** with SendUserFile (`display:'attach'`). Name per the session-output schema: `YYYY-MM-DD_[Topic]_Report_v##.docx`. Finish with two or three sentences of findings and one next step; do not recap the steps.

## Accuracy rules

- Keep the artifact's evidence-basis tags (ACTUAL, ESTIMATE, SENSITIVITY, SPECULATIVE, upper bound) on every dollar figure and say that mixed bases are not additive. Capitalized-value figures use an illustrative cap rate and are tagged [FORECAST].
- Leasable SF = total SF minus common-area SF (Broadway 500, Northwood 400). Do not back into SF from a rounded occupancy percentage.
- Treat insurance-tracker statuses as tracker data that may lag renewals; phrase as verify, not as lapsed.
- Respect cash-basis timing: flag tax, insurance and snow swings as possible timing before presenting them as run-rate.
- Label the report internal. Do not name active confidential deals; check the roster first if any are in the data.
- Do not state market claims (current rates, today's pricing) that are not in the source; tag them [FORECAST] or omit them.

## Pitfalls

- Use `ShadingType.CLEAR`, never SOLID. Do not use tables as rules. `PageBreak` only inside a Paragraph.
- A figure that is `keepNext` with a caption can jump a whole page; budget about 3 inches of vertical space for a 500 px wide chart.
- Fonts may be absent in the render environment; the page count can shift slightly in Word, so leave slack at page bottoms.