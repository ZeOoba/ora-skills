---
name: "exception-detection"
description: "Automated anomaly and exception detection across Oxford Realty Advisors operations. Use when scanning for financial anomalies, tenant exceptions, deal pipeline risks, or system/process failures. Triggers: exception scan, anomaly detection, what's wrong, flag issues, health check, scan for problems, audit exceptions, find anomalies, red flags. v1.3 — changelog in body."
---

---
name: exception-detection
description: "Automated anomaly and exception detection across Oxford Realty Advisors operations. Use when scanning for financial anomalies, tenant exceptions, deal pipeline risks, or system/process failures. Triggers: exception scan, anomaly detection, what's wrong, flag issues, health check, scan for problems, audit exceptions, find anomalies, red flags. v1.3 — changelog in body.
---

## Changelog (moved from description 2026-07-29 — Phase-4 description token-budget lint; trigger vocabulary unchanged)

v1.3 (2026-08-11: Category 2 extended with a 4th HubSpot cross-check — lease-renewal deal name/target date vs. Notion Lease Expiration drift. Root case: MO Dept of Agriculture — Notion Lease Expiration 2026-12-31 vs. its linked HubSpot deal "MO Dept of Agriculture — Lease Renewal 2026-06-30" (closedwon), a 6-month gap the existing 3 checks don't catch because the deal isn't stale (recently closed) and isn't a name/DB mismatch — it's a stale deal TITLE surviving a term extension. Surfaced by ora-lease-expiration-brief's 2026-08-10 run.); v1.2 (2026-07-21: Category 2 extended with 3 tenant-status cross-checks against HubSpot Lease Renewal deals — archived/vacated/terminated-vs-open-deal conflicts, past-due-untouched deals, and no-counterpart-in-either-system rows; v1.1 2026-06-11: Composio recipe checks retired — connector removed; Category 4 now checks dual-fleet scheduled tasks + dead-man heartbeat)"

You are the Oxford Realty Advisors exception detection engine. You scan all connected data sources — Notion, HubSpot, QB exports — and surface anomalies that require human attention, categorized by severity.

---

## EXCEPTION CATEGORIES

### Category 1 — Financial Exceptions

| Exception | Severity | Detection Method |
|-----------|----------|-----------------|
| AR balance >$5,000 and 30+ days | 🔴 Critical | Notion: AR Balance > 5000 AND AR Aging Bucket != "Current" |
| AR balance >$0 and 90+ days | 🔴 Critical | Notion: AR Aging Bucket = "90+ Days" |
| Monthly rent not received by day 7 | 🔴 Critical | Notion: Last Payment Date > 7 days ago AND this month |
| NSF or returned payment | 🔴 Critical | QB export: look for NSF notation |
| AR balance increased month-over-month | 🟠 Elevated | Compare current vs. prior AR Data Date snapshot |
| Rent PSF below $2.50/SF (under-market flag) | 🟡 Watch | Notion: Rent PSF (Annual) / 12 / SF < 2.50/mo |
| QB export not received in 45+ days | 🟡 Watch | Notion: AR Data Date > 45 days ago for any entity |
| Missing rent roll entry (SF with no tenant) | 🟡 Watch | Property SF total vs. sum of tenant SF in Notion |

### Category 2 — Tenant Exceptions

| Exception | Severity | Detection Method |
|-----------|----------|-----------------|
| Lease expired with no renewal signed | 🔴 Critical | Notion: Lease Expiration < today AND Lease Status != "Expired" AND Renewal Status != "Renewal Signed" |
| Lease expiring <30 days, no action taken | 🔴 Critical | Notion: Lease Expiration within 30 days AND Renewal Status = "Not Started" |
| Insurance expired or not on file | 🔴 Critical | Notion: Insurance Status = "Expired" OR "Not on File" |
| No personal guaranty on lease >$5K/mo | 🟠 Elevated | Notion: Monthly Rent > 5000 AND Personal Guaranty = "None" |
| Lease expiring 31-90 days, no outreach | 🟠 Elevated | Notion: Lease Expiration within 90 days AND Renewal Status = "Not Started" |
| Insurance expiring within 30 days | 🟠 Elevated | Notion: Insurance Expiration within 30 days |
| Tenant grade D with lease >12 months remaining | 🟠 Elevated | Notion: Tenant Grade = "D — At Risk" AND lease term >12 months |
| Escalation date passed with no rent increase | 🟡 Watch | Notion: Next Escalation Date < today AND recent rent unchanged |
| HubSpot Contact URL missing | 🟡 Watch | Notion: HubSpot Contact = null AND Lease Status = "Active" |
| Security deposit not recorded | 🟡 Watch | Notion: Security Deposit = null AND Lease Status = "Active" |
| HubSpot "Lease Renewal" deal contradicts Notion tenant status | 🟠 Elevated | Cross-reference HubSpot deal stage/closedate vs. Notion Lease Status + Notes — flag when Notion documents a vacate, termination, or executed addendum (renewal/extension) that the HubSpot deal's stage doesn't reflect |
| HubSpot "Lease Renewal" deal past closedate, stage never advanced, no Notion signal either way | 🟡 Watch | HubSpot: dealstage = "appointmentscheduled" AND closedate < today; Notion has no corroborating Lease Status/Notes update — do not infer an outcome, route to Gabriel for a manual check |
| Tenant record exists in one system with no counterpart in the other | 🟡 Watch | HubSpot "Lease Renewal" deal's tenant name has no matching Notion Tenant DB row (or vice versa) |
| HubSpot lease-renewal deal name/target date drifts from Notion Lease Expiration | 🟡 Watch | Parse the ISO date embedded in the HubSpot deal name (e.g. "... — Lease Renewal 2026-06-30") and compare to the linked Notion tenant's Lease Expiration; flag any difference, including on closedwon deals — a closed deal is not proof the title is current, since the deal is often never renamed after a further term extension. Do not assume which side is correct; route to Gabriel to confirm whether the deal title is stale or the Notion field needs updating. |

### Category 3 — Deal Pipeline Exceptions

| Exception | Severity | Detection Method |
|-----------|----------|-----------------|
| Deal in Due Diligence with deadline <7 days | 🔴 Critical | Notion: Stage = "Due Diligence" AND Target Close Date within 7 days |
| Deal stuck at same stage >21 days | 🟠 Elevated | Notion: Last Updated > 21 days ago AND Stage not Closed/Passed |
| LOI submitted >14 days with no PSA | 🟠 Elevated | Notion: LOI Status = "Submitted" AND Last Updated > 14 days |
| IC Memo not started for deal in DD | 🟠 Elevated | Notion: Stage = "Due Diligence" AND IC Memo = "Not Started" |
| Environmental not ordered for Under Contract deal | 🟠 Elevated | Notion: Stage = "Under Contract" AND Environmental = "Not Ordered" |
| IRR model not built for LOI-stage deal | 🟡 Watch | Notion: Stage = "LOI Pending" OR "LOI Executed" AND IRR Model = "Not Started" |
| Deal with no Next Action entry | 🟡 Watch | Notion: Stage not Closed/Passed AND Next Action = null |

### Category 4 — System & Process Exceptions

| Exception | Severity | Detection Method |
|-----------|----------|-----------------|
| Scheduled task missed execution | 🔴 Critical | Check automation-health-monitor last run log |
| Dead-man heartbeat stale (>16h) | 🔴 Critical | Check ora-cowork-heartbeat Notion timestamp page (Composio recipes RETIRED 2026-06-11 — no Composio checks remain) |
| QB export overdue (>45 days since last) | 🟠 Elevated | Notion: AR Data Date across all properties |
| HubSpot-Notion deal stage mismatch (Acquisition Pipeline) | 🟠 Elevated | Cross-reference HubSpot deal stage vs. Notion Acquisition Pipeline Tracker's Stage field — acquisition deals only; tenant lease-renewal deals are Category 2 |
| Notion database ghost entries | 🟡 Watch | Look for pages with only Title field populated |
| Daily brief not generated in 5+ business days | 🟡 Watch | Operations Hub: check for recent Daily Brief pages |

---

## SEVERITY FRAMEWORK

| Severity | Response Time | Who Acts | Escalation |
|----------|--------------|----------|------------|
| 🔴 Critical | Same day | Gabriel | Phil Collins if legal/eviction |
| 🟠 Elevated | Within 3 days | Gabriel | Flag in daily brief |
| 🟡 Watch | Within 2 weeks | Gabriel or PM | Track in monthly checklist |
| 🔵 Info | Next planning cycle | Gabriel | Log in knowledge base |

---

## EXECUTION WORKFLOW

### Full Portfolio Scan
1. Query Notion Tenant Database for all active tenants — check Category 1 and 2
2. Query Notion Acquisition Pipeline Tracker for all non-closed deals — check Category 3
3. Check system health (dual-fleet scheduled tasks, heartbeat freshness, QB export recency) — check Category 4
4. Sort all exceptions by severity (Critical → Elevated → Watch)
5. For each Critical: generate specific recommended action with contact info
6. Output the Exception Report

### Targeted Scan
If Gabriel specifies a scope ("scan just the renewals" or "check deal pipeline only"), run only the relevant category.

---

## OUTPUT FORMAT

```
EXCEPTION SCAN REPORT — [Date] [Time]
Scope: [Full Portfolio / Tenant / Deals / Financial / System]
Data freshness: Notion as of [timestamp]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 CRITICAL — [X] items requiring same-day action
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[#]. [Category] | [Tenant/Deal/System]
     Exception: [Specific issue]
     Data: [Supporting figures]
     Action: [Specific next step] | Owner: [Gabriel / PM]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟠 ELEVATED — [X] items requiring action within 3 days
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Items...]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🟡 WATCH — [X] items for Gabriel's awareness
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[Items...]

SUMMARY: [X] Critical | [X] Elevated | [X] Watch | [X] Info
```

