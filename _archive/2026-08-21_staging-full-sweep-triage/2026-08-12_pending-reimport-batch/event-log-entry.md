## 2026-08-12 — package-and-stage-skill Entry point B: 5-skill reimport batch installed and cache-verified (Cowork session)

**Confirmed by Gabriel's Save-skill click**, not merely the upstream repo commit. Runtime-cache re-sync verified in-session at 17:57–17:58 ET 2026-08-12; every file in every package byte-matches (RAW MATCH, no EOL-normalization needed) against the AppData skills-plugin cache mirror.

**Installed (Entry point B — pre-packaged, no repackaging):**

| Skill | Version | Pkg entries | Cache verify |
|---|---|---|---|
| tax-appeal | v1.1 | 1 | RAW MATCH, 17:57 |
| fleet-advisory-remediation | v1.1 frontmatter / v1.2 changelog | 1 | RAW MATCH, 17:57 |
| daily-brief | v2.8 | 2 (+target-markets.json) | RAW MATCH both, 17:57 |
| deal-comparison | v1.0 | 2 (+target-markets.json) | RAW MATCH both, 17:57 |
| market-monitor | v1.2 | 2 (+target-markets.json) | RAW MATCH both, 17:58 |

Packages built earlier the same day from ora-skills @ b66b708 and handed off pre-built. Four-item integrity pre-check run per package before any install: exists · zip entries (all forward-slash, `testzip()` clean, no backslash entries) · freshness vs the CURRENT repo (all RAW MATCH; `target-markets.json` compared against the REPO-ROOT copy, 44,268 B, identical across all three consumers) · staged to session outputs. Step 0 plugin gate run first: `plugin_of()` returned `None` for all five, so the standalone Save-skill path was correct.

**Handoff premise corrected mid-run.** HEAD was `0f5c23a` ("feat(pipeline-stamping): wire Next Action Date into the deal-touching skills"), not `b66b708` as stated in the handoff. `git diff b66b708..HEAD` touched only `acquisition-underwriting/SKILL.md`, `deal-execution/SKILL.md`, `loi-generation/SKILL.md` — exactly the three excluded from this batch — so the five installed skills were unaffected and their packages were not stale. This is the step-2/Entry-point-B freshness check doing precisely what it exists for: the handoff's stated commit was wrong, and only a hash comparison against the current repo (rather than trust in the stated SHA) established that the packages were still good.

**The recurring "invalid skill format" import failure did NOT reproduce.** All five imported cleanly via the Cowork Save-skill button, including all three multi-file packages. Diagnostic notes for the open bug:
- The suspected variable (step 6's multi-file Settings bug) was not isolated by this batch, because the Cowork path — not Settings → Capabilities — was used for all five, per step 6's routing rule.
- These three "multi-file" packages are **flat** (`SKILL.md` + sibling `target-markets.json`), not subfoldered. Step 6's documented Settings defect is specifically a `references/`/`scripts/` **subfolder-drop**. A flat second entry is a different shape; this batch provides no evidence either way about subfoldered packages under Settings.
- Package-side causes are ruled out for these five: frontmatter `name` == dir on all, descriptions 380–903 of 1024, no UTF-8 BOM, no zip corruption, no backslash entries. EOL is not the variable — tax-appeal is CRLF and fleet-advisory-remediation is LF, and both are single-file controls that behaved identically.
- Conclusion: prior "invalid skill format" rejections were **not** caused by these packages' contents. If the failure recurs, the next discriminating test is a *subfoldered* package through Settings vs Cowork, holding package contents constant.

**Not done in this session (surface boundary, per skill v1.11/v1.12):** the PENDING_REIMPORT ledger was deliberately NOT cleared — Gabriel reserved that for a Code session that will first verify the sync in `main.log` (non-zero Delta). Ledger clearing is Code-surface only. This log entry itself was prepared in the Cowork session and written from Code via `append-event-log.py --entry-file`.

**Ledger state at the time of writing (Code session, 2026-08-12 ~18:20 ET, amended from the draft).** The draft's "not cleared" characterization was accurate when written but is no longer current. The phantom `rent-comp` line is gone (Task 1 landed as `171dc8a`), and `deal-execution` / `loi-generation` have also been cleared. Those two clears were verified legitimate rather than assumed: `pending_reimport.py candidates` — which unions the ledger with a fresh full repo-vs-cache SHA256 sweep — reports no drift for either, so a real Save-skill reimport did occur. Remaining genuine pending entries are recorded in the follow-on entry below.

**Housekeeping:** two integrity-check scratch scripts (`_epb_check.py`, `_epb_fm.py`) moved from `_staging\` to `_archive\2026-08-12_epb-integrity-scratch\` — never deleted, per the repo's archive rule. `_epb_verify.py` (post-install cache verifier) written to the same archive dir.

**Workflow-optimization candidates:**
- The post-install cache verifier written ad hoc this session (`_epb_verify.py`) does exactly what step 7 requires and has now been hand-rolled more than once. Worth promoting into `tools/` as a first-class command (e.g. `pending_reimport.py verify <skill>`) so step 7's verify stops being retyped per session.
- Entry point B's freshness check should not accept a handoff-stated commit SHA at face value — this session's stated `b66b708` was already two commits stale. Cheap hardening: have the pre-check print `git rev-parse HEAD` alongside the claimed SHA and flag any divergence explicitly, rather than leaving it to the operator to notice.
- `fleet-advisory-remediation`'s frontmatter version (v1.1) trails its own changelog top entry (v1.2). Minor, but the frontmatter is what a drift check and a reader both see first; worth a sweep for the same mismatch across the skill store.
