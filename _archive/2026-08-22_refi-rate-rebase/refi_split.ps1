Set-Location C:\Users\Owner\ora-skills
Write-Output "=== REMOTE STATE (is febb870 pushed?) ==="
git rev-parse HEAD
git rev-parse '@{u}'
git status -sb | Select-Object -First 1
