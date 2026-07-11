---
name: package-and-stage-skill
description: Oxford Realty Advisors skill packaging and staging helper — companion to ora-skill-store-drift-check. Use when the user says: package a skill, stage a skill, repackage skill, re-upload skill, install skill update, build a .skill, save-skill installer, push a repo skill to the platform, or after a drift check reports "repo newer → re-upload to Cowork/claude.ai needed". Packages the authoritative repo copy at C:\Users\Owner\ora-skills\[skill]\SKILL.md into a validated, Cowork-importable .skill via tools/package_skills.py (NEVER PowerShell Compress-Archive), stages it in the session outputs, and surfaces the one-click Save-skill installer. Does NOT register the skill — registration is the human's Save-skill / Settings→Capabilities click; the AppData runtime cache re-syncs from the platform after import. Read-only on the runtime cache. Multi-file skills: routes install to Cowork and verifies post-install — desktop Settings upload has a confirmed bug dropping subfolder files. v1.1
---

# package-and-stage-skill

Companion to `ora-skill-store-drift-check`. Turns a "repo newer → re-upload to Cowork/claude.ai needed" finding (or any repo skill edit that must reach the platform) into one staged, one-click installer.

**Source of truth = the git repo** `C:\Users\Owner\ora-skills\<skill>\SKILL.md`. The AppData runtime cache is a read-only mirror that rebuilds from the platform after import — never write it directly (2026-06-11 Roaming-alias clobber incident).

**Registration is human-gated.** This skill packages and stages; it does NOT install. A session cannot write the skill registry — Gabriel clicks **Save skill** (or Settings → Capabilities) on the staged `.skill`.

## Input

- One or more skill names. Default: the skill(s) the latest drift-check comment flagged **repo-newer**.

## Procedure

1. **Confirm source.** `C:\Users\Owner\ora-skills\<skill>\SKILL.md` exists. Run `git status --short -- <skill>/`; if dirty, STOP and commit first — repo-first rule: the repo leads the platform, never the reverse. Record the last commit (`git log -1`).
2. **Package — sanctioned tool ONLY.** Via Desktop Commander on Windows: `python tools\package_skills.py "<session outputs dir>" <skill ...>`. NEVER PowerShell `Compress-Archive` (writes backslash zip entries → importer rejects per zip-spec APPNOTE 4.4.17.1; ruling 2026-06-11). The tool validates frontmatter (`name` == dir, `description` ≤ 1024 chars), scans named-count headers across every `*.md`, and asserts forward-slash entries. A non-zero exit is a real defect — surface it verbatim, do not work around it.
3. **Stage.** Emit the `.skill` into the current Cowork session's outputs directory (the one that maps to `/mnt/user-data/outputs`).
4. **Surface.** `present_files` the `.skill` → renders the **Save skill** install button.
5. **Route multi-file skills to Cowork, not desktop Settings.** If the skill has ANY file beyond `SKILL.md` (a `references/`, `templates/`, or `scripts/` dir), tell Gabriel to install via the Cowork **Save skill** button, not Settings → Capabilities → Skills. **Confirmed bug (reproduced twice, 2026-07-11):** the desktop Settings single-`.skill` upload path silently drops subfolder files on import — `SKILL.md` lands, `references/*.md` etc. do not — while the Cowork install path installs the full package correctly. Single-file skills (no subfolders) are unaffected by either path.
6. **Verify post-install.** After Gabriel confirms installation, check the AppData runtime cache mirror (`…\local-agent-mode-sessions\skills-plugin\<outer-UUID>\<inner-UUID>\skills\<skill>\`) contains every file the packaged `.skill` did — not just `SKILL.md`. If any file is missing, the install silently failed (most likely the desktop-Settings bug above); tell Gabriel to re-install via Cowork instead of assuming the drift is closed.
7. **Hand off.** Tell Gabriel: click **Save skill** (or, for single-file skills only, Settings → Capabilities) to register. After import the runtime cache re-syncs to the new version — that closes the drift; a re-run of `ora-skill-store-drift-check` should then read IN-SYNC.

## Done =

packager exited 0 with `description N/1024 OK` + `N entries OK` + a forward-slash entry list · `.skill` present in session outputs · repo path git-clean (or dirty surfaced and committed) · `present_files` called · multi-file skills routed to Cowork install · post-install file-count verified against the packaged `.skill` · no write to the runtime cache · no email / external send.

## Why a skill, not a scheduled task

Packaging + import is event-driven (it fires off a drift finding) and registration needs a human click — it cannot run unattended. Invoke on demand, or immediately after the drift check flags a repo-newer skill.

## Changelog

- v1.1 (2026-07-11): added steps 5-6 — route multi-file skills to Cowork install and verify post-install file count, after a workflow-audit session confirmed (twice, reproducible) that the desktop Settings→Capabilities single-`.skill` upload silently drops subfolder files while Cowork's install path does not.
- v1.0 (2026-06-22): initial. Companion to ora-skill-store-drift-check; sanctioned-packager-only; human-gated Save-skill registration; read-only on the runtime cache.
