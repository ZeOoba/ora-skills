Write-Output "=== DEFAULT LOG PATH ==="
Select-String -Path C:\Users\Owner\.claude\maintenance\append-event-log.py -Pattern 'default|LOG' |
  Select-Object -First 8 | ForEach-Object { $_.Line.Trim() }
Write-Output "=== RECENT HEADERS ==="
$log = "C:\Users\Owner\.claude\projects\C--Users-Owner-OneDrive---Oxford-Capital-Partners\memory\event_log.md"
if (Test-Path $log) {
  Select-String -Path $log -Pattern '^## ' | Select-Object -First 5 | ForEach-Object { $_.Line }
} else { Write-Output "LOG NOT AT EXPECTED PATH" }
