Set-Location C:\Users\Owner\ora-skills
Write-Output "=== STAGE (each separately so one miss cannot abort the rest) ==="
git add acquisition-underwriting/SKILL.md
Write-Output "add SKILL.md exit: $LASTEXITCODE"
git add acquisition-underwriting/versions/CHANGELOG-v3.2-v4.11.md
Write-Output "add new archive exit: $LASTEXITCODE"
Write-Output "=== INDEX PRE-COMMIT ==="
git diff --cached --name-status
Write-Output "=== COMMIT BY PATHSPEC (skill dir) ==="
git commit -m "docs(acquisition-underwriting): v4.15 - archive v4.8-v4.11, add conventions-change consumer sweep" -- acquisition-underwriting/
Write-Output "COMMIT EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { Write-Output "ABORT"; exit 1 }
Write-Output "=== POST-COMMIT VERIFY ==="
git show --stat --oneline HEAD
Write-Output "=== REPACKAGE FROM COMMITTED TREE ==="
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-22" acquisition-underwriting
Write-Output "PACKAGER EXIT: $LASTEXITCODE"
$src = "C:\Users\Owner\ora-skills\_staging\2026-08-22\acquisition-underwriting.skill"
$dst = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\_skill_transfer"
Copy-Item $src -Destination $dst -Force
Get-FileHash $src -Algorithm SHA256 | Select-Object -ExpandProperty Hash
Get-FileHash (Join-Path $dst "acquisition-underwriting.skill") -Algorithm SHA256 | Select-Object -ExpandProperty Hash
Write-Output "=== PUSH ==="
git push origin main
Write-Output "PUSH EXIT: $LASTEXITCODE"
git status -sb
