$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Owner\ora-skills'
git add -A
git commit -m "tools/package_skills.py + README packaging rule: never Compress-Archive (PS5.1 backslash zip-entry bug breaks Cowork skill import); always package via python tools/package_skills.py"
git push origin main 2>&1
git log --oneline -1
Write-Output '=== END ==='
