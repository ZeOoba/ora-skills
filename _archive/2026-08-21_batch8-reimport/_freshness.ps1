Set-Location C:\Users\Owner\ora-skills

Write-Output "=== main.log liveness ==="
$log = "$env:APPDATA\Claude\logs\main.log"
if (Test-Path $log) {
  $fi = Get-Item $log
  Write-Output ("main.log LastWriteTime: " + $fi.LastWriteTime)
  Write-Output ("Now: " + (Get-Date))
  Write-Output "--- last 5 lines mentioning SkillsPlugin/Delta/Sync ---"
  Select-String -Path $log -Pattern "SkillsPlugin|Delta:|Sync complete" | Select-Object -Last 15 | ForEach-Object { $_.Line }
} else {
  Write-Output "main.log NOT FOUND at $log"
}

Write-Output ""
Write-Output "=== locating skills-plugin cache root ==="
$cacheRoots = @()
$candidates = @(
  "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin",
  "$env:LOCALAPPDATA\Claude\local-agent-mode-sessions\skills-plugin"
)
foreach ($c in $candidates) {
  if (Test-Path $c) { Write-Output "FOUND: $c"; $cacheRoots += $c }
}
