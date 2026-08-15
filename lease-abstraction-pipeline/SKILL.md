---
name: lease-abstraction-pipeline
description: 'Lease abstraction (single document or batch) and rent roll data extraction for Oxford Realty Advisors. Use whenever the user mentions: abstract this lease, abstract/parse leases, extract lease data or terms, lease abstract, summarize/read/review this lease, process lease folder, batch lease, lease pipeline, run lease abstraction, update rent roll from leases, or scheduled lease scan — for one or more commercial leases uploaded directly or in a folder, SharePoint, or Google Drive. Also trigger when an uploaded PDF/DOCX appears to be a commercial lease, or on "run the lease pipeline" / "process the leases" / "update my rent roll". Produces: 32-field abstract per lease (markdown single-doc; master XLSX batch with derived metrics, quality flags, portfolio analytics), Notion Tenant Database upsert, email summary to ggoldberg@oxfordra.net ONLY (routing canon 2026-06-10). Autonomous unattended operation — do not pause mid-run. v2.5 (2026-08-15: see Changelog)'
---

# Lease Abstraction Pipeline — Oxford Realty Advisors

Autonomous batch extraction of 32 structured data fields from every lease in a target folder. Outputs a master XLSX workbook, upserts Notion Tenant Database, and sends a completion summary. Designed for unattended execution.

---

## OPERATING PRINCIPLES

- **Never pause mid-run** for individual lease ambiguities. Mark the field `NOT FOUND`, flag it, and continue.
- **Exact language preferred** over paraphrase for fields: Permitted Use, Early Termination, Assignment/Subletting, Environmental Responsibility.
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

**Text PDF:** Extract via pdfplumber. **Scanned PDF:** Attempt pdfplumber first. If text yield &lt; 100 words, fall back to pytesseract OCR. Flag result as `OCR-EXTRACTED` in output — verify accuracy on flagged records. **DOCX:** Extract via python-docx. **Password-protected / corrupted:** Log in Tab 6 with error code. Skip.

---

## STEP 3 — 30-FIELD EXTRACTION (per lease)

Extract every field. Mark `NOT FOUND` if absent.

### PARTIES & PREMISES

#Field1Landlord entity name (+ state of formation if stated)2Tenant entity name (+ state of formation if stated)3Guarantor(s) — names, entity type, full/limited scope, burn-off terms4Property address — full street address5Suite/unit number (or "entire building")6Rentable square footage7Permitted use — exact lease language

### TERM

#Field8Lease commencement date9Lease expiration date10Total term length — calculate in months and years11Extension options — count, length each, notice period, rent mechanism (market/fixed/CPI)12Early termination rights — exact conditions, notice requirement, penalty formula13Holdover rate — % of base rent or "market rate"

### ECONOMICS

#Field14Base rent schedule — full escalation table (period, monthly rent, annual rent, $/SF/yr)15Escalation type — fixed %, CPI, market reset, flat16Free rent / concessions — duration, conditions, abatement structure17Security deposit — amount, form (cash/LOC), return conditions, interest accrual18Lease type — NNN / modified gross / gross / industrial gross19CAM structure — estimated annual CAM, mgmt fee cap, base year, controllable cap, exclusions20Tenant improvement allowance — $/SF or lump sum, conditions, disbursement deadline21Percentage rent — breakpoint, rate, reporting obligation (or N/A)22Late fee — grace period (days), fee amount or % of monthly rent

### LEGAL & RISK

#Field23Personal guaranty — present/absent, full/limited, burn-off date or conditions24Assignment/subletting — consent standard, recapture right, profit sharing (exact language)25Insurance requirements — coverage types, minimum amounts, additional insured, waiver of subrogation26Default cure periods — monetary (days), non-monetary (days), cross-default provisions27ROFR/ROFO — on what space, on what terms28SNDA/subordination — required/not required, non-disturbance language29Environmental responsibility — tenant scope, landlord scope, pre-existing carveout (exact language)30Condemnation/casualty — termination trigger, restoration obligation, rent abatement

### CAM RECOVERY (v2.3 addition — closes a gap found during the FY2025 CAM reconciliation review, 2026-07-12)

#Field31CAM Recovery Type — classify from Field 19's CAM structure language plus Field 18's lease type into exactly one of: "Full CAM + Tax + Insurance", "Tax Only", "Capped CAM", "Uncapped CAM", "NNN — All Pass-Through", "Gross — No Recovery", "Partial Recovery" (these 7 values are the live options on the Notion Tenant Database's CAM Recovery Type field — do not invent a new option). Inference guide: Lease Type=Gross with no CAM/tax passthrough language -> Gross — No Recovery. Lease Type=NNN with full CAM+tax+insurance passthrough and no cap mentioned -> NNN — All Pass-Through (or Uncapped CAM if the lease frames it as CAM specifically, not full NNN). Any "controllable expense cap" or "cap of X% per year" language -> Capped CAM. Tenant pays only real estate tax reimbursement, no CAM -> Tax Only. Passthrough applies to only some categories (e.g. CAM but not insurance) -> Partial Recovery. If the language doesn't clearly map to one option, mark NOT FOUND and flag for manual review rather than guessing — same discipline as every other field.32Tenant Pro-Rata Share — the tenant's % share of building/project CAM pool (usually stated as "Tenant's Proportionate Share" or a ratio of Field 6 Rentable SF to total building/project SF). Extract the stated percentage if given; if only the ratio/SF figures are given, calculate it and flag as CALCULATED (not stated) in output. NOT FOUND if neither is present.

---

## STEP 4 — DERIVED METRICS (per lease)

MetricFormulaRent PSF Year 1Annual base rent Yr 1 ÷ Rentable SFRent PSF Final YearAnnual base rent final year ÷ Rentable SFEscalation CAGR(Final yr rent / Yr 1 rent)^(1/(term yrs − 1)) − 1Total undiscounted base rentSum of all monthly base rent paymentsNPV of base rent (8%)PV of monthly payments discounted at 8%/yrEffective rent PSF(Total rent − free rent value) ÷ (SF × term yrs)Months until expirationFrom today → expiration date

---

## STEP 5 — QUALITY FLAGS (per lease)

SeverityFlag Condition🔴 CRITICALRent &lt; $4.00/SF NNN🔴 CRITICALMissing personal guaranty on leases &gt; $5,000/mo🔴 CRITICALAssignment permitted without landlord consent🔴 CRITICALNo default cure period stated🔴 CRITICALEnvironmental liability assigned entirely to landlord🟡 WARNINGRent &gt; $12.00/SF NNN — verify market justification🟡 WARNINGEscalation &lt; 2%/yr — below inflation target🟡 WARNINGEscalation &gt; 4%/yr — verify tenant acceptance🟡 WARNINGExtension notice period &lt; 9 months🟡 WARNINGHoldover rate &lt; 150% of base rent🟡 WARNINGSecurity deposit &lt; 2 months rent🟡 WARNINGNo SNDA provision🟡 WARNINGNo late fee provision🟡 WARNINGLease term &lt; 3 years🟡 WARNINGExtension option without market rent reset🔵 INFOAny field = NOT FOUND — manual review required🔵 INFOLease expires within 12 months — add to renewal pipeline🔵 INFOOCR-extracted document — verify accuracy

---

## STEP 6 — XLSX OUTPUT

**File naming:** per ORA's three standing naming schemas (ratified 2026-06-10; ORA Cowork Global Operating Prompt v3.0, 2026-07-16 — do NOT unify; supersedes the archived v2.0/2026-06-11 doc of the same ratified rule). The master abstract workbook is a session/analysis output → use `YYYY-MM-DD_[Topic]_[DocType]_v##.ext` in an `/outputs/` subfolder. (Supersedes the single unified "ORA File-Naming Standard 2026-05-14.md," which predates the 2026-06-10 three-schema ratification and is retained only as historical provenance.) **Save to:** SharePoint `Oxford Realty Advisors > Lease Abstracts > [Year]`

TabContents**1 — Master Rent Roll**One row/lease. All 30 fields + 7 derived metrics + flag counts. Freeze row 1. Auto-filter. Color: red fill = any CRITICAL, yellow = WARNING only, white = clean.**2 — Rent Schedules**One block/tenant: name, property, suite, then full escalation table (Year, Period Start, Period End, Monthly, Annual, PSF).**3 — Quality Flags Dashboard**One row/flag: File, Tenant, Property, Suite, Severity, Description.**4 — Expiration Heatmap**Count of expirations by quarter, next 5 years. Highlight quarters with 3+ expirations.**5 — Portfolio Analytics**WALT (by SF), avg rent PSF (weighted by SF), occupancy-weighted total rent, % with guaranty, % with ROFR, % NNN vs. gross, rent PSF std dev with outlier flags (&gt;1.5 SD).**6 — Skipped Files**File name, reason, timestamp.

---

## STEP 7 — NOTION UPSERT

Target database: ORA Notion Tenant Database. Logic: update record if tenant already exists (match on Tenant Name + Property + Suite); create new record if no match. Do not overwrite records where Notion shows a more recent modified date than the lease document, unless Gabriel explicitly instructs.

Notion FieldSource FieldTenant NameField 2 — Tenant entity namePropertyField 4 — Property addressSuiteField 5 — Suite/unitLease StartField 8 — Commencement dateLease EndField 9 — Expiration dateCurrent Rent (monthly)Field 14 — Base rent Year 1, monthlyRent PSFDerived — Rent PSF Year 1Lease TypeField 18Renewal OptionsField 11GuarantyField 23 — Yes/NoDays Until ExpirationDerived — Months until expiration × 30Flag CountTotal flags (all severities)Flag StatusHighest severity: Critical / Warning / CleanCAM Recovery TypeField 31 (v2.3)Tenant Pro-Rata ShareField 32 (v2.4)

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
- **document-assembly:** Use extracted data to auto-populate estoppels, renewal offers, lease addenda.
- **lease-renewal-pipeline:** Auto-trigger for any lease flagged as expiring within 12 months.

---

## REFERENCE FILES

See `references/extraction-edge-cases.md` for guidance on:

- Leases with multiple amendment documents
- Side letters and letter agreements
- Leases referencing exhibits not included in the file
- Ground leases and master lease structures

## Changelog

- v2.5 (2026-08-15): LOW fix (Skill Text Audit finding F9) + new finding (coverage-gap-3, stale file-naming-standard citation). Moved the v2.4/v2.3 changelog prose that had accumulated in the description field down here (both already existed in this section, so the description copies were pure duplication); description now carries a single trailing version tag. Step 6's file-naming citation updated from the archived "ORA Cowork Global Settings v2.0" (2026-06-11) to the current "ORA Cowork Global Operating Prompt v3.0" (2026-07-16) — the underlying three-schema rule is unchanged, only the version/document-name citation; same fix applied to the companion `SCHEDULED_TASK.md`. No extraction field, derived metric, or quality flag changed.
- v2.4 (2026-08-12): Repointed the cross-skill `rent-comp` reference (retired 2026-08-05) at `acquisition-underwriting`, which absorbed the comp-grid discipline on 2026-08-12 per Gabriel's scoped-restore ruling. Below/above-market rent PSF flags now have a live method again. No extraction field, derived metric, or quality flag changed.

- v2.3 (2026-07-12): added Fields 31 (CAM Recovery Type) + 32 (Tenant Pro-Rata Share) — the FY2025 CAM reconciliation data-readiness review (ora-cam-reconciliation-annual, 2026-07-12) found these two fields blocking a defensible reconciliation (0/139 and 45/138 leases populated respectively) with no existing extraction path to backfill them. Notion Tenant Database's "CAM Recovery Type" select field already existed with 7 live options (unused); added a matching "Tenant Pro-Rata Share" number/percent property to the same data source. STEP 7 Notion mapping updated; frontmatter field-count bumped 30->32.
- v2.2 (2026-07-08): HIGH fix (Skill Text Audit finding 5) — Step 6 file-naming citation repointed from the superseded single "ORA File-Naming Standard 2026-05-14.md" to the ratified three-schema doctrine (ORA Cowork Global Settings v2.0, 2026-06-10/11); master workbook classified as a session/analysis output. Also (MEDIUM fix, finding 10): companion `SCHEDULED_TASK.md` version stamp (was 1.0 / 2026-04-04) synced to this file's version.
