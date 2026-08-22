# Item 1 — Save-skill click prep, 2026-08-17

Four skills are live-but-unregistered: hash-identical to the runtime cache via the
`post-commit` raw-sync, but with NO corroborating "Save-skill click confirmed" line in
`event_log.md` at their current version. A raw-sync closes content drift; it does NOT
register a skill in the platform's skill index. Only Gabriel's Save-skill click does that.

**Scope note:** the source prompt for this pass named three skills (daily-brief,
ora-setup-audit, package-and-stage-skill). Re-reading `_staging/PENDING_REIMPORT.md`
just now (17:23Z) turned up a fourth line not in that list — `register-scheduled-task`,
pending since 2026-08-17T16:52Z, commit `10bac87` (the v2.11 id-collision fix) — which
is the current HEAD of this repo. Same mechanism, same remediation, so it's included
below rather than left for a separate pass. Flagging the discrepancy since the prompt
that generated this list was evidently stale by ~2.5 hours before I started.

## Packages staged (content-verified no-op — drift report confirms IN-SYNC on all four)

| Skill | Version | Package | Bytes | Ledger line (PENDING_REIMPORT.md) |
|---|---|---|---|---|
| daily-brief | v2.11 | `_staging/2026-08-17_item1-reimport-prep/daily-brief.skill` | 30,200 | `daily-brief \| pending since 2026-08-17T02:04Z \| commit e98c92f "fix(daily-brief): split incident narrative to references/, size fix (Automation Audit Rev 9/15)" \| trigger: daily-brief/SKILL.md, daily-brief/references/incident-history.md` |
| ora-setup-audit | v1.5 | `_staging/2026-08-17_item1-reimport-prep/ora-setup-audit.skill` | 7,491 | `ora-setup-audit \| pending since 2026-08-17T02:13Z \| commit 4697d8a "docs(ora-setup-audit): v1.5 - local-mirror drift is now structurally prevented" \| trigger: ora-setup-audit/SKILL.md` |
| package-and-stage-skill | v1.21 | `_staging/2026-08-17_item1-reimport-prep/package-and-stage-skill.skill` | 18,979 | `package-and-stage-skill \| pending since 2026-08-17T15:36Z \| commit f2c31da "docs(package-and-stage-skill): v1.21 - pre-flight frontmatter gate" \| trigger: package-and-stage-skill/SKILL.md` |
| register-scheduled-task | v2.11 | `_staging/2026-08-17_item1-reimport-prep/register-scheduled-task.skill` | 10,273 | `register-scheduled-task \| pending since 2026-08-17T16:52Z \| commit 10bac87 "fix(register-scheduled-task): v2.11 -- id-collision fleet-resolution must never be tested via a live delete" \| trigger: register-scheduled-task/SKILL.md` |

## Explicitly NOT done (per doctrine)

- No Save-skill click performed.
- No "confirmed install" line written to `event_log.md`.
- No `pending_reimport.py clear` run on any of the four.

## Action for Gabriel

Open Cowork, click Save skill for each of the four packages above in one pass, then
either let the next `ora-skill-store-drift-check` run corroborate the install via
`event_log.md` cross-check, or have a session log the confirmation and clear the four
ledger lines.
