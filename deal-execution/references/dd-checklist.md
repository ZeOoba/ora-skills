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
