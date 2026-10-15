# artifact-to-docx-report

Turns a published Claude artifact (a dashboard or review page with an embedded JSON dataset) into an ORA-styled Word report with charts, KPI tiles, callouts and an action plan. Companion to the `artifact-to-docx-report` skill, which carries the procedure and accuracy rules.

## Layout

| Path | Purpose |
|---|---|
| `lib/docx_helpers.js` | Reusable docx-js building blocks: `H1/H2/H3`, `lede`, `bullet`, `table` (navy header, zebra, dual widths, cantSplit), `tiles` (KPI row), `callout`, `img`, `cap`, ORA palette and `$k/$m/pc/sg/chg` formatters. Call `init(chartsDir)` first. |
| `lib/ora_chart_style.py` | matplotlib palette, rcParams, `$K` / `$M` axis formatters, `make_save(outDir)`. |
| `scripts/extract_artifact_data.py` | Pull `<script type="application/json" id="data">` out of the saved page, write `data.json`, print the schema. |
| `scripts/render_check.sh` | docx to PDF, page images, contact sheets, XSD validation. |
| `scripts/run_pipeline.sh` | Whole chain in one command. |
| `examples/property_financials/` | The report built from the Property Financials Review artifact: `charts.py` (10 charts plus `stats.json`, `dims.json`) and `make.js` (16-page document). |

## Run the example

```bash
# 1. Save the full page locally (the plain read truncates at ~16K chars):
#    Artifact action:read url:<link> path:index.html
bash scripts/run_pipeline.sh /path/to/index.html examples/property_financials ./2026-10-05_Property-Financials-Review_Report_v01.docx
```

Requirements: Python 3 with matplotlib and pillow, Node with `docx`, LibreOffice, poppler (`pdftoppm`). The render step expects the docx skill's validator at `/mnt/skills/public/docx/scripts/office/`.

## Make a new report from a different artifact

1. `python3 -I scripts/extract_artifact_data.py index.html data.json` and read the printed schema.
2. Copy `examples/property_financials` to `examples/<name>`.
3. In `charts.py`, rewrite the chart blocks for the new data. Keep writing `stats.json` (numbers the document quotes) and `dims.json` (pixel sizes, so images keep their aspect ratio).
4. In `make.js`, rewrite the sections. Compute every figure in code from `data.json`; never retype numbers or reuse pre-rounded percentages.
5. `bash scripts/run_pipeline.sh index.html examples/<name> out.docx`, then Read the contact sheets and fix pagination.

## Data-specific code in the example

`charts.py` and `make.js` assume the property-review schema: `props`, `cube`, `sf`, `xt.debt`, `xt.tenants`, `insights`, `portfolio`. Only the example reads those keys; `lib/` and `scripts/` are schema-free.

## Known sharp edges

- Hard-coded in the example: Northwood common area of 400 SF (leasable SF net of common area) and an illustrative 7% cap rate tagged [FORECAST]. Change both if the data or house view changes.
- Fonts (EB Garamond, DM Sans) fall back when not installed; page count can shift a page in Word.
- Insurance statuses come from a tracker and may lag renewals; the report words them as verify, not as lapsed.
