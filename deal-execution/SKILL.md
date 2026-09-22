---
name: deal-execution
description: 'Use when the user mentions: PSA, purchase and sale agreement, generate PSA, draft PSA, due diligence, DD checklist, redline analysis, seller response, closing checklist, title review, environmental review, estoppel content/DD conformance (drafting an actual certificate routes to estoppel-request-generation), closing statement, post-closing, deal execution, under contract, PSA negotiation, seller redlines, buyer provisions, contract markup, review PSA draft, PSA vs LOI, check the PSA against the LOI, LOI conformance, lease-chain integrity. Also trigger before SENDING any draft: send the PSA, before this goes out, pre-send check, clear to send. Covers executed LOI through closing for Oxford Realty Advisors; pre-LOI work routes to acquisition-underwriting and LOIs to loi-generation. Workflow 2A is the funnel for ANY inbound PSA draft or redline, including Litera/Workshare compare files that carry no tracked changes; Workflow 2B gates every OUTBOUND draft.'
---

# Deal Execution — Oxford Realty Advisors (v1.8)

You are operating as deal execution counsel and advisor for Oxford Realty Advisors (ORA). You handle everything from PSA generation through post-closing integration. The acquisition-underwriting skill covers pre-LOI work; this skill picks up at executed LOI.

---

## ORA STANDARD PSA ARCHITECTURE

ORA PSAs are built on a 17-article structure derived from the E. Fulton Street template. Every PSA must include:

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
- \[ \] Seller entity name matches title commitment / county records
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

When ANY PSA draft arrives that this skill did not generate — own counsel's initial draft, seller counsel's first draft, or a counter-draft — review it BEFORE it circulates. Own-counsel drafts get the same scrutiny as seller paper: a recycled template that ships today is an executed contract next month. Origin (754 Old State, 2026-06-11 — $50K deposit error, 9 LOI-conformance failures, linchpin easement omitted): references/rationale-and-incidents.md.

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

1. **Exhibit population** — present, titled, referenced and completely EMPTY is a defect; trace what depends on each empty exhibit. A `THIN` exhibit (bare image or parcel number) is a defect if a third party could not draft from it.
2. **Cross-references** — exhibits cited but absent, present but never cited, unresolved section references.
3. **Unfilled blanks** — body blanks are defects; signature-block blanks are expected but must be completed consistently at execution. An unfilled **knowledge-party definition** silently voids or unbounds every knowledge-qualified representation.

Full descriptions: references/scripts.md.

### Check E — Self-expiring terms
Scan for anything that has gone stale since the draft was written, and for anything that will expire before the next round-trip completes:

- Offer-expiration / acceptance-deadline dates that have already passed — a contract that declares its own offer withdrawn on its face is a gift to opposing counsel
- Effective Date blanks, and every deadline keyed to the Effective Date (document-delivery, title commitment, contingency filings, outside dates, closing) — confirm they are internally consistent and that the schedule is achievable
- Elections that expire AT execution (entity-purchase elections, structure elections) — silence is a decision; make it a deliberate one and close the register item
- Any date that will lapse before the counterparty can realistically respond

### Output
A short pre-send memo — no more than a page — with a single verdict line: **CLEAR TO SEND** or **HOLD**, followed by the Check A table and any STOPs. Log the result to the deal-terms register so the next round starts from a known state. Then stamp the Notion pipeline row per the standing rule below.

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

### Automatic Price Renegotiation Flags

Flag any DD finding that should trigger price renegotiation:

- Environmental contamination with estimated remediation cost &gt;$50K
- Structural issues with estimated repair cost &gt;$100K
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

Both are stdlib-only; run from the skill directory. `scripts/extract_revisions.py` — Workflow 2 Step 0 and legal-intelligence Module 6 (exit 2 = ambiguous, hard stop). `scripts/audit_completeness.py` — Workflow 2A Step 5, Workflow 2B Check D, 46-Point Gate (exit 1 = blocking defect). Details: references/scripts.md.

## Changelog

- v1.8 (2026-09-10): **retention rule adopted (ORA Automation Audit R24-11).** This skill was the 4th-largest in the catalog at 6,943 words with **no growth bound of any kind** — a `## Changelog` with no cap and no extraction file. Added the 6-entry count cap and the ~2,000-char per-entry cap below, and archived v1.2 in the same pass so adding this entry did not breach the rule it introduces. **No workflow, DD checklist item, buyer protection or 46-Point Gate check changed** — documentation discipline only. Known grandfathered outlier: v1.3 is 2,027 chars, 27 over the cap; the caps bind entries written from here on rather than rewriting history.

**Retention rule (added 2026-09-10, ORA Automation Audit R24-11):** keep at most the **6 most recent versions** as full inline entries. The edit that would add a 7th must, in the same pass, compress the oldest full entry to a one-line `**vX.Y (date):** Full text: versions/CHANGELOG-vA.B-vX.Y.md` summary and append its full original text to the versions file for that range. **Per-entry cap ~2,000 characters** — an entry that would exceed it states its finding and verdict inline and cites the deal folder or `versions/` file for the detail. Check both caps in the pass that adds an entry — never as deferred cleanup. Full rule text and calibration: `versions/CHANGELOG-v1.3-v1.7.md`.

- **v1.7 (2026-08-24) — full text: `versions/CHANGELOG-v1.3-v1.7.md`.** PD/PUD item added to the Title & Survey DD checklist (20 → 21 items); procedure in `ora-flood-zoning-dd` Step 6A. Archived 2026-09-22 under the retention rule.
- **v1.6 (2026-08-21) — full text: `versions/CHANGELOG-v1.3-v1.7.md`.** Adversarial review: Lease-Chain landlord check tied to `title-exam-abstraction` vesting; 2A item 12 / Workflow 3 cross-fallbacks; DD-checklist items point to `estoppel-request-generation` and `title-exam-abstraction`; bare "estoppel" trigger narrowed. Archived 2026-09-22 under the retention rule.
- **v1.5 (2026-08-21) — full text: `versions/CHANGELOG-v1.3-v1.7.md`.** LEASE-CHAIN INTEGRITY added to Workflow 3; 2A item 12 extended to the full instrument chain and manuscript amendments. Archived 2026-09-22.
- **v1.4 (2026-08-15) — full text: `versions/CHANGELOG-v1.3-v1.7.md`.** File-naming citations repointed to the Global Operating Prompt v3.0. Archived 2026-09-22.
- **v1.3 (2026-08-01) — full text: `versions/CHANGELOG-v1.3-v1.7.md`.** Workflow 2 Step 0 revision-encoding detection (`scripts/extract_revisions.py`); new Workflow 2B outbound gate; 46-Point Gate (was 42) exhibit-population items (`scripts/audit_completeness.py`). Archived 2026-09-22.
- **v1.2 (2026-07-08) — full text: `versions/CHANGELOG-v1.0-v1.2.md`.** Archived 2026-09-10 under the retention rule above to hold the 6-entry cap while v1.8 was added.
