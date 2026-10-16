---
name: "municipal-record-recon"
description: "Use to find PD agreements, site plans, use restrictions or title history for a US parcel: assessor parcel lookup, deed chain, Land Evidence sweep, then an APRA/public-records request draft."
---

# Municipal Record Recon

Purpose: for a target address, identify parcels, walk the recorded chain, find recorded use restrictions and PD/zoning approvals, and, where the governing instrument is not in land evidence, draft and track a public-records request. Output leads with parcel identifiers.

## Invariants
- Never send the public-records request to the municipality without explicit in-turn confirmation (outbound counterparty send).
- Never fabricate Book/Page, instrument numbers or quoted text. Quote only what was read; mark unread pages as unread.
- Active confidential deals must not be named on external surfaces (the records request should name the parcel, not ORA's deal interest).
- Save the outbound draft to /outputs/ and Notion BEFORE attempting to send, so a context reset cannot lose it.

## Procedure
1. **Parcel.** Query the municipal assessor (Vision / actDataScout / local GIS). Capture Plat/Lot, PID, address, acres, use code, zoning per land line, owner and mailing address, assessment, and the deed Book/Page table. Check companion lots under the same owner. Note assessor artifacts (for example identical acreage shortfalls on split-zone lines) and do not treat them as facts.
2. **Deed chain.** Walk the Book/Page table backward. Read each instrument image for: exceptions and encumbrances, PD / zoning references, easements, restrictions, consolidations.
3. **Land Evidence sweep** (SearchIQS or county equivalent). Search by Book/Page, each grantor/grantee name, and description types: ZONING DECISION, RESOLUTION, SITE PLAN, DECLARATIONS AND RESTRICTIONS, ENVIRONMENTAL LAND USAGE RESTRICTION, EASEMENT, AGREEMENT. Read each hit in full: adjacent pages are continuation pages.
4. **Non-recorded approvals.** If the PD master agreement or conditions of approval are not recorded, identify the custodian: Planning Dept, Town Council, Planning Board, Zoning Board, Town Clerk. Collect contact emails and phone.
5. **Records request.** Draft under the state public-records statute (RI: R.I.G.L. 38-2-1 et seq., 10 business days under 38-2-7(b), extendable 20 business days for good cause). List the records by category, ask for electronic copies, segregable release, fee notice, acknowledgment and response date, and referral if held by another office. Compute dates with a business-day calculator excluding state holidays (RI: Columbus Day; check Election Day and Veterans Day) and flag the holiday assumption.
6. **Persist.** Save the draft and the sent copy in /outputs/YYYY-MM-DD_[Topic]_[DocType]_v##.ext. Add a row to Notion Critical Deadlines Tracker (Category Regulatory) for the statutory date and the extended outer date. Add an entry to the Knowledge Base Entries database (Category Legal & Compliance).
7. **Send** only on in-turn confirmation, through the approved send path. If the connector lacks Mail.Send, use Outlook on the web in Chrome once the user has signed in; never enter credentials.

## Browser constraints (SearchIQS)
- Guest access needs a manual guest-button click by the user.
- Never navigate to viewer or result URLs by address bar: it logs the guest session out. Use the in-page search form and JS clicks on the ASP.NET postback buttons.
- Viewer frequently freezes: wait 10 s and retry.
- Outlook on the web: a compose deep link pre-fills To and Subject; Cc and body must be typed. Typing a numbered list into the body auto-numbers: type list items without the numerals.

## Deliverable format
1. Parcel table (Plat/Lot, PID, address, acres, use, owner)
2. Deed chain (Book/Page, date, parties, PD/restriction finding)
3. Recorded use restrictions with Book/Page, instrument number and what was and was not read
4. PD status and custodian contacts
5. Request status with dated deadlines
6. At most 5 workflow-optimization bullets