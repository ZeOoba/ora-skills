Set-Location C:\Users\Owner\ora-skills
python _staging\fm_gate.py package-and-stage-skill
Write-Output "GATE EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { Write-Output "ABORT"; exit 1 }
git add package-and-stage-skill/SKILL.md
git commit -m "docs(package-and-stage-skill): v1.26 - route to claim_work.py before multi-commit edits" -- package-and-stage-skill/
Write-Output "COMMIT EXIT: $LASTEXITCODE"
git show --stat --oneline HEAD
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-22" package-and-stage-skill
Write-Output "PACKAGER EXIT: $LASTEXITCODE"
$src = "C:\Users\Owner\ora-skills\_staging\2026-08-22\package-and-stage-skill.skill"
$dst = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\_skill_transfer"
Copy-Item $src -Destination $dst -Force
Get-FileHash $src -Algorithm SHA256 | Select-Object -ExpandProperty Hash
git push origin main
Write-Output "PUSH EXIT: $LASTEXITCODE"
Write-Output "=== LINT SWEEP STATUS ==="
if (Get-Process python -ErrorAction SilentlyContinue) { Write-Output "lint STILL RUNNING" } else { Write-Output "lint FINISHED" }
Get-Content C:\Users\Owner\ora-skills\_staging\lint_out.txt -ErrorAction SilentlyContinue | Select-Object -Last 30
