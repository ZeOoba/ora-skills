Set-Location C:\Users\Owner\ora-skills
git add package-and-stage-skill/SKILL.md
git commit -m "docs(package-and-stage-skill): v1.15 -- bridge carve-out for step 7, host-shell script-file discipline, cloud staging path" -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>" -m "Claude-Session: https://claude.ai/code/session_0116KdTcmebXZxX5NmBVWpnq"
Write-Output "COMMIT_EXIT: $LASTEXITCODE"
git log -1 --format="%h %s"
git push origin main
Write-Output "PUSH_EXIT: $LASTEXITCODE"
Write-Output "=== STATUS ==="
git status --short
Write-Output "=== PACKAGE ==="
python tools\package_skills.py C:\Users\Owner\ora-skills\_staging\2026-08-14 package-and-stage-skill
Write-Output "PKG_EXIT: $LASTEXITCODE"
$f = "C:\Users\Owner\ora-skills\_staging\2026-08-14\package-and-stage-skill.skill"
Write-Output ((Get-Item $f).Length.ToString() + " " + (Get-FileHash $f -Algorithm SHA256).Hash)
Write-Output "=== LEDGER ==="
python tools/pending_reimport.py list
Write-Output "=== DONE ==="
