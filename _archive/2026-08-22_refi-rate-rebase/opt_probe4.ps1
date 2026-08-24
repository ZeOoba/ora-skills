Set-Location C:\Users\Owner\ora-skills
Write-Output "=== STAGED DIFF: acquisition-underwriting/SKILL.md (vs HEAD) ==="
git diff --cached --stat -- acquisition-underwriting/SKILL.md
git diff --cached -- acquisition-underwriting/SKILL.md | Select-Object -First 60
Write-Output "=== IS MY v4.13 STILL ON DISK? ==="
Select-String -Path acquisition-underwriting\SKILL.md -SimpleMatch -Pattern 'fixed rate **6.50%**' | ForEach-Object { "DISK refi: line $($_.LineNumber) OK" }
Select-String -Path acquisition-underwriting\SKILL.md -SimpleMatch -Pattern 'v4.13 (2026-08-22)' | ForEach-Object { "DISK v4.13 header: line $($_.LineNumber) OK" }
Write-Output "=== IS MY v4.13 IN THE INDEX? ==="
git show :acquisition-underwriting/SKILL.md | Select-String -SimpleMatch -Pattern 'fixed rate **6.50%**' | ForEach-Object { "INDEX refi 6.50: line $($_.LineNumber)" }
Write-Output "=== OTHER STAGED FILES DIFFSTAT ==="
git diff --cached --stat
