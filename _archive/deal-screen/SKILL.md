---
name: deal-screen
description: Screen a new deal from Crexi, LoopNet, or a broker email. Quick go/no-go with scoring.
user-invocable: true
allowed-tools: Read Glob Grep Write WebSearch WebFetch mcp__a3e380ce-2ea9-4b42-92d9-37c588a4b760__search_crm_objects mcp__c5f4869f-7d3a-4472-a66a-8e61315feb51__notion-search
---

## Instructions

Screen the deal described in $ARGUMENTS against Oxford's acquisition criteria.

1. Extract key metrics: location, SF, price, price/SF, in-place NOI, cap rate, tenant count, building type/year
2. Score against the Oxford Acquisition Scorecard (18 weighted criteria):
   - Product type (shallow bay flex/warehouse preferred)
   - Geography (Mid-Atlantic, Ohio, Midwest)
   - Size (10K–100K SF buildings)
   - Multi-tenant (preferred over single-tenant)
   - Price point, cap rate, replacement cost basis
3. Check HubSpot for any existing relationship with the broker or property
4. Check Notion Deal Sourcing Log for duplicates
5. Output a quick verdict:
   - **PASS** → Add to Notion Deal Sourcing Log, note next steps
   - **REVIEW** → Flag specific concerns, recommend deeper look
   - **SKIP** → Brief reason why it doesn't fit
6. If PASS, estimate a back-of-envelope IRR range
