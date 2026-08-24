Set-Location C:\Users\Owner\ora-skills
python C:\Users\Owner\.claude\maintenance\append-event-log.py --entry-file "C:\Users\Owner\ora-skills\_staging\event_log_entry_2026-08-22c.md"
Write-Output "APPEND EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { Write-Output "ABORT - not clearing ledger"; exit 1 }
python tools\pending_reimport.py clear model-bulk-edit
Write-Output "=== LEDGER AFTER ==="
python tools\pending_reimport.py list
Write-Output "=== ARCHIVE SPENT STAGING SCRATCH ==="
$arch = "C:\Users\Owner\ora-skills\_archive\2026-08-22_refi-rate-rebase"
New-Item -ItemType Directory -Force -Path $arch | Out-Null
Get-ChildItem "C:\Users\Owner\ora-skills\_staging" -File | Where-Object {
  $_.Name -match '^(refi_|opt_|archive_|mbe_|pss_|lint_|event_log_|fm_gate|verify_|state_probe|postinstall)' -or $_.Name -match '^lint2?_(out|err)\.txt$'
} | ForEach-Object { Move-Item $_.FullName -Destination $arch -Force; "  archived: $($_.Name)" }
Write-Output "=== FINAL TREE ==="
git status -sb
