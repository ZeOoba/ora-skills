Set-Location "C:\Users\Owner\ora-skills"
python "_staging\2026-08-14\_check_pss_full.py"
git log -1 --format="%H %ci %s"
git merge-base --is-ancestor 899b10b HEAD
if ($LASTEXITCODE -eq 0) { Write-Output '899b10b IS_ANCESTOR' } else { Write-Output '899b10b NOT_ANCESTOR' }
git status --short -- package-and-stage-skill/
