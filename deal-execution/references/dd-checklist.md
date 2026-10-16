# deal-execution — DD checklist categories and key items

Moved out of `SKILL.md` on 2026-09-22 (body split). Read before generating the DD checklist workbook (Workflow 3) and before waiving the DD contingency on any occupied suite (Lease-Chain Integrity). ORA's standard DD checklist has 156 items across 8 categories; the key items per category are below.

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

**TITLE & SURVEY (21 items)**

- Preliminary title commitment (Schedule A and B) — abstract via `title-exam-abstraction`, which also supplies the vesting record Lease-Chain Integrity below checks landlord identity against
- Review and approve/object to all Schedule B exceptions
- ALTA/NSPS survey
- Confirm survey matches legal description
- Easement review (access, utility, drainage)
- Covenant and restriction review
- Confirm no mechanic's liens
- Mineral rights status
- Flood zone determination (FEMA)
- Zoning verification letter from municipality
- **If the parcel sits in a PD/PUD:** obtain the approved PD plan from the planning department, plus a written statement from a named official of the **amendment tier** (minor/administrative vs. major/board) for any intended site change and for any use ORA may re-tenant into — `ora-flood-zoning-dd` Step 6A. A municipality confirming that a recorded cross-access or parking instrument is *not* a PD requirement clears the **zoning** question only: the instrument still binds every party and successor, and terminating or amending it stays a multi-party consent-and-recording deliverable. Reduced parking under a PD plan can also carry an updated-parking-plan filing on each new tenancy — a post-closing operations item, not a closing item, but it belongs in the register before it is forgotten.

**LEGAL DD (24 items)**

- All leases and amendments (every tenant) — **EXECUTED counterparts, not file copies (see Lease-Chain Integrity below)**
- Estoppel certificates from all tenants — draft via `estoppel-request-generation`, which pre-fills from the lease abstract and converts Lease-Chain Integrity/other DD defects into certification-caveat language; do not draft blank-form estoppels by hand
- Subordination, Non-Disturbance, Attornment (SNDA) from lender if encumbered
- Guaranty review for each tenant
- Notice of assignment delivery requirements in each lease
- Assignment/subletting restrictions
- Purchase option or ROFR review (in each lease)
- Go-dark provisions
- Co-tenancy clauses
- Operating hours requirements
- Prohibited uses

**LEASE-CHAIN INTEGRITY (Category: Legal — run on every occupied suite — added v1.5)**

> Origin: 2026-08-21, 754 Old State Route 74. Two separate defects surfaced on one small multi-tenant building. The
> anchor's base lease in the seller's file was **unexecuted** — blank signature lines, page struck diagonally, annotated
> "Lease Sent 7/14/20" — while the First Amendment that amends it by reference, and certifies no party is in default, was
> fully signed. The intervening three-year renewal existed only as a handwritten margin note. On the second suite the
> landlord named in the lease was not the seller at all. Buyer would have closed holding an executed amendment to a lease
> it could not prove was signed.

For each occupied suite, reconstruct and verify the full chain before waiving the DD contingency:

- Build the instrument chain end to end — base lease, every renewal, every amendment — by date and instrument name. Any
  term evidenced only by a margin note, an email, or a rent-roll line is a **gap**, not a term.
- Confirm an **executed counterpart exists for every link**, not merely a copy. Blank signature blocks, "sent" annotations
  and diagonal strikes mark transmittal drafts. Add missing executed originals to the seller's closing-deliverable list.
- Confirm the **landlord named in each lease matches title vesting** — the authoritative source is `title-exam-abstraction`'s
  vesting record, not the self-reported "seller" field on the deal (a DBA or predecessor-entity mismatch that title vesting
  would catch can pass a bare seller-name comparison clean). If `title-exam-abstraction` hasn't run yet for this deal, fall
  back to comparing against the seller (or a predecessor whose interest demonstrably ran to the seller) and flag the check
  as provisional pending the title abstract. A mismatch is an authority defect, not a typo: it raises whether the seller can
  convey the leasehold stream and whether the tenant owes rent to the party ORA is buying from. Two mismatches across two
  leases is a papering pattern — escalate to an affirmative PSA representation rather than a one-off correction.
- Catalogue every **manuscript amendment** on the face of each lease (struck clauses, interlineated dates or rents,
  hand-completed party lines) and confirm each is initialed by all parties. See `lease-abstraction-pipeline` STEP 2A —
  OCR does not see ink, so this requires reading page images.
- Reconcile **tenant of record** against the rent roll and the estoppel. A natural person with no entity and no guarantor
  is a different credit than the trade name on the rent roll suggests.

**ENTITY VERIFICATION (Category: Legal — run on every acquisition: before the first PSA draft, again before estoppels go out, and again within 30 days of closing — added v1.10)**

> Origin: 2026-10-15, 754 Old State Route 74. Estoppel V3 was ready for signature with three party names never checked
> against a state record: the 754C co-tenant "Godesana Organics, LLC" (the 2020 lease says "goDesana LLC"), the 754B trade
> name "3Waters Behavioral Health", and a Union Township PD Minor Amendment approved for applicant "Oxford Financial
> Partners, LLC" — not ORA's contracting entity, Oxford Capital Partners, LLC. Each was chased one-off eight days before the
> PSA §9.5 estoppel delivery deadline.

Look up, in the business-entity registry of its **state of formation** (and of the **property's state** where it is
foreign-registered there), every party that will sign, be named in, or be certified in a deal document:

- **Seller**, and any predecessor in the lease chain or in title vesting.
- **Each tenant entity, and each trade name** on the rent roll, leases or estoppels (assumed/fictitious-name filings are a
  separate search, sometimes county-level). A natural-person tenant is confirmed as having no entity behind it.
- **Each entity guarantor.**
- **ORA's own buyer and assignee entities**, and any ORA entity named as applicant or owner on a municipal filing
  (zoning, PD, permits). ORA's own names are where a wrong one is least likely to be caught.

Record for each party in the Deal-Terms Register: exact registered name (punctuation and capitalization as filed),
entity number, type, formation state, status, registered agent, date checked, and the registry record as evidence.
Never type a party name from memory or from another document's spelling.

Registries for ORA's states: Ohio — Secretary of State Business Search; Maryland — SDAT Business Entity Search
(Maryland Business Express; read the forfeiture status, not only "active"); Indiana — INBiz; Wisconsin — DFI corporate
records search; Missouri — Secretary of State business entity search; Kansas — Secretary of State business entity search;
Tennessee — Secretary of State business search. Delaware-formed entities: Division of Corporations entity search (status
there requires ordering a good-standing certificate).

Act on the result:
- **Name differs from the document** → conform the document to the registered name. Where a lease used a variant, the
  estoppel recites both and the tenant certifies they are the same entity (`estoppel-request-generation`).
- **Status not active / good standing** (forfeited, cancelled, revoked, dissolved) → an authority defect, not a typo: the
  entity cannot validly sign. Seller: affirmative PSA representation plus a good-standing certificate as a closing
  deliverable. Tenant: surface before the estoppel goes out — it is a credit question and a signature-authority question.
- **Trade name with no entity behind it** → the individuals are the tenant; draft every instrument that way.
- **ORA entity misnamed on a municipal filing** → correct it with the municipality, or document it in the closing file,
  before any instrument cites that approval.

Re-run the status check within 30 days of closing (good standing can lapse mid-contract) and put good-standing
certificates for Seller and the ORA buyer entity on the closing-deliverables list.

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
- Business verification (registry status per **Entity Verification** under Legal above; UCC searches)
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
