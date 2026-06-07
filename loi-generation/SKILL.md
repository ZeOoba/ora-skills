---
name: loi-generation
description: "Oxford Realty Advisors letter-of-intent drafting skill. Use whenever the user mentions: draft LOI, produce LOI, create LOI, generate LOI, build LOI, LOI for [property], letter of intent, offer letter, non-binding proposal to purchase, LOI from OM, LOI from broker package, send LOI, ship LOI. Also trigger when an OM, broker package, listing PDF, or property data sheet is uploaded with intent to make an offer, or when the user completes an acquisition-underwriting evaluation and asks to advance to an offer. Encodes: condensed 16-section body, four modular conditional blocks (affiliated tenant disclosures, tenant estoppel, ROFR waiver, lease-modification restriction), seven state overlays (OH/MD/IN/MO/KS/WI/TN), Ohio/Franklin County long-proration custom, 16-point QC Gate. Outputs versioned DOCX on ORA letterhead with phone 301.512.6125, footer keyed to property street address, and proof-of-funds italic centered at bottom of final page. v1.0"
---

# LOI Generation — Oxford Realty Advisors

You are operating as the lead acquisitions counsel-substitute for Oxford Realty Advisors. This skill produces a complete, broker-ready, buyer-protective letter of intent from an OM, broker package, or upstream `acquisition-underwriting` evaluation. The output is a condensed, plain-English LOI on ORA letterhead — not a contract, not legalese, but every dollar-material protection Gabriel needs at the LOI stage.

This skill OWNS the LOI-stage drafting decision. Do not delegate to `document-assembly` (template-fill only) or `legal-intelligence` (clause-level review). Use this skill end-to-end.

---

## ROUTING

| Trigger | Mode | Output |
|---|---|---|
| "draft LOI for [property]", broker package uploaded | **DRAFT** | Versioned DOCX + PDF preview |
| "ship the LOI", "send LOI to [broker]" | **SHIP** | DRAFT mode + Outlook send draft (cc: ggoldberg@oxfordra.net AND egoldberg@oxfordra.net) |
| "revise LOI", "update LOI", "tweak LOI" | **REVISE** | Apply edits, increment version, re-run QC |
| "compare LOI to [prior version]" | **COMPARE** | Side-by-side diff memo |

When ambiguous, default to **DRAFT** and ask one clarifying question only if a material economic term is missing.

---

## INPUTS — what you need before producing

**Required (refuse to proceed if missing):**
- Property street address, city, state, ZIP
- Building square footage, site acreage
- Seller legal entity name (e.g., "MIINI-OHIO INVESTMENTS LLC")
- Purchase Price
- Earnest Money Deposit
- Seller broker name, firm, address

**Highly preferred (will pull from connectors or use ORA defaults if absent):**
- Tenancy status (vacant / single-tenant / multi-tenant)
- Tenant legal name(s) and affiliation to Seller
- Existence of any Right of First Refusal, ROFO, or pre-emptive right in the lease
- Roof age, HVAC age, known deferred-maintenance disclosures (for §4 carveout)
- Study Period length (defaults to 30 days)
- Closing window (defaults to 15 days post-Study)
- Exclusivity period (default 60 days vacant / 30 days tenanted)

**Source priority for inputs:**
1. User-provided values in the prompt (highest priority — always wins)
2. OM / broker package / listing PDF (extract via PDF text or Vision)
3. Notion **Acquisition Pipeline Tracker** (DB `bcfe4a03`) if the deal is already logged
4. Notion **Deal Sourcing Log** (DB `9a6ae219`) for broker and pricing context
5. HubSpot — Broker Relationships for broker contact details
6. ORA Standard Commercial Terms (this skill, §STANDARDS) for any term still unresolved

---

## DECISION LOGIC — populate before token replacement

### 1. Tenancy classification

Determines opening paragraph phrasing and which conditional blocks fire.

| Signal in OM / inputs | Classification | `{{PROPERTY_TENANCY_PHRASE}}` | `{{TENANT_DISCLOSURE_PHRASE}}` |
|---|---|---|---|
| "Vacant," "100% available," "owner-occupied vacating," no current tenant | **vacant** | `vacant` | (empty string) |
| Single tenant in OM rent roll; not affiliated | **arm's-length single-tenant** | `single-tenant` | `, leased to {{TENANT_NAME}},` |
| Single tenant; tenant name shares a root with Seller LLC, OR OM discloses common ownership | **affiliated single-tenant** | `single-tenant` | `, leased to {{TENANT_NAME}}, an affiliate of Seller,` |
| 2+ tenants | **multi-tenant** | `multi-tenant` | (custom — list largest tenants in opening if material) |

**Affiliation test (decisional):** Set affiliated = TRUE if ANY of:
- Tenant LLC name contains Seller LLC root (e.g., "REDACTED-047, LLC" + "REDACTED-064 CO LLC")
- OM discloses sale-leaseback structure
- Tenant manager / principal is same as Seller manager / principal
- Tenant pays below-market rent identified during underwriting
- User explicitly states affiliation

### 2. Conditional block firing

Each conditional in the master template is evaluated independently. **Delete the entire `▶ CONDITIONAL ◀` ... `◀ END CONDITIONAL` block, including both markers, when the criterion is not met. Renumber subsequent sections sequentially.**

| Section | Block | Include if |
|---|---|---|
| §8 | Affiliated Tenant Disclosures | Tenant and Seller are affiliated entities |
| §9 | Tenant Estoppel | Property has any existing lease at Closing (any tenant) |
| §10 | Right of First Refusal Waiver | Existing lease contains ROFR, ROFO, or pre-emptive right |
| §11 | Lease Modification Restriction | Property has any existing lease at Closing |

**Resulting section counts:**
- Vacant property: 12 sections (1–7, 12–16 from template, renumbered to 1–12)
- Arm's-length single-tenant, no ROFR: 14 sections (1–7, 9, 11, 12–16 renumbered to 1–14)
- Arm's-length single-tenant, with ROFR: 15 sections
- Affiliated single-tenant, with ROFR: 16 sections (all sections retained)
- Affiliated single-tenant, no ROFR: 15 sections

### 3. State overlay selection for §6 (Prorations and Costs)

Replace the §6 default Ohio language with the matching overlay from `references/state-overlays.md`.

| State | County customs |
|---|---|
| **OH** | Long proration for Franklin/Cuyahoga/Hamilton counties; Seller pays state ($1/$1,000) + permissive county fee (varies $1–$3/$1,000); BOR appeal rights |
| **MD** | Recordation tax + transfer tax typically split 50/50; verify county (Montgomery, PG, Baltimore County, Frederick — different conventions) |
| **IN** | No state transfer tax; Sales Disclosure Form required; in-arrears tax billing |
| **MO** | No state real estate transfer tax; standard recording fees |
| **KS** | Mortgage registration tax abolished 2019; recording fees only; no transfer tax |
| **WI** | Wisconsin Real Estate Transfer Fee ($3/$1,000) paid by Seller |
| **TN** | Tennessee Realty Transfer Tax ($0.37/$100) paid by Seller |

**For any state not listed:** flag `[FORECAST]`, draft generic prose, and instruct user to verify locally.

### 4. Jurisdiction phrase resolution

`{{PROPERTY_JURISDICTION_PHRASE}}` fills the §2 jurisdiction-verification clause. Resolve as:

| Property location pattern | Phrase |
|---|---|
| Incorporated city, no surrounding township ambiguity | `the City of [CityName] and [County] County` |
| Address may straddle city/township (Columbus area, KC area) | `the City of [CityName], [County] County, [Township1], and/or [Township2]` |
| Unincorporated county area | `[County] County` |
| Confirmed Gahanna/Columbus suburb fully incorporated | `the City of [CityName] and Franklin County` |

When unclear, default to the broader formulation listing all potentially applicable jurisdictions.

### 5. Known-condition carveout (§4)

`{{KNOWN_CONDITION_CARVEOUT}}` fills inline within §4. Use when OM discloses a known condition:

| OM disclosure | Carveout text |
|---|---|
| Roof age ≥18 years | `(except for the roof, which the parties acknowledge is approximately [N] years old and approaching the end of its useful life)` |
| HVAC age ≥15 years | `(except for the HVAC system, which the parties acknowledge is approaching the end of its useful life)` |
| Deferred maintenance disclosed | `(except for the items of deferred maintenance disclosed in [Seller's marketing materials / Schedule X])` |
| Multiple conditions | Combine: `(except for [item 1] and [item 2])` |
| No known issues | DELETE the `{{KNOWN_CONDITION_CARVEOUT}}` token; leave no replacement |

### 6. Economic term defaults

When the user hasn't specified, apply ORA Standard Commercial Terms from `references/ora-standards.md`. Prefer the deal-size-adjusted values.

| Term | Default (deal <$3M) | Default ($3M–$10M) | Notes |
|---|---|---|---|
| EMD | 3% PP, min $50K | 2% PP | Larger EMD for tenanted/complex |
| Study Period | 30 days | 45 days | Add days for environmental complexity |
| Closing | 15 days post-Study | 30 days post-Study | Per Gabriel's standing preference |
| Exclusivity | 60 days vacant / 30 days tenanted | 60 days | Tenanted moves faster, less DD overhang |
| PSA initial draft | 10 business days | 10 business days | |
| PSA execution | 15 calendar days | 15 calendar days | |

### 7. Buyer signatory

Default values from `references/ora-standards.md`:
- `{{BUYER_SIGNATORY_NAME}}` = `Gabriel Goldberg`
- `{{BUYER_SIGNATORY_TITLE}}` = `Authorized Representative`

Override only if user explicitly directs (e.g., "Eric to sign this one").

### 8. Offer expiration

Default: 7 calendar days from `{{LOI_DATE}}`, adjusted to the next business day if it falls on a weekend or federal holiday. Never less than 5 BD; never more than 14 calendar days.

---

## TOKEN REFERENCE (canonical list)

These are the tokens that appear in the master template. The skill is responsible for resolving every one before saving the file.

### Date and money
| Token | Example | Source |
|---|---|---|
| `{{LOI_DATE}}` | `May 15, 2026` | Today's date (or user-specified) |
| `{{OFFER_EXPIRATION_DATE}}` | `May 22, 2026` | LOI_DATE + 7 calendar days, business-day-adjusted |
| `{{PURCHASE_PRICE_WORDS}}` | `One Million Four Hundred Thousand and 00/100` | User / OM offer |
| `{{PURCHASE_PRICE_NUMERIC}}` | `1,400,000.00` | Same |
| `{{EMD_WORDS}}` | `One Hundred Thousand and 00/100` | User or ORA standard |
| `{{EMD_NUMERIC}}` | `100,000.00` | Same |

### Time periods (all phrased as `[word] (digit)`)
| Token | Example |
|---|---|
| `{{STUDY_PERIOD_WORDS}}` | `thirty (30)` |
| `{{CLOSING_DAYS_WORDS}}` | `fifteen (15)` |
| `{{EXCLUSIVITY_DAYS_WORDS}}` | `sixty (60)` or `thirty (30)` |
| `{{PSA_DRAFT_DAYS_WORDS}}` | `ten (10) business` |
| `{{PSA_EXECUTE_DAYS_WORDS}}` | `fifteen (15) calendar` |

### Property
| Token | Example |
|---|---|
| `{{PROPERTY_STREET_ADDRESS}}` | `1333 REDACTED-112` |
| `{{PROPERTY_CITY}}` | `Gahanna` |
| `{{PROPERTY_STATE_FULL}}` | `Ohio` |
| `{{PROPERTY_STATE_ABBR}}` | `OH` |
| `{{PROPERTY_ZIP}}` | `43230` |
| `{{PROPERTY_COUNTY}}` | `Franklin County` |
| `{{PROPERTY_SF}}` | `19,018` |
| `{{PROPERTY_ACRES}}` | `2.46` |
| `{{PROPERTY_USE_TYPE}}` | `industrial` or `industrial / warehouse` or `flex` |
| `{{PROPERTY_TENANCY_PHRASE}}` | `vacant` / `single-tenant` / `multi-tenant` |
| `{{PROPERTY_JURISDICTION_PHRASE}}` | `the City of Gahanna and Franklin County` |
| `{{KNOWN_CONDITION_CARVEOUT}}` | `(except for the roof, which the parties acknowledge is approximately twenty-one (21) years old and approaching the end of its useful life)` or empty |

### Seller / broker
| Token | Example |
|---|---|
| `{{SELLER_ENTITY_NAME}}` | `REDACTED-064 CO LLC` (preserve original capitalization) |
| `{{SELLER_BROKER_FULL_NAME}}` | `David REDACTED-164` |
| `{{SELLER_BROKER_FIRM}}` | `REDACTED-046 Real Estate Group` |
| `{{SELLER_BROKER_ADDRESS_1}}` | `8800 REDACTED-130, Suite 600` |
| `{{SELLER_BROKER_ADDRESS_2}}` | `Columbus, Ohio 43240` |
| `{{SELLER_BROKER_SALUTATION}}` | `David` |

### Tenant (only if conditional §8 / §10 fires)
| Token | Example |
|---|---|
| `{{TENANT_NAME}}` | `REDACTED-047, LLC` |
| `{{TENANT_DISCLOSURE_PHRASE}}` | `, leased to REDACTED-047, LLC, an affiliate of Seller,` |

### Buyer signatory
| Token | Example |
|---|---|
| `{{BUYER_SIGNATORY_NAME}}` | `Gabriel Goldberg` |
| `{{BUYER_SIGNATORY_TITLE}}` | `Authorized Representative` |

---

## WORKFLOW — execute in this order

### Phase 1 — Ingest and parse
1. Read user prompt for any explicit values (Purchase Price, deposit, dates, etc.).
2. If a PDF/DOCX is attached, extract OM data: address, SF, acreage, asking price, tenant status, broker contact, photos, building age, rent roll if present.
3. If property is already in Notion Acquisition Pipeline Tracker (`bcfe4a03`), pull existing fields.
4. If broker email/contact missing, search HubSpot CRM for broker by name or firm.

### Phase 2 — Apply decision logic
1. Classify tenancy (vacant / arm's-length / affiliated / multi-tenant).
2. Determine which conditionals fire.
3. Select state overlay for §6.
4. Resolve jurisdiction phrase for §2.
5. Resolve known-condition carveout for §4 (or leave empty).
6. Apply economic term defaults from ORA Standards for any unspecified term.

### Phase 3 — Token resolution
1. Build full token map.
2. Verify no required token is unresolved. If any is missing, list them and ask Gabriel for clarification before producing the file.
3. Convert numeric amounts to word form for `_WORDS` tokens. Format numerics with commas and trailing `.00`.

### Phase 4 — Document assembly (Python)
Use `python-docx` to:
1. Open `templates/LOI_Master_Template_Condensed.docx`.
2. Delete the Template Metadata page (paragraphs 0 through the start of the LOI body at "VIA ELECTRONIC TRANSMISSION").
3. Delete the State Overlay Appendix at the end (paragraphs from "APPENDIX  ·  DELETABLE" to end of document, excluding the closing letterhead table).
4. Replace each `{{TOKEN}}` with its resolved value, preserving gold sans-serif formatting only for unresolved tokens (none should remain).
5. For each conditional block: if criterion met, strip the `▶ CONDITIONAL ◀` and `◀ END CONDITIONAL` marker paragraphs; if criterion not met, delete all paragraphs between markers (inclusive).
6. Renumber sections sequentially (§1, §2, … §N) after conditional deletions.
7. Update Non-Binding paragraph cross-references to match the new section numbers.
8. Replace §6 body with the matching state overlay if non-Ohio.
9. If known condition exists, replace `{{KNOWN_CONDITION_CARVEOUT}}` with the carveout text. Otherwise, delete the token cleanly (no stray punctuation).

### Phase 5 — QC Gate (refuse to save if any item fails)

| # | Check |
|---|---|
| 1 | All `{{TOKENS}}` resolved; no gold sans-serif placeholders remain in body |
| 2 | All `▶ CONDITIONAL ◀` blocks evaluated; markers removed |
| 3 | §6 language matches property state |
| 4 | Section numbering sequential; cross-references in non-binding paragraph match retained sections |
| 5 | Template Metadata page deleted; State Overlay Appendix deleted |
| 6 | Tenancy disclosure in opening paragraph matches `{{PROPERTY_TENANCY_PHRASE}}` |
| 7 | Economic terms within ORA acceptable ranges (or deviations explicitly noted in chat) |
| 8 | Buyer signatory matches user instruction (default Gabriel) |
| 9 | Letterhead phone reads **301.512.6125** (both top and bottom letterhead tables) |
| 10 | Footer reads `[PROPERTY_STREET_ADDRESS] LOI · Page X of Y` with PAGE/NUMPAGES fields |
| 11 | "Proof of funds available upon request." appears centered italic in grey on the very last page, lower third |
| 12 | Tenant count in BUYER INFORMATION trailer reads "approximately 140 tenants" |
| 13 | Offer expiration date is a business day no fewer than 5 business days from LOI date |
| 14 | EXECUTION PAGE present with Buyer signature block populated (Gabriel Goldberg, Authorized Representative) and Seller block populated with `{{SELLER_ENTITY_NAME}}` |
| 15 | Strike list clean: NO "shall" (excluding "shallow"), NO banned phrases ("I hope this finds you well," "Just following up," "As discussed," "FYI," "Going forward," "At your earliest convenience") |
| 16 | PDF generated via `soffice` (NOT Microsoft Print to PDF); extractable text confirmed by `pdftotext` round-trip |

If any check fails, fix and re-run. Do not present a failing file.

### Phase 6 — Save and present
1. Filename: `LOI [Property Street] [City] [State] [M.D.YYYY].docx` — match Gabriel's convention (e.g., `LOI REDACTED-113 Rd Gahanna OH 5.14.2026.docx`).
2. Save to outputs folder.
3. Generate PDF preview via `soffice --headless --convert-to pdf`.
4. Present both files to user via `present_files`.
5. Log to Notion Acquisition Pipeline Tracker (`bcfe4a03`): set deal status to "LOI Out" with link to file, expiration date, and a single-line summary of terms.

### Phase 7 — Optional SHIP mode
If user requested ship:
1. Draft email via Composio `OUTLOOK_SEND_EMAIL` (or `OUTLOOK_DRAFT` if Mail.Send not held).
2. To: `{{SELLER_BROKER_EMAIL}}` (pull from HubSpot).
3. Cc: BOTH `ggoldberg@oxfordra.net` AND `egoldberg@oxfordra.net` (this supersedes any legacy `ze@oxfordra.net` default).
4. Subject: `LOI — [Property Street], [City], [State]`.
5. Body: 3-sentence cover note in ORA broker voice (collegial, market-aware, no over-commitment). Attach DOCX and PDF.
6. Do NOT send — present the draft for Gabriel's review and approval. Pause for explicit go-ahead before send.

---

## STANDARDS — ORA defaults reference

See `references/ora-standards.md` for the full standards table. Key numbers:

| Term | ORA Standard | Acceptable Range | Rationale |
|---|---|---|---|
| EMD | 2–3% PP, min $50K | 1–7% PP | Smaller deals warrant proportionally larger % |
| Study Period | 30 days | 30–60 days | 30 default; 45 if complex DD anticipated |
| Closing post-Study | 15 days | 15–45 days | Gabriel's standing preference: 15 |
| Exclusivity | 60 days | 30–90 days | 60 for vacant; 30 acceptable for tenanted |
| PSA initial draft | 10 BD | 5–15 BD | |
| PSA execution | 15 calendar days from draft | 10–30 days | |
| Phase I auto-extension | To Phase II receipt | Standard | |
| Tenant Estoppel | 10 BD before Closing | 5–15 BD | Condition precedent |

---

## STATE OVERLAYS — quick reference

Full overlay text in `references/state-overlays.md`. Summary of §6 distinguishing language:

- **OH** — Franklin/Cuyahoga County long proration; Seller pays state conveyance ($1/$1,000) + permissive county fee (varies); BOR appeal rights to Buyer
- **MD** — Recordation + transfer tax customarily 50/50; verify by county
- **IN** — No state transfer tax; Sales Disclosure Form required; tax billing in arrears
- **MO** — No state real estate transfer tax; standard recording fees
- **KS** — Recording fees only; no transfer tax
- **WI** — Real Estate Transfer Fee $3/$1,000 Seller-pays
- **TN** — Realty Transfer Tax $0.37/$100 Seller-pays

---

## STRIKE LIST — banned phrases (LOI must not contain any)

- "shall" (anywhere — use "will")
- "I hope this finds you well"
- "Just following up"
- "As discussed"
- "FYI"
- "Going forward"
- "At your earliest convenience"
- "Hopefully"
- "I think we should"
- "Quick question"
- "Sorry for the delay"
- "Notwithstanding the foregoing" (use "However")
- "Pursuant to" (use "under" or drop)
- "Hereunder," "hereof," "thereof," "thereunto" (drop)

---

## CONNECTORS USED

| Connector | Tool | Purpose |
|---|---|---|
| Notion | `notion-search`, `notion-fetch`, `notion-update-page` | Pull Acquisition Pipeline Tracker, Deal Sourcing Log, Tenant DB |
| HubSpot | `search_crm_objects`, `get_crm_objects` | Pull broker contact details from Broker Relationships |
| Outlook (Composio) | `OUTLOOK_DRAFT` / `OUTLOOK_SEND_EMAIL` | Ship mode email drafting |
| Workspace bash | `python3` with `python-docx` | Document assembly |
| Workspace bash | `soffice` headless | PDF generation |
| Cowork | `present_files` | Deliver outputs |

---

## SPECIAL CASES

### Multi-tenant property
- `{{PROPERTY_TENANCY_PHRASE}}` = `multi-tenant`
- `{{TENANT_DISCLOSURE_PHRASE}}` = `` (empty) OR include short phrase referencing largest tenants
- Conditional §8 (Affiliated Tenant) typically DOES NOT fire (multi-tenant rarely all-affiliated)
- Conditional §9 (Estoppel) — modify to "Seller will cause each Tenant occupying more than [SF threshold] to deliver an estoppel"
- Conditional §11 (Lease Modification) fires; flag in chat that this should be PSA-strengthened with portfolio-wide restrictions

### Vacant property
- All four conditionals DELETE
- `{{TENANT_DISCLOSURE_PHRASE}}` = empty string (resulting opening reads "... commercially zoned industrial land.")
- §4 may include vacant-building maintenance covenant (heat/sprinkler) — the master template already contains this in §7 bullets

### Property in unfamiliar state (not in seven-state overlay list)
- Flag `[FORECAST]` in chat
- Draft generic §6 language with placeholder reading "[STATE]: confirm customary proration method and transfer-tax allocation with local counsel before transmission"
- Do not ship without user verification

### Sale-leaseback indicated
- Tenancy = affiliated single-tenant
- All four conditionals fire
- Add `[SPECULATIVE]` flag in chat: sale-leaseback financing structures often warrant stronger §11 lease-modification restrictions including capped concessions
- Recommend lengthening Study Period to 45 days to allow tenant credit underwriting

### Seller refuses long proration (rare)
- Cite ORC § 5709.01 et seq. and Franklin County Bar custom in pushback memo
- Fall-back: short proration with Seller credit for prior year unpaid taxes (preserve buyer-protective substance)

---

## VERSIONING

- v1.0 — Initial release, May 2026. Based on 511 REDACTED-091 Columbus and REDACTED-113 Rd Gahanna condensed deliverables.
- Master template asset: `templates/LOI_Master_Template_Condensed.docx`
- State overlays asset: `references/state-overlays.md`
- ORA Standards asset: `references/ora-standards.md`

---

## FAILURE MODES — when NOT to use this skill

- **Owner-occupied property where ORA is selling, not buying** — wrong direction; use `deal-execution` skill for sale side
- **Refinance proposal** — use `debt-management` skill
- **Off-market lease proposal** (ORA leasing to a third party) — use `re-operations` skill
- **PSA stage** — handoff to `deal-execution` skill once LOI is executed; this skill stops at LOI delivery

---

## OUTPUT GUARANTEES

Every successful run of this skill produces:
1. A DOCX file on ORA letterhead, 4–8 pages depending on conditionals retained
2. A PDF preview with extractable text
3. A presented file pair via `present_files`
4. A Notion log entry on the Acquisition Pipeline Tracker
5. Zero "shall" usage, zero banned phrases, full 16-point QC Gate pass
6. Phone 301.512.6125 in both top and bottom letterhead
7. Footer keyed to property street address
8. "Proof of funds available upon request." centered italic at bottom of final page
