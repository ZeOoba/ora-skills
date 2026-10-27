> **v1.13:** this file describes the retired CONDENSED master (`templates/archive/LOI_Master_Template_Condensed_v1.1.docx`). Its jurisdiction-phrase and known-condition-carveout tables remain valid as value rules (SKILL.md Rules 4–5); everything else is history.

# loi-generation — master-template mechanics

Moved out of `SKILL.md` on 2026-09-22 (body split). Read before evaluating the inline §13 entity-interest conditional and before renumbering sections after conditional deletion.

## §13 inline entity-interest conditional (template hook, added 2026-08-18)

**Template hook (added 2026-08-18):** the master template carries this as an INLINE conditional within §13 (Acquisition Structure and Assignment) — a `▶ CONDITIONAL ◀` block containing one sentence keyed to `{{ENTITY_INTEREST_TYPE}}`, immediately following the existing Buyer-designee-LLC paragraph. It does NOT get its own numbered heading and does NOT affect section renumbering — evaluate it independently of the four numbered conditionals (§8/§9/§10/§11). Default is DELETE: fire it only when Seller itself holds the Property through a single-asset entity (an LLC, corporation, or LP whose sole asset is the Property) AND Buyer wants to preserve the option to buy that entity instead of taking a deed. A trust seller does NOT get this treatment — a trust is not a signing legal person in the entity-interest sense, and ORA deals with trust sellers convey by deed with the trustee identified on the Execution Page (see 3700 Kinsman Blvd, 2026-08-18, where this exact question arose and was resolved to deed conveyance).

## Format selection rationale (Gabriel ruling 2026-06-10)

Rationale (Gabriel ruling 2026-06-10): a sophisticated counterparty expects the PSA to carry the legal weight; an over-lawyered LOI invites pre-PSA redlining and delay. With unsophisticated sellers the longer form anchors more terms while leverage is highest.

## CONDENSED merge map (Decision Rule 0b)

**CONDENSED merge map** (apply after conditional deletion/renumbering):
1. §1 Price/Deposit/Closing → single block paragraph.
2. §2 document-delivery bullets → one "property file" sentence (tax bills 3 yrs, plans/permits/COs, existing survey & title, environmental reports + governmental correspondence, service contracts + COIs, utility account info, vacancy confirmation or rent roll).
3. §4 Property Condition → two sentences: defect-free assumption (the repricing hook — ALWAYS retain) + as-is delivery with systems-operable standard. Bill-of-sale conveyance moves to the PSA list in Process.
4. §6 Prorations → one paragraph: "customary [County] allocations," long-proration method + BOR rights (OH), Seller pays conveyance fee / owner's policy / half escrow / lien releases; Buyer pays endorsements / deed recording / half escrow / survey.
5. Exclusivity + Definitive Documentation → merged "Process and Exclusivity" section, ending with the PSA-deferred list: bill of sale; Buyer access & insurance during Study Period; **Deposit due within two (2) business days after PSA execution**; closing/deed mechanics per the Acquisition Structure section.
6. Miscellaneous → two sentences (confidentiality 2 yrs; OH law/venue/time-of-essence/counterparts-e-signature).

## Resulting section counts after conditional deletion

**Resulting section counts:**
- Vacant property: 12 sections (1–7, 12–16 from template, renumbered to 1–12)
- Arm's-length single-tenant, no ROFR: 14 sections (1–7, 9, 11, 12–16 renumbered to 1–14)
- Arm's-length single-tenant, with ROFR: 15 sections
- Affiliated single-tenant, with ROFR: 16 sections (all sections retained)
- Affiliated single-tenant, no ROFR: 15 sections

These counts reflect the four numbered conditionals only. The inline §13 entity-interest election adds a paragraph (not a numbered section) when fired, and never changes the count above or triggers renumbering.

## Jurisdiction phrase resolution (Decision Rule 4)

### 4. Jurisdiction phrase resolution

`{{PROPERTY_JURISDICTION_PHRASE}}` fills the §2 jurisdiction-verification clause. Resolve as:

| Property location pattern | Phrase |
|---|---|
| Incorporated city, no surrounding township ambiguity | `the City of [CityName] and [County] County` |
| Address may straddle city/township (Columbus area, KC area) | `the City of [CityName], [County] County, [Township1], and/or [Township2]` |
| Unincorporated county area | `[County] County` |
| Confirmed Gahanna/Columbus suburb fully incorporated | `the City of [CityName] and Franklin County` |

When unclear, default to the broader formulation listing all potentially applicable jurisdictions.

## Known-condition carveout (Decision Rule 5)

### 5. Known-condition carveout (§4)

`{{KNOWN_CONDITION_CARVEOUT}}` fills inline within §4. Use when OM discloses a known condition:

| OM disclosure | Carveout text |
|---|---|
| Roof age ≥18 years | `(except for the roof, which the parties acknowledge is approximately [N] years old and approaching the end of its useful life)` |
| HVAC age ≥15 years | `(except for the HVAC system, which the parties acknowledge is approaching the end of its useful life)` |
| Deferred maintenance disclosed | `(except for the items of deferred maintenance disclosed in [Seller's marketing materials / Schedule X])` |
| Multiple conditions | Combine: `(except for [item 1] and [item 2])` |
| No known issues | DELETE the `{{KNOWN_CONDITION_CARVEOUT}}` token; leave no replacement |
