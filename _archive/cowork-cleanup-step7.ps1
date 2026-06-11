$ErrorActionPreference = 'Stop'
$cache = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'
$repo  = 'C:\Users\Owner\ora-skills'
New-Item -ItemType Directory -Force -Path "$repo\lease-abstraction-pipeline\references" | Out-Null
Copy-Item "$cache\lease-abstraction-pipeline\SCHEDULED_TASK.md" "$repo\lease-abstraction-pipeline\SCHEDULED_TASK.md" -Force
Copy-Item "$cache\lease-abstraction-pipeline\references\extraction-edge-cases.md" "$repo\lease-abstraction-pipeline\references\extraction-edge-cases.md" -Force
Get-ChildItem -Recurse "$repo\lease-abstraction-pipeline" | ForEach-Object { $_.FullName.Replace($repo,'') }
