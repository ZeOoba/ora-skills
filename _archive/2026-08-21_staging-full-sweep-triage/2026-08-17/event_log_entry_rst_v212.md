## 2026-08-17 -- register-scheduled-task v2.12 packaged + staged (bounded-pause resume rule)

Cloud Cowork session, Desktop Commander bridge live. Gabriel handed over a
proposed v2.11 -> v2.12 patch ("bulk pause must register its own auto-resume").
Adopted with corrections and expansions; committed to the repo as 655c346.

WHAT WAS VERIFIED FIRST (read-only, both registries):
- CC/MCP: 35 of 40 tasks disabled; one-time resume `ora-routine-pause-resume-08-21`
  registered and enabled, fireAt 2026-08-21 17:00 ET, naming all 35 ids.
- LAMS/Cowork: 27 of 28 tasks disabled, NO resume of any kind. Sole enabled entry
  is `ora-counsel-review-standard-positions-2027` (one-time, fires 2027-08-02).
- Therefore: the CC fleet restores itself Friday; the LAMS fleet does not restore
  at all. `ora-cowork-heartbeat` and `automation-health-monitor` are both among
  the disabled LAMS tasks -- the pause silenced the detectors for its own failure.
- The proposed patch's premise was correct. Its claim that "nothing surfaces that
  asymmetry" was slightly overstated: the CC resume task's step 6 email carries a
  reminder line about the LAMS fleet -- but it does not send until 2026-08-21
  17:00 ET, i.e. at the END of the window rather than the start.

CHANGES BEYOND THE PROPOSED PATCH:
1. Re-hinged the rule on a BOUNDED pause (stated/implied end) rather than a BULK
   one. Bulk is the aggravating factor; a single task paused "until Friday" fails
   identically, and a genuinely open-ended pause has no resume to register.
2. Added: "pause all routines" is fleet-ambiguous -- resolve against both
   registries and register one resume per fleet in scope.
3. Added: never blanket-pause `ora-cowork-heartbeat` / `automation-health-monitor`
   without saying so in the same turn.
4. Added: a resume must NOT re-stamp `[MODEL:]` dates. This resolves a live
   contradiction -- the v2.8 PAUSE bullet says re-tag with a current date on
   re-enable, while the CC resume task's own step 5 correctly forbids it per
   memory/feedback_verified_null_vs_inferred_null.md. v2.12 scopes v2.8's rule to
   a hand re-enable where the model IS observed.
5. Kept the patch's `fireAt` field name -- verified correct: one-time resume tasks
   carry `fireAt`, not `cronExpression`/`nextRunAt`.
6. Incident narrative filed to references/incident-history.md, not SKILL.md
   (one fact, one home -- the size discipline from package-and-stage-skill v1.20).

PACKAGING: tools/package_skills.py exit 0; description 969/1024 (a first build hit
1069 and then 1023 -- the step-2a gate caught both before any Save-skill ask, which
is exactly the silent-rejection trap package-and-stage-skill v1.21 was written for;
trimmed explanatory text, never trigger vocabulary, to leave 55 chars of headroom).
2 entries, forward-slash paths. SHA256 fca9f4ff08e852cdc58879d193226694588c7366c19a033a9fdaff1cd840e03d.
Transferred into the cloud session via the base64+SHA256 bridge fallback (two
device_request_folder_access dialogs timed out unanswered), byte-identity asserted.

STATUS: STAGED, NOT INSTALLED. Save-skill click pending. Do NOT clear
_staging/PENDING_REIMPORT.md until the click is confirmed and the AppData cache
mirror is verified to hold BOTH packaged files.

OPEN ITEM (higher priority than this skill edit): the LAMS fleet still has no
resume. `ora-lams-routine-pause-resume-08-21` must be registered from a NATIVE
on-device Cowork session (cloud sessions carry no registry MCP tools -- Rule 1).
Draft spec staged alongside this entry.
