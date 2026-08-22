Write-Output "=== APPEND EVENT LOG ==="
python C:\Users\Owner\.claude\maintenance\append-event-log.py --entry-file C:\Users\Owner\ora-skills\_staging\event_entries_2026-08-14_skill-installs.md
Write-Output "EXIT: $LASTEXITCODE"
Set-Location C:\Users\Owner\ora-skills
Write-Output "=== CLEAR LEDGER ==="
python tools/pending_reimport.py clear lease-addendum
python tools/pending_reimport.py clear document-assembly
python tools/pending_reimport.py clear exception-detection
python tools/pending_reimport.py clear package-and-stage-skill
Write-Output "=== LEDGER STATE ==="
python tools/pending_reimport.py list
Write-Output "=== DONE ==="
