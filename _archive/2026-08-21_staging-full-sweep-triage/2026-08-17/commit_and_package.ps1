$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Owner\ora-skills'
Write-Output '=== staging only the target skill ==='
git add register-scheduled-task/SKILL.md register-scheduled-task/references/incident-history.md
git status --short -- register-scheduled-task/
Write-Output '=== commit ==='
git commit -m "fix(register-scheduled-task): v2.12 -- a bounded pause must register its resume per fleet, same session/surface/pass

Root incident 2026-08-17: 'pause all routines until Friday 5pm' was executed
on CC/MCP with a resume registered (ora-routine-pause-resume-08-21, fires
2026-08-21 17:00 ET) while the LAMS/Cowork counterpart pause committed with no
resume at all -- its registration was dispatched to a cloud-sandbox Cowork
session with no registry MCP tools, which correctly halted at Rule 1, but only
after the pause had landed. Verified read-only same day: CC 35/40 disabled with
a resume pending, LAMS 27/28 disabled with none.

Also codified, beyond the originally proposed patch:
- re-hinged the rule on a BOUNDED pause (stated end) rather than a BULK one --
  a single task paused 'until Friday' fails identically
- 'pause all routines' is fleet-ambiguous; resolve against both registries
- never blanket-pause ora-cowork-heartbeat / automation-health-monitor -- both
  live on LAMS, so the sweep silenced the detectors for its own failure
- a resume must NOT re-stamp [MODEL:] dates; qualifies the v2.8 re-enable
  re-tag rule, which contradicted the live resume task's own step 5

Doc-only. No registration, cron, or archive-first-delete-second logic changed."
Write-Output '=== log ==='
git log -1 --format='%h %ad %s' --date=short
Write-Output '=== package ==='
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-17" register-scheduled-task
Write-Output ('=== packager exit: ' + $LASTEXITCODE + ' ===')
