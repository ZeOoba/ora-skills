# ORA Authoritative Skills Library

This directory is the **source of truth** for Oxford Realty Advisors custom skills
that execute deal-analysis, operations, and document-generation workflows.

## Scope

Git-tracked as of 2026-04-16 (workflow-audit Fix #3a). Scoped to this subtree only —
the enclosing `Cowork OS/` and `OneDrive - Oxford Capital Partners (1)/` roots are
NOT git-tracked and must not be (they contain QBB backups, tenant PII, and financial
statements that should never enter a repo).

## Packaging (.skill files) — MANDATORY RULE (2026-06-11)

To install/update a skill on the Cowork platform, package it as a `.skill` zip and
import it (Cowork chat "Save skill" button, or Settings → Capabilities).

**NEVER use PowerShell `Compress-Archive`** — Windows PowerShell 5.1 writes zip
entry paths with backslashes, violating the zip spec (APPNOTE 4.4.17.1); the Claude
importer rejects the file with *"Zip file contains path with invalid characters."*

**ALWAYS package with:** `python tools/package_skills.py <outdir> [skill ...]`
(emits forward-slash entries, asserts validity, prints the entry list).

## Layout

Each subdirectory is one skill and must contain:
- `SKILL.md` — the skill definition (YAML frontmatter + Markdown body)
- Optional `references/`, `scripts/`, `assets/` for skill-specific resources

## Backup discipline

Per-file `.backup-<timestamp>` sidecars and `skill-audit-YYYYMMDD-HHMMSS/` directories
are produced by audit/install passes. These are ignored by `.gitignore`. The git
history IS the version-control layer going forward — sidecar backups exist for
mid-session rollback, not for durable versioning.

## Dual-write discipline

Changes to skills in this directory must also land in the AppData runtime cache:
`C:/Users/Owner/AppData/Roaming/Claude/local-agent-mode-sessions/skills-plugin/<outer-UUID>/<inner-UUID>/skills/`

Do NOT treat AppData as the source of truth — it is a runtime cache that can be
rebuilt from this directory. If the two diverge, this directory wins.

## Recovery

If this directory is ever lost:
1. Git pull from the remote (if one exists — add one).
2. Fall back to the `skill-audit-YYYYMMDD-HHMMSS/` backup snapshots in
   `C:/Users/Owner/.claude/backups/`.
3. Last resort: re-export from Cowork Desktop via claude.ai skills UI.

## Current skills (2026-07-09 — regenerated from live folder listing; supersedes the stale 2026-06-07 count of 10)

**43 git-tracked skill directories** (plus the `cowork-settings` meta/settings skill — 44 total):
`acquisition-underwriting`, `annual-cycle`, `automation-health-monitor`, `capex-budgeting`,
`cash-position-monitor`, `census-acs-extract`, `code-debugging-optimizations`, `communication-intelligence`,
`conversation-archival`, `daily-brief`, `deal-comparison`, `deal-execution`, `deal-retirement`,
`debt-management`, `deploy-site`, `disposition-analysis`, `document-assembly`, `exception-detection`,
`investor-relations`, `lease-abstraction-pipeline`, `lease-renewal-pipeline`, `legal-intelligence`,
`loi-generation` (the SOLE LOI path — 16-pt QC Gate, 7 state overlays, ORA letterhead), `maintenance-analytics`,
`market-monitor`, `monthly-close`, `ora-flood-zoning-dd`, `oxford-cc-strategic-audit`, `package-and-stage-skill`,
`parcel-data-recovery`, `personal-portfolio`, `portfolio-growth`, `portfolio-reporting`, `psa-reconciliation`,
`re-operations`, `register-scheduled-task`, `rent-comp`, `rent-roll-qc`, `submarket-spatial-analysis`,
`tax-appeal`, `tenant-email`, `tenant-intelligence`, `vendor-management`, `website-perfection`.

`annual-cycle`, `capex-budgeting`, `cash-position-monitor`, `deal-retirement`, `investor-relations`,
`submarket-spatial-analysis`, and `vendor-management` were migrated into this repo 2026-07-09 from the
`ora-operations-extensions` plugin (closing the same re-sync-revert risk that motivated vendoring
`debt-management` earlier the same day). `deal-execution`, `tenant-intelligence`, `market-monitor`,
`legal-intelligence`, `rent-comp`, and `re-operations` are ALSO now fully repo-backed — the prior README
listed them as plugin-only, which was stale/incorrect as of this regeneration.

**Shared data:** `target-markets.json` — canonical buy-box market list consumed by `acquisition-underwriting`.

**Retired to `_archive/`** on 2026-06-07 (subsumed by `acquisition-underwriting`'s SCREEN / SNAPSHOT / COMPS
modes — not live; kept for reference, reversible): `deal-screen`, `cap-rate-snapshot`, `market-comp-analyzer`,
plus the earlier `underwrite`. Note `underwrite` carries `user-invocable: true`; it stays in `_archive/`
precisely so it does not re-expose a slash-invocable duplicate.

## Runtime skill dependencies (outside this repo)

Anthropic-core skills (`docx`, `xlsx`, `pptx`, `pdf`, `mcp-builder`, `schedule`, `skill-creator`, `setup-cowork`,
`consolidate-memory`, `init`, `review`, `security-review`) resolve from the platform at runtime and are
intentionally not vendored here. As of 2026-07-09, no ORA-specific skill remains plugin-only-and-unvendored —
if a future skill is added via a plugin before being pulled into this repo, note it here explicitly so
Recovery (above) doesn't silently miss it.

**Maintenance note:** this section drifted stale for a month (2026-06-07 → 2026-07-09) once before. The
`ora-skill-store-drift-check` weekly task should treat "does this README's skill list match the live folder
list" as one of its checks going forward, not just repo-vs-Cowork-cache drift.
