Set-Location C:\Users\Owner\ora-skills
git add -- package-and-stage-skill/SKILL.md
git commit -F C:\Users\Owner\ora-skills\_staging\2026-08-17\msg.txt
Write-Output "---LOG---"
git log -2 --oneline
Write-Output "---STATUS---"
git status --short
Write-Output "---UNPUSHED---"
git log origin/main..HEAD --oneline
