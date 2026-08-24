Set-Location C:\Users\Owner\ora-skills
Write-Output "=== COMMIT CONTENTS ==="
git show --stat --oneline febb870
Write-Output "=== WORKING TREE NOW ==="
git status --short
