# ORA Authoritative Skills Library

This directory is the **source of truth** for Oxford Realty Advisors custom skills
that execute deal-analysis, operations, and document-generation workflows.

## Scope

Git-tracked as of 2026-04-16 (workflow-audit Fix #3a). Scoped to this subtree only —
the enclosing `Cowork OS/` and `OneDrive - Oxford Capital Partners (1)/` roots are
NOT git-tracked and must not be (they contain QBB backups, tenant PII, and financial
statements that should never enter a repo).

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

## Current skills (2026-04-16)

11 skills: `acquisition-underwriting`, `cap-rate-snapshot`, `deal-screen`,
`deploy-site`, `document-assembly`, `lease-abstraction-pipeline`,
`lease-renewal-pipeline`, `market-comp-analyzer`, `monthly-close`, `tenant-email`,
`underwrite`.
