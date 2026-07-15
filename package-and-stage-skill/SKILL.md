---
name: package-and-stage-skill
description: Oxford Realty Advisors skill packaging and staging helper — companion to ora-skill-store-drift-check. Use when the user says: package a skill, stage a skill, repackage skill, re-upload skill, install skill update, build a .skill, save-skill installer, or after a drift check reports "repo newer → re-upload needed". Packages the repo copy at C:\Users\Owner\ora-skills\[skill]\SKILL.md into a validated, Cowork-importable .skill via tools/package_skills.py (NEVER PowerShell Compress-Archive). Hash-prechecks the runtime cache first and short-circuits (no packaging, no Save-skill ask) if already current. Stages the .skill in session outputs and surfaces the one-click Save-skill installer. Does NOT register — that's Gabriel's Save-skill/Settings→Capabilities click; runtime cache re-syncs after import. Multi-file skills route to Cowork install, not desktop Settings (bug drops subfolder files). Logs confirmed installs — the click, not just the repo commit — to event_log.md. v1.2
---

# package-and-stage-skill

Companion to `ora-skill-store-drift-check`. Turns a "repo newer → re-upload to Cowork/claude.ai needed" finding (or any repo skill edit that must reach the platform) into one staged, one-click installer.

**Source of truth = the git repo** `C:\Users\Owner\ora-skills\<skill>\SKILL.md`. The AppData runtime cache is a read-only mirror that rebuilds from the platform after import — never write it directly (2026-06-11 Roaming-alias clobber incident).

**Registration is human-gated.** This skill packages and stages; it does NOT install. A session cannot write the skill registry — Gabriel clicks **Save skill** (or Settings → Capabilities) on the staged `.skill`.

## Input

- One or more skill names. Default: the skill(s) the latest drift-check comment flagged **repo-newer**.

## Procedure

1. **Confirm source.** `C:\Users\Owner\ora-skills\<skill>\SKILL.md` exists. Run `git status --short -- <skill>/`; if dirty, STOP and commit first — repo-first rule: the repo leads the platform, never the reverse. Record the last commit (`git log -1`).
2. **Pre-check the runtime cache — short-circuit if already current.** Before packaging, hash-compare every file in the repo skill dir against its counterpart at `…\local-agent-mode-sessions\skills-plugin\<outer-UUID>\<inner-UUID>\skills\<skill>\` (SHA256 via PowerShell `Get-FileHash`; same file count, same names, same hashes). If everything matches, the skill is already live at the repo's version: **STOP** — do not package, do not ask for a Save-skill click. Log a one-line `event_log.md` note ("`<skill>` already in sync at v`<X.Y>`, no reimport needed") and report that to whoever asked. Proceed to step 3 only on an actual diff (missing runtime file, hash mismatch, or file-count mismatch). This step exists because a 2026-07-15 session was dispatched to reimport two skills already packaged, staged, and installed by an earlier *unlogged* session — the handed-off premise ("hasn't reached the runtime yet") was stale, and only a hash check caught it before wasted packaging and a needless Save-skill ask.
3. **Package — sanctioned tool ONLY.** Via Desktop Commander on Windows: `python tools\package_skills.py "<session outputs dir>" <skill ...>`. NEVER PowerShell `Compress-Archive` (writes backslash zip entries → importer rejects per zip-spec APPNOTE 4.4.17.1; ruling 2026-06-11). The tool validates frontmatter (`name` == dir, `description` ≤ 1024 chars), scans named-count headers across every `*.md`, and asserts forward-slash entries. A non-zero exit is a real defect — surface it verbatim, do not work around it.
4. **Stage.** Emit the `.skill` into the current Cowork session's outputs directory (the one that maps to `/mnt/user-data/outputs`).
5. **Surface.** `present_files` the `.skill` → renders the **Save skill** install button.
6. **Route multi-file skills to Cowork, not desktop Settings.** If the skill has ANY file beyond `SKILL.md` (a `references/`, `templates/`, or `scripts/` dir), tell Gabriel to install via the Cowork **Save skill** button, not Settings → Capabilities → Skills. **Confirmed bug (reproduced twice, 2026-07-11):** the desktop Settings single-`.skill` upload path silently drops subfolder files on import — `SKILL.md` lands, `references/*.md` etc. do not — while the Cowork install path installs the full package correctly. Single-file skills (no subfolders) are unaffected by either path.
7. **Verify post-install, then log the click — not just the commit.** After Gabriel confirms installation, check the AppData runtime cache mirror contains every file the packaged `.skill` did — not just `SKILL.md`. If any file is missing, the install silently failed (most likely the desktop-Settings bug above); tell Gabriel to re-install via Cowork instead of assuming the drift is closed. Once verified, log the confirmed install to `event_log.md` in the same pass: skill name(s), version, confirming timestamp, and that this was Gabriel's **Save-skill click**, not merely the upstream repo commit. A repo commit is evidence the fix was authored; it is not evidence anyone installed it — that gap (a click that happened but was never logged) is exactly what caused the 2026-07-15 redundant-dispatch near-miss step 2 now catches on the read side. This log entry is what lets a future step-2 pre-check, or a drift-check, trust "already installed" from the log instead of re-deriving it from a hash comparison every single time.
8. **Hand off.** Tell Gabriel: click **Save skill** (or, for single-file skills only, Settings → Capabilities) to register. After import the runtime cache re-syncs to the new version — that closes the drift; a re-run of `ora-skill-store-drift-check` should then read IN-SYNC.

## Done =

hash pre-check run first, every time (either short-circuited with a logged already-in-sync note, or proceeded because a real file-level diff was found) · packager exited 0 with `description N/1024 OK` + `N entries OK` + a forward-slash entry list · `.skill` present in session outputs · repo path git-clean (or dirty surfaced and committed) · `present_files` called · multi-file skills routed to Cowork install · post-install file-count verified against the packaged `.skill` · a `event_log.md` entry recorded once install is confirmed, naming the Save-skill click itself (not just the repo commit) · no write to the runtime cache · no email / external send.

## Why a skill, not a scheduled task

Packaging + import is event-driven (it fires off a drift finding) and registration needs a human click — it cannot run unattended. Invoke on demand, or immediately after the drift check flags a repo-newer skill.

## Changelog

- v1.2 (2026-07-15): added step 2 — a mandatory hash pre-check against the runtime cache that short-circuits packaging entirely when the skill is already current, and extended step 7 to log the confirmed Save-skill *click* to `event_log.md` (not just the upstream repo commit). Motivated by a same-day incident: a session was dispatched to reimport `orphaned-task-forensics` and `fleet-advisory-remediation` v1.1 on the premise the fix "hadn't reached the runtime yet" — it already had, via an earlier session that packaged and installed it but never logged the click. A manual hash check caught the stale premise before any redundant packaging or Save-skill ask; this version makes that check (and the logging that would have prevented the stale premise in the first place) part of the standard procedure rather than something an agent has to think to do.
- v1.1 (2026-07-11): added steps 5-6 (now 6-7) — route multi-file skills to Cowork install and verify post-install file count, after a workflow-audit session confirmed (twice, reproducible) that the desktop Settings→Capabilities single-`.skill` upload silently drops subfolder files while Cowork's install path does not.
- v1.0 (2026-06-22): initial. Companion to ora-skill-store-drift-check; sanctioned-packager-only; human-gated Save-skill registration; read-only on the runtime cache.
