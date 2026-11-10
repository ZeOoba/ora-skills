---
name: "masterlease-jurisdiction-rebase"
description: "Use when the user mentions: new master lease version, rebase the lease templates, regenerate the MD/MO templates, jurisdiction overlay, conform the lease to a state, state-conformed lease template, update property lease forms, lease template for Easton / Salisbury / Northwood / Raytown / Columbia, or uploads a new ORA_MasterLease_ShallowBayIndustrial_v*.docx or ORA_MasterLease_ShallowBay_MultiTenantMG_v*.docx (v2.x NNN / v3.x MG lines, read from the footer tag). Also use when adding a NEW property or state overlay, or converting a property to NNN. Rebases Oxford Realty Advisors jurisdiction-conformed Master Lease property templates onto a new master revision in one command, and generates state-conformed (MD/MO) property templates from the OH-anchored master. Companion to lease-form-qc (which QCs drafted leases); this skill produces the templates leases are drafted FROM."
---

# Master Lease Jurisdiction Rebase — Oxford Realty Advisors (v1.10)

One-command regeneration of state-conformed property lease templates whenever the
controlled master (`ORA_MasterLease_ShallowBayIndustrial_v*.docx`) revs. Built from the
2026-08-03 conformance session, where it produced the MD-EAS / MD-SBY / MO-RAY v2.2
variants and then rebased them onto v2.4 with zero manual edits.

## Why this exists

The 2026-08-03 propagation audit proved that hand-copying leases spreads defects
(34–36/39 failures on every executed lease; ZIP cross-contamination between properties).
The same failure mode applies to templates: hand-porting jurisdictional edits onto each
new master revision silently drops or duplicates clauses. This engine applies every
jurisdictional change as an **asserted-count substitution** — if an anchor string moved
or vanished in the new master, the run fails loudly and names the anchor, instead of
producing a quietly wrong template.

## Canonical master — the drift rule

**Never build from a cached or knowledge-store copy of the master.** Version drift
happened twice on 2026-08-03 (a v2.1 cache was used while v2.4 was canonical).

- Canonical location: **`Business/Leases All properties/` (egoldberg's OneDrive/SharePoint),
  pinned 2026-08-03 by Gabriel.** Always pull the highest version number present in that
  folder before a rebase run — never rely on a cached copy from this project's Knowledge
  files, a prior session, or any other knowledge-store source (see the
  v2.1-cache-while-v2.4-was-canonical incident above). Superseded revisions live in that
  folder's `/archive/` subfolders and are excluded from the highest-version scan.
  If the connected SharePoint search tool doesn't index that path on a given surface
  (observed 2026-08-04 — the connector resolved the folder to 9050 Red Branch Road's own
  lease archive, not the portfolio master), fall back to this skill's bundled
  `scripts/fixtures/ORA_MasterLease_ShallowBayIndustrial_v2.7_TEMPLATE.docx`, which the
  test suite validates against canonical v2.7 (the v2.6 fixture is retained for the
  lease-form-qc v2.6→v2.7 regression assertion) — but say so explicitly in the output and
  flag that production use should be confirmed against the live copy first.
- Freshness check before any run: compare the version string in the supplied master's
  filename (`v2.5` etc.) against the newest version mentioned anywhere in the session
  and in this skill's changelog. If the supplied master is not the highest version
  known, stop and ask which is canonical.
- The six ratified standing lease positions (2026-08-03, carried in `lease-form-qc`)
  are baked into the master. This skill must never alter them: modified gross /
  calendar base year · co-tenancy not guaranty · 1.0× deposit · 10% late fee + 18%
  default interest (savings clause is allowed and included; silent reduction is not) ·
  flat Hazardous Materials ban · no extension option. **Exception:** the expense-recovery
  structure (modified gross vs. NNN) may be overridden per property via the
  `lease_structure` config field — see below — on Gabriel's explicit, sourced direction
  only. The other five positions have no override mechanism.

## How to run

```bash
python3 -I scripts/rebase.py --master <path/to/ORA_MasterLease_..._vX.Y_TEMPLATE.docx> \
    --property MD-EAS --out <session-scratch-dir>
# or all configured properties (on a v3.0 master: only the properties with a "v3_0" entry):
python3 -I scripts/rebase.py --master <master.docx> --all --out <session-scratch-dir>
```

**Standard post-checks on every output (v1.10):** `post_check()` (tokens, residue, markers)
and **`check_format_parity()`** — per-character run-formatting parity against the master (see
"Run-formatting parity"). Either failure aborts the run with the template already named.

**`--all` by line (v1.10):** on a v3.x master, the properties with a `v3_0` entry; on a v2.x
master **from v2.8 on**, only the NNN-line properties (no `v3_0` entry: MD-COL, OH-ST-NNN) — the
four MG-line properties moved to v3.x and are not re-emitted on the NNN line (`--property`
still reaches them). v2.7 and earlier: all properties, unchanged.

The form line is read from the master's **footer tag** (`ORA Master Lease vX.Y`): v2.x →
the long-form path below; v3.x → the v3.0 short-form path (see "v3.0 short-form MG master").
A master whose filename version and footer tag disagree, or whose footer parts carry mixed
tags, aborts with ANCHOR DRIFT before anything is written.

`--out` is ALWAYS passed explicitly, pointed at session scratch — never omitted, never
the canonical OneDrive folder (see Workspace & output hygiene).

Outputs `ORA_MasterLease_ShallowBay_<property>_vX.Y_TEMPLATE.docx` per property —
the master edited in place (python-docx cross-run splice), so native formatting,
numbering, styles, headers and exhibits survive untouched.

The script:
1. Loads `config/properties.json` (property facts) and `config/state_overlays.json`
   (state law tables).
2. Applies every substitution with an expected match count; any mismatch aborts with
   the anchor named.
3. If the property's config sets `"lease_structure": "NNN"`, rewrites the modified-gross
   OPERATING COSTS AND TAXES article into a full NNN structure (Operating Costs + Taxes
   + Insurance, no base year) — see "NNN override" below. Otherwise the master's default
   modified-gross / calendar-base-year language is left untouched.
4. Inserts the Maximum Lawful Rate savings clause after Counterparts (cloned styling;
   skipped if already present).
5. Post-checks: zero residue of the master's anchor state, zero unfilled entity/state
   tokens, savings clause present and positioned, state statutes at expected counts;
   for NNN properties, zero residual `[BASE YEAR]` token and the OPERATING COSTS, TAXES
   AND INSURANCE heading and Insurance defined term both present.

## Workspace & output hygiene (v1.4 — the 2026-08-04 sweep rule)

Root cause of the 2026-08-04 superseded-file sweep: ~450 of 491 files removed from
`Business/Leases All properties/` were build debris (working copies, extractions,
node_modules, eval logs, .tmp/.lock files) that sessions had created inside the
canonical business folder. Binding rules for every run of this skill (and the model
for any ORA skill that builds artifacts):

1. **All working artifacts go to session scratch/outputs, never the OneDrive business
   folder.** Working copies, text extractions, diffs, page renders, npm/python scratch
   dirs, node_modules, eval logs, tmp files — none of these are ever created under
   `Business/Leases All properties/` or any other OneDrive business path. The canonical
   folder receives exactly two classes of file from a run: final
   `ORA_MasterLease_ShallowBay_*_TEMPLATE.docx` outputs and the run memo.
2. **No short-name working copies.** Never copy the master or a property template to an
   abbreviated name (`MD-EAS_v2.4.docx`, `OH_v2.4.1.docx`, …) — this is how hash-identical
   duplicates of canonical templates ended up loose at the folder root on 2026-08-03.
   Reference canonical files by full path. If a tool requires a writable local copy, make
   it in session scratch under the unmodified canonical filename and remove it at run end.
3. **`--out` is explicit, always.** Point it at session scratch, run QC there, then move
   the verified finals to the canonical folder. The script's historical default
   (`--out .`) wrote into whatever directory the session happened to be in — the source
   of the root-level debris. (Source patch pending; see changelog.)
4. **End-of-run sweep.** Before closing, list anything the run created in the canonical
   folder that is not a final template or the run memo, and move it to that folder's
   `/archive/` (never delete — ORA invariant 6). Superseded prior-version templates
   displaced by the run's outputs are moved to `/archive/` in the same sweep.

## NNN override (per property, opt-in only)

The master's default is modified gross with a calendar base year (ratified position #1).
A property runs full NNN instead only when its `config/properties.json` entry sets
`"lease_structure": "NNN"` — omit the field entirely for the default. Set it only on
Gabriel's explicit, sourced direction that the property's leasing practice is NNN; never
infer it from a single executed lease without confirming it's the property's standing
practice.

**MD-COL (9050 Red Branch Road, Columbia MD)** is the first and, as of this writing,
only NNN property (added 2026-08-04). Gabriel confirmed the building runs NNN leases
building-wide, consistent with the executed LINERX LLC / Eddie Woo Park lease (Suite
D+E) and Muirkirk Properties' own NNN form in continuous use across ~16 suites since at
least 2011. The override rewrites Section 4 (OPERATING COSTS AND TAXES → OPERATING
COSTS, TAXES AND INSURANCE) to drop the base-year stop and add an explicit `"Insurance"`
defined term — the OH-anchored master folds insurance into the generic Operating Costs
definition, but 9050's own paper always separated Taxes / Insurance / CAM as three
distinct pass-through categories, so the override matches that structure rather than
inventing a new one. No other ratified position is touched by the override: co-tenancy,
1.0× deposit, 10%/18% + savings clause, flat Hazardous Materials ban, and no extension
option all still apply on MD-COL exactly as on every other property.

Implementation: `nnn_text_rules()` + `convert_to_nnn()` in `scripts/rebase.py`, applied
between `build_rules()` and `insert_savings_clause()`. Anchors are keyed to the master's
original (modified-gross) Section 4 text and fail loudly the same way as `build_rules()`
on drift. The new Insurance definition paragraph is inserted into the blank spacer
paragraph two paragraphs after the Taxes definition, with its list numbering (`numPr`/
`pStyle`) copied from the Operating Costs paragraph so it renders in sequence as `(iii)`
rather than as an unnumbered, unindented paragraph — this was the one non-obvious defect
in the first hand-built version of this conversion (2026-08-04) and is why the automated
version copies `pPr` explicitly rather than leaving the target paragraph's default style.

## When a run fails (anchor drift)

An assertion failure means the new master changed the anchor text — that is the system
working. Diff the new master against the prior one (pandoc to text is fine), update the
anchor in `scripts/rebase.py` or the configs, note the change in the changelog below,
and re-run. Never loosen an assertion to "0 or 1" to make a run pass.

## Adding a property or state

- New property in MD/MO: add an entry to `config/properties.json` (entity from the
  executed-lease record or the ratified LLC roster — never invented; SF from the
  Portfolio Basis workbook / Master Workbook; PM block from executed-lease practice,
  tokens where unknown). `entity_state` is REQUIRED and must be sourced from the
  Articles of Organization, the ratified LLC roster, or an executed lease's recital —
  the engine fails closed without it. Formation state is frequently but not always the
  property state; assuming it silently was a defect caught in the 2026-08-03 evals.
  `lease_structure` is OPTIONAL — omit for the modified-gross default; set to `"NNN"`
  only per the NNN override rule above.
- New state (IN/WI/KS/TN are pre-listed as RESEARCH-REQUIRED): complete the state's
  entry in `config/state_overlays.json` with fresh statutory research — UETA citation,
  possession/eviction statutes, holdover statute, environmental overlay, parcel-number
  nomenclature, plus any state-specific clause (Maryland's §3-101(e) memorandum-of-lease
  proviso is the model, keyed by the `extra_no_recording` field). Do not copy another
  state's citations as scaffolding; an empty field fails closed.

## Home-state properties (added v1.8)

An Ohio property on the OH-anchored master takes no state overlay: set `"home_state": true`
in its `config/properties.json` entry (first user: `OH-MOR`, 384–420 Morrison Road). The
engine then uses `build_rules_home()` — property facts only (entity ×4, formation-state
article ×3, premises, building, share denominator, Franklin County parcel, PM block, BLI
premises/building, payment direction) — with `L = {"state": "Ohio"}`, and the post-check
skips the Ohio-residue assertion. All six ratified positions stay untouched. Required
fields: `entity`, `entity_state`, `premises`, `building_def`, `share_denominator`, `parcel`,
`pm_block`. Facts must be county-verified (Franklin County Auditor GIS `ParcelFeatures`
layer: PARCELID, SITEADDRESS, ZIPCD, BLDGAREA, OWNERNME1).

**Footer fill walks every footer part.** The v2.5 fill iterated `section.footer` only —
the *default* footer — so even-page and first-page footers kept `[PREMISES ADDRESS]`
(MD-Columbia printed the raw token on every page through v2.6). From v1.8 the engine walks
every `/footer` relationship part; `TestFooterFillAllParts` asserts no footer part of any
rebased multi-tenant template keeps the token (fails on the v1.7 engine for MD-COL/OH-MOR).

## v3.0 short-form MG master (added v1.9)

`ORA_MasterLease_ShallowBay_MultiTenantMG_v3.0_TEMPLATE.docx` (2026-10-08) is a rewrite,
not an edit of v2.7 — none of the v2.x anchors exist in it. `build_rules_v30()` carries its
own anchor set, **recovered by paragraph diff of the v3.0 master against the four v3.0
property templates built from it on 2026-10-08** (OH-MOR, MD-EAS, MD-SBY, MO-RAY), every
substitution count-asserted (ANCHOR DRIFT never-loosen rule unchanged):

- **Property facts (all four):** `[LANDLORD ENTITY]` ×5 · `a [LANDLORD STATE] limited liability
  company` ×3 · `[PREMISES ADDRESS]` ×4 (BLI, signature page, Exhibit A, Exhibit B) + every
  footer part · BLI building line from `building_def` + parcel reference · BLI share
  denominator · `[BUILDING DEFINITION]` · payment sentence (`payment_direction`) · PM name in
  the insurance clause and COPY TO block · `[MANAGER STREET ADDRESS]` / `[MANAGER CITY, STATE ZIP]`
  (×1, or ×2 when `payment_direction` is null and the Rent section keeps its tokens — a filled
  `pm_block` with a null `payment_direction` fails closed) · `ATTN:`.
- **Multi-building project (`v3_0.project_rsf`, Salisbury):** `project_def`, BLI
  "; Project: 53,700 rentable square feet", share "of the Project", gross-up and water
  allocation Building → Project.
- **State overlay (MD, MO; not home state):** Business Day holiday state, Specialized
  Equipment contractor licensing state, insurer licensing state, notice-to-quit waiver
  (Ohio Chapter 1923 → `possession_statutes`), holdover statute sentence, environmental
  overlay, Authority qualification state, governing law, MD no-recording proviso, and the
  signature-page note via the new overlay field **`v3_signature_note`** (MD: memorandum-of-lease
  note; MO: `null` = delete the Ohio-only notarial note). Required for any v3.0 rebase —
  fail-closed if absent.
- **Home state (OH-MOR):** property facts only; Ohio text and the Ohio-only note retained.

Anchors never start in, or span, a bold label/defined term ("Building / Project:",
"Building", "Hazardous Materials"): `replace_in_paragraph()` writes the new text into the
first run it touches, so such an anchor bolds the fill or un-bolds the term. The first v1.9
draft did exactly that in three paragraphs; the run-format parity test caught it.

Config: a property is on the v3.0 line only if its `properties.json` entry has a **`v3_0`**
object (MD-EAS, MD-SBY, MO-RAY, OH-MOR); it carries v3-only facts (`parcel_reference` with the
SDAT account numbers for MD-EAS/MD-SBY; `project_rsf` for MD-SBY). MO-RAY uses the overlay's
`(Jackson County Parcel No. [PARCEL NO])`; OH-MOR derives the Franklin County reference from
`parcel`. NNN (MD-COL) and single-tenant (OH-ST-NNN) entries never get one — a v3.0 master run
against them fails closed. The v3.0 master is MG-only: `variant`/`lease_structure` overrides
abort on it. The v2.x path is unchanged and still rebases all six v2.7 properties.

**Parity (test_rebase.py `V30ParityTests`):** rebasing `scripts/fixtures/…MultiTenantMG_v3.0_TEMPLATE.docx`
reproduces each stored template in `scripts/fixtures/v3.0_expected/` **text-equal (body +
every footer part) and character-format-equal** (per-paragraph pPr + per-run rPr segments).
Package XML differs only in run segmentation (the 2026-10-08 build split fills into separate
runs); every other package part is byte-identical. Salisbury: the stored template already
carries Gabriel's 2026-10-08 payee direction, so with the corrected config parity is exact;
the test also replays the pre-fix config and asserts it differs in exactly the Rent payee,
insurance PM name and COPY TO name/street lines.

## Facts provenance (do not re-derive from leases)

Entity names (29000 INFORMATION LANE, LLC · 2203 NORTHWOOD, LLC · 9620 STATE 350, LLC ·
Muirkirk Properties, LLC) were sourced from executed leases / the ORA Entity Structure DB.
Building SF (48,000 / 53,700 / 34,560 / 90,000) from the Portfolio Basis workbook / ORA
Property Register. Salisbury: **MD SDAT verified 2026-10-06** — three accounts, 2203 **Marvel Road** (09-053646,
Map 102 P110), 2205 Northwood Dr (09-053654, P111), 2207 Northwood Dr (09-053662, P113), 18,000 SF
each per SDAT (54,000 vs the 53,700 RSF denominator — denominator unchanged pending Gabriel), ZIP
21801. "2203 Northwood Drive" was never a valid address; the entity name 2203 NORTHWOOD, LLC is
unchanged (legal name). Easton: SDAT 01-088645 (27,000 SF) + 01-088742 (21,000 SF) = 48,000 SF,
ZIP 21601 confirmed. Salisbury payee/PM (**2026-10-08, Gabriel: rent paid to the property manager,
not Landlord**): SVN Miller Commercial Real Estate, 206 East Main Street, Salisbury, MD 21801 (SVN
staff email signatures, M. Messick 10/2/26 and T. Spicer-Davis 10/6/26); `properties.json` MD-SBY
`payment_direction` + `pm_block` corrected 2026-10-15 (v1.9), ATTN Brady Smith unchanged. Morrison (OH-MOR): Franklin County parcel 010-208204, 31,200 SF, ZIP 43213. 9050 Red Branch Road's Howard County SDAT Tax Account No. is unresolved — direct
SDAT query did not return content programmatically as of 2026-08-04; left tokenized.
ZIPs, suites, parcel/tax-account numbers, per-building Northwood RSF, and the Raytown PM
block are deliberately tokenized: fill at drafting time from the county record or PM
agreement, and run `lease-form-qc` on every drafted lease before it leaves the office.

## Single-tenant variant (added v1.6)

`"variant": "single-tenant"` in a `config/properties.json` entry (currently only
**OH-ST-NNN**, paired with `"lease_structure": "NNN"`) regenerates the
OH-SingleTenant-NNN template family from the master: entire-building demise
(incl. paved/yard areas), 100% Proportionate Share, gross-up and "Tenant's
Allocation" removed, exclusive parking, tenant site-services maintenance
addendum — then the NNN conversion and savings clause. Variant entries stay
generic-tokenized (no entity/premises/PM fills; tokens fill at drafting time),
skip the state-overlay gate (the family is anchored to the master's own state),
and get their own post-check branch (token/residue/marker assertions). Delta set
recovered 2026-08-04 by paragraph diff of the v2.4.1 variant against its v2.4.1
base; engine output verified text-identical to the hand-built v2.6 canonical.
Relocation clause (h) is retained as an inert option by ratified judgment call.

## Run-formatting parity (standard check, added v1.10)

`format_parity(master_doc, out_doc)` / `check_format_parity()` in `rebase.py`, run by `main()`
on every output. `replace_in_paragraph()` writes a fill into the FIRST run its anchor touches,
so an anchor that starts in a bold label bolds the fill and one that spans a bold defined term
un-bolds it — text-identical, visibly wrong. Paragraphs are aligned by text; in a changed
paragraph the common prefix/suffix and any re-emitted master text (≥ 8-character blocks) must
keep their formatting, and the fill must carry a formatting found on the text it replaced.
Compared: visible properties only (bold, italic, underline, strike, caps, size, font, colour,
highlight, shading, style, vertAlign…); rsid/lang/proofing ignored; a colour ≤ #404040 counts as
black (the v2.x masters carry stray #2F2F2F runs). **First run (2026-10-15) found real defects
in production templates:** MD-COL v2.7 (BLI "Base Year" fill bold; heading period bolded — 3
findings) and OH-ST-NNN v2.7 (BLI "Demised Premises" and share fills bold, defined terms
"Demised Premises" un-bolded and the share definition bolded — 13). Fixed by re-keying five
anchors (NNN: BLI `" [BASE YEAR]"` after the body sentence, heading without its period;
single-tenant: demise sentence stops before the defined term, BLI demise and share lines keyed
after their bold labels, share definition starts at "shall mean") — same text out, counts
still asserted (never-loosen rule). Tests: `FormatParityTests`.

## Power-rights line: v2.8 NNN / v3.1 MG (added v1.10)

Both Phase-1 masters rebase with **zero anchor drift** on the existing rule sets. One new rule:
**single-tenant P7** — on a v2.8+ master the OH-SingleTenant-NNN conversion also deletes the P7
fragment ", and such spaces shall not count against Tenant’s Allocation while so designated"
(count 1, asserted), so no undefined term remains while Landlord's EV install / designate /
charge right and the reasonable-access proviso stay (Gabriel, 2026-10-15: "Drop allocation
sentence"; lease-form-qc FP7 has the matching single-tenant branch). Not applied to v2.7 (no P7
sentence). `PowerRightsRebaseTests`: `--all` sets, lease_qc 0 of 68 / 0 of 73 ENFORCED on every
output, every P1–P8 marker present (P8 module bracketed + counsel note), fragment dropped only on
single-tenant paper, P7 rule asserted. **Counsel item:** on single-tenant paper the P1
reservation lists "parking areas" while Tenant holds the exclusive right to the parking areas
(which the single-tenant demise includes) — reconcile in the counsel pass.

## Shared tracked-change editor (added v1.5; v2 ops added v1.10)

`scripts/ora_docx_redline.py` — the reusable asserted-count tracked-change editor. Use it for
every master revision instead of rebuilding the machinery ad hoc (it was reimplemented three
times across the v2.3, v2.5 and v2.6 builds before extraction, and the 2026-10-15 Phase-1
power-rights build still needed a wrapper script for four missing ops — now built in):

| Op | What it does |
|---|---|
| `replace` / `insert_after` | in-run tracked substitution / insertion (v1) |
| `delete` | tracked deletion of `target` inside each run holding `context` (count asserted) |
| `insert_paragraph_after` | tracked NEW paragraph after each paragraph whose text contains `anchor_text` (count asserted, default 1); pPr — style **and numbering** (`numPr`) — copied from the anchor (`"ppr_from": "anchor"`), from a reference paragraph named by a unique text snippet, or given explicitly (`"ppr"`); paragraph mark + every run tracked; runs carry an `rpr` (named or raw) or `bold`/`underline`/`italic` |
| `insert_paragraphs_after` | v1 BodyText bold-label rows after an exact XML anchor |
| any op + `"part"` | target any XML part, e.g. `"word/footer*.xml"` for the footer form tag; the count is asserted **across all matching parts**; each part gets its own `w:id` range |
| `accept` / `--accept-out` | **XML-level accept-all-changes** (drop `w:del`, unwrap `w:ins`, drop paragraph-mark revisions) — the clean `_TEMPLATE` keeps every other byte of every package part and the source run structure, so it rebases cleanly. Refuses formatting changes, moves and deleted paragraph marks rather than guess. Use this, **not** a LibreOffice `accept_changes.py` round-trip, for the clean template (LibreOffice re-serialises the whole package and drops unused header/footer parts). |

Spec = JSON: a v1 list of ops, or `{"author", "date", "start_id", "rpr": {...}, "ppr": {...}, "ops": [...]}`.
CLI: `python3 -I scripts/ora_docx_redline.py --in <master> --out <REDLINE> --spec <spec.json> --accept-out <TEMPLATE>`;
`... accept --in <REDLINE> --out <TEMPLATE>`. Python API: `apply_spec()`, `accept_docx()`,
`tracked_change_count()`, `Redliner`. Committed build specs live in **`specs/`** —
`power-rights_v2.7-to-v2.8.json` and `power-rights_v3.0-to-v3.1.json` are the Phase-1 build,
and re-running them reproduces the committed v2.8 / v3.1 masters byte-for-byte in every
package part (29 / 28 tracked changes; lease_qc 0 of 68 / 0 of 73 — `test_ora_docx_redline.py`
`Phase1EquivalenceTests`). In-run anchors must sit inside one `<w:t>` (run `merge_runs.py`
first); always validate output with the docx skill's `validate.py --original --author`.
ANCHOR DRIFT failures follow the same never-loosen rule as `rebase.py`.

## Changelog

- v1.10 (2026-10-15): (0) **Run-formatting parity is a standard post-check** (`format_parity()`,
  `check_format_parity()`; see its section) and five v2.x anchors were re-keyed after it found
  bold-fill / un-bolded-term defects in the production MD-COL and OH-ST-NNN v2.7 templates (text
  unchanged). **v2.8 / v3.1 power-rights masters** supported: `power_rights_master()`,
  single-tenant P7 allocation-fragment rule, `--all` on a v2.8+ NNN master emits only the
  NNN-line properties. New tests: `FormatParityTests` (5), `PowerRightsRebaseTests` (6);
  `test_rebase.py` 19 → 30. (1) **`ora_docx_redline.py` v2** — the Phase-1 power-rights build's four
  wrapper-script workarounds are first-class ops: `insert_paragraph_after` (styled/numbered tracked
  paragraph, pPr copied from the anchor or a reference paragraph), `delete`, `"part"` targeting
  (footer/header globs, count asserted across parts, per-part `w:id` ranges) and XML-level
  `accept` / `--accept-out`; v1 ops and list specs unchanged except that a count mismatch now
  exits with `ANCHOR DRIFT ...` instead of a bare `AssertionError`; output keeps the source's
  zip member order. New `specs/power-rights_v2.7-to-v2.8.json` and `..._v3.0-to-v3.1.json` (the
  Phase-1 `build.py` edit list, ported verbatim) reproduce the Phase-1 masters byte-for-byte;
  `fixtures/` gains the v2.8 / v3.1 masters. New `scripts/test_ora_docx_redline.py` (18 tests);
  the CI gate now runs `masterlease-jurisdiction-rebase/scripts/test_*.py`.
- v1.9 (2026-10-15): v3.0 short-form multi-tenant MG master support. (1) **Form detection** —
  `master_form()`/`is_v3()` read the footer tag; `rebase_one()`, `post_check()` and `main()`
  dispatch on it; filename/footer version mismatch and mixed footer tags abort. (2) **v3.0
  engine** — `build_rules_v30()`, `apply_signature_note_v30()`, `rebase_one_v30()`,
  `post_check_v30()` (tokens, Ohio/OHIO/Revised Code/R.C. residue, state, savings clause,
  footer tag, entity). Anchors from the master↔template diff; see the v3.0 section. (3)
  **Config** — `v3_0` entries for MD-EAS, MD-SBY, MO-RAY, OH-MOR; `v3_signature_note` in the
  MD/MO overlays; **MD-SBY payee/PM fix** (SVN Miller Commercial Real Estate, 206 East Main
  Street, Salisbury, MD 21801 — run-memo open item; old values kept in `_payee_note_2026-10-15`).
  `--all` on a v3.0 master emits only `v3_0` properties. (4) **Tests** — `fixtures/` gains the
  v3.0 master and `fixtures/v3.0_expected/` (the four 2026-10-08 templates, unmodified copies);
  new `V30ParityTests` (12: form detection, config keys, text parity, character-format parity,
  Salisbury pre-fix delta, CLI `--all` set, NNN refusal, anchor drift, duplicated anchor,
  missing signature note, missing `v3_0`, v2.7 path untouched). Fixed: the
  `if __name__ == "__main__"` block sat above `TestFooterFillAllParts`, so `python3 test_rebase.py`
  ran 6 tests, not 7 (discovery ran 7); the CLI subprocess test now runs `-I -B`. Suite: **19
  passed** (script mode and discovery). v2.7 `--all` re-run: six templates, all 0/60 on
  lease-form-qc v2.10; v3.0 `--all`: four templates, all 0/65.

- v1.8 (2026-10-06): v2.7 revision cycle. (1) **Home-state path** — `build_rules_home()` +
  `home_state` config flag; post-check and test branches skip Ohio residue; first property
  OH-MOR (384–420 Morrison Rd, Fairground Village Center, LLC, parcel 010-208204). (2) **Footer
  fill fix** — walk every footer part, not `section.footer`; new `TestFooterFillAllParts`
  (red on v1.7 for MD-COL/OH-MOR, green on v1.8). (3) **Config** — MD-EAS ZIP 21601, MO-RAY ZIP
  64133, MD-SBY premises/building/project rebuilt on the SDAT-verified 2203 Marvel Road /
  2205–2207 Northwood Drive addresses with tax map/parcels; SDAT provenance notes. (4) **Parity
  fixture** swapped v2.6 → v2.7 (accepted master; v2.6 retained). Suite: 7 passed / 23 subtests.

- v1.7 (2026-08-24): Description trimmed to restore headroom (was 1003/1024,
  headroom 21 -- close-out work-order item 4). Dropped the dated
  anti-contamination and single-tenant-variant version-history parentheticals;
  no trigger vocabulary or rule clause removed. `description_budget.py` now
  reports headroom 174.

- v1.6 (2026-08-04): Single-tenant variant support. `single_tenant_rules()` /
  `convert_to_single_tenant()` + `variant` config field + OH-ST-NNN entry;
  `rebase_one`, `post_check`, `main()` and the parity test all branch on the
  variant; `--all` now emits five templates. First run's ST_ALLOC_DEF constant
  fired ANCHOR DRIFT against the real master (reconstructed from memory instead
  of extracted) — corrected from the document text; the never-loosen discipline
  working as designed. 6/6 tests green; engine variant output text-identical to
  the 2026-08-04 hand-built canonical.

- v1.5 (2026-08-04): Phase-3 close of the v2.5→v2.6 revision cycle. (1) Parity fixture
  swapped v2.5 → v2.6 (accepted-changes copy of the redline master); v2.6 rebase of all
  four properties ran with ZERO anchor drift — no rekey needed, v1.3 anchor set carries
  forward unchanged. (2) `--out` is now `required=True` in packaged source — closes the
  v1.4 PENDING one-liner. (3) `scripts/ora_docx_redline.py` added (see section above).
  All 6 tests green against the v2.6 fixture.

- v1.4 (2026-08-04): Workspace & output hygiene section added after the 2026-08-04
  superseded-file sweep of `Business/Leases All properties/` (491 files; ~450 were
  session build debris — `mlr2/` with node_modules, `mjr-*` eval workspaces, short-name
  template copies at the folder root). Rules: working artifacts in session scratch only;
  no short-name copies; `--out` always explicit; end-of-run debris sweep to `/archive/`.
  **PENDING source patch (ora-skills repo, Code surface):** `scripts/rebase.py`
  `--out` default `"."` → `required=True` — one line, `main()` argparse block. *(Applied
  in the v1.5 packaged source; repo-side port still pending.)* Runtime
  SKILL.md updated ahead of source per the v1.1.2 reconciliation precedent; reconcile on
  the next package-and-stage run and clear the PENDING_REIMPORT note. No anchors,
  configs, or engine behavior changed in v1.4.

- v1.3 (2026-08-04): Anchors rekeyed to master v2.5 (the external-review adjudication
  build: 18 edits + 4 ratified gate adoptions). Changes: `[LANDLORD ENTITY]` 3->4 and
  entity clause 2->3 (Basic Lease Information page adds one each); PM-block anchors
  are now the tokens `[MANAGER STREET ADDRESS]` / `[MANAGER CITY, STATE ZIP]` (master
  pre-tokenized — the old Columbus literals are gone); new BLI fill rules (premises
  line, building/parcel line built from `building_def` + `parcel_reference`); NNN mode
  neutralizes the BLI Base Year line ("Not applicable — full NNN"); `rebase_one` now
  fills the footer lease-identifier `[PREMISES ADDRESS]`; parity fixture swapped to
  v2.5 (v2.4.1 fixture retired per anchor-drift discipline); all 6 tests green; all
  four properties (MD-EAS, MD-SBY, MO-RAY, MD-COL) rebased 0-of-46 on lease-form-qc
  v2.2. The v2.5 master's venue clause is deliberately tokenless ("county in which the
  Project is located") — no venue overlay needed per state.

- v1.2 (2026-08-04): Added the per-property `lease_structure` NNN override (opt-in only,
  never inferred) and the MD-COL (9050 Red Branch Road, Columbia MD) property entry —
  first non-modified-gross property in the registry, confirmed by Gabriel against the
  executed LINERX LLC/Eddie Woo Park lease and the building's ~15-year NNN practice.
  `nnn_text_rules()` / `convert_to_nnn()` added to `scripts/rebase.py`; `post_check()`
  extended with NNN-specific residue/heading checks. Extracted the per-property pipeline
  (`build_rules` + optional `convert_to_nnn` + `insert_savings_clause`) into a single
  `rebase_one()` used by both `main()` and `test_rebase.py` — the first version of this
  change added the NNN step to `main()` only, and `ParityAgainstKnownMasterTests`
  (which called `apply()`/`insert_savings_clause()` directly, duplicating the pipeline
  rather than reusing it) caught the omission by failing its own post-check on MD-COL.
  Fixed by removing the duplication rather than patching the test in place — the same
  anti-drift principle this skill applies to leases, applied to itself. Also documents
  the SharePoint canonical-master-location fallback to the bundled fixture, observed
  2026-08-04 when the connected search tool didn't index the pinned path on the Cowork
  surface.
- v1.1.2 (2026-08-03): canonical master location resolved — Gabriel pinned
  `Business/Leases All properties/` (egoldberg's OneDrive/SharePoint); both v2.4 and
  the v2.4.1 typo-fix companion parked there same day. Closes the UNRESOLVED gap this
  section carried since v1.0. Resolved independently on both surfaces — Code-surface
  close-out, and a Cowork-surface hand-edit applied directly to the packaged `.skill`
  ahead of the Code-surface source — with divergent prose; reconciled here so the two
  surfaces stop drifting.
- v1.1.1 (2026-08-03, Code-surface close-out): dropped the `Demised Premisess` fix-up
  rule from `build_rules` — v2.4.1 (the typo-fix companion master, uploaded same
  session) already corrects the spelling upstream, so the rule's own "drop this rule
  once fixed upstream" comment now applies. Caught by the new parity test running
  against the real v2.4.1 fixture: the rule's asserted count (1) found 0 matches,
  correctly firing ANCHOR DRIFT rather than silently passing. Anchors rekeyed to
  v2.4.1. Do not re-add a 0-or-1-tolerant version of this rule — retire fix-up rules
  once the upstream master absorbs them, per this skill's own anchor-drift discipline.
- v1.1 (2026-08-03): Eval-loop fixes. (1) Article-aware entity clause — "an Indiana /
  an Ohio limited liability company" (first vowel-initial state through the engine
  produced "a Indiana"); "a Utah" special-cased by sound. (2) `entity_state` is now a
  separate, sourced, REQUIRED config field — the engine no longer assumes the LLC is
  formed in the property state, and fails closed when the field is missing. All three
  current entities' formation states sourced from executed-lease recitals. (3) Version
  parser tolerates suffixed master filenames (e.g., v2.5-DRAFT) and no longer emits a
  doubled "v" on unparseable names.
- v1.0 (2026-08-03): Engine extracted from the v2.2 build + v2.4 rebase session.
  Anchors keyed to master v2.4. MD (Talbot/Wicomico) and MO (Jackson) overlays ratified;
  IN/WI/KS/TN stubs fail closed pending research.
