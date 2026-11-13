# PSA Fact Schema — Canonical 12-Section Structure

This is the authoritative schema for Oxford Realty Advisors' PSA Fact Table. Every PSA Reconciliation produces a workbook whose rows follow the identifiers, sections, and field names below. Do not rename fields. Add new fields only at the end of a section and assign the next Fact # in sequence.

Every Example value in this file is synthetic: a fictional multi-parcel, dual-jurisdiction industrial deal built to show format and arithmetic (P-037 and P-038 derive from P-031, P-024 and P-026). Never paste a real deal's facts here; `tools/test_example_registers_synthetic.py` enforces it.

Numbering convention: `P-###` for Fact IDs, zero-padded to 3 digits, monotonically increasing. Deleted facts are tombstoned (row retained, Value = "DEPRECATED", Note = reason) — never re-used.

## Data types

- **Text**: free-form UTF-8. Always stored in Excel as text even if numeric-looking (e.g., parcel IDs, instrument numbers).
- **Number**: stored as native Excel number; apply currency / SF / acreage / per-SF format per the field.
- **Date**: stored as Excel date serial; format `mm/dd/yyyy`.
- **Boolean**: `Yes` / `No` / `N/A` — always text, never TRUE/FALSE.
- **Enum**: one value from an explicit set — never a paraphrase.

---

## SECTION 1 — PARTIES (P-001 to P-015)

| Fact # | Field | Type | Typical PSA Source | Example (synthetic) |
|---|---|---|---|---|
| P-001 | Purchaser — Contracting Entity | Text | Preamble | Example Buyer Holdings, LLC (fictional) |
| P-002 | Purchaser — Trading Name / Notice Name | Text | §17 (Notice) | Example Realty Advisors, LLC (fictional) |
| P-003 | Purchaser — Address (Notice) | Text | §17 | 100 Example Way, Anytown, MD 20000 |
| P-004 | Purchaser — Principal / Attn | Text | §17 | [Principal Name], President (example) |
| P-005 | Purchaser — Principal Email | Text | §17 | principal@buyer.example |
| P-006 | Purchaser — Secondary Contact | Text | §17 (cc line) | [Secondary Contact Name] — acquisitions@buyer.example |
| P-007 | Buyer's Counsel — Firm | Text | §17 (with a copy to) | Example Law Group, LLC (fictional) |
| P-008 | Buyer's Counsel — Attorney | Text | §17 | [Attorney Name], Esq. (example) |
| P-009 | Buyer's Counsel — Email | Text | §17 | counsel@buyerlaw.example |
| P-010 | Seller — Entity | Text | Preamble | Example Seller Partnership, LLC (fictional Ohio LLC) |
| P-011 | Seller — Address (Notice) | Text | §17 | 200 Example Street, Anytown, OH 43000 |
| P-012 | Seller — Signatory | Text | Signature block | [Signatory Name] (example) |
| P-013 | Seller — Signatory Title | Text | Signature block | [Title, e.g. Managing Member] |
| P-014 | Seller's Counsel — Firm + Attorneys + Emails | Text | §17 (with a copy to) | Example Seller Counsel LLP (fictional) — [Attorney A] & [Attorney B] — a@sellerlaw.example / b@sellerlaw.example |
| P-015 | Broker(s) — Firm + Agent + Representing Party | Text | Brokerage article | [Agent Name] — Example Brokerage Co. (fictional) — representing Seller; Seller pays under separate agreement |

---

## SECTION 2 — PROPERTY (P-016 to P-030)

| Fact # | Field | Type | Typical PSA Source | Example (synthetic) |
|---|---|---|---|---|
| P-016 | Property — Street Addresses | Text | Preamble + Exhibit A | 100-140 Example Street (north) + 101-125 Example Street (south), Anytown, OH 43000 |
| P-017 | Parcel ID #1 | Text | Exhibit A | EXAMPLE-PARCEL-A |
| P-018 | Parcel ID #2 | Text | Exhibit A | EXAMPLE-PARCEL-B |
| P-019 | Parcel ID #3 | Text | Exhibit A | EXAMPLE-PARCEL-C |
| P-020 | Parcel ID #4 | Text | Exhibit A | — (3-parcel example) |
| P-021 | Parcel ID #5 | Text | Exhibit A | — (3-parcel example) |
| P-022 | Parcel count | Number | Preamble | 3 |
| P-023 | Building count | Number | Preamble | 4 |
| P-024 | Total SF (governing) | Number | Preamble | 150,000 |
| P-025 | Total SF (exhibit component sum) | Number | Exhibit A tract component sum | 148,800 (flag variance) |
| P-026 | Total Acres | Number | Preamble / Exhibit A | 12.00 |
| P-027 | Jurisdiction #1 | Text | Exhibit A | City of Anytown (example) |
| P-028 | Jurisdiction #2 (if multi) | Text | Exhibit A | Village of Example Heights (example) |
| P-029 | Zoning by Jurisdiction | Text | Exhibit A + DD | Anytown M (Manufacturing) / Example Heights LI (Limited Industrial) |
| P-030 | Recorded Deed Reference | Text | Exhibit A header | Inst. #[instrument no.] Example Co. OH (mm/dd/yyyy) |

---

## SECTION 3 — ECONOMICS (P-031 to P-045)

| Fact # | Field | Type | Typical PSA Source | Example (synthetic) |
|---|---|---|---|---|
| P-031 | Purchase Price | Number (USD) | §3 | $3,000,000.00 |
| P-032 | All-Cash? | Boolean | §5 / §3 | Yes |
| P-033 | Financing Contingency | Boolean | §4 or §6 | No |
| P-034 | Earnest Money Deposit | Number (USD) | §2.1 | $150,000.00 |
| P-035 | EMD Refundability | Text | §4.1 / §2 | Refundable during Feasibility Period; non-refundable post |
| P-036 | Escrow Agent | Text | §2.1 | Example Title Services (fictional), 300 Example Ave., Anytown OH 43000, (555) 555-0100 |
| P-037 | Price per SF | Number | Derived (P-031 ÷ P-024) | $20.00 |
| P-038 | Price per Acre | Number | Derived (P-031 ÷ P-026) | $250,000 |
| P-039 | Environmental — Buyer Cap | Number (USD) | Environmental section | $50,000 |
| P-040 | Environmental — Seller Credit Max | Number (USD) | Environmental section | $10,000 |
| P-041 | Environmental — Termination Threshold | Number (USD) | Environmental section | $75,000 |
| P-042 | Closing Cost Allocation | Text (enum) | §8 | Split 50/50 (PSA §8.2) — NOT standard county custom |
| P-043 | Title Insurance Cost Allocation | Text | §7 | Split 50/50 |
| P-044 | Counsel Fees | Text (enum) | §8.1 | Each party own |
| P-045 | Broker Commission — Seller-paid? | Boolean | Brokerage article | Yes — Seller pays under separate agreement |

---

## SECTION 4 — KEY DATES (P-046 to P-062)

All dates derived from a single root input (Effective Date P-046). When re-running after an amendment, change only P-046 and let the rest recompute.

| Fact # | Field | Type | Derivation / Source |
|---|---|---|---|
| P-046 | Effective Date (root input) | Date | Latest signature block date |
| P-047 | Deposit Due | Date | Effective Date + 5 business days (§2.1) |
| P-048 | Seller Document Delivery Due (§4.3) | Date | Effective Date + 5 business days |
| P-049 | Seller Document Delivery Due (§6) | Date | Effective Date + 5 calendar days |
| P-050 | Seller Authority Package (§15.1.16) Due | Date | Effective Date + 5 calendar days — FP CLOCK PAUSED UNTIL DELIVERED |
| P-051 | Title Commitment Delivery | Date | Effective Date + 10 calendar days (§7) |
| P-052 | Phase II Order-By | Date | Effective Date + 5 calendar days (§4.3) |
| P-053 | Phase I Target Delivery | Date | Negotiated with consultant; track separately |
| P-054 | Phase II Target Delivery | Date | Negotiated with consultant; track separately |
| P-055 | FP Earliest Expiry | Date | Effective Date + 30 calendar days (§4.1) |
| P-056 | FP Hard Outer Limit | Date | Effective Date + 60 calendar days (§4.1) |
| P-057 | FP Actual Expiry | Date | Later of (P-055, Phase II receipt + 5 BD), capped at P-056 |
| P-058 | Closing Outer Cap — Explicit Date | Date | §9.1 ("but in no case beyond [BLANK]") — often BLANK; record as N/A and flag |
| P-059 | Closing Outer Cap — Source of Hard Stop | Text | Seller lender letter, calendar date, or "None — §9.1 blank" |
| P-060 | Target Close Date | Date | FP Actual Expiry + 5 days (§9.1) |
| P-061 | Proration Date | Date | §8.2 / §10 | Midnight before Closing (per §8.2) |
| P-062 | Offer Expiration (§26) | Date | §26 blank in execution version — typically moot |

---

## SECTION 5 — PSA MECHANICS (P-063 to P-078)

Each mechanics row is either "present" or "not present" for the executed PSA. If present, capture any numeric thresholds or named carve-outs.

| Fact # | Field | Type | Typical PSA Source | Notes |
|---|---|---|---|---|
| P-063 | AS-IS Conveyance? | Boolean | §25 | Yes, but carve-outs apply (see P-064) |
| P-064 | AS-IS Carve-Outs | Text | §25 | Express reps, vacancy/make-safe, §22 survival |
| P-065 | Material Adverse Change (MAC) Triggers | Text | §8 | 10% NOI drop · tenant loss >5K SF · material uninsured casualty · new liens · insurance lapse |
| P-066 | Vacancy Delivery Scope | Text | §9.2(d) | Specific buildings + SF to be delivered vacant |
| P-067 | Make-Safe Requirements | Text | §9.2(e) | Anchor bolts removed; ¼"+ steel plates; NEC-compliant electrical; plumbing capped/pressure-tested; drains functional; envelope sealed; floor patched/leveled; PE cert + unconditional lien waivers |
| P-068 | Seller Default Remedy | Text | §11.3 | Deposit return + out-of-pocket up to $[cap] (uncapped on Willful Default) OR specific performance |
| P-069 | Purchaser Default Remedy | Text | §11.2 | Seller retains Deposit; sole remedy |
| P-070 | Hazardous Materials Disclosure | Text | §15.1.10 | e.g., Seller affirmatively discloses property "may contain Hazardous Materials" |
| P-071 | §13 Violation Compliance Owner | Text (enum) | §13 | Seller (Seller complies with municipal violation notices at Closing) |
| P-072 | §15.1.16 Authority Package — FP Pause | Boolean | §15.1.16 | Yes (FP clock paused until Seller delivers authority pkg) |
| P-073 | Assignment by Purchaser | Text | §23 | Freely assignable to any entity |
| P-074 | Assignment by Seller | Text | §23 or silent | Typically silent / not permitted |
| P-075 | Seller §1031 Cooperation Provision | Boolean | §29 | Yes — Seller reserves right; Buyer cooperates at no cost |
| P-076 | Buyer §1031 Provision | Boolean | §29 or silent | Typically silent — confirm Buyer's intent separately |
| P-077 | Confidentiality — Permitted Disclosures | Text | §27 | Attorneys, accountants, mortgage holders, subpoena |
| P-078 | Governing Law | Text | §18 | State of [property state] |

---

## SECTION 6 — SURVIVAL & WARRANTIES (P-079 to P-086)

| Fact # | Field | Type | Typical PSA Source | Example (synthetic) |
|---|---|---|---|---|
| P-079 | General Reps Survival | Text / Months | §22(a) | 18 months |
| P-080 | Environmental Reps Survival | Text / Months | §22(b) | 36 months |
| P-081 | Fundamental Reps Survival (authority, title, liens, OFAC) | Text / Months | §22(c) | Indefinite |
| P-082 | Rep Basket / Threshold | Number or "None" | §22 or rep-specific | None (or $[threshold]) |
| P-083 | Rep Cap | Number or "None" | §22 | None (or $[cap]) |
| P-084 | OFAC Compliance Rep | Boolean | §15.1.13 | Yes |
| P-085 | No-Bankruptcy Rep (Seller) | Boolean | §15.1.1 | Yes |
| P-086 | Authority Rep | Boolean | §15.1.5 / §15.1.6 | Yes |

---

## SECTION 7 — LITIGATION & GOVERNMENT NOTICES (P-087 to P-099)

Populate one row per disclosed item. Numbering resets per deal — stay sequential in the table.

| Fact # | Field | Type | Typical Source | Example (synthetic) |
|---|---|---|---|---|
| P-087 | Case / Notice Type | Text (enum) | Exhibit F | Litigation / Lis Pendens / Agency Notice / Code Enforcement / Foreclosure |
| P-088 | Case Caption or Notice Title | Text | Exhibit F | Example County Board of Health v. Example Seller Partnership LLC (fictional) |
| P-089 | Case / Instrument Number | Text | Exhibit F | [case no.] / Inst. #[instrument no.] |
| P-090 | Court / Agency | Text | Exhibit F | Example County Court of Common Pleas (example) |
| P-091 | Filed Date | Date | Exhibit F | [mm/dd/yyyy] |
| P-092 | Current Status | Text | Exhibit F | Consent order entered [date]; follow-up compliance inspection pending |
| P-093 | Property-Specific? | Boolean | Exhibit F | Yes |
| P-094 | Seller §13 Cure Obligation? | Boolean | PSA §13 x Exhibit F | Yes |
| P-095 | Title-Impacting? | Boolean | Judgment lookup | Yes (Lis Pendens recorded) |
| P-096 | Co-Defendant Tenant? | Text | Exhibit F | N/A |
| P-097 | Known Dollar Exposure | Number or N/A | Exhibit F / counsel memo | TBD |
| P-098 | Dismissed / Resolved? | Boolean | Exhibit F | No |
| P-099 | Action Required at Closing | Text | Derived | Attorney review; title commitment must extinguish Lis Pendens; escrow if uncured |

**Recurring subtypes to capture as separate rows:**
- Municipal code notices (per building / per citation)
- Zoning notices
- Graphics / signage code notices
- Environmental agency approvals or notices of violation
- Pending litigation (tort, contract, landlord-tenant, environmental)
- Foreclosure / lender actions
- Lis pendens / mechanic's lien / judgment

---

## SECTION 8 — TENANTS & LEASES (P-100 to P-119)

One row block per tenant. Allocate 4 rows per tenant across the same Fact # span (e.g., P-100 to P-103 = Tenant 1; P-104 to P-107 = Tenant 2). Use Field to differentiate.

Per tenant, capture:

| Field | Type | Source | Example (synthetic tenant) |
|---|---|---|---|
| Tenant Name | Text | Exhibit B / D | Example Tenant A Co. (fictional) |
| Premises Address | Text | Exhibit B | 201-205 Example Street |
| Premises SF | Number | Exhibit B | 8,000 |
| Monthly Base Rent (Y1) | Number | Exhibit D | $4,000.00 |
| Annual Base Rent (Y1) | Number | Exhibit D | $48,000.00 |
| Escalation Structure | Text | Exhibit D | 3% every 2 yrs from Y5 |
| Expiration Date | Date | Exhibit B / D | 06/30/2029 |
| Options to Renew | Text | Exhibit D | 2 × 5-yr |
| Guarantor | Text | Exhibit B / lease | — |
| Security Deposit | Number | lease | $[amount] |
| In-Place at Close? | Boolean | §9.2(d) | Yes |
| Lease Cancellation Executed? | Boolean | separate doc | No |
| Body-vs-Exhibit Discrepancy Flag | Text | Reconciliation | e.g., "Example Tenant B lease body states 06/30/2029; Exhibit D states 06/30/2028 — reconcile" |

---

## SECTION 9 — CLOSING DELIVERABLES (P-120 to P-135)

Each §9.3 (Seller) and §9.4 (Purchaser) deliverable as a discrete row.

| Fact # | Field | Type | Typical Source |
|---|---|---|---|
| P-120 | Special Warranty Deed (Seller) | Boolean | §9.3(a) |
| P-121 | Assignment of Leases (Seller) | Boolean | §9.3(b) + Exhibit C |
| P-122 | Owner's Affidavit & Gap Indemnity (Seller) | Boolean | §9.3(c) |
| P-123 | C/Os + Permits Transfer (Seller) | Boolean | §9.3(d) |
| P-124 | Proof of Tax Payment (Seller) | Boolean | §9.3(e) |
| P-125 | FIRPTA Non-Foreign Affidavit (Seller) | Boolean | §9.3(f) |
| P-126 | Substitute 1099-S (Seller) | Boolean | §9.3(g) |
| P-127 | Settlement Statement (Seller) | Boolean | §9.3(h) |
| P-128 | Authorizing Resolution (Seller) | Boolean | §9.3(i) |
| P-129 | Updated Certified Rent Roll (Seller) | Boolean | §9.3(k) |
| P-130 | Tenant Notification Letters (Seller) | Boolean | §9.3(l) + Exhibit E |
| P-131 | Bring-Down Certificate (Seller) | Boolean | §15.1.17 |
| P-132 | Purchase Price Wire (Purchaser) | Boolean | §9.4(a) |
| P-133 | Purchaser Settlement Statement (Purchaser) | Boolean | §9.4(b) |
| P-134 | Purchaser Entity Authority Package (Purchaser) | Boolean | §9.4(b) |
| P-135 | Other Title-Company-Required Docs (Purchaser) | Boolean | §9.4(b) |

---

## SECTION 10 — EXCLUSIONS (P-136 to P-142)

| Fact # | Field | Type | Typical Source | Example (synthetic) |
|---|---|---|---|---|
| P-136 | Excluded Equipment? | Boolean | §25.1 | Yes |
| P-137 | Excluded Equipment — Description | Text | §25.1 | Example seller-owned packaging line, conveyors and racking |
| P-138 | Excluded Equipment — Removal Cost to Buyer? | Text (enum) | §25.1 | None |
| P-139 | Excluded Fixtures vs. Personal Property | Text | §25.1 + schedule | Personal property + trade fixtures |
| P-140 | Post-Removal Restoration Obligation | Text | §25.1 + §9.2(e) | Yes — Seller repairs damage from removal; make-safe applies |
| P-141 | Pre-Closing Walkthrough Required? | Boolean | §9.2(e) or §25.1 | Yes (recommended) |
| P-142 | Tenant-Owned Equipment List | Text | Per-tenant lease | Reference lease exhibits |

---

## SECTION 11 — NOTICES & MISCELLANEOUS (P-143 to P-150)

| Fact # | Field | Type | Typical Source | Example (synthetic) |
|---|---|---|---|---|
| P-143 | Notice Delivery Methods | Text | §17 | Email OR certified mail return receipt OR Federal Express |
| P-144 | Notice Deemed-Received Rule | Text | §17 | Email: date of email; FedEx: next business day; certified mail: actual receipt |
| P-145 | Time is of the Essence | Boolean | §28 | Yes |
| P-146 | Electronic Signatures / Counterparts | Boolean | §21 | Yes |
| P-147 | Memorandum of Contract — Recordable? | Boolean | §21.10 | **No** (example: a PSA that prohibits recording — note deviation from ORA standard) |
| P-148 | Dispute Resolution | Text | §20 | Prevailing party entitled to fees + costs |
| P-149 | Force Majeure / COVID-19 Tolling | Boolean | §21.11 | Yes |
| P-150 | Integration / Entire Agreement | Boolean | §21.2 | Yes |

---

## SECTION 12 — EXHIBITS (P-151+)

One row per exhibit referenced in the PSA. Confirm each is attached.

| Fact # | Field | Type | Example (synthetic) |
|---|---|---|---|
| P-151 | Exhibit A — Legal Description | Text | Attached — 12.00 AC across 3 Tracts |
| P-152 | Exhibit B — Existing Leases Schedule | Text | Attached — 3 tenants (Example Tenants A, B, C) |
| P-153 | Exhibit C — Assignment & Assumption of Leases (form) | Text | Attached |
| P-154 | Exhibit D — Rent Roll | Text | Attached |
| P-155 | Exhibit E — Tenant Notification Letter (form) | Text | Attached |
| P-156 | Exhibit F — Litigation and Government Notices | Text | Attached — see Section 7 detail |

If a PSA uses different exhibit letters (e.g., PSA with Exhibits G, H, I, J), map by content not label. Record the letter used in a Note.

---

## Row count expectations by deal complexity

| Deal | Approx. Rows |
|---|---|
| Single-parcel single-tenant industrial | ~95 |
| Multi-parcel multi-tenant industrial (typical Oxford deal) | ~125–155 |
| Portfolio transaction or dual-jurisdiction | 160+ |

A Fact Table under 90 rows for a multi-parcel deal almost certainly has omissions — review each section.

---

## Reconciliation memory

When re-running this skill after a PSA amendment, preserve the original Fact Table as v01 and produce v02. The v02 Fact Table carries an "Amendment Delta" column noting every row whose Value changed, with before/after. Downstream cascade packs built from v02 must reference v02 only — never mix.
