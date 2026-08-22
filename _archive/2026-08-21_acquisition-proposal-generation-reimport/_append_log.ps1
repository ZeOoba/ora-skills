$entry = 'C:\Users\Owner\ora-skills\_staging\2026-08-21_acquisition-proposal-generation-reimport\event_log_entry_apg_v3.1.md'
$script = 'C:\Users\Owner\.claude\maintenance\append-event-log.py'
$log = 'C:\Users\Owner\.claude\projects\C--Users-Owner-OneDrive---Oxford-Capital-Partners\memory\event_log.md'

$before = (Get-Item -LiteralPath $log)
Write-Output ("LOG_BEFORE bytes={0} mtime={1:yyyy-MM-dd HH:mm:ss}" -f $before.Length, $before.LastWriteTime)

Write-Output "=== RUNNING APPENDER ==="
& python $script --entry-file $entry 2>&1 | ForEach-Object { Write-Output ("OUT`t" + $_) }
$code = $LASTEXITCODE
Write-Output ("EXITCODE=" + $code)

$after = (Get-Item -LiteralPath $log)
Write-Output ("LOG_AFTER bytes={0} mtime={1:yyyy-MM-dd HH:mm:ss}" -f $after.Length, $after.LastWriteTime)
Write-Output ("BYTES_DELTA=" + ($after.Length - $before.Length))

Write-Output ""
Write-Output "=== ENTRY PRESENT IN LOG? (not merely spooled) ==="
$txt = [Text.Encoding]::UTF8.GetString([IO.File]::ReadAllBytes($log))
$needle = 'acquisition-proposal-generation v3.1 INSTALLED'
Write-Output ("ENTRY_IN_LOG=" + $txt.Contains($needle))
$lines = $txt -split "`n"
$idx = 0
for ($i = 0; $i -lt $lines.Count; $i++) { if ($lines[$i] -match '^## \d{4}-\d{2}-\d{2}\b') { $idx = $i; break } }
Write-Output ("NEWEST_HEADER=" + $lines[$idx])

Write-Output ""
Write-Output "=== SPOOL / RESIDUE CHECK ==="
$dir = Split-Path -Parent $log
Get-ChildItem -LiteralPath $dir -Force -Filter 'event_log.md*' | ForEach-Object {
  Write-Output ("RESIDUE`t{0}`t{1}`t{2:yyyy-MM-dd HH:mm:ss}" -f $_.Name, $_.Length, $_.LastWriteTime)
}
$pend = Join-Path $dir 'event_log.md.pending'
if (Test-Path -LiteralPath $pend) {
  Get-ChildItem -LiteralPath $pend -Force | ForEach-Object { Write-Output ("PENDING`t" + $_.Name) }
} else { Write-Output "PENDING_DIR=absent" }
