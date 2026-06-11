$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Owner\ora-skills'
git add -A
git commit -m "Enforce 1024-char description limit: package_skills.py frontmatter validation (name match, description presence/length); trim lease-abstraction-pipeline (1365->1019) and psa-reconciliation (1083->922) descriptions; add tools/desc_lengths.py report"
git push origin main 2>&1
git log --oneline -1
Write-Output '=== END ==='
