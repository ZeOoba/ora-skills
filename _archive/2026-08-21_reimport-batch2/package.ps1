$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\Owner\ora-skills'
$outdir = 'C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch2'
python tools\package_skills.py $outdir insurance-renewal-review package-and-stage-skill dirty-tree-triage
Write-Output "EXIT CODE: $LASTEXITCODE"
Get-ChildItem $outdir -Filter '*.skill' | ForEach-Object { Write-Output ($_.Name + ' | ' + $_.Length + ' bytes') }
