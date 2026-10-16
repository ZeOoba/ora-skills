---
name: "tenant-prospect-qa"
description: "Use when a prospective tenant emails questions about a specific ORA unit (panel/power, base-year opex, utilities, term, TI/free rent, tour) and a reply must be drafted from sourced facts."
---

# Tenant Prospect Q&A

Drafts a reply to a prospect's property questions from a per-property fact sheet. Draft only; never send to an external counterparty without explicit in-turn confirmation.

## Procedure
1. Run the vacancy gate (vacancy-status-gate) for every unit named. If rent roll, lease expiry and AR disagree, stop and report the conflict before drafting availability language.
2. Identify the property LLC (signature) and the use. Confirm any use approval on file (Eric's approvals are per-property; an approval for one property does not extend to another). Flag animal, medical, hazmat or high-power uses.
3. Pull facts, in this order, citing source and date inline in the internal notes (not the external draft):
   - Electrical: building systems sheet (Intertek PCA section 2.6, Foust 2020). State service type (amps, voltage, phase) as building-level; make panel space and 240V/208V suitability subject to confirmation at the tour. 120/208V is not 240V; 3-phase 120/240V delta is likely high-leg, so 240V circuits go on the correct legs. New circuits by a licensed electrician with landlord consent.
   - Opex: CAM year-end reconciliation workbook. Base year = calendar year of commencement; quote the latest full year as a reference total, $/SF, and the bay's pro-rata share (bay SF / building GLA). Tenant pays increases over base, assessed the following year.
   - Utilities: electric and gas direct-metered to tenant; water submetered; quote water history if held; never invent per-suite electric/gas figures.
   - Term/concessions: standard 3-5 years with 3% escalations; units leased as-is; TI/free rent only for longer terms and stronger credit unless Gabriel states otherwise. Treat concessions language as a placeholder for his decision.
4. Never attach or quote PCA reports externally; quote only the specific service specs.
5. Produce the draft via the compose card, signed as the property LLC. Close with an internal note: items to verify, conflicts, approvals missing.

## Output
One email draft plus a short internal checklist (not in the email). End with at most 5 workflow-optimization bullets.