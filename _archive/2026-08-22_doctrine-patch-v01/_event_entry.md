## 2026-08-22 -- Doctrine patch v01: 4 skills installed via Cowork Save-skill click

Cowork session ran package-and-stage-skill Entry point B for the 4 packages staged at
`_staging\2026-08-22_doctrine-patch-v01\` (repo commit 8728924, "doctrine: apply Kinsman
Blvd patch bundle v01"). All 4 confirmed installed via Gabriel's Save-skill click, not
merely the upstream repo commit.

**acquisition-underwriting -> v4.15** (not v4.14 as originally staged). Freshness
pre-check found the staged v4.14 package STALE: repo HEAD had moved to 329bb2b
("v4.15 - archive v4.8-v4.11, add conventions-change consumer sweep", 2026-08-22
18:13:46 -0400), 12 minutes after the cited 8728924. Staged package rejected per
Entry point B item 3; rebuilt fresh via `tools\package_skills.py` against current
repo (validated: description 997/1024, 9 entries, forward-slash paths, byte-verified
SHA256 both sides). Installed package is v4.15, not v4.14.
Confirming timestamp: cache CreationTime moved 2026-08-22 17:50:08 -> 20:40:58.899538
(America/New_York); Local main.log `[SkillsPlugin] Delta: 1 to download` / `Sync
complete: 1 downloaded` at 2026-08-22 20:40:58 -- exact-second match.

**acquisition-proposal-generation -> v3.2** (walk-price QC gate added). Freshness
pre-check clean (byte-identical to repo). Confirming timestamp: cache CreationTime
moved 2026-08-21 16:46:25 -> 20:41:04.971143; Local main.log `Delta: 2 to download`
/ `Sync complete: 2 downloaded` at 2026-08-22 20:41:04 -- exact-second match (paired
with market-monitor, downloaded in the same sync cycle).

**market-monitor -> v1.5** (run-triggered DOCTRINE-DRIFT REPORT section added).
Freshness pre-check clean (byte-identical to repo, incl. shared target-markets.json).
Confirming timestamp: cache CreationTime moved 2026-08-16 15:57:44 -> 20:41:04.959873;
same 20:41:04 `Delta: 2` / `Sync complete: 2 downloaded` cycle as acquisition-proposal-
generation above.

**loi-generation -> v1.8** (23-point QC gate, item 23 = walk-price clearance).
Freshness pre-check clean (byte-identical to repo). Confirming timestamp: cache
CreationTime moved 2026-08-21 18:09:42 -> 20:41:20.578527; Local main.log `Delta: 1
to download` / `Sync complete: 1 downloaded` at 2026-08-22 20:41:20 -- exact-second
match.

All 4: `plugin_of()` returned None (not plugin-bundled -- standalone Save-skill
correct). Post-install cache mirror file-count verified against each `.skill`'s
packaged entries -- no missing files for any of the 4. `%APPDATA%\Claude\logs\
main.log` (Roaming) has been stale since 2026-08-21 00:51:03 (app went down for
update) and was not usable for corroboration; `%LOCALAPPDATA%\Claude\Logs\main.log`
(Local) was live and gave exact-second corroboration for all 4, per the v1.24
doctrine addendum.

**Flagged, not remediated this session:** every sync cycle in the Local main.log
around this install logs `[warn] [SkillsPlugin] Remote skill "acquisition-underwriting"
maps to the same directory as an earlier remote skill, skipping`, and `ListSkills`
shows two enabled entries named "acquisition-underwriting" (skill_01Bfw31cAN8cY73Fojo67rgq
and skill_012DJmjQBkLtQtfu6We1owXx). This predates this session's install (the warning
fires on every cycle, not just the ones that touched acquisition-underwriting) and
looks like a duplicate platform-side registration, not an install defect -- the sync
itself completed correctly (Delta 1 / downloaded 1, file-count and content verified).
Surfacing for Gabriel; not investigated or collapsed here.
