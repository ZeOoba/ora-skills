Set-Location C:\Users\Owner\ora-skills
Write-Output "---DIFFSTAT---"
git diff --stat -- register-scheduled-task/SKILL.md
Write-Output "---HUNKS---"
git diff --unified=1 -- register-scheduled-task/SKILL.md | Select-Object -First 40
Write-Output "---RESCUE DIR---"
Get-ChildItem C:\Users\Owner\ora-skills\_staging\repo-first-rescue -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName + "  " + $_.Length }
Write-Output "---PENDING---"
Get-Content C:\Users\Owner\ora-skills\_staging\PENDING_REIMPORT.md -Tail 12 -ErrorAction SilentlyContinue
