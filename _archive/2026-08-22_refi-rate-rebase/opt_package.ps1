Set-Location C:\Users\Owner\ora-skills
Write-Output "=== PACKAGE ==="
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-22" package-and-stage-skill
Write-Output "PACKAGER EXIT: $LASTEXITCODE"
$src = "C:\Users\Owner\ora-skills\_staging\2026-08-22\package-and-stage-skill.skill"
$dstDir = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\_skill_transfer"
Copy-Item $src -Destination $dstDir -Force
Write-Output "=== HASHES ==="
Get-FileHash $src -Algorithm SHA256 | Select-Object -ExpandProperty Hash
Get-FileHash (Join-Path $dstDir "package-and-stage-skill.skill") -Algorithm SHA256 | Select-Object -ExpandProperty Hash
Write-Output "=== PUSH ==="
git push origin main
Write-Output "PUSH EXIT: $LASTEXITCODE"
git status -sb | Select-Object -First 1
