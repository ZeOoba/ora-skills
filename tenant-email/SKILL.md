---
name: tenant-email
description: Draft a tenant communication email. Use when writing to tenants about renewals, notices, maintenance, rent, or introductions. v1.1 (2026-07-24: fixed missing entity-awareness — every draft signed as plain "Gabriel Goldberg" with no property-LLC lookup, root cause of the recurring Outbox QC Check D defect; now resolves and embeds the property LLC signature block as literal text)
user-invocable: true
allowed-tools: Read Glob Grep WebFetch mcp__c0ea3c01-b8f1-4371-aa06-08a1449f59fc__outlook_email_search mcp__a3e380ce-2ea9-4b42-92d9-37c588a4b760__search_crm_objects
---

## Instructions

Draft a tenant email for $ARGUMENTS.

1. Look up the tenant in HubSpot CRM to get current lease details, contact info, and communication history
2. Check the Oxford Email Templates Library.docx for the matching template category
3. Reference the CLAUDE.md for tenant/property context
4. Resolve the signing entity: every tenant email is landlord-capacity correspondence, and the landlord is the PROPERTY LLC, not the firm. Look up the tenant's property in `Claude_Workspace/00_Governance/References/Voice/ORA_Property-LLC-Signature-Roster_v01.md` to get the exact LLC name (VERIFIED vs PENDING status — never invent a legal name for a PENDING entity; use it as-is for informal mail only, per Hard Invariant 7).
5. Draft the email with:
   - Professional but approachable tone
   - Specific lease terms referenced (rent, expiration, escalation)
   - Clear call to action
   - Signature block, embedded as literal text in the draft body (do NOT rely on Outlook's Insert Signature picker or its default-signature-on-new-message setting — that recurring gap is the Outbox QC Check D defect):
     ```
     [Property LLC Name], by Oxford Realty Advisors LLC, its Manager
     Gabriel Goldberg, Principal
     ggoldberg@oxfordra.net | 301-512-6125
     ```
   - If the draft is later opened/finished in Outlook and a generic default signature auto-populates on top of this block, delete the auto-inserted one before send — the block above is the one that must remain.
6. If this is a renewal notice, reference the lease expiration date and proposed new terms
7. If this is a welcome letter for a new acquisition, include property management contact info and rent payment instructions
