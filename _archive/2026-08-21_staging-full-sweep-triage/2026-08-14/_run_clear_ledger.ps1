Set-Location "C:\Users\Owner\ora-skills"
python tools\pending_reimport.py clear package-and-stage-skill
Write-Output "EXITCODE=$LASTEXITCODE"
