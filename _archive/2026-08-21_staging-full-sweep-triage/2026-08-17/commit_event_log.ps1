$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Owner\.claude'
git add 'projects\C--Users-Owner-OneDrive---Oxford-Capital-Partners\memory\event_log.md'
git status --short -- 'projects\C--Users-Owner-OneDrive---Oxford-Capital-Partners\memory\event_log.md'
git commit -m "chore(memory): commit event_log.md backlog (6 entries)

Isolated commit -- only event_log.md, per dirty-tree-triage's isolate-and-
commit discipline. Five other memory files (INDEX_reference.md, MEMORY.md,
open-items-tracker.md, reference_ora_pm.md, rules.md) are also dirty in this
tree but left untouched: no provenance established for them in this session,
so they are not swept in with an unrelated commit."
git log -1 --format='%h %ad %s' --date=short
Write-Output '--- remaining dirty (untouched, flagged only) ---'
git status --short
