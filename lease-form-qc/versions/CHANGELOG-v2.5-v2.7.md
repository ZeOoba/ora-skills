# lease-form-qc changelog archive, v2.5–v2.7

Full-text entries rolled off the inline Changelog under the 6-entry retention rule (2026-10-29; v2.7 added 2026-11-08). Repo-only; excluded from packaging.

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
