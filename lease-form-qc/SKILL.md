---
name: "lease-form-qc"
description: "Pre-execution QC gate for leases on Oxford Realty Advisors' own landlord form. Use when the user says: QC this lease, check this lease before signing, lease form check, run the lease QC, review our lease draft, or uploads an ORA-form lease DOCX. Run before ANY outbound lease goes to a tenant or broker: 60 checks (cross-refs, undefined terms, OpEx, statutory cites, rent arithmetic), PASS/FAIL. ALSO the sole path for grading an existing lease against its LOI: does the lease match the LOI, LOI vs lease, LOI conformance (LOI-Lease Audit mode; no lease yet = lease-generation). Not legal-intelligence (counterparty paper) or deal-execution 2A (PSA vs LOI)."
---

# Lease Form QC — Oxford Realty Advisors own paper (v2.9: v2.7-standard checks F19–F21; v2.8 LOI-Lease Audit mode + T3/T4/D1/D2 + --loi-audit)

Pre-execution gate for leases drafted on the ORA landlord form. Run BEFORE a draft
goes to a tenant, broker, or counsel. This is a defect scan of **our** paper — for
counterparty leases and PSAs use `legal-intelligence`.

Two questions, two modes. **"Is this lease clean?"** → the 60-check scan below.
**"Does this lease match the LOI?"** → the LOI ↔ Lease Audit (standalone mode,
v2.7; scripted v2.8) further down — `--loi-audit` runs the scan and the matrix in one call;
the intake and reverse pass are the work the scanner cannot do. If there is no drafted lease yet, the request is
`lease-generation`, not this skill.

## Ratified standing positions (Gabriel Goldberg, 2026-08-03)

These six were open decision gates. They are now **settled ORA policy** and are baked
into `ORA_MasterLease_ShallowBayIndustrial_v2.3_TEMPLATE.docx`. Apply them by default;
do not re-ask unless the deal presents a specific reason to depart.

| # | Position | Drafting consequence |
|---|---|---|
| 1 | **Modified gross**, tenant pays its proportionate share of increases over a base year. Base year = **the calendar year in which the Commencement Date occurs.** | Never label rent "net base rent" — that label is the A7 defect. Keep calendar-year accounting (matches Franklin County tax billing and ORA's books). No annualization of the base is needed: the Building incurs a full calendar year of cost regardless of when the tenant takes possession. |
| 2 | **Co-tenancy, not a guaranty.** Individuals are joined as joint-and-several co-tenants. | No guaranty exhibit. Conform insolvency language to "**if Tenant, any person or entity comprising Tenant, or any guarantor of this Lease**…" so it reaches co-tenants. Accept that co-tenants hold full tenant rights (notice, cure, possession). External AI reviewers will recommend a separate personal guaranty — that recommendation is **rejected as settled policy**, not an open question. |
| 3 | **Security deposit = 1.0× monthly rent.** | Do not propose 2 months absent a specific credit concern. |
| 4 | **Late fee 10% + 18% default interest**, retained. | Known penalty-characterization risk, consciously accepted. Do not silently reduce to 5%. The 18% now carries a lesser-of-maximum-lawful-rate savings clause (added 2026-08-03) — that clause preserves the rate, it does not soften it. |
| 5 | **Flat Hazardous Materials ban — no retail-product carve-out.** | Keep the environmental section absolute. Maximum landlord leverage is the deliberate choice. When the tenant's use plausibly involves packaged chemicals, note the day-one-breach/waiver risk in the report, but do not insert a carve-out. |
| 6 | **No extension option** by default. | Preserves mark-to-market flexibility. If an option is ever added, total possible term may exceed three years, triggering the R.C. 5301.01 acknowledgment (notarization) requirement. |

## External AI review intake (formalized v2.2)

When Gabriel supplies one or more external LLM reviews of ORA paper, run this protocol
(proven on the v2.2 reviews 2026-08-03 and the v2.4.1 ChatGPT/Grok/Gemini reviews
2026-08-04):

0. **Review-packet rule (added v2.3):** external AI reviews of ORA paper must be run on
   the master **and Exhibit B (Rules & Regulations) together** — never the bare master.
   Reviewers who see only the master report the operational package (roof, floor loading,
   exterior storage, plumbing, docks, utility capacity) as "missing"; this false finding
   recurred in both the 2026-08-04 v2.4.1 and v2.5 cycles. If a supplied review shows no
   awareness of Exhibit B, note it in the report and rule those points ALREADY DONE.
1. **Verify every factual claim against the document XML before ruling** — extracted
   text hides Word's numbering layer, footers and exhibit attachments; expect
   hallucinated defects (fake typos, "no numbering", "missing" provisions that exist).
2. **Screen every suggestion against the six ratified positions** — tenant-side edits
   (late-fee/default-rate reductions, entry notice, tiered holdover, audit rights,
   expense caps, SNDA-by-default, tenant self-help/offset, guaranty restructure) are
   rejected wholesale on landlord paper.
3. **Check whether the reviewer saw Exhibit B** — operational-package recommendations
   are usually already implemented there; rule them ALREADY DONE, not accepted.
4. **Rule each point** with the taxonomy AGREE / PARTIAL / REJECT / ALREADY DONE /
   FACTUALLY FALSE / DECISION GATE / COUNSEL PASS / DEFER-v3.0, one-to-two-sentence
   reasoning each, and verify quantitative claims (occurrence counts) directly.
5. **Route accepted edits** as asserted-count substitutions on the controlled master
   (never hand-edits to property templates), then rerun this QC and the
   masterlease-jurisdiction-rebase engine.

Reference adjudications (Claude Lease Project Outputs): 2026-08-04_MasterLease-v2.4.1_External-Review-Adjudication_Memo_v01.docx
(18 edits + 4 gate adoptions -> master v2.5) and 2026-08-04_MasterLease-v2.5_External-Review-Adjudication_Memo_v01.docx
(11 edits + Exhibit B v1.2 -> master v2.6; zero gates re-opened).

## Adjudicating external AI reviews of ORA paper (added v2.1)

Three external models reviewed template v2.2 on 2026-08-03. Lessons that generalize:

- **Verify every factual claim against the XML before acting.** Two models
  independently reported a "Demised Premisess" typo that does not exist anywhere in
  the document, and one claimed "no sections are numbered" when 35 Heading-1 sections
  carry style-based auto-numbering. External reviewers cannot see Word's numbering
  layer from extracted text and will hallucinate agreement with each other.
- **One real catch survived verification:** a numeric self-reference ("this Section 24
  shall be self-operative") broke when a section insertion shifted Subordination from
  24 to 25. Fix pattern: replace numeric self-references with "this Section" — now
  check F7.
- **Screen every suggestion against the ratified positions first.** Tenant-side edits
  (indemnity carve-outs for landlord negligence, entry-notice requirements, late-fee
  reductions, tenant self-help/offset, holdover reduction to 125–150%, landlord
  condition representations against as-is delivery) are drafted for the wrong client
  and are rejected wholesale on landlord paper.
- **Genuinely valuable additive material goes to the Rules & Regulations exhibit, not
  the lease body:** roof-penetration controls, exterior storage/trailer/container
  bans, truck parking, loading-dock rules, plumbing/floor-drain abuse, utility-capacity
  disclaimer, security and business-interruption disclaimers, CO/permits warranty,
  pest and mold responsibility. The lease already binds Tenant to promulgated rules;
  an exhibit keeps the form stable and lets rules evolve without re-papering.

## Why this exists

An audit on 2026-08-03 scanned six ORA-form leases spanning 2021–2026 (386 Morrison
08-2021, 410 Morrison 11-2022, 2822 Banwick 04-2025, 420 Morrison 10-2025, 2018
Zettler 02-2026, 388 Morrison/Shefler 08-2026). Result: **each failed 34–36 of the
original 39 checks** (39 of 42 current checks for the Shefler lease). Defects are
inherited from the base form, not introduced deal by deal. The SharePoint lease
library holds ~106 documents on this form.

Root cause: **cross-property contamination.** The Zettler building block (ZIP 43232)
was pasted into Morrison Road paper (correct ZIP 43213 — verified against Franklin
County Auditor parcel 010-208204, ZIPCD 43213, BLDGAREA 31,200) sometime between 2022
and 2025, and propagated forward. New leases were being spun from the last executed
lease rather than a controlled master, so every correction died with the deal it was
made on. The template now cites the county parcel number in the building description
— keep that pattern for every property.

## How to run

### Step 1 — Automated scan

```bash
python3 scripts/lease_qc.py <lease.docx|pdf|txt> [more ...] [--allow-tokens]
                            [--no-ocr] [--json]
```

Extraction, the OCR fallback, the UNREADABLE gate, and the report/CLI harness come
from the shared `ora_doc_qc.py` (also used by `pma-qc` and `listing-agreement-qc`). The
module is not vendored inside this skill's `scripts/` directory — `tools/package_skills.py`'s
`SHARED_ROOT_DEPS` injects a copy from the repo root at packaging time, landing at
`scripts/ora_doc_qc.py` inside the packaged `.skill` so lease-form-qc installs and runs
standalone. In a raw repo/worktree checkout, `lease_qc.py`'s sys.path fallback resolves
the repo-root `tools/` copy instead. DOCX is read from `word/document.xml`, PDF via
`pdftotext` with an OCR fallback, and plain text directly — useful for bulk-scanning
historical leases pulled from SharePoint. The report opens with a FILE / EXTRACTION /
ENC / RESULT block, then one line per FAIL with severity (BLOCK / HIGH / MED / LOW).

**Exit codes: 0 = clean, 1 = one or more failures, 2 = usage / extraction /
UNREADABLE.** Exit 2 is the important one: a document that will not yield enough text
to scan (a scanned PDF with no text layer, OCR unavailable) now gets **no QC verdict
at all** rather than a fabricated one. Before v2.5 a PDF was read as if it were UTF-8
prose and reported ~16 mojibake "failures" including BLOCKs. Never report a QC result
for a file that exited 2 — supply a text-layer copy, or install poppler-utils +
tesseract.

Benchmarks (scanner v2.9, 60 checks = 54 defect checks + T1–T4 + D1 + D2): untouched ORA-form lease
fails the v2.8 count **+3** (F19–F21; measured 2026-10-06: 2016 Zettler 4.6.2026 lease 50→**53**, 2824 Banwick
12-25 lease 52→**55** — the older ≈39–48 range predates T3/T4/D1/D2 and is no longer a benchmark); a v2.4.1-derived lease fails exactly F10–F13 (+F14–F21); a
v2.5-derived lease fails exactly **F14–F21**; a v2.6-derived lease fails exactly **F19–F21**;
a v2.7-derived lease = **0 of 60** (v2.9, 2026-10-06: the v2.7 master and all six rebased
property templates — MD-Columbia, MD-Easton, MD-Salisbury, MO-Raytown, OH-Columbus Morrison,
OH-SingleTenant-NNN — re-run directly, all 0 of 60). v2.8 note on the v2.6 master (the OH
master fixture in this repo re-verified directly at v2.8: T2–T4, D1 and D2 do not fire; T2 does not fire — its footer complex
fields are PAGE/NUMPAGES page numbering, not FILENAME/DOCPROPERTY. The five rebased
state-conformed property templates this repo does not carry a local copy of were not
independently re-run for this change; confirm the same 0-of-57 on them before relying
on this benchmark for those files).
The scanner also enforces a **T1 token gate**: any
unfilled `[TOKEN]` **in the body or the footer** of a file whose name lacks
`_TEMPLATE` is a BLOCK failure (drafted leases must be fully filled; pass
`--allow-tokens` to scan a working draft). The footer half matters — the master's
footer carries `[PREMISES ADDRESS]` and `[TENANT ENTITY]`, and a token fill that
edits only the body leaves them printing on every page. Anything
above 0 on a template-derived lease means a token fill introduced a defect. **Scan clean or accepted documents only** — a tracked-change
redline contains both old and new text and will spuriously fail (~15 checks); run
`accept_changes.py` first.

### Step 2 — Check revision encoding before reporting "no changes"

A Litera / Workshare / Word-compare output carries **zero** `<w:ins>`/`<w:del>`
elements and encodes revisions as strikethrough plus coloured underline. Counsel
comments live in `word/comments.xml` and are invisible to a tracked-change parse.
State the detected encoding at the top of every report.

The scanner does this for you. The ENC line distinguishes all three states:
`tracked changes: <n>` (real OOXML `w:ins`/`w:del`), `compare-tool formatting
(strikethrough), no tracked changes` (Litera/Workshare/Word-compare output — run
`accept_changes.py` before believing the ~15 spurious failures), and `no tracked
changes (clean)`. It also reports `comments.xml: yes|no`.

### Step 3 — Report

Table: Class · Section · Status · Severity · Recommended fix. Then any item where the
deal departs from a ratified standing position above.

---

## Defect classes

### Class 1 — DEAL-BLOCKING

| ID | Defect |
|---|---|
| A1 | **ZIP / address conflict.** Section 1 premises ZIP contradicts the Section 4 building-block ZIP. Morrison Road = 43213 (county-verified); Zettler Road = 43232. Verify against the Franklin County Auditor parcel record, never against another lease. |
| A6 | **Operating-cost pass-through has no billing machinery** — no estimates, no annual reconciliation, no payment window, no survival. Unenforceable in practice. |
| A7 | **"Net base rent" label on a base-year structure.** Contradicts ratified position 1. Delete "net." |
| A11 | **Audited financial statements** demanded of small tenants who will never produce them — perpetual technical default, worthless covenant. |
| B7 | **Notices fail where they matter.** Tenant's only notice address is the Demised Premises; individual co-tenants get no separate address. Under ratified position 2 co-tenants must be independently noticed. |

### Class 2 — DEAD & FRAGILE CROSS-REFERENCES

- **A2** — "RIGHTS RESERVED BY LANDLORD" cited but the section does not exist in the
  legacy form. Fix by *adding* the section (landlord-protective), not striking the reference.
- **A2b** — "INSPECTIONS, REPAIRS AND INSTALLATIONS" cited; actual heading is "ENTRY
  FOR INSPECTIONS, REPAIRS AND INSTALLATIONS." A second occurrence drops the plural.
- **A3** — "ALL RISK PROPERTY INSURANCE" cited; actual heading is "INSURANCE."
- **A9** — Prevailing-party carve-out cites DEFAULT OF TENANT; the landlord-only fee
  rule lives in REMEDIES.
- **F7 (new)** — **Fragile numeric self-references** ("this Section 24 shall be
  self-operative"): any inserted section shifts auto-numbering and silently breaks
  them. Confirmed live: adding Rights Reserved moved Subordination 24→25. Use "this
  Section" for self-references; verify all remaining numeric refs (2(a), 11) against
  live numbering after ANY section insertion or reorder.

### Class 3 — UNDEFINED OPERATIVE TERMS

`Project`, `Building`, `Premises` (vs. `Demised Premises`), `Business Day`,
`Governmental Agency`, `Lease Term`. Standard definitions block goes under DEMISED
PREMISES (Building = county parcel-cited address + RSF; Project = Building + land +
common areas; Business Day = weekdays excl. Ohio bank holidays; Lease Term = term +
extensions + holdover). Match **any quote style** when testing for a definition —
the form mixes straight and curly quotes.

### Class 4 — OBSOLETE / WRONG STATUTORY CITATIONS

CERCLA: 42 U.S.C. § 9061 → **§ 9601**. HMTA: 49 U.S.C. § 1802 → **§ 5101** (recodified 1994).

### Class 5 — OHIO LAW EXPOSURE

- **B2** — Unqualified no-mitigation disclaimer vs. *Frenchtown Square Partnership v.
  Lemstone, Inc.*, 99 Ohio St.3d 254, 2003-Ohio-3648. Add "except to the extent
  required by applicable law."
- **B3** — Acceleration without reletting-proceeds credit invites a penalty attack.
- **F8 (new)** — 18% default interest should carry a **usury savings clause** (lesser
  of 18% or maximum lawful rate). Preserves the rate under ratified position 4.
- **R.C. 5301.01** — total possible term (including options) over three years requires
  acknowledgment. Position 6 keeps terms short; still check every option.
- Jury waiver and subrogation waiver enforceable; no Ohio commercial deposit statute.

### Class 5a — v2.5 STANDARD PROVISIONS (added v2.2)

- **F10** — venue clause (courts of the county where the Project is located; tokenless, rebase-safe).
- **F11** — indemnity carve-out for losses waived under the INSURANCE waiver of subrogation.
- **F12** — "Governmental Agency" and "Building Standard" defined.
- **F13** — Operating Costs exclude amounts separately billed to / paid directly by tenants.

### Class 5b — v2.6 STANDARD PROVISIONS (added v2.4)

- **F14** — "All Risk (Special Form) Property insurance" — modernized policy-form terminology.
- **F15** — Landlord exculpation enumerates managers, members, officers, employees, agents.
- **F16** — assignment/sublease excess-rent (profit) capture, net of documented brokerage.
- **F17** — continuous prepaid annual HVAC preventative-maintenance contract, copy delivered annually.
- **F18** — footer carries the ORA Master Lease form-version tag (vintage forensics).
- **T1** — unfilled-token gate on non-template files (BLOCK; `--allow-tokens` to override).

### Class 5c — CROSS-DOCUMENT PROVENANCE (added for the lease-generation handoff)

- **T2** — footer FILENAME/DOCPROPERTY field resolves to a tenant name other than this
  lease's own defined Tenant (BLOCK). Catches a lease cloned from a **different**
  tenant's executed lease as a drafting shortcut (instead of the property template),
  where a stale Word field in the footer still displays the old tenant's name even
  after every `[TOKEN]` has been filled — T1 cannot see this, because a field's cached
  result is not a token, it is ordinary-looking text that happens to be wrong. Handles
  a co-tenant list (ratified position 2) by checking a footer field against every
  listed name, not just the first. No FILENAME/DOCPROPERTY field in the footer at all —
  lease-generation's own output, which replaces the field with static text — passes
  cleanly by design. Can only see a Word **complex** field (`<w:fldChar>` +
  `<w:instrText>`); a **simple** field (`<w:fldSimple w:instr="...">`) stores its
  instruction in a tag attribute the shared extraction module discards along with every
  other tag, and is invisible to this check — a documented limit, not a gap to route
  around inside this file (see `_footer_field_candidates()`'s comment).

### Class 5d — INTERNAL CONSISTENCY / EXECUTION READINESS (added v2.8)

Four checks that read only what the shared extractor already provides (body, footer,
file name); `ora_doc_qc.py` is unchanged. IDs **D1/D2** (the v2.8 brief called them
C1/C2) avoid the existing Class 6 `C1`/`C2`.

- **T3** — unfilled underscore blanks (`_____`, five or more) in body or footer of a
  non-`_TEMPLATE` file (**HIGH**, not BLOCK: a blank tenant `ATTN:` line is a notice
  defect a party can cure by hand, not a fabricated-verdict risk like T1's unfilled
  `[TOKEN]`). Honors `--allow-tokens`. Execution copies legitimately carry blank
  signing lines, so each blank is judged by the label nearest it (the 40 characters
  before it; for a bare rule line the line above, the caption after, and the line
  below): `Signature`, `Signed`, `By:`, `Date:`, `Print Name`, `Name:`, `Title:`,
  `Its:`, `day of`, `, 20__`, `(SEAL)`, Initials, Witness, Notary. `Date:`/`Name:`
  preceded by another word (`Commencement Date:`) is not a signing label. `ATTN:`,
  `Email:`, notice-address lines and blanks inside a rent, deposit, SF, parcel or
  commencement sentence fire. Detail = count + first six matches with leading context.
- **T4** — exhibit / schedule stubs (**BLOCK**, non-template): `TO BE ATTACHED`
  (`… PRIOR TO EXECUTION`), `TO BE INSERTED`, `TO BE PROVIDED`, `[ATTACH`,
  `PLACEHOLDER`, and an `EXHIBIT X` / `SCHEDULE X[-n]` heading with under 40 words of
  content and no embedded drawing. Limits: the drawing test is document-level
  (any `word/media/` part, a letterhead logo included, disables the heading test —
  the phrase test still runs) and needs the file path, which the CLI registers;
  a bare exhibit *list* (consecutive headings, no text) is treated as a list, not stubs.
- **D1** — Basic Lease Information ↔ body drift (**MED**, only when a BLI block
  exists): Security Deposit, Monthly Rent, Annual Base Rent, Proportionate Share,
  Parking, Late Fee, Default Interest (annualized figures only), Escalation, and the
  Utilities scope set vs the SERVICES AND UTILITIES section. Fires once per label that
  the body states differently; an absent body statement or token-valued BLI line is
  silent. Dollars compare to the cent.
- **D2** — rent-schedule arithmetic (**HIGH**, silent when no schedule table): Year 1
  = PSF × RSF (within 2-dp PSF rounding) and annual/12 = monthly; later rows must
  reproduce under ONE method — annual-compounded or monthly-rounded — to the cent.
  A row matching neither, or rows split across the two methods, fail unless the lease
  says the schedule controls. Tables with a PSF column or monthly-before-annual parse
  correctly; a multi-year row (`Years 3-5`) ends verification at that row.

### Class 5e — v2.7 STANDARD PROVISIONS (added v2.9)

Lessons from the FCSS / 9620 State 350 negotiation, applied to the master on 2026-10-06.

- **F19** (HIGH) — NOTICES (B) still reads "if to Tenant, at the Demised Premises." **B7 cannot see
  this**: B7 passes as soon as any Tenant notice-address paragraph exists, while clause (B) keeps
  routing every Tenant notice to the premises only — useless before occupancy and after abandonment.
  v2.7 wording: notice address set forth below and, from the Commencement Date, also the premises.
- **F20** (MED) — escalating rent ("second Lease Year") with no controlling rent schedule, or the
  v2.6 `[OPTIONAL: ATTACH RENT SCHEDULE …]` bracket left in. The schedule is mandatory from v2.7
  and controls over the escalation sentence; D2 then verifies its arithmetic.
- **F21** (MED) — no late-signing commencement clause. v2.7 shifts the Commencement Date to the
  first full month after full execution when the lease is not signed by the 15th of the preceding
  month (expiration, Lease Years, schedule and base year shift with it). In the standing counsel
  scope. Expected to fire on vintage-form deal leases (e.g. FCSS v5) — informational there.

### Class 6 — MISSING PROVISIONS

No-recording · Landlord default standard · Force majeure · OFAC · Counterparts/
e-signature · Time of the essence · Personal property taxes · Exhibit A premises
depiction with stipulated non-remeasurable SF · Rent schedule table · County parcel
number in the building description.

### Class 7 — OTHER SUBSTANTIVE GAPS

A8 corporation-only authority clause · A10 circular Delay-in-Commencement · B4
ambiguous holdover formula (keep the 200% rate, fix the arithmetic) · B5 unallocated
HVAC replacement (Landlord replaces at end of useful life, amortized into Operating
Costs, unless Tenant's maintenance default) · B6 insurance gaps (CGL aggregate,
Employer's Liability, contractor minimums, annual COI delivery) · B8 water billing
mechanism · B11 guarantor/co-tenant conform per position 2 · Rent proration by actual
days in month, not 1/30th.

### Class 8 — TYPOGRAPHY AND MECHANICS

"his agents" → "its" · "succeeding Lease or succeeding tenant" · "a comparable
publications" · "Interior lighting" stray capital · "tenant shall provide" lowercase ·
"under seal" · missing comma in building address · empty Heading-1 spacer paragraphs
before the signature block · **F9 (new)** non-breaking-space artifacts in operative
text (legacy Word residue; also masks regex-based QC checks) · F6 Business-Day late
fee vs calendar-day cure (passes once Business Day is defined) · blank execution date.

### Class 9 — CLAUSE ORDER

Sequencing defects in the legacy form (Security Deposit after Assignment; Landlord
Cure stranded; Financial Statements after Miscellaneous). Reordering is optional —
if done, re-verify every numeric cross-reference (see F7).

---

## `--loi-conformance` mode (added for the lease-generation handoff)

```bash
python3 scripts/lease_qc.py --loi-conformance <deal-terms-register.json> <lease.docx> [--json]
```

Replays lease-generation's own "LOI conformance matrix" gate (that skill's SKILL.md
"3. Gates", item 4) as a scanner-owned, testable output instead of a manual judgment
call: loads a `deal-terms-register.json` (schema at
`lease-generation/references/deal-terms-register.schema.json`), reads the drafted
lease's text, and emits one row per field category — landlord, tenant, co_tenants,
premises, use, term, options, rent, expense_structure, utilities, security_deposit,
parking, landlord_work, maintenance, insurance, broker, signage (17 total) — each a
**CONFORMS / CONFORMS+ / PARTIAL / MISSING / CONFLICT** verdict. Not every schema leaf
has its own row: `special_provisions` (a heterogeneous array of ad-hoc clauses with no
fixed shape to match against) and a handful of already-covered categories' own
sub-fields (`utilities.gas`/`.trash`, `parking.allocation`/`.vehicle_class_cap`) are not
independently verified — treat a CONFORMS row as "the fields this mode checks conform,"
not "every negotiated term in this category was verified," and cross-check those
specific sub-fields by hand. Text and `--json` report shapes both follow the standard
scan mode's conventions. Exit codes: **0** = every row CONFORMS/CONFORMS+, **1** = at
least one PARTIAL/MISSING/CONFLICT row (matches the matrix gate: "nothing ships with
PARTIAL/MISSING/CONFLICT unless Gabriel resolved it"), **2** = usage / register-load /
lease-UNREADABLE error, including a malformed register (not a JSON object) or a missing
lease file — a single malformed FIELD inside an otherwise-valid register degrades just
that row to MISSING (with a `could not evaluate` detail) rather than crashing the whole
matrix. This is a separate code path from the standard 60-check scan (different question, different
source of truth, different output shape) and does not add to `checks_run`.

---

## LOI ↔ Lease Audit — standalone mode (added v2.7)

**Trigger:** an LOI and a drafted lease arrive together and the question is "do they
match" — whoever drafted the lease (broker, counsel, a prior session, or
`lease-generation`). This is the grading twin of `lease-generation` Gate 4 (which runs
*inside* production) and of `deal-execution` Workflow 2A (PSA vs LOI, buyer side). The
matrix alone answers only "is every LOI term in the lease"; a lease that conforms on the
matrix can still carry a term the LOI never contemplated, an unanswered tenant question,
an exhibit stub, or a blank signature block. Run all five steps; report from the memo
structure in Step E. Deterministic throughout — no clarifying questions unless a
material financial assumption is genuinely ambiguous.

### Step A — LOI intake (the part no scanner can do)

1. **Operative version.** Read the header stamps ("Landlord Response m/d/yy", "Tenant
   Revised m/d/yy"), the signature block (who signed, title, date) and whether Landlord
   countersigned. A tenant-signed counter without Landlord countersignature is the
   tenant's *offer*; a lease drafted to that version is the operative acceptance — say
   so in the memo. The LOI's non-binding clause does not change this.
2. **Redlined LOI PDFs.** `pdftotext` flattens strikethrough and underline into one
   text stream: every struck phrase reads as live text ("on or about Octoberupon the
   latter of November 1"). Render the pages (`pdftoppm -r 130 -png`) and read the
   images to classify struck vs. inserted before building the register. Never build a
   register from the flattened text of a redline. Same rule for Litera/Workshare LOIs.
3. **Tenant comments embedded in the LOI** ("How are sewer and water being
   sub-metered?") go into the register's `open_items`, one per question. Each must be
   answered by the lease or by a stated property fact. A tenant question the lease
   silently contradicts is a **CONFLICT**, not a MISSING.
4. **Garble and undefined abbreviations** ("and DFH") are open items addressed to the
   drafting broker by name, never guessed at.
5. **Internal LOI contradictions** (inspection right "within 30 days of the
   Commencement Date" beside delivery "prior to the commencement date") are recorded
   as such; note which reading the lease adopted and whether it is the landlord-favorable
   one.

### Step B — Register and matrix

Build `deal-terms-register.json` per `lease-generation/references/deal-terms-register.schema.json`,
every field sourced to an LOI section number. Then:

```bash
python3 scripts/lease_qc.py --loi-audit <register.json> <lease.docx> [--json]
```

One call: the standard 60-check scan (T3/T4/D1/D2/F19–F21 included), then the conformance
matrix (18th row `open_items`: every register open item needs a non-null `resolution`
and its `lease_clause` present in the lease; string items are unresolved), then
`AUDIT: <scan failures> scan failure(s) [<n> BLOCK] · <rows> matrix row(s) · exit <code>`.
Exit = max of the two components (2 > 1 > 0). Decomposed form, same results:
`--loi-conformance <register.json> <lease.docx>` plus `python3 scripts/lease_qc.py <lease.docx>`.

Hand-check the sub-fields the mode documents as unverified (`special_provisions`,
`utilities.gas/.trash`, `parking.allocation/.vehicle_class_cap`).

### Step C — Reverse pass: BEYOND-LOI terms

The matrix is register → lease only. Walk the lease and list every operative term with
no LOI antecedent, classed:

| Class | Meaning | Disposition |
|---|---|---|
| **STANDARD-FORM** | Master boilerplate and ratified positions (late fee / default rate, assignment recapture + profit share, no-recording, relocation right, Tenant Delay, deemed acceptance, landlord-default no-offset) | List once; no action. Flag relocation when the Landlord Work is tenant-specific (custom build-out, shielding, anchoring) — it will be struck and undermines the tenant-facing tone. |
| **NARROWING** | Lease grants an LOI term but bounds it in a way the LOI did not (retaining an existing furnace inside a "new HVAC system"; carving the PM contract out of an HVAC repair cap; a fair-market floor at last-year rent; a designated area where the LOI said "outdoor areas") | Landlord-favorable negotiating positions. Report as positions, not conformance defects, and recommend they be disclosed to the tenant's broker rather than left to be discovered. |
| **USE-CONFLICT** | A form prohibition that may defeat the LOI's stated use (blank/simulated-munitions ban vs. a security training facility; flat Hazardous Materials ban vs. a packaged-chemicals user) | Must be confirmed with the tenant before release. Ratified position 5 is not softened — the *finding* is reported, per the position's own instruction. |
| **MISSING-GRANT** | An LOI grant with no lease clause at all (early access, hose bib, pylon panel) | Conformance defect. Fix before release — draft the clause landlord-bounded per `lease-generation/references/clause-modules.md`. |

### Step D — Mechanics (deterministic; scripted in v2.8 — check IDs below)

1. **Rent schedule arithmetic** (**D2**). PSF × RSF = Year-1 annual; recompute every year under
   the lease's *stated* method (compounding on rounded monthly rent vs. on annual). Any
   cent variance must be explained by the stated rounding rule, and the lease must say
   the schedule controls. Option-term rent basis stated.
2. **Proportionate share** = premises RSF ÷ building RSF, two decimals, building RSF
   verified against the property's executed leases / Notion Property Register, not the
   LOI.
3. **BLI ↔ body** (**D1**). Every Basic Lease Information line has a body counterpart with the
   identical value (watch scope drift: "water" vs. "water and sewer"). Body controls;
   conform the BLI anyway.
4. **Exhibit completeness** (**T4**). Every exhibit the body references exists; any "TO BE
   ATTACHED", "TO BE ATTACHED PRIOR TO EXECUTION", schedule stub, or exhibit consisting
   of placeholder text is an execution blocker. Where an exhibit needs a drawing, confirm
   an image is embedded (`word/media/`) — "outlined in red below" with nothing below is a
   stub.
5. **Blank-field scan** (**T3**). Underscore runs (`_____`), "day of ______, 20__", ATTN / e-mail
   lines, signature-block names and titles. T1 sees `[TOKENS]` only; underscores are
   invisible to it.
6. **Parties.** Entity name and state of organization vs. the LOI — and vs. any LOI
   request that the tenant supply its entity → Secretary of State verification item.
   Landlord signatory vs. the manager of record for the property LLC; notice block
   complete.
7. **Commencement chain.** Each LOI delivery condition maps to a lease Delivery
   Condition; each LOI "no later than" maps to a hard date; each LOI outside date to a
   remedy. A softened condition (CO "or equivalent" widened to "existing certificate or
   final inspection approval") is reported as a NARROWING, not silently accepted.

### Step E — Report

Memo, ORA style guide, named `YYYY-MM-DD_[Tenant]-[Property]_LOI-Lease-Conformance_Memo_v##`,
saved to the Leases project and mirrored to SharePoint when the destination is known:

1. **Bottom line** — one paragraph: economics conform / N deviations / N defects / N blockers.
2. **Conforming terms** — table: LOI § · term · lease clause · ✓ (with any benign
   variance noted inline, e.g. the $0.03 rounding case).
3. **Deviations** — numbered, each with LOI § · lease clause · class from Step C ·
   action. Conformance defects (MISSING-GRANT, CONFLICT, unanswered open item) first;
   NARROWING positions second; STANDARD-FORM last.
4. **Execution blockers** — exhibits, blanks, entity/signatory verification,
   countersignature status.
5. **Recommended sequence** — defects fixed before release; positions decided; what to
   concede to hold what.

Reference run: First Coast Security Solutions / 9620 E. State Rte 350 Raytown, Unit
107-108 (2026-09-24) — 17 conforming, 9 deviations (2 conformance defects: water
metering contradicted an open tenant question; early access absent), 6 execution
blockers. Memo: `2026-09-24_FCSS-9620-Raytown-LOI-Lease-Conformance_Memo_v01.md`
(Leases project).

### Shipped in v2.8

T3, T4, D1, D2, the `open_items` matrix row and `--loi-audit` implement Step D's mechanics and Step B's single entry point.
The reverse pass (Step C) remains a judgment step — no scanner reads a lease for terms the LOI never contemplated.

## Decision gates — never fix unilaterally

Only genuine departures from the six ratified positions get comments now. Gate rulings
2026-08-04 (Gabriel): ADOPTED into master v2.5 — Basic Lease Information page (body
controls on conflict), relocation right (Rights Reserved clause (h)), assignment
recapture, CC&R compliance. REJECTED as defaults (deal-by-deal concessions only) —
SNDA/non-disturbance (pure subordination remains the landlord default),
affiliate-assignment carve-out. Remaining counsel-pass items: attorney-in-fact
estoppel, R.C. Ch. 1923 self-help/notice-to-quit waiver, acceleration formula,
gross-up methodology.

## Output

- Redline deterministic fixes as **real tracked changes** (`<w:ins>`/`<w:del>` with
  author and date), never clean overwrites.
- **Normalize runs before editing** — split multi-`<w:t>` runs into one-`<w:t>` runs
  first; a splitter that keeps only the first `<w:t>` silently truncates paragraphs.
- Validate with the `docx` skill's `scripts/office/validate.py <out> --original <in>
  --author "<author>"`; must report **All validations PASSED**.
- Deliver the QC report as a DOCX per the ORA Institutional Style Guide (EB Garamond /
  DM Sans / IBM Plex Mono; Navy #1B2A4A, Gold #C9A96E, Parchment #F5F3EF), named
  `YYYY-MM-DD_[Property]_Lease-QC_v##.docx`.

## Preventing recurrence

Draft new leases from **`ORA_MasterLease_ShallowBayIndustrial_v2.6_TEMPLATE.docx`** (accept the
tracked v2.5→v2.6 changes when drafting) with
**`ORA_MasterLease_ExhibitB_RulesAndRegulations_v1.2_TEMPLATE.docx`** attached as Exhibit B
(0 of 46; all six positions encoded; BLI page, venue, subrogation carve-out, OpEx separate-billing exclusion included; deal terms tokenized; parcel-number pattern
included). Never copy the last executed lease. After filling tokens, run this QC
anyway — token fills introduce their own errors. **After inserting or removing any
section, re-verify every numeric cross-reference** — that is exactly how the v2.2
Section 24 defect was born.

## Changelog

### v2.9 (2026-10-06) — v2.7-standard checks F19–F21

`checks_run` 57 → **60**. Additive: no existing ID, severity, title, regex or logic changed; `tools/ora_doc_qc.py`
untouched. **F19** NOTICES (B) premises-only (HIGH — B7 blind spot), **F20** mandatory controlling rent schedule
(MED), **F21** late-signing commencement clause (MED). Clean benchmark moves to the v2.7 master fixture
(`masterlease-jurisdiction-rebase/scripts/fixtures/…v2.7_TEMPLATE.docx`); the v2.6 fixture is kept and now fails
exactly F19–F21 (asserted). New `TestV27Standards` (fire/silent pair per check); parity helpers exclude F19–F21
like T1–D2. Re-benchmarked: v2.7 master + six property templates 0/60; v2.6 master, MD-Columbia v2.6 and
OH-ST-NNN v2.6 each exactly F19–F21; FCSS CLEAN v5 fires F21 only among the three (vintage form, expected).

### v2.8 (2026-09-24) — LOI ↔ Lease Audit mechanics scripted

Code release completing v2.7 (`checks_run` 53 → **57**). Additive: no existing check ID, severity, regex or logic
changed; `tools/ora_doc_qc.py` untouched.

| Change | Why |
|---|---|
| **T3** underscore-blank gate (HIGH) with per-blank signing-label exemption | v2.7 handoff said BLOCK; amended to HIGH — a blank `ATTN:`/e-mail line is a curable notice defect, and a BLOCK would also risk false positives on execution copies' blank signature lines. |
| **T4** exhibit/schedule stub gate (BLOCK) | "TO BE ATTACHED" and bare exhibit headings shipped in the FCSS draft; T1 sees `[TOKENS]` only. |
| **D1** BLI ↔ body drift (MED) and **D2** rent-schedule arithmetic (HIGH) — named D, not C | The brief called them C1/C2, but `C1`/`C2` already exist (Class 6 no-recording, default-cure); renaming the new checks kept every existing ID intact. |
| `open_items` row in `--loi-conformance`; register schema `open_items` becomes `oneOf [string, {item, resolution, lease_clause, source}]` | Open items were previously never carried through; strings stay valid (unresolved). Example register updated; existing rows unchanged. |
| **`--loi-audit`** composed mode | One command runs Gate 3 + Gate 4 of lease-generation and the standalone audit; exit = max of components. |

Regression evidence: 141 tests (89 at v2.6), full suite green; OH master v2.6 fixture **0 of 57**, T3/T4/D1/D2 silent;
two independent code-review passes — pass 1: 2 Critical (D2 PSF-column and TI-allowance misreads) + 4 Important, all fixed;
pass 2: 2 Important (T3 signature-block layout, initials/witness lines) + 2 Minor, all fixed.

### v2.7 (2026-09-24) — LOI ↔ Lease Audit standalone mode

Doctrine-only change (no scanner code touched; `checks_run` still 53). Systematizes the
FCSS / 9620 State 350 run, where the question "do the LOI and the lease match up"
arrived with a broker-drafted lease and a tenant-redlined, tenant-signed LOI —
outside `lease-generation`'s pipeline, so Gate 4 never ran, and outside anything the
matrix checks (redline intake, unanswered tenant questions, terms beyond the LOI,
exhibit stubs, underscore blanks, schedule arithmetic).

| Change | Why |
|---|---|
| Description gains the LOI-vs-lease trigger phrases and routes "no lease yet" to `lease-generation` | `lease-generation`'s own description says "make the lease match the LOI", which reads as grading; the two skills now split produce/grade explicitly (mirrored in `lease-generation` v1.1). |
| Five-step audit procedure (intake → register/matrix → reverse pass → mechanics → memo) | Each step covers a finding class the matrix cannot produce. The reverse pass's four classes (STANDARD-FORM / NARROWING / USE-CONFLICT / MISSING-GRANT) separate conformance defects from negotiating positions so the memo's "fix before release" list is not padded with positions. |
| Redline-intake rule | `pdftotext` on the FCSS LOI produced "Octoberupon the latter of November" — struck and inserted text fused. A register built from that text would have carried the wrong commencement date. |
| Code-surface handoff list (T3/T4, BLI diff, schedule recompute, `open_items` carry-through, `--loi-audit`) | The mechanics are deterministic and belong in the scanner with tests; kept out of this release so the doctrine could ship without an untested code change. |

### v2.6 — T2 + `--loi-conformance` mode (lease-generation handoff)

Two additions handed off from `lease-generation`'s SKILL.md, both additive (no
existing check ID, severity, or logic changed):

| Change | Why |
|---|---|
| **T2** registered (BLOCK) | Footer FILENAME/DOCPROPERTY field naming a different tenant than this lease's own defined Tenant — the cross-contamination failure mode this skill exists to catch generally, specific to a stale field surviving a token fill. Ctx-aware (like A2/F9/F18), not `bool_check()`-wrapped: reads `ctx["meta"]["footer"]` and `ctx["raw"]`. Detects Word **complex** fields (`fldChar`+`instrText`) only — a **simple** field's `w:instr` attribute is discarded by the shared extraction module's tag-stripping and is invisible here; widening that is an `ora_doc_qc.py` change, out of this file's reach (see Class 5c). A candidate is only ever treated as a tenant claim when it occupies the documented tenant slot — a FILENAME token after a literal `Lease` marker, or a DOCPROPERTY whose property NAME itself reads tenant/lessee-labeled — after independent review reproduced false BLOCKs on address-only filenames and on ordinary metadata properties (`Company`, `DocID`, `Title`, `Manager`). Checks_run is now **53**. |
| `--loi-conformance <register.json>` mode added | A second CLI mode (dispatched before CHECKS/`run_cli()`) replaying lease-generation's "LOI conformance matrix" gate as a scanner-owned, testable CONFORMS/CONFORMS+/PARTIAL/MISSING/CONFLICT matrix across 17 field categories. Separate code path, separate source of truth (the deal's own register, not the fixed defect registry) — does not touch `checks_run` or the standard scan's severity model. Two independent review passes found and fixed: dollar-amount matching was truncating cents (a register rent stated to the cent could silently CONFORMS against a lease stating different cents); the `gross` expense-structure phrase matched "gross negligence" in any lease's exculpation clause regardless of actual structure; `term`'s CONFORMS+ was inferred from bare "early access" text rather than the register's own `term.early_access` field; a `suite` value with no word-boundary anchoring could never fail; `utilities`' key-name fallback made that row unfailable; the mode had no error containment (a missing lease file or a malformed register field raised an uncaught exception at **exit 1**, indistinguishable from a real "the matrix has blocking rows" verdict, now **exit 2**, or a contained MISSING row for one malformed field); a CPI/fixed-dollar-step escalation (not text-matchable) silently CONFORMS'd instead of reporting PARTIAL; and `landlord_work`/`signage`'s exact-phrase matching against free-text register descriptions made those two rows essentially unfailable to CONFORM even against ORA's own canonical example register (`_phrase_present()` gained a `threshold` mode: a majority of a description's significant (5+ char) words, matched anywhere in the lease text, rather than every word verbatim in one window). |

Regression evidence: 89 unit tests in `tests/` (41 new — 16 on T2 including 4 dedicated
false-positive-surface cases, 25 on `--loi-conformance` including its own dedicated
regression-fix test class — the pre-existing 48 unchanged in substance; two hardcoded
`checks_run`/"N of 52" literals bumped to 53 to reflect T2's registration). Two
independent code review passes (pr-review-toolkit code-reviewer, re-run after the first
pass's fixes since a review verdict is keyed to exact content) found 3 critical + 6
important defects on the first pass and 2 further important defects on the second,
all fixed and covered above and in `tests/`. The
OH master v2.6 fixture in this repo re-verified directly: **0 of 53**, T2 silent (its
footer complex fields are PAGE/NUMPAGES, not FILENAME/DOCPROPERTY) — the five rebased
state-conformed property templates live outside this repo and were not independently
re-run for this change.

### v2.5.1 (2026-08-17) — review fixes, before v2.5 ever shipped

Both items below were caught by independent review of the v2.5 retrofit and fixed on
the same branch, so no operator ever saw the defective behavior.

| Change | Why |
|---|---|
| **T1 scans the FOOTER again** | v2.5 registered T1 via the shared `unfilled_token_check()`, which reads the document BODY only. Footer text lives in `meta["footer"]`, a channel that helper never looks at — so removing the old `[[FOOTER]]` splice silently dropped the footer from the token gate. ORA's own v2.6 master carries `[PREMISES ADDRESS]` and `[TENANT ENTITY]` in `word/footer2.xml`/`footer3.xml`: a lease with a filled body and an untouched footer cleared T1 and would have gone out for signature with both tokens on every page. T1 is now a local ctx-aware check scanning body **and** footer with the same regex, the same two gates (`_TEMPLATE` filename, `--allow-tokens`), and the same BLOCK severity. |
| **ENC precision restored** (supersedes the v2.5 "ENC precision lost" row, now removed) | `ora_doc_qc.scan()` now carries `extract()`'s `meta["strike"]` into its report dict and `print_report()` branches on it, so the ENC line again distinguishes compare-tool strikethrough from a genuinely clean document. The Step 2 workaround heuristic this briefly required is deleted. |

Regression evidence: 47 unit tests in `tests/` (5 new, all on the footer-token path,
including one that asserts the shared body-only helper *would* have missed it and
that the v2.5 `[[FOOTER]]` false BLOCK does not return); `pma-qc` and
`listing-agreement-qc` fixtures re-run unchanged.

### v2.5 (2026-08-17) — retrofit onto the shared `ora_doc_qc.py`

Extraction, OCR fallback, UNREADABLE gate, report, and CLI now come from the shared
module. Check logic is unchanged except where noted. Intentional behavior changes:

| Change | Why |
|---|---|
| **Exit 2 added** for usage / extraction / UNREADABLE | A PDF used to be read as UTF-8 prose. Measured on a 8-word no-text-layer PDF: **16 of 51 "FAILED", 2 BLOCK, exit 1** — a verdict on a document never read. Such input now returns no QC result. |
| **T1 stopped firing on `[FOOTER]`** | `text_of()` spliced a `[[FOOTER]]` marker onto every DOCX and `TOKEN_RE` matched the inner `[FOOTER]`. On all 10 real executed ORA leases regression-tested, that was the **only** token T1 ever found — a spurious **BLOCK** on every non-`_TEMPLATE` lease. Marker gone, false BLOCK gone. |
| **F6 now fires on ORA's own paper** | ORA paper writes "five `\xa0` (5) Business Days…"; the old pipeline never folded the non-breaking space, so F6's plain-space pattern silently never matched. It fired on 8 of 10 real leases once folded — a real defect that had been invisible. |
| **A3 / A9 now catch smart-quoted cross-references** | They match an ASCII `"` class; Word emits curly quotes, so they used to miss every real instance. Neither fires on the v2.6 master. |
| **T1 is a registered check** | Was synthesized ad hoc inside `scan()`. Now in the registry, so it appears in `--json` and the denominator (**52**, not 51). |
| **F18 reads `meta["footer"]`** | Replaces the `[[FOOTER]]` parsing trick. Same four-row truth table; footer boilerplate no longer leaks into every other check's body text. |
| **Report format** | Shared `print_report()` block. Nothing parses this script's stdout; `masterlease-revision-cycle` / `-jurisdiction-rebase` gate on the exit code, unchanged. |

Regression evidence: 42 unit tests in `tests/`; 23 real ORA files (10 executed leases,
7 addenda/intake copies, 6 v2.6 templates) diffed pre- vs post-retrofit with **zero
unexplained verdict changes** — every delta traced to a row above. All six v2.6
templates: **0 of 52**, identical before and after.
