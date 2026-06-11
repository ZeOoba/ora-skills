$ErrorActionPreference = 'Continue'
$repo  = 'C:\Users\Owner\ora-skills'
$cache = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'
New-Item -ItemType Directory -Force -Path "$repo\_archive\lease-renewal-pipeline_pre-notionmcp_2026-06-11" | Out-Null
Copy-Item "$repo\lease-renewal-pipeline\SKILL.md" "$repo\_archive\lease-renewal-pipeline_pre-notionmcp_2026-06-11\SKILL.md" -Force
Copy-Item "$cache\lease-renewal-pipeline\SKILL.md" "$repo\lease-renewal-pipeline\SKILL.md" -Force
Copy-Item "$cache\lease-renewal-pipeline\references" "$repo\_archive\lease-renewal-pipeline_pre-notionmcp_2026-06-11\references" -Recurse -Force
New-Item -ItemType Directory -Force -Path "$repo\exception-detection" | Out-Null
Copy-Item "$cache\exception-detection\SKILL.md" "$repo\exception-detection\SKILL.md" -Force
Write-Output '--- cache dir inventories (for .skill bundling) ---'
Get-ChildItem -Recurse $cache | Where-Object { -not $_.PSIsContainer } | ForEach-Object { $_.FullName.Replace($cache,'') }
