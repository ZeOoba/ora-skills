$cache = "C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills"
$skills = @('lease-addendum','document-assembly','exception-detection','package-and-stage-skill')
foreach ($s in $skills) {
  Write-Output "=== CACHE: $s ==="
  $d = Join-Path $cache $s
  if (Test-Path $d) {
    Get-ChildItem -Recurse -File $d | ForEach-Object { $_.FullName.Replace("$d\","") + " | " + $_.LastWriteTime }
  } else { Write-Output "ABSENT" }
}
Write-Output "=== MAIN.LOG SYNC LINES (today) ==="
$log = "C:\Users\Owner\AppData\Roaming\Claude\logs\main.log"
Select-String -Path $log -Pattern "Delta|Sync complete" | Select-Object -Last 12 | ForEach-Object { $_.Line }
Write-Output "=== APPEND-EVENT-LOG LOCATION ==="
Get-ChildItem -Path "C:\Users\Owner\.claude" -Recurse -Filter "append-event-log.py" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
Write-Output "=== DEVICE TIME ==="
Get-Date -Format "yyyy-MM-ddTHH:mm:ssK"
Write-Output "=== DONE ==="
