# masterlease-jurisdiction-rebase changelog archive, v1.0–v1.4

Full-text entries rolled off the inline Changelog under the 6-entry retention rule (2026-10-29). Repo-only; excluded from packaging.

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
