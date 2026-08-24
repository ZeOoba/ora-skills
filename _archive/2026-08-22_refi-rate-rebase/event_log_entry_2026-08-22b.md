## 2026-08-22 -- Save-skill clicks confirmed: acquisition-underwriting v4.15, model-bulk-edit v1.0, package-and-stage-skill v1.26

Three confirmed platform installs, verified post-click per package-and-stage-skill step 7
(cache file count vs the packaged .skill, CreationTime vs a measured pre-click baseline, and
Local main.log correlation where available).

- **acquisition-underwriting v4.15** (commit 329bb2b). Cache CreationTime moved 17:50:08 ->
  2026-08-22 20:40:58; 9 files present, matching the 9 entries in the packaged .skill
  (SKILL.md + target-markets.json + 7 references). Cache SKILL.md line 7 reads
  "(v4.15 -- Buy Box & Scorecard v1.1)". Carries the concurrent session's v4.14 Kinsman batch,
  this session's v4.13 refi-rate change, the v4.8-v4.11 changelog archive, and the new
  conventions-change consumer sweep rule.

- **model-bulk-edit v1.0** (commit b02a3e2). FIRST install -- no prior cache directory existed.
  CreationTime 20:41:28, 2 files (SKILL.md + scripts/cached_value_lint.py), matching the
  packaged .skill exactly. The subfolder file landed, confirming the Cowork install path
  handled the multi-file package correctly (the desktop Settings path drops subfolders).

- **package-and-stage-skill v1.26** (commit 2ced173). Strongest evidence of the three:
  CreationTime moved 17:58:05 -> 20:41:33, cache description ends "Commit by pathspec; claim
  first. v1.26", AND the Local main.log shows `Delta: 1 to download` at 20:41:32 ->
  `Sync complete: 1 downloaded, 0 failed` at 20:41:33 -- an exact-second match to the
  CreationTime move. This is the v1.24 correlation working as designed: first-hand,
  skill-specific proof that rules out the mirror-sync-hook explanation.

  All three PENDING_REIMPORT lines cleared.

- **DUPLICATE REGISTRATION -- now CONFIRMED by the app itself, not inferred.** The earlier
  flag this session raised from `ListSkills` (two enabled entries named
  `acquisition-underwriting`: skill_012DJmjQBkLtQtfu6We1owXx and
  skill_01Ukeyw2g9c99nVdsSpnTiyr) is corroborated by the desktop app's own log, twice during
  this sync cycle:

      [warn] [SkillsPlugin] Remote skill "acquisition-underwriting" maps to the same
      directory as an earlier remote skill, skipping

  One of the two registrations is being SKIPPED on every sync. Benign right now -- the cache
  landed v4.15 correctly -- but it means the account carries a registration the runtime
  silently ignores, and which of the pair "wins" is not something this session can determine
  or control. `plugin_of` returns None, so this is not the known plugin-shadow case.
  A session cannot delete a registry entry: needs manual removal in Settings -> Capabilities.
  Recommend removing whichever entry is NOT the one currently resolving, then re-running a
  sync and confirming the warn line is gone.

- **Cached-value sweep across the Business tree did NOT complete -- killed, not finished.**
  `scripts/cached_value_lint.py` was launched detached against
  `OneDrive\...\Business` and reached **9.1 GB RSS** (PID 40816) before it was terminated.
  It exhausted the paging file: an unrelated PowerShell invocation failed with
  "Could not load file or assembly 'System.Management.Automation' ... The paging file is too
  small for this operation to complete (0x800705AF)". Cause is a real defect in the script as
  shipped in v1.0: it calls `openpyxl.load_workbook()` TWICE per workbook (data_only False and
  True) without `read_only=True`, so both full object trees are held in memory per file.
  No portfolio-wide cached-value result exists yet; the `125DouglasPike` finding stands, but
  nothing else has been audited. Fix tracked for model-bulk-edit v1.1.
