---
name: cowork-settings
description: Use when the user wants to version, diff, or publish the Oxford Realty Advisors Claude Cowork Global Settings document — mentions version the cowork settings, new cowork settings, diff cowork settings, update cowork preferences, revise global settings, new preferences version, cowork settings vN, rev the preferences block, or any request to revise, compare, or publish the ORA Cowork User Preferences governance document (versioned settings .md, brand-styled .pdf with extractable text layer, version-to-version diff report).
---

# cowork-settings (v1.0)

Governs the ORA Claude Cowork Global Settings document — the single-source user-preferences block for every Cowork session.

## When to invoke

- **Version bump**: user wants to revise the settings block (add/remove/change a rule).
- **Diff**: user wants to compare two versions or see what changed.
- **Publish**: user wants to re-emit the branded PDF and markdown for archival.
- **A/B**: user wants to run a lite variant alongside the full version.

## Core workflow

### A. New version (bump vN → vN+1)

1. Read the latest version from `./versions/` (sort by filename).
2. Ask the user (single question) which of:
   - **Patch (v1.0 → v1.0.1)**: typo, wording tightened, no behavioral change.
   - **Minor (v1.0 → v1.1)**: new rule or section, backward compatible.
   - **Major (v1.0 → v2.0)**: rule removed or semantics changed.
3. Copy latest into `./versions/YYYYMMDD_ORA_CoworkGlobalSettings_v{N}_{M}.md` with today's date.
4. Apply the user's proposed changes inline.
5. Bump the version table at the bottom of the markdown with a one-line changelog entry.
6. Run `scripts/build_pdf.py` against the new .md to produce the branded PDF.
7. Run `scripts/diff_versions.py <old> <new>` to emit a changelog markdown.
8. Run the 16-point QC Gate (ORA Institutional Style Guide v1.0+ — encoded inline in global preferences; the former `institutional-output-standards` skill was never installed and must not be referenced); confirm PDF text layer extracts.
9. Output all three artifacts (new .md, new .pdf, changelog .md) to `/mnt/user-data/outputs` and present them.

### B. Diff two existing versions

1. Read the two specified version files from `./versions/`.
2. Run `scripts/diff_versions.py` to produce a unified changelog markdown with:
   - Section-scoped additions / removals / modifications
   - Breaking-change flags on any removed rule
   - [SPECULATIVE] impact note on attention-budget implications
3. Present the changelog.

### C. Republish current version

Run `scripts/build_pdf.py` against the current version; re-output both .md and .pdf.

## Governance rules

- **Skill-overrides-preferences principle holds.** This skill's logic supersedes the user-preferences block when they conflict (per the block itself).
- **Never delete a prior version.** Archive everything in `./versions/` — it is the governance trail.
- **Every version MUST preserve these invariants** (Tier-0, cannot be removed without explicit major-version confirmation):
  1. Identity guardrail — "Never 'Ze' or 'Ze Ooba'"
  2. Email routing — Outlook COM (`send-via-outlook.ps1`) sole send path; automated outputs → ggoldberg@ ONLY; ora-am-brief Daily Brief is the sole cc-Eric exception (ratified 2026-06-10/11)
  3. PDF extractable-text standard (Amendment No. 1)
  4. Netlify `--prod` guardrail
  5. File-naming — THREE standing schemas (deal files / financial models / ISO-dated outputs; ratified 2026-06-10, never unify)
- **Review cadence.** Surface a reminder if ≥90 days since the last version; suggest either a v(N+0.1) refresh or an explicit "no changes needed" decision logged in the changelog.

## Outputs

- `/mnt/user-data/outputs/YYYYMMDD_ORA_CoworkGlobalSettings_v{N}_{M}.md`
- `/mnt/user-data/outputs/YYYYMMDD_ORA_CoworkGlobalSettings_v{N}_{M}.pdf`
- `/mnt/user-data/outputs/YYYYMMDD_ORA_CoworkGlobalSettings_changelog_v{old}_to_v{new}.md`

## Session-end

- Flag any rule added in the last three revisions that could now be demoted into a more specific skill (preference-to-skill migration).
- Recommend deletion of memory edits that are now fully encoded in the settings.
