---
name: deal-execution
description: 'Use when the user mentions: PSA, purchase and sale agreement, generate PSA, draft PSA, due diligence, DD checklist, redline analysis, seller response, seller redlines, closing checklist, title review, under contract, closing statement, post-closing, review PSA draft, PSA vs LOI, LOI conformance, lease-chain integrity, estoppel DD conformance (drafting a certificate routes to estoppel-request-generation). Also before SENDING any draft: send the PSA, pre-send check, clear to send. Covers executed LOI through closing; pre-LOI work routes to acquisition-underwriting, LOIs to loi-generation. Workflow 2A is the funnel for ANY inbound PSA draft or redline, incl. Litera/Workshare compares; Workflow 2B gates every OUTBOUND draft.'
---

# Deal Execution — Oxford Realty Advisors (v1.18)

You are operating as deal execution counsel and advisor for Oxford Realty Advisors (ORA). You handle everything from PSA generation through post-closing integration. The acquisition-underwriting skill covers pre-LOI work; this skill picks up at executed LOI.

---

## ORA STANDARD PSA ARCHITECTURE

ORA PSAs are built on a 17-article structure derived from the template from ORA's first executed 2026 PSA. Every PSA must include:

### Mandatory Buyer-Protective Provisions (NEVER DELETE)

1. **Bring-Down Certificate** — Seller must re-certify all representations at closing; any material change allows Buyer to terminate
2. **MAC Clause** — Material Adverse Change right to terminate if property condition, tenant status, or financial performance deteriorates materially between execution and closing
3. **Vacancy Delivery Cross-Default** — If vacancy exceeds agreed threshold at closing, Buyer may terminate or reduce price via formula
4. **Memorandum of Contract Recording Right** — ORA has the right (not obligation) to record a memorandum in the county land records upon execution
5. **Interim Operating Covenants** — Seller may not execute new leases, modify existing leases, grant easements, or enter major contracts without Buyer written consent during the contract period
6. **Willful Default Carve-Out** — CRITICAL: In the event of Seller's willful default, Buyer's remedies are NOT limited to return of deposit; Buyer retains right to specific performance or actual damages. This provision must never be deleted or modified.

### Environmental Cost-Sharing Framework and 17-Article Structure

**Read references/psa-architecture.md before generating any PSA (Workflow 1) or running the 46-Point Gate.** It carries the environmental cost-sharing framework (Phase I/II cost and access rules, remediation allocation formula) and the 17-article structure every ORA PSA must follow (Article 14 Default and Remedies carries the Willful Default Carve-Out; Article 17 Environmental Provisions).

---

## WORKFLOW 1 — PSA GENERATION

When Gabriel says "generate PSA" or "draft PSA" for a property:

1. Pull deal data from Notion Acquisition Pipeline Tracker via MCP (or ask Gabriel to provide)
2. Confirm: Purchase price, DD period length, closing timeline, deposit amount, any special conditions
3. Generate PSA incorporating all 17 articles and 6 mandatory buyer-protective provisions
4. Run the 46-point quality gate checklist (see below)
5. Output as DOCX using the docx skill
6. File naming: per ORA's three standing naming schemas (ratified 2026-06-10 — do NOT unify). PSA deliverables are deal-bound → deal-file schema `[Address] [Purpose] [MM-YYYY]`. Citation provenance: references/rationale-and-incidents.md.

### 46-Point Quality Gate Checklist

Before delivering any PSA draft, verify:

- \[ \] All 6 mandatory buyer-protective provisions present and unmodified
- \[ \] Willful Default Carve-Out language is verbatim (not paraphrased)
- \[ \] Purchase price matches LOI / underwriting model exactly
- \[ \] Deposit amount and structure correct (typically 1-2%, hard on Day 1 or at end of DD)
- \[ \] DD period length matches agreed terms
- \[ \] All defined terms are defined before first use
- \[ \] No blank fields or \[TBD\] remaining
- \[ \] Seller entity name matches title commitment / county records **and the state business-entity registry (exact registered name; Active / Good Standing)** — references/dd-checklist.md § Entity Verification
- \[ \] Buyer entity name matches ORA's intended acquisition entity
- \[ \] Proration date specified (typically day of closing)
- \[ \] Closing date specified or formula clear
- \[ \] Broker disclosure matches actual broker(s) on deal
- \[ \] All exhibits referenced in body are attached: Exhibit A (legal description), Exhibit B (rent roll), Exhibit C (personal property), Exhibit D (form of deed), Exhibit E (form of assignment of leases)
- \[ \] **Every exhibit is POPULATED, not merely present** — run `scripts/audit_completeness.py`. "Attached" and "has content" are different questions, and only the second one matters. An empty exhibit passes a visual check indefinitely: at 754 Old State Route 74, Exhibit B (Rent Roll) was a heading and nothing else across four drafting rounds and two law firms, while §7 defined "Leases" by reference to it and §15.1.2 confirmed the absence of renewal and purchase options "except as expressly set forth on" it
- \[ \] Exhibit A carries an actual legal description, not just a parcel or tax-ID number — a deed and a title policy cannot be drafted from a parcel number
- \[ \] No unfilled blanks in the body, and specifically: the **knowledge-party definition** in the representations article names a real individual and title (an open blank there unbounds or voids every knowledge-qualified representation in the document)
- \[ \] Every section cross-reference resolves to a section that exists
- \[ \] Survival period for representations specified (typically 12 months post-closing)
- \[ \] Title standard specified (marketable title, ALTA)
- \[ \] Survey type specified (ALTA/NSPS)
- \[ \] Environmental Phase I timing specified
- \[ \] Notice provisions include correct addresses and emails for both parties
- \[ \] Governing law specified (state where property is located)
- \[ \] Dispute resolution clause present
- \[ \] Recording right for memorandum of contract explicitly included
- \[ \] All tenant leases to be assigned (not terminated) at closing
- \[ \] Security deposit assignment provision present
- \[ \] Prorations: taxes, insurance, rent, CAM — all addressed
- \[ \] Seller to deliver estoppels from tenants above threshold SF
- \[ \] SNDA requirements for existing financing (if any)
- \[ \] Tenant notification obligations at closing addressed
- \[ \] Insurance requirements during contract period specified
- \[ \] Force majeure clause present
- \[ \] Counterparts / electronic signature provision present
- \[ \] Time is of the essence stated
- \[ \] Entire agreement / merger clause present
- \[ \] Severability clause present
- \[ \] No conflicting definitions between articles
- \[ \] Purchase price adjustment mechanism (if any) fully defined
- \[ \] Closing cost allocation (who pays what) fully specified
- \[ \] Deed form matches state requirements (warranty, special warranty, or quitclaim as appropriate)
- \[ \] Transfer tax allocation stated
- \[ \] Seller's closing deliverables list complete
- \[ \] Buyer's closing deliverables list complete
- \[ \] Post-closing obligations (if any) fully specified
- \[ \] Anti-assignment clause — Buyer retains right to assign to controlled entity

---

## WORKFLOW 2 — REDLINE ANALYSIS

When Seller returns a redlined PSA:

### Step 0 — Detect the revision encoding BEFORE parsing (never skip)

**Do not assume the file carries OOXML tracked changes.** Litera Compare / Workshare Compare / Word Compare deliver a FLATTENED document — revisions are strikethrough/underline formatting runs and the file contains ZERO `<w:ins>`/`<w:del>` — so a tracked-change grep reads it as "seller accepted everything", a false negative on the entire redline (references/redline-encoding.md).

Run the detector first, on every inbound marked-up document:

```
python scripts/extract_revisions.py "<file>.docx"
```

It reports every encoding present — `ooxml-tracked-changes`, `compare-tool-formatting` (Litera/Workshare/Word compare output), `comments` (a commented draft carries no revisions at all and must never be reported as clean), or `clean`. Definitions: references/redline-encoding.md.

Exit codes: **0** revisions and/or comments found · **1** genuinely clean · **2** AMBIGUOUS · **3** unreadable.

**Exit 2 is a stop, not a warning.** It fires when a document reads clean but its filename or its own content says it should not. Never report such a document as clean or fully accepted without opening it by eye.

**A document can carry more than one encoding at once** — a compare output that counsel then tracked-edited before sending. The script reports all of them and warns on the mix; never analyse one and assume it is the whole redline.

How the script identifies insertions (positive strikethrough signal required before compare mode; hyperlink-styled runs ignored): references/redline-encoding.md.

**Read the compare-tool summary block before anything else.** It names the BASE the counterparty compared against — every provision NOT marked is accepted *from that base*, not merely left uncommented — and its own change tally. **Confirm the base is the draft ORA actually sent**; if it names an earlier draft, re-base the whole round before analysis. Cite the tool's own tally externally, not the script's run counts. Detail: references/redline-encoding.md.

> Origin: 2026-07-31, 754 Old State Route 74 — a Litera Compare output with 0 tracked changes and 29 real revisions. See references/rationale-and-incidents.md.

Then:

1. Confirm which encoding was detected and state it at the top of the analysis
2. Parse every revision and categorize:

CategoryDefinitionAction**ACCEPT**Immaterial clarification, consistent with ORA intentAccept without negotiation**NEGOTIATE**Adverse change but has acceptable middle groundPropose counter-language**REJECT**Directly contrary to ORA's interests; no acceptable compromiseReject with written explanation**CRITICAL**Deletes or weakens mandatory buyer-protective provisionsReject + flag for Gabriel + require explanation from Seller

3. Flag all deletions or modifications to the 6 mandatory buyer-protective provisions — these are automatic CRITICAL flags

4. Score overall seller aggressiveness: 1 (cosmetic) → 10 (adversarial)

   - 1-3: Seller is cooperative; few substantive redlines
   - 4-6: Normal negotiation; several adverse changes but deal still workable
   - 7-9: Seller is aggressive; multiple critical provisions attacked
   - 10: Seller has gutted buyer protections; reconsider deal economics or walk

5. Produce Negotiation Strategy Memo:

   - Overall assessment and aggressiveness score
   - Top 5 issues by priority
   - For each: ORA's position, Seller's position, proposed counter, fallback, walk-away point
   - Recommended response timeline
   - Output as DOCX: ORA_RedlineAnalysis\_\[PropertyShortName\]\_v\[X.Y\].docx

6. Every redline round ALSO re-runs Workflow 2A Steps 1–3 (LOI conformance + register check) on the resulting draft — a seller redline can delete a register-tracked term as easily as an initial draft can omit it.

7. **A quiet round is a finding, not an absence of one.** When the counterparty returns few or no substantive changes, say so explicitly and enumerate what they ACCEPTED — particularly provisions a counterparty would ordinarily contest. That list is the KEEP list for every subsequent round, and it is the strongest available read on counterparty motivation. Do not let a light redline produce a light memo.

---

## WORKFLOW 2A — INBOUND DRAFT REVIEW (LOI CONFORMANCE)

**Walk-price check (v1.14).** At the start of Workflows 2A, 3 (DD) and 4 (closing), and on each outbound 2B round, compare the PSA contract price with the current walk, read from the deal's Deal Sourcing Log row (`collection://9a6ae219-85a3-4621-899c-c757fd062f8b`; the last `RE-SOLVED v4.37 (YYYY-MM-DD): $X` line appended in `Notes / Flags` if present, otherwise a `Walk Price` solved under v4.37 or later, and re-solved under v4.53 or later when the deal carries a v4.53 IRR add-on — single tenant / tenant >50% of rent, tertiary market or satellite, environmental-heavy use without a clean Phase II, new operating competency — or a land credit (re-solve if neither); on a Mixed-Use Component Lens deal, the lens's binding walk, never the Base walk, and a stored walk on a deal that meets any lens trigger (`acquisition-underwriting` Mixed-Use Component Lens, "Fires when") is stale and re-solved with the v4.58 lens first when it has no `COMPONENT LENS` line (solved before v4.57, or without the lens) or was a v4.57 lens walk (IRR leg only); an exception ratified against such a walk is re-ratified). If the price exceeds it and no exception is ratified against a walk solved under v4.37 or later, stop and raise the live-offer exception trigger (`acquisition-underwriting`, Pre-v4.37 walks) before the next step.

When ANY PSA draft arrives that this skill did not generate — own counsel's initial draft, seller counsel's first draft, or a counter-draft — review it BEFORE it circulates. Own-counsel drafts get the same scrutiny as seller paper: a recycled template that ships today is an executed contract next month. Origin (754 Old State, 2026-06-11 — USD 50K deposit error, 9 LOI-conformance failures, linchpin easement omitted): references/rationale-and-incidents.md.

### Step 1 — Assemble ground truth
1. Read the EXECUTED LOI in full (signed copy, not a prior draft).
2. Read `DEAL-TERMS-REGISTER.md` in the deal folder (written by loi-generation Phase 6b at LOI draft, finalized at execution — a DRAFT-status register still counts and must be read). If absent: sweep the IC memo, meeting notes, and broker correspondence for terms agreed outside the LOI, SAY SO in the output, and create the register before finishing — side-channel terms are exactly what this step exists to catch.
3. Note the structural facts boilerplate most often contradicts: tenancy (multi-tenant / single / vacant), state, asset type, included personal property, excluded parcels.

### Step 2 — LOI conformance table (mechanical — every row, no skipping)
Extract each negotiated LOI term, locate its PSA counterpart, and status every row CONFORMS / DRIFTED / REVERSED / MISSING with §-cites on both sides. Canonical rows (add deal-specific ones):

1. Purchase price (words AND numerals)
2. Deposit: amount, due date, escrow agent identity, interest-bearing status
3. Deposit refundability triggers (study-period walk, seller default, title failure, estoppel failure, failure of any condition precedent)
4. Study/Feasibility Period: length, commencement trigger, and TERMINATION STANDARD — an any-reason sole-discretion walk must never be narrowed to test-results-based
5. Environmental: Phase I/II rights, automatic extension, deposit refundability during extension
6. Closing timing formula
7. Deed type and title standard (state-correct terminology)
8. Cost allocations: conveyance fees, title premium (check local custom before conceding splits), escrow split, recording, survey
9. Proration method, tax treatment, BOR/appeal rights — and their survival of closing
10. Casualty: threshold, proceeds + deductible assignment, termination right
11. Condemnation: threshold, award assignment
12. Estoppels: content (including NO renewal/extension/purchase options where the thesis depends on it; the full instrument chain by date; and verbatim reproduction of any manuscript amendment, signed by every party to it), timing, condition-precedent status. Where the lease-chain integrity check found a gap, an unexecuted counterpart or a landlord-of-record mismatch, the estoppel is the instrument that cures it — draft it to say so explicitly. **If Lease-Chain Integrity hasn't run yet for this suite** (Workflow 2A's PSA review commonly precedes Workflow 3's DD, where the check actually executes): don't assume a clean chain — note that the check is outstanding and flag estoppel content as provisional pending it, rather than silently omitting the cure language.
13. Interim operating covenants — the lease lockdown must cover AMENDMENTS to existing leases, concessions, and consents, not just new leases; capex consent threshold; insurance maintenance; service-contract controls and termination at closing
14. Personal property: Bill of Sale, schedule, free-and-clear delivery; tenant security deposit transfer
15. 1031 cooperation — mutual per ORA default, never seller-only
16. Assignment rights + any entity-purchase election (flag elections that EXPIRE at PSA execution)
17. Governing law AND venue
18. Seller document-delivery list, timing, and consequences of late delivery (day-for-day DD extension)

### Step 3 — Register check (highest-value check in this workflow)
Every OPEN register item tagged "Must land in: PSA" must appear in the draft. Absent = automatic CRITICAL. Side-channel terms — easements, parcel exclusions, verbal agreements, strategy-driven omissions — exist in NO binding document until the PSA captures them.

### Step 4 — Template provenance scan
Each hit is evidence the draft needs structural review, not typo cleanup:
- **Out-of-state markers**: water rent, annual benefit charges, front-foot charges, "collector of taxes", ground rent, density credits, wrong-state statute cites, wrong-state title standards (e.g., "good of record and in fact" outside MD)
- **Stale boilerplate**: COVID/"Virus" tolling clauses, expired statute versions, obsolete program references
- **Wrong-asset residue**: vacant-property covenants in a tenanted deal (or vice versa), singular "the Lease" in a multi-tenant deal, residential terms in commercial paper
- **Copy-paste tells**: the counterparty's name inside our own reps, numbering gaps, blank fields, undefined defined-terms, duplicated overlapping sections

### Step 5 — Standards check and ranked output
Run the 6 Mandatory Buyer-Protective Provisions check and the review-relevant 46-Point Gate items. Run `scripts/audit_completeness.py` (see Workflow 2B Check D) — exhibits, cross-references, and unfilled blanks are mechanical checks that must not be done by eye. Output ranked: Tier 1 (deal-critical — must not circulate), Tier 2 (value and risk), Tier 3 (hygiene), then a KEEP list of ORA-favorable provisions that must survive redline rounds. Lead with the single most important defect. DOCX memo on request: `YYYYMMDD_[Property]_PSAReviewMemo_v##.docx`.

**Independent conformance pass.** Before finalizing the ranked output, dispatch the `psa-redline-checker` agent (read-only; pin the dispatch model) on the draft plus the executed LOI, `DEAL-TERMS-REGISTER.md` and the Standard Positions canon — give it NO prior review memo so it re-derives conformance cold. Reconcile its deviations against your conformance table; any deviation you did not catch is a Tier 1 candidate. It is a sub-step of this workflow, not a replacement for it (psa-reconciliation's Fact Table cascade is separate).

**INTERIM aggregate-LTV ledger (v1.11).** For a PSA under which ORA sells or changes Oxford's share of an asset, or that carries a loan, follow the INTERIM checklist in `debt-management/references/ltv-interim-netting-checklist.md`; for a terminated PSA, prompt Gabriel to mark its row WITHDRAWN per the same checklist.

**Every review memo produced under this workflow is an input to Workflow 2B.** Write recommendations so they can be checked mechanically later: cite the § being changed, and state the change as a concrete before/after, not as advice. A recommendation phrased as "consider strengthening the remedies section" cannot be verified in an outbound draft; "§11.3.2 — add willful-default carve-out permitting actual damages" can.

---

## WORKFLOW 2B — OUTBOUND DRAFT GATE (run before ANY draft leaves ORA)

Workflow 2A guards paper coming IN. Nothing guarded paper going OUT — and that is where the larger loss occurred.

> Origin: 2026-08-01, 754 Old State Route 74 — the outbound 7/22 draft dropped **nine** of fifteen review-memo recommendations, **four** of them ORA's own mandatory buyer-protective provisions, three executed-LOI terms and two standing positions; seller never rejected any of them because they were never sent. **Read references/rationale-and-incidents.md (Workflow 2B origin) before waiving any Check A item.**

Run this gate on any draft ORA is about to send — whether ORA drafted it, own counsel drafted it, or it is ORA's markup of seller paper. It takes minutes and is not optional.

### Check A — Prior-memo delta (the check that would have caught 754)
For EVERY prior review memo on this deal, in order, enumerate each recommendation and status it against the outbound draft:

- **LANDED** — present in the draft, in substance
- **DROPPED** — absent, with no recorded decision. **Automatic STOP.** A dropped item is either reinstated or consciously waived on the record; it is never silently omitted.
- **WAIVED** — absent, but Gabriel decided not to pursue it. Requires a one-line reason in the deal-terms register. A waiver made once carries forward; it does not need re-litigating each round.
- **SUPERSEDED** — overtaken by a later development. State what superseded it.

Report as a table with a §-cite and the memo/date each recommendation came from. **Never grade this from memory of the memo — reopen the memo file and work down it line by line.** The failure mode is not disagreement about a recommendation; it is a recommendation nobody looked at again.

### Check B — The 6 Mandatory Buyer-Protective Provisions
Confirm all six are present and unmodified in the outbound draft: bring-down certificate, MAC clause, vacancy delivery cross-default, memorandum of contract recording right, interim operating covenants, willful default carve-out. Absent = STOP.

Grep the draft for each by its operative language, not by section number — these ORA-added provisions vanish quietly because nothing in the template complains when they are missing.

### Check C — LOI conformance and register re-check
Re-run Workflow 2A Steps 2 and 3 (LOI conformance table + register check) against the OUTBOUND draft. An ORA-side drafting round can reverse an executed LOI term as easily as seller's can: at 754, interest-bearing escrow, the 5% casualty threshold, and the 30-day Phase II extension were all agreed in the executed LOI and all three were non-conformant in ORA's own outbound draft.

Frame every Check C finding to the counterparty as a **conformance correction, not a new ask** — it costs the counterparty nothing to restore a term it already agreed to in the LOI, and framing it as a fresh negotiation invites a trade that was already made.

### Check D — Mechanical completeness sweep
```
python scripts/audit_completeness.py "<outbound draft>.docx"
```
Non-zero exit = STOP. The script checks three things reviewers reliably miss because they read the body and skim the back matter:

1. **Exhibit population** — present, titled, referenced and completely EMPTY is a defect; trace what depends on each empty exhibit. **An exhibit whose only content is an empty table grid (zero rows, every cell blank, struck-only, or only a DMS stamp or an empty content-control prompt) is EMPTY and blocks** (Gabriel's in-turn ruling, 2026-11-06). Underscore runs are blanks, not content: an exhibit holding only rules is EMPTY. A `THIN` exhibit (bare image, parcel number, or a header-only table) is advisory: a defect if a third party could not draft from it.
2. **Cross-references** — exhibits cited but absent, present but never cited, unresolved section references.
3. **Unfilled blanks** — body blanks are defects; signature-block blanks are expected but must be completed consistently at execution. **A blank inside a data exhibit that follows IN WITNESS WHEREOF is a body blank and blocks** (Gabriel's in-turn ruling, 2026-11-06). Only genuine signature, notary or recording-form lines are exempt, judged line by line: signature labels with nothing but the blank (`By:`, `Name:`, `Title:`, `Its:`, `Date:`, `Authorized Signatory:`, `Attest:`), a bare signature rule (in a data-captioned exhibit, or past the end of a Form-of region, only inside a signature stack anchored by a strong cue judged on the whole line — an unfilled `By: ____`; a filled `By:` naming a person (`By: Jane Q. Doe, Manager`, `By: JOHN SMITH`, `By: José Núñez`; never an entity word or a placeholder such as `To Be Provided`, `See Schedule`, `TBD`, `Pending`, `To Follow`) or with a `Name:`/`Title:`/`Its:` line directly beside it; a seal-only line (`____ (SEAL)`, `[SEAL]`, `(Corporate Seal)`, `(L.S.)`); a Notary Public title or commission line; a full venue line (`STATE OF OHIO )`, `COUNTY OF FRANKLIN ) ss:`); or `(Signature)`/Signature/Authorized Signatory/Printed Name as a whole label followed by nothing, a blank or a personal name — never a mid-prose match (`…, to wit:`, `County of Franklin (the "County")`, `Monument stamped (SEAL)`, `I hereby certify …`, `Signature Aviation LLC`, `By: Acme LLC`), reached through at most three adjacent signature-label lines, with at most one rule per stack; a filled or unfilled `Name:`/`Title:`/`Date:`/`Dated:`/`Witness`/`Attest` line never clears a rule on its own, and an unfilled `Name:`/`Title:`/`Date:` there needs the same stack), `(SEAL)` lines, and venue lines in venue shape (`STATE OF OHIO ) ss:`, `____ COUNTY )`, MD `…, TO WIT:`). Notary acknowledgment sentences (OH/IN/MD/MO/KS/WI/TN: acknowledged, sworn, personally appeared, witness my hand, in testimony whereof, given under my hand, I hereby certify) are exempt only next to a notary cue (Notary Public, commission line, venue line, notary seal). Party labels (`Tenant:`, `Seller:`, `Grantee:`, `Return to:` …) need a signature line directly beside them, entity lines need one within three lines, and none of these is ever exempt inside a data-captioned exhibit (a rent roll's `Tenant: ____` is a value). A line carrying `$`, a value word (rent, rental, price, parcel, lot, suite, unit, term, deposit, amount, balance, premises, address …), a second value label or a non-seal parenthetical is never exempt. **Exhibits captioned "Form of …" (deed, assignment, estoppel, bill of sale, notice letter) are templates completed at closing: their blanks never block — but a data caption (rent roll, legal or property description, any schedule, tenant list, leases, service contracts, permitted exceptions, lease abstract, personal property list) overrides the exemption and blocks** (Gabriel's in-turn rulings, 2026-11-06: Form-of exemption; data captions override it). The caption is the first non-blank block after the heading; a Form-of region ends at the next block opening with EXHIBIT/SCHEDULE/ANNEX/APPENDIX/ATTACHMENT/RIDER or carrying a data caption, and what follows is judged as data; an inline cross-reference to a separately attached exhibit or schedule inside the form (`Legal Description: See Exhibit A attached hereto.`) does not end it when that exhibit has exactly one EXHIBIT heading, outside the form exhibit; `see Schedule 1 below`, `attached as Schedule 1 below`, `… herein`, any Schedule reference, or a reference to an exhibit with no heading or several headings does. Exhibits attached before IN WITNESS WHEREOF keep the body-blank rule. An unfilled **knowledge-party definition** silently voids or unbounds every knowledge-qualified representation.

Full descriptions: references/scripts.md.

### Check E — Self-expiring terms
Scan for anything that has gone stale since the draft was written, and for anything that will expire before the next round-trip completes:

- Offer-expiration / acceptance-deadline dates that have already passed — a contract that declares its own offer withdrawn on its face is a gift to opposing counsel
- Effective Date blanks, and every deadline keyed to the Effective Date (document-delivery, title commitment, contingency filings, outside dates, closing) — confirm they are internally consistent and that the schedule is achievable
- Elections that expire AT execution (entity-purchase elections, structure elections) — silence is a decision; make it a deliberate one and close the register item
- Any date that will lapse before the counterparty can realistically respond

### Check F — Independent second pass
Dispatch the `psa-redline-checker` agent (read-only; pin the dispatch model) on the outbound draft against the executed LOI, the deal-terms register and the Standard Positions. Give it NO prior review memo (it must re-derive conformance cold). Any deviation it reports that Checks A–E did not catch is a **STOP** until reinstated or waived on the record.

### Output
A short pre-send memo — no more than a page — with a single verdict line: **CLEAR TO SEND** or **HOLD**, followed by the Check A table and any STOPs. Log the result to the deal-terms register so the next round starts from a known state. A CLEAR TO SEND execution version under which ORA sells or changes Oxford's share of an asset, or that carries a loan: follow the INTERIM checklist (Workflow 2A Step 5). Then stamp the Notion pipeline row per the standing rule below.

---

## WORKFLOW 2C — ESSENTIAL-ONLY OUTBOUND REDLINE (ORA markup of counterparty paper)

Use when ORA marks up an instrument the counterparty drafted (easement, REA, shared-maintenance agreement, termination, PSA, amendment, estoppel) and the markup must be tracked changes limited to essential items (Gabriel's standing preference: push back only on provisions that protect against real loss). Origin: 754 Old State Parking Easement & Shared Maintenance Agreement, 2026-11-25.

1. **Ground truth.** Read the deal decision log, including section 10 (agreed outside the documents, `deal-decision-log` v1.1+), the deal-terms register, the governing contract section that defines the instrument (for example PSA §31), and the last review memo. Note any contractual response clock ("within five (5) days after receipt").
2. **Review and tier.** Tier 1 = essential (real loss: rights, access, insurance, lender subordination, preservation of recorded easements, notice mechanics that start deemed approvals). Tier 2 = optional or housekeeping (caps, typos, preparer lines). Mark Tier 2 only if Gabriel selects it.
3. **Ask before drafting.** Run `ora-open-decisions` once, before the redline: scope tier, wording that could reveal confidential strategy, how to paper any NOT PAPERED side agreement, insurance limits or blanks, and format (tracked-change author; margin notes or not). If a decision turns on what was agreed, answer it from decision-log section 10, cite the row, and backfill rows found by fresh search.
4. **Write the spec.** A JSON list of ops for `scripts/essential_redline.py`: `insert` (anchor + `at` end/start/offset), `delete`, `replace`, `new_para_after` (copies the anchor paragraph's numbering so new sections auto-number), `comment` (margin note on the anchor paragraph). Each anchor must match exactly once in run text; order ops so no anchor is text an earlier op split. Tracked text never carries confidential rationale; margin notes may cite internal emails, so they belong in the review copy only. Worked example: `references/examples/essential_redline_spec_754-parking-easement.json`.
5. **Run, validate, inspect.**
   - `python scripts/essential_redline.py spec.json in.docx review.docx --author "Gabriel Goldberg"` (review copy, with notes)
   - `python scripts/essential_redline.py spec.json in.docx outbound.docx --author "Gabriel Goldberg" --strip-comments` (outbound copy)
   - Exit 2 names the failing op and anchor; fix the anchor and rerun. Nothing is written on failure.
   - Validate both with the docx skill: `scripts/office/validate.py <out> --original in.docx --author "<author>"` (every edit tracked).
   - Render to PDF and look at one changed page; export to text with LibreOffice and confirm new sections carry the expected numbers.
6. **File and hold.** Deal-file naming schema, save to the deal folder `outputs/`, add a register row and update the review memo and decision log. Nothing is sent: an outbound counterparty send needs Gabriel's or Eric's in-turn confirmation. If the instrument is PSA paper, run Workflow 2B on the outbound copy first.

Tool detail and limits: references/scripts.md § essential_redline.py.

---

## WORKFLOW 3 — DUE DILIGENCE MANAGEMENT

ORA's standard DD checklist has 156 items across 8 categories. When DD period opens:

### DD Checklist Generation

Generate a full checklist in XLSX format with:

- Item number
- Category (Financial, Physical, Legal, Title, Environmental, Zoning, Tenant, Market)
- Description
- Responsible party (Buyer or Seller)
- Due date (calculated from DD period commencement)
- Status: Not Started / In Progress / Complete / Issue Found
- Notes / Issue Description

### DD Categories and Key Items

**Read references/dd-checklist.md before generating the DD checklist workbook** — it carries the key items per category (Financial 28 · Physical 22 · Environmental 18 · Title & Survey 21 · Legal 24 · Zoning & Permits 14 · Tenant 20 · Market 10), the PD/PUD item (`ora-flood-zoning-dd` Step 6A), and the routing to `title-exam-abstraction` (title commitment abstract + vesting record) and `estoppel-request-generation` (never draft blank-form estoppels by hand).

**LEASE-CHAIN INTEGRITY (Category: Legal — run on every occupied suite, before waiving the DD contingency):** reconstruct the full instrument chain by date (base lease, every renewal, every amendment — a margin note, email or rent-roll line is a **gap**, not a term); confirm an **executed counterpart exists for every link** (transmittal drafts show blank signature blocks, "sent" annotations, diagonal strikes — add missing originals to the seller's closing deliverables); confirm the **landlord named in each lease matches title vesting** per `title-exam-abstraction` (provisional seller-name fallback if it hasn't run; two mismatches is a papering pattern — escalate to an affirmative PSA representation); catalogue every **manuscript amendment** and confirm all-party initials (read the page images — OCR does not see ink); reconcile **tenant of record** against the rent roll and the estoppel. **Read references/dd-checklist.md (Lease-Chain Integrity) for the full procedure and its 754 Old State origin.**

**ENTITY VERIFICATION (Category: Legal — every acquisition; before the first PSA draft, before estoppels, and within 30 days of closing):** look up every party that signs or is named — Seller and predecessors, each tenant entity **and trade name**, entity guarantors, and ORA's own buyer/assignee and any ORA entity on a municipal filing — in the state registry of formation (and the property state if foreign-registered); record exact registered name, number, status and date checked in the Deal-Terms Register; conform every document to the registered name; treat a non-active status as an authority defect. **Read references/dd-checklist.md (Entity Verification) for the registries, the action rules and the 754 Old State origin.**

### Automatic Price Renegotiation Flags

Flag any DD finding that should trigger price renegotiation:

- Environmental contamination with estimated remediation cost &gt;USD 50K
- Structural issues with estimated repair cost &gt;USD 100K
- Roof replacement required within 2 years
- Any tenant with &gt;60 days delinquency not disclosed pre-contract
- Zoning non-conformance that limits redevelopment rights
- Any undisclosed encumbrance on title
- Occupancy at closing materially below rent roll provided at LOI

---

## WORKFLOW 4 — CLOSING COORDINATION

### Pre-Closing Checklist (10 business days out)

- \[ \] All DD items resolved or waived in writing
- \[ \] Closing statement draft received from title company
- \[ \] Review closing statement: verify all prorations, credits, and adjustments
- \[ \] Confirm wiring instructions with title company (verify via phone — no email-only wire instructions)
- \[ \] Confirm entity formation documents ready for title company
- \[ \] Entity status re-checked within 30 days of closing for Seller, the ORA buyer/assignee and every tenant signing a closing document; good-standing certificates for Seller and the ORA buyer in hand (references/dd-checklist.md § Entity Verification)
- \[ \] Confirm signatory authority documentation (operating agreement, resolution)
- \[ \] Confirm lender (if any) has cleared to close
- \[ \] Confirm all Seller closing deliverables received or committed
- \[ \] Final walk-through scheduled
- \[ \] Tenant notification letters drafted (to be sent day of closing)

### Closing Statement Review

When Gabriel uploads a closing statement (HUD-1 or ALTA Settlement Statement):

- Verify purchase price matches PSA
- Verify deposit credit applied correctly
- Verify proration calculations (taxes, rent, CAM)
- Flag any line items that were not anticipated
- Confirm seller proceeds net of broker commission matches expectation
- Verify all ORA closing costs (title insurance, recording fees, transfer taxes) are accurate
- Output: annotated PDF with any issues flagged in red

### Post-Closing Integration

Post-closing operational setup (`re-operations` retired 2026-08-05, redundant with named ops siblings — route by task: `rent-roll-reconciliation` for PM-platform/tenant-DB setup (items 2, 9 below), `ora-pm-ledger` to track the remaining manual steps as ops tasks; items 4, 6, 10 are Eric/manual, not skill-automated):

 1. Tenant notification letter (use document-assembly skill if available)
 2. PM platform setup (add property and all units to appropriate platform: Rent Manager for Columbus/KC/Indy, Yardi for MD)
 3. Insurance transfer (notify broker, update policy to new entity)
 4. QuickBooks Desktop entity creation (new LLC → new class in QBD; manual step by Eric, not Cowork-automated)
 5. Utility transfer to new entity
 6. Bank account opening for new property entity
 7. Existing service contract assumption or termination
 8. HubSpot deal marked Closed Won; Notion pipeline updated to Closed (set Stage = Closed Won **and `Last Activity` = today**)
 9. Physical key and access credential transfer
10. Lender notification (if existing debt assumed)
11. LTV ledger (INTERIM; v1.11): follow the INTERIM checklist in `debt-management/references/ltv-interim-netting-checklist.md` (BOOKED-VERIFIED).

---

## NOTION PIPELINE STAMPING (standing rule — added 2026-07-17)

Any time this skill acts on a deal that has an Acquisition Pipeline Tracker row (`bcfe4a03`) — generating a PSA (Workflow 1), reviewing an inbound PSA draft or processing a redline round (Workflow 2A), or completing closing (post-closing checklist above) — update that row: advance PSA Status / Stage as the action warrants **and set `Last Activity` = today (date-only)**.

This is load-bearing for the weekly `ora-deal-command-board`, which reads `Last Activity` (not Notion's system last-edited timestamp) to decide staleness — PSA negotiation that happens off-Notion must still bump it, or the deal false-flags STALLED while under active work. Do NOT rely on the board to stamp this itself; it is read-only by charter. Origin (754 Old State Route 74, 2026-07-17): references/rationale-and-incidents.md.

**`Next Action Date` — stamp it whenever the next action carries a date (added 2026-08-12).** The tracker gained a `Next Action Date` date property on 2026-08-11. Rule: **if the `Next Action` text you write names or implies a date, write that date into `Next Action Date` as well — never only into the prose.** If the next action genuinely has no date, leave the column NULL; do not invent one, and do not substitute the target close date or a guess like "about a month out." This is the same argument `loi-generation` Phase 6 already makes for `LOI Expiration Date`: a date sitting only in prose rots the moment anyone edits the field, and nothing can safely alert against it.

Where a workflow produces several dated obligations at once, `Next Action Date` carries the **nearest one ORA must act on**, not the furthest; the full set belongs in the Deal-Terms Register and the diary. Stamp what the document says, not what you infer it means — both consumers (`ora-deal-command-board` STEP 2b, `ora-deal-aging-sla` STEP 3d) surface a wrong date as a contradiction rather than silently trusting it, but a human still pays for the reconciliation. Rationale: references/rationale-and-incidents.md.

---

## OUTPUT FORMATS

- DD Checklist: XLSX workbook (use xlsx skill)
- PSA: DOCX (use docx skill)
- Redline Analysis: DOCX structured memo
- Closing Checklist: Notion page or DOCX
- File naming: per ORA's three standing naming schemas (ratified 2026-06-10 — do NOT unify). Redline/closing deliverables are deal-bound → deal-file schema `[Address] [Purpose] [MM-YYYY]`. Citation provenance: references/rationale-and-incidents.md.

## SCRIPTS

All three are stdlib-only; run from the skill directory. `scripts/essential_redline.py` — Workflow 2C (JSON-spec tracked-change redline with optional margin notes; exit 2 = an anchor did not match exactly once, nothing written). `scripts/extract_revisions.py` — Workflow 2 Step 0 and legal-intelligence Module 6 (exit 2 = ambiguous, hard stop). `scripts/audit_completeness.py` — Workflow 2A Step 5, Workflow 2B Check D, 46-Point Gate (exit 1 = blocking defect). Details: references/scripts.md.

## Changelog

- v1.18 (2026-11-25): **Workflow 2C — essential-only outbound redline** (Gabriel's request, 2026-11-25). Procedure for ORA markup of counterparty paper (ground truth incl. the decision-log side-agreement ledger, Tier 1/Tier 2, one `ora-open-decisions` batch before drafting, file-and-hold) plus `scripts/essential_redline.py` (JSON-spec tracked changes and margin notes; review and `--strip-comments` outbound copies; tests in `tests/test_essential_redline.py`). Tested by reproducing the 754 Old State Parking Easement redline. Supersedes a same-day card install labelled "v1.17", which was built from the stale v1.16 mirror and dropped the repo's 11/23 v1.17 walk-price change; this version restores it (repo-first). Retention: v1.13, v1.12 and v1.11 compressed, full text in `versions/CHANGELOG-v1.11-v1.13.md`. **No DD checklist item, buyer protection or 46-Point Gate check changed. No governor constant changed (DSCR 1.25x; 40% aggregate; 65% per-property).**
- v1.17 (2026-11-23): Walk-price check names the Mixed-Use Component Lens walk: the lens's binding walk, never its Base walk, and a stored walk on a lens-trigger deal without a `COMPONENT LENS` line, or a v4.57 lens walk (IRR leg only), is re-solved under `acquisition-underwriting` v4.58 first, with any exception re-ratified. No workflow, gate or governor change.
- v1.16 (2026-11-15): Walk-price check: a walk on a deal that carries a v4.53 IRR add-on or a land credit must be re-solved under `acquisition-underwriting` v4.53 or later (consumer sweep for v4.53, Gabriel in-turn ratification 2026-11-14; RE-4.53-1, RE-4.53-2; the sweep had missed this check). No governor constant changed.
- v1.15.1 (2026-11-14): Wording only: dollar figures in the body now read "USD n" with no dollar sign before a digit, because a skill invoked with arguments has every dollar-digit sequence in its body replaced by an argument token (`tools/lint_skill_dollar_args.py`). No value, rule, threshold or constant changed.
- v1.15 (2026-11-08; Gabriel in-turn approval of the fix, 2026-11-08): **Check D: bare rule in a data exhibit blocks.** `scripts/audit_completeness.py` classed a line of only underscores as a signature rule unconditionally and counted the underscores toward exhibit population, so a post-signature Legal Description exhibit holding nothing but `________` passed the gate (not even THIN). Now, in a data-captioned exhibit (and after a Form-of region ends) a bare rule, or an unfilled `Name:`/`Title:`/`Date:` label, is a signature blank only inside a signature stack anchored by a strong cue judged on the whole line — an unfilled `By: ____`; a filled `By:` naming a person (`By: Jane Q. Doe, Manager`, `By: JOHN SMITH`, `By: José Núñez`; never an entity word or a placeholder such as `To Be Provided`, `See Schedule`, `TBD`, `Pending`, `To Follow`) or with a `Name:`/`Title:`/`Its:` line directly beside it; a seal-only line (`____ (SEAL)`, `[SEAL]`, `(Corporate Seal)`, `(L.S.)`); a Notary Public title or commission line; a full venue line (`STATE OF OHIO )`, `COUNTY OF FRANKLIN ) ss:`); or `(Signature)`/Signature/Authorized Signatory/Printed Name as a whole label followed by nothing, a blank or a personal name — never a mid-prose match (`…, to wit:`, `County of Franklin (the "County")`, `Monument stamped (SEAL)`, `I hereby certify …`, `Signature Aviation LLC`, `By: Acme LLC`) (no `$` or value word), reached through at most three adjacent signature-label lines (reach 3 = By/Name/Title/Date stack) with at most one rule per stack (round-2 R1); otherwise it is a body blank. Filled or unfilled `Name:`/`Title:`/`Date:`/`Dated:`/`Witness`/`Attest` lines never clear a rule on their own (merge-gate REFUTE C3: `Date: October 31, 2026`, `Name: Acme LLC` are rent-roll data). Signature-only words standing alone (`Its`, `Attest`, `Witness`, `Date Signed`, `Name and Title`, `Dated as of …`, `Executed this … day of …`) stay exempt per the 2026-11-06 line-level ruling. A Form-of region is no longer ended by an inline cross-reference to a separately attached exhibit or schedule (`Legal Description: See Exhibit A attached hereto.` in a Form of Deed; REFUTE C2); a reference into the exhibit (`Leases: see Schedule 1 below`) still ends it and the schedule that follows is judged as data (round-2 R2). Round 3 and final refute: the cross-reference exception holds only for an Exhibit reference whose id has exactly one EXHIBIT heading, outside the form exhibit, and rejects below/following/herein in both shapes; a Schedule reference, a missing or duplicated heading ends the region, fail closed (`Leases: see Schedule 1 attached` + headingless schedule, with or without an unrelated `SCHEDULE 1` / `Schedule 1 - Wire Instructions` in another exhibit, `attached as Schedule 1 below`, `as described in Exhibit Z attached` with no Exhibit Z all block); a filled `By:`/caption naming a placeholder (`To Be Provided`, `See Schedule Two`, `To Follow`, `Not Yet Available`, `Information Forthcoming`, `Seller Counsel`) never clears a rule; all-caps and Unicode personal names (`JOHN SMITH`, `José Núñez`, `Seán O'Brien-Murphy`) and `[SEAL]`/`(Corporate Seal)` lines do; `Dated`/`Executed`/`Signed` link a stack only in label, `as of`, `this … day of` shape (not `Signed leases are on file`). **Accepted by design under the Form-of ruling:** inside a Form-of region kept open by a valid cross-reference, form-field blanks such as `Rent: $____` or `Parcel No. ____` are form blanks and do not block (merge-gate X6/X7). **Accepted residuals:** (i) capitalised entity or geographic names on a filled `By:`/Printed Name line read as a person (`By: North Coast`, `By: Acme Warehouse`; origin/main passes them too); (ii) after a valid single-target Exhibit cross-reference, headingless inline data later in the same Form-of exhibit is judged as form (follows from the C2 decision); (iii) a full venue line alone (`STATE OF OHIO )`) clears an adjacent rule (origin/main passes it too); (iv) fail-closed false block: an all-caps signer line with no `By:` label (`JOHN SMITH, MANAGER` under a rule) blocks; (v) the pre-existing flaky timing test `rulings4::TestCueLookupIsLinear::test_ten_thousand_venue_lines_in_one_cell` (about 0.86s median on origin/main against a 1.0s threshold) is left untouched. Gabriel's in-turn ruling (2026-11-08): the 2026-11-06 line-level exemption of signature-only words standing alone is kept unchanged. Accepted fail-closed: a typed signer in a data exhibit with no `By:` (`SELLER:` / entity / rule / `John Smith, Managing Member`) blocks. Underscore runs no longer count toward exhibit population (rule-only exhibit = EMPTY; parcel number plus rule = THIN). Form-of exhibits, non-data exhibits and `(SEAL)` rules unchanged. Check D items 1 and 3 and `references/scripts.md` updated. **No DD checklist item, buyer protection or 46-Point Gate check changed. No governor constant changed (DSCR 1.25x; 40% aggregate; 65% per-property).**
- v1.14 (2026-11-06; Gabriel in-turn 2026-10-28, re-landed from stranded PR #173 with `acquisition-underwriting` v4.43): walk-price check at the start of Workflows 2A, 3 and 4 and each 2B round, read from the Deal Sourcing Log row (PSA price vs a walk solved under `acquisition-underwriting` v4.37 or later; no exception ratified against a pre-v4.37 walk carries over). No other step changed. **No governor constant changed.**
- **v1.13 (2026-11-06):** Check D Form-of exemption, data-caption override and line-level signature rules. Full text: `versions/CHANGELOG-v1.11-v1.13.md`.
- **v1.12 (2026-11-06):** Check D blocking rules widened (empty table grid = EMPTY; post-signature exhibit blanks block). Full text: `versions/CHANGELOG-v1.11-v1.13.md`.
- **v1.11 (2026-10-26):** INTERIM aggregate-LTV pointers (2A Step 5, 2B Output, Post-Closing item 11). Full text: `versions/CHANGELOG-v1.11-v1.13.md`.
- **v1.10 (2026-10-16) — full text: `versions/CHANGELOG-v1.8-v1.10.md`.** ENTITY VERIFICATION added to Workflow 3.
- **v1.9 (2026-09-30) — full text: `versions/CHANGELOG-v1.8-v1.10.md`.** independent agent passes wired in.
- **v1.8 (2026-09-10) — full text: `versions/CHANGELOG-v1.8-v1.10.md`.** retention rule adopted (ORA Automation Audit R24-11).

**Retention rule (added 2026-09-10, ORA Automation Audit R24-11):** keep at most the **6 most recent versions** as full inline entries. The edit that would add a 7th must, in the same pass, compress the oldest full entry to a one-line `**vX.Y (date):** Full text: versions/CHANGELOG-vA.B-vX.Y.md` summary and append its full original text to the versions file for that range. **Per-entry cap ~2,000 characters** — an entry that would exceed it states its finding and verdict inline and cites the deal folder or `versions/` file for the detail. Check both caps in the pass that adds an entry — never as deferred cleanup. Full rule text and calibration: `versions/CHANGELOG-v1.3-v1.7.md`.

- **v1.7 (2026-08-24) — full text: `versions/CHANGELOG-v1.3-v1.7.md`.** PD/PUD item added to the Title & Survey DD checklist (20 → 21 items); procedure in `ora-flood-zoning-dd` Step 6A. Archived 2026-09-22 under the retention rule.
- **v1.6 (2026-08-21) — full text: `versions/CHANGELOG-v1.3-v1.7.md`.** Adversarial review: Lease-Chain landlord check tied to `title-exam-abstraction` vesting; 2A item 12 / Workflow 3 cross-fallbacks; DD-checklist items point to `estoppel-request-generation` and `title-exam-abstraction`; bare "estoppel" trigger narrowed. Archived 2026-09-22 under the retention rule.
- **v1.5 (2026-08-21) — full text: `versions/CHANGELOG-v1.3-v1.7.md`.** LEASE-CHAIN INTEGRITY added to Workflow 3; 2A item 12 extended to the full instrument chain and manuscript amendments. Archived 2026-09-22.
- **v1.4 (2026-08-15) — full text: `versions/CHANGELOG-v1.3-v1.7.md`.** File-naming citations repointed to the Global Operating Prompt v3.0. Archived 2026-09-22.
- **v1.3 (2026-08-01) — full text: `versions/CHANGELOG-v1.3-v1.7.md`.** Workflow 2 Step 0 revision-encoding detection (`scripts/extract_revisions.py`); new Workflow 2B outbound gate; 46-Point Gate (was 42) exhibit-population items (`scripts/audit_completeness.py`). Archived 2026-09-22.
- **v1.2 (2026-07-08) — full text: `versions/CHANGELOG-v1.0-v1.2.md`.** Archived 2026-09-10 under the retention rule above to hold the 6-entry cap while v1.8 was added.
