$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\Owner\ora-skills'
$outdir = 'C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch3'
python tools\package_skills.py $outdir deal-execution debt-management document-assembly estoppel-request-generation lease-abstraction-pipeline legal-intelligence
Write-Output "EXIT CODE: $LASTEXITCODE"
Get-ChildItem $outdir -Filter '*.skill' | ForEach-Object { Write-Output ($_.Name + ' | ' + $_.Length + ' bytes') }
