---
name: "masterlease-revision-cycle"
description: "Use when the user supplies external LLM reviews (ChatGPT/Grok/Gemini) of the ORA master lease and asks to adjudicate + implement, or says: run the revision cycle, rev the master, adjudicate and build, implement lease review feedback, new master version end-to-end. Oxford Realty Advisors end-to-end master-lease revision cycle — one command from external AI reviews to a new master revision with rebased property templates, chaining lease-form-qc external-review intake, masterlease-jurisdiction-rebase, and a pointer/ledger close-out."
---

# Master Lease Revision Cycle — Oxford Realty Advisors (v1.1)

End-to-end pipeline from external AI reviews of the ORA master lease to a shipped
master revision with rebased property templates. Extracted 2026-08-04 after the
identical structure ran twice in one day (v2.4.1→v2.5 morning cycle, v2.5→v2.6
afternoon cycle). This skill orchestrates; the domain logic lives in the three
skills it chains — never duplicate their procedures here.

## Preconditions

- Canonical master = highest `ORA_MasterLease_ShallowBayIndustrial_v*.docx` in
  `Business/Leases All properties/` (never a cached copy — drift rule in
  masterlease-jurisdiction-rebase).
- Review packet: external reviewers must have been given the master **and Exhibit B
  (Rules & Regulations) together** (lease-form-qc v2.3 review-packet rule). If a
  supplied review shows no Exhibit B awareness, its operational-package points are
  ruled ALREADY DONE, not accepted.

## Phases (all in one pass unless a decision gate fires)

**Phase 0 — Adjudicate** (lease-form-qc "External AI review intake"):
verify every factual claim against the document XML before ruling; screen every
suggestion against the six ratified standing positions and prior gate rulings
(re-litigated settled gates are rejected by pointer, not re-argued); rule each
point AGREE / PARTIAL / REJECT / ALREADY DONE / FACTUALLY FALSE / DECISION GATE /
COUNSEL PASS / DEFER-v3.0. Deliverable: adjudication memo DOCX (ORA style guide,
`YYYY-MM-DD_MasterLease-vX.Y_External-Review-Adjudication_Memo_v01.docx`) into
`Claude Lease Project Outputs/`. STOP for Gabriel's confirmation of the accepted
edit list before building. Genuine new decision gates get an explicit ratification
table; anything touching the six ratified positions is never changed unilaterally.

**Phase 1 — Build** the new master:
write the accepted edits as a committed spec (`masterlease-jurisdiction-rebase/specs/<cycle>_vA-to-vB.json`)
and apply it to the canonical master with `ora_docx_redline.py` (bundled with
masterlease-jurisdiction-rebase) as REAL tracked changes — asserted counts, author + date, never
clean overwrites, never hand-edits to property templates, never a wrapper script around the
`Redliner` class. Use its built-in ops: `replace` / `insert_after` for in-run edits, `delete` for
tracked deletions, `insert_paragraph_after` for new sections/subsections (pPr incl. Heading style and
numbering copied from the anchor or a reference heading via `ppr_from`), and `"part":
"word/footer*.xml"` for the footer form tag (`ORA Master Lease vX.Y`, count asserted across parts).
One command writes both deliverables:
`python3 -I ora_docx_redline.py --in <master> --out <..._REDLINE-vs-vA.docx> --spec <spec> --accept-out <..._TEMPLATE.docx>`
— the clean `_TEMPLATE` is the **XML-level accept-all** of the redline (every other package byte and
the run structure kept, so Phase 2 rebases it cleanly); do not produce it with a LibreOffice
`accept_changes.py` round-trip (re-serialises the package, drops unused header/footer parts).
Validate the REDLINE with the docx skill's `validate.py --original --author` (must PASS; the
tracked-change count it reports must equal `tracked_change_count()`). Run `lease_qc.py` on the clean
TEMPLATE — must be 0 failures, in the form line the footer tag declares. Verify the six ratified
positions, all gate adoptions, and every numeric cross-reference (F7) intact. Rebuild Exhibit B if
the cycle accepted exhibit micro-adds (version bump). Park finals in `Business/Leases All properties/`
(master at root; Exhibit B in `Claude Lease Project Outputs/`); working artifacts stay in session
scratch (workspace-hygiene rules).

**Phase 2 — Rebase** property templates:
`rebase.py --master <new master, accepted-changes copy> --all --out <scratch>`.
Anchor-drift failures are the system working: rekey per the never-loosen rule,
note in the rebase skill changelog. Re-verify each output independently
(lease_qc 0-failures + presence of every new edit marker; NNN structure intact
on MD-COL). Move finals to `Claude Lease Project Outputs/`; sweep displaced
prior-version templates to `/archive/` (never delete); write the run memo.

**Phase 3 — Systematize**:
extend `lease_qc.py` with a check per new standard provision (new F-class,
"vX.Y standard"); re-benchmark (prior-version-derived lease fails exactly the new
checks; new-version-derived = 0); swap the rebase parity fixture to the new master
and run its test suite green; update `MASTER-LEASE-TEMPLATE-POINTER.md`; bump and
repackage both skills as `.skill` installers (present for Save-skill click);
append the repo-reconciliation note to `PENDING_REIMPORT.md` (ora-skills source
lives on the Code surface).

**Phase 4 — Counsel pass** (standing scope; gates v3.0): attorney-in-fact
estoppel · R.C. Ch. 1923 self-help/notice-to-quit waiver · acceleration formula
(incl. discount rate) · gross-up methodology (stated %, base-year symmetry) ·
MD/MO overlay confirmation.

**Phase 5 — Close out**: event-log entry; archive the adjudication memo to the
Notion Knowledge Base (conversation-archival); move the superseded master and
Exhibit B revisions to `/archive/`; executed leases stay on vintage forms — new
deals draft from the new master only.

## Hard rules carried from the component skills

- Verify before ruling; expect reviewer hallucinations (numbering, "missing"
  provisions, phantom typos, stale-copy reviews).
- Tenant-side edits are rejected wholesale on landlord paper; settled gates are
  not re-opened by a new review repeating them.
- Asserted-count substitutions only; ANCHOR DRIFT fails loudly; never loosen.
- Nothing lands in the OneDrive business folder except finals and run memos.
- Never delete — `/archive/`.

## Changelog

- **v1.1 (2026-10-15):** Phase 1 builds from a committed spec with `ora_docx_redline.py` v2's
  built-in ops (styled/numbered paragraph insertion, tracked delete, footer-part edits) and
  produces the clean TEMPLATE by XML-level accept-all instead of a LibreOffice round-trip
  (proven: the Phase-1 power-rights specs reproduce the v2.8 / v3.1 masters byte-for-byte).
- **v1.0 (2026-08-04):** Initial. Proven twice on 2026-08-04 (v2.4.1→v2.5 morning cycle, v2.5→v2.6 afternoon cycle) before extraction into a skill.
