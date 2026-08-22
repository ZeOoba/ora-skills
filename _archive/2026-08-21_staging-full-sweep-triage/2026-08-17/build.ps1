Set-Location C:\Users\Owner\ora-skills
Write-Output "---PLUGIN_OF---"
python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print(plugin_of('package-and-stage-skill'));print(plugin_of('listing-agreement-qc'))"
Write-Output "---PACKAGE---"
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-17" package-and-stage-skill
Write-Output "---EXIT---"
Write-Output $LASTEXITCODE
Write-Output "---STAGED---"
Get-ChildItem "C:\Users\Owner\ora-skills\_staging\2026-08-17" -Filter *.skill | ForEach-Object { $_.Name + "  " + $_.Length }
