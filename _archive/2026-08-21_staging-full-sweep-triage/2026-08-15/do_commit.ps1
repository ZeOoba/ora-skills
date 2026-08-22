Set-Location 'C:\Users\Owner\.claude'
$msgFile = 'C:\Users\Owner\ora-skills\_staging\2026-08-15\commit_msg.txt'
git commit -F $msgFile
Write-Host "commit exit: $LASTEXITCODE"
Write-Host '--- log -1 ---'
git log -1 --stat
Write-Host '--- status after ---'
git status --short
