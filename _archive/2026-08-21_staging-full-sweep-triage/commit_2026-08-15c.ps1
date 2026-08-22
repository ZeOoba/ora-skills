$ErrorActionPreference = 'Stop'
Set-Location 'C:\Users\Owner\ora-skills'
git commit -F '_staging\commit-msg_2026-08-15.txt'
Write-Output '=== git log -1 ==='
git log -1 --stat
Write-Output '=== git status ==='
git status --short
