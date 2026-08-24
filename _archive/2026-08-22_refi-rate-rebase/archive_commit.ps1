Set-Location C:\Users\Owner\ora-skills
Write-Output "=== STAGE MY PATHS ONLY ==="
git add acquisition-underwriting/SKILL.md acquisition-underwriting/versions/CHANGELOG-v3.2-v4.11.md acquisition-underwriting/versions/CHANGELOG-v3.2-v4.7.md
Write-Output "=== INDEX PRE-COMMIT (snapshot, not a lock) ==="
git diff --cached --name-only
Write-Output "=== COMMIT BY PATHSPEC ==="
git commit -m "docs(acquisition-underwriting): v4.15 - archive v4.8-v4.11, add conventions-change consumer sweep" -- acquisition-underwriting/SKILL.md acquisition-underwriting/versions/CHANGELOG-v3.2-v4.11.md acquisition-underwriting/versions/CHANGELOG-v3.2-v4.7.md
Write-Output "COMMIT EXIT: $LASTEXITCODE"
Write-Output "=== POST-COMMIT VERIFY (only my files) ==="
git show --stat --oneline HEAD
Write-Output "=== PACKAGE ==="
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
git status -sb | Select-Object -First 1
