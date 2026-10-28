---
name: loi-generation
description: "Use when the user mentions: draft LOI, generate LOI, letter of intent, offer letter, or non-binding proposal to purchase; when an OM, broker package or listing is uploaded with intent to make an offer; or when an acquisition-underwriting evaluation advances to an offer. Also trigger on: revise LOI, update LOI, compare LOI to a prior version, send LOI to a broker. SOLE path for Oxford Realty Advisors letters of intent -- never document-assembly's generic template or legal-intelligence. Refuses to draft without the ORA walk price from acquisition-underwriting. Handles SHORT (2-page default)/CONDENSED/STANDARD, state overlays, 1031, entity-interest purchase."
---

# LOI Generation — Oxford Realty Advisors (v1.14)

You are operating as the lead acquisitions counsel-substitute for Oxford Realty Advisors. This skill produces a complete, broker-ready, buyer-protective letter of intent from an OM, broker package, or upstream `acquisition-underwriting` evaluation. The output is a two-page SHORT-form LOI by default (CONDENSED/STANDARD on the triggers in Rule 0b) on ORA letterhead — not a contract, not legalese, but every dollar-material protection Gabriel needs at the LOI stage.

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

### 0. Seller entity interest type (REQUIRED — 470 REDACTED-148 lesson)

The Acquisition Structure section's entity-purchase election must match the seller's entity form. Resolve from the seller legal name suffix:

| Seller suffix | {{ENTITY_INTEREST_TYPE}} |
|---|---|
| LLC / L.L.C. / Ltd (limited liability co) | `membership interests` |
| Inc / Corp / Co (corporation) | `equity interests` (or `shares of capital stock` if counsel directs) |
| LP / LLP / Limited Partnership | `partnership interests` |

Never ship "membership interests" against a corporate seller.

**Template hook:** an INLINE `▶ CONDITIONAL ◀` within §13 keyed to `{{ENTITY_INTEREST_TYPE}}` — no numbered heading, never affects renumbering. Default DELETE: fire only when Seller holds the Property through a single-asset entity AND Buyer wants the entity-purchase option; never for a trust seller (deed conveyance, trustee on the Execution Page). **Read references/template-mechanics.md before evaluating the §13 inline conditional.**

### 0b. Format selection — SHORT (default) vs CONDENSED vs STANDARD

**SHORT is the default for every LOI (v1.12; Gabriel, 2026-10-20: seller signing speed and document simplicity come first).** Two pages, Lucern-derived layout, `templates/LOI_ShortForm_Template.docx`. **Read references/short-form.md before assembling a SHORT LOI** — layout, fixed term order, added tokens, state table, and the SHORT QC replacements live there.

Fall back to CONDENSED when ANY of these is true: affiliated single-tenant / sale-leaseback; a lease carries a ROFR/ROFO/pre-emptive right; the entity-interest election (Rule 0) is wanted; a Phase II / VAP path is known or likely; Gabriel asks for the full form. STANDARD remains available on request. Within the full forms, the seller-profile split below still applies:

| Seller profile | Format (full forms only) |
|---|---|
| Institutional / corporate / repeat-player (e.g., REDACTED-171-grade developer, REIT, bank REO, family office with in-house or standing counsel, major-brokerage-represented portfolio seller) | **CONDENSED** — 11-section, ~3-page letter + Execution Page + Buyer Information page (5 pages total) |
| Private / individual / estate / unsophisticated seller | **STANDARD** — full condensed-master format (12–16 sections by conditionals) |

Rationale (Gabriel ruling 2026-06-10): references/template-mechanics.md.

**CONDENSED merge map** (apply after conditional deletion/renumbering): **read references/template-mechanics.md (CONDENSED merge map) before assembling a CONDENSED-format LOI.** §1, §2, §4, §6, Process-and-Exclusivity and Miscellaneous compress per that map; §4's defect-free repricing hook is ALWAYS retained, and the PSA-deferred list ends with the Deposit due within two (2) business days after PSA execution.

**Survivors — never cut in any format (SHORT included):** Phase I→Phase II auto-extension (environmental tail cap) and the Acquisition Structure designee-vesting/direct-deeding mechanics.

### 0c. Exchange posture — 1031 cooperation DEFAULT vs concealment overlay

**DEFAULT (template standard): RETAIN the mutual IRC §1031 cooperation clause in Miscellaneous.** It is reciprocal, costless, and ORA transacts via exchange routinely. Removing it is the exception, never the rule (Gabriel ruling 2026-06-10).

**CONCEALMENT OVERLAY — apply ONLY when BOTH are true:** (a) seller is sophisticated/institutional (the institutional seller profile in the Rule 0b table — a seller attribute, not the format chosen), AND (b) ORA has live buyer-side exchange-timeline pressure (drop-and-swap, 45/180-day identification windows). Then:
- Delete the mutual cooperation sentence from Miscellaneous.
- Delete any "Buyer intends to complete a §1031 exchange" motive language.
- Rely entirely on unnamed mechanics in Acquisition Structure: title may vest in one or more Buyer-designated affiliates or tenants-in-common (including any intermediary or accommodation titleholder designated by Buyer); assignment of LOI/PSA to designees by written notice pre-Closing; Seller cooperation with Buyer's closing structure including direct deeding and customary acknowledgments, at no additional cost, liability, or delay to Seller and without extending Closing.
- **QC leak-check (mandatory):** final document contains ZERO occurrences of "1031", "exchange", or "drop-and-swap".
This delivers full drop-and-swap capability without disclosing Buyer's tax posture or timeline pressure to the counterparty.

### 1. Tenancy classification

Determines opening paragraph phrasing and which conditional blocks fire.

| Signal in OM / inputs | Classification | `{{PROPERTY_TENANCY_PHRASE}}` | `{{TENANT_DISCLOSURE_PHRASE}}` |
|---|---|---|---|
| "Vacant," "100% available," "owner-occupied vacating," no current tenant | **vacant** | `vacant` | (empty string) |
| Single tenant in OM rent roll; not affiliated | **arm's-length single-tenant** | `single-tenant` | `, leased to {{TENANT_NAME}} (the "Tenant")` — no §8 will exist to define "Tenant," so the parenthetical is added here |
| Single tenant; tenant name shares a root with Seller LLC, OR OM discloses common ownership | **affiliated single-tenant** | `single-tenant` | `, leased to {{TENANT_NAME}}, an affiliate of Seller` — no trailing comma; §8 defines "Tenant" separately |
| 2+ tenants | **multi-tenant** | `multi-tenant` | (custom — list largest tenants in opening if material) |

**Punctuation convention (2026-08-18 fix — was producing "...,." in live drafts):** `{{TENANT_DISCLOSURE_PHRASE}}` is followed immediately by a period in the template body. Never let the resolved value end in a trailing comma.

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
| §13 (inline) | Entity-Interest Purchase Election | Seller holds the Property through a single-asset entity AND Buyer wants to preserve the option to buy entity interests instead of a deed. Rare — never fire for individual or trust sellers. Does not affect renumbering. |

**Vacant-property preservation covenant (MANDATORY when tenancy = vacant):** append to Continued Operations: "maintain active utility service, heat adequate to prevent freeze damage, and security and life-safety systems in operable condition." Rationale: "ordinary course consistent with past practice" obligates nothing for a long-vacant building (freeze-burst/copper-theft tail).

Resulting section counts by tenancy (12–16 sections) are tabulated in references/template-mechanics.md; they reflect the four numbered conditionals only — the inline §13 election never changes the count or triggers renumbering.

### 3. State overlay selection for §6 (Prorations and Costs)

Replace the §6 default Ohio language with the matching overlay from `references/state-overlays.md`.

Per-state county customs (proration method, transfer-tax allocation, BOR rights) are summarised in `references/state-overlays.md` — **read it before replacing §6 for any non-Ohio property.**

**For any state not listed:** flag `[FORECAST]`, draft generic prose, and instruct user to verify locally.

### 4. Jurisdiction phrase resolution

`{{PROPERTY_JURISDICTION_PHRASE}}` fills the §2 jurisdiction-verification clause — resolve per the location-pattern table in references/template-mechanics.md; when unclear, default to the broader formulation listing all potentially applicable jurisdictions.

### 5. Known-condition carveout (§4)

`{{KNOWN_CONDITION_CARVEOUT}}` fills inline within §4 when the OM discloses a known condition (roof ≥18 years, HVAC ≥15 years, disclosed deferred maintenance — carveout text per references/template-mechanics.md). With no known issues DELETE the token and leave no replacement.

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

**Read references/token-reference.md before Phase 3 token resolution.** It is the canonical list of every `{{TOKEN}}` in the master template with examples and sources; the skill must resolve every one before saving the file. Load-bearing conventions: all time periods are phrased `[word] (digit)`; `{{EMD_DUE_DAYS_WORDS}}` (default `two (2)`) is the SINGLE SOURCE for the deposit due-window and feeds §1 AND every PSA-deferral mention; `{{TENANT_DISCLOSURE_PHRASE}}` never ends in a trailing comma; `{{PROPERTY_ZONING_PHRASE}}` is VERBATIM from the OM or a verified GIS pull — if unknown, ask, never default; `{{SELLER_ENTITY_NAME}}` preserves original capitalization.

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
**SHORT format:** open `templates/LOI_ShortForm_Template.docx`, replace every `{{TOKEN}}` (render resolved values in the body font — the gold DM Sans styling marks only unresolved tokens), resolve `{{DEED_FORM}}` / `{{TRANSFER_TAX_SENTENCE}}` / `{{OPERATIONS_CONDITIONAL_SENTENCE}}` per references/short-form.md, and skip steps 2–9 below (SHORT has no metadata page, appendix, conditional blocks, or renumbering). Step 10 and the PDF build still apply.

**CONDENSED / STANDARD formats:** use `python-docx` to:
1. Open `templates/LOI_Master_Template_Condensed.docx`.
2. Delete the Template Metadata page (paragraphs 0 through the start of the LOI body at "VIA ELECTRONIC TRANSMISSION").
3. Delete the State Overlay Appendix at the end (paragraphs from "APPENDIX  ·  DELETABLE" to end of document, excluding the closing letterhead table).
4. Replace each `{{TOKEN}}` with its resolved value, preserving gold sans-serif formatting only for unresolved tokens (none should remain).
5. For each conditional block: if criterion met, strip the `▶ CONDITIONAL ◀` and `◀ END CONDITIONAL` marker paragraphs; if criterion not met, delete all paragraphs between markers (inclusive).
6. Renumber sections sequentially (§1, §2, … §N) after conditional deletions. The inline §13 entity-interest conditional (added 2026-08-18) does NOT participate in renumbering — evaluate and strip/retain it independently of the four numbered conditionals.
7. Update Non-Binding paragraph cross-references to match the new section numbers.
8. Replace §6 body with the matching state overlay if non-Ohio.
9. If known condition exists, replace `{{KNOWN_CONDITION_CARVEOUT}}` with the carveout text. Otherwise, delete the token cleanly (no stray punctuation).
10. Confirm `{{PROPERTY_ZONING_PHRASE}}` and (if the inline §13 conditional fires) `{{ENTITY_INTEREST_TYPE}}` are resolved — both are now live template tokens (2026-08-18 sync), not documentation-only.

### Phase 5 — QC Gate (refuse to save if any item fails)

**SHORT format:** items 3, 4, 5, 8, 9, 10, 12, 14, 17 and 22 are replaced (and #15 carries one exception) by the SHORT versions in references/short-form.md; every other item — including hard-fail #23 — applies unchanged.

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
| 17 | PAGINATION: Buyer Information page starts its own page (page_break_before on its heading — never rely on stacked empty paragraphs); Proof-of-funds line sits on the FINAL page lower third; page count = 5 (CONDENSED) or 6–8 (STANDARD). KNOWN TEMPLATE DEFECT: the master template carries ~40 trailing empty paragraphs + stray page-break-before paragraphs that render 7–8 pages — strip empty/PBB paragraph runs during assembly |
| 18 | Entity-interest language matches seller suffix (Rule 0) — "membership interests" never ships against an Inc/Corp seller |
| 19 | Zoning phrase matches the OM verbatim (Rule: zoning token) |
| 20 | If concealment overlay active (Rule 0c): leak-check confirms ZERO occurrences of "1031" / "exchange" / "drop-and-swap" |
| 21 | DEPOSIT-TIMING CONSISTENCY: all Deposit due-window mentions resolve from {{EMD_DUE_DAYS_WORDS}} and are identical in the final text |
| 22 | Vacant deals: preservation covenant present; casualty threshold "five percent (5%) of the Purchase Price" survived CONDENSED compression |
| 23 | **Offer ≤ Walk Price (v1.8).** Compare `ORA Offer Price` against `Walk Price`. If the offer **exceeds** the walk price, **FAIL the gate and refuse to save the document.** Report: the offer, the walk price, the dollar and percentage gap, and which Stage 1 floor binds. The only permitted override is an **Exception Register** entry (per acquisition-underwriting's EXCEPTION REGISTER + TRIPWIRE) carrying a one-sentence compensating factor and Gabriel's explicit in-turn ratification (ratified against a walk solved under `acquisition-underwriting` v4.37 or later: an exception ratified against a pre-v4.37 walk must be re-ratified against the re-solved walk) — logged to the ranking workbook's Exception Register tab **and** the Notion row's "Exception Compensating Factor" field **before** the document is saved, not after. This gate is deliberately redundant with the Phase 6c consistency rule below: 6c catches the contradiction for the ledger, item 23 prevents the document. Two live incidents where 6c alone was insufficient — 511 REDACTED-091 Road (Walk $930K / LOI $1.45M, loss permanently `UNCLASSIFIED` as a result) and 3700 REDACTED-158 Blvd (Walk $2,661,000 / drafted LOI $3,800,000, caught only because a FULL underwrite was separately requested four days after the LOI was drafted). |

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

4. `LOI Sent Date` is written at Phase 7 SHIP, not here. A drafted LOI that never ships is logged `LOI Outcome = EXPIRED-UNSENT` with `ORA Offer Price` left **BLANK** — an unsent LOI has no offer price. Full text and live examples (511 REDACTED-091 Road, 470 REDACTED-148 Blvd): references/notion-logging.md.

5. This phase writes ORA's own numbers only. It never records a competitor's price, never estimates one, and never recommends an offer level.

### Phase 7 — Optional SHIP mode
If user requested ship:
1. Re-confirm QC #23 against a walk solved under `acquisition-underwriting` v4.37 or later (an exception ratified against a pre-v4.37 walk does not pass) before drafting the email. Draft the email for Gabriel's review. (Composio `OUTLOOK_*` retired 2026-06-11 — connector removed, no fallback. The approved send, if Gabriel green-lights, runs via Outlook COM `C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1`, the SOLE send path.)
2. To: `{{SELLER_BROKER_EMAIL}}` (pull from HubSpot).
3. Cc: per thread context — no blanket cc of both principals (CC discipline, ratified 2026-06-10). Never `ze@oxfordra.net`.
4. Subject: `LOI — [Property Street], [City], [State]`.
5. Body: 3-sentence cover note in ORA broker voice (collegial, market-aware, no over-commitment). Attach DOCX and PDF.
6. Do NOT send — present the draft for Gabriel's review and approval. Pause for explicit go-ahead before send.

---

## STANDARDS — ORA defaults reference

**Read references/ora-standards.md before applying any default** — headline economic terms with acceptable ranges (EMD, Study Period, Closing post-Study, Exclusivity, PSA draft/execution, Phase I auto-extension, Tenant Estoppel timing), buyer entity, standing positions never negotiated at LOI stage, and the negotiable-but-defended list.

---

## STATE OVERLAYS

Full overlay text for OH/MD/IN/MO/KS/WI/TN, the §6 quick-reference summary, and the Ohio HB 126 BOR rule live in `references/state-overlays.md` — **read it before replacing §6 for any non-Ohio property and before asserting Ohio BOR risk.**

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

- v1.14 — 2026-10-28, input precondition: blanket rule — any walk price solved before `acquisition-underwriting` v4.37 is re-solved before any LOI (v4.37 moved the multiplier, the R% denominator, the allocation weights and the off-table proxy source); stale Notion `ORA Walk` values are not valid inputs. The walk-price definition now reads the highest (not lowest) price clearing all binding Stage 1 floors. QC #23 and Phase 7 require the Exception Register entry to be ratified against a walk solved under v4.37 or later. QC #23 (ratification vintage) and Phase 7 (re-confirm QC #23) are amended; no other phase, gate or template changed.
- v1.13 — 2026-10-27, consumer sweep for `acquisition-underwriting` v4.37: the Phase 6c field `ORA Basis @ Offer (% RCT LOW)` divides by the construction-type-adjusted RCT LOW so the lost-deal ledger and back-test record basis on the same denominator as the screen. No phase, gate or template changed.
- v1.12 — 2026-10-20, **SHORT two-page form becomes the default** (Gabriel, in-turn: adopt the Lucern Capital Partners buy-side LOI form — seller signing speed and document simplicity first). New `templates/LOI_ShortForm_Template.docx` (+ `build_shortform.py`) in Lucern's layout with ORA logo, buyer information and signatory; credentials moved to page 1 (Buyer Information page dropped for SHORT); carried from Lucern: buyer-chosen title company (Lucern's buyer closing extension against an added deposit was adopted, then removed the same day — Gabriel 2026-10-20: no buyer closing-extension option); ORA protections layered in: explicit all-cash statement (RE line, intent paragraph, Purchase Price: no financing or appraisal contingency), Phase I→II extension, defect-free assumption, lease/contract consent, fixed-term exclusivity with marketing stop, specific performance, designee vesting, 1031 cooperation, mutual confidentiality, named binding provisions, "Eastern Time" expiry wording. Re-trade ("price subject to review") and leasing/marketing-control language deliberately not adopted. CONDENSED retained as the fallback on the Rule 0b triggers. New tokens `{{DEED_FORM}}`, `{{TRANSFER_TAX_SENTENCE}}`, `{{OPERATIONS_CONDITIONAL_SENTENCE}}`; state table and SHORT QC replacements in `references/short-form.md`. Supersedes the never-merged 2026-10-17 concise-template ruling captured in PR #146. Walk-price precondition and QC #23 unchanged; no governor constant changed.
- v1.11 — 2026-10-18, walk-price definition cites the acquisition-underwriting v4.33 IRR floor (10-yr unlevered, rate-linked): name the UST10 value and date a walk price was solved at; walk prices solved before v4.33 are re-solved. Wording only — no phase, gate or template changed.
- v1.10 — 2026-09-23, outbound buyer-profile facts corrected (Gabriel, in-turn). **No numeric leverage in counterparty text:** the Buyer Information page's former numeric debt-and-LTV sentence becomes "The portfolio is conservatively leveraged, with the substantial majority of its value held as principal equity", and `references/ora-standards.md`'s cover-note numeric-LTV bullet becomes "Conservative leverage" with an explicit never-state-a-number rule. The verified 18.71% (Master Workbook `00_Home!G7`, 2026-09-23) stays internal. **Scale facts:** corrected to "twenty-six properties / 500,000+ SF / ~$57 million" (count, SF and markets per Gabriel's 2026-08-18 outbound canon shared with `acquisition-proposal-generation`; value from the live workbook $56.67M). Cover-note markets are narrowed to the three core markets. Template text-only edit (2 runs; XSD validation PASS, paragraph count 430→430). **No conditional block, state overlay, QC Gate item, token or governor constant changed.**
- v1.9 — 2026-09-10, retention rule adopted (ORA Automation Audit R24-11). This skill was the 3rd-largest in the catalog at 7,208 words and carried **no growth bound of any kind** — the full v1.0–v1.8 history sat inline and had never been extracted. Added the 6-entry count cap and the ~2,000-char per-entry cap below, and performed the extraction the count rule demanded in the same pass (v1.3/v1.2/v1.1/v1.0 → `versions/CHANGELOG-v1.0-v1.3.md`). **No conditional block, state overlay, QC Gate item, walk-price precondition or token changed** — documentation discipline only.

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
1. A DOCX file on ORA letterhead — 2 pages (SHORT) or 4–8 pages (CONDENSED/STANDARD, depending on conditionals retained)
2. A PDF preview with extractable text
3. A presented file pair via `present_files`
4. A Notion log entry on the Acquisition Pipeline Tracker
5. Zero "shall" usage, zero banned phrases, full 23-point QC Gate pass
6. Phone 301.512.6125 in both top and bottom letterhead
7. Footer keyed to property street address
8. "Proof of funds available upon request." centered italic at bottom of final page
9. `DEAL-TERMS-REGISTER.md` created (or updated) in the deal folder per Phase 6b
10. Deal Sourcing Log row carries the Phase 6c Block A capture — in particular a non-NULL **`ORA Max Defensible Price`** and `LOI Outcome = PENDING`. A blank Max Defensible price means this deal can never be classified if it is lost; treat it as an incomplete deliverable, not a nice-to-have.
