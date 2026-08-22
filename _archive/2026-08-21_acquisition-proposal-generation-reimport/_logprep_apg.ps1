$ErrorActionPreference = 'Continue'
foreach ($p in @(
  'C:\Users\Owner\.claude\maintenance\append-event-log.py',
  'C:\Users\Owner\.claude\projects\C--Users-Owner-OneDrive---Oxford-Capital-Partners\memory\event_log.md',
  'C:\Users\Owner\.claude\projects\C--Users-Owner-OneDrive---Oxford-Capital-Partners\memory\MEMORY.md'
)) {
  Write-Output ("PATH`t{0}`texists={1}" -f $p, (Test-Path -LiteralPath $p))
}
Write-Output ""
Write-Output "=== append-event-log.py USAGE HEADER (first 45 lines) ==="
$s = 'C:\Users\Owner\.claude\maintenance\append-event-log.py'
if (Test-Path -LiteralPath $s) { Get-Content -LiteralPath $s -TotalCount 45 | ForEach-Object { Write-Output ("SRC`t" + $_) } }
Write-Output ""
Write-Output "=== event_log.md TAIL (last 20 lines) ==="
$e = 'C:\Users\Owner\.claude\projects\C--Users-Owner-OneDrive---Oxford-Capital-Partners\memory\event_log.md'
if (Test-Path -LiteralPath $e) { Get-Content -LiteralPath $e -Tail 20 | ForEach-Object { Write-Output ("EL`t" + $_) } }
