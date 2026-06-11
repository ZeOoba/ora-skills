$repo = 'C:\Users\Owner\ora-skills'
$pat = 'NOTION_QUERY_DATABASE_WITH_FILTER|OUTLOOK_SEND_EMAIL|Composio recipe|Composio connection active|ze@oxfordra|outlook-handoff|email-archival|vendor-coi-autoextract|title-commitment-redline'
Write-Output '=== SWEEP (active dirs, should be empty or retired-context only) ==='
Get-ChildItem -Recurse $repo -Include *.md,*.py |
  Where-Object { $_.FullName -notmatch '\\(_archive|\.git|versions)\\' } |
  Select-String -Pattern $pat |
  ForEach-Object { ($_.Path.Replace($repo,'')) + ':' + $_.LineNumber + ': ' + ($_.Line.Trim().Substring(0, [Math]::Min(140, $_.Line.Trim().Length))) }
Write-Output '=== GIT ==='
Set-Location $repo
git fetch origin 2>&1
git status -sb | Select-Object -First 2
git add -A
git commit -m "Recommendations pass 2026-06-11: lease-renewal-pipeline migrated to Notion MCP (Composio paginator archived); exception-detection v1.1 Composio checks retired; lease-abstraction SCHEDULED_TASK.md COM-only dependency; aux files synced into repo"
git log --oneline -2
git push origin main 2>&1
Write-Output '=== END ==='
