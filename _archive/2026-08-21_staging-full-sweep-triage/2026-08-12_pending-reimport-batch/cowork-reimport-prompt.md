Reimport 5 edited skills into the Cowork runtime cache: acquisition-underwriting,
capex-budgeting, lease-abstraction-pipeline, parcel-data-recovery,
submarket-spatial-analysis.

Context: a Code session closed out the 2026-08-05 retired-skill remediation
(rent-comp comp-grid absorbed into acquisition-underwriting per Gabriel's
scoped-restore ruling; four other skills tombstoned; a silently-skipping test
revived). Landed in ora-skills as commit d03fe62. All five SKILL.md files
changed and got a version bump (acquisition-underwriting v4.10->v4.11,
capex-budgeting v1.0->v1.1, lease-abstraction-pipeline v2.3->v2.4,
parcel-data-recovery v1.6->v1.7, submarket-spatial-analysis v1.3->v1.4). None
of the five have been reimported into the runtime cache yet -- verified via
main.log, four periodic sync cycles since the commit all show
`Delta: 0 to download, 0 to remove`.

Use the `package-and-stage-skill` skill, **Entry point A** (repackage fresh
from the current repo -- these are freshly edited SKILL.md files, not
pre-built packages; do not reuse any .skill file from an earlier session, it
may be stale). Confirm the repo is at or past commit d03fe62 before packaging
(`git log --oneline -1` in `C:\Users\Owner\ora-skills`) -- if it has moved
further, that's fine, just note the actual HEAD you packaged from.

For each of the five skills:
1. Package fresh via Entry point A's own integrity pre-check (existence, zip
   entry cleanliness, freshness vs current repo).
2. Click Save-skill.
3. **Verify the install actually happened -- do not treat "the click
   succeeded" as sufficient.** Check
   `AppData\Roaming\Claude\logs\main.log` for that skill's install: a
   `[SkillsPlugin]` line with `Delta: N to download` where N > 0 for that
   cycle, followed by `Sync complete: N downloaded, 0 failed`. If the delta
   reads 0 after your click, the install did not register -- do not report it
   as done.

**Watch specifically for acquisition-underwriting.** main.log has logged this
warning on every periodic sync since at least 2026-08-12 23:05, independent of
this batch:
```
[SkillsPlugin] Remote skill "acquisition-underwriting" maps to the same
directory as an earlier remote skill, skipping
```
If acquisition-underwriting's Save-skill click doesn't produce a non-zero
delta, this warning is the likely cause -- a directory collision on the
runtime side, not a packaging defect in this batch. Report it explicitly
either way (resolved on its own / still recurring / blocked the install).

**Do not clear anything in `ora-skills/_staging/PENDING_REIMPORT.md`.**
Ledger clearing is Code-surface only, per that file's own header and the
2026-08-12 event_log precedent (the prior 5-skill batch this same day was
installed from Cowork and explicitly left the ledger for a Code session to
clear after independently verifying the main.log delta).

When done, report per skill: version installed, the main.log timestamp +
delta line as evidence, and any anomalies (especially the
acquisition-underwriting warning above). A Code session will pick this up,
independently re-verify against main.log, and clear the five ledger entries
(`acquisition-underwriting`, `capex-budgeting`, `lease-abstraction-pipeline`,
`parcel-data-recovery`, `submarket-spatial-analysis`) once confirmed.
