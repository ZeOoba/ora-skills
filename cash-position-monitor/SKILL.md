---
name: cash-position-monitor
description: "Use when the user mentions: cash position, cash balance, treasury, reserve adequacy, distribution headroom, cash forecast, weekly cash, daily cash, intercompany, sweep account, cash concentration, debt service coverage of cash, or any task requiring real-time consolidated cash visibility — multi-entity cash position consolidation across QuickBooks accounts. The scheduled Monday snapshot runs inside the ora-am-brief task (Block D); this skill is the on-demand path."
license: ORA Internal
---

# Cash Position Monitor (v1.1)

Produce consolidated multi-entity cash position views with reserve adequacy checks and distribution headroom calculations.

## Scope

All ORA entities: holding company, property-level SPVs, manager entity. Includes operating, capex, lender-required, and LP-distribution accounts. Excludes Gabriel/Eric personal accounts (see personal-portfolio).

## Triggers

Daily/weekly cash snapshot, reserve adequacy check, distribution decision, refi cash analysis, capital call timing, vendor payment timing, intercompany sweep.

## Inputs

- QuickBooks (cash-flow-quickbooks-account, profit-loss-quickbooks-account) — balances by account
- Notion Operations Hub — reserve policy floors, distribution policy
- Notion debt schedule — upcoming debt service obligations
- LP database — pending capital calls, scheduled distributions
- Vendor payable aging (QuickBooks A/P)

## Standard Workflows

### Weekly Snapshot

The scheduled run is Block D of the `ora-am-brief` task (Mondays). That task spec is authoritative for the scheduled run; the steps below are the on-demand version. The former standalone `ora-cash-position-snapshot` task no longer exists.
1. Pull current balances by account, by entity.
2. Compute consolidated total.
3. Compute operating reserve adequacy: cash − payables vs. policy floor.
4. Compute distribution headroom: cash − (next 30-day debt service + reserve floors + payables).
5. Compute week-over-week delta.
6. Flag: any reserve below floor (ALERT), any week-over-week drop > 10% (WARN).
7. Update ora-cash-position artifact.
8. Email Gabriel only (ggoldberg@oxfordra.net). Scheduled and automated outputs never cc Eric; the Daily Brief is the sole exception.

### Distribution Decision Support
1. Pull current cash and outflows for next 90 days.
2. Apply waterfall to compute distributable cash by LP.
3. Stress test: 90-day cash position post-distribution.
4. Output: distribution decision memo (DOCX) with sensitivity to occupancy and tenant payment timing.

### Refi Cash Analysis
1. For a refi candidate, model: closing-day cash impact (prepay penalty, points, reserves, return of equity).
2. Quantify: cash freed for redeployment vs. cash consumed by closing costs.
3. Output: cash impact section of debt-management refi memo.

### Capital Call Timing
1. For an upcoming acquisition, identify cash gap.
2. Stagger call timing to minimize idle LP cash.
3. Output: capital call schedule (xlsx).

## Outputs

- xlsx cash position workbook (entity-level, consolidated, trend)
- DOCX cash memos for distribution and refi decisions
- ora-cash-position artifact refresh
- Notion Operations Hub cash page update
- File naming: YYYYMMDD_Cash-Position_[period]_v##.xlsx

## Boundaries

- This skill READS cash data; it does not move money. Per CLAUDE.md, no actual transfers, ACH, or wires are executed.
- Distribution recommendations are advisory; Gabriel approves all distributions.
- All forecasts beyond 30 days marked [FORECAST].

## Dependencies

- portfolio-reporting skill (NOI inputs)
- xlsx skill (cash schedules)
- docx skill (decision memos)
- ~~investor-relations skill (distribution waterfall)~~ — retired 2026-09-09, no replacement assigned

## Changelog

- **v1.1 (2026-11-05):** The description and the Weekly Snapshot section said this skill powers `ora-cash-position-snapshot`. That task is not on either fleet; its work was folded into `ora-am-brief` Block D (Mondays). Both now point there. Step 8 said "Email Gabriel + Eric", which contradicted the email routing rule (scheduled outputs go to ggoldberg@ only; the Daily Brief cc is the sole exception) and the Block D spec ("Email to Gabriel (only)"); it now says Gabriel only. Whether to retire this skill is still open (catalog review F7). No scored or governor constant changed.
- **v1.0:** initial.
