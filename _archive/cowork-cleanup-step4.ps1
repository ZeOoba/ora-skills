$ErrorActionPreference = 'Continue'
$repo  = 'C:\Users\Owner\ora-skills'
$cache = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'
New-Item -ItemType Directory -Force -Path "$repo\_archive\monthly-close_v1.1_archived-2026-06-11" | Out-Null
Copy-Item "$repo\monthly-close\SKILL.md" "$repo\_archive\monthly-close_v1.1_archived-2026-06-11\SKILL.md" -Force
Copy-Item "$cache\monthly-close\SKILL.md" "$repo\monthly-close\SKILL.md" -Force
Write-Output "--- monthly-close synced; new frontmatter: ---"
Get-Content "$repo\monthly-close\SKILL.md" -TotalCount 3 | Select-Object -Last 1 | ForEach-Object { $_.Substring(0, 120) }
Set-Location $repo
Write-Output "--- git status ---"
git status --short
git remote -v
