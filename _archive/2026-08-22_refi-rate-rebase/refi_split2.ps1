Set-Location C:\Users\Owner\ora-skills
Write-Output "=== SOFT RESET ==="
git reset --soft HEAD~1
Write-Output "=== UNSTAGE HARNESS WIP ==="
git restore --staged acquisition-underwriting-eval-harness/
Write-Output "=== STAGED NOW ==="
git diff --cached --name-only
Write-Output "=== RECOMMIT (no-verify: mirror sync already ran this cycle) ==="
git commit --no-verify -m "feat(acquisition-underwriting): refi rate default 7.00% -> 6.50% (v4.13)"
Write-Output "EXIT: $LASTEXITCODE"
Write-Output "=== VERIFY ==="
git show --stat --oneline HEAD
Write-Output "=== WORKING TREE (harness WIP should be back to modified) ==="
git status -sb
