---
name: "settlement-basis-extraction"
description: "Use when the user says: import settlement statements, build the basis register, extract closing costs, OCR the settlement PDFs, make scanned tax returns searchable, capitalize closing charges, reconcile a settlement to Schedule L, or points at a folder of HUD-1/ALTA settlement statements, deeds, or closing packages — extracting acquisition/disposition data from HUD-1/ALTA settlement statements into a capitalizable-basis register for Oxford Realty Advisors property entities. Also trigger when a new acquisition or disposition closes and the settlement package needs to be worked into the entity's basis and the portfolio's EXCHANGE_1031 tracking."
---

# Settlement-Basis Extraction — ORA (v1.6)

## When to use this

Any time a settlement statement (HUD-1 or ALTA Combined) needs to become a
line item in an entity's basis, and every time an acquisition or disposition
closes. This is the same procedure that built the 2026-08-17 Tax & Basis
Register from 32 settlement PDFs across 27 transactions -- it is written so
that work is repeatable rather than re-invented per closing.

Do not use this for lease abstraction, insurance declarations, or tax
returns themselves -- those have their own skills
(`lease-abstraction-pipeline`, `insurance-renewal-review`). This skill's
scope is strictly: settlement statement in, capitalizable basis + charge
detail + 1031 chain entry out.

One exception: the end-of-job twin sweep (step 10) also covers scanned tax
returns. This skill makes them searchable; it does not extract them. Every
later search over returns (tax-appeal, disposition-analysis, annual-cycle,
open-item sweeps) depends on those twins.

## Method

### 0. Find the whole closing package before declaring anything NOT FOUND

The settlement statement is one document in a package. Deeds, PSAs and
assignments, owner's title policies, operating agreements, intercompany
promissory notes, deeds of conversion and QI/1031 forms sit together in
`Business\Corporate and Settlement and Legal Documents\<property or LLC>\`
(about 520 PDFs, one subfolder per property or entity; 1031 forms also in
`...\1031 Forms`). Read that subfolder first. A "price NOT FOUND", "no
lender", "no operating agreement" or "chain-of-title gap" finding is
unreliable until it has been checked against it -- the 2026-09 fact-base
builds missed this folder and reported all four wrongly.

Run the census first: `python scripts/package_census.py "<folder>"
[--factbase <fact-base.json>]`. It lists every PDF with page count, text /
partial / image-only status (sampled, so it is cheap), whether an `(OCR)`
twin already exists, and any path long enough to break Python on Windows
(the census reads them itself; for other tools, copy them out with Git Bash
`cp` or open them with the `\\?\` prefix). With `--factbase` it
lists every field still NOT FOUND / INFERRED / CONFLICT / illegible and says
whether the fact base ever recorded a `recheck_*` against this folder; a
flagged field with no recorded recheck is unverified, not a finding.

### 1. Triage every document for a text layer before doing anything else

A HUD-1/ALTA PDF is either a native digital document (title company software
output -- has a real text layer) or a scan (has none). Do not assume; check
each file. If extracting text returns empty or near-empty content, the
document is image-only and needs OCR before anything downstream can read it
programmatically.

- Digitally-generated ALTA statements (recent closings, e.g. a 2023+ Stewart
  Title combined statement) usually have a text layer.
- Older HUD-1s, faxed pages, and anything with visible fold marks / skew in
  a preview are almost always scans.
- Historically, roughly 70% of a settlement corpus comes back scan-only
  (23 of 32 in the 2026-08-17 corpus). Budget for OCR being the majority
  case, not the exception.

### 2. OCR every image-only document at 300 dpi, and keep the twin next to the original

Run OCR (300 dpi minimum, greyscale, `--psm 6` per page -- lower resolutions
lose small print like transfer tax splits and per-diem prorations) and save
the searchable output ALONGSIDE
the original in the same folder, not in a separate output tree. Naming:
`<original filename> (OCR).pdf`. This is a one-time cost per document --
once a file has a searchable twin, every future skill run (this one,
tax-appeal, disposition-analysis) benefits without re-OCRing.

Use `Taxes Estimated + Returns\_ora-tax-tools\ocr_twins.py` rather than
hand-rolled OCR. With no flags it is a census that changes nothing. `--run`
creates the missing twins with ocrmypdf (300 dpi oversample, `--psm 6`,
`--skip-text` so PARTIAL files keep their text pages). It never overwrites
an original or an existing twin. A twin with no text is reported as
`twins_unusable` and its original stays on the to-do list. A failed OCR is
saved as `<name> (OCR)-FAILED.pdf`, never under the twin name, and is not
retried (`PRIOR-FAILURE`) until that file is removed. A scan byte-identical
to one that already has a twin is listed under `duplicates_skipped`, not
re-OCR'd.

Where to run it:
- The census runs anywhere Python has pypdf or PyMuPDF, including the
  laptop through the device bridge. Allow about 90 s per folder over the
  OneDrive mount, and run one folder per call because a bridge call times
  out at about 180 s.
- Create twins (`--run`) in a workspace that has `ocrmypdf`; the laptop does
  not. Stage the scans, run the script on the staged folder, then commit
  each twin back beside its original. Commit files up to 25 MB by
  `stagedPath`; for larger ones, send the file first and commit by its
  `fileUuid`.
- Tesseract-only OCR on the laptop measured about 30 s per page (2026-11-24)
  versus 2-4 s per page with ocrmypdf in the workspace.

Where a digit cannot be read with confidence after OCR, leave the cell
**blank** in the register and set its `basis = blank` (see "Cell basis"
below). Never guess a number to fill a cell. Log the illegible field in
the EXCEPTIONS tab with the file name and the specific line item.

Two known illegible-field patterns worth watching for specifically:
- Contract sales price (HUD-1 line 101) sometimes fails OCR when the rest of
  the page is legible. If line 101 is unreadable, the contract price can
  often be corroborated from the transfer-tax and commission lines (both are
  usually a fixed percentage of price) -- derive it that way rather than
  leaving it blank. If the tax lines fix the price exactly (a fixed
  ad-valorem rate), set `basis = derived`; if they only bound it (minimum
  or rounded tax, a cap), enter the floor and set `basis = lower-bound`.
- An entire settlement table (all of Section L, or the whole HUD-1 second
  page) can fail as a block, typically from a bad fax generation or a
  photocopy-of-a-photocopy. When that happens, don't partially transcribe
  around it -- flag the whole document as "OCR failed, request clean copy"
  in EXCEPTIONS and move on. Partial transcription of a garbled table is
  worse than no transcription.

### Cell basis: every non-transcribed figure carries a persistent flag

`BASIS_REGISTER` and `CHARGE_DETAIL` each carry a `basis` column. Values:
`transcribed` (read directly off the document), `derived` (computed or
corroborated from other lines or a public record -- record the method in
the adjacent note; an exact back-solve), `lower-bound` (a floor the other
figures bound but do not fix, e.g. "at least ~$4.78M implied" from a
minimum transfer-tax line), or `blank` (the cell is left empty -- an
unreadable digit per step 2 or a missing allocation per step 5 -- and has
an EXCEPTIONS row). A cell with no digit read from a source document is
never `transcribed`. Prose flags in a note are not enough: they do not
survive a re-sort or a hand-off, and in the 2026-08-17 register a
`lower-bound` price was later stated outright in the closing package that
nobody re-opened.

Re-check rule: after the step 7 recalc gate and before the step 9
verification pass, the builder re-checks every cell whose `basis` is not
`transcribed` (`blank` cells included) against the step 0 package. When
the package states the figure, replace the cell with the stated value,
set `basis = transcribed`, cite the document in SOURCE_INDEX, and note
the old value in the cell note. When it still does not, leave the flag
in place and list the cell under EXCEPTIONS as "unresolved after package
sweep". Add a live count of unresolved cells to the README tab,
`COUNTA(<basis range>)-COUNTIF(<basis range>,"transcribed")`, so the
count is visible at hand-off. `COUNTA` skips empty cells, so every row
must carry a `basis` value; a plain `<>transcribed` criterion would
instead over-count empty cells as unresolved.

### 3. Transcribe verbatim, then cross-foot before touching anything else

Watermarks and skewed scans scramble column order (for example
Commissions and Insurance swapped). Resolve any suspect label order from the
PDF's word coordinates, not from the OCR reading order.

Transcribe every settlement charge line as it appears -- do not net, round,
or reclassify during transcription. Cross-foot each settlement against its
own printed control totals (Borrower's total due = Seller's total due =
Section L total, or the ALTA combined-statement subtotals/totals block).
A settlement that doesn't foot to zero against its own printed totals has a
transcription error somewhere in that document -- find and fix it before
moving to the next document, not at the end of the batch.

### 4. Tag every closing charge capitalizable / not

Every line in Section L (HUD-1) or the charges block (ALTA) gets a
capitalizable/not-capitalizable tag. Use `references/charge-capitalization-taxonomy.md`
for the standard tagging rules (Reg. 1.263(a)-2, transfer taxes, prorations,
loan costs vs. acquisition costs). This produces the CHARGE_DETAIL tab --
one row per closing-charge line, tagged, for every settlement in the batch.
The 2026-08-17 register carried 442 such lines across 27 transactions; do
not summarize charges into a single "closing costs" number, the per-line
detail is what lets a future preparer or IC memo pull exactly which costs
were capitalized and why.

### 5. Flag land/improvement allocation gaps as you go, don't wait for the tax return

If a settlement's entire debit total lands in one basis bucket with no
land/improvement split (common when the settlement statement itself doesn't
allocate), flag it immediately in EXCEPTIONS -- "zero land basis, needs
assessor ratio or appraisal split" -- rather than letting it silently
capitalize 100% to depreciable improvements. This has been a recurring
finding (1100 Rarig, and 401 Sunburst's Dorchester County SDAT record showing
Land Value $0) -- treat a missing split as a standing exception category, not
a one-off.

A $0 or blank land line does not mean zero land basis: leave the register
cell blank (never $0), set `basis = blank`, and log "needs assessor ratio
or appraisal split". Franklin County OH, Baltimore City and County MD,
Dorchester County MD and Talbot County MD publish land/improvement
ratios; cite the source and as-of date and set `basis = derived`. Seller
credits reduce basis -- carry them in their own column (for example the
5600 Sunnyside 1992 credit of $1,137.30), never netted into a charge line. A 1031 replacement row's
"indicated basis" is COST; tax basis is carryover, so label it as such.

### 6. Update the EXCHANGE_1031 tab and the 1031 chain register together, at every closing

If the settlement is a leg of a like-kind exchange (QI named on the HUD-1 /
ALTA, or the closing falls within 45/180 days of a known relinquishment),
add a row to EXCHANGE_1031 AND to the standing 1031 Exchange Chain Register
(see the companion register -- ask the user if they don't have a current
copy) in the same session. Record: identification-notice parcels, this
leg's settlement date and parcel(s), and whether this leg is on the Form
8824 (leave blank/PENDING if the 8824 hasn't been filed yet -- don't wait
for the return to create the row). The point of updating both at closing
time, rather than retroactively, is that a parcel-count mismatch between the
identification notice and the settlement is visible immediately, not two tax
seasons later -- this is exactly how the McGregor/Northwood gap in the
2026-08-17 register went undetected for two years.

Run these six standing checks at every closing:

1. Compare parcel counts on the settlement, the 45-day identification notice
   and the Form 8824. Any mismatch is a defect.
2. For every identified property that closes, record whether it closed
   inside or outside the exchange.
3. Same taxpayer: the vesting entity on the deed must be the exchanger or its
   disregarded entity. Check the operating agreement -- a two-member LLC is
   not disregarded (7658 Fishel, LLC: Eric Goldberg 90% / 3 Peaks Capital 10%
   per the executed agreement, while FVC was the exchanger).
4. Related party: run the seller AND the lender against the ORA affiliate
   list before funding. Section 1031(f) has a two-year lookback.
5. Boot: any dollar that leaves the QI to anyone other than the seller or
   the settlement agent is presumptively boot (a holdback paid to the
   settlement agent, as on 6300 Sheriff Road, is the pattern).
6. Basis: replacement property takes carryover basis under Section 1031(d);
   never book cost, and remember basis can carry over twice.

### 7. Build/refresh the workbook

Standard tab structure (create tabs that don't yet exist; append to ones
that do -- do not create a parallel workbook per batch). Every figure is
transcribed verbatim, with blank cells where a digit can't be read with
confidence:

- `README` -- what was imported this pass, source paths, coverage, OCR
  method note, gaps to close.
- `ENTITY_MASTER` -- one row per LLC/entity.
- `TAX_SUMMARY` -- federal + state filing summary by entity-year.
- `PROPERTY_PL` -- Form 8825 line-by-line by property.
- `BALANCE_SHEET` -- Schedule L + M-2.
- `DEPR_COSTSEG` -- depreciation and cost segregation position by property.
- `BASIS_REGISTER` -- one row per property, rolling basis; carries the
  `basis` column (see "Cell basis").
- `CHARGE_DETAIL` -- one row per settlement closing-charge line, tagged
  capitalizable/not (see step 4); carries the `basis` column (see "Cell
  basis").
- `EXCHANGE_1031` -- one row per exchange leg (see step 6).
- `PAYMENTS` -- coupons/estimated payments if in scope for this batch.
- `EXCEPTIONS` -- every illegible field, cross-foot failure, land/basis
  gap, and non-`transcribed` cell unresolved after the package sweep, with
  file name and specific line item.
- `SOURCE_INDEX` -- file name -> tab/row(s) it feeds, so a reviewer can trace
  any number back to its settlement statement.

Every check column in the workbook should be a live formula, not a
hardcoded value -- the point is that the workbook re-verifies itself when a
row is edited later. Wrap the checks in `ROUND(...,2)` so they evaluate to
zero. Build per the `xlsx` skill's conventions and ship only when
`recalc.py` returns `status: success` with `total_errors: 0`. A clean recalc
shows the formulas evaluate, not that they are right; roll-up lines such as
"See Statement" and "TOTAL OTHER EXPENSES" must be excluded from the Other
column (they were double-counted on 6 of 12 property rows in the first
build).

### 8. Close with a "six items that change a number" style summary, not a raw diff dump

After the workbook is built, write a short list (the 2026-08-17 register
used six) of the specific findings that would change a number a preparer or
IC memo currently relies on -- zero land basis, a parcel missing from an
8824, a related-party exposure, a Section 481(a) catch-up with no Form 3115,
a title-chain gap, an error in a previously-issued memo. This is the
highest-value output of the whole procedure; the workbook is the evidence,
this list is the action item.

### 9. Run an independent verification pass before delivery

Have a reviewer who did not build the workbook re-check it, grepping the
source text for every figure verified, and confirming the "Cell basis"
re-check was done for every non-`transcribed` cell. In the first build
this pass caught the roll-up double-count above. Do not ship on the
builder's own recalc.

### 10. Twin sweep: settlement folders AND tax-return folders, at the end of every job

Before reporting the job done, run `ocr_twins.py` over:
1. the settlement package folder(s) touched this job (`--scope all`);
2. `Business\Taxes Estimated + Returns` (`--scope returns`);
3. `Business\Loans External` (`--scope returns`), because lender packages
   are where full-year entity returns end up (the TY2020-2023 returns were
   found only in the Park National loan file).

`--scope returns` matches return-type file names: 1040/1041/1065/1120/
1120-S, K-1, 8824, 4562, 8825, `MD Form 510/511/502`, IT 4738, BR-25,
"tax return", "taxes", "tax bill". It is a name filter, so run
`--scope all` on a folder whenever a return might be saved under another
name.

Create every missing twin (step 2 explains where). The job is done only
when each census reports `scans_without_twin: 0` and an empty
`twins_unusable`, or when every remaining file has an EXCEPTIONS row
(`OCR-FAILED` / `PRIOR-FAILURE` → "request clean copy"). Spot-check each new
twin against one figure already known from another source before calling
it good. In the 2026-11-25 sweep the Fenton MD 511 tax ($6,781) and the
2022 1040 AGI ($727,662) both matched. Paste each census's one-line
summary in the response.

## Output

- The refreshed workbook (xlsx), named per the session-output convention:
  `YYYY-MM-DD_TaxAndBasisRegister_Workbook_vXX.xlsx` in the deal's
  `/outputs/` subfolder.
- Searchable OCR twins left alongside every original that needed them,
  in the settlement folders and the tax-return folders (step 10), with
  each census summary line in the response.
- An updated 1031 Exchange Chain Register (see companion register skill/
  workbook) if any leg closed this batch.
- A short "items that change a number" list in the response, not just in
  the workbook.
- **Project sync (mandatory, v1.5).** The workbook in
  `Taxes Estimated + Returns\outputs\` is the source of record; the
  claude.ai project "Taxes + Settlement Statements" carries a text mirror.
  After saving a new workbook version, run
  `_ora-tax-tools\sync_outputs_to_project.py` and upload every name in its
  `pending_upload` to the project as `claude/<name>` (read each file in full
  first; parts are capped at 40 KB), then re-run with `--mark-uploaded`.
  If the Projects tool is not available in the session, say so in the
  response and leave the files pending for the scheduled task
  `ora-tax-outputs-project-sync`. Do not report the register as delivered
  while its mirror is pending and unflagged.

## Do not

- Do not guess a digit to fill a blank cell. Blank + EXCEPTIONS row beats a
  plausible-looking wrong number.
- Do not summarize CHARGE_DETAIL into a single closing-costs figure -- keep
  the per-line detail.
- Do not wait until the tax return is being prepared to reconcile an
  exchange leg against its identification notice -- do it at closing.
- Do not treat a land-value-zero settlement as resolved by capitalizing
  100% to improvements -- that is the exception, not the default.
- Do not overwrite or delete an existing twin, even a bad one: report it
  (`twins_unusable`) and let a person replace it.
- Do not count a scan as handled because a file named `(OCR).pdf` exists
  beside it: a twin with no text layer is not a twin.

## Changelog

- v1.6 (2026-11-25): Added step 10, a twin sweep over the settlement
  folders plus `Taxes Estimated + Returns` and `Loans External`
  (`--scope returns`). Step 2 now runs through `_ora-tax-tools\ocr_twins.py`
  (census by default; `--run` creates twins; never overwrites; flags
  unusable twins; parks failures as `(OCR)-FAILED.pdf`; skips byte-identical
  duplicates). Root incident: on 2026-11-24 the scanned TY2023 entity
  returns sat unsearchable in the Park National loan file, so open-item
  sweeps missed Forms 8824 and the Muirkirk step-up until they were OCR'd
  by hand. The first sweep (2026-11-25) found two more scanned returns
  (Fenton MD 2025, the Symetra-file 2022 1040); both folders now census
  clean. Description gains "make scanned tax returns searchable" (650/1024
  chars).

- v1.5 (2026-11-24): Output now requires the project sync step. Root
  incident: register v02–v04 (2026-11-14) were saved only to OneDrive and
  the project worked from v01 data for ten days, re-asking questions v04
  had already closed. Convention recorded in the project's
  `claude/README_SourceOfRecord.md`. Description unchanged.

- v1.4 (2026-09-21): Added `scripts/package_census.py` (step 0): package
  inventory with text-layer triage, OCR-twin detection and long-path flags,
  plus a `--factbase` mode that lists unverified NOT FOUND / INFERRED /
  CONFLICT fields. Tests: `tools/test_package_census.py`. Description
  unchanged except the version tag.

- v1.3 (2026-09-21): Added persistent `basis` column (`transcribed` /
  `derived` / `lower-bound` / `blank`) and the pre-ship re-check of every
  non-`transcribed` cell against the step 0 package, after a `lower-bound`
  price ("at least ~$4.78M implied") in the 2026-08-17 register turned out
  to be stated outright in the closing package. Description unchanged
  except the version tag.

- v1.2 (2026-09-21): Reconciled against the full method in the 2026-08-17
  project transfer. Added step 0 (read the Corporate and Settlement folder
  package before declaring NOT FOUND), watermark column-order rule,
  greyscale/`--psm 6` OCR settings, land-ratio sources and seller-credit
  column, the six standing 1031 checks, `ROUND(...,2)`/`recalc.py` ship gate
  with the roll-up exclusion, and step 9 (independent verification).
  Description unchanged.

- v1.1 (2026-08-24): Description trimmed to restore headroom (was 1019/1024,
  headroom 5 -- close-out work-order item 4, the tightest of the six flagged
  skills). Dropped the "LLC" gloss and the dated version-history parenthetical
  ("first cut, generalized from..."); the full workbook-tab list and every
  trigger phrase kept intact. `description_budget.py` now reports headroom 123.