$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Owner\ora-skills'
Write-Output '=== PENDING_REIMPORT ledger ==='
python tools\pending_reimport.py list
Write-Output '=== publish-status dogfood ==='
python tools\skill_drift_report.py --publish-status insurance-renewal-review package-and-stage-skill capex-budgeting
