Set-Location C:\Users\Owner\ora-skills
Write-Output "=== FRONTMATTER GATE ==="
python _staging\fm_gate.py acquisition-underwriting
Write-Output "GATE EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { Write-Output "ABORT - gate failed"; exit 1 }
Write-Output "=== STAGE + COMMIT (skill dir only) ==="
git add acquisition-underwriting/SKILL.md acquisition-underwriting/references/ic-memo-structure.md
git commit -m "feat(acquisition-underwriting): refi rate default 7.00% -> 6.50% (v4.13)"
Write-Output "COMMIT EXIT: $LASTEXITCODE"
git log -1 --oneline
Write-Output "=== PACKAGE ==="
New-Item -ItemType Directory -Force -Path "C:\Users\Owner\ora-skills\_staging\2026-08-22" | Out-Null
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-22" acquisition-underwriting
Write-Output "PACKAGER EXIT: $LASTEXITCODE"
Get-ChildItem "C:\Users\Owner\ora-skills\_staging\2026-08-22" | Select-Object Name,Length
