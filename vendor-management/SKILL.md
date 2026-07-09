---
name: vendor-management
description: Vendor scoring, RFP issuance, contract intake, and performance review for Oxford Realty Advisors. Use when the user mentions: vendor, contractor, RFP, bid, vendor score, vendor performance, 1099, W-9, COI, certificate of insurance, vendor contract, MSA, vendor concentration, rebid, vendor onboarding, vendor offboarding, performance review, vendor audit, or any task related to managing the firm's external service providers. v1.0
license: ORA Internal
---

# Vendor Management

Manage the lifecycle of vendor relationships across maintenance, capex, professional services, and supply.

## Scope

All vendors transacted with ORA entities: maintenance, capex contractors, professional services (legal, accounting, brokerage, insurance), property management adjuncts, IT, banking. Excludes LP/lender relationships.

## Triggers

Vendor onboarding, RFP/bid solicitation, vendor performance review, contract renewal, COI/W-9 collection, vendor scoring, rebid decision, 1099 prep, vendor concentration audit.

## Inputs

- Notion Vendor Database (canonical record)
- QuickBooks vendor records (spend, payment history, 1099-eligible flag)
- ora-vendor-scoreboard artifact (TTM scoring)
- COI/W-9 documents in SharePoint /Vendors/[vendor]/
- Contracts and MSAs in SharePoint /Vendors/Contracts/
- Property service requests in maintenance system (Yardi/AppFolio/Rent Manager)

## Standard Workflows

### Vendor Onboarding
1. Collect W-9, COI, and references.
2. Verify COI naming ORA entities as additional insured.
3. Check insurance limits against ORA standards (GL $1M/$2M, umbrella where applicable).
4. Issue MSA from template library.
5. Create Notion record and QuickBooks vendor entry.
6. Output: vendor onboarding packet (DOCX) and SharePoint folder.

### RFP / Rebid
1. Pull current vendor cost, response time, and quality history.
2. Identify 3+ qualified alternatives from Vendor Database or referrals.
3. Generate RFP package (DOCX) with scope, specifications, timeline.
4. Distribute via communication-intelligence skill.
5. Score responses on price, qualifications, references, schedule.
6. Output: vendor selection memo (DOCX) with recommendation.

### Performance Review (semi-annual)
1. Pull TTM transaction data.
2. Score on: cost vs. benchmark, response time, repeat-call rate, tenant feedback.
3. Compare to benchmarks for category.
4. Flag rebid candidates (price drift > 8% YoY OR response time > 1.5× benchmark).
5. Output: vendor scorecard (xlsx) and review memo (DOCX).

### Concentration Audit
1. Compute: top-vendor share by category and overall.
2. Flag single-source dependencies.
3. Recommend: backup vendors for critical categories.
4. Output: concentration risk memo (DOCX).

### COI / W-9 Renewal
1. Quarterly scan of vendor master file.
2. Flag vendors with COI expiring < 60 days.
3. Generate renewal request emails.

## Outputs

- DOCX deliverables follow ORA Institutional Style Guide v1.0+
- xlsx scorecards with per-vendor and per-category views
- File naming: YYYYMMDD_[Vendor-or-Category]_[DocType]_v##.docx
- Notion Vendor Database updates after every interaction
- ora-vendor-scoreboard artifact refresh

## Boundaries

- This skill DRAFTS vendor communications and contracts. POs and signed contracts require Gabriel approval.
- Termination of vendor relationships requires explicit Gabriel decision.
- 1099 issuance handled by accounting; this skill PREPARES the data only.

## Dependencies

- communication-intelligence skill (vendor email drafts)
- legal-intelligence skill (MSA review)
- xlsx skill (scorecard models)
- docx skill (RFPs and memos)
