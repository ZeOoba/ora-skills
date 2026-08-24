Set-Location C:\Users\Owner\ora-skills
python _staging\archive_pass2.py
Write-Output "EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { exit 1 }
Remove-Item acquisition-underwriting\versions\CHANGELOG-v3.2-v4.9.md -Force
Write-Output "=== GATE ==="
python _staging\fm_gate.py acquisition-underwriting
Write-Output "=== SIZES ==="
Get-ChildItem acquisition-underwriting\SKILL.md,acquisition-underwriting\versions\*.md | Select-Object Name,Length
Write-Output "=== SANITY: refi rate + v4.14 content still intact ==="
Select-String -Path acquisition-underwriting\SKILL.md -SimpleMatch -Pattern 'fixed rate **6.50%**' | ForEach-Object { "refi 6.50 line $($_.LineNumber)" }
Select-String -Path acquisition-underwriting\SKILL.md -SimpleMatch -Pattern 'STAGE -1 item 8' | ForEach-Object { "v4.14 item1 ref line $($_.LineNumber)" }
Select-String -Path acquisition-underwriting\SKILL.md -SimpleMatch -Pattern 'Conventions-change consumer sweep' | ForEach-Object { "consumer sweep line $($_.LineNumber)" }
Write-Output "=== GIT STATUS ==="
git status --short -- acquisition-underwriting/
