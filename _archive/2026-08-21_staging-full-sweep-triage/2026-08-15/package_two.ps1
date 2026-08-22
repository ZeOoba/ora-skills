Set-Location 'C:\Users\Owner\ora-skills'
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-15" insurance-renewal-review package-and-stage-skill
Write-Host "packager exit: $LASTEXITCODE"
Get-ChildItem "C:\Users\Owner\ora-skills\_staging\2026-08-15\insurance-renewal-review.skill","C:\Users\Owner\ora-skills\_staging\2026-08-15\package-and-stage-skill.skill" -ErrorAction SilentlyContinue | Select-Object Name, Length
