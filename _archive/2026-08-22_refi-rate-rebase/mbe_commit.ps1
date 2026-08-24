Set-Location C:\Users\Owner\ora-skills
Write-Output "=== FRONTMATTER GATE ==="
python _staging\fm_gate.py model-bulk-edit
Write-Output "GATE EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { Write-Output "ABORT"; exit 1 }
Write-Output "=== PLUGIN ROUTING GATE ==="
python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print(plugin_of('model-bulk-edit'))"
Write-Output "=== LINT SELF-TEST (script must run clean on a known-good tree) ==="
python model-bulk-edit\scripts\cached_value_lint.py "C:\Users\Owner\ora-skills\_staging" --quiet
Write-Output "SELFTEST EXIT: $LASTEXITCODE"
Write-Output "=== STAGE + COMMIT BY PATHSPEC ==="
git add model-bulk-edit/SKILL.md model-bulk-edit/scripts/cached_value_lint.py
git diff --cached --name-only
git commit -m "feat(model-bulk-edit): v1.0 - bulk model edit doctrine + cached-value linter" -- model-bulk-edit/
Write-Output "COMMIT EXIT: $LASTEXITCODE"
git show --stat --oneline HEAD
Write-Output "=== PACKAGE ==="
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-22" model-bulk-edit
Write-Output "PACKAGER EXIT: $LASTEXITCODE"
$src = "C:\Users\Owner\ora-skills\_staging\2026-08-22\model-bulk-edit.skill"
$dst = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\_skill_transfer"
Copy-Item $src -Destination $dst -Force
Get-FileHash $src -Algorithm SHA256 | Select-Object -ExpandProperty Hash
Get-FileHash (Join-Path $dst "model-bulk-edit.skill") -Algorithm SHA256 | Select-Object -ExpandProperty Hash
git push origin main
Write-Output "PUSH EXIT: $LASTEXITCODE"
