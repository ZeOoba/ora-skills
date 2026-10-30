# SHORT Form — the ORA house LOI (default since v1.12; the only format since v1.15)

**Origin (Gabriel, 2026-10-20, in-turn):** adopt the Lucern Capital Partners buy-side LOI form (Columbus Multi-Tenant Portfolio LOI dated 10/20/2026) as ORA's default, because "seller signing with speed and simplicity of document are the most important elements." Use all of Lucern's formatting; substitute ORA's letterhead logo, buyer information and signatory; carry the improvements agreed in the same session. This supersedes the never-merged 2026-10-17 "single concise template (v2)" ruling captured in PR #146 (Gabriel, 2026-10-20: the Lucern short form governs).

**v1.15 (Gabriel, 2026-10-27, in-turn): "All LOIs generated should match the formatting in the attached document"** — a SHORT-form LOI ORA sent on 10/20/2026 that added Purchase Option and Tenant Conditions terms. SHORT is now the only format; the CONDENSED fallbacks below are replaced by conditional terms.

Template: `templates/LOI_ShortForm_Template.docx`. Fill: `python templates/fill_shortform.py values.json out.docx`. QC: `python templates/qc_shortform.py out.pdf values.json`. Rebuild the template with `templates/build_shortform.py <oxford-logo-512.png> <out.docx>` (logo source `website-canonical/images/oxford-logo-512.png`) or `--cropped <logo_full.png> <logo_mark.png> <out.docx>` using `word/media/image1.png` and `image2.png` unzipped from the current template (pixel-identical).

---

## Conditional terms (v1.15 — replace the former CONDENSED fallbacks)

| Situation | SHORT mechanism | Verbatim pattern (adapt names and periods) |
|---|---|---|
| Tenant purchase option | **Purchase Option** `{{PURCHASE_OPTION_TERM}}` | This offer is contingent on the permanent removal of the Tenant’s option to purchase the Property under [lease reference]. At least five (5) business days before expiration of the Due Diligence Period (which extends day-for-day until delivery), Seller will deliver a written termination and release of that option, executed by the Tenant in recordable form reasonably acceptable to Buyer, that permanently extinguishes the option and any related right of the Tenant to acquire the Property, effective at or before Closing. If it is not delivered by that date, Buyer may terminate and receive a full refund of the earnest money. Its delivery is a condition precedent to Buyer’s obligation to close. |
| ROFR / ROFO / pre-emptive right | **Tenant Conditions** `{{TENANT_CONDITIONS_TERM}}` | Within five (5) business days after acceptance, Seller will request, and on receipt deliver, [holder]’s written waiver of its right of first refusal as to a sale to Buyer or its designee (or written confirmation that its election period expired unexercised); Buyer need not execute the PSA or spend diligence funds until it is delivered, and the Exclusivity period extends until ten (10) business days after delivery. If [holder] exercises that right, this LOI terminates. |
| Named estoppel confirmations | **Tenant Conditions** (append) | At least five (5) business days before expiration of the Due Diligence Period (which extends day-for-day until delivery), Seller will deliver the Tenant’s estoppel confirming [rent through date, NNN pass-throughs, option status, no side agreements]. Each is a condition precedent to Buyer’s obligation to close. |
| Affiliated tenant / sale-leaseback | **Tenant Conditions** (append) | Within five (5) business days after acceptance, Seller will deliver the Tenant’s executed lease with all amendments and side letters, its federal income tax returns for the trailing three years, and a current interim profit-and-loss statement and balance sheet. |
| Zoning DD-Critical / nonconforming use / PD-PUD | **Zoning** `{{ZONING_TERM}}` | Buyer’s obligation to close is conditioned on Buyer’s receipt, before Closing, of written confirmation from [authority] (or another zoning determination reasonably acceptable to Buyer) that [uses] may lawfully continue or be re-established at the Property, together with Buyer’s intended [improvements]. If that confirmation is not received, Buyer may terminate and receive a full refund of the earnest money. |
| Entity-interest election / drop-and-swap structure | `{{ENTITY_INTEREST_SENTENCE}}` (Other Conditions; leading space) | ` Title may also vest in tenants-in-common or an accommodation titleholder designated by Buyer, and before PSA execution Buyer may instead elect to acquire all {{ENTITY_INTEREST_TYPE}} in a single-purpose entity holding only the Property.` (either clause alone when only one is wanted) |
| Extra Seller deliveries | `{{DD_DELIVERY_ADDITIONS}}` (Due Diligence; leading comma, trailing comma) | `, written confirmation of the date the Property was last occupied for [use],` |
| Tenant contact needed for the above | `{{CONFIDENTIALITY_TENANT_CARVEOUT}}` (leading comma) | `, to the Tenant as needed to obtain the waiver, termination, and estoppels described above` |
| Phase II / VAP path | Base Due Diligence text | Auto-extension now also runs on a Buyer-elected Phase II and to any voluntary action program determination — no fallback needed |

Empty values delete optional terms and leave inline tokens blank. Gabriel may still ask for the retired long form (`templates/archive/LOI_Master_Template_Condensed_v1.1.docx`); say it is retired and confirm in-turn before using it.

---

## Layout (Lucern form — do not restyle)

- Letter, 1.0" side margins, 1.2" top (header 0.28" from edge), 1.0" bottom. Times New Roman 11 pt body, single spaced.
- Page 1 header: full ORA logo top-left (0.8" high). Pages 2+: same logo at 0.45".
- Body: date, addressee block, `RE:` line with hanging indent, salutation, credentials paragraph, intent paragraph, then labelled terms.
- Terms: underlined label + colon at the margin, text on a 1.6" hanging indent, justified, 8 pt after.
- Signature: "Regards," → Gabriel Goldberg / Authorized Representative / Oxford Realty Advisors (e-signature space only — Gabriel, 2026-10-20). Acceptance block indented 0.6": "Accepted, subject to the execution of a Purchase Agreement." with By / Seller and Title & Name / Date lines.
- "Proof of funds available upon request." centered italic grey 9 pt directly below the acceptance block.
- Footer on every page: grey bold 9 pt `9510 Persimmon Tree Road, Suite 200 │ Potomac, MD 20854 │ 301.512.6125 │` + hyperlinked `www.oxfordra.net`, ORA block mark right-aligned. No page numbers (Lucern form).
- No Template Metadata page, no State Overlay Appendix, no Execution Page, no Buyer Information page — the credentials sentence on page 1 replaces the Buyer Information page.
- Credentials paragraph (Gabriel, 2026-10-20): verifiable firm facts from `references/ora-standards.md` Portfolio context only — family-owned / family capital, founded 2005, property count, square footage, product mix, markets, tenant count, no outside investors, all-cash. Never state portfolio value or a closing-record claim ("closed substantially all…") in a SHORT LOI or its cover note.
- Target length: **two pages filled; three when a conditional term fires** (v1.15 tests: vacant OH + Zoning + entity sentence = 3; tenanted MO + Purchase Option + Tenant Conditions = 3; the 10/20/2026 reference LOI = 3). Tested 2026-10-20 (soffice, Liberation Serif metrics = Times New Roman), all at 2 pages: Ohio multi-tenant with estoppel sentence; vacant with preservation covenant; arm's-length single-tenant with tenant disclosure; multi-tenant with dominant-tenant disclosure; multi-tenant plus a roof known-condition carveout. Headroom is about one line beyond those cases: stacking two extra lines of deal text (e.g. a non-Ohio transfer-tax sentence plus a single-tenant disclosure plus a long LP seller name) renders 3 pages — report under #17. Terms may break across pages (widow/orphan control on). Do not restore PSA-deferred clauses (Gabriel, 2026-10-20: none restored).

## Term order (fixed)

Purchase Price · Deposit Terms · Due Diligence · [Zoning] · Closing · Property Condition · Costs · Operations · [Purchase Option] · [Tenant Conditions] · Exclusivity · Other Conditions · Confidentiality · Offer & Acceptance (carries the binding-provisions sentence). Bracketed terms appear only when they fire.

**Survivors — never cut from SHORT:** Phase I→II auto-extension (Due Diligence — triggers on a REC or a recommendation for further investigation; refundability extends with it); defect-free assumption (Property Condition); designee vesting / direct deeding (Other Conditions); deposit due-window from `{{EMD_DUE_DAYS_WORDS}}`; "Buyer’s obligation to close is not contingent on financing or appraisal."; the all-cash statement in the RE line ("All-Cash Letter of Intent"), intent paragraph ("all-cash, non-binding") and Purchase Price ("all cash, paid … in immediately available funds")

**No buyer closing-extension option (Gabriel, 2026-10-20):** Closing is fixed at `{{CLOSING_DAYS_WORDS}}` days after the Due Diligence Period; do not add Lucern's extension-for-added-deposit right back. Costs does not mention Buyer financing.

**Deliberately omitted (PSA-deferred, Gabriel 2026-10-20):** casualty / risk of loss, title-objection cure mechanics, closing-deliverables list, governing law and venue, capex cap, Bill of Sale detail (personal property still conveys under Property Condition). Affiliated-tenant disclosures and ROFR waivers are no longer omitted — they ride in **Tenant Conditions** when triggered (v1.15).

---

## Tokens added or changed for SHORT

All other tokens follow `references/token-reference.md`. `_WORDS` tokens keep the `[word] (digit)` convention.

| Token | Rule | Example |
|---|---|---|
| `{{DEED_FORM}}` | From the state table below | `general warranty deed` |
| `{{TRANSFER_TAX_SENTENCE}}` | From the state table below; one full sentence ending in a period | `Seller will pay all conveyance, transfer, or similar taxes payable upon the transfer of the Property.` |
| `{{OPERATIONS_CONDITIONAL_SENTENCE}}` | Tenanted: the estoppel sentence. Vacant: the preservation covenant. Empty string only if neither applies (never both empty for a vacant deal) | see below |
| `{{PSA_DRAFT_DAYS_WORDS}}` | Includes the unit word | `ten (10) business` |
| `{{CLOSING_DAYS_WORDS}}` | Starts the sentence — capitalize the first word | `Fifteen (15)` |
| `{{PROPERTY_COUNTY}}` | Includes "County" | `Franklin County` |
| `{{ZONING_TERM}}` / `{{PURCHASE_OPTION_TERM}}` / `{{TENANT_CONDITIONS_TERM}}` | Whole term body, or `""` to delete the term (v1.15) | see Conditional terms |
| `{{ENTITY_INTEREST_SENTENCE}}` | Leading space, or `""` | see Conditional terms |
| `{{DD_DELIVERY_ADDITIONS}}` | Leading and trailing comma, or `""` | see Conditional terms |
| `{{CONFIDENTIALITY_TENANT_CARVEOUT}}` | Leading comma, or `""` | see Conditional terms |

SHORT uses numeric-only price and deposit (`{{PURCHASE_PRICE_NUMERIC}}`, `{{EMD_NUMERIC}}`); the `_WORDS` price/EMD tokens are not used.

**Operations sentences (verbatim):**
- Tenanted (any lease at Closing): `Seller will deliver tenant estoppel certificates in form reasonably acceptable to Buyer not less than ten (10) business days before Closing.`
- Vacant: `Seller will also maintain active utility service, heat adequate to prevent freeze damage, and security and life-safety systems in operable condition.`

**Concealment overlay (Rule 0c) on SHORT:** set `"CONCEALMENT_OVERLAY": true` in values.json. `fill_shortform.py` deletes the §1031 sentence from Other Conditions, removes "exchange intermediaries" from Confidentiality, rewords Purchase Price's "in exchange for free and clear title" to "against delivery of free and clear title", and refuses to save if "1031", "exchange" or "drop-and-swap" remains. The designee-vesting sentence stays.

### State table — `{{DEED_FORM}}` and `{{TRANSFER_TAX_SENTENCE}}`

Transfer-tax allocations mirror `references/state-overlays.md`. Deed forms other than Ohio are ORA's buyer-side asks against typical local practice and are marked **[verify with counsel]** until Philip Collins confirms; surface the flag in the chat summary on any non-Ohio deal.

| State | `{{DEED_FORM}}` | `{{TRANSFER_TAX_SENTENCE}}` |
|---|---|---|
| OH | general warranty deed (standing position) | Seller will pay all conveyance, transfer, or similar taxes payable upon the transfer of the Property. |
| MD | special warranty deed [verify with counsel] | State recordation and county transfer taxes will be divided equally between the parties, unless {{PROPERTY_COUNTY}} custom allocates them differently. |
| IN | general warranty deed [verify with counsel] | Indiana imposes no state transfer tax; Seller and Buyer will jointly execute the Indiana Sales Disclosure Form at Closing. |
| MO | special warranty deed [verify with counsel] | Missouri imposes no state real estate transfer tax. |
| KS | general warranty deed [verify with counsel] | Kansas imposes no real estate transfer tax. |
| WI | warranty deed [verify with counsel] | Seller will pay the Wisconsin real estate transfer fee. |
| TN | general warranty deed [verify with counsel] | Seller will pay the Tennessee realty transfer tax. [verify — this row follows state-overlays.md, but Tennessee places this tax on the purchaser; confirm with counsel and correct both files before any TN LOI ships] |
| Other | flag `[FORECAST]`; do not ship without Gabriel's verification (existing special-case rule) | — |

Real-estate-tax proration rides on "the method customary in `{{PROPERTY_COUNTY}}`, `{{PROPERTY_STATE_FULL}}`" — in Ohio this delivers long proration by custom. If a seller contests the proration method, fall back to the CONDENSED §6 overlay language for that state.

---

## SHORT QC Gate — replaces items 3, 4, 5, 8, 9, 10, 12, 14, 17 and 22 of the full gate in references/qc-gate.md

Every other item of `references/qc-gate.md` applies unchanged, including the hard-fail **#23 Offer ≤ Walk Price**.

| # | SHORT replacement |
|---|---|
| 3 | `{{DEED_FORM}}` and `{{TRANSFER_TAX_SENTENCE}}` match the property state's row above |
| 4 | Term labels appear in the fixed order above; the binding sentence names Exclusivity and Confidentiality |
| 5 | No metadata page, appendix, Execution Page, or Buyer Information page present |
| 8 | Signatory check reads the signature block (no Execution Page in SHORT): Gabriel Goldberg / Authorized Representative / Oxford Realty Advisors (or override) |
| 9 | `301.512.6125` appears in the footer on every page (grep count = page count); `301.983.8000` returns zero |
| 10 | Footer reads the Persimmon Tree address │ Potomac │ phone │ `www.oxfordra.net` with the block mark; no page numbers required |
| 12 | Credentials sentence reads "privately held, family-owned … founded in 2005 … twenty-six properties, primarily shallow-bay industrial and flex, totaling more than 500,000 square feet … approximately 140 tenants … only its own capital, with no outside investors … all-cash". It states NO portfolio value, NO closing/track-record claim, and no numeric LTV, debt, or leverage figure (Gabriel, 2026-10-20; v1.10 rule) |
| 14 | Acceptance block present; Seller line carries `{{SELLER_ENTITY_NAME}}`; Buyer signatory Gabriel Goldberg, Authorized Representative (or override) |
| 17 | Page count = 2, or ≤ 3 when a conditional term fires (`qc_shortform.py` sets the limit from values.json). Without conditional terms, if the filled letter runs to 3 pages, tighten deal-specific phrases (tenant disclosure, zoning) — never delete a survivor clause; if still 3, report it rather than shrinking fonts or margins |
| 22 | Vacant deals: the preservation covenant is the Operations conditional sentence (no casualty-threshold check in SHORT) |

Item 11 (proof-of-funds line) checks for the line directly below the acceptance block on the final page.

**#15 exception:** the acceptance line "Accepted, subject to the execution of a Purchase Agreement." is fixed template text and is exempt from the "Subject to" strike-list entry; any other occurrence still fails.

**Helper script (v1.15):** `templates/qc_shortform.py <pdf> <values.json>` automates #1, #4 (including the conditional terms), #5, #9–#12, #14–#17 and #21; exit 0 required. The CONDENSED `qc_gate.py` in `references/qc-gate.md` no longer applies.

**Page-break behaviour:** Offer & Acceptance, the signature block, the acceptance block and the proof-of-funds line are chained keep-with-next, so on overflow the last term moves to page 3 with the signatures (the Seller never signs a page carrying no terms). Any filled letter that still reaches 3 pages is reported under #17.

**Token notes (override token-reference.md for SHORT):** `{{TENANT_DISCLOSURE_PHRASE}}` is followed by " — on the general terms below." rather than a period, and still must not end in a comma; for multi-tenant deals leave it empty unless a dominant tenant is material (e.g. `, the largest tenant being Acme Supply, LLC`). `{{CLOSING_DAYS_WORDS}}` opens a sentence — capitalize it (`Fifteen (15)`), unlike the CONDENSED example.
