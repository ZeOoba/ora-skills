## 2026-07-21 — 15-skill Save-skill batch confirmed installed (Entry point B pre-packaged install)

Companion to the same-day "21 index-unregistered skills" backfill entry above: the 14 re-staged skills plus the 1 held skill (acquisition-underwriting) — 15 total — were packaged today via `tools/package_skills.py` in an earlier Code-surface session, hash-verified against the repo at package time, and handed off to this Cowork session for install via `package-and-stage-skill` Entry point B (pre-packaged install, steps 5-8 only).

**Step 0 (plugin-membership gate):** `plugin_of()` returned `None` for all 15 — none are shadowed by a plugin bundle; standalone Save-skill path confirmed correct for every package.

**Integrity pre-check (per package, before surfacing):** exists · zip entries forward-slash, expected file set matches repo dir · SKILL.md byte-identical to repo · `SHARED_ROOT_DEPS` `target-markets.json` byte-identical to repo root for the 3 consumers in this batch (acquisition-underwriting, deal-comparison, rent-comp). No package rejected back to Entry point A.

**Gabriel confirmed the Save-skill click on all 15.** Post-install verification: every packaged file present and content-identical in the runtime cache mirror (`...\skills-plugin\...\skills\<skill>\`) for all 15 — no missing files, no stale content. Runtime-cache `SKILL.md` mtimes cluster 2026-07-21 16:31:14-16:33:43, consistent with sequential clicks landing this session (not stale pre-existing cache), including acquisition-underwriting (16:31:14) — closing the gap the 2026-07-18 doctrine review had logged as still awaiting this click, independent of content freshness (content was already byte-identical pre-click, per that entry).

**Confirmed installs (skill v version):**
- acquisition-underwriting v4.3
- census-acs-extract v1.0
- communication-intelligence v1.2
- conversation-archival v2.0
- deal-comparison v1.0
- document-assembly v1.3
- file-reconciliation v1.0
- fleet-advisory-remediation v1.1
- graph-app-registration v1.0
- legal-intelligence v1.1
- orphaned-task-forensics v1.1
- portfolio-growth v1.0
- portfolio-reporting v1.1
- rent-comp v1.1
- tenant-intelligence v1.0

`pending_reimport.py clear <skill>` run for all 15 post-verification. The 6 skills backfill-confirmed earlier today (exception-detection, deal-execution, loi-generation, owner-outreach, disposition-analysis, market-monitor) were untouched, per instruction — no click needed for those.
