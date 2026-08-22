Set-Location "C:\Users\Owner\ora-skills"
Write-Output "=== pending_reimport.py list ==="
python tools\pending_reimport.py list
Write-Output ""
Write-Output "=== pending_reimport.py candidates ==="
python tools\pending_reimport.py candidates
Write-Output ""
Write-Output "=== pending_reimport.py shared-deps ==="
python tools\pending_reimport.py shared-deps
