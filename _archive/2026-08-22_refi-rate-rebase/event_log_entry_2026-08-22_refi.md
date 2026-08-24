## 2026-08-22 -- Save-skill clicks confirmed: package-and-stage-skill v1.25, acquisition-underwriting v4.13

Two confirmed platform installs from the refi-rate-rebase session. Logged per package-and-stage-skill
step 7 (the click, not merely the repo commit).

- **package-and-stage-skill v1.25** (commit 8f00bb4). CONFIRMED, two independent signals:
  (i) a live `ListSkills` account call returns the skill enabled with a description string ending
  "Commit by pathspec. v1.25" -- the platform's own copy, not the cache; (ii) runtime-cache directory
  CreationTime = 2026-08-22 17:58:05, after the 17:55 commit. A mirror-sync overwrite rewrites bytes in
  place and leaves CreationTime untouched, so a moved CreationTime is a real teardown/recreate.
  PENDING_REIMPORT line cleared.

- **acquisition-underwriting v4.13** (commit 5b1f319, refi rate default 7.00% -> 6.50%). CONFIRMED on
  CreationTime alone: cache directory CreationTime = 2026-08-22 17:50:08, after the 17:45:01 commit, and
  the repo state at that moment was v4.13. ListSkills is NOT corroborating here -- this skill's
  description carries no version token, so the account call cannot discriminate versions for it.
  CAVEAT, recorded rather than smoothed over: no pre-click CreationTime baseline was captured during
  this session's step 2, which the v1.23 rule requires unconditionally. The 17:50:08 reading is
  therefore compared against an inferred prior state, not a measured one. Evidence is good but one
  notch weaker than the doctrine calls for.
  PENDING_REIMPORT line NOT cleared -- see below.

- **acquisition-underwriting ledger line deliberately left pending.** The current pending line is for
  commit 8728924 (REDACTED-158 Blvd doctrine bundle, v4.14) written at 22:01Z by a concurrent session, not
  for v4.13. v4.14 has not been installed: the cache CreationTime has not moved since 17:50:08. Clearing
  the line would mark an uninstalled version as installed.

- **DUPLICATE REGISTRATION FLAGGED (needs Gabriel).** `ListSkills` returns TWO enabled entries named
  `acquisition-underwriting`, ids `skill_012DJmjQBkLtQtfu6We1owXx` and `skill_01Ukeyw2g9c99nVdsSpnTiyr`,
  with byte-identical descriptions. `plugin_of('acquisition-underwriting')` returns None, so this is not
  the known plugin-shadow-copy case (step 0). Two registrations of the same skill name means an
  ambiguous resolution at invocation time and an install that may land on only one of them. A session
  cannot delete a registry entry; this needs a manual removal in Settings -> Capabilities.

- Local main.log (`%LOCALAPPDATA%\Claude\Logs\main.log`) was live (mtime 18:07:36) but its last 400 lines
  carried no `[SkillsPlugin]` entries, so the v1.24 exact-second correlation was unavailable for either
  skill. CreationTime was the operative discriminator, as v1.22/v1.23 anticipate.
