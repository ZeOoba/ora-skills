## 2026-08-21 — acquisition-proposal-generation v3.1 INSTALLED (Save-skill click confirmed, not merely committed)

**What happened.** Gabriel clicked **Save skill** in Cowork on the staged
`acquisition-proposal-generation.skill` package and confirmed it in-session at
**2026-08-21 16:46 ET**. This entry records the CLICK, not the upstream repo commit —
the repo commit (`fc78d55`, 2026-08-21 16:31:50 -0400, "Add acquisition-proposal-generation
skill v3.1") is evidence the skill was authored, never evidence anyone installed it.
First install of this skill; it is new, not a revision of a previously-installed version.

**Path.** package-and-stage-skill v1.21 Entry point B (pre-packaged install, no repackaging).
Package built by an earlier Code session at
`ora-skills\_staging\2026-08-21_acquisition-proposal-generation-reimport\`.

**Pre-check (all green).** Existence ASSERTED, not inferred: 439,052 bytes, mtime 16:39:59.
SHA256 `1105ff284549d99fd378a3f3c3165610c0791a666f620f3530ded6b9609bd4d6` — matched the
handoff's expected hash, and the copy staged into session outputs re-hashed identical.
5 zip entries, all forward-slash, no directory records, expected file set exactly.
All 5 packaged entries byte-matched the current repo copies. Frontmatter gate:
`name` == dir, description 966/1024. `plugin_of` = None (standalone path correct).
Repo tree clean. Not a SHARED_ROOT_DEPS consumer.

**Routed to Cowork Save-skill deliberately.** 5-file skill (`SKILL.md`, `scripts/build.js`,
`scripts/photos/{1100_rarig,55_newplant,9050_redbranch}.jpg`). Desktop Settings →
Capabilities was explicitly ruled out per the 2026-07-11 subfolder-drop bug — that path
would have landed SKILL.md alone and silently discarded the generator.

**Post-install verify — 5/5 files, and the directory was REBUILT, not overwritten.**
The cache mirror at
`…\skills-plugin\583f08bc-…\a6ad2c61-…\skills\acquisition-proposal-generation\`
carries all five files, each hashing MATCH against the repo. Decisive signal: the
directory's own **CreationTime moved to 16:46:25** (from 16:21:45 pre-click), with every
file created at 16:46:25 — a genuine platform tear-down-and-re-download. A
`sync_appdata_mirror.py` content overwrite replaces file bytes in place and leaves the
directory's CreationTime untouched, so directory re-creation is the discriminator.

**Evidence caveat, recorded deliberately (v1.13 doctrine).** The pre-click state was
*contaminated* and would have read as "already installed" to a careless pass: `ListSkills`
already returned the skill enabled at v3.1, and all 5 cache files already hashed identical
to the repo. Both were untrustworthy — the pre-commit mirror-sync hook had overwritten the
cache files at 16:31:01–16:31:09 (before the 16:31:50 commit), which is the
hash-match-by-construction case, and the account-side v3.1 description was consistent with
a 16:21:45 *pre-commit* build whose contents the hook had already erased locally. The
ledger still listing the skill pending, plus the absence of any corroborating sync cycle,
is what correctly kept this on the install path.

**`main.log` was unavailable as corroboration on this machine.** `main.log` has not been
written since 2026-08-20 20:51:03 ("going down for update"); there is no 2026-08-21
`SkillsPlugin` activity in any log file in `%APPDATA%\Claude\logs`. Step 2's normal
Delta→Sync-complete corroboration could not be obtained, so the directory-recreation
timestamp above was used as the first-hand substitute. **Standing consequence: while the
desktop build is not writing main.log, the step-2 short-circuit gate cannot be satisfied
at all — every skill will read as un-corroborated, and cache-directory CreationTime is the
fallback discriminator.**

**Ledger.** `pending_reimport.py clear acquisition-proposal-generation` run only AFTER
this append returned exit 0. The other 5 pending entries (daily-brief,
insurance-renewal-review, listing-agreement-qc, register-scheduled-task,
settlement-basis-extraction) were left untouched.

**Discrepancy surfaced, not repaired.** The dispatch named 8 other pending skills; the
ledger holds only 5. `debt-management`, `lease-addendum`, and `loi-generation` are NOT in
`_staging/PENDING_REIMPORT.md`. Reported, not acted on — out of scope for this task.
