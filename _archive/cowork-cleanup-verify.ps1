$repo = 'C:\Users\Owner\ora-skills'
$pat = 'ze@oxfordra|outlook-handoff|email-archival|vendor-coi-autoextract|institutional-output-standards|title-commitment-redline|Claude_pzs8sxrjxfjjc|splice|Composio|9 scheduled tasks|31-item|Principal at Oxford'
Get-ChildItem -Recurse $repo -Include *.md,*.py,*.json |
  Where-Object { $_.FullName -notmatch '\\(_archive|\.git)\\' } |
  Select-String -Pattern $pat |
  ForEach-Object { ($_.Path.Replace($repo,'')) + ':' + $_.LineNumber + ': ' + ($_.Line.Trim().Substring(0, [Math]::Min(160, $_.Line.Trim().Length))) }
Write-Output '=== END SWEEP ==='
