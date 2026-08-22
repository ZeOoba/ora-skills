$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\Owner\ora-skills'
$outdir = 'C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch4'
python tools\package_skills.py $outdir isolated-commit lease-addendum loi-generation
Write-Output "EXIT CODE: $LASTEXITCODE"
Get-ChildItem $outdir -Filter '*.skill' | ForEach-Object { Write-Output ($_.Name + ' | ' + $_.Length + ' bytes') }
