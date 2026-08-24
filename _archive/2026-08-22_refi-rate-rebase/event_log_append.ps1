Set-Location C:\Users\Owner\ora-skills
Write-Output "=== APPEND EVENT LOG ==="
python C:\Users\Owner\.claude\maintenance\append-event-log.py --entry-file "C:\Users\Owner\ora-skills\_staging\event_log_entry_2026-08-22_refi.md"
Write-Output "APPEND EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { Write-Output "ABORT - not clearing ledger"; exit 1 }
Write-Output "=== CLEAR LEDGER (package-and-stage-skill ONLY) ==="
python tools\pending_reimport.py clear package-and-stage-skill
Write-Output "CLEAR EXIT: $LASTEXITCODE"
Write-Output "=== LEDGER AFTER ==="
python tools\pending_reimport.py list
