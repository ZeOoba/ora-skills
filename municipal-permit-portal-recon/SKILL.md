---
name: "municipal-permit-portal-recon"
description: "Use when diligencing a property's permits and certificates of occupancy: pull the Auditor permit list and county permit portal, reconcile, flag gaps, and build the register."
---

# Municipal Permit Portal Recon

Purpose: for a target address, build a complete permit, inspection, certificate-of-occupancy and completed-work record from the County Auditor permit history plus the county permit portal, reconcile the two, flag gaps, and load the register into the DD Tracker. Companion to municipal-record-recon (parcels, deeds, PD/zoning, public-records requests); use that skill for title/zoning and this one for permits.

## Invariants
- Read-only research. Never send a records request, Seller request or any external message without explicit in-turn confirmation. Save drafts to /outputs/ first.
- Never fabricate permit numbers, dates, valuations or inspection results. Quote only what was opened. Mark inferred links [inferred].
- Absence from every source is evidence of no permit, not proof. State coverage limits in every report.
- Active confidential deals are not named externally; requests name the Property and parcel only.

## Procedure
1. **Parcel and Auditor.** Get the PARID and any prior parcel numbers. Pull the Auditor property profile permit-history table verbatim (number, date, type, valuation) and record the data-currency date. This is the pre-portal index and the source of renovation entries on PCA intake forms.
2. **Portal coverage.** Find the portal (Tyler EnerGov Permit Central, Accela, etc.) and read its stated coverage start on the county page. Clermont County OH: Building Inspection and Public Health records from Jan 2019. Do not assume earlier coverage; pre-coverage conversions appear as legacy records with default dates (e.g. applied 1/1/2019).
3. **Search the portal (Chrome).** Public view, no login. Search by PARCEL first, then ADDRESS in the county format (Clermont: "754 OLD SR 74", not "754 Old State Route 74"). Type searches in the UI; hash-URL navigation does not run searches. Select-all and clear the box before each query (text is retained). Owner and contractor names are not indexed. Parcel and address searches should return the same set; if not, resolve why.
4. **Open every permit.** Tabs: Summary, Locations, Fees, Reviews, Inspections, Attachments, Contacts, Sub-Records, More Info. "More Info" holds scope, code edition, occupancy and certificate dates. ?tab= URL params do not re-render: click the tab with JS (return only 'clicked'), then get_page_text. If a JS result is blocked as cookie/query-string data, use JS only to click. Capture permit GUIDs from read_page/href if needed. get_page_text may return only the first loaded section: use read_page.
5. **Inspections.** Result rows rarely show the parent permit: map by date and discipline, mark [inferred].
6. **Reconcile** in the register's Source_Check tab: each permit Both / Auditor / Portal. Expect the Auditor list to omit expired permits and signs and the portal to omit pre-coverage permits; the union is the register.
7. **Completed work outside permits.** From invoices, proposals, inspection reports and zoning letters in the deal folder: roofs (date stamps, warranties), rooftop units, water heaters, fire/sprinkler, tenant work.
8. **Flags.** Expired permit with no final; occupancy permit without CO; occupied suite with no CO; major work with no permit; construction-type or suite-name inconsistencies; no fire/sprinkler records; code-enforcement and municipal-court search.
9. **Deliver.** Fill ORA_PermitCORegister template (Permit_CO_Register tab to the DD Tracker); write the Word report per the ORA Style Guide with the 16-pt QC gate; fonts via ora-brand-fonts.
10. **Follow-through (drafts, not sends).** Standing Seller request at PSA execution; Carlisle or other manufacturer warranty request through the owner of record; pre-coverage paper-file request to the county Building Department under current and prior parcels. Schedule portal re-pulls before Feasibility expiry and 2-3 days pre-closing; compare to the saved baseline counts.

## Deliverable
Word report: bottom line; permit register; portal detail per permit; inspection log; completed work outside the permit record; gaps and actions with owner and date tied to PSA sections; sources and limits. Reference implementation: 754 Old State Route 74, 10/16/2026 (15 permits, 14 inspections, no roofing permit).

## Workflow-optimization bullets
End substantive sessions with at most 5 bullets of systematization candidates.