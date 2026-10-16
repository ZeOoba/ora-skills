---
name: "lease-renewal-pipeline"
description: "Flag upcoming lease expirations across the portfolio and route renewal-letter drafting through document-assembly. Use when the user mentions upcoming lease expirations, renewal pipeline, which leases are expiring, renewal tracking, expiring leases this quarter, or asks to check/run the lease renewal cycle. Does not itself draft a letter or score tenant risk — see document-assembly and tenant-intelligence. v1.3"
---

## Instructions

Review and manage upcoming lease expirations across the Oxford portfolio.

### Default behavior (no arguments)
Show all leases expiring in the next 6 months.

### With $ARGUMENTS
- A property name → filter to that property
- A timeframe (e.g., "next 90 days", "Q3 2026") → filter to that window
- A tenant name → show that tenant's lease details and renewal status

### Steps

1. **Gather lease data:**
   - **Canonical source:** Notion Tenant Database, queried via the **Notion MCP** (`notion-fetch` / `notion-search`). The former Composio query path (`NOTION_QUERY_DATABASE_WITH_FILTER` against the wrapper ID, with the prefixed-cursor workaround in `references/notion_paginator.py`) is **RETIRED 2026-06-11** — the Composio connector was removed; do not route through it. The paginator is archived under `_archive/lease-renewal-pipeline_pre-notionmcp_2026-06-11/` for history only.
   - **ID routing:** `notion-fetch` and schema introspection → **data source ID** `b12f4cfd-a995-4755-8341-6435ae8173b4` (`collection://b12f4cfd-a995-4755-8341-6435ae8173b4`). Calling `notion-fetch` on the wrapper ID returns `validation_error: "Aggregation property not found in data source"` — a misleading routing quirk, not a data problem (resolved 2026-04-27; see Database ID Map in Knowledge Base). The **database wrapper ID** `8dbbaec0-611a-4617-be07-6a77d0d0307a` remains valid only for browser URLs (`notion.so/{id}`).
   - **Full portfolio scan:** `notion-fetch` on the data source ID, paginating until exhausted; filter client-side on Lease Status. For small targeted lookups (single tenant or property), `notion-search` is sufficient.
   - **Active scope:** Lease Status ∈ {Active, Month-to-Month, Notice Given, Expired}. Exclude Vacant, blank-status stubs, and rows whose Tenant Name contains `⛔` or `DUPLICATE`. Also exclude rows with `Row Retired` checked.
   - **Cross-reference** with rent roll files at `OneDrive\Claude_Workspace\01_Cowork_OS\Cowork_OS_Workspace\` (glob `*rent roll*`, `*lease*`) only when Notion fields are sparse for a given tenant.
   - **Lease-source check (v1.3):** Notion dates and options can trace to a non-canonical copy. Before any renewal terms go to a letter or to Gabriel as fact, confirm the lease against the canonical executed copy using the Notion page `Lease Path Map (Master Lease Database)` (3e96ecd8-9e59-81fe-ad70-fdcd7c2ab885). Read the tenant's `Assignment / Sublet Terms (Lease)` and `Parking Terms (Lease)` source notes: if they say ARCHIVE COPY or unexecuted, mark that tenant's expiration, options and notice period SOURCE UNVERIFIED in the pipeline table. SharePoint search does not index the canonical folders; do not treat "not found in search" as "no lease".

2. **Build the expiration pipeline:**
   - Sort by expiration date (soonest first)
   - For each lease show: tenant, property, unit, SF, current rent, rent/SF, lease start, lease end, renewal options (if any), notice period, and source status (VERIFIED / SOURCE UNVERIFIED)

3. **Flag urgency levels:**
   - **CRITICAL** (red): expires within 60 days, no renewal signed
   - **ACTION NEEDED** (yellow): expires within 120 days, no renewal activity
   - **MONITOR** (green): expires within 180 days, renewal option exists or discussions underway

4. **For CRITICAL and ACTION NEEDED tenants:**
   - Check Outlook/HubSpot for recent communication with the tenant
   - Determine the terms to propose: new term (3-5 years), rent bump (3% annual or market adjustment), key lease terms to update
   - **Renewal letters are standalone formal documents, not email bodies — per CLAUDE.md's Comms drafting tie-break, route drafting to the `document-assembly` skill's templates, never draft letter prose directly in this skill or hand off to `tenant-email`.** Pass `document-assembly` the tenant name, property, the proposed terms above, and the urgency tier, plus the source status so unverified dates are not stated as fact in the letter.
   - Save the resulting draft to the appropriate property folder

5. **Summary output:**
   - Total leases expiring in window
   - Occupied SF at risk
   - Revenue at risk (annual)
   - Recommended actions prioritized by urgency
   - Count of SOURCE UNVERIFIED tenants in the window

### Output Format
Markdown table for the pipeline, followed by draft renewal letters for any critical expirations.

## Changelog

- **v1.3 (2026-09-28):** added the lease-source check to STEP 1 and a source-status column, so renewal terms drawn from Notion are not stated as fact when they trace to an archive or unexecuted copy (archive copies can differ from the canonical Master Lease Database copy). Also excludes `Row Retired` rows from scope. First live case: Bakers Specialty Services, 1100 Rarig Unit K, term ending 10/31/2026, whose Notion terms were read from an archive draft. No detection logic, urgency tier, cadence or handoff behavior changed.
- **v1.2 (2026-09-07):** ORA Automation Audit R23 follow-up — this skill had ZERO trigger phrases in its description, so it could never win a manual, name-based routing decision against tenant-intelligence or document-assembly; only its scheduled-task cron ever ran it. Added trigger vocabulary ("upcoming lease expirations", "renewal pipeline", "expiring leases this quarter", etc.) plus explicit deferrals for drafting (document-assembly) and risk scoring (tenant-intelligence), so it can. No detection logic, cadence, or handoff behavior changed.
- **v1.1 (2026-08-14):** Fixed a live skill-routing collision (ORA Automation Audit Revision 8, `ora-setup-audit`) — Step 4 previously drafted renewal-letter prose directly with no format specified and no reference to CLAUDE.md's ratified comms-drafting tie-break, a silent third path around `document-assembly`/`tenant-email`. Now determines terms only and hands drafting to `document-assembly`, consistent with the tie-break's "tenant-directed formal letters (renewal offers, notices) route to document-assembly" rule. No change to lease-data sourcing or urgency logic.