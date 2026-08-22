$src = 'C:\Users\Owner\ora-skills\_staging\2026-08-21_acquisition-proposal-generation-reimport'
$dst = 'C:\Users\Owner\ora-skills\_archive\2026-08-21_acquisition-proposal-generation-reimport'
Write-Output ("SOURCE_STILL_EXISTS=" + (Test-Path -LiteralPath $src))
Write-Output ("ARCHIVE_EXISTS=" + (Test-Path -LiteralPath $dst))
Get-ChildItem -LiteralPath $dst -Recurse -File | ForEach-Object {
  Write-Output ("ARCHIVED`t{0}`t{1}" -f $_.FullName.Substring($dst.Length+1), $_.Length)
}
Write-Output ""
Write-Output "=== _staging REMAINDER (other work untouched) ==="
Get-ChildItem -LiteralPath 'C:\Users\Owner\ora-skills\_staging' -Directory -ErrorAction SilentlyContinue |
  Sort-Object Name -Descending | Select-Object -First 8 | ForEach-Object { Write-Output ("STAGING_DIR`t" + $_.Name) }
Write-Output ("PENDING_LEDGER_FILE=" + (Test-Path -LiteralPath 'C:\Users\Owner\ora-skills\_staging\PENDING_REIMPORT.md'))
