---
name: lease-renewal-pipeline
description: Flag upcoming lease expirations across the portfolio and draft renewal templates.
user-invocable: true
allowed-tools: Read Glob Grep Write WebSearch WebFetch mcp__c5f4869f-7d3a-4472-a66a-8e61315feb51__notion-search mcp__c5f4869f-7d3a-4472-a66a-8e61315feb51__notion-fetch mcp__a3e380ce-2ea9-4b42-92d9-37c588a4b760__search_crm_objects mcp__c0ea3c01-b8f1-4371-aa06-08a1449f59fc__outlook_email_search
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
   - Search Notion for the tenant/lease database
   - Check local files in the Cowork OS folder for rent rolls, lease abstracts
   - Cross-reference with any Excel rent roll files (glob for `*rent roll*`, `*lease*`)

2. **Build the expiration pipeline:**
   - Sort by expiration date (soonest first)
   - For each lease show: tenant, property, unit, SF, current rent, rent/SF, lease start, lease end, renewal options (if any), notice period

3. **Flag urgency levels:**
   - **CRITICAL** (red): expires within 60 days, no renewal signed
   - **ACTION NEEDED** (yellow): expires within 120 days, no renewal activity
   - **MONITOR** (green): expires within 180 days, renewal option exists or discussions underway

4. **For CRITICAL and ACTION NEEDED tenants:**
   - Check Outlook/HubSpot for recent communication with the tenant
   - Draft a renewal letter template with:
     - Proposed new term (3-5 years)
     - Proposed rent bump (3% annual or market adjustment)
     - Key lease terms to update
   - Save drafts to the appropriate property folder

5. **Summary output:**
   - Total leases expiring in window
   - Occupied SF at risk
   - Revenue at risk (annual)
   - Recommended actions prioritized by urgency

### Output Format
Markdown table for the pipeline, followed by draft renewal letters for any critical expirations.
