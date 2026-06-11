---
name: legal-intelligence
description: "Oxford Realty Advisors legal document analysis, clause library, and contract intelligence. Use this skill whenever the user mentions: lease review, PSA review, contract analysis, redline, clause comparison, lease clause, indemnification, default provisions, personal guaranty, environmental indemnity, estoppel, SNDA, tenant improvement, CAM clause, assignment and subletting, insurance requirements, memorandum of lease, deed of trust, promissory note, loan document, solar lease, vendor contract, or any request to analyze, compare, draft, or negotiate a legal document. Also trigger when the user uploads a PDF or DOCX that appears to be a lease, contract, PSA, loan document, or legal agreement. v1.1 (2026-06-11: dead title-commitment-redline deferral removed; title commitments handled in-skill)."
---

# Legal Intelligence — Oxford Realty Advisors

## MODULE 1: DOCUMENT CLASSIFICATION

When a legal document is uploaded, immediately classify it as one of:

- **Lease** — commercial, industrial, retail, office, ground, or solar
- **Purchase and Sale Agreement (PSA)**
- **Loan document** — promissory note, deed of trust, guaranty, loan application
- **Estoppel certificate**
- **SNDA** — Subordination, Non-Disturbance, and Attornment agreement
- **Vendor/service contract**
- **Amendment or addendum** to an existing agreement
- **Letter of Intent (LOI)**
- **Title commitment / title insurance policy** — handled HERE (this skill) at the clause level, with `deal-execution` coordinating closing context when the commitment surfaces inside an active DD workflow. Review structure: verify Schedule A (insured, estate, amount, effective date, vesting) against the PSA; cross-walk every Schedule B-I requirement to a responsible party and cure path; classify each Schedule B-II exception as CTC (clear to close), NEG (negotiate/endorse over), or WALK (deal-threatening); and assemble the ALTA endorsement-request list. Output: XLSX exception matrix + DOCX endorsement-request letter per ORA institutional standards. *(v1.1, 2026-06-11: the former deferral to a `title-commitment-redline` skill is removed — that skill was scaffolded 2026-05-15 but never installed on any surface; verified absent 2026-06-09 audit and re-verified 2026-06-11.)*

State the document type at the top of every analysis before proceeding.

---

## MODULE 2: LEASE REVIEW FRAMEWORK

For any commercial lease, extract and analyze the following in order:

### ECONOMICS
- Base rent schedule with all escalations: annual %, CPI, fixed dollar, or market reset
- Lease type classification: NNN, modified gross, gross, or percentage rent
- CAM structure: pro rata, base year stop, or fixed CAM with annual escalation cap
- Tenant improvement allowance: amount, disbursement conditions, amortization if early termination
- Free rent or concession periods
- Security deposit: dollar amount vs. monthly rent ratio
- Calculate rent PSF annually for the entire lease term — present as a schedule table

### TERM & OPTIONS
- Initial term: commencement date, expiration date, term length
- Extension options: count, length per option, notice period required, rate reset mechanism
- Early termination rights: trigger conditions, notice period, termination penalty (typically 6 months' rent + unamortized TI)
- Right of First Refusal (ROFR) on adjacent space or on purchase of property
- Right of First Offer (ROFO): trigger, offer period, strike price mechanics
- Holdover provisions: rate (flag if not explicitly 150% or higher), tenancy type created

### RISK PROVISIONS
- **Personal guaranty:** present/absent, full vs. limited scope, burn-off schedule, corporate vs. individual
- **Assignment and subletting:** consent standard (sole discretion vs. not unreasonably withheld), profit sharing, landlord recapture right
- **Default provisions:** monetary cure period, non-monetary cure period, notice requirements, landlord remedies (termination, acceleration, re-entry, damages)
- **Insurance requirements:** minimum coverages, additional insured language, waiver of subrogation, 30-day cancellation notice
- **Indemnification:** mutual vs. one-sided, cross-indemnity carve-outs, survival period post-lease
- **Environmental:** tenant vs. landlord responsibility for contamination, pre-existing condition carve-outs, survival
- **Casualty and condemnation:** termination triggers (threshold % of damage), restoration obligations, rent abatement during restoration, allocation of condemnation awards
- **Subordination:** automatic vs. conditional, SNDA requirement, non-disturbance protections for tenant

### LANDLORD-SPECIFIC CONCERNS (Gabriel's history-derived)
Flag each of the following if present:
- ⚠️ Below-market rent — compare to Oxford portfolio comps and stated market rates
- ⚠️ Related-party or self-dealing terms — tenant-favorable provisions without market justification
- ⚠️ Extension notice period shorter than 9 months — risk of inadvertent holdover
- ⚠️ No mark-to-market reset at extension — locks landlord into below-market rent for option term
- ⚠️ Structural maintenance allocated to landlord — quantify roof/HVAC/structure CapEx exposure
- ⚠️ Memorandum of lease provisions that conflict with lease body (per 1333 Research Road precedent)
- ⚠️ No explicit COI expiration tracking obligation on tenant
- ⚠️ ROFR or purchase option that would impair lender financing or future sale

---

## MODULE 3: PSA REVIEW FRAMEWORK

For any Purchase and Sale Agreement:

### KEY TERMS EXTRACT
- Purchase price, deposit amount, deposit structure (hard/soft, phasing)
- Due diligence period: length, start trigger, extension rights, termination right
- Closing date: target, outside closing date, extension rights and costs
- Representations and warranties: survival period, materiality qualifiers, knowledge qualifiers
- Closing conditions: title, survey, tenant estoppels, SNDA, environmental
- Prorations: rent, taxes, CAM, security deposits — proration date and mechanics
- Assignment rights: can Oxford assign to an affiliated entity pre-closing?

### CRITICAL PROVISIONS (Gabriel's history-derived — hold firm on all three)
- **Willful default carve-out:** Seller must not be able to simply walk away on a default — ensure seller's deposit obligation or specific performance remedy is available for willful default
- **Memorandum of contract recording right:** Oxford's right to record notice of contract in public record as cloud against title
- **MAC clause:** Material Adverse Change provision giving Oxford termination right if material adverse change to property between execution and closing

### PSA RED FLAGS
- Seller representations limited to "actual knowledge" without deemed knowledge of property manager
- No representation on pending litigation or code violations
- Environmental indemnity carved out entirely
- Tenant estoppel threshold below 85% of in-place NNN rent
- Missing cross-default between PSA and any related documents (seller leaseback, etc.)

---

## MODULE 4: CLAUSE LIBRARY

Oxford's preferred clause language for key provisions:

### RENT ESCALATION
- **Standard fixed:** 3.0% annual increase on each anniversary of commencement date
- **CPI-based:** Greater of 2.0% or CPI-U (All Urban Consumers, U.S. City Average), capped at 4.0%
- **Market reset at extension:** FMV determined by independent MAI appraisal; if parties cannot agree within 30 days, each selects an appraiser, the two appraisers select a third, and the median of three appraisals controls

### DEFAULT AND REMEDY
- Monetary default cure period: 5 calendar days after written notice
- Non-monetary default cure period: 30 days after written notice (extended for diligent cure in progress)
- Late fee: 5% of overdue amount after 5-day grace period
- Interest on overdue amounts: lesser of 18% per annum or maximum rate permitted by law
- Landlord remedies on default: termination of lease + acceleration of all remaining rent + repossession + actual damages + attorneys' fees

### ENVIRONMENTAL
- Tenant bears full liability for all environmental conditions caused or contributed to by tenant or tenant's agents
- Landlord bears responsibility for pre-existing environmental conditions documented in Phase I/II at execution
- Mutual indemnification with 3-year survival period post-lease expiration

### INSURANCE MINIMUMS (Oxford standard)
- Commercial General Liability: $1,000,000 per occurrence / $2,000,000 aggregate
- Property / Casualty: replacement cost value of all tenant improvements and personal property
- Workers' Compensation: statutory limits; Employer's Liability: $500,000
- Umbrella / Excess Liability: $5,000,000 per occurrence
- Oxford named as additional insured on all policies
- 30-day advance written notice of cancellation or material change
- Certificates provided to Oxford within 10 days of policy inception and annually thereafter

### PERSONAL GUARANTY
- **Full guaranty option:** Full, unconditional, irrevocable personal guaranty of all lease obligations for the full term
- **Burn-off option:** Full guaranty for first 24 months; burns off if no uncured monetary default as of month 24
- **Rolling option:** Guaranty covering next 12 months of base rent, rolling forward monthly; no burn-off

### ASSIGNMENT / SUBLETTING
- Landlord consent required; consent not to be unreasonably withheld, conditioned, or delayed (30-day response window)
- Landlord receives 50% of any sublease premium above base rent (after deducting tenant's reasonable transaction costs)
- Landlord retains recapture right for any proposed assignment: may terminate lease and re-lease space directly within 30 days of tenant's assignment request

---

## MODULE 5: COUNTERPARTY PATTERN RECOGNITION

### KING ENERGY (solar leases)
Historical pattern — King Energy pushes for:
- Unilateral ITC (Investment Tax Credit) termination right if NTP (Notice to Proceed) not reached by specified date
- Extended recoupment window (standard 5 years → requests 10 years)
- Reduced Site Access Fee caps in later years

Oxford should push back on:
- Expansion of security safeguarding duty beyond standard reasonable care
- Rent deferral beyond Year 5 of operations
- NTP deadlines without corresponding King Energy diligence obligations (they cannot trigger termination by failing to obtain permits)
- Broad force majeure that covers ITC policy changes

### SELLER'S COUNSEL ON PSAs
Common deletion attempts — HOLD FIRM on all three:
1. Willful default carve-out (do not remove)
2. Memorandum of contract recording right (do not remove)
3. MAC clause (do not remove)

### SMALL INDUSTRIAL TENANTS
Common tenant pushback areas:
- Personal guaranty (can concede burn-off but not full waiver for new tenants)
- CAM reconciliation transparency (can concede annual statement; cannot concede audit right)
- Insurance minimums (can reduce umbrella to $2M for small tenants; cannot waive additional insured)

Oxford can offer without significant risk:
- Minor TI allowance ($3-5/SF for paint/carpet)
- 1 month free rent on new leases (not renewals)
- Flexible move-in timing (2-4 week window)

---

## MODULE 6: DOCUMENT COMPARISON ENGINE

When asked to compare two versions of the same document type:

1. Produce a structured discrepancy table in this format:
   | Section | Version A Language | Version B Language | Classification | Beneficiary | Oxford Impact |
   |---------|-------------------|-------------------|---------------|-------------|---------------|

2. Classify each discrepancy:
   - **Material** — changes rights, obligations, economics, or risk allocation
   - **Minor** — clarifying language only, no substantive change
   - **Drafting Error** — appears to be an unintentional inconsistency or omission

3. Identify which party benefits from each change (Landlord / Tenant / Neutral)

4. Flag any provision that contradicts another recorded document (title commitment, memorandum of lease, prior amendment, recorded easement)

5. Produce executive summary: total discrepancy count, material vs. minor breakdown, top 3 issues requiring resolution, recommended negotiation strategy

6. Output format: offer both inline markdown table AND .docx file via document-assembly skill

---

## TRIGGER PHRASES
Activate this skill automatically when Gabriel says:
"review this lease", "PSA review", "compare these contracts", "redline", "clause analysis", "what does this provision mean", "is this standard", "solar lease", "King Energy", "Symetra", "loan docs", "promissory note", "deed of trust", "estoppel", "SNDA", "personal guaranty", "assignment clause", "default provision", "indemnification", "CAM clause", "TI allowance", "extension notice", "holdover", "environmental indemnity"
