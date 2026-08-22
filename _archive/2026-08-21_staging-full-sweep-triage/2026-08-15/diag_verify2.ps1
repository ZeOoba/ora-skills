$ErrorActionPreference = 'Continue'
$ahmCache = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\automation-health-monitor\SKILL.md'
$ahmRepo = 'C:\Users\Owner\ora-skills\automation-health-monitor\SKILL.md'
Write-Output "=== automation-health-monitor cache vs repo hash ==="
(Get-FileHash $ahmCache -Algorithm SHA256).Hash
(Get-FileHash $ahmRepo -Algorithm SHA256).Hash
Write-Output "=== searching for package-and-stage-skill cache dir ==="
Get-ChildItem -Path 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin' -Recurse -Directory -Filter 'package-and-stage-skill' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
