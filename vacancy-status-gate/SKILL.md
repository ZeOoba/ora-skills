---
name: "vacancy-status-gate"
description: "Use before any ORA unit is described as available, vacant or quoted to a prospect: reconcile rent roll, lease expiry, AR ledger and Notion tenant record."
---

# Vacancy Status Gate

No 'Available' claim goes to a prospect, broker or listing until these sources agree.

## Procedure
1. Read the live ORA Master Workbook rent roll first (source of record; a mirror more than 7 days behind is stale). Fall back to the newest property rent roll file and state its date.
2. For each unit: tenant of record, lease end, rent, move-in.
3. Check the lease file for the real expiry, holdover, renewal or termination language.
4. Check the AR ledger / delinquency export for open balances on the tenant. Open AR means surrender and possession are unresolved.
5. Check the Notion Tenant database (8dbbaec0) and recent briefs for status notes (notices, move-out, holdover).
6. Compare against any marketing statement (flyer, email, listing). Classify each unit: CLEAR (all agree vacant), CONFLICT (sources disagree), OCCUPIED, or HOLDOVER.
7. Report a table: unit, each source's claim, classification, action. For CONFLICT, name the single question that resolves it (e.g. confirm possession date and keys returned).

## Rules
Read-only. Never edit the rent roll, ledger or Notion. Never state a unit is available externally while it is CONFLICT or HOLDOVER.