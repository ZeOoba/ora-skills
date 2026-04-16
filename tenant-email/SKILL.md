---
name: tenant-email
description: Draft a tenant communication email. Use when writing to tenants about renewals, notices, maintenance, rent, or introductions.
user-invocable: true
allowed-tools: Read Glob Grep WebFetch mcp__c0ea3c01-b8f1-4371-aa06-08a1449f59fc__outlook_email_search mcp__a3e380ce-2ea9-4b42-92d9-37c588a4b760__search_crm_objects
---

## Instructions

Draft a tenant email for $ARGUMENTS.

1. Look up the tenant in HubSpot CRM to get current lease details, contact info, and communication history
2. Check the Oxford Email Templates Library.docx for the matching template category
3. Reference the CLAUDE.md for tenant/property context
4. Draft the email with:
   - Professional but approachable tone
   - Specific lease terms referenced (rent, expiration, escalation)
   - Clear call to action
   - Gabriel Goldberg signature block (ggoldberg@oxfordra.net | 301-512-6125)
5. If this is a renewal notice, reference the lease expiration date and proposed new terms
6. If this is a welcome letter for a new acquisition, include property management contact info and rent payment instructions
