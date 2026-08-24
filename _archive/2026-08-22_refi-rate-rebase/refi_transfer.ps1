$src = "C:\Users\Owner\ora-skills\_staging\2026-08-22\acquisition-underwriting.skill"
$dstDir = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\_skill_transfer"
New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
Copy-Item $src -Destination $dstDir -Force
Write-Output "=== HASHES ==="
Get-FileHash $src -Algorithm SHA256 | Select-Object Hash,Path
Get-FileHash (Join-Path $dstDir "acquisition-underwriting.skill") -Algorithm SHA256 | Select-Object Hash,Path
Write-Output "=== PACKAGED SKILL.md vs REPO SKILL.md (normalized) ==="
python C:\Users\Owner\ora-skills\_staging\verify_pkg.py
