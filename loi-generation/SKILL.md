---
name: loi-generation
description: "Use when the user mentions: draft LOI, generate LOI, letter of intent, offer letter, or non-binding proposal to purchase; when an OM, broker package or listing is uploaded with intent to make an offer; or when an acquisition-underwriting evaluation advances to an offer. Also trigger on: revise LOI, update LOI, compare LOI to a prior version, send LOI to a broker. SOLE path for Oxford Realty Advisors letters of intent -- never document-assembly's generic template or legal-intelligence. Refuses to draft without the ORA walk price from acquisition-underwriting. Every LOI uses the SHORT house form (logo header, labeled terms, address footer); handles state overlays, 1031, entity-interest purchase."
---

# LOI Generation — Oxford Realty Advisors (v1.17)

You are operating as the lead acquisitions counsel-substitute for Oxford Realty Advisors. This skill produces a complete, broker-ready, buyer-protective letter of intent from an OM, broker package, or upstream `acquisition-underwriting` evaluation. The output is a SHORT-form LOI — the ORA house format (logo header, underlined labeled terms, address footer, acceptance block), two pages, three when a conditional term fires — — not a contract, not legalese, but every dollar-material protection Gabriel needs at the LOI stage.

This skill OWNS the LOI-stage drafting decision. Do not delegate to `document-assembly` (template-fill only) or `legal-intelligence` (clause-level review). Use this skill end-to-end.

---

## ROUTING

| Trigger | Mode | Output |
|---|---|---|
| "draft LOI for [property]", broker package uploaded | **DRAFT** | Versioned DOCX + PDF preview |
| "ship the LOI", "send LOI to [broker]" | **SHIP** | DRAFT mode + Outlook draft for review (cc per thread context — no blanket cc of both principals; CC discipline 2026-06-10) |
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
- **`Walk Price`** — the ORA walk price from `acquisition-underwriting` (the highest price clearing **all** binding Stage 1 floors: Basis, Yield, and IRR — the IRR floor is 10-yr unlevered and rate-linked since acquisition-underwriting v4.33, so cite the UST10 value and date the walk price was solved at; a walk price solved before v4.33 must be re-solved, and so must **any walk price solved before `acquisition-underwriting` v4.37** (blanket rule: v4.37 moved the construction-type multiplier, the renovation R% denominator, the portfolio allocation weights and the off-table `[PROXY]` source, so no pre-v4.37 walk is trusted; it cut the Piper PEMB walk about 10%); a stale Notion `ORA Walk` value is not a valid input). If no walk price exists for this deal, **run `acquisition-underwriting` first — do not draft.** An LOI is an offer; ORA does not make offers at prices it has not tested. Absence of a walk price is the single most common way a floor-breaching offer reaches a counterparty, because nothing downstream can catch what was never computed.

- **`Parcel Record`** — the county auditor/assessor record of the subject parcel(s), pulled and dated within 14 days per Rule 0d. Refuse to draft without it.

**Highly preferred (will pull from connectors or use ORA defaults if absent):**
- Tenancy status (vacant / single-tenant / multi-tenant)
- Tenant legal name(s) and affiliation to Seller
- Existence of any Right of First Refusal, ROFO, or pre-emptive right in the lease
- Roof age, HVAC age, known deferred-maintenance disclosures (for the Property Condition carveout)
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

### 0. Seller entity interest type (REQUIRED — 470 REDACTED-148 lesson)

The entity-purchase election (`{{ENTITY_INTEREST_SENTENCE}}`, Other Conditions) must match the seller's entity form. Resolve from the seller legal name suffix:

| Seller suffix | {{ENTITY_INTEREST_TYPE}} |
|---|---|
| LLC / L.L.C. / Ltd (limited liability co) | `membership interests` |
| Inc / Corp / Co (corporation) | `equity interests` (or `shares of capital stock` if counsel directs) |
| LP / LLP / Limited Partnership | `partnership interests` |

Never ship "membership interests" against a corporate seller.

**Template hook (v1.15):** `{{ENTITY_INTEREST_SENTENCE}}` in Other Conditions, built with `{{ENTITY_INTEREST_TYPE}}` (references/short-form.md). Default empty: fill only when Seller holds the Property through a single-asset entity AND Buyer wants the entity-purchase option (or Gabriel asks for it, e.g. an Ohio drop-and-swap); never for a trust seller (deed conveyance, trustee in the acceptance block).

### 0b. Format — SHORT only (v1.15; CONDENSED and STANDARD retired)

**Every LOI uses the SHORT form (Gabriel, 2026-10-27: "All LOIs generated should match the formatting in the attached document" — a SHORT-form LOI ORA sent on 10/20/2026).** Template `templates/LOI_ShortForm_Template.docx`, filled with `templates/fill_shortform.py`. **Read references/short-form.md before assembling** — layout, fixed term order, tokens, conditional terms, state table and the SHORT QC gate live there.

The v1.12 fallbacks to CONDENSED are replaced by SHORT conditional terms (Rule 2): affiliated tenant / sale-leaseback and ROFR/ROFO → **Tenant Conditions**; tenant purchase option → **Purchase Option**; entity-interest election → `{{ENTITY_INTEREST_SENTENCE}}` in Other Conditions; a known or likely Phase II / VAP path → the Due Diligence auto-extension (now covering a Buyer-elected Phase II and any voluntary action program determination); open zoning item → **Zoning**. The CONDENSED master is retired to `templates/archive/LOI_Master_Template_Condensed_v1.1.docx` and never produces an outbound LOI — including a REVISE of an LOI first drafted in it, which is rebuilt in SHORT. If Gabriel explicitly asks for the old long form in-turn, say it is retired and confirm before using the archived master.


### 0b. Format — SHORT only (v1.15; CONDENSED and STANDARD retired)

**Every LOI uses the SHORT form (Gabriel, 2026-10-27: "All LOIs generated should match the formatting in the attached document" — a SHORT-form LOI ORA sent on 10/20/2026).** Template `templates/LOI_ShortForm_Template.docx`, filled with `templates/fill_shortform.py`. **Read references/short-form.md before assembling** — layout, fixed term order, tokens, conditional terms, state table and the SHORT QC gate live there.

The v1.12 fallbacks to CONDENSED are replaced by SHORT conditional terms (Rule 2): affiliated tenant / sale-leaseback and ROFR/ROFO → **Tenant Conditions**; tenant purchase option → **Purchase Option**; entity-interest election → `{{ENTITY_INTEREST_SENTENCE}}` in Other Conditions; a known or likely Phase II / VAP path → the Due Diligence auto-extension (now covering a Buyer-elected Phase II and any voluntary action program determination); open zoning item → **Zoning**. The CONDENSED master is retired to `templates/archive/LOI_Master_Template_Condensed_v1.1.docx` and never produces an outbound LOI — including a REVISE of an LOI first drafted in it, which is rebuilt in SHORT. If Gabriel explicitly asks for the old long form in-turn, say it is retired and confirm before using the archived master.

**Survivors — never cut:** Phase I→Phase II auto-extension (environmental tail cap) and the designee-vesting/direct-deeding mechanics in Other Conditions; the defect-free assumption in Property Condition; for vacant deals the preservation covenant in Operations.

### 0c. Exchange posture — 1031 cooperation DEFAULT vs concealment overlay

**DEFAULT (template standard): RETAIN the mutual IRC §1031 cooperation sentence in Other Conditions.** It is reciprocal, costless, and ORA transacts via exchange routinely. Removing it is the exception, never the rule (Gabriel ruling 2026-06-10).

**CONCEALMENT OVERLAY — apply ONLY when BOTH are true:** (a) seller is sophisticated/institutional (developer, REIT, bank REO, family office with standing counsel, or major-brokerage portfolio seller), AND (b) ORA has live buyer-side exchange-timeline pressure (drop-and-swap, 45/180-day identification windows). Then:
- Set `"CONCEALMENT_OVERLAY": true` in values.json: `fill_shortform.py` deletes the §1031 cooperation sentence from Other Conditions and "exchange intermediaries" from Confidentiality, rewords "in exchange for free and clear title" in Purchase Price, then runs the leak-check itself.
- Delete any "Buyer intends to complete a §1031 exchange" motive language.
- Rely entirely on unnamed mechanics in Other Conditions (base text plus `{{ENTITY_INTEREST_SENTENCE}}` where needed): title may vest in one or more Buyer-designated affiliates or tenants-in-common (including any intermediary or accommodation titleholder designated by Buyer); assignment of LOI/PSA to designees by written notice pre-Closing; Seller cooperation with Buyer's closing structure including direct deeding and customary acknowledgments, at no additional cost, liability, or delay to Seller and without extending Closing.
- **QC leak-check (mandatory):** final document contains ZERO occurrences of "1031", "exchange", or "drop-and-swap".
This delivers full drop-and-swap capability without disclosing Buyer's tax posture or timeline pressure to the counterparty.

### 0d. Parcel-record pre-flight (REQUIRED — 511 REDACTED-091 lesson)

Before any token is resolved, pull the parcel record from the county auditor/assessor of record (the county's own property-search site, e.g. Franklin County: property.franklincountyauditor.com; endpoint per `county-parcel-screen`'s registry where one exists). OMs, broker packages and listing sites are not a substitute. Record five fields with the parcel ID and the site's "data current as of" date:

| # | Field | Flag → required response |
|---|---|---|
| 1 | **Owner of record** | Must equal `{{SELLER_ENTITY_NAME}}` character-for-character (unusual spellings preserved, never "corrected"). Mismatch → **STOP**: resolve against the deed / Secretary of State (recent transfer, trust, affiliate, wrong parcel) before drafting. |
| 2 | **Land use code / property class** | Outside the county's industrial / warehouse / manufacturing classes → **USE-CLASSIFICATION FLAG**. |
| 3 | **Structure / occupancy type** | Non-industrial (e.g. "Health Spa", retail, office) on an industrial target → **USE-CLASSIFICATION FLAG**. Response: fire the **Zoning** conditional term (Rule 2) and add the last-industrial/warehouse/contractor-occupancy-date disclosure via `{{DD_DELIVERY_ADDITIONS}}`; route the zoning question to `ora-flood-zoning-dd`. |
| 4 | **Last transfer** — date, price, instrument, parcel count | Supplies the auditor value for the Rule 5c HB 126 test. Transfer within 24 months, multi-parcel, or non-warranty instrument (quitclaim, sheriff, fiduciary) → note in chat; non-warranty → confirm Seller can give `{{DEED_FORM}}`. |
| 5 | **Tax status** — net annual tax, total paid, delinquency / lien / CDQ, pending BOR, abatement / TIF / CAUV | Delinquency, lien, CDQ, or total paid materially above annual billed → Costs must require Seller to credit all unpaid prior-year taxes, penalties and interest. Pending BOR → note in chat. Abatement / TIF / CAUV → confirm it survives transfer before underwriting relies on it. |

Post the five fields as a dated **Parcel Pre-Flight** block in chat ahead of the draft, and write the parcel ID plus any flags to the Acquisition Pipeline row's `Next Action`. Only a field-1 mismatch blocks drafting; every other flag requires its response in the LOI text or an explicit in-turn waiver from Gabriel, noted in chat.

### 1. Tenancy classification

Determines opening paragraph phrasing and which conditional blocks fire.

| Signal in OM / inputs | Classification | `{{PROPERTY_TENANCY_PHRASE}}` | `{{TENANT_DISCLOSURE_PHRASE}}` |
|---|---|---|---|
| "Vacant," "100% available," "owner-occupied vacating," no current tenant | **vacant** | `vacant` | (empty string) |
| Single tenant in OM rent roll; not affiliated | **arm's-length single-tenant** | `single-tenant` | `, leased to {{TENANT_NAME}} (the "Tenant")` — the intent paragraph is where "Tenant" is defined |
| Single tenant; tenant name shares a root with Seller LLC, OR OM discloses common ownership | **affiliated single-tenant** | `single-tenant` | `, leased to {{TENANT_NAME}}, an affiliate of Seller` — no trailing comma; Tenant Conditions carries the affiliate disclosures |
| 2+ tenants | **multi-tenant** | `multi-tenant` | (custom — list largest tenants in opening if material) |

**Punctuation convention (2026-08-18 fix — was producing "...,." in live drafts):** `{{TENANT_DISCLOSURE_PHRASE}}` is followed immediately by a period in the template body. Never let the resolved value end in a trailing comma.

**Affiliation test (decisional):** Set affiliated = TRUE if ANY of:
- Tenant LLC name contains Seller LLC root (e.g., "REDACTED-047, LLC" + "REDACTED-064 CO LLC")
- OM discloses sale-leaseback structure
- Tenant manager / principal is same as Seller manager / principal
- Tenant pays below-market rent identified during underwriting
- User explicitly states affiliation

### 2. Conditional terms (SHORT)

Each conditional is a whole labeled term (a `{{..._TERM}}` token; `fill_shortform.py` deletes the paragraph when the value is empty) or an inline sentence token. Verbatim patterns are in references/short-form.md.

| Term / token | Include if | Replaces (retired CONDENSED) |
|---|---|---|
| **Tenant Conditions** `{{TENANT_CONDITIONS_TERM}}` — affiliated-tenant disclosures | Tenant and Seller are affiliated entities | §8 |
| **Tenant Conditions** — ROFR/ROFO waiver before PSA or diligence spend | A lease carries a ROFR, ROFO or pre-emptive right | §10 |
| **Tenant Conditions** — named estoppel confirmations | Specific lease facts must be confirmed (rent term, NNN tax pass-through, option status) | §9 (the generic estoppel stays in `{{OPERATIONS_CONDITIONAL_SENTENCE}}`) |
| **Purchase Option** `{{PURCHASE_OPTION_TERM}}` | A tenant holds an option to purchase | — (10/20/2026 LOI precedent) |
| **Zoning** `{{ZONING_TERM}}` | Zoning is DD-Critical, the intended use is nonconforming, or the parcel is PD/PUD | — (2026-10-27 Ohio LOI precedent) |
| `{{ENTITY_INTEREST_SENTENCE}}` (Other Conditions) | Rule 0 conditions met | inline §13 |
| `{{DD_DELIVERY_ADDITIONS}}` (Due Diligence) | Extra Seller deliveries needed (e.g. last-occupancy date for a nonconforming use) | §2 delivery list |
| `{{CONFIDENTIALITY_TENANT_CARVEOUT}}` | Tenant Conditions requires contact with a tenant | §16 tenant disclosure |

The lease-modification restriction (§11) is already in the base Operations term. **Vacant-property preservation covenant (MANDATORY when tenancy = vacant):** `{{OPERATIONS_CONDITIONAL_SENTENCE}}` carries it verbatim (references/short-form.md). Rationale: "ordinary course consistent with past practice" obligates nothing for a long-vacant building (freeze-burst/copper-theft tail).

### 3. State overlay selection for Costs

Resolve `{{DEED_FORM}}` and `{{TRANSFER_TAX_SENTENCE}}` from the state table in references/short-form.md (which mirrors `references/state-overlays.md`).

Per-state county customs (proration method, transfer-tax allocation, BOR rights) are summarised in `references/state-overlays.md` — **read it before resolving the Costs tokens for any non-Ohio property.**

**For any state not listed:** flag `[FORECAST]`, draft generic prose, and instruct user to verify locally.

### 4. Jurisdiction phrase resolution

`{{PROPERTY_JURISDICTION_PHRASE}}` names the jurisdiction in the Zoning term — resolve per the location-pattern table in references/template-mechanics.md; when unclear, default to the broader formulation listing all potentially applicable jurisdictions.

### 5. Known-condition carveout (Property Condition)

`{{KNOWN_CONDITION_CARVEOUT}}` fills inline within Property Condition when the OM discloses a known condition (roof ≥18 years, HVAC ≥15 years, disclosed deferred maintenance — carveout text per references/template-mechanics.md). With no known issues DELETE the token and leave no replacement.

### 5b. PSA-deferral list — standard contents (Process/Definitive Documentation section)

Always enumerate, so the PSA anchor is set without LOI negotiation: bill-of-sale conveyance at no cost; Buyer access & insurance during Study Period; Deposit due {{EMD_DUE_DAYS_WORDS}} business days after PSA execution; closing/deed mechanics per the Acquisition Structure section; specific-performance remedy for Buyer upon Seller default (all-cash buyer's primary risk is being shopped); title commitment within ten (10) days after PSA execution; Property delivered broom-clean, free of debris and personal property of others. OHIO DEALS add: Seller cooperation with — and agreement not to independently stipulate to — real-property-tax valuation proceedings affecting pre-Closing periods.

### 5c. Ohio BOR risk — statutory thresholds (HB 126)

Run the HB 126 dual test — recorded sale exceeds auditor value by BOTH 10% AND $500,000 [verify thresholds with counsel] — at offer price vs auditor value before asserting BOR risk; below either threshold the school-board original-complaint route is barred. **Read references/state-overlays.md (Ohio BOR dual-threshold rule) before drafting Ohio §6 or BOR language.**

### 6. Economic term defaults

When the user hasn't specified, apply ORA Standard Commercial Terms from `references/ora-standards.md`. Prefer the deal-size-adjusted values.

Deal-size-adjusted defaults (<$3M vs $3M–$10M: EMD, Study Period, Closing, Exclusivity, PSA draft and execution windows) are tabulated in `references/ora-standards.md` — **read it before filling any unspecified economic term.**

### 7. Buyer signatory

Default values from `references/ora-standards.md`:
- `{{BUYER_SIGNATORY_NAME}}` = `Gabriel Goldberg`
- `{{BUYER_SIGNATORY_TITLE}}` = `Authorized Representative`

Override only if user explicitly directs (e.g., "Eric to sign this one").

### 8. Offer expiration

Default: 7 calendar days from `{{LOI_DATE}}`, adjusted to the next business day if it falls on a weekend or federal holiday. Never less than 5 BD; never more than 14 calendar days.

---

## TOKEN REFERENCE

**Read references/token-reference.md before Phase 3 token resolution.** It is the canonical list of value tokens (SHORT-specific tokens are in references/short-form.md) with examples and sources; the skill must resolve every one before saving the file. Load-bearing conventions: all time periods are phrased `[word] (digit)`; `{{EMD_DUE_DAYS_WORDS}}` (default `two (2)`) is the SINGLE SOURCE for the deposit due-window and feeds §1 AND every PSA-deferral mention; `{{TENANT_DISCLOSURE_PHRASE}}` never ends in a trailing comma; `{{PROPERTY_ZONING_PHRASE}}` is VERBATIM from the OM or a verified GIS pull — if unknown, ask, never default; `{{SELLER_ENTITY_NAME}}` preserves original capitalization.

---

## WORKFLOW — execute in this order

### Phase 1 — Ingest and parse
1. Read user prompt for any explicit values (Purchase Price, deposit, dates, etc.).
2. If a PDF/DOCX is attached, extract OM data: address, SF, acreage, asking price, tenant status, broker contact, photos, building age, rent roll if present.
3. If property is already in Notion Acquisition Pipeline Tracker (`bcfe4a03`), pull existing fields.
4. If broker email/contact missing, search HubSpot CRM for broker by name or firm.
5. Run the Rule 0d parcel-record pre-flight and post the dated Parcel Pre-Flight block. A field-1 owner mismatch stops the run here.

### Phase 2 — Apply decision logic
1. Classify tenancy (vacant / arm's-length / affiliated / multi-tenant).
2. Determine which conditionals fire.
3. Select the state row for Costs (`{{DEED_FORM}}`, `{{TRANSFER_TAX_SENTENCE}}`).
4. Resolve the jurisdiction phrase (Zoning term, when it fires).
5. Resolve the known-condition carveout for Property Condition (or leave empty).
6. Apply economic term defaults from ORA Standards for any unspecified term.
7. Apply every Rule 0d flag: use-classification → Zoning term + last-industrial-occupancy disclosure; tax delinquency/arrearage → Seller credit for all unpaid prior-year taxes, penalties and interest.

### Phase 3 — Token resolution
1. Build full token map.
2. Verify no required token is unresolved. If any is missing, list them and ask Gabriel for clarification before producing the file.
3. Convert numeric amounts to word form for `_WORDS` tokens. Format numerics with commas and trailing `.00`.

### Phase 4 — Document assembly (SHORT)
1. Write `values.json` mapping every template token (references/short-form.md) to its resolved value; optional terms and inline optional tokens get `""` when they do not fire.
2. `python templates/fill_shortform.py values.json "LOI [Street] [City] [ST] [M.D.YYYY].docx"` — fails on any unresolved token; resolved text takes the body font.
3. `soffice --headless --convert-to pdf` on the DOCX.
4. `python templates/qc_shortform.py <pdf> values.json` must exit 0; then render every page (`pdftoppm`) and look at it.
5. Never open or fill `templates/archive/LOI_Master_Template_Condensed_v1.1.docx` for an outbound LOI.

### Phase 5 — QC Gate (refuse to save if any item fails)

Run `templates/qc_shortform.py` first (it automates #1, #4, #5, #9–#12, #14–#17, #21). Full check text and the remaining manual items: references/short-form.md.

| # | Check |
|---|---|
| 1 | No unresolved `{{TOKENS}}` |
| 2 | Every conditional term evaluated against Rule 2; omitted terms leave no residue |
| 3 | `{{DEED_FORM}}` / `{{TRANSFER_TAX_SENTENCE}}` match the property state's row |
| 4 | Labeled terms in the fixed order; the binding sentence names Exclusivity and Confidentiality |
| 5 | No metadata page, appendix, Execution Page, Buyer Information page, or `§` numbering |
| 6 | Tenancy wording in the intent paragraph matches `{{PROPERTY_TENANCY_PHRASE}}` |
| 7 | Economic terms within ORA acceptable ranges (or deviations explicitly noted in chat) |
| 8 | Signature block = Gabriel Goldberg / Authorized Representative / Oxford Realty Advisors (or override) |
| 9 | `301.512.6125` in the footer on every page; `301.983.8000` never |
| 10 | Address footer with block mark on every page; no page numbers |
| 11 | "Proof of funds available upon request." once, centered italic grey, directly below the acceptance block |
| 12 | Credentials paragraph verbatim canon: no portfolio value, no closing-record claim, no leverage figure |
| 13 | Offer expiration is a business day no fewer than 5 business days from LOI date |
| 14 | Acceptance block with `Seller: {{SELLER_ENTITY_NAME}}` |
| 15 | Strike list clean: NO "shall" (excluding "shallow"), NO banned phrases (acceptance line exempt from "Subject to") |
| 16 | PDF generated via `soffice` (NOT Microsoft Print to PDF); extractable text |
| 17 | Two pages; three only when a conditional term fires; never shrink fonts or margins to fit |
| 18 | Entity-interest language matches seller suffix (Rule 0) — "membership interests" never ships against an Inc/Corp seller |
| 19 | Zoning phrase matches the OM or a verified GIS pull verbatim |
| 20 | If concealment overlay active (Rule 0c): ZERO occurrences of "1031" / "exchange" / "drop-and-swap" |
| 21 | Deposit window appears once, in Deposit Terms, from `{{EMD_DUE_DAYS_WORDS}}` |
| 22 | Vacant deals: preservation covenant present in Operations |
| 23 | **Offer ≤ Walk Price (v1.8).** Compare `ORA Offer Price` against `Walk Price`. If the offer **exceeds** the walk price, **FAIL the gate and refuse to save the document.** Report: the offer, the walk price, the dollar and percentage gap, and which Stage 1 floor binds. The only permitted override is an **Exception Register** entry (per acquisition-underwriting's EXCEPTION REGISTER + TRIPWIRE) carrying a one-sentence compensating factor and Gabriel's explicit in-turn ratification (ratified against a walk solved under `acquisition-underwriting` v4.37 or later: an exception ratified against a pre-v4.37 walk must be re-ratified against the re-solved walk) — logged to the ranking workbook's Exception Register tab **and** the Notion row's "Exception Compensating Factor" field **before** the document is saved, not after. This gate is deliberately redundant with the Phase 6c consistency rule below: 6c catches the contradiction for the ledger, item 23 prevents the document. Two live incidents where 6c alone was insufficient — 511 REDACTED-091 Road (Walk $930K / LOI $1.45M, loss permanently `UNCLASSIFIED` as a result) and 3700 REDACTED-158 Blvd (Walk $2,661,000 / drafted LOI $3,800,000, caught only because a FULL underwrite was separately requested four days after the LOI was drafted). |
| 24 | **Parcel pre-flight (v1.16).** Rule 0d block present and dated within 14 days; Seller name in the acceptance block matches the auditor's owner of record exactly; every Rule 0d flag answered in the LOI text or by a Gabriel waiver noted in chat. FAIL on a missing pull, an owner mismatch, or an unanswered flag. |

If any check fails, fix and re-run. Do not present a failing file.

### Phase 6 — Save and present
1. Filename: `LOI [Property Street] [City] [State] [M.D.YYYY].docx` — match Gabriel's convention (e.g., `LOI REDACTED-113 Rd Gahanna OH 5.14.2026.docx`).
2. Save to outputs folder.
3. Generate PDF preview via `soffice --headless --convert-to pdf`.
4. Present both files to user via `present_files`.
5. Log to Notion Acquisition Pipeline Tracker (`bcfe4a03`): `LOI Status` = "Submitted"; the dedicated **`LOI Expiration Date`** date field = `{{OFFER_EXPIRATION_DATE}}` (**never only into `Next Action` prose** — `ora-deal-aging-sla` STEP 3c reads the column); link to file; one-line terms summary in `Next Action`; **`Last Activity` = today (date-only)** (what `ora-deal-command-board` reads for staleness); **`Next Action Date`** = the date ORA must next act on (normally the seller-response deadline; NULL if none — never default it to the expiration). **Keep the two dates distinct even when they coincide.** **Read references/notion-logging.md before writing the Notion row** for the full rule text and its 470 REDACTED-148 origin.

### Phase 6b — Deal Terms Register (MANDATORY — at draft AND at execution)
The register is the deal's tracking point for every material term — especially terms agreed OUTSIDE the LOI (easements, parcel exclusions, verbal agreements, strategy-driven omissions), which exist in NO binding document until the PSA captures them. Origin (754 Old State easement gap, 2026-06-11): references/notion-logging.md.

1. **At draft time**: create `DEAL-TERMS-REGISTER.md` in the deal folder (status DRAFT). Sections:
   - **Off-LOI terms** — every term agreed in negotiation but deliberately or accidentally not in the LOI. ASK the user explicitly: "What was agreed with the seller that is NOT in this LOI?" Each item gets: source (memo/notes/call), **Must land in** (PSA / DD / closing docs), **Status** (OPEN/RESOLVED).
   - **Strategy constraints** — positions to keep OUT of deal documents (e.g., no tenant-retention commitments, confidential rationales). Marked INTERNAL ONLY.
   - **Tracking items** — facts that must reconcile through DD (SF discrepancies, stale title work, election deadlines that expire at PSA execution).
2. **At execution** (when the countersigned LOI returns): update the register to EXECUTED status, re-confirm the off-LOI list against the final negotiation record, and date it.
3. Header must carry: "INTERNAL ONLY — never share with seller, broker, or any counterparty."
4. Downstream: deal-execution Workflow 2A reads this register at every PSA draft/redline round — every OPEN "Must land in: PSA" item missing from a draft is an automatic CRITICAL. psa-reconciliation validates the executed PSA against it.
5. Confidential-deal overlay: for hook-protected deals, the register stays in the deal folder / approved staging paths only (rules.md §7a) — never in outputs/ trees bound for external surfaces.

### Phase 6c — Lost-Deal Ledger capture (MANDATORY — at draft time)
Write ORA's own offer into structured Notion fields the moment the LOI exists — every value is already in working memory now and expensive or impossible to reconstruct later. This is the capture half of the lost-deal post-mortem ledger; `ora-passed-deal-tracker` Step 4b writes the outcome half.

1. Locate the deal's row in the Notion **Deal Sourcing Log** (`collection://9a6ae219-85a3-4621-899c-c757fd062f8b`), matching on normalized street address. **If no row exists, create one** — a deal that reached LOI without a sourcing row is a gap, not a reason to skip capture. **If more than one row matches, do not guess:** write to the row with the most complete underwriting and flag the duplicate to Gabriel (this is live — `511 REDACTED-091 Road` currently has two rows).

2. Set these properties (Block A):

   | Property | Value |
   |---|---|
   | `LOI Sent Date` | the date the LOI is actually delivered (leave NULL at draft if unshipped) |
   | `ORA Offer Price` | the purchase price in the LOI |
   | `ORA Offer $/SF` | offer ÷ Total SF |
   | `ORA Basis @ Offer (% RCT LOW)` | all-in basis ÷ the construction-type-adjusted RCT v03 LOW for the market (POINT × multiplier + adders, × 0.9, per `acquisition-underwriting` v4.37; equals the bare LOW for tilt-up/precast with no adder) |
   | **`ORA Max Defensible Price`** | **see §3 — the load-bearing number** |
   | `Offer: DD Days` / `Offer: Close Days` / `Offer: Deposit $` | from the LOI terms |
   | `Offer: All-Cash` / `Offer: Financing Contingency` | from the LOI terms |
   | `LOI Outcome` | `PENDING` |

3. **`ORA Max Defensible Price` — compute it NOW, at LOI time.** It is the price at which this deal *first breaches a Stage 1 floor* (the vintage-ramp basis floor or the 8% YoC floor, whichever binds first). Fixed at this moment and **never recomputed at outcome time** — recomputing once the winning price is known is hindsight bias, and the downstream classifier refuses a value written after the fact; without it a lost deal is permanently `UNCLASSIFIED`. It is a *different number from `Walk Price`*, and both must be consistent with `ORA Offer Price`. **An offer above the walk price is a contradiction — stop and resolve it, do not write both.**

4. `LOI Sent Date` is written at Phase 7b (confirmed-sent write-back), not here. A drafted LOI that never ships is logged `LOI Outcome = EXPIRED-UNSENT` with `ORA Offer Price` left **BLANK** — an unsent LOI has no offer price. Full text and live examples (511 REDACTED-091 Road, 470 REDACTED-148 Blvd): references/notion-logging.md.

5. This phase writes ORA's own numbers only. It never records a competitor's price, never estimates one, and never recommends an offer level.

6. **Re-query immediately before any create (v1.17).** A dedupe done earlier in the run can be stale: a sourcing scan may have created the row since. Right before creating a Deal Sourcing Log row, query the data source again by the natural key (normalized street address, then `Listing URL`) across rows of EVERY `Status`, `Dead` and `Passed` included, and update a match instead of creating a row. Query the data source, not search alone (search lags, so a miss there proves nothing). If a create returns no page ID or a quota notice, follow the scans' STEP 5 CREATE-VERIFY rule: look the row up by the same key and never blind-retry the create. A duplicate that appears anyway is flagged to Gabriel and resolved only by `deal-retirement` step 3a, the one place the first-sighting fields may move between rows. This applies to item 1 here and to Phase 7b item 3.

7. **Never-write fields (v1.17).** This skill never writes `Verdict at First Sighting` or `Score at First Sighting` in any phase: on a row it creates (here or Phase 7b item 3) both stay BLANK, and on a row it updates both stay exactly as found. They are the sourcing scans' write-once original prediction, written on row creation only, which the monthly back-test (`maintenance/funnel-backtest.py` in `~/.claude`) grades against the row's later outcome; an LOI is not a first sighting. This skill also never sets `Status = Dead` (reserved for a listing that is gone) and never records a pass: a pass or kill after LOI is recorded by `deal-retirement` as `Go / No-Go` = 🔴 Pass.

### Phase 7 — Optional SHIP mode
If user requested ship:
1. Re-confirm QC #23 against a walk solved under `acquisition-underwriting` v4.37 or later (an exception ratified against a pre-v4.37 walk does not pass) before drafting the email. Draft the email for Gabriel's review. (Composio `OUTLOOK_*` retired 2026-06-11 — connector removed, no fallback. The approved send, if Gabriel green-lights, runs via Outlook COM `C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1`, the SOLE send path.)
2. To: `{{SELLER_BROKER_EMAIL}}` (pull from HubSpot).
3. Cc: per thread context — no blanket cc of both principals (CC discipline, ratified 2026-06-10). Never `ze@oxfordra.net`.
4. Subject: `LOI — [Property Street], [City], [State]`.
5. Body: 3-sentence cover note in ORA broker voice (collegial, market-aware, no over-commitment). Attach DOCX and PDF.
6. Do NOT send — present the draft for Gabriel's review and approval. Pause for explicit go-ahead before send.

### Phase 7b — Confirmed-sent write-back (v1.16; Gabriel in-turn 2026-10-30)
Runs ONLY when Gabriel states in-turn that this LOI was actually SENT, whether by Phase 7 or by hand. A drafted, saved, approved or ship-drafted LOI is NOT sent: never infer "sent" from a draft, a file or a send request. Until Gabriel confirms, nothing in this phase is written.
1. Find the row in the Notion **Deal Sourcing Log** (`collection://9a6ae219-85a3-4621-899c-c757fd062f8b`) by deal name / normalized street address (`Deal Name / Address`), preferring the row Phase 6c wrote for this LOI. **More than one plausible row, or no confident match: ask Gabriel which row, naming the Phase 6c row. Do not guess.** (This is stricter than Phase 6c item 1. Phase 6c writes draft-time fields, and this phase writes the field the sourcing scorecard counts as an LOI.)
2. Set `LOI Sent Date` (`date:LOI Sent Date:start`, date only) = the date Gabriel gives (if he gives none, ask; do not assume today), and `LOI Outcome` = `PENDING`. If `ORA Offer Price` is blank (an unsent-LOI row), set it to the price in the sent LOI. If `LOI Outcome` already holds WON, LOST, SELLER-PULLED, WINNER-BUSTED or TERMINATED-DILIGENCE, or `LOI Sent Date` already holds a different date, stop and ask before overwriting. `EXPIRED-UNSENT` or empty becomes `PENDING`.
3. **No row:** create one with the minimal fields: `Deal Name / Address`, `LOI Sent Date` and `LOI Outcome` = `PENDING`, plus `ORA Offer Price` when it is the figure in the sent LOI. Then tell Gabriel the row was created and that it lacks the Phase 6c Block A capture (`ORA Max Defensible Price` in particular) until Phase 6c is run on it.
4. Confirm the write back to Gabriel (row, date, outcome). This phase writes only the fields named above, and never the Phase 6c item 7 never-write fields; a Phase 7b item 3 create re-queries first per Phase 6c item 6. It never edits a governor constant, a score or a walk price. Rationale: references/notion-logging.md.

---

## STANDARDS — ORA defaults reference

**Read references/ora-standards.md before applying any default** — headline economic terms with acceptable ranges (EMD, Study Period, Closing post-Study, Exclusivity, PSA draft/execution, Phase I auto-extension, Tenant Estoppel timing), buyer entity, standing positions never negotiated at LOI stage, and the negotiable-but-defended list.

---

## STATE OVERLAYS

Full overlay text for OH/MD/IN/MO/KS/WI/TN, the quick-reference summary, and the Ohio HB 126 BOR rule live in `references/state-overlays.md` — **read it before resolving the Costs tokens for any non-Ohio property and before asserting Ohio BOR risk.**

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

Notion (`notion-search`/`notion-fetch`/`notion-update-page` — Pipeline Tracker, Deal Sourcing Log, Tenant DB) · HubSpot (`search_crm_objects`/`get_crm_objects` — broker contacts) · Outlook COM `send-via-outlook.ps1` via Desktop Commander `start_process` (SHIP mode only, after explicit approval — the SOLE send path; Composio `OUTLOOK_*` retired 2026-06-11) · `python-docx` · `soffice` headless · `present_files`. Table: references/connectors-and-special-cases.md.

---

## SPECIAL CASES

**Read references/connectors-and-special-cases.md before Phase 2 when the deal is multi-tenant, vacant, in a state outside the seven-state overlay list, a sale-leaseback, or the seller refuses long proration.** Hard rules that survive regardless: unfamiliar-state deals carry a `[FORECAST]` flag and a placeholder §6 and never ship without user verification; sale-leaseback = affiliated single-tenant with all four conditionals firing; vacant deletes all four conditionals.

---

## VERSIONING

- v1.17 — 2026-11-05, **never-write first-sighting fields** (Gabriel-approved write-once rule, business-loops review F-11): new Phase 6c item 6 (re-query the Sourcing Log by natural key immediately before any create, so a scan-created row is never duplicated; merge-gate F-001 on #214) and item 7, cited by Phase 7b item 4 — no phase writes `Verdict at First Sighting` or `Score at First Sighting` (blank on a created row, untouched on an updated one), none sets `Status = Dead`, and a pass after LOI is recorded by `deal-retirement` as `Go / No-Go` = 🔴 Pass. Removed the stale duplicate `(v1.15)` H1 line. No score, gate, floor, walk-price or governor value changed.
- v1.16 — 2026-10-30, **Phase 7b confirmed-sent write-back** (Gabriel, in-turn 2026-10-30, Deal Sourcing Expansion Plan §6 and §10). When Gabriel confirms an LOI was actually SENT, write `LOI Sent Date` and `LOI Outcome` = `PENDING` to the matching Deal Sourcing Log row (`collection://9a6ae219-85a3-4621-899c-c757fd062f8b`). Draft-only stays draft-only: "sent" is never inferred from a draft. An ambiguous row match is asked, never guessed. No row → create one with minimal fields. Root cause: the weekly sourcing scorecard showed 0 LOIs in 90 days because Phase 6c item 4 deferred `LOI Sent Date` to Phase 7, which never wrote it. Phase 6c item 4 re-pointed to 7b; v1.9 and v1.10 archived to `versions/CHANGELOG-v1.9-v1.10.md` under the retention rule. **No QC Gate item, template, token or governor constant changed.**
- v1.16 — 2026-10-30 (authored 2026-10-27 in Cowork as v1.14; captured by runtime-cache PR #170, renumbered over main v1.13/v1.14 and v1.15), parcel-record pre-flight (Rule 0d): `Parcel Record` required input; Phase 1 step 5 pulls owner of record, land use, structure type, last transfer and tax status from the county auditor/assessor; Phase 2 step 7 maps flags to responses (use-classification → Zoning term + last-occupancy disclosure; tax arrearage → full prior-year credit); QC item 24. Origin: 511 REDACTED-091 Rd — Franklin County parcel REDACTED-135-00 showed structure "Health Spa" / land use 499 and 2025 taxes paid $33,373 vs $18,646 billed, none in the broker package. Supersedes a parallel "v1.12" draft built on stale v1.11 (captured as PR #168, never merged). No template, token, script, overlay or walk-price rule changed.
- v1.15 — 2026-10-30 (authored 2026-10-27 as v1.13; renumbered on rebase over main's v1.13/v1.14), **SHORT becomes the only LOI format (Gabriel, in-turn: all LOIs must match the format of the SHORT-form LOI he sent on 10/20/2026).** Root cause of the request: an Ohio re-engagement LOI was drafted from a stale installed v1.11 copy of this skill in the old navy/gold master, because v1.12 had not been re-imported. Changes: CONDENSED/STANDARD fallbacks replaced by SHORT conditional terms (Tenant Conditions, Purchase Option, Zoning) and inline tokens (`{{ENTITY_INTEREST_SENTENCE}}`, `{{DD_DELIVERY_ADDITIONS}}`, `{{CONFIDENTIALITY_TENANT_CARVEOUT}}`); Due Diligence auto-extension also covers a Buyer-elected Phase II and VAP determinations; Confidentiality adds "as required by law"; new `templates/fill_shortform.py` and `templates/qc_shortform.py`; `build_shortform.py --cropped` rebuilds from the embedded logos (pixel-identical); CONDENSED master moved to `templates/archive/` (not deleted); SKILL.md QC gate is SHORT-only (item 23 walk-price gate unchanged). Tested: vacant OH 2 pp; vacant OH + Zoning + entity sentence 3 pp; tenanted MO + Purchase Option + Tenant Conditions 3 pp. No state overlay, walk-price rule, Notion logging, or governor constant changed.
- v1.14 — 2026-10-28, input precondition: blanket rule — any walk price solved before `acquisition-underwriting` v4.37 is re-solved before any LOI (v4.37 moved the multiplier, the R% denominator, the allocation weights and the off-table proxy source); stale Notion `ORA Walk` values are not valid inputs. The walk-price definition now reads the highest (not lowest) price clearing all binding Stage 1 floors. QC #23 and Phase 7 require the Exception Register entry to be ratified against a walk solved under v4.37 or later. QC #23 (ratification vintage) and Phase 7 (re-confirm QC #23) are amended; no other phase, gate or template changed.
- v1.13 — 2026-10-27, consumer sweep for `acquisition-underwriting` v4.37: the Phase 6c field `ORA Basis @ Offer (% RCT LOW)` divides by the construction-type-adjusted RCT LOW so the lost-deal ledger and back-test record basis on the same denominator as the screen. No phase, gate or template changed.
- v1.12 — 2026-10-20, **SHORT two-page form becomes the default** (Gabriel, in-turn: adopt the Lucern Capital Partners buy-side LOI form — seller signing speed and document simplicity first). New `templates/LOI_ShortForm_Template.docx` (+ `build_shortform.py`) in Lucern's layout with ORA logo, buyer information and signatory; credentials moved to page 1 (Buyer Information page dropped for SHORT); carried from Lucern: buyer-chosen title company (Lucern's buyer closing extension against an added deposit was adopted, then removed the same day — Gabriel 2026-10-20: no buyer closing-extension option); ORA protections layered in: explicit all-cash statement (RE line, intent paragraph, Purchase Price: no financing or appraisal contingency), Phase I→II extension, defect-free assumption, lease/contract consent, fixed-term exclusivity with marketing stop, specific performance, designee vesting, 1031 cooperation, mutual confidentiality, named binding provisions, "Eastern Time" expiry wording. Re-trade ("price subject to review") and leasing/marketing-control language deliberately not adopted. CONDENSED retained as the fallback on the Rule 0b triggers. New tokens `{{DEED_FORM}}`, `{{TRANSFER_TAX_SENTENCE}}`, `{{OPERATIONS_CONDITIONAL_SENTENCE}}`; state table and SHORT QC replacements in `references/short-form.md`. Supersedes the never-merged 2026-10-17 concise-template ruling captured in PR #146. Walk-price precondition and QC #23 unchanged; no governor constant changed.
- v1.11 — 2026-10-18, walk-price definition cites the acquisition-underwriting v4.33 IRR floor (10-yr unlevered, rate-linked): name the UST10 value and date a walk price was solved at; walk prices solved before v4.33 are re-solved. Wording only — no phase, gate or template changed.
- **v1.10 (2026-09-23) — full text: `versions/CHANGELOG-v1.9-v1.10.md`.** Outbound buyer-profile facts corrected; no numeric leverage in counterparty text. Archived 2026-10-30.
- **v1.9 (2026-09-10) — full text: `versions/CHANGELOG-v1.9-v1.10.md`.** Retention rule adopted (6-entry count cap, ~2,000-char per-entry cap). Archived 2026-10-30.

**Retention rule (added 2026-09-10, ORA Automation Audit R24-11):** keep at most the **6 most recent versions** as full inline entries. The edit that would add a 7th must, in the same pass, compress the oldest full entry to a one-line `**vX.Y (date):** Full text: versions/CHANGELOG-vA.B-vX.Y.md` summary and append its full original text to the versions file for that range. **Per-entry cap ~2,000 characters** — an entry that would exceed it states its finding and verdict inline and cites the deal folder or `versions/` file for the detail. Check both caps in the pass that adds an entry — never as deferred cleanup. Full rule text and calibration: `versions/CHANGELOG-v1.4-v1.8.md`.

- **v1.8 (2026-08-22) — full text: `versions/CHANGELOG-v1.4-v1.8.md`.** Walk-price precondition moved upstream: `Walk Price` added to required inputs (refuse to draft without it — run `acquisition-underwriting` first) and hard-fail QC Gate item 23 (Offer ≤ Walk Price; override only via a ratified Exception Register entry). Phase 6c left deliberately redundant. Origin: 511 REDACTED-091 Road, 3700 REDACTED-158 Blvd. No scorecard weight, Stage 1 floor, or governor constant changed. Archived 2026-09-22 under the retention rule.
- **v1.7 (2026-08-21) — full text: `versions/CHANGELOG-v1.4-v1.8.md`.** Repo-first reconciliation of two independently-built v1.6 revisions; template v1.1 adopted; Phase 6c retained. Archived 2026-09-22.
- **v1.6 (2026-08-18) — full text: `versions/CHANGELOG-v1.4-v1.8.md`.** Template/skill sync pass (3700 REDACTED-158 Blvd): `{{PROPERTY_ZONING_PHRASE}}` and inline §13 `{{ENTITY_INTEREST_TYPE}}` wired into template v1.1; Execution Page subtitle and tenant-disclosure punctuation defects fixed. Archived 2026-09-22 under the retention rule.
- **v1.6 (2026-08-16) — full text: `versions/CHANGELOG-v1.4-v1.8.md`.** Lost-Deal Ledger capture (Phase 6c) incl. `ORA Max Defensible Price`; Deliverables item 10. Archived 2026-09-22.
- **v1.4 (2026-06-11) — full text: `versions/CHANGELOG-v1.4-v1.8.md`.** Deal Terms Register (Phase 6b), consumed by deal-execution Workflow 2A and psa-reconciliation. Archived 2026-09-22.
- **v1.3 (2026-06-11) — full text: `versions/CHANGELOG-v1.0-v1.3.md`.** Composio-retirement merge; SHIP mode re-pointed to the Outlook COM sole send path. Archived 2026-09-10 to hold the 6-entry cap.
- **v1.2 / v1.1 / v1.0 — full text: `versions/CHANGELOG-v1.0-v1.3.md`** (v1.2 2026-06-10 adversarial hardening; v1.1 2026-06-10 470 REDACTED-148 calibration incl. Rule 0/0b/0c; v1.0 initial release May 2026). Archived 2026-09-10 under the retention rule above.


---

## FAILURE MODES — when NOT to use this skill

- **Owner-occupied property where ORA is selling, not buying** — wrong direction; use `deal-execution` skill for sale side
- **Refinance proposal** — use `debt-management` skill
- **Off-market lease proposal** (ORA leasing to a third party) — `re-operations` retired 2026-08-05 (redundant with named ops siblings, no direct-execution evidence); for the lease document itself, use `lease-form-qc`
- **PSA stage** — handoff to `deal-execution` skill once LOI is executed; this skill stops at LOI delivery (sole exception: Phase 6b register update to EXECUTED status when the countersigned LOI returns)

---

## OUTPUT GUARANTEES

Every successful run of this skill produces:
1. A SHORT-form DOCX in the ORA house format — 2 pages, 3 when a conditional term fires
2. A PDF preview with extractable text
3. A delivered file pair (Cowork `present_files`; chat `SendUserFile`)
4. A Notion log entry on the Acquisition Pipeline Tracker
5. Zero "shall" usage, zero banned phrases, `qc_shortform.py` exit 0, full 24-point QC Gate pass
5. Zero "shall" usage, zero banned phrases, `qc_shortform.py` exit 0, full 23-point QC Gate pass
6. Phone 301.512.6125 in the address footer on every page
7. Oxford logo header on every page (large on page 1)
8. "Proof of funds available upon request." centered italic directly below the acceptance block
9. `DEAL-TERMS-REGISTER.md` created (or updated) in the deal folder per Phase 6b
10. Deal Sourcing Log row carries the Phase 6c Block A capture — in particular a non-NULL **`ORA Max Defensible Price`** and `LOI Outcome = PENDING`. A blank Max Defensible price means this deal can never be classified if it is lost; treat it as an incomplete deliverable, not a nice-to-have.
