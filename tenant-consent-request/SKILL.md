---
name: "tenant-consent-request"
description: "Use when a tenant asks to sublet, share space, add an occupant, assign, or change use or parking; drives lease-clause analysis and a consent-request reply. Feeds tenant-email for drafting."
---

# Tenant Consent Request (ORA)

Purpose: turn an inbound tenant request that touches the assignment/sublet, use, or parking clauses into (1) a lease-grounded analysis and (2) a draft reply that opens a formal consent request without conceding anything. Drafting mechanics, signature block and Property-LLC resolution belong to `tenant-email`; this skill supplies the analysis and the content. Draft only. Any outbound send to a tenant or third party needs Gabriel's in-turn confirmation.

## Triggers
sublease, sublet, shared operations, share space, additional occupant, co-tenant, license to use, assign the lease, change of use, add a subcontractor or affiliate to the premises, extra parking, "what fee applies", "does this need landlord approval".

## Routing note
Inbound requests often reach ORA as a forward from the third-party property manager (e.g., Peak Real Estate Partners). The manager is asking how to proceed; the reply goes to the manager with tenant-ready text to relay, unless Gabriel says otherwise. Do not assume the tenant is the addressee. Standing ask to the manager: forward the request with the suite, lease dates, and rent/insurance standing, and hold all responses on consent, fees and parking until ORA replies.

## Procedure
1. Identify tenant, suite, property, landlord entity. Source of record: Notion Tenant Database (8dbbaec0) row, then HubSpot (current tenants only). Never fabricate tenant or lease facts. Read the Tenant row's `Parking Terms (Lease)` and `Assignment / Sublet Terms (Lease)` fields first; they are a shortcut, not a substitute for step 3, and they carry their own source/verification note.
2. Locate the lease text (SharePoint search by tenant + property). Check whether the copy is EXECUTED. Archive copies with a blank execution date are drafts: cite clause numbers only after confirming the executed text matches, and say so in the output.
3. Read these clauses in full and quote operative language: Use; Assignment/Subletting/Encumbering; Insurance (limits, additional insured); Parking (allocation formula, landlord designation right, vehicle storage/repair prohibitions); Signage; Rules & Regulations; Notices; guarantor/joint-and-several language.
4. Classify the request. Check whether the assignment clause defines "sublet" to include permitting occupancy or use by another party, and whether it covers "otherwise transfer". A request labeled "shared operations" or "license" is treated as a sublet request if the clause language reaches it.
5. Extract fee and cost terms exactly: admin fee amount, whether per request, whether payable at time of request, whether owed if denied, and any cost/attorney-fee reimbursement as additional rent. Do not confirm or waive a fee the tenant characterizes; restate what the lease says.
6. Parking: compute the allocation from the lease formula (tenant RSF / project RSF), state that occupant spaces come out of the tenant's allocation, and flag any vehicle storage/maintenance/service restrictions. If the project space count is unknown, say so rather than estimating.
7. Property-level checks from the Notion Property Register row: (a) lender: read Lender, Active Loan Count and the Notes; if the row is stale or silent, mark lender consent UNVERIFIED and name the loan documents to check; (b) zoning: read the Zoning field and Notes; if the requested use (dispatch, transport, added occupant) is not a listed use or no zoning verification letter is on file, flag it before any consent is recommended. Keep zoning and lender findings internal; do not put them in the manager/tenant reply.
8. Flag remaining unknowns: executed-lease status, project space count, tenant standing (rent current, COI current), Property-LLC roster verification status.
9. Draft the reply. Required elements: no occupancy until written consent; sole-discretion standard as written; fee and cost reimbursement as written; information package request; parking answer (not confirmed, with the clause basis); statement that consent, if given, will be a written consent/occupancy agreement signed by tenant and occupant with tenant remaining fully liable; non-waiver sentence. Information package: exact SF and location, hours, headcount; occupant legal name, state, principals; evidence of underlying contract and subcontract (pricing redactable); COI meeting the lease insurance section naming landlord entity and manager as additional insureds; vehicle count/type and overnight staging; the fee.
10. Signature block (literal text): `[Property LLC], by Oxford Realty Advisors LLC, its Manager / Gabriel Goldberg, VP Acquisitions / ggoldberg@oxfordra.net | 301-512-6125`. Use the exact LLC from the Property-LLC roster; if the roster cannot be found, use the landlord name from the lease and say it is unverified.
11. Log the request: create or update a row in the Notion `Tenant Requests` database (Ops Hub > Databases; data source 3f62fde8-72e4-4421-97c7-5cc7b8d5c062). Set Tenant (relation), Property, Request Type, Status, Date Received, Source, Lease Clause Basis, the three checkboxes (Admin Fee Received, COI Received, Info Package Complete), Lender Consent Needed, Next Action, Notes. Update Status as the request moves (Received > Info Requested > Under Review > Consent Granted / Consent Denied / Withdrawn > Closed). Never mark Consent Granted without Gabriel's in-turn instruction.
12. Close with a short decision list for Gabriel (consideration beyond fee and costs; consent conditions) and label speculation [SPECULATIVE]. Recommended default posture: process as a conditional consent, do not refuse outright, do not concede parking or fee interpretation.

## Output
One message: bottom-line recommendation; lease-clause findings (clause number + operative language); draft reply; not-verified list; decisions for Gabriel; link to the Tenant Requests row. Institutional register, no filler. If Outlook draft creation is unavailable (the M365 connector may hold read-only mail scopes), deliver the draft as a file and say why.

## Do not
- Do not confirm parking counts, waive fees, or signal approval.
- Do not describe an unsigned lease draft as the operative lease.
- Do not send. Drafts go to Gabriel; outbound counterparty sends need explicit confirmation.