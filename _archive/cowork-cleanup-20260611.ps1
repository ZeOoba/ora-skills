$ErrorActionPreference = 'Stop'
$src  = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\local_63860b09-fe36-44a3-8f6d-0232b8bf9b03\outputs'
$repo = 'C:\Users\Owner\ora-skills'
New-Item -ItemType Directory -Force -Path "$repo\register-scheduled-task","$repo\daily-brief","$repo\legal-intelligence","$repo\_archive\lease-abstraction-pipeline_v1.2_archived-2026-06-11" | Out-Null
Copy-Item "$repo\lease-abstraction-pipeline\SKILL.md" "$repo\_archive\lease-abstraction-pipeline_v1.2_archived-2026-06-11\SKILL.md" -Force
Copy-Item "$src\20260611_register-scheduled-task_SKILL_v2.0.md" "$repo\register-scheduled-task\SKILL.md" -Force
Copy-Item "$src\20260611_daily-brief_SKILL_v2.5.md" "$repo\daily-brief\SKILL.md" -Force
Copy-Item "$src\20260611_legal-intelligence_SKILL_v1.1.md" "$repo\legal-intelligence\SKILL.md" -Force
Copy-Item "$src\20260611_lease-abstraction-pipeline_SKILL_v2.1.md" "$repo\lease-abstraction-pipeline\SKILL.md" -Force
Get-ChildItem -Recurse $repo -Filter SKILL.md | Where-Object { $_.FullName -notmatch '\\\.git' } |
  Select-Object @{n='Path';e={$_.FullName.Replace($repo,'')}}, Length, LastWriteTime |
  Format-Table -AutoSize | Out-String -Width 220
