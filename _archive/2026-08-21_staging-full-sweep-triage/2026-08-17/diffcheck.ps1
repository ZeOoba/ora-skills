Set-Location C:\Users\Owner\ora-skills
git diff --stat -- package-and-stage-skill/SKILL.md
Write-Output "---HUNKS---"
git diff --unified=0 -- package-and-stage-skill/SKILL.md | Select-String '^@@' | ForEach-Object { $_.Line }
Write-Output "---STATUS---"
git status --short
