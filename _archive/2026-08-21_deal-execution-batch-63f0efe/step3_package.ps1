Set-Location "C:\Users\Owner\ora-skills"
$outdir = "C:\Users\Owner\ora-skills\_staging\2026-08-21"
python tools\package_skills.py "$outdir" deal-execution document-assembly estoppel-request-generation lease-abstraction-pipeline legal-intelligence package-and-stage-skill
Write-Output "EXIT CODE: $LASTEXITCODE"
