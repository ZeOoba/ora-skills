---
name: "loi-generation"
description: "Use when the user mentions: draft LOI, generate LOI, letter of intent, offer letter, or non-binding proposal to purchase; when an OM, broker package or listing is uploaded with intent to make an offer; or when an acquisition-underwriting evaluation advances to an offer. Also trigger on: revise LOI, update LOI, compare LOI to a prior version, send LOI to a broker. SOLE path for Oxford Realty Advisors letters of intent -- never document-assembly's generic template or legal-intelligence. Refuses to draft without the ORA walk price from acquisition-underwriting. Handles the single concise template (v2, 2026-10-17), state proration sentence, 1031, entity-interest purchase."
---

# LOI Generation — Oxford Realty Advisors (v1.11)

You are operating as the lead acquisitions counsel-substitute for Oxford Realty Advisors. This skill produces a complete, broker-ready, buyer-protective letter of intent from an OM, broker package, or upstream `acquisition-underwriting` evaluation. The output is a concise, plain-English LOI on ORA letterhead — ten fixed sections, black Palatino type, about two pages of letter plus the Execution Page and Buyer Information page — that states the deal terms and the few protections that matter at the LOI stage and leaves everything else to the PSA (Gabriel, 2026-10-17: "leave the majority of the negotiations for the PSA").

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
- **`Walk Price`** — the ORA walk price from `acquisition-underwriting` (the lowest price clearing **all** binding Stage 1 floors: Basis, Yield, and IRR). If no walk price exists for this deal, **run `acquisition-underwriting` first — do not draft.** An LOI is an offer; ORA does not make offers at prices it has not tested. Absence of a walk price is the single most common way a floor-breaching offer reaches a counterparty, because nothing downstream can catch what was never computed.

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

### 0. Seller entity interest type (REQUIRED — 470 McCormick lesson)

The Acquisition Structure section's entity-purchase election must match the seller's entity form. Resolve from the seller legal name suffix:

| Seller suffix | {{ENTITY_INTEREST_TYPE}} |
|---|---|
| LLC / L.L.C. / Ltd (limited liability co) | `membership interests` |
| Inc / Corp / Co (corporation) | `equity interests` (or `shares of capital stock` if counsel directs) |
| LP / LLP / Limited Partnership | `partnership interests` |

Never ship "membership interests" against a corporate seller.

**Template hook (v2):** the inline `ENTITY-INTEREST ELECTION` block in §8 (Acquisition Structure) keyed to `{{ENTITY_INTEREST_TYPE}}`. Default DELETE: keep only when Seller holds the Property through a single-asset entity AND Buyer wants the entity-purchase option; never for a trust seller (deed conveyance, trustee on the Execution Page).

### 0b. Format — one concise template for every seller (v1.11)

**Gabriel ruling 2026-10-17:** every LOI uses `templates/LOI_Master_Template_v2.docx`, built from the approved 8625 Troost Ave LOI. The STANDARD/CONDENSED split is retired; the v1.x master template (`LOI_Master_Template_Condensed.docx`) moves to `versions/` for reference only. The LOI carries deal terms and the protections that cannot wait for the PSA; everything else goes into the PSA-deferral sentence in §9.

**Fixed structure (never renumbered):** 1 Price, Deposit, and Closing · 2 Study Period · 3 Environmental · 4 Property Condition · 5 Title and Prorations · 6 Leases and Conditions to Closing (tenanted) OR Continued Operations (vacant) · 7 Brokerage · 8 Acquisition Structure · 9 Process and Exclusivity · 10 Miscellaneous · Non-Binding paragraph (binds §7, the exclusivity covenant in §9, and the confidentiality and governing-law provisions of §10) · closing line and signature · Execution Page · Buyer Information page.

**Formatting standard (Gabriel, 2026-10-17 — overrides the ORA Style Guide palette for external LOIs):** Palatino Linotype throughout (body 11 pt, line spacing 1.15, left-aligned — never justified; Palatino chosen over Georgia for level, lining numerals in a figures-heavy document); section headings bold small caps 11.5 pt, black, 14 pt above and 5 pt below, no trailing period; bold black lead-ins ("Purchase Price:"); no gold, navy or sans-serif accents anywhere; hairline letterhead rule; date and address block in regular weight, only the RE line bold; one letterhead (top of page 1 only); every section kept on one page (keep-with-next and keep-together). Letterhead tagline: INDUSTRIAL & FLEX · PRINCIPAL OWNERSHIP · SINCE 2005.

**Survivors — never cut:** the Phase I→II auto-extension (§3, capped at {{PHASE2_CAP_WORDS}}), the Acquisition Structure designee-vesting/direct-deeding mechanics (§8), the defect-free assumption with its terminate-or-reprice remedy (§4), the condition-failure Deposit refund (§6), and the Deposit due-window in the §9 PSA-deferral sentence.

### 0c. Exchange posture — 1031 cooperation DEFAULT vs concealment overlay

**DEFAULT (template standard): RETAIN the mutual IRC §1031 cooperation clause in Miscellaneous.** It is reciprocal, costless, and ORA transacts via exchange routinely. Removing it is the exception, never the rule (Gabriel ruling 2026-06-10).

**CONCEALMENT OVERLAY — apply ONLY when BOTH are true:** (a) seller is sophisticated/institutional (REIT, bank REO, institutional or repeat-player seller with standing counsel), AND (b) ORA has live buyer-side exchange-timeline pressure (drop-and-swap, 45/180-day identification windows). Then:
- Set `{{EXCHANGE_COOPERATION_SENTENCE}}` to empty (removes the mutual cooperation sentence from §10).
- Delete any "Buyer intends to complete a §1031 exchange" motive language.
- Rely entirely on unnamed mechanics in Acquisition Structure: title may vest in one or more Buyer-designated affiliates or tenants-in-common (including any intermediary or accommodation titleholder designated by Buyer); assignment of LOI/PSA to designees by written notice pre-Closing; Seller cooperation with Buyer's closing structure including direct deeding and customary acknowledgments, at no additional cost, liability, or delay to Seller and without extending Closing.
- **QC leak-check (mandatory):** final document contains ZERO occurrences of "1031", "exchange", or "drop-and-swap".
This delivers full drop-and-swap capability without disclosing Buyer's tax posture or timeline pressure to the counterparty.

### 1. Tenancy classification

Determines opening paragraph phrasing and which conditional blocks fire.

| Signal in OM / inputs | Classification | `{{PROPERTY_TENANCY_PHRASE}}` | `{{TENANT_DISCLOSURE_PHRASE}}` |
|---|---|---|---|
| "Vacant," "100% available," "owner-occupied vacating," no current tenant | **vacant** | `vacant` | (empty string) |
| Single tenant in OM rent roll; not affiliated | **arm's-length single-tenant** | `single-tenant` | `, leased to {{TENANT_NAME}} (the "Tenant")` — the only place "Tenant" is defined |
| Single tenant; tenant name shares a root with Seller LLC, OR OM discloses common ownership | **affiliated single-tenant** | `single-tenant` | `, leased to {{TENANT_NAME}}, an affiliate of Seller (the "Tenant")` — no trailing comma; keep the AFFILIATED TENANT block |
| 2+ tenants | **multi-tenant** | `multi-tenant` | (custom — list largest tenants in opening if material) |

**Punctuation convention (2026-08-18 fix — was producing "...,." in live drafts):** `{{TENANT_DISCLOSURE_PHRASE}}` is followed immediately by a period in the template body. Never let the resolved value end in a trailing comma.

**Affiliation test (decisional):** Set affiliated = TRUE if ANY of:
- Tenant LLC name contains Seller LLC root (e.g., "Buckeye Elm Contracting, LLC" + "BUCKEYE ELM HOLDINGS CO LLC")
- OM discloses sale-leaseback structure
- Tenant manager / principal is same as Seller manager / principal
- Tenant pays below-market rent identified during underwriting
- User explicitly states affiliation

### 2. Conditional block firing (template v2)

Each `▶ CONDITIONAL ◀  NAME — criterion` … `◀ END CONDITIONAL` block is evaluated by name in `deal.json` → `conditionals`; `scripts/assemble_loi.py` keeps or deletes it (nesting supported) and refuses to run if any block is unspecified. Section numbers never change.

| Block | Keep when |
|---|---|
| `TENANTED` (§6 Leases and Conditions to Closing) | Any lease exists at Closing |
| `ESTOPPEL` (inside TENANTED) | Always when TENANTED. Due at least five (5) business days before the Study Period expires; `{{ESTOPPEL_SPECIFIC_CONFIRMATIONS}}` adds deal-specific certifications (e.g. tax recovery) |
| `PURCHASE OPTION` (inside TENANTED) | A lease grants a purchase option ORA requires removed (termination in Buyer's form, due five (5) business days before the Study Period expires) |
| `ROFR` (inside TENANTED) | A lease grants a ROFR, ROFO or pre-emptive right (Seller requests the waiver within five (5) business days after acceptance and diligently pursues it; Buyer need not sign the PSA until it arrives or the election period expires; set `{{EXCLUSIVITY_END_PHRASE}}` to run to the later of the base period or ten (10) business days after that event) |
| `AFFILIATED TENANT` (inside TENANTED) | Tenant and Seller are affiliated (Rule 1 test) |
| `VACANT` (§6 Continued Operations) | No lease at Closing — carries the mandatory preservation covenant and the 5% casualty threshold |
| `ENTITY-INTEREST ELECTION` (inline, §8) | Default DELETE; keep only per Rule 0 |

Exactly one of TENANTED / VACANT is kept.

### 3. State proration sentence and deed (template v2)

§5 is one paragraph: deed, title exceptions, lien release, "customary {{PROPERTY_COUNTY}} allocations", optional `{{TENANT_TAX_PRORATION_PHRASE}}`, then `{{STATE_PRORATION_SENTENCE}}` (leading space; empty when the state needs nothing beyond customary allocations). Defaults, from `references/state-overlays.md` (still the source for the underlying customs):

| State | `{{STATE_PRORATION_SENTENCE}}` | `{{DEED_TYPE}}` |
|---|---|---|
| OH | ` Real estate taxes prorate on the Ohio long-proration method, and Buyer retains Board of Revision rights for post-Closing periods.` (run the HB 126 dual test, Rule 5c, before asserting BOR risk) | `general warranty deed` |
| MD | ` Recordation and transfer taxes are shared equally unless {{PROPERTY_COUNTY}} custom differs.` | `special warranty deed` [verify] |
| IN | ` Real estate taxes, billed in arrears, prorate through Closing.` | `general warranty deed` [verify] |
| MO, KS | (empty) | `general warranty deed` |
| WI | ` Seller pays the Wisconsin real estate transfer fee.` | `warranty deed` [verify] |
| TN | ` Seller pays the Tennessee realty transfer tax.` | `general warranty deed` [verify] |

Any state not listed: `[FORECAST]` flag, empty sentence, and user verification before shipping. `{{PROPERTY_TIME_ZONE}}`: Eastern (OH, MD, most of IN, East TN) or Central (MO, KS, WI, West/Middle TN, NW/SW IN).

### 4. Jurisdiction phrase

Template v2 has no jurisdiction-verification clause (deferred to diligence); `{{PROPERTY_JURISDICTION_PHRASE}}` is retired.

### 5. Known-condition carveout (§4)

`{{KNOWN_CONDITION_CARVEOUT}}` sits immediately after "significant deferred maintenance" in §4, so its value starts with a space and opens a parenthesis, e.g. ` (except for the roof, which the parties acknowledge is approximately twenty-one (21) years old and approaching the end of its useful life)`. Carveout texts per `references/template-mechanics.md`; empty string when nothing is disclosed.

### 5b. PSA-deferral sentence (§9)

§9 ends: "The PSA will address the remaining terms, including customary representations and covenants, risk of loss and condemnation, the estoppel form, closing deliveries and Buyer's remedies, with the Deposit due within {{EMD_DUE_DAYS_WORDS}} business days after PSA execution." Items cut from the LOI in v1.11 that MUST land in the PSA draft (record them in the Deal Terms Register): specific performance for Seller default; the 5% casualty threshold (tenanted deals); service-contract and capital-spending covenants; full estoppel content; title commitment within ten (10) days; Buyer access and insurance; bill of sale; broom-clean delivery; Ohio deals — Seller cooperation with, and no independent stipulation in, tax valuation proceedings.

### 5c. Ohio BOR risk — statutory thresholds (HB 126)

Run the HB 126 dual test — recorded sale exceeds auditor value by BOTH 10% AND $500,000 [verify thresholds with counsel] — at offer price vs auditor value before asserting BOR risk; below either threshold the school-board original-complaint route is barred. **Read references/state-overlays.md (Ohio BOR dual-threshold rule) before drafting the Ohio §5 sentence or any BOR language.**

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

`references/token-reference.md` lists the v1.x tokens; template v2 changes (also in `references/token-reference-v2.md` once committed):

- **Retired:** `{{PROPERTY_JURISDICTION_PHRASE}}`, `{{EXCLUSIVITY_DAYS_WORDS}}` (replaced by the phrase below), `{{PSA_EXECUTE_DAYS_WORDS}}`.
- **New:**
  - `{{SELLER_ENTITY_NAME_CAPS}}` / `{{SELLER_ENTITY_FORM_PHRASE}}` — Execution Page ("JINC HOLDINGS, LLC" / "a Missouri limited liability company"); `{{SELLER_ENTITY_NAME}}` is the prose form.
  - `{{ANCILLARY_DISCLOSURE_PHRASE}}` — e.g. ", with a portion of the site ground-leased to New Cingular Wireless PCS, LLC (the “Tower Tenant”)"; empty if none.
  - `{{PHASE2_CAP_WORDS}}` — default `forty-five (45)`.
  - `{{DEED_TYPE}}`, `{{STATE_PRORATION_SENTENCE}}`, `{{PROPERTY_TIME_ZONE}}` — Rule 3.
  - `{{TENANT_TAX_PRORATION_PHRASE}}` — ", with real estate taxes prorated to account for amounts reimbursed by the Tenant" when tenanted; empty when vacant.
  - `{{ESTOPPEL_PARTIES}}` (e.g. "the Tenant"), `{{ESTOPPEL_SPECIFIC_CONFIRMATIONS}}` (leading comma, e.g. ", including without qualification that real estate taxes are Triple Net Expenses payable by the Tenant under Section 2.3.1.1 of its lease"; may be empty).
  - `{{OPTION_HOLDER}}`, `{{OPTION_LEASE_REF}}`, `{{ROFR_HOLDER}}`.
  - `{{EXCLUSIVITY_END_PHRASE}}` — "thirty (30) days after acceptance" (tenanted) / "sixty (60) days after acceptance" (vacant), or the ROFR "later of" form (Rule 2).
  - `{{EXCHANGE_COOPERATION_SENTENCE}}` — " The parties will cooperate with any IRC §1031 exchange at no cost, liability or delay to the cooperating party." (default); empty under the concealment overlay (Rule 0c).
- **Unchanged conventions:** periods phrased `[word] (digit)`; `{{EMD_DUE_DAYS_WORDS}}` is the single source of the deposit window (now stated only in §9; §1 cross-refers); `{{TENANT_DISCLOSURE_PHRASE}}` never ends in a comma and is the ONLY place "Tenant" is defined; `{{PROPERTY_ZONING_PHRASE}}` verbatim from the OM or a verified GIS pull.
- **Buyer is always "Oxford Realty Advisors, LLC"** in the letter and the Execution Page (the letterhead keeps "OXFORD REALTY ADVISORS").

## WORKFLOW — execute in this order

### Phase 1 — Ingest and parse
1. Read user prompt for any explicit values (Purchase Price, deposit, dates, etc.).
2. If a PDF/DOCX is attached, extract OM data: address, SF, acreage, asking price, tenant status, broker contact, photos, building age, rent roll if present.
3. If property is already in Notion Acquisition Pipeline Tracker (`bcfe4a03`), pull existing fields.
4. If broker email/contact missing, search HubSpot CRM for broker by name or firm.

### Phase 2 — Apply decision logic
1. Classify tenancy (vacant / arm's-length / affiliated / multi-tenant).
2. Determine which conditionals fire.
3. Select the §5 state proration sentence and deed type (Rule 3).
4. Set the ROFR-linked exclusivity phrase and estoppel confirmations (Rule 2).
5. Resolve known-condition carveout for §4 (or leave empty).
6. Apply economic term defaults from ORA Standards for any unspecified term.

### Phase 3 — Token resolution
1. Build full token map.
2. Verify no required token is unresolved. If any is missing, list them and ask Gabriel for clarification before producing the file.
3. Convert numeric amounts to word form for `_WORDS` tokens. Format numerics with commas and trailing `.00`.

### Phase 4 — Document assembly

1. Write `deal.json` (`tokens` for every template token, `conditionals` for every block, `concealment_overlay`).
2. Run `python scripts/assemble_loi.py deal.json --template templates/LOI_Master_Template_v2.docx --out "LOI [Street] [City] [ST] [M.D.YYYY].docx" --pdf`. It deletes/keeps conditionals, replaces tokens in body, tables and footer, sets file metadata (author = signatory, today's date, title), renders the PDF with `soffice`, forces a page break before any heading LibreOffice leaves orphaned, and runs the mechanical QC checks (exit 1 on failure).
3. If `templates/LOI_Master_Template_v2.docx` or `scripts/assemble_loi.py` is not in this skill folder yet, use the staged copies at `ROOT\Claude outputs\tools\loi-template-v2\`; if neither is reachable, STOP and say so — never fall back to the v1.x template.
4. The PDF from `soffice` may embed a metric-compatible substitute for Palatino Linotype; before shipping, export the final PDF from Word on Gabriel's machine.

### Phase 5 — QC Gate (refuse to save if any item fails)

`assemble_loi.py` automates items marked (A); the rest are manual.

| # | Check |
|---|---|
| 1 | (A) All `{{TOKENS}}` resolved |
| 2 | (A) All conditional blocks evaluated; markers removed; exactly one of TENANTED / VACANT kept |
| 3 | §5 state sentence and deed type match the property state (Rule 3) |
| 4 | Non-binding paragraph cites §7, §9 (exclusivity covenant) and §10 — fixed numbering, never renumbered |
| 5 | Document starts with letterhead + date and ends with the Buyer Information page |
| 6 | Opening-paragraph tenancy phrase matches the deal; "Tenant" defined once ((A) checks duplicates) |
| 7 | Economic terms within ORA ranges (`references/ora-standards.md`) or deviations stated in chat |
| 8 | Buyer signatory matches instruction (default Gabriel Goldberg / Authorized Representative); Buyer named "Oxford Realty Advisors, LLC" |
| 9 | (A) Letterhead phone 301.512.6125 present (one letterhead, top of page 1) |
| 10 | Footer reads `[PROPERTY_STREET_ADDRESS] LOI · Page X of Y` |
| 11 | (A) "Proof of funds available upon request." on the final page |
| 12 | (A) Buyer Information reads "approximately 140 tenants"; portfolio figures re-verified against the live Master Workbook before shipping |
| 13 | Offer expiration is a business day at least 5 business days after the LOI date, stated as 5:00 p.m. {{PROPERTY_TIME_ZONE}} Time |
| 14 | Execution Page complete (Buyer block, Seller entity name and form phrase) |
| 15 | (A) Strike list clean (no "shall", no banned phrases) |
| 16 | PDF via `soffice` (never Microsoft Print to PDF) with extractable text; final send copy exported from Word |
| 17 | (A) 4–6 pages; Buyer Information starts its own page; no numbered heading orphaned at a page bottom; no section split across pages |
| 18 | Entity-interest language matches seller suffix (Rule 0) |
| 19 | Zoning phrase verbatim from the OM or verified GIS |
| 20 | (A when flagged) Concealment overlay: zero "1031" / "exchange" / "drop-and-swap" |
| 21 | Deposit due-window appears once (§9) and matches `{{EMD_DUE_DAYS_WORDS}}` |
| 22 | Vacant deals: preservation covenant and 5% casualty threshold present (VACANT block) |
| 23 | **Offer ≤ Walk Price (v1.8).** Compare `ORA Offer Price` against `Walk Price`. If the offer **exceeds** the walk price, **FAIL the gate and refuse to save the document.** Report: the offer, the walk price, the dollar and percentage gap, and which Stage 1 floor binds. The only permitted override is an **Exception Register** entry (per acquisition-underwriting's EXCEPTION REGISTER + TRIPWIRE) carrying a one-sentence compensating factor and Gabriel's explicit in-turn ratification — logged to the ranking workbook's Exception Register tab **and** the Notion row's "Exception Compensating Factor" field **before** the document is saved, not after. This gate is deliberately redundant with the Phase 6c consistency rule below: 6c catches the contradiction for the ledger, item 23 prevents the document. Two live incidents where 6c alone was insufficient — 511 Industrial Mile Road (Walk $930K / LOI $1.45M, loss permanently `UNCLASSIFIED` as a result) and 3700 Kinsman Blvd (Walk $2,661,000 / drafted LOI $3,800,000, caught only because a FULL underwrite was separately requested four days after the LOI was drafted). |
| 24 | (A) Formatting standard: Palatino Linotype only; no brand colors (C9A96E / 1B2A4A) in the document |
| 25 | File metadata shows the signatory as author and today's date (no stale template dates) |

### Phase 6 — Save and present
1. Filename: `LOI [Property Street] [City] [State] [M.D.YYYY].docx` — match Gabriel's convention (e.g., `LOI 1333 Research Rd Gahanna OH 5.14.2026.docx`).
2. Save to outputs folder.
3. Generate PDF preview via `soffice --headless --convert-to pdf`.
4. Present both files to user via `present_files`.
5. Log to Notion Acquisition Pipeline Tracker (`bcfe4a03`): `LOI Status` = "Submitted"; the dedicated **`LOI Expiration Date`** date field = `{{OFFER_EXPIRATION_DATE}}` (**never only into `Next Action` prose** — `ora-deal-aging-sla` STEP 3c reads the column); link to file; one-line terms summary in `Next Action`; **`Last Activity` = today (date-only)** (what `ora-deal-command-board` reads for staleness); **`Next Action Date`** = the date ORA must next act on (normally the seller-response deadline; NULL if none — never default it to the expiration). **Keep the two dates distinct even when they coincide.** **Read references/notion-logging.md before writing the Notion row** for the full rule text and its 470 McCormick origin.

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

1. Locate the deal's row in the Notion **Deal Sourcing Log** (`collection://9a6ae219-85a3-4621-899c-c757fd062f8b`), matching on normalized street address. **If no row exists, create one** — a deal that reached LOI without a sourcing row is a gap, not a reason to skip capture. **If more than one row matches, do not guess:** write to the row with the most complete underwriting and flag the duplicate to Gabriel (this is live — `511 Industrial Mile Road` currently has two rows).

2. Set these properties (Block A):

   | Property | Value |
   |---|---|
   | `LOI Sent Date` | the date the LOI is actually delivered (leave NULL at draft if unshipped) |
   | `ORA Offer Price` | the purchase price in the LOI |
   | `ORA Offer $/SF` | offer ÷ Total SF |
   | `ORA Basis @ Offer (% RCT LOW)` | all-in basis ÷ RCT v03 LOW for the market |
   | **`ORA Max Defensible Price`** | **see §3 — the load-bearing number** |
   | `Offer: DD Days` / `Offer: Close Days` / `Offer: Deposit $` | from the LOI terms |
   | `Offer: All-Cash` / `Offer: Financing Contingency` | from the LOI terms |
   | `LOI Outcome` | `PENDING` |

3. **`ORA Max Defensible Price` — compute it NOW, at LOI time.** It is the price at which this deal *first breaches a Stage 1 floor* (the vintage-ramp basis floor or the 8% YoC floor, whichever binds first). Fixed at this moment and **never recomputed at outcome time** — recomputing once the winning price is known is hindsight bias, and the downstream classifier refuses a value written after the fact; without it a lost deal is permanently `UNCLASSIFIED`. It is a *different number from `Walk Price`*, and both must be consistent with `ORA Offer Price`. **An offer above the walk price is a contradiction — stop and resolve it, do not write both.**

4. `LOI Sent Date` is written at Phase 7 SHIP, not here. A drafted LOI that never ships is logged `LOI Outcome = EXPIRED-UNSENT` with `ORA Offer Price` left **BLANK** — an unsent LOI has no offer price. Full text and live examples (511 Industrial Mile Road, 470 McCormick Blvd): references/notion-logging.md.

5. This phase writes ORA's own numbers only. It never records a competitor's price, never estimates one, and never recommends an offer level.

### Phase 7 — Optional SHIP mode
If user requested ship:
1. Draft the email for Gabriel's review. (Composio `OUTLOOK_*` retired 2026-06-11 — connector removed, no fallback. The approved send, if Gabriel green-lights, runs via Outlook COM `C:\Users\Owner\.claude\scheduled-tasks\_shared\send-via-outlook.ps1`, the SOLE send path.)
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

Template v2 uses one `{{STATE_PRORATION_SENTENCE}}` per state (Rule 3 table). `references/state-overlays.md` remains the source for county customs, the full overlay text used in PSA drafting, and the Ohio HB 126 BOR rule — read it before asserting BOR risk or for any non-listed state.

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

**Read references/connectors-and-special-cases.md before Phase 2 when the deal is multi-tenant, vacant, in a state outside the seven-state overlay list, a sale-leaseback, or the seller refuses long proration.** Hard rules that survive regardless: unfamiliar-state deals carry a `[FORECAST]` flag and an empty `{{STATE_PRORATION_SENTENCE}}` and never ship without user verification; sale-leaseback = affiliated single-tenant (TENANTED + ESTOPPEL + AFFILIATED TENANT, plus PURCHASE OPTION / ROFR if the lease grants them); vacant keeps only the VACANT block in §6.

---

## VERSIONING

- v1.11 — 2026-10-17, concise template v2 adopted (Gabriel, in-turn, after review of the 8625 Troost Ave LOI). One template for every seller (STANDARD/CONDENSED retired; v1.x master moved to `versions/`); ten fixed sections, never renumbered; formatting standard (Palatino Linotype, black only, left-aligned, small-caps headings, one letterhead, sections kept whole) overrides the Style Guide palette for external LOIs; new standard clauses: estoppel and option deliverables due five (5) business days before Study Period expiry with day-for-day extension, Deposit refund on any failed condition, Phase II extension capped, ROFR request-and-pursue mechanics with exclusivity tied to the waiver, exclusivity limited to sale negotiations, consideration recited as Buyer's diligence spend, §4 terminate-or-reprice remedy, "acceptance" and "Closing" defined, expiration at 5:00 p.m. local time, Buyer named "Oxford Realty Advisors, LLC". New `scripts/assemble_loi.py` (conditionals, tokens, metadata, orphan fix, automated QC). QC Gate rewritten for v2 (items 9, 17 changed; 24–25 added). No walk-price rule, Phase 6b/6c ledger rule or governor constant changed.
- v1.10 — 2026-09-23, outbound buyer-profile facts corrected (Gabriel, in-turn). **No numeric leverage in counterparty text:** the Buyer Information page's former numeric debt-and-LTV sentence becomes "The portfolio is conservatively leveraged, with the substantial majority of its value held as principal equity", and `references/ora-standards.md`'s cover-note numeric-LTV bullet becomes "Conservative leverage" with an explicit never-state-a-number rule. The verified 18.71% (Master Workbook `00_Home!G7`, 2026-09-23) stays internal. **Scale facts:** corrected to "twenty-six properties / 500,000+ SF / ~$57 million" (count, SF and markets per Gabriel's 2026-08-18 outbound canon shared with `acquisition-proposal-generation`; value from the live workbook $56.67M). Cover-note markets are narrowed to the three core markets. Template text-only edit (2 runs; XSD validation PASS, paragraph count 430→430). **No conditional block, state overlay, QC Gate item, token or governor constant changed.**
- v1.9 — 2026-09-10, retention rule adopted (ORA Automation Audit R24-11). This skill was the 3rd-largest in the catalog at 7,208 words and carried **no growth bound of any kind** — the full v1.0–v1.8 history sat inline and had never been extracted. Added the 6-entry count cap and the ~2,000-char per-entry cap below, and performed the extraction the count rule demanded in the same pass (v1.3/v1.2/v1.1/v1.0 → `versions/CHANGELOG-v1.0-v1.3.md`). **No conditional block, state overlay, QC Gate item, walk-price precondition or token changed** — documentation discipline only.

**Retention rule (added 2026-09-10, ORA Automation Audit R24-11):** keep at most the **6 most recent versions** as full inline entries. The edit that would add a 7th must, in the same pass, compress the oldest full entry to a one-line `**vX.Y (date):** Full text: versions/CHANGELOG-vA.B-vX.Y.md` summary and append its full original text to the versions file for that range. **Per-entry cap ~2,000 characters** — an entry that would exceed it states its finding and verdict inline and cites the deal folder or `versions/` file for the detail. Check both caps in the pass that adds an entry — never as deferred cleanup. Full rule text and calibration: `versions/CHANGELOG-v1.4-v1.8.md`.

- **v1.8 (2026-08-22) — full text: `versions/CHANGELOG-v1.4-v1.8.md`.** Walk-price precondition moved upstream: `Walk Price` added to required inputs (refuse to draft without it — run `acquisition-underwriting` first) and hard-fail QC Gate item 23 (Offer ≤ Walk Price; override only via a ratified Exception Register entry). Phase 6c left deliberately redundant. Origin: 511 Industrial Mile Road, 3700 Kinsman Blvd. No scorecard weight, Stage 1 floor, or governor constant changed. Archived 2026-09-22 under the retention rule.
- **v1.7 (2026-08-21) — full text: `versions/CHANGELOG-v1.4-v1.8.md`.** Repo-first reconciliation of two independently-built v1.6 revisions; template v1.1 adopted; Phase 6c retained. Archived 2026-09-22.
- **v1.6 (2026-08-18) — full text: `versions/CHANGELOG-v1.4-v1.8.md`.** Template/skill sync pass (3700 Kinsman Blvd): `{{PROPERTY_ZONING_PHRASE}}` and inline §13 `{{ENTITY_INTEREST_TYPE}}` wired into template v1.1; Execution Page subtitle and tenant-disclosure punctuation defects fixed. Archived 2026-09-22 under the retention rule.
- **v1.6 (2026-08-16) — full text: `versions/CHANGELOG-v1.4-v1.8.md`.** Lost-Deal Ledger capture (Phase 6c) incl. `ORA Max Defensible Price`; Deliverables item 10. Archived 2026-09-22.
- **v1.4 (2026-06-11) — full text: `versions/CHANGELOG-v1.4-v1.8.md`.** Deal Terms Register (Phase 6b), consumed by deal-execution Workflow 2A and psa-reconciliation. Archived 2026-09-22.
- **v1.3 (2026-06-11) — full text: `versions/CHANGELOG-v1.0-v1.3.md`.** Composio-retirement merge; SHIP mode re-pointed to the Outlook COM sole send path. Archived 2026-09-10 to hold the 6-entry cap.
- **v1.2 / v1.1 / v1.0 — full text: `versions/CHANGELOG-v1.0-v1.3.md`** (v1.2 2026-06-10 adversarial hardening; v1.1 2026-06-10 470 McCormick calibration incl. Rule 0/0b/0c; v1.0 initial release May 2026). Archived 2026-09-10 under the retention rule above.


---

## FAILURE MODES — when NOT to use this skill

- **Owner-occupied property where ORA is selling, not buying** — wrong direction; use `deal-execution` skill for sale side
- **Refinance proposal** — use `debt-management` skill
- **Off-market lease proposal** (ORA leasing to a third party) — `re-operations` retired 2026-08-05 (redundant with named ops siblings, no direct-execution evidence); for the lease document itself, use `lease-form-qc`
- **PSA stage** — handoff to `deal-execution` skill once LOI is executed; this skill stops at LOI delivery (sole exception: Phase 6b register update to EXECUTED status when the countersigned LOI returns)

---

## OUTPUT GUARANTEES

Every successful run of this skill produces:
1. A DOCX file on ORA letterhead built from template v2, 4–6 pages
2. A PDF preview with extractable text
3. A presented file pair via `present_files`
4. A Notion log entry on the Acquisition Pipeline Tracker
5. Zero "shall" usage, zero banned phrases, full 25-point QC Gate pass
6. Phone 301.512.6125 in the (single) letterhead
7. Footer keyed to property street address
8. "Proof of funds available upon request." centered italic at bottom of final page
9. `DEAL-TERMS-REGISTER.md` created (or updated) in the deal folder per Phase 6b
10. Deal Sourcing Log row carries the Phase 6c Block A capture — in particular a non-NULL **`ORA Max Defensible Price`** and `LOI Outcome = PENDING`. A blank Max Defensible price means this deal can never be classified if it is lost; treat it as an incomplete deliverable, not a nice-to-have.