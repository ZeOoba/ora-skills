Set-Location 'C:\Users\Owner\ora-skills'
git commit -F '_staging\2026-08-15\commit_msg2.txt'
Write-Output "COMMIT_EXIT=$LASTEXITCODE"
git log -1 --format="%H %ci %s"
