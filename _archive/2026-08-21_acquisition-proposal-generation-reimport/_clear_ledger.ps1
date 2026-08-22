Set-Location 'C:\Users\Owner\ora-skills'
Write-Output "=== BEFORE ==="
& python tools/pending_reimport.py list 2>&1 | ForEach-Object { Write-Output ("B`t" + $_) }
Write-Output ""
Write-Output "=== CLEAR acquisition-proposal-generation ==="
& python tools/pending_reimport.py clear acquisition-proposal-generation 2>&1 | ForEach-Object { Write-Output ("C`t" + $_) }
Write-Output ("EXITCODE=" + $LASTEXITCODE)
Write-Output ""
Write-Output "=== AFTER ==="
& python tools/pending_reimport.py list 2>&1 | ForEach-Object { Write-Output ("A`t" + $_) }
