$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Owner\ora-skills'
python -c "import py_compile; py_compile.compile('tools/pause_resume.py', doraise=True); print('compiles OK')"
git add tools/pause_resume.py
git status --short -- tools/pause_resume.py
git commit -m "feat(tools): add pause_resume.py -- fleet-symmetry check + resume-task generator

Companion to register-scheduled-task v2.12's 'Bounded pause' rule. Two
subcommands, both read-only against the registry (never registers anything --
that stays MCP-only per Rule 1):

  status       walks both fleet registries, flags any disabled RECURRING task
               with no live ENABLED one-time resume mentioning its id, and
               separately flags ora-cowork-heartbeat / automation-health-monitor
               if either is among the uncovered set (the two mechanisms that
               would otherwise surface a missed resume).

  gen-resume   emits a resume SKILL.md from the LIVE disabled-recurring-task
               list for one fleet, instead of hand-typing/copy-pasting ids --
               the exact step that silently dropped the LAMS resume in the
               2026-08-17 incident this tool exists to prevent.

Verified against the live registry same day: `status` reproduced the incident
exactly (CC/MCP 0 missing, LAMS 26 missing incl. both detectors), and
`gen-resume --fleet lams` produced a 25-id list identical to the hand-authored
draft it replaced."
git log -1 --format='%h %ad %s' --date=short
