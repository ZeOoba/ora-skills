$ErrorActionPreference = 'Continue'
$out = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\local_e1460d82-7046-46bd-bf0d-ac5628773e96\outputs'
Get-ChildItem $out -Filter *.skill | Remove-Item -Force
python 'C:\Users\Owner\ora-skills\tools\package_skills.py' $out register-scheduled-task daily-brief legal-intelligence automation-health-monitor lease-abstraction-pipeline loi-generation lease-renewal-pipeline exception-detection 2>&1
Write-Output ("exit: " + $LASTEXITCODE)
