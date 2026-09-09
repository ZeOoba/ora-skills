---
name: investor-relations
description: Oxford Realty Advisors investor relations fund-level reporting and LP accounting. Use when the user mentions: capital call, distribution notice, K-1, LP report, fund accounting, capital account, commitment, called capital, distributed capital, NAV, IRR, MOIC, TVPI, DPI, RVPI, LP onboarding, side letter, subscription agreement, or LP meeting prep/materials. Owns the numbers and records, not correspondence: drafting an LP-facing letter, email, or query response routes to `communication-intelligence` (or `legal-intelligence` for redline/negotiation work, e.g. a side letter or subscription agreement markup) per CLAUDE.md's Comms drafting canon. v1.1 (2026-09-09: narrowed scope, added correspondence deferral — collided with CLAUDE.md's LP-mail canon via an old open-ended clause; ora-setup-audit R23-9)
license: ORA Internal
---

# Investor Relations

Handle all LP-facing communications, fund-level reporting, capital account maintenance, and LP query response for Oxford Realty Advisors.

## Scope

Covers communications and reporting to existing LPs in any ORA-sponsored entity. Excludes prospective-LP fundraising materials (separate fundraising track).

## Triggers

Capital call drafts, distribution notices, quarterly investor letters, LP query response, K-1 cover letters, LP onboarding, side-letter analysis, capital account reconciliation, LP-meeting prep.

## Inputs

- LP database in Notion (or HubSpot LP records)
- Fund accounting from QuickBooks
- Subscription agreements and side letters in SharePoint /LP/[fund]/
- Quarterly portfolio data from portfolio-reporting skill
- ora-investor-letter-draft prior outputs for narrative continuity

## Standard Workflows

### Capital Call Draft
1. Pull commitment, called-to-date, and uncalled balance for each LP.
2. Compute pro-rata call amount based on the deal funding need.
3. Generate capital call notice DOCX per LP using document-assembly templates.
4. Save to SharePoint /LP/CapitalCalls/YYYYMMDD/.
5. Email Gabriel for review BEFORE LP send.

### Distribution Notice
1. Pull distributable cash from QuickBooks; cross-check ora-cash-position artifact.
2. Apply waterfall: preferred return, return of capital, promote.
3. Compute per-LP distribution by capital account.
4. Generate distribution notice DOCX per LP with breakdown.
5. Update LP database capital accounts.
6. Save to SharePoint /LP/Distributions/YYYYMMDD/.
7. Email Gabriel for review BEFORE LP send.

### Quarterly Investor Letter (auto-drafted by ora-investor-letter-draft)
- Letter from the Principal: narrative, key events.
- Portfolio performance: AUM, NOI, occupancy, WALT.
- Acquisitions and dispositions during quarter.
- Capital markets activity.
- Portfolio outlook (next quarter).
- Final letter requires Gabriel approval before any LP send.

### LP Query Response
1. Pull LP's capital account history and entity holdings.
2. Pull recent communications for context.
3. Draft response in ORA Style, professional tone.
4. Surface any factually ambiguous claims as [SPECULATIVE] for Gabriel review.

### K-1 Cover Letter
1. After CPA delivers K-1s, generate cover letter per LP linking K-1 to entity, cap account, and key tax items.
2. Save to SharePoint /LP/K1/YYYY/.
3. Email Gabriel for review.

## Outputs

- All LP-facing DOCX deliverables follow ORA Institutional Style Guide v1.0+
- File naming: YYYYMMDD_[LP or Fund]_[DocType]_[v##].docx
- All LP capital account changes mirrored to Notion / fund-accounting system
- 16-point QC Gate run on every LP-facing deliverable before Gabriel review

## Boundaries

- NEVER send LP-facing communications without explicit Gabriel approval (CLAUDE.md AUTONOMOUS OPERATION).
- Capital account math must be deterministic — no [SPECULATIVE] in ledger entries.
- Side letter compliance is checked but never overridden.
- Tax allocations are drafted only with CPA review.

## Dependencies

- portfolio-reporting skill (quarterly metrics)
- document-assembly skill (LP letter templates)
- xlsx skill (capital account schedules)
- docx skill (formal correspondence)
- communication-intelligence skill (LP email drafts)
