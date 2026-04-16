---
name: market-comp-analyzer
description: Pull market comps and build a structured comparison for acquisition candidates.
user-invocable: true
allowed-tools: Read Glob Grep Write WebSearch WebFetch mcp__Apify__apify-slash-rag-web-browser mcp__Apify__call-actor mcp__Apify__search-actors mcp__c5f4869f-7d3a-4472-a66a-8e61315feb51__notion-search mcp__a3e380ce-2ea9-4b42-92d9-37c588a4b760__search_crm_objects
---

## Instructions

Build a structured market comp analysis for the property or market described in $ARGUMENTS.

### Input
The user will provide: an address, a market/submarket name, or a deal name from the active pipeline.

### Steps

1. **Define the comp set parameters:**
   - Property type: match the subject (default: shallow bay flex/warehouse)
   - Geography: 5-mile radius from subject (or same submarket)
   - Size: +/- 50% of subject SF
   - Timeframe: sales within last 24 months

2. **Research comps via web search:**
   - Search CoStar, Crexi, LoopNet, and local broker sites for recent sales
   - For each comp gather: address, sale date, sale price, price/SF, cap rate, SF, year built, occupancy at sale, buyer, seller, broker
   - Target 5-8 comparable sales

3. **Research lease comps:**
   - Search for recent lease transactions in the submarket
   - Gather: tenant, address, SF leased, rent/SF (NNN vs gross), lease term, TI allowance, free rent
   - Target 5-8 lease comps

4. **Market context:**
   - Submarket vacancy rate and trend
   - Average asking rent and rent growth
   - New construction pipeline (deliveries next 12-24 months)
   - Major employers and economic drivers
   - Population/job growth trends

5. **Build the comp grid:**
   - Sale comps table sorted by relevance to subject
   - Lease comps table sorted by date
   - Adjustments narrative: explain why subject should trade above/below the comp average

6. **Valuation bracket:**
   - Low / mid / high price/SF based on comps
   - Implied value range for the subject
   - Recommended offer range

7. **Output:**
   - Save as `[Address] Market Comps [MM-YYYY].html` in the deal folder
   - Display summary in chat

### Comp Quality Notes
- Prioritize flex/warehouse over pure office or retail comps
- Prefer multi-tenant over single-tenant comps
- Note any comps that are portfolio sales (price/SF may be distorted)
- Flag comps older than 18 months as potentially stale
