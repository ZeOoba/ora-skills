# lease-form-qc changelog archive, v2.7

Full-text entries rolled off the inline Changelog under the 6-entry retention rule (2026-11-14). Repo-only; excluded from packaging.

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
