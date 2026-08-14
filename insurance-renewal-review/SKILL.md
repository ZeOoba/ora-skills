---
name: "insurance-renewal-review"
description: "Oxford Realty Advisors property insurance renewal review — OCR scanned Erie/Selective declarations, build a per-property premium history, diff each renewal against the prior term, and flag coverage reductions, rate-only increases, and data gaps. Use when the user says: review insurance policies, insurance renewal review, how has insurance changed, premium history, shop our insurance, self-insure, insurance declarations, coverage changes, deductible options, or points at a folder of insurance PDFs/declarations. Also trigger when a folder contains scanned Erie/Selective/carrier declaration PDFs and the user asks for trends, comparisons, or a renewal decision. v1.0 (2026-08-13, built from the Insurance Policies Historical + Current portfolio review)."
---

---
name: insurance-renewal-review
description: Oxford Realty Advisors property insurance renewal review — OCR scanned declarations, build premium history, diff terms, flag coverage changes and gaps.
---

# Insurance Renewal Review (ORA)

Codifies the extraction/compare/flag pass built 2026-08-13 reviewing "Insurance Policies Historical + Current" (5 property folders, 25 PDFs, 1 broker .msg, 3 tracking XLSX — every PDF a scanned image with no text layer).

## Trigger phrases
"review insurance policies", "insurance renewal review", "how has insurance changed", "premium history", "shop our insurance", "should we self-insure", "insurance declarations", "coverage changes", "deductible options" — or the user points at a folder of insurance PDFs/declarations and asks for trends, comparisons, or a renewal decision.

## Step 1 — Inventory and triage every file

- `find <folder> -type f` for a full inventory; one subfolder per property is the ORA convention.
- Run `pdftotext -layout` on every PDF first. ORA's carrier (Erie Insurance) and its agency (Foundation Insurance Group) deliver 100% Microsoft-Print-to-PDF scans with zero text layer — `pdftotext` will return only page-break bytes. Confirm this per-file (`wc -c` on the output) before assuming OCR is needed; do not skip the check.
- `md5sum` every PDF up front. Duplicate/renamed files are common (found: a byte-identical "#2" file misnamed as a second policy). Report duplicates explicitly — never silently treat them as two documents.
- Check for `.msg` attachments — brokers forward missing endorsements this way. Extract with `extract-msg` (pip, `--break-system-packages`); list sender, date, subject, body, and every attachment; extract and read PDF attachments too. A `.msg` in the folder is often the ONLY place a mid-term amendment or endorsement lives — do not skip it because it isn't a PDF.

## Step 2 — OCR ladder (for scanned/image-only PDFs)

1. `pdftoppm -r 200 -png` to render pages (150–200 dpi is enough for triage; re-render the specific page at 400–600 dpi to confirm any dollar figure before reporting it — OCR misreads digits more than any other content class).
2. `tesseract page.png stdout --psm 6` for a first-pass read, OR use the Read tool directly on the rendered PNG (vision) — vision reading is more reliable for declarations pages with dense tabular layouts than tesseract alone. Cross-check the two when a figure matters.
3. **Every dollar figure that goes into a deliverable must be re-rendered at ≥400 dpi and visually confirmed** — this is not optional. State the confidence explicitly if a digit is genuinely ambiguous; never guess.
4. Two cores and ~250 pages of scans will time out a single serial render/OCR pass (observed: `pdftoppm` across a full folder exceeded a 120s tool timeout). Either background the render (`nohup ... &`, poll for completion) or split the work across parallel subagents by property folder — one agent per property folder is the natural split and lets 4–5 folders OCR concurrently instead of serially.

## Step 3 — Per-document extraction checklist

For every distinct policy document (package/property, umbrella/BCL, and any standalone GL/inland-marine), extract verbatim:

1. Named insured(s) and mailing address
2. Carrier / underwriting entity (note: Erie writes package business under **Erie Insurance Company** and umbrella business under a differently-named **Erie Insurance Exchange** — these are different underwriting entities on the same account; don't conflate them) and the agency/broker
3. Policy number and exact policy period
4. **Total premium** (the single most important field) — plus any per-line breakdown and the TRIA/terrorism charge if separately disclosed (Erie discloses this only as a token $2–$4 line on the TRIA disclosure form, IL985F/H — check that form specifically, it is not on the main declarations page)
5. Property coverage: building limit (or blanket limit across a location schedule), BPP, business income/rental value basis (Actual Loss Sustained is Erie's default, with a period-of-indemnity but usually no dollar cap — note this explicitly since it reads like a gap but is standard for this carrier), valuation basis (RC/ACV/Agreed Value), coinsurance %, inflation guard / automatic adjustment %
6. Deductibles (AOP, wind/hail — Erie commonly just says "Property deductible," meaning no separate wind number exists — say so rather than reporting "NOT SHOWN" as if it were an omission; named storm)
7. GL limits (each occurrence, aggregate, products/completed ops, personal & advertising injury, damage-to-premises-rented/fire legal, medical)
8. Umbrella/excess limits, premium, and its own schedule of underlying insurance (cross-check this against the actual primary limits — see Step 5)
9. Location/building schedule: every address, year built, class code, square footage/construction/sprinkler status IF the dec format carries it (Erie's blanket format usually does NOT print per-building SF/construction/sprinkler — say "NOT SHOWN — format limitation," not "gap," when that's structurally true of every year)
10. Endorsements, exclusions (esp. new ones — PFAS/CG4032, nuclear/CU2123, cyber/CAT203, abuse-molestation/CAT149 recur across the Erie book), loss payees/mortgagees/additional insureds

If a figure is illegible or absent: say "NOT LEGIBLE" or "NOT SHOWN" — never guess, never fabricate, never silently carry forward a prior year's number.

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

