---
name: insurance-renewal-review
description: "Oxford Realty Advisors property insurance renewal review — OCR scanned Erie/Selective declarations, build a per-property premium history, diff each renewal against the prior term, and flag coverage reductions, rate-only increases, and data gaps. Use when the user says: review insurance policies, insurance renewal review, how has insurance changed, premium history, shop our insurance, self-insure, insurance declarations, coverage changes, deductible options, or points at a folder of insurance PDFs/declarations. Also trigger when a folder contains scanned Erie/Selective/carrier declaration PDFs and the user asks for trends, comparisons, or a renewal decision. v1.1 (2026-08-15: split Steps 2-3 into references/, no procedural change; fixed a duplicate stacked frontmatter block — see Changelog)."
---

# Insurance Renewal Review (ORA) — v1.1

Codifies the extraction/compare/flag pass built 2026-08-13 reviewing "Insurance Policies Historical + Current" (5 property folders, 25 PDFs, 1 broker .msg, 3 tracking XLSX — every PDF a scanned image with no text layer).

## Trigger phrases
"review insurance policies", "insurance renewal review", "how has insurance changed", "premium history", "shop our insurance", "should we self-insure", "insurance declarations", "coverage changes", "deductible options" — or the user points at a folder of insurance PDFs/declarations and asks for trends, comparisons, or a renewal decision.

## Step 1 — Inventory and triage every file

- `find <folder> -type f` for a full inventory; one subfolder per property is the ORA convention.
- Run `pdftotext -layout` on every PDF first. ORA's carrier (Erie Insurance) and its agency (Foundation Insurance Group) deliver 100% Microsoft-Print-to-PDF scans with zero text layer — `pdftotext` will return only page-break bytes. Confirm this per-file (`wc -c` on the output) before assuming OCR is needed; do not skip the check.
- `md5sum` every PDF up front. Duplicate/renamed files are common (found: a byte-identical "#2" file misnamed as a second policy). Report duplicates explicitly — never silently treat them as two documents.
- Check for `.msg` attachments — brokers forward missing endorsements this way. Extract with `extract-msg` (pip, `--break-system-packages`); list sender, date, subject, body, and every attachment; extract and read PDF attachments too. A `.msg` in the folder is often the ONLY place a mid-term amendment or endorsement lives — do not skip it because it isn't a PDF.

## Step 2 — OCR ladder (for scanned/image-only PDFs)

Full technical ladder (render dpi, tesseract vs. vision read, the mandatory ≥400 dpi re-render/confirm rule for dollar figures, and the 2-core/250-page timeout workaround): `references/ocr-and-extraction-checklist.md` § Step 2.

## Step 3 — Per-document extraction checklist

Full 10-item field checklist and carrier-specific gotchas (Erie package vs. umbrella underwriting entities, the TRIA disclosure form, the Actual-Loss-Sustained business-income default, the blanket-format SF/construction reporting gap): `references/ocr-and-extraction-checklist.md` § Step 3.

## Step 4 — Build the premium history

- One row per property per policy year, package + umbrella premium, combined total, YoY % change, building limit/TIV, YoY TIV % change, and rate-per-$100-of-TIV (`=combined/TIV*100`). This decomposition is the whole point: it separates genuine rate increases from exposure growth (inflation-guard-driven limit increases are NOT rate increases).
- Flag any YoY combined increase that outpaces the TIV increase by a wide margin — that is the signal for "push back at renewal," not the raw dollar delta.
- Umbrella premiums moving independently of umbrella limits (limits flat, premium up double digits) is the single highest-value anomaly to surface — it showed up at every property in the 2026-08-13 review and is worth a standing line item.
- Build as an XLSX per the `xlsx` skill (Arial, ORA Style Guide colors if the deliverable is institutional-facing, formulas not hardcoded results, `recalc.py` before shipping).

## Step 5 — Cross-check the umbrella's own paperwork

Every umbrella/BCL declaration carries its own "Schedule of Underlying Insurance" listing the primary GL limits it sits above. **Check this against the actual current primary limits, not just the label.** Umbrellas are issued/priced before the primary is finalized or amended mid-term, and the schedule can go stale by months while the premium still moves. This was the single largest unresolved-cost item found in the 2026-08-13 review (a 44% umbrella increase attaching above a primary limit the umbrella's own dec still showed as 5x lower than actual).

## Step 6 — Diff against the prior term

For every property, produce a change log: effective date, what changed (limit, deductible, coinsurance→Agreed Value, exclusion added/removed, mortgagee added, address/location added or removed), direction (Improvement / Reduction / Cost-only / Administrative / Exposure-added), and premium impact if stated. Source every entry to a specific document — never a general "the coverage changed."

Common patterns worth naming explicitly when found: a coinsurance→Agreed Value conversion (real improvement, usually cheap); a deductible increase traded for a liability-limit increase (net could go either way — say which document proves it and let the reader judge); an inflation-guard line that stops printing on the declarations (ambiguous — flag as "disappeared from the dec, unclear if actually removed," don't assume either way); a location added then removed within one term (check for a coverage gap in the removal window against whatever replaced it — e.g. the tenant's own policy).

## Step 7 — Deductible/retention options

If a "Deductible Options" or similar quote tab exists in any tracker workbook in the folder, extract it verbatim into its own sheet and compute subtotals by line type (package vs. umbrella) using `SUMIFS`, not manual addition — the source data mixes entities and the eye misses rows. Frame the output as a shop-vs-retain ladder (saving at each deductible tier vs. current, against total current premium) rather than a bare table — that's the number that actually informs a self-insurance decision. Do not conclude "self-insure" or "don't" — that call needs loss-run history, which a declarations-only review never has; say so explicitly as an open item.

## Step 8 — Reconcile against any tracker workbook already in the folder

Renewal trackers (e.g., "Eric & Gabriel Goldberg Accounts.xlsx"-style files) go stale — they're hand-maintained snapshots, not linked to the declarations. Cross-check every premium figure in the tracker against the actual declaration for that term. When they disagree, the declaration wins — flag the tracker row as corrected, cite the source document, and never silently overwrite the tracker's history without noting what changed and why. If a scheduled task (e.g. an insurance-renewal-monitor) treats a DIFFERENT source (like a master workbook) as canonical, cross-check that too — a declarations-based review is ground truth and can surface that the "canonical" source itself is wrong. Surface the conflict; do not adjudicate which doctrine wins without the user.

## Step 9 — Rank data gaps by dollar consequence, not by document order

Produce a ranked punch list: missing base renewal declarations, missing statements of values, missing loss runs, missing mortgagee/loss-payee schedules where debt is known or suspected to exist, entity-name conflicts between the policy and other legal documents (LLC vs. Inc, EIN mismatches), and any named-insured mailing-address drift. Rank by what it would cost if wrong (a missing mortgagee on debt-encumbered collateral outranks a missing square-footage field).

## Step 10 — Deliverables and next actions

Standard output set for a full review:
1. Premium-history XLSX (Summary, Coverage Changes, Deductible Options, Data Gaps, Source Index tabs) — session-output naming (`YYYY-MM-DD_Topic_DocType_v##.xlsx`), saved to the project's `/outputs/` subfolder.
2. A draft-only broker data-request email (native-text PDFs going forward, SOVs, 5-yr loss runs, any specific re-rate/attachment-status questions raised in Step 5/6) — **never send without the user's explicit in-turn confirmation**, regardless of how routine it looks.
3. If a tracker workbook needed correction (Step 8), a corrected version as a NEW file — do not overwrite an existing user file in a non-Claude OneDrive business folder without permission first.
4. Housekeeping: byte-identical duplicate files move to a same-folder `/archive/` subfolder (never delete) — ask permission first, since this touches existing files in a non-Claude business folder.
5. If a scheduled renewal/lapse monitor already exists for this portfolio, update it (don't duplicate it) with any 90-day-out SOV/loss-run reminder logic and any source-of-record conflict this review surfaced — see Step 8. Check `list_scheduled_tasks` and `list_sessions` (concurrent-writer check) before touching it, per the `register-scheduled-task` skill.

## QC before presenting

- Every dollar figure traceable to a specific source document and, where it mattered, a 400+ dpi re-render.
- No fabricated square-footage/construction/BPP/business-income-limit figures where the carrier's dec format simply doesn't carry them — say so plainly instead of inferring.
- XLSX passes `recalc.py` with zero errors.
- Scope of any tracker correction stated explicitly (which properties were verified this pass vs. carried over unverified).

## Changelog

- v1.1 (2026-08-15): size refactor — Step 2 (OCR ladder) and Step 3 (extraction checklist) moved verbatim to `references/ocr-and-extraction-checklist.md`, no procedural change. Also fixed a duplicate stacked YAML frontmatter block present in v1.0 (two consecutive `---`-fenced blocks at the top of the file; a strict single-fence parser would read only the second, truncated one, silently shrinking the routing surface to a stub description with no trigger phrases).
- v1.0 (2026-08-13): initial. Built from the Insurance Policies Historical + Current portfolio review.
