---
name: "lease-abstraction-pipeline"
description: "Lease abstraction (single document or batch) and rent roll data extraction for Oxford Realty Advisors. Use whenever the user mentions: abstract this lease, abstract/parse leases, extract lease data or terms, lease abstract, summarize/read/review this lease, process lease folder, batch lease, lease pipeline, run lease abstraction, update rent roll from leases, or scheduled lease scan — for one or more commercial leases uploaded directly or in a folder, SharePoint, or Google Drive. Also trigger when an uploaded PDF/DOCX appears to be a commercial lease, or on \"run the lease pipeline\" / \"process the leases\" / \"update my rent roll\". Produces: 33-field abstract per lease (markdown single-doc; master XLSX batch with derived metrics, quality flags, portfolio analytics), Notion Tenant Database upsert, email summary to ggoldberg@oxfordra.net ONLY (routing canon 2026-06-10). Autonomous unattended operation — do not pause mid-run. v2.8 (2026-09-28: see Changelog)"
---

# Lease Abstraction Pipeline — Oxford Realty Advisors

Autonomous batch extraction of 33 structured data fields from every lease in a target folder. Outputs a master XLSX workbook, upserts Notion Tenant Database, and sends a completion summary. Designed for unattended execution.

---

## OPERATING PRINCIPLES

- **Never pause mid-run** for individual lease ambiguities. Mark the field `NOT FOUND`, flag it, and continue.
- **Exact language preferred** over paraphrase for fields: Permitted Use, Early Termination, Assignment/Subletting, Parking Terms, Environmental Responsibility.
- **Conflict rule:** If two conflicting values exist for the same field (e.g., rent in body vs. exhibit), extract both, flag discrepancy, note source of each.
- **Date format:** MM/DD/YYYY throughout.
- **Currency:** Two decimal places, no rounding.
- **SF:** Integer with comma separator (e.g., 12,500).
- **Notification:** Always email [ggoldberg@oxfordra.net](mailto:ggoldberg@oxfordra.net) ONLY (no cc — routing canon 2026-06-10) on completion (or failure). Draft the email — do NOT send without confirmation unless this is a scheduled unattended run (see Scheduled Task section).

---

## STEP 1 — FOLDER INVENTORY

Locate the target folder. Default paths in order of priority:

1. SharePoint: `Oxford Realty Advisors > Master Lease Database`
2. Path specified by Gabriel in the trigger message
3. `/mnt/uploads/` (if files uploaded directly to the current Cowork session) — see CLAUDE.md "Primary output path" for canonical mount conventions

List all files. Log: total count, file types (PDF / DOCX / other), estimated scanned PDF count. Print inventory summary before processing begins.

Skip (and log in Tab 6): files that are not leases, corrupted files, password-protected files.

---

## STEP 2 — DOCUMENT INGESTION (per file)

**Text PDF:** Extract via pdfplumber. **Scanned PDF:** Attempt pdfplumber first. If text yield < 100 words, fall back to pytesseract OCR. Flag result as `OCR-EXTRACTED` in output — verify accuracy on flagged records. **DOCX:** Extract via python-docx. **Password-protected / corrupted:** Log in Tab 6 with error code. Skip.

**Classify the ingestion path and carry it forward.** Record `INGEST_PATH` = `TEXT_LAYER` | `OCR` | `DOCX` per document.
Any document on the `OCR` path is subject to STEP 2A below and cannot be reported as abstracted until STEP 2A has run.

---

## STEP 2A — MANUSCRIPT-AMENDMENT SWEEP (mandatory for every `OCR` document)

> Origin: 2026-08-21, 754 Old State Route 74. A lease term of "May 31, 2030" was struck through in ink and replaced by
> hand with "2027", the paragraph circled and initialed. Tesseract transcribed the typed layer and dropped the manuscript
> change with no signal that anything was missing. An IC memo and a full IRR model were rebuilt around a rollover trough
> that does not exist, and were published before Gabriel caught it. The same sweep then found four more hand changes OCR
> had missed — including that the base lease in the file was **unexecuted**.

**The rule: on a scanned document, OCR text is evidence of the FORM, not of the BARGAIN.** Commercial leases are routinely
amended on their face — struck clauses, interlineated dates and rents, hand-completed party lines, initialed margins. OCR
sees none of it. Never report a field from an `OCR` document until the page image for that field has been read visually.

**Procedure**

1. **Render.** `pdftoppm -r 300 -png <file> img/<stem>` — one PNG per page.
2. **Contact sheet.** Tile every page into one image at ~600 px width, 4 columns (PIL). Pen strokes are large and cursive
   and remain visible at that scale. Read the sheet before reading any extracted text.
3. **Zoom and read visually — mandatory pages, whether or not the sheet shows marks:**
   - every page carrying a Field 8-17 economic term (commencement, expiry, rent, escalation, free rent, options)
   - the party/recital block (Fields 1-3)
   - **every signature page**
   - any page whose OCR output contains garbled fragments, stray single characters, or nonsense tokens — that noise is
     frequently the OCR engine failing on ink
4. **Record each manuscript item** in a new `MANUSCRIPT AMENDMENTS` block on the abstract: page, clause, typed text,
   hand-written replacement, and whether it is initialed and by how many parties.
5. **Where hand and type conflict, the hand controls the abstract** — and the conflict is reported, never silently resolved.

**Execution check (run on every document, not only OCR ones).** Inspect the signature block and record `EXECUTION_STATUS`
= `EXECUTED` | `UNEXECUTED` | `PARTIALLY_EXECUTED` | `INDETERMINATE`. A file copy with blank signature lines is a
transmittal draft, not a lease — at 754 Old State the 2020 base lease was unsigned, struck diagonally, and annotated
"Lease Sent 7/14/20", while the amendment that amends it by reference was fully executed. Where an amendment recites a
base lease or renewal that is absent or unexecuted, flag the **chain gap** explicitly and name every missing instrument.

For a **TEXT_LAYER or DOCX** document, the signature block is ordinary extracted text and this check is satisfied by
reading it during normal field extraction — but do not assume clean execution purely from the presence of extractable
text. A HYBRID document (a digital body with one embedded scanned/ink signature page — e.g. a Word lease printed, signed,
and re-scanned only for the last page) can clear the OCR-fallback threshold and never trigger STEP 2A at all. If any page
of a TEXT_LAYER/DOCX document looks like a scanned image (no extractable text on that page specifically, even though the
document as a whole ingested cleanly), route that page through STEP 2A's render/zoom procedure before recording
`EXECUTION_STATUS` — never infer execution status from extraction success/absence alone.

---

## STEP 3 — 33-FIELD EXTRACTION (per lease)

Extract every field. Mark `NOT FOUND` if absent.

### PARTIES & PREMISES

| # | Field |
|---|---|
| 1 | Landlord entity name (+ state of formation if stated) |
| 2 | Tenant entity name (+ state of formation if stated) |
| 3 | Guarantor(s) — names, entity type, full/limited scope, burn-off terms |
| 4 | Property address — full street address |
| 5 | Suite/unit number (or "entire building") |
| 6 | Rentable square footage |
| 7 | Permitted use — exact lease language |

### TERM

| # | Field |
|---|---|
| 8 | Lease commencement date |
| 9 | Lease expiration date |
| 10 | Total term length — calculate in months and years |
| 11 | Extension options — count, length each, notice period, rent mechanism (market/fixed/CPI) |
| 12 | Early termination rights — exact conditions, notice requirement, penalty formula |
| 13 | Holdover rate — % of base rent or "market rate" |

### ECONOMICS

| # | Field |
|---|---|
| 14 | Base rent schedule — full escalation table (period, monthly rent, annual rent, $/SF/yr) |
| 15 | Escalation type — fixed %, CPI, market reset, flat |
| 16 | Free rent / concessions — duration, conditions, abatement structure |
| 17 | Security deposit — amount, form (cash/LOC), return conditions, interest accrual |
| 18 | Lease type — NNN / modified gross / gross / industrial gross |
| 19 | CAM structure — estimated annual CAM, mgmt fee cap, base year, controllable cap, exclusions |
| 20 | Tenant improvement allowance — $/SF or lump sum, conditions, disbursement deadline |
| 21 | Percentage rent — breakpoint, rate, reporting obligation (or N/A) |
| 22 | Late fee — grace period (days), fee amount or % of monthly rent |

### LEGAL & RISK

| # | Field |
|---|---|
| 23 | Personal guaranty — present/absent, full/limited, burn-off date or conditions |
| 24 | Assignment/subletting — consent standard, recapture right, profit sharing, admin fee amount and whether owed if denied, cost/attorney-fee reimbursement (exact language) |
| 25 | Insurance requirements — coverage types, minimum amounts, additional insured, waiver of subrogation |
| 26 | Default cure periods — monetary (days), non-monetary (days), cross-default provisions |
| 27 | ROFR/ROFO — on what space, on what terms |
| 28 | SNDA/subordination — required/not required, non-disturbance language |
| 29 | Environmental responsibility — tenant scope, landlord scope, pre-existing carveout (exact language) |
| 30 | Condemnation/casualty — termination trigger, restoration obligation, rent abatement |

### CAM RECOVERY (v2.3 addition — closes a gap found during the FY2025 CAM reconciliation review, 2026-07-12)

| # | Field |
|---|---|
| 31 | CAM Recovery Type — classify from Field 19's CAM structure language plus Field 18's lease type into exactly one of: "Full CAM + Tax + Insurance", "Tax Only", "Capped CAM", "Uncapped CAM", "NNN — All Pass-Through", "Gross — No Recovery", "Partial Recovery" (these 7 values are the live options on the Notion Tenant Database's CAM Recovery Type field — do not invent a new option). Inference guide: Lease Type=Gross with no CAM/tax passthrough language -> Gross — No Recovery. Lease Type=NNN with full CAM+tax+insurance passthrough and no cap mentioned -> NNN — All Pass-Through (or Uncapped CAM if the lease frames it as CAM specifically, not full NNN). Any "controllable expense cap" or "cap of X% per year" language -> Capped CAM. Tenant pays only real estate tax reimbursement, no CAM -> Tax Only. Passthrough applies to only some categories (e.g. CAM but not insurance) -> Partial Recovery. If the language doesn't clearly map to one option, mark NOT FOUND and flag for manual review rather than guessing — same discipline as every other field. |
| 32 | Tenant Pro-Rata Share — the tenant's % share of building/project CAM pool (usually stated as "Tenant's Proportionate Share" or a ratio of Field 6 Rentable SF to total building/project SF). Extract the stated percentage if given; if only the ratio/SF figures are given, calculate it and flag as CALCULATED (not stated) in output. NOT FOUND if neither is present. |

### PARKING (v2.8 addition — closes a gap found 2026-09-28 at 9620 State Route 350)

| # | Field |
|---|---|
| 33 | Parking terms — exact lease language on: allocation formula or fixed count, exclusive vs. non-exclusive, reserved vs. unreserved, landlord's right to designate or restrict spaces, and restrictions on vehicle storage, maintenance, service or repair. If the allocation is a ratio of tenant RSF to project RSF, compute the percentage and flag as CALCULATED; do NOT state a space count unless the lease or a site plan gives the project's total spaces. NOT FOUND if the lease is silent. |

---

## STEP 4 — DERIVED METRICS (per lease)

| Metric | Formula |
|---|---|
| Rent PSF Year 1 | Annual base rent Yr 1 ÷ Rentable SF |
| Rent PSF Final Year | Annual base rent final year ÷ Rentable SF |
| Escalation CAGR | (Final yr rent / Yr 1 rent)^(1/(term yrs − 1)) − 1 |
| Total undiscounted base rent | Sum of all monthly base rent payments |
| NPV of base rent (8%) | PV of monthly payments discounted at 8%/yr |
| Effective rent PSF | (Total rent − free rent value) ÷ (SF × term yrs) |
| Months until expiration | From today → expiration date |

---

## STEP 5 — QUALITY FLAGS (per lease)

| Severity | Flag Condition |
|---|---|
| 🔴 CRITICAL | Rent < $4.00/SF NNN |
| 🔴 CRITICAL | Missing personal guaranty on leases > $5,000/mo |
| 🔴 CRITICAL | Assignment permitted without landlord consent |
| 🔴 CRITICAL | No default cure period stated |
| 🔴 CRITICAL | Environmental liability assigned entirely to landlord |
| 🟡 WARNING | Rent > $12.00/SF NNN — verify market justification |
| 🟡 WARNING | Escalation < 2%/yr — below inflation target |
| 🟡 WARNING | Escalation > 4%/yr — verify tenant acceptance |
| 🟡 WARNING | Extension notice period < 9 months |
| 🟡 WARNING | Holdover rate < 150% of base rent |
| 🟡 WARNING | Security deposit < 2 months rent |
| 🟡 WARNING | No SNDA provision |
| 🟡 WARNING | No late fee provision |
| 🟡 WARNING | Lease term < 3 years |
| 🟡 WARNING | Extension option without market rent reset |
| 🔵 INFO | Any field = NOT FOUND — manual review required |
| 🔵 INFO | Lease expires within 12 months — add to renewal pipeline |
| 🔴 CRITICAL | `EXECUTION_STATUS` = UNEXECUTED or PARTIALLY_EXECUTED — file copy is a draft, not a lease |
| 🔴 CRITICAL | Amendment references a base lease or renewal not present in the file (chain gap) |
| 🔴 CRITICAL | Manuscript amendment present that is NOT initialed by all parties |
| 🔴 CRITICAL | Landlord named in the lease does not match title vesting (per `title-exam-abstraction`; fall back to the deal's self-reported seller name if title-exam-abstraction hasn't run yet, and note the check as provisional) |
| 🟡 WARNING | Manuscript amendment present and initialed — must be reproduced verbatim in any estoppel |
| 🟡 WARNING | Tenant of record is a natural person with no entity and no guaranty |
| 🟡 WARNING | Term evidenced only by a margin note rather than a separate instrument |
| 🟡 WARNING | Assignment/subletting clause reaches "permitting occupancy or use by another party" — shared-occupancy requests need landlord consent (informational cross-reference for Field 24) |
| 🔵 INFO | OCR-extracted document — STEP 2A sweep completed, verify accuracy |
| 🔵 INFO | `INGEST_PATH` = OCR and STEP 2A not yet run — abstract is INCOMPLETE, do not publish |

---

## STEP 6 — XLSX OUTPUT

**File naming:** per ORA's three standing naming schemas (ratified 2026-06-10; ORA Cowork Global Operating Prompt v3.0, 2026-07-16 — do NOT unify; supersedes the archived v2.0/2026-06-11 doc of the same ratified rule). The master abstract workbook is a session/analysis output → use `YYYY-MM-DD_[Topic]_[DocType]_v##.ext` in an `/outputs/` subfolder. (Supersedes the single unified "ORA File-Naming Standard 2026-05-14.md," which predates the 2026-06-10 three-schema ratification and is retained only as historical provenance.) **Save to:** SharePoint `Oxford Realty Advisors > Lease Abstracts > [Year]`

| Tab | Contents |
|---|---|
| 1 — Master Rent Roll | One row/lease. All 33 fields + 7 derived metrics + flag counts. Freeze row 1. Auto-filter. Color: red fill = any CRITICAL, yellow = WARNING only, white = clean. |
| 2 — Rent Schedules | One block/tenant: name, property, suite, then full escalation table (Year, Period Start, Period End, Monthly, Annual, PSF). |
| 3 — Quality Flags Dashboard | One row/flag: File, Tenant, Property, Suite, Severity, Description. |
| 4 — Expiration Heatmap | Count of expirations by quarter, next 5 years. Highlight quarters with 3+ expirations. |
| 5 — Portfolio Analytics | WALT (by SF), avg rent PSF (weighted by SF), occupancy-weighted total rent, % with guaranty, % with ROFR, % NNN vs. gross, rent PSF std dev with outlier flags (>1.5 SD). |
| 6 — Skipped Files | File name, reason, timestamp. |

---

## STEP 7 — NOTION UPSERT

Target database: ORA Notion Tenant Database. Logic: update record if tenant already exists (match on Tenant Name + Property + Suite); create new record if no match. Do not overwrite records where Notion shows a more recent modified date than the lease document, unless Gabriel explicitly instructs.

| Notion Field | Source Field |
|---|---|
| Tenant Name | Field 2 — Tenant entity name |
| Property | Field 4 — Property address |
| Suite | Field 5 — Suite/unit |
| Lease Start | Field 8 — Commencement date |
| Lease End | Field 9 — Expiration date |
| Current Rent (monthly) | Field 14 — Base rent Year 1, monthly |
| Rent PSF | Derived — Rent PSF Year 1 |
| Lease Type | Field 18 |
| Renewal Options | Field 11 |
| Guaranty | Field 23 — Yes/No |
| Days Until Expiration | Derived — Months until expiration × 30 |
| Flag Count | Total flags (all severities) |
| Flag Status | Highest severity: Critical / Warning / Clean |
| CAM Recovery Type | Field 31 (v2.3) |
| Tenant Pro-Rata Share | Field 32 (v2.4) |
| Assignment / Sublet Terms (Lease) | Field 24 (v2.8) — condensed exact language, prefixed with a source note: document name and `EXECUTION_STATUS` |
| Parking Terms (Lease) | Field 33 (v2.8) — condensed exact language plus calculated allocation %, prefixed with the same source note |

The existing numeric `Parking Spaces` field is NOT written by this pipeline unless the lease states a fixed count. When `EXECUTION_STATUS` is anything other than EXECUTED, still write Fields 24 and 33 but the source note must say the copy is unexecuted.

---

## STEP 8 — COMPLETION NOTIFICATION

After all processing is complete, draft (do NOT auto-send unless scheduled unattended run) an email to [ggoldberg@oxfordra.net](mailto:ggoldberg@oxfordra.net) ONLY:

**Subject:** `ORA Lease Abstraction Complete — [N] leases processed — [DATE]`

**Body:**

```
Run completed: [timestamp]
Leases processed: [N]
Skipped files: [N] (see Tab 6)
Total fields NOT FOUND: [N] (requires manual review)
Critical flags: [N]
Warning flags: [N]
Leases expiring within 12 months: [N]

Output: [SharePoint link to XLSX]
Notion: [N] records updated, [N] records created

Top issues requiring your review:
1. [Top CRITICAL flag summary]
2. [Second issue if any]
3. [Third issue if any]
```

For **scheduled unattended runs**: send automatically without asking for confirmation via Outlook COM — the SOLE send path (Composio retired 2026-06-11; NO fallback): Desktop Commander `start_process` → `powershell -ExecutionPolicy Bypass -File "C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1" -To "ggoldberg@oxfordra.net" -Subject "ORA Lease Abstraction Complete — [N] leases processed — [DATE]" -BodyFile "<temp body file>" -BodyFormat html`. Automated outputs route to ggoldberg@oxfordra.net ONLY (routing canon 2026-06-10 — no cc; the cc-Eric exception is the Daily Brief only). On non-zero exit: retry once, then flag loudly in the Notion completion record — do NOT halt. (Gmail is disabled on the ORA tenant; never use Gmail or any Composio/Rube tool.) For **manually triggered runs**: present draft to Gabriel and wait for approval.

---

## EXECUTION SUMMARY (print to chat when complete)

```
✅ Lease Abstraction Pipeline Complete
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Files inventoried:     [N]
Leases extracted:      [N]
Skipped:               [N]
NOT FOUND fields:      [N total across batch]
🔴 Critical flags:     [N]
🟡 Warning flags:      [N]
🔵 Info flags:         [N]
Expiring ≤12 months:  [N]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
XLSX: [SharePoint link]
Notion: [N] updated / [N] created
```

---

## CROSS-SKILL INTEGRATION

- **legal-intelligence:** Reference clause library when flagging non-standard provisions. Compare against Oxford preferred positions.
- **tenant-intelligence:** Feed extracted data into tenant risk scoring for existing portfolio tenants.
- **acquisition-underwriting** (successor to the retired `rent-comp`, 2026-08-05): compare extracted rent PSF against current market comps for below/above-market flags, using that skill's COMPS mode / comp-grid discipline (absorbed from `rent-comp` on 2026-08-12 — see the 2026-08-12 event_log entry).
- **title-exam-abstraction** (2026-08-21): source of the vesting record the STEP 5 landlord-mismatch flag checks the lease's named landlord against.
- **estoppel-request-generation** (2026-08-21): consumes the 33-field abstract (including `EXECUTION_STATUS`/`INGEST_PATH`/`MANUSCRIPT AMENDMENTS`) to pre-fill and draft tenant estoppel certificates — the sole path for that deliverable; `document-assembly`'s Template 7 is superseded, see that skill's own note.
- **document-assembly:** Use extracted data to auto-populate renewal offers, lease addenda.
- **lease-renewal-pipeline:** Auto-trigger for any lease flagged as expiring within 12 months.
- **tenant-consent-request** (2026-09-28): reads the Notion `Assignment / Sublet Terms (Lease)` and `Parking Terms (Lease)` fields this pipeline writes (Fields 24 and 33) as its first-pass lease shortcut.

---

## REFERENCE FILES

See `references/extraction-edge-cases.md` for guidance on:

- Leases with multiple amendment documents
- Side letters and letter agreements
- Leases referencing exhibits not included in the file
- Ground leases and master lease structures

## Changelog

- v2.8 (2026-09-28): added Field 33 (Parking terms) and widened Field 24 to capture the assignment/sublet admin fee, whether it is owed if the request is denied, and cost/attorney-fee reimbursement. Origin: 9620 State Route 350 shared-occupancy request — the parking allocation formula and the $500 per-request fee were only discoverable by re-reading the full lease, and the Notion Tenant Database had no field for either. STEP 7 now writes two new Tenant Database text fields (`Assignment / Sublet Terms (Lease)`, `Parking Terms (Lease)`) with a mandatory source/execution note. Added one STEP 5 warning cross-referencing occupancy-by-another-party language. Rebuilt the field, metric, flag, XLSX-tab and Notion-mapping tables as proper Markdown tables (the synced copy had them collapsed into run-on text); no field, formula, flag threshold or routing rule from v2.7 changed. Field count 32 -> 33.
- v2.7 (2026-08-21, adversarial review): the v2.6 landlord-mismatch flag had no defined source for "owner of record" —
  now checks against `title-exam-abstraction`'s vesting record (added to CROSS-SKILL INTEGRATION), with a provisional
  seller-name fallback when that skill hasn't run yet. The execution check's "run on every document" line had no
  described mechanism for TEXT_LAYER/DOCX documents — STEP 2A's render/zoom procedure was OCR-scoped only; added
  explicit routing for a hybrid document (digital body, one embedded scanned signature page) to STEP 2A regardless of
  overall ingestion path. CROSS-SKILL INTEGRATION's estoppel line repointed from `document-assembly` (whose Template 7
  is now superseded) to `estoppel-request-generation`.
- v2.6 (2026-08-21): manuscript-amendment sweep. New STEP 2A makes a visual page-image review mandatory for every
  OCR-path document before any field is reported, adds an `EXECUTION_STATUS` check and a lease-chain-gap check to every
  document, and adds nine STEP 5 quality flags covering unexecuted counterparts, chain gaps, un-initialed hand changes,
  landlord-of-record mismatch and natural-person tenants. Origin: 754 Old State Route 74 — OCR silently dropped an
  initialed strike-through that moved a lease expiry by three years, and the published memo and model were both wrong
  until Gabriel caught it. The same sweep then found an unexecuted base lease that four months of file review had missed.
- v2.5 (2026-08-15): LOW fix (Skill Text Audit finding F9) + new finding (coverage-gap-3, stale file-naming-standard citation). Moved the v2.4/v2.3 changelog prose that had accumulated in the description field down here (both already existed in this section, so the description copies were pure duplication); description now carries a single trailing version tag. Step 6's file-naming citation updated from the archived "ORA Cowork Global Settings v2.0" (2026-06-11) to the current "ORA Cowork Global Operating Prompt v3.0" (2026-07-16) — the underlying three-schema rule is unchanged, only the version/document-name citation; same fix applied to the companion `SCHEDULED_TASK.md`. No extraction field, derived metric, or quality flag changed.
- v2.4 (2026-08-12): Repointed the cross-skill `rent-comp` reference (retired 2026-08-05) at `acquisition-underwriting`, which absorbed the comp-grid discipline on 2026-08-12 per Gabriel's scoped-restore ruling. Below/above-market rent PSF flags now have a live method again. No extraction field, derived metric, or quality flag changed.

- v2.3 (2026-07-12): added Fields 31 (CAM Recovery Type) + 32 (Tenant Pro-Rata Share) — the FY2025 CAM reconciliation data-readiness review (ora-cam-reconciliation-annual, 2026-07-12) found these two fields blocking a defensible reconciliation (0/139 and 45/138 leases populated respectively) with no existing extraction path to backfill them. Notion Tenant Database's "CAM Recovery Type" select field already existed with 7 live options (unused); added a matching "Tenant Pro-Rata Share" number/percent property to the same data source. STEP 7 Notion mapping updated; frontmatter field-count bumped 30->32.
- v2.2 (2026-07-08): HIGH fix (Skill Text Audit finding 5) — Step 6 file-naming citation repointed from the superseded single "ORA File-Naming Standard 2026-05-14.md" to the ratified three-schema doctrine (ORA Cowork Global Settings v2.0, 2026-06-10/11); master workbook classified as a session/analysis output. Also (MEDIUM fix, finding 10): companion `SCHEDULED_TASK.md` version stamp (was 1.0 / 2026-04-04) synced to this file's version.