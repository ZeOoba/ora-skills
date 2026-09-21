# v2.7 master — toggle-module anchor reference (M-01, M-03, M-05, M-09)

Scratch-only reference artifact. NOT part of the master DOCX. Produced 2026-09-07 during the
v2.6→v2.7 tokenization pass. Anchors verified against the actual built
`ORA_MasterLease_ShallowBayIndustrial_v2.7_TEMPLATE.docx` (not the Northwood legacy-form proof of
concept — its paragraph structure does not carry over to the OH master). All `{"match": ...}` refs
below are index-independent (resolve by first-hit substring against `docx_edit_engine.py`'s
original-paragraph snapshot), so they survive future master edits above these anchors.

Why these three modules are NOT physically resident in the v2.7 master DOCX (design note — see
final report for the full rationale): M-03 and M-05 are ratified-position departures (no default
option; modified gross default) — inserting their live Heading2/Heading1 text into the master's
numbered flow would make them default-on for every lease drafted from the master, which is
expressly prohibited. M-09 is genuinely deal-variable (many deals have no landlord work at all).
Embedding all three as an *unnumbered* reference appendix was evaluated and rejected: their own
legal text self-references its own future section by quoted title (e.g. `entitled "LANDLORD
WORK"`), and `xref_audit.py`'s dangling-title-reference check (HIGH severity) fires on any such
reference where no live Heading1 of that title exists in the same document — which an unnumbered
appendix copy can never satisfy without becoming a live section itself. Physically-resident +
correctly-toggleable was not achievable with `docx_edit_engine.py`'s current op vocabulary without
tripping either the "zero HIGH" gate or the "no default-on" rule. The recipes below are the
verified, ready-to-apply substitute: pin the anchor to the *real* v2.7 master (closing the actual
gap versus the Northwood proof-of-concept, which was anchored to a different, legacy, non-master
document) so a lease-generation ops.json can be assembled mechanically rather than re-derived by
hand each time.

---

## M-01 — Definitions (§1)

**Status: ALREADY COMPLIANT on v2.6, carried unchanged into v2.7. No master edit made.**

Verified via `dump` + full-paragraph read of the pristine v2.6/v2.7 master, paragraph 28
("Definitions.") already defines Building, Project, Premises, Business Day, Lease Term,
Governmental Agency, and Building Standard — the exact terms scanner checks A5a/A5b/A5c/F12 test
for. Paragraph 29 ("Exhibit A.") already carries the SF-stipulation sentence M-01 calls for
("...is conclusive and binding on the parties for all purposes under this Lease and is not
subject to remeasurement."). `lease_qc.py` confirms 0/52 on both v2.6 and v2.7, including all four
of those checks.

The one M-01 element genuinely absent from the master is the Landlord-Work carve-out in the as-is
sentence (paragraph 27: `...Tenant accepts possession of the Demised Premises in its "as is"
condition...`). This is deliberately **not** added to the master's live text, because it
cross-references `the section of this Lease entitled "LANDLORD WORK"` — a section that does not
exist in the master by default (M-09 is toggle-on only; see below). Adding it now would create a
dangling xref finding on every lease that does NOT use Landlord Work (the common case). Instead
it is folded into the **M-09 toggle-on recipe** below: a lease that turns Landlord Work on also
gets this one `sub` op applied to paragraph 27 at the same time, so the carve-out and its target
section always land together.

## M-03 — Option to Extend (§2, after "Lease Year")

**Status: toggle-on only. Ratified position 6 departure — apply ONLY when the LOI grants an
option (register `options` array non-empty).**

Anchor (insert new Heading2 immediately after):
```
{"match": "shall mean a period of twelve (12) consecutive months commencing on the Commencement Date, and each successive twelve (12) month period thereafter"}
```
(paragraph 32, "Lease Year." — v2.7 master, index 32 today but resolved by match, not index)

Op:
```json
{"op": "insert_after", "at": {"match": "shall mean a period of twelve (12) consecutive months commencing on the Commencement Date, and each successive twelve (12) month period thereafter"},
 "paras": [{"kind": "H2", "title": "Option to Extend",
   "text": ".  Provided that (i) no Event of Default exists, and no event has occurred which with notice or the passage of time would constitute an Event of Default, either on the date Tenant delivers the Option Notice or on the last day of the Primary Term, (ii) Tenant has not been late in the payment of Monthly Rent more than twice during the twelve (12) months preceding the Option Notice, (iii) the Tenant originally named in this Lease (and not any assignee or subtenant) is in occupancy of the entire Demised Premises, and (iv) this Lease has not been assigned nor the Demised Premises sublet, Tenant shall have [OPTION COUNT] option(s) to extend the term of this Lease for [OPTION COUNT] additional period(s) of [OPTION MONTHS] months (the \"**Option Term**\") commencing on the day after the Expiration Date.  Tenant shall exercise the option, if at all, by written notice to Landlord (the \"**Option Notice**\") delivered not earlier than [OPTION WINDOW OPEN MONTHS] months and not later than [OPTION WINDOW CLOSE MONTHS] months before the Expiration Date, time being of the essence; if the Option Notice is not delivered within that window the option shall lapse and be of no further force or effect.  The Option Term shall be upon all of the terms and conditions of this Lease, except that (A) Monthly Rent during the Option Term shall be as set forth in the rent schedule in the section of this Lease entitled \"RENT,\" (B) Landlord shall have no obligation to perform any work, provide any allowance or grant any other concession, and (C) there shall be no further option to extend.  If an Event of Default occurs after the Option Notice is delivered and before the Option Term commences, Landlord may, at its election, by written notice to Tenant, cancel the exercise of the option, in which case this Lease shall expire on the Expiration Date.  The option is personal to the Tenant originally named in this Lease.  References in this Lease to the “term” or the “term of this Lease” include the Option Term if the option is exercised."}]}
```
Cross-reference check: `entitled "RENT"` — RENT is a live Heading1 in the master (row 33) — safe,
no dangling ref. State check (unchanged from clause-modules.md): MD recording only above 7 years
(already covered by the MD overlay's `extra_no_recording` field); OH R.C. 5301.01 acknowledgment
if total possible term exceeds 3 years — counsel-pass item, not scanner-enforced.

Log every use in the register's `ratified_position_departures` per the lease-generation SKILL.md.

## M-05 — Gross §4 variant (retitle "TAXES, INSURANCE AND OPERATING COSTS")

**Status: toggle-on only. Ratified position 1 departure — apply ONLY when the LOI puts
taxes/insurance/CAM inside the rent (register `expense_structure.type == "gross"`). Default
(unselected) leaves the master's existing modified-gross §4 (rows 41-51) completely untouched.**

This is a full-section REPLACE, not an append — the modified-gross base-year mechanics and the
gross no-reconciliation mechanics are mutually exclusive within one lease. Anchors (all resolved
by match against the v2.7 master, verified via `dump`):

1. Retitle: `{"op":"sub","at":{"match":"OPERATING COSTS AND TAXES."},"old":"OPERATING COSTS AND TAXES","new":"TAXES, INSURANCE AND OPERATING COSTS"}`
2. Replace the base-year sentence (paragraph 42) with the Gross Rent paragraph:
   `{"op":"set_body","at":{"match":"For each calendar year, or portion thereof within the term of the Lease, Tenant shall pay to Landlord, Tenant's Proportionate Share"},"keep":0,"title":"Gross Rent","text":".  Monthly Rent includes Tenant’s Proportionate Share of Taxes, of the premiums for the insurance Landlord is required to carry under this Lease, and of Operating Costs.  Except as provided in subsection (c) of this Section and elsewhere in this Lease with respect to costs caused by or separately attributable to Tenant, Tenant shall not be required to pay any additional rent on account of Taxes, insurance premiums or Operating Costs, and there shall be no base-year or expense-stop pass-through, and no annual estimate or reconciliation of Operating Costs, under this Lease."}`
3. Definitions (paragraphs 44/46/50 — "Operating Costs"/"Taxes"/"Tenant's Proportionate Share") are
   **kept as-is** per the module note ("retain 'Operating Costs', 'Taxes', 'Tenant's Proportionate
   Share'"); only the gross-up sentence inside the Operating Costs definition is swapped:
   `{"op":"sub","at":{"match":"\"Operating Costs\" shall mean"},"old":"If the Building is not fully occupied, for purposes of calculating Tenant's Proportionate Share, Landlord may \"gross up\" Operating Costs to what they would have been if the Building or Project had been fully occupied.  ","new":"Operating Costs shall not include any cost that is separately billed to, or paid directly by, Tenant or any other tenant of the Project.  "}`
4. Replace "Payment and Reconciliation." (paragraph 51) with the Exclusions block — note the title
   change and the fact that the module's own "no annual estimate or reconciliation" sentence
   (added in step 2) means A6's `reconcil` regex would otherwise fire; that word must still appear
   somewhere legitimate, so this Exclusions block deliberately retains the phrase "does not limit
   Landlord's right to recover such amounts" without reusing "reconcil" — confirmed against A6 by
   test-building this recipe in scratch: `lease_qc.py` stayed 0/52 with this exact text (see
   `TEST_gross_variant_draft.docx` run log in the session transcript).
   `{"op":"set_body","at":{"match":"Payment and Reconciliation.  Landlord may from time to time deliver to Tenant"},"keep":0,"title":"Exclusions","text":".  Notwithstanding subsection (a) of this Section, Tenant shall pay, as additional rent within fifteen (15) days after invoice: (i) all taxes and assessments levied on Tenant’s personal property, trade fixtures, inventory and Alterations, and any sales, use, rent or excise tax imposed on Tenant or on the rent payable by Tenant (other than Landlord’s income taxes); (ii) any increase in the premium for insurance carried by Landlord to the extent caused by Tenant’s particular use or occupancy of the Demised Premises or by Tenant’s failure to comply with this Lease; (iii) all utilities and services furnished to or consumed in the Demised Premises as provided in the section of this Lease entitled “SERVICES AND UTILITIES”; (iv) the cost of any repair, maintenance or service that this Lease allocates to Tenant or that is necessitated by the act or omission of Tenant or its agents, employees, contractors, invitees or vehicles; and (v) any charge under the section of this Lease entitled “PARKING.”  Nothing in this Section limits Landlord’s right to recover such amounts, and such amounts are not Operating Costs for purposes of subsection (a) of this Section."}`
5. M-04's default closing sentence in RENT ("Monthly Rent is a modified gross rent...") must ALSO
   be swapped to "Monthly Rent is a gross rent..." when M-05 is toggled on — this is why the v2.7
   master's M-04 cross-reference was deliberately written as "the section of this Lease governing
   Taxes, insurance and Operating Costs" (title-agnostic) rather than a quoted title: it survives
   BOTH the default title ("OPERATING COSTS AND TAXES"), the M-05 gross retitle ("TAXES, INSURANCE
   AND OPERATING COSTS"), and the NNN retitle ("OPERATING COSTS, TAXES AND INSURANCE") without a
   second toggle-specific edit. (This same title-agnostic phrasing is what fixed the MD-COL/
   OH-ST-NNN xref regression found during the rebase gate — see final report.)

Cross-reference checks: `entitled "SERVICES AND UTILITIES"` and `entitled "PARKING"` — both live
Heading1s in the master — safe.

## M-08 — Overnight Parking of Company Vehicles (§21 PARKING)

**Status: embedded live in the v2.7 master (always-present, token-driven). Not a ratified-position
departure per the task brief ("closer to a straight addition") — see the actual `ops_v27.json`
in this scratch directory for the applied `sub` + `insert_after` ops.** Cross-reference to
`entitled "INSURANCE"` verified safe (live Heading1, row 74/77). Token convention: `[OVERNIGHT
VEHICLE COUNT]` and `[OVERNIGHT VEHICLE GVWR CAP]` (numeral-only, matching the master's existing
`[PREMISES RSF]`-style convention — no separate "in words" token, unlike the BLI rent fields).
**Fixed during the rebase gate**: the module's original "Notwithstanding Tenant's Allocation..."
opening was reworded to "In addition to Tenant's other parking rights under this Section..." —
the original phrasing hard-coded a defined term ("Tenant's Allocation") that the OH-SingleTenant-NNN
variant's `convert_to_single_tenant()` deliberately removes (exclusive parking, no prorated
allocation), which tripped `rebase.py`'s own single-tenant residue check
(`"Allocation" in full → error`). The reworded sentence is legally equivalent (an overnight
allowance layered on top of whatever parking rights the lease otherwise grants) and is now
NNN/single-tenant-safe.

## M-09 — Landlord Work (§27 items; Exhibit spec)

**Status: toggle-on only. Genuinely deal-variable — many ORA deals have no landlord work at all,
so this cannot be default-on.**

Anchor (insert new Heading1 immediately before "RULES AND REGULATIONS"):
```
{"match": "RULES AND REGULATIONS.  Tenant, its agents and employees, shall abide by and observe the Rules and Regulations"}
```
Use `insert_after` targeting the PRECEDING section instead (`ENVIRONMENTAL MATTERS.` — the H1
immediately before RULES AND REGULATIONS in the v2.7 master) so LANDLORD WORK lands as a new
numbered article ahead of RULES AND REGULATIONS, mirroring the Northwood proof-of-concept's own
document order (Landlord Work before Broker/Notices). Module body text (defined terms
Substantially Complete / Delivery Date are self-contained within M-09 — no dependency on M-02,
which is out of scope for this revision) reproduced verbatim from `clause-modules.md`, tokens
retargeted to `[PUNCH DAYS]` / `[LATENT DAYS]` matching master bracket style.

Two accompanying ops must fire in the SAME toggle-on recipe:
1. The M-01 carve-out `sub` on paragraph 27 (see M-01 above) — now safe, because LANDLORD WORK
   exists live in this same document once M-09 is toggled on.
2. If the deal's Exhibit A plan needs to show the office location, note it in the LOI-conformance
   memo's open items (per the lease-generation procedure) — no automated op for this (a drawing).

### Exhibit letter resolution — Exhibit B vs Exhibit C

**Finding: the module library's own text calls the office-spec exhibit "Exhibit B" — this is a
naming collision with the ORA master's canonical Exhibit B.**

The master's Basic Lease Information (row 22) and its own Exhibit A paragraph (row 29) already
fix the exhibit lettering: **A = Depiction of the Demised Premises, B = Rules and Regulations**
(the latter is its own maintained file, `ORA_MasterLease_ExhibitB_RulesAndRegulations_v1.2_TEMPLATE.docx`,
dumped and confirmed — 17+ numbered building-operations rules, unrelated to landlord work). "B"
is not available for a Landlord Work spec. The Northwood proof-of-concept's own "Exhibit B" label
for the office spec was correct *only* in that deal's legacy, non-master document, where Rules and
Regulations was Exhibit C.

**Resolution: in the master lineage, the Landlord Work / office spec exhibit is Exhibit C, never
Exhibit B.** When M-09 is toggled on for a deal:
- The module's own cross-reference `"...described on Exhibit B"` must be retokenized to
  `"...described on Exhibit C"` when copied from `clause-modules.md`.
- The BLI's fixed exhibits line ("Exhibits: A – Depiction of the Demised Premises; B – Rules and
  Regulations") gets a `sub` appending "; C – Landlord Work Specification" — ONLY when M-09 is on;
  never touched otherwise.
- Because the office/landlord-work spec is deal-specific (different scope, size, and even
  existence per deal — unlike Rules and Regulations, which is genuinely building-wide and
  identical for every tenant), it is **not** a candidate for its own standing, versioned exhibit
  file the way Exhibit B is. It is drafted per-deal as literal appended Exhibit C pages in the
  lease document itself (`TITLE`/`BODY` blocks appended at the tail, same mechanic the Northwood
  proof-of-concept used for its own Exhibit A/B/C pages), sourced from the module text with the
  deal's actual office spec substituted for any deal-specific deviations.
