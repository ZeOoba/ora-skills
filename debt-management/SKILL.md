---
name: debt-management
description: Oxford Realty Advisors debt management and capital-markets skill. Use when the user mentions: refinance, refi, term sheet, lender selection, loan negotiation, DSCR, debt yield, LTV, debt covenant, lender call, prepayment, defeasance, swap, rate cap, hedge, balloon, maturity, loan reserves, lender package, lender comparison, capital stack, recap, mezzanine, preferred equity, or any task related to evaluating, negotiating, or managing the firm's debt. Also trigger when the user uploads a term sheet, loan commitment letter, or lender proposal. v1.2
license: ORA Internal
---

# Debt Management

Manage and optimize ORA's debt portfolio across the loan lifecycle: origination, monitoring, covenant compliance, refinance evaluation, and lender relationships.

## Scope

Covers all debt instruments held by ORA entities: agency loans, life-co loans, bank loans, CMBS, bridge debt, mezzanine, and preferred equity. Excludes personal debt (Gabriel/Eric — see personal-portfolio).

## Triggers

Refinance evaluation, term-sheet redline, lender call prep, covenant test, DSCR/LTV/debt-yield calculation, hedge evaluation, balloon planning, lender RFP, capital-stack restructuring.

## Inputs

- Notion debt schedule (linked from Operations Hub 32b6ecd8)
- Loan documents in SharePoint /Loans/[entity]/
- Term sheets uploaded by user
- Capital-markets benchmarks (10Y Treasury, SOFR, BBB CMBS spreads, life-co spreads)

## Standard Workflows

### Refinance Evaluation
1. Pull current loan terms from Notion debt schedule.
2. Calculate breakeven refi rate including prepay penalty, defeasance, points, legal.
3. Build NPV comparison: hold-current vs. refi-now vs. refi-at-maturity.
4. Survey market: 3+ lender quotes. Use HubSpot lender-relationship database for outreach.
5. Output: refi-decision memo (DOCX, ORA Style) with NPV table, sensitivity to rate moves, and recommended action.

### Term-Sheet Redline
1. Compare against ORA Standard Lender Provisions library (Notion Knowledge Base).
2. Flag any deviation in: prepayment rights, debt-yield/DSCR triggers, recourse scope, reserves, transfer/assumption, springing recourse, environmental indemnity.
3. Produce redline DOCX with comments using legal-intelligence skill conventions.

### Lender Call Prep
1. Pull last 4 quarters of operating data for the property/portfolio.
2. Build covenant compliance summary (DSCR, debt yield, LTV).
3. Surface any operational anomalies (occupancy drops, major capex, tenant departures).
4. Produce 2-page lender brief (DOCX, ORA Style).

### Covenant Test
1. Pull tested covenants from loan documents.
2. Compute current value vs. covenant threshold.
3. Flag any covenant within 10% of breach.
4. Output: compliance memo (DOCX) and Notion update.

## Outputs

- DOCX deliverables follow ORA Institutional Style Guide v1.0+
- File naming: YYYYMMDD_[Property-or-Topic]_[DocType]_[v##].docx
- Mirror to SharePoint /Loans/Analysis/
- Notion update to debt schedule and Operations Hub

## Boundaries

- This skill DRAFTS lender communications. It does not SEND. Outbound to lenders requires Gabriel's explicit approval per CLAUDE.md AUTONOMOUS OPERATION rules.
- Hedge execution (swaps, caps) is never automated — drafts only.
- All redlines are produced as comments/tracked changes; final acceptance is human.

## Dependencies

- legal-intelligence skill (for redline mechanics)
- portfolio-reporting skill (for NOI inputs)
- communication-intelligence skill (for lender email drafts)
- xlsx skill (for sensitivity models)
- docx skill (for memo deliverables)

## Changelog

- v1.2 (2026-07-08): Migrated into `ora-skills` (git-pinned, `package-and-stage-skill`-covered) from the `ora-operations-extensions` plugin. That plugin has no `installed_plugins.json` entry and no local commit pinning — it is Cowork/Connector-platform-managed, not Code-managed — so its runtime-cache copy had zero protection against a silent re-sync revert. This repo copy is now the source of truth. Once installed via Save-skill, remove the old `ora-operations-extensions:debt-management` plugin skill (Settings → Capabilities) to avoid duplicate-skill triggering.
- v1.1 (2026-07-08): Removed stale `ora-debt-maturity-snapshot` / `ora-lender-covenant-tracker` scheduled-task references (root cause of the 2026-07-08 fleet resurrection loop) — fixed directly on the plugin's runtime-cache and Claude_Workspace source-pack copies, prior to this migration.
