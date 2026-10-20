# SHORT Form — Two-Page LOI (default format since v1.12)

**Origin (Gabriel, 2026-10-20, in-turn):** adopt the Lucern Capital Partners buy-side LOI form (Columbus Multi-Tenant Portfolio LOI dated 10/20/2026) as ORA's default, because "seller signing with speed and simplicity of document are the most important elements." Use all of Lucern's formatting; substitute ORA's letterhead logo, buyer information and signatory; carry the improvements agreed in the same session. This supersedes the never-merged 2026-10-17 "single concise template (v2)" ruling captured in PR #146 (Gabriel, 2026-10-20: the Lucern short form governs).

Template: `templates/LOI_ShortForm_Template.docx` (rebuild with `templates/build_shortform.py`; logo source `website-canonical/images/oxford-logo-512.png`).

---

## When SHORT applies — and when to fall back to CONDENSED

SHORT is the default for every LOI. Use the CONDENSED master (`LOI_Master_Template_Condensed.docx`, existing rules unchanged) instead when ANY of the following is true:

| Trigger | Why SHORT is insufficient |
|---|---|
| Affiliated single-tenant / sale-leaseback | Needs the §8 affiliated-tenant financial disclosures |
| Existing lease carries a ROFR / ROFO / pre-emptive right | Needs the §10 waiver-before-diligence-spend clause |
| Entity-interest purchase election wanted (Rule 0, inline §13) | SHORT has no entity-purchase option |
| Known or likely Phase II / VAP environmental path | Needs CONDENSED §3's full tail and refund mechanics |
| Gabriel asks for the full form | — |

The STANDARD format is unchanged and still available on request. Record the format chosen, and the trigger if CONDENSED, in the chat summary.

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
- Target length: **two pages filled.** Tested 2026-10-20 (soffice, Liberation Serif metrics = Times New Roman), all at 2 pages: Ohio multi-tenant with estoppel sentence; vacant with preservation covenant; arm's-length single-tenant with tenant disclosure; multi-tenant with dominant-tenant disclosure; multi-tenant plus a roof known-condition carveout. Headroom is about one line beyond those cases: stacking two extra lines of deal text (e.g. a non-Ohio transfer-tax sentence plus a single-tenant disclosure plus a long LP seller name) renders 3 pages — report under #17. Terms may break across pages (widow/orphan control on). Do not restore PSA-deferred clauses (Gabriel, 2026-10-20: none restored).

## Term order (fixed)

Purchase Price · Deposit Terms · Due Diligence · Closing · Property Condition · Costs · Operations · Exclusivity · Other Conditions · Confidentiality · Offer & Acceptance (carries the binding-provisions sentence).

**Survivors — never cut from SHORT:** Phase I→II auto-extension (Due Diligence — triggers on a REC or a recommendation for further investigation; refundability extends with it); defect-free assumption (Property Condition); designee vesting / direct deeding (Other Conditions); deposit due-window from `{{EMD_DUE_DAYS_WORDS}}`; "Closing is not contingent on financing."

**Deliberately omitted (PSA-deferred, Gabriel 2026-10-20):** casualty / risk of loss, title-objection cure mechanics, closing-deliverables list, governing law and venue, capex cap, Bill of Sale detail (personal property still conveys under Property Condition), affiliated-tenant disclosures, ROFR waiver.

---

## Tokens added or changed for SHORT

All other tokens follow `references/token-reference.md`. `_WORDS` tokens keep the `[word] (digit)` convention.

| Token | Rule | Example |
|---|---|---|
| `{{DEED_FORM}}` | From the state table below | `general warranty deed` |
| `{{TRANSFER_TAX_SENTENCE}}` | From the state table below; one full sentence ending in a period | `Seller will pay all conveyance, transfer, or similar taxes payable upon the transfer of the Property.` |
| `{{OPERATIONS_CONDITIONAL_SENTENCE}}` | Tenanted: the estoppel sentence. Vacant: the preservation covenant. Empty string only if neither applies (never both empty for a vacant deal) | see below |
| `{{EXTENSION_DEPOSIT_NUMERIC}}` | 0.25% of Purchase Price, rounded up to the nearest $5,000, minimum $25,000; digits with `.00` | `25,000.00` |
| `{{PSA_DRAFT_DAYS_WORDS}}` | Includes the unit word | `ten (10) business` |
| `{{CLOSING_DAYS_WORDS}}` | Starts the sentence — capitalize the first word | `Fifteen (15)` |
| `{{PROPERTY_COUNTY}}` | Includes "County" | `Franklin County` |

SHORT uses numeric-only price and deposit (`{{PURCHASE_PRICE_NUMERIC}}`, `{{EMD_NUMERIC}}`); the `_WORDS` price/EMD tokens are not used.

**Operations sentences (verbatim):**
- Tenanted (any lease at Closing): `Seller will deliver tenant estoppel certificates in form reasonably acceptable to Buyer not less than ten (10) business days before Closing.`
- Vacant: `Seller will also maintain active utility service, heat adequate to prevent freeze damage, and security and life-safety systems in operable condition.`

**Concealment overlay (Rule 0c) on SHORT:** delete the sentence beginning "The parties will cooperate with any IRC §1031 exchange" from Other Conditions; the designee-vesting sentence stays. Leak-check still applies.

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
| 17 | Page count = 2. If the filled letter runs to 3 pages, tighten deal-specific phrases (tenant disclosure, zoning) — never delete a survivor clause; if still 3, report it rather than shrinking fonts or margins |
| 22 | Vacant deals: the preservation covenant is the Operations conditional sentence (no casualty-threshold check in SHORT) |

Item 11 (proof-of-funds line) checks for the line directly below the acceptance block on the final page.

**#15 exception:** the acceptance line "Accepted, subject to the execution of a Purchase Agreement." is fixed template text and is exempt from the "Subject to" strike-list entry; any other occurrence still fails.

**Helper script:** the `qc_gate.py` helper in `references/qc-gate.md` asserts the CONDENSED trailer ("140 tenants", ≥2 phone hits). On SHORT, skip those two checks and apply the SHORT #9/#12 rows by hand until the helper gains a SHORT mode.

**Page-break behaviour:** Offer & Acceptance, the signature block, the acceptance block and the proof-of-funds line are chained keep-with-next, so on overflow the last term moves to page 3 with the signatures (the Seller never signs a page carrying no terms). Any filled letter that still reaches 3 pages is reported under #17.

**Token notes (override token-reference.md for SHORT):** `{{TENANT_DISCLOSURE_PHRASE}}` is followed by " — on the general terms below." rather than a period, and still must not end in a comma; for multi-tenant deals leave it empty unless a dominant tenant is material (e.g. `, the largest tenant being Acme Supply, LLC`). `{{CLOSING_DAYS_WORDS}}` opens a sentence — capitalize it (`Fifteen (15)`), unlike the CONDENSED example.
