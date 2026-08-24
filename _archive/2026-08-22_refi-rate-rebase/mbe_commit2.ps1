Set-Location C:\Users\Owner\ora-skills
python _staging\fm_gate.py model-bulk-edit
Write-Output "GATE EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { exit 1 }
python -c "import ast;ast.parse(open(r'model-bulk-edit/scripts/cached_value_lint.py',encoding='utf8').read());print('syntax OK')"
git add model-bulk-edit/SKILL.md model-bulk-edit/scripts/cached_value_lint.py
git diff --cached --name-only
git commit -m "fix(model-bulk-edit): v1.1 - read_only load, 9.1GB -> 48MB peak; arg-quoting trap" -- model-bulk-edit/
Write-Output "COMMIT EXIT: $LASTEXITCODE"
git show --stat --oneline HEAD
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-22" model-bulk-edit
Write-Output "PACKAGER EXIT: $LASTEXITCODE"
$src = "C:\Users\Owner\ora-skills\_staging\2026-08-22\model-bulk-edit.skill"
$dst = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\_skill_transfer"
Copy-Item $src -Destination $dst -Force
Get-FileHash $src -Algorithm SHA256 | Select-Object -ExpandProperty Hash
git push origin main
Write-Output "PUSH EXIT: $LASTEXITCODE"
