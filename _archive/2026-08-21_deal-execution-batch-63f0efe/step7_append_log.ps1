Set-Location "C:\Users\Owner\.claude"
python "C:\Users\Owner\.claude\maintenance\append-event-log.py" --entry-file "C:\Users\Owner\ora-skills\_staging\2026-08-21\event_log_entry_batch63f0efe.md"
Write-Output "APPEND EXIT CODE: $LASTEXITCODE"
