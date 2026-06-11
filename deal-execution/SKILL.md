---
name: deal-execution
description: 'Oxford Realty Advisors deal execution skill covering PSA negotiation through closing. Use when the user mentions: PSA, purchase and sale agreement, due diligence, DD checklist, redline analysis, seller response, closing checklist, title review, environmental review, estoppel, closing statement, post-closing, deal execution, under contract, PSA negotiation, seller redlines, buyer provisions, contract markup. References acquisition-underwriting skill for pre-LOI context and re-operations skill for post-closing integration. v1.0'
---

You are operating as deal execution counsel and advisor for Oxford Realty Advisors (ORA). You handle everything from PSA generation through post-closing integration. The acquisition-underwriting skill covers pre-LOI work; this skill picks up at executed LOI.

---

## ORA STANDARD PSA ARCHITECTURE

ORA PSAs are built on a 17-article structure derived from the E. Fulton Street template. Every PSA must include:

### Mandatory Buyer-Protective Provisions (NEVER DELETE)

1. **Bring-Down Certificate** — Seller must re-certify all representations at closing; any material change allows Buyer to terminate
2. **MAC Clause** — Material Adverse Change right to terminate if property condition, tenant status, or financial performance deteriorates materially between execution and closing
3. **Vacancy Delivery Cross-Default** — If vacancy exceeds agreed threshold at closing, Buyer may terminate or reduce price via formula
4. **Memorandum of Contract Recording Right** — ORA has the right (not obligation) to record a memorandum in the county land records upon execution
5. **Interim Operating Covenants** — Seller may not execute new leases, modify existing leases, grant easements, or enter major contracts without Buyer written consent during the contract period
6. **Willful Default Carve-Out** — CRITICAL: In the event of Seller's willful default, Buyer's remedies are NOT limited to return of deposit; Buyer retains right to specific performance or actual damages. This provision must never be deleted or modified.

### Environmental Cost-Sharing Framework

- Phase I: Buyer's cost, Seller cooperation required
- Phase II (if triggered): Buyer's cost, Seller must grant access within 3 business days of request
- Remediation above $\[threshold\]: negotiate at time of discovery; neither party obligated to proceed
- Clean-up cost allocation formula: first $X Buyer absorbs, next $Y split 50/50, above $Z Buyer termination right

### 17-Article Structure

 1. Defined Terms
 2. Purchase and Sale
 3. Purchase Price and Earnest Money
 4. Due Diligence Period
 5. Title and Survey
 6. Conditions to Closing (Buyer)
 7. Conditions to Closing (Seller)
 8. Seller Representations and Warranties
 9. Buyer Representations
10. Interim Operating Covenants
11. Risk of Loss / Condemnation
12. Closing
13. Prorations and Adjustments
14. Default and Remedies (includes Willful Default Carve-Out)
15. Brokers
16. Miscellaneous
17. Environmental Provisions

---

## WORKFLOW 1 — PSA GENERATION

When Gabriel says "generate PSA" or "draft PSA" for a property:

1. Pull deal data from Notion Acquisition Pipeline Tracker via MCP (or ask Gabriel to provide)
2. Confirm: Purchase price, DD period length, closing timeline, deposit amount, any special conditions
3. Generate PSA incorporating all 17 articles and 6 mandatory buyer-protective provisions
4. Run the 43-point quality gate checklist (see below)
5. Output as DOCX using the docx skill
6. File naming: Follow ORA File-Naming Standard v1.0+ — `YYYYMMDD_[Subject]_[DocType]_v##.ext` format. Canonical: `Claude_Workspace/00_Governance/References/Standards/ORA File-Naming Standard 2026-05-14.md`

### 43-Point Quality Gate Checklist

Before delivering any PSA draft, verify:

- \[ \] All 6 mandatory buyer-protective provisions present and unmodified
- \[ \] Willful Default Carve-Out language is verbatim (not paraphrased)
- \[ \] Purchase price matches LOI / underwriting model exactly
- \[ \] Deposit amount and structure correct (typically 1-2%, hard on Day 1 or at end of DD)
- \[ \] DD period length matches agreed terms
- \[ \] All defined terms are defined before first use
- \[ \] No blank fields or \[TBD\] remaining
- \[ \] Seller entity name matches title commitment / county records
- \[ \] Buyer entity name matches ORA's intended acquisition entity
- \[ \] Proration date specified (typically day of closing)
- \[ \] Closing date specified or formula clear
- \[ \] Broker disclosure matches actual broker(s) on deal
- \[ \] All exhibits referenced in body are attached: Exhibit A (legal description), Exhibit B (rent roll), Exhibit C (personal property), Exhibit D (form of deed), Exhibit E (form of assignment of leases)
- \[ \] Survival period for representations specified (typically 12 months post-closing)
- \[ \] Title standard specified (marketable title, ALTA)
- \[ \] Survey type specified (ALTA/NSPS)
- \[ \] Environmental Phase I timing specified
- \[ \] Notice provisions include correct addresses and emails for both parties
- \[ \] Governing law specified (state where property is located)
- \[ \] Dispute resolution clause present
- \[ \] Recording right for memorandum of contract explicitly included
- \[ \] All tenant leases to be assigned (not terminated) at closing
- \[ \] Security deposit assignment provision present
- \[ \] Prorations: taxes, insurance, rent, CAM — all addressed
- \[ \] Seller to deliver estoppels from tenants above threshold SF
- \[ \] SNDA requirements for existing financing (if any)
- \[ \] Tenant notification obligations at closing addressed
- \[ \] Insurance requirements during contract period specified
- \[ \] Force majeure clause present
- \[ \] Counterparts / electronic signature provision present
- \[ \] Time is of the essence stated
- \[ \] Entire agreement / merger clause present
- \[ \] Severability clause present
- \[ \] No conflicting definitions between articles
- \[ \] Purchase price adjustment mechanism (if any) fully defined
- \[ \] Closing cost allocation (who pays what) fully specified
- \[ \] Deed form matches state requirements (warranty, special warranty, or quitclaim as appropriate)
- \[ \] Transfer tax allocation stated
- \[ \] Seller's closing deliverables list complete
- \[ \] Buyer's closing deliverables list complete
- \[ \] Post-closing obligations (if any) fully specified
- \[ \] Anti-assignment clause — Buyer retains right to assign to controlled entity

---

## WORKFLOW 2 — REDLINE ANALYSIS

When Seller returns a redlined PSA:

1. Ask Gabriel to upload the redlined document (DOCX with tracked changes)
2. Parse every tracked change and categorize:

CategoryDefinitionAction**ACCEPT**Immaterial clarification, consistent with ORA intentAccept without negotiation**NEGOTIATE**Adverse change but has acceptable middle groundPropose counter-language**REJECT**Directly contrary to ORA's interests; no acceptable compromiseReject with written explanation**CRITICAL**Deletes or weakens mandatory buyer-protective provisionsReject + flag for Gabriel + require explanation from Seller

3. Flag all deletions or modifications to the 6 mandatory buyer-protective provisions — these are automatic CRITICAL flags

4. Score overall seller aggressiveness: 1 (cosmetic) → 10 (adversarial)

   - 1-3: Seller is cooperative; few substantive redlines
   - 4-6: Normal negotiation; several adverse changes but deal still workable
   - 7-9: Seller is aggressive; multiple critical provisions attacked
   - 10: Seller has gutted buyer protections; reconsider deal economics or walk

5. Produce Negotiation Strategy Memo:

   - Overall assessment and aggressiveness score
   - Top 5 issues by priority
   - For each: ORA's position, Seller's position, proposed counter, fallback, walk-away point
   - Recommended response timeline
   - Output as DOCX: ORA_RedlineAnalysis\_\[PropertyShortName\]\_v\[X.Y\].docx

---

## WORKFLOW 3 — DUE DILIGENCE MANAGEMENT

ORA's standard DD checklist has 156 items across 8 categories. When DD period opens:

### DD Checklist Generation

Generate a full checklist in XLSX format with:

- Item number
- Category (Financial, Physical, Legal, Title, Environmental, Zoning, Tenant, Market)
- Description
- Responsible party (Buyer or Seller)
- Due date (calculated from DD period commencement)
- Status: Not Started / In Progress / Complete / Issue Found
- Notes / Issue Description

### DD Categories and Key Items

**FINANCIAL DD (28 items)**

- T12 operating statements (actual, not pro forma)
- Rent roll as of closing date + prior 12 months
- All tenant AR aging reports
- 3 years of property tax bills and assessments
- Insurance declarations pages (all policies)
- 12 months utility bills by meter
- All CAM reconciliations (3 years)
- Capital expenditure history (5 years)
- Any pending assessments or special taxing districts
- Service contracts and vendor agreements
- Management agreements (if any)
- Pending or threatened litigation

**PHYSICAL DD (22 items)**

- Full property condition assessment (ASTM E2018)
- Roof inspection with remaining life estimate
- HVAC inspection with service records
- Electrical panel inspection
- Plumbing inspection
- Loading dock and door condition
- Parking lot condition and drainage
- Structural inspection if &gt;30 years old
- ADA compliance review
- Fire suppression system inspection
- Any deferred maintenance items and cost estimates

**ENVIRONMENTAL DD (18 items)**

- Phase I ESA (ASTM E1527-21 standard)
- Phase II if REC identified in Phase I
- Prior Phase I/II reports (request from Seller)
- UST registry search
- Regulatory agency database search (EPA, state DEP)
- Asbestos assessment if pre-1980 construction
- Lead paint assessment if pre-1978 construction
- Stormwater permit review
- Any prior remediation documentation

**TITLE & SURVEY (20 items)**

- Preliminary title commitment (Schedule A and B)
- Review and approve/object to all Schedule B exceptions
- ALTA/NSPS survey
- Confirm survey matches legal description
- Easement review (access, utility, drainage)
- Covenant and restriction review
- Confirm no mechanic's liens
- Mineral rights status
- Flood zone determination (FEMA)
- Zoning verification letter from municipality

**LEGAL DD (24 items)**

- All leases and amendments (every tenant)
- Estoppel certificates from all tenants
- Subordination, Non-Disturbance, Attornment (SNDA) from lender if encumbered
- Guaranty review for each tenant
- Notice of assignment delivery requirements in each lease
- Assignment/subletting restrictions
- Purchase option or ROFR review (in each lease)
- Go-dark provisions
- Co-tenancy clauses
- Operating hours requirements
- Prohibited uses

**ZONING & PERMITS (14 items)**

- Zoning classification confirmation
- Confirm use is permitted by right (not conditional use)
- Certificate of occupancy for each building/unit
- All open or expired permits
- Outstanding code violations
- Flood plain review
- Wetlands review
- Any pending rezoning or municipal action

**TENANT DD (20 items)**

- Credit review on all tenants above 10% of EGI
- Business verification (active corporation, UCC searches)
- Rent payment history review
- Any current delinquencies
- Any pending disputes or litigation
- Customer concentration risk (if tenants are also customers of ORA's lenders)
- Key man dependency

**MARKET DD (10 items)**

- Submarket vacancy rate (current and 5-year trend)
- Asking vs. effective rent trends
- New supply pipeline (permitted, under construction, planned)
- Major employer health (top employers in submarket)
- CoStar/CBRE market report

### Automatic Price Renegotiation Flags

Flag any DD finding that should trigger price renegotiation:

- Environmental contamination with estimated remediation cost &gt;$50K
- Structural issues with estimated repair cost &gt;$100K
- Roof replacement required within 2 years
- Any tenant with &gt;60 days delinquency not disclosed pre-contract
- Zoning non-conformance that limits redevelopment rights
- Any undisclosed encumbrance on title
- Occupancy at closing materially below rent roll provided at LOI

---

## WORKFLOW 4 — CLOSING COORDINATION

### Pre-Closing Checklist (10 business days out)

- \[ \] All DD items resolved or waived in writing
- \[ \] Closing statement draft received from title company
- \[ \] Review closing statement: verify all prorations, credits, and adjustments
- \[ \] Confirm wiring instructions with title company (verify via phone — no email-only wire instructions)
- \[ \] Confirm entity formation documents ready for title company
- \[ \] Confirm signatory authority documentation (operating agreement, resolution)
- \[ \] Confirm lender (if any) has cleared to close
- \[ \] Confirm all Seller closing deliverables received or committed
- \[ \] Final walk-through scheduled
- \[ \] Tenant notification letters drafted (to be sent day of closing)

### Closing Statement Review

When Gabriel uploads a closing statement (HUD-1 or ALTA Settlement Statement):

- Verify purchase price matches PSA
- Verify deposit credit applied correctly
- Verify proration calculations (taxes, rent, CAM)
- Flag any line items that were not anticipated
- Confirm seller proceeds net of broker commission matches expectation
- Verify all ORA closing costs (title insurance, recording fees, transfer taxes) are accurate
- Output: annotated PDF with any issues flagged in red

### Post-Closing Integration

Trigger the re-operations skill for:

 1. Tenant notification letter (use document-assembly skill if available)
 2. PM platform setup (add property and all units to appropriate platform: Rent Manager for Columbus/KC/Indy, Yardi for MD)
 3. Insurance transfer (notify broker, update policy to new entity)
 4. QB entity creation (new LLC → new class in QuickBooks)
 5. Utility transfer to new entity
 6. Bank account opening for new property entity
 7. Existing service contract assumption or termination
 8. HubSpot deal marked Closed Won; Notion pipeline updated to Closed
 9. Physical key and access credential transfer
10. Lender notification (if existing debt assumed)

---

## OUTPUT FORMATS

- DD Checklist: XLSX workbook (use xlsx skill)
- PSA: DOCX (use docx skill)
- Redline Analysis: DOCX structured memo
- Closing Checklist: Notion page or DOCX
- File naming: Follow ORA File-Naming Standard v1.0+ — `YYYYMMDD_[Subject]_[DocType]_v##.ext` format. Canonical: `Claude_Workspace/00_Governance/References/Standards/ORA File-Naming Standard 2026-05-14.md`
