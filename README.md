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

## Current skills (2026-06-07)

**10 git-tracked skill directories:** `acquisition-underwriting` (v2.0, modal — SCREEN/SNAPSHOT/COMPS/UNDERWRITE/FULL),
`cowork-settings`, `deploy-site`, `document-assembly` (v1.2), `lease-abstraction-pipeline`,
`lease-renewal-pipeline`, `loi-generation` (the SOLE LOI path — 16-pt QC Gate, 7 state overlays, ORA
letterhead; vendored 2026-06-07), `monthly-close`, `psa-reconciliation`, `tenant-email`.

**Shared data:** `target-markets.json` — canonical buy-box market list consumed by `acquisition-underwriting`.

**Retired to `_archive/`** on 2026-06-07 (subsumed by `acquisition-underwriting`'s SCREEN / SNAPSHOT / COMPS
modes — not live; kept for reference, reversible): `deal-screen`, `cap-rate-snapshot`, `market-comp-analyzer`,
plus the earlier `underwrite`. Note `underwrite` carries `user-invocable: true`; it stays in `_archive/`
precisely so it does not re-expose a slash-invocable duplicate.

## Runtime skill dependencies (outside this repo)

Some skills here hand off to skills **not stored in this repo** that resolve from the anthropic-skills plugin
at runtime — `docx`, `deal-execution`, `tenant-intelligence`, `market-monitor`, `legal-intelligence`,
`rent-comp`, `re-operations`. The composed runtime (this repo + the plugin) makes them reachable; a Recovery
(above) that restores ONLY this repo will NOT restore them. (`loi-generation` — the SOLE LOI path — was
plugin-only and source-controlled nowhere until 2026-06-07, when it was vendored into this repo so the LOI
guardrail is backed up and survives recovery.)
