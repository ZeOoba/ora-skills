Write-Output '--- WORKTREE LEDGERS ---'
Get-Content C:\Users\Owner\ora-skills-worktrees\eval-harness-n6\_staging\PENDING_REIMPORT.md -ErrorAction SilentlyContinue | Select-Object -Last 12
Write-Output '=== mirror-sync worktree ==='
Get-Content C:\Users\Owner\ora-skills-worktrees\appdata-mirror-sync\_staging\PENDING_REIMPORT.md -ErrorAction SilentlyContinue | Select-Object -Last 12
Set-Location C:\Users\Owner\ora-skills
Write-Output '--- BACKFILL 18:27 TRIO ---'
python tools\pending_reimport.py record cc7c60a
python tools\pending_reimport.py record 6119993
python tools\pending_reimport.py record de0ac95
Write-Output '--- GIT CLEAN CHECK (both skills) ---'
git status --short -- daily-brief/ register-scheduled-task/
Write-Output '--- PACKAGE BOTH ---'
python tools\package_skills.py C:\Users\Owner\ora-skills\_staging\2026-08-14 daily-brief register-scheduled-task
Write-Output '--- HASHES + B64 ---'
foreach ($n in @('daily-brief','register-scheduled-task')) {
  $p = 'C:\Users\Owner\ora-skills\_staging\2026-08-14\' + $n + '.skill'
  Write-Output ($n + ' ' + (Get-Item $p).Length + ' ' + (Get-FileHash $p -Algorithm SHA256).Hash)
  [Convert]::ToBase64String([IO.File]::ReadAllBytes($p)) | Out-File -Encoding ascii ($p + '.b64')
}
Write-Output '--- LEDGER FINAL ---'
python tools\pending_reimport.py list
