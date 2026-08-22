$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\Owner\ora-skills'
$outdir = 'C:\Users\Owner\ora-skills\_staging\2026-08-22_reimport-batch6'
python tools\package_skills.py $outdir package-and-stage-skill
Write-Output "EXIT CODE: $LASTEXITCODE"
Get-ChildItem $outdir -Filter '*.skill' | ForEach-Object { Write-Output ($_.Name + ' | ' + $_.Length + ' bytes') }
