$ErrorActionPreference = 'Continue'
$pasCache = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\package-and-stage-skill\SKILL.md'
$pasRepo = 'C:\Users\Owner\ora-skills\package-and-stage-skill\SKILL.md'
Write-Output "=== package-and-stage-skill cache vs repo hash ==="
(Get-FileHash $pasCache -Algorithm SHA256).Hash
(Get-FileHash $pasRepo -Algorithm SHA256).Hash
Write-Output "=== main.log recent sync entries ==="
$mainlog = "$env:APPDATA\Claude\logs\main.log"
if (Test-Path $mainlog) {
  Select-String -Path $mainlog -Pattern "automation-health-monitor|package-and-stage-skill|Sync complete" | Select-Object -Last 25 | ForEach-Object { $_.Line }
} else {
  Write-Output "main.log not found at $mainlog"
}
