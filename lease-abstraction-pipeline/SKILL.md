---
name: lease-abstraction-pipeline
description: "Batch lease abstraction and rent roll data extraction for Oxford Realty Advisors. Use this skill whenever the user mentions: abstract leases, parse leases, extract lease data, process lease folder, batch lease, lease pipeline, lease data extraction, run lease abstraction, pull lease terms from folder, parse all leases, lease parsing, update rent roll from leases, scheduled lease scan, or any request to systematically extract structured data from multiple commercial lease documents stored in a folder, SharePoint directory, or Google Drive. Also trigger when the user says 'run the lease pipeline', 'process the leases', or 'update my rent roll'. Produces: master XLSX workbook (30 fields per lease, derived metrics, quality flags, portfolio analytics), Notion Tenant Database upsert, and email summary to ze@oxfordra.net. Designed for autonomous unattended operation — do not pause mid-run for individual lease clarifications. v1.2"
---

# Lease Abstraction Pipeline — Oxford Realty Advisors

Autonomous batch extraction of 30 structured data fields from every lease in a target folder. Outputs a master XLSX workbook, upserts Notion Tenant Database, and sends a completion summary. Designed for unattended execution.

---

## OPERATING PRINCIPLES

- **Never pause mid-run** for individual lease ambiguities. Mark the field `NOT FOUND`, flag it, and continue. This rule is absolute — do not pause even if more than 50% of a lease's fields are NOT FOUND; log the lease in Tab 6 with reason "Low extraction yield (<50% of fields)" and continue.
- **Exact language preferred** over paraphrase for fields: Permitted Use, Early Termination, Assignment/Subletting, Environmental Responsibility. "Exact language" means verbatim quotation with a maximum length of 500 characters per field; if the provision exceeds 500 characters, extract the operative clause verbatim and append `[...TRUNCATED — see source document §X]`.
- **Conflict rule:** If two conflicting values exist for the same field (e.g., rent in body vs. exhibit), extract both, flag discrepancy, note source of each. When both values are numeric, use the value from the most recent amendment as the primary value in Tab 1 Master Rent Roll and record the alternate in Tab 3 Quality Flags Dashboard.
- **Date format:** MM/DD/YYYY throughout. If a lease expresses a date as "the first day of the month following Commencement," resolve it to an actual MM/DD/YYYY date using the Commencement Date as the anchor. If it cannot be resolved deterministically, enter `NOT FOUND` and flag.
- **Currency:** Two decimal places, no rounding. Enter as numeric values (not strings with "$") so XLSX can aggregate.
- **SF:** Integer with comma separator (e.g., 12,500). Store as integer in XLSX for aggregation; the comma is display formatting only.
- **Notification:** Always email ze@oxfordra.net on completion (or failure). For manually triggered runs, draft the email and wait for approval before sending. For scheduled unattended runs (see Scheduled Task section), send automatically via Gmail MCP without confirmation.

---

## STEP 1 — FOLDER INVENTORY

Locate the target folder. Default paths in strict priority order (use first available):
1. Path explicitly specified by Ze in the trigger message (highest priority)
2. `/mnt/user-data/uploads/` (if files uploaded directly in the current session)
3. SharePoint: `Oxford Realty Advisors > Master Lease Database`

If none of the three are accessible, fail fast: email ze@oxfordra.net with subject "Lease Pipeline — Folder Not Accessible" and halt.

List all files. Log: total count, file types (PDF / DOCX / other), estimated scanned PDF count (defined as a PDF where pdfplumber yields <100 words on page 1). Print inventory summary before processing begins.

Skip (and log in Tab 6): files that are not leases (detected by keyword absence — if none of "Lease", "Landlord", "Tenant", "Premises" appear in the first 2,000 characters, treat as non-lease), corrupted files (any file that raises an exception on open), password-protected files.

---

## STEP 2 — DOCUMENT INGESTION (per file)

**Text PDF:** Extract via pdfplumber.
**Scanned PDF:** Attempt pdfplumber first. If text yield < 100 words across the entire document, fall back to pytesseract OCR. Flag result as `OCR-EXTRACTED` in output — verify accuracy on flagged records.
**DOCX:** Extract via python-docx.
**Password-protected / corrupted:** Log in Tab 6 with error code. Skip.

---

## STEP 3 — 30-FIELD EXTRACTION (per lease)

Extract every field. Mark `NOT FOUND` if absent — do not substitute market-standard assumptions for missing values.

### PARTIES & PREMISES
| # | Field |
|---|-------|
| 1 | Landlord entity name (+ state of formation if stated) |
| 2 | Tenant entity name (+ state of formation if stated) |
| 3 | Guarantor(s) — names, entity type, full/limited scope, burn-off terms |
| 4 | Property address — full street address |
| 5 | Suite/unit number (or "entire building") |
| 6 | Rentable square footage |
| 7 | Permitted use — exact lease language |

### TERM
| # | Field |
|---|-------|
| 8 | Lease commencement date |
| 9 | Lease expiration date |
| 10 | Total term length — calculate in months and years |
| 11 | Extension options — count, length each, notice period, rent mechanism (market/fixed/CPI) |
| 12 | Early termination rights — exact conditions, notice requirement, penalty formula |
| 13 | Holdover rate — % of base rent or "market rate" |

### ECONOMICS
| # | Field |
|---|-------|
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
|---|-------|
| 23 | Personal guaranty — present/absent, full/limited, burn-off date or conditions |
| 24 | Assignment/subletting — consent standard, recapture right, profit sharing (exact language) |
| 25 | Insurance requirements — coverage types, minimum amounts, additional insured, waiver of subrogation |
| 26 | Default cure periods — monetary (days), non-monetary (days), cross-default provisions |
| 27 | ROFR/ROFO — on what space, on what terms |
| 28 | SNDA/subordination — required/not required, non-disturbance language |
| 29 | Environmental responsibility — tenant scope, landlord scope, pre-existing carveout (exact language) |
| 30 | Condemnation/casualty — termination trigger, restoration obligation, rent abatement |

---

## STEP 4 — DERIVED METRICS (per lease)

| Metric | Formula |
|--------|---------|
| Rent PSF Year 1 | Annual base rent Yr 1 ÷ Rentable SF |
| Rent PSF Final Year | Annual base rent final year ÷ Rentable SF |
| Escalation CAGR | (Final yr rent / Yr 1 rent)^(1/(term yrs − 1)) − 1 |
| Total undiscounted base rent | Sum of all monthly base rent payments |
| NPV of base rent (8%) | PV of monthly payments discounted at 8%/yr |
| Effective rent PSF | (Total rent − free rent value) ÷ (SF × term yrs) |
| Months until expiration | From today → expiration date |

If any input field is `NOT FOUND`, set the dependent derived metric to `NOT FOUND` and flag. Do not compute a derived metric using a zero or assumed substitute.

---

## STEP 5 — QUALITY FLAGS (per lease)

| Severity | Flag Condition |
|----------|---------------|
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
| 🔵 INFO | OCR-extracted document — verify accuracy |

Flag thresholds compare against fully extracted values only. If the input field is `NOT FOUND`, do not trigger the CRITICAL or WARNING flag for that condition; trigger only the `NOT FOUND` INFO flag.

---

## STEP 6 — XLSX OUTPUT

**File name:** `ORA_LeaseAbstract_Batch_[YYYYMMDD]_v1.0.xlsx` — replace `[YYYYMMDD]` with the current date in that format (e.g., `ORA_LeaseAbstract_Batch_20260416_v1.0.xlsx`).
**Save to:** SharePoint `Oxford Realty Advisors > Lease Abstracts > [Year]` — replace `[Year]` with the current 4-digit year.

| Tab | Contents |
|-----|----------|
| **1 — Master Rent Roll** | One row/lease. All 30 fields + 7 derived metrics + flag counts. Freeze row 1. Auto-filter. Color: red fill = any CRITICAL, yellow = WARNING only (no CRITICAL), white = no CRITICAL or WARNING flags. |
| **2 — Rent Schedules** | One block/tenant: name, property, suite, then full escalation table (Year, Period Start, Period End, Monthly, Annual, PSF). |
| **3 — Quality Flags Dashboard** | One row/flag: File, Tenant, Property, Suite, Severity, Description. |
| **4 — Expiration Heatmap** | Count of expirations by quarter, next 5 years (20 quarters from current quarter). Highlight quarters with 3 or more expirations. |
| **5 — Portfolio Analytics** | WALT (by SF), avg rent PSF (weighted by SF), occupancy-weighted total rent, % with guaranty, % with ROFR, % NNN vs. gross, rent PSF std dev with outlier flags (any value >1.5 standard deviations from the SF-weighted mean). |
| **6 — Skipped Files** | File name, reason, timestamp. |

---

## STEP 7 — NOTION UPSERT

Target database: ORA Notion Tenant Database.
Match logic: update record if tenant already exists (match criteria below); create new record if no match.

**Match criteria (all three must match exactly, case-insensitive):**
1. Tenant Name (Notion field) == Field 2 Tenant entity name
2. Property (Notion field) == Field 4 Property address
3. Suite (Notion field) == Field 5 Suite/unit

**Overwrite rule:** If the Notion record's "Last Modified" timestamp is more recent than the source lease document's file modification date, DO NOT overwrite any field. Instead, log the conflict in Tab 6 with reason "Notion record newer than lease doc — manual review required." The only way to override this is an explicit instruction from Ze in the trigger message (e.g., "force overwrite Notion").

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
| Flag Status | Highest severity present: Critical / Warning / Clean |

---

## STEP 8 — COMPLETION NOTIFICATION

After all processing is complete, generate an email to ze@oxfordra.net with the content below. For manually triggered runs, save as draft and wait for approval. For scheduled unattended runs, send automatically via Gmail MCP.

**Subject:** `ORA Lease Abstraction Complete — N leases processed — [DATE]` — replace `N` with the actual count and `[DATE]` with today's MM/DD/YYYY.

**Body:**
```
Run completed: [timestamp — ISO 8601 format]
Leases processed: [integer count]
Skipped files: [integer count] (see Tab 6)
Total fields NOT FOUND: [integer count] (requires manual review)
Critical flags: [integer count]
Warning flags: [integer count]
Leases expiring within 12 months: [integer count]

Output: [SharePoint URL to the XLSX file]
Notion: [N] records updated, [N] records created

Top issues requiring your review:
1. [Highest-severity CRITICAL flag summary — one line]
2. [Second CRITICAL flag, or highest WARNING if fewer than 2 CRITICALs]
3. [Third flag, in the same priority order; omit this line entirely if fewer than 3 flags exist]
```

Any bracketed field in the body above must be replaced with an actual value before the email is saved/sent. If a required value is unavailable, enter `NOT AVAILABLE` — do not emit the literal bracket text.

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
Expiring ≤12 months:   [N]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
XLSX: [SharePoint URL]
Notion: [N] updated / [N] created
```

Replace every `[N]` and `[SharePoint URL]` placeholder with actual values before printing. Do not emit the literal bracket text.

---

## CROSS-SKILL INTEGRATION

- **legal-intelligence:** Reference clause library when flagging non-standard provisions. Compare against Oxford preferred positions.
- **tenant-intelligence:** Feed extracted data into tenant risk scoring for existing portfolio tenants.
- **rent-comp:** Compare extracted rent PSF against current market comps for below/above-market flags.
- **document-assembly:** Use extracted data to auto-populate estoppels, renewal offers, lease addenda.
- **lease-renewal-pipeline:** Auto-trigger for any lease flagged as expiring within 12 months.

---

## REFERENCE FILES

See `references/extraction-edge-cases.md` for guidance on:
- Leases with multiple amendment documents
- Side letters and letter agreements
- Leases referencing exhibits not included in the file
- Ground leases and master lease structures
