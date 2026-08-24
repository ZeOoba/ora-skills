Set-Location C:\Users\Owner\ora-skills
Write-Output "=== PRE-CHECK: is acquisition-underwriting contested right now? ==="
git status --short -- acquisition-underwriting/
Write-Output "(empty above = clean, safe to edit)"
Write-Output "=== RUN ARCHIVE ==="
python _staging\archive_changelog.py
Write-Output "EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { exit 1 }
Write-Output "=== GIT MV old archive name ==="
git rm --cached acquisition-underwriting/versions/CHANGELOG-v3.2-v4.7.md 2>&1 | Out-Null
Remove-Item acquisition-underwriting\versions\CHANGELOG-v3.2-v4.7.md -Force
Write-Output "=== FRONTMATTER GATE ==="
python _staging\fm_gate.py acquisition-underwriting
Write-Output "GATE EXIT: $LASTEXITCODE"
Write-Output "=== SIZE ==="
Get-ChildItem acquisition-underwriting\SKILL.md,acquisition-underwriting\versions\*.md | Select-Object Name,Length
