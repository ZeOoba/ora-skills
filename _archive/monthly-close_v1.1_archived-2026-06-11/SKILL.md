---
name: monthly-close
description: "Oxford Realty Advisors monthly accounting and operations close process. Encodes the complete 31-item Monthly Checklist workbook across 8 categories. Use when the user mentions: monthly close, month-end, monthly checklist, payment dashboard, QB journal entries, bank reconciliation, lender payments, borrower payments, asset management fees, CAM reconciliation, month-end close, 1st of the month. v1.1"
---

You are executing the Oxford Realty Advisors monthly close process. This skill encodes the complete 31-item Monthly Checklist workbook. Every item has a due date, cross-system verification requirement, and downstream dependency map.

---

## MONTHLY CLOSE OVERVIEW

**Frequency:** Monthly (all items due on the 1st of the month unless explicitly noted as quarterly).
**Quarterly items:** Categories and items marked "quarterly" run only in January, April, July, and October.
**Systems involved:** QuickBooks Desktop (~20 LLC entities), Rent Manager (Columbus/KC/Toledo), Yardi CRC (2 MD properties), Yardi standalone (1 property), AppFolio (Northwood/MD).

---

## CATEGORY 1 — BORROWER PAYMENTS (5 items)

These are payments ORA RECEIVES as lender (Oxford Capital Partners lending program):

| # | Item | Due Date | Source System | Notes |
|---|------|----------|---------------|-------|
| 1.1 | Park National Borrower Payment | 1st | QB / Bank | Verify receipt, post to QB |
| 1.2 | Symetra Borrower Payment | 1st | QB / Bank | Verify receipt, post to QB |
| 1.3 | Banwick/Morrison Loan Payment | 1st | QB / Bank | Track principal/interest split per amortization schedule |
| 1.4 | Any other active borrower loans | 1st | QB / Bank | Check the current active loan schedule in SharePoint (Operations > Loan Schedules); process every active loan listed |
| 1.5 | Accrual-basis interest income entry | 1st | QB | Post accrual if cash not received by end of the 1st business day |

**Verification:** Pull the bank statement for each entity account; confirm deposit matches expected payment schedule. Flag any payment more than 5 calendar days late for Ze review.

---

## CATEGORY 2 — LENDER RECEIPTS (6 items)

These are payments ORA MAKES as borrower (portfolio mortgages):

| # | Item | Due Date | Source System | Notes |
|---|------|----------|---------------|-------|
| 2.1 | Symetra loan payment | 1st | QB / Bank auto-pay | Verify auto-pay executed |
| 2.2 | Park National loan payment | 1st | QB / Bank auto-pay | Verify auto-pay executed |
| 2.3 | Any other active mortgage | 1st | QB / Bank | Check the active mortgage list in SharePoint (Operations > Loan Schedules); confirm each scheduled payment |
| 2.4 | Interest accrual — external loans | 1st | QB | Post accrual only if not already auto-booked by QB |
| 2.5 | Interest accrual — intercompany loans | 1st | QB | Post at the blended rate documented in the most recent intercompany loan agreement |
| 2.6 | Loan covenant tracking | Monthly, 1st | QB / Notes | Flag any covenant violation OR any covenant within 10% of its trigger threshold |

**Verification:** Match QB loan liability balances to amortization schedules. Alert Ze if any loan has a balloon payment within 90 calendar days.

---

## CATEGORY 3 — ASSET MANAGEMENT FEES (3 items, QUARTERLY: Jan/Apr/Jul/Oct)

| # | Item | Due Date | Source System | Notes |
|---|------|----------|---------------|-------|
| 3.1 | Oxford Capital Partners → property entities | Quarterly, 1st | QB | Fee per the current management agreement |
| 3.2 | ORA LLC management fee | Quarterly, 1st | QB | Fee per the current management agreement |
| 3.3 | Asset mgmt fee accrual (non-quarterly months only) | Monthly, 1st (Feb/Mar/May/Jun/Aug/Sep/Nov/Dec) | QB | Accrue exactly one-third of the most recent quarterly fee |

**Verification:** Confirm fee calculation against current AUM and property value (use the most recent quarterly property values from the Portfolio Tracker in Notion). Verify intercompany eliminations are set up correctly.

---

## CATEGORY 4 — QUICKBOOKS JOURNAL ENTRIES (11 items)

One JE per property entity. Each month:

| # | Property Entity | PM Platform | Key Entries |
|---|----------------|-------------|-------------|
| 4.1 | [Property 1] | Rent Manager | Revenue, expenses, depreciation |
| 4.2 | [Property 2] | Rent Manager | Revenue, expenses, depreciation |
| 4.3 | [Property 3] | Yardi CRC | Revenue, expenses, depreciation |
| 4.4 | [Property 4] | Yardi standalone | Revenue, expenses, depreciation |
| 4.5 | [Property 5] | AppFolio | Revenue, expenses, depreciation |
| 4.6–4.11 | [Remaining 6 entities] | As assigned in the Entity-Platform Mapping sheet | Revenue, expenses, depreciation |

The placeholders `[Property 1]` through `[Remaining 6 entities]` above are references to the Entity-Platform Mapping sheet in SharePoint (`Oxford Realty Advisors > Operations > Entity Platform Mapping.xlsx`). Pull the live mapping at runtime and substitute actual entity names — do not emit placeholder text in output.

**For each entity JE, execute these six sub-steps in order:**
1. Pull P&L from the assigned PM platform (export CSV).
2. Map revenue lines: base rent, CAM reimbursements, late fees, other income.
3. Map expense lines: repairs & maintenance, insurance, taxes, utilities, management fees, professional fees.
4. Post depreciation (building and improvements per the fixed asset schedule in QB).
5. Reconcile ending cash to bank statement.
6. Compare current month against prior month. Flag any expense or revenue line with a month-over-month change greater than 10% in absolute value that does not have a documented explanation in the entity's operations notes.

**Source:** QB Desktop exports from SharePoint QB Exports folder, using file naming `QB_PL_[EntityName]_[YYYYMM].csv` format.

---

## CATEGORY 5 — RECONCILIATIONS (2 items)

| # | Item | Due Date | Notes |
|---|------|----------|-------|
| 5.1 | Oxford South Club Solar reconciliation | 1st | Solar income → Oxford entity; verify against utility statement |
| 5.2 | 1851 South Club Solar reconciliation | 1st | Solar income → 1851 entity; verify against utility statement |

**Process:** Compare solar generation report to revenue posted in QB. Flag any month where generation is more than 15% below the prior year's same calendar month (potential panel issue).

---

## CATEGORY 6 — HUBSPOT TASKS (2 items)

| # | Item | Due Date | Notes |
|---|------|----------|-------|
| 6.1 | Escalation queue review | 1st | Review all open HubSpot tickets; close resolved tickets, escalate any ticket older than 14 calendar days without a response |
| 6.2 | Lease expiration pipeline update | 1st | Move any lease with expiration within 180 calendar days to the "Approaching" stage; verify renewal status |

**Process:** Use HubSpot MCP to pull all open deals in the Tenant Renewal Pipeline. Identify any tenant with lease expiring within 180 calendar days not yet in the pipeline and add them. Flag any tenant at "Month-to-Month" stage who has been in that stage for more than 60 calendar days.

---

## CATEGORY 7 — TENANT COMMUNICATION (2 items)

| # | Item | Due Date | Notes |
|---|------|----------|-------|
| 7.1 | Delinquency communications | 1st | Run delinquency report; draft notices per the escalation ladder below |
| 7.2 | Renewal outreach | 1st | Draft renewal offers for leases expiring in 90 to 180 calendar days |

**Delinquency Escalation Ladder (exact day counts):**
- Day 3 past due: Friendly reminder (document-assembly Template 8)
- Day 10 past due: Formal notice with late fee calculation (document-assembly Template 9)
- Day 30 past due: Demand letter with cure period per lease (document-assembly Template 10)
- Day 45 or later past due: Attorney referral packet (document-assembly Template 11) — requires Ze approval before sending

All delinquency notices are drafted only. None is sent without Ze's explicit approval, regardless of the day count.

**Verification:** Pull AR aging from each PM platform; cross-reference with HubSpot; flag any discrepancy greater than $100 between platforms.

---

## CATEGORY 8 — WORKFLOW GAPS (8 items)

These are items flagged for improvement but currently manual. Include them in the monthly close checklist as "open improvement items" — do not attempt to execute the target state until the target-state infrastructure is built.

| # | Item | Current Process | Target State |
|---|------|----------------|--------------|
| 8.1 | COI auditing | Manual spreadsheet check | Automated expiration alerts via Zapier |
| 8.2 | Lease expiration pipeline | HubSpot manual | Zapier automation from Notion DB |
| 8.3 | CAM accrual review | Manual QB entry | Template journal entry |
| 8.4 | Rent roll reconciliation | Manual cross-check | Automated via PM platform export |
| 8.5 | Vendor invoice cycle | Manual approval | HubSpot deal stage workflow |
| 8.6 | Bank reconciliation expansion | Currently 1 entity | All 11 entities monthly |
| 8.7 | Lender covenant tracking | Ad hoc | Monthly covenant check in QB |
| 8.8 | Deal pipeline row in Payment Dashboard | Manual | Auto-populated from HubSpot MCP |

---

## EXECUTION SEQUENCE

When this skill is triggered, execute in this exact order:

### Step 1 — Determine what's due this month
Output exactly:
```
Current month: [MONTH YEAR — e.g., April 2026]
Is this a quarterly month (Jan/Apr/Jul/Oct)? [YES or NO]
Items due: [comma-separated list of applicable item numbers, e.g., 1.1, 1.2, ..., 7.2]
```

Replace each bracketed field with actual values. Do not emit the literal bracket text.

### Step 2 — Generate prioritized checklist
Output a checklist in exactly this format for each item due:
```
☐ [Category#.Item#] — [Item Name]
   System: [specific PM platform, QB entity, or MCP connector]
   Exact steps: [numbered sub-steps, at least 2]
   Downstream if missed: [one sentence describing what breaks]
   Estimated time: [integer minutes]
```

### Step 3 — Check Notion for in-progress status
Use Notion MCP to query Operations Hub for any items already marked complete this month (match by Category# + Item# + current month). Update checklist status accordingly.

### Step 4 — Track completion
As Ze confirms items complete, update checklist with ✅ and an ISO 8601 timestamp. Flag any item not confirmed complete by end of the first business day of the month.

### Step 5 — Post to Notion Operations Hub
Create a page titled exactly "Monthly Close — [MONTH YEAR]" in Notion Operations Hub with:
- Checklist with current status
- Any flagged issues or variances (from Step 2 variance flagging rules above)
- Completion timestamp (ISO 8601)

---

## SCHEDULED TASK BEHAVIOR

When run as "Monthly Close Kickoff" on the 1st of the month at 7:00 AM ET:
1. Generate this month's checklist automatically using the rules above.
2. Post to Notion Operations Hub (Step 5).
3. Create a HubSpot task for Ze titled "Monthly Close Checklist — [MONTH YEAR] — Due: [Date]" with a link to the Notion page; set HubSpot due date to the end of the first business day of the month.
4. If this is January, April, July, or October, include all Category 3 quarterly items in the checklist.
5. Check for any items from last month that were not marked complete in Notion; flag them at the top of this month's checklist under a "Prior Month Incomplete" section.

For scheduled runs: do not wait for confirmation at any step. Execute all five steps and then report completion.

---

## OUTPUT FORMATS
- Checklist: Posted to Notion Operations Hub (via Notion MCP) AND printed inline in Cowork chat
- Journal entry workpapers: XLSX (use xlsx skill)
- Tenant notices: DOCX (use document-assembly skill Templates 8 through 11 as applicable)
- Summary report: Markdown in Cowork chat
