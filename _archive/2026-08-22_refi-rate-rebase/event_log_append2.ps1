Set-Location C:\Users\Owner\ora-skills
python C:\Users\Owner\.claude\maintenance\append-event-log.py --entry-file "C:\Users\Owner\ora-skills\_staging\event_log_entry_2026-08-22b.md"
Write-Output "APPEND EXIT: $LASTEXITCODE"
if ($LASTEXITCODE -ne 0) { Write-Output "ABORT - not clearing ledger"; exit 1 }
python tools\pending_reimport.py clear acquisition-underwriting
python tools\pending_reimport.py clear model-bulk-edit
python tools\pending_reimport.py clear package-and-stage-skill
Write-Output "=== LEDGER AFTER ==="
python tools\pending_reimport.py list
