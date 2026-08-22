$d = 'C:\Users\Owner\OneDrive - Oxford Capital Partners (1)'
Write-Output ("exists: " + (Test-Path -LiteralPath $d))
if (Test-Path -LiteralPath $d) {
  Get-ChildItem -LiteralPath $d -Directory -ErrorAction SilentlyContinue |
    Select-Object -First 20 | ForEach-Object { Write-Output ("  DIR " + $_.Name) }
  $dest = Join-Path $d 'Claude_Workspace\_skill_staging'
  New-Item -ItemType Directory -Path $dest -Force | Out-Null
  Copy-Item 'C:\Users\Owner\ora-skills\_staging\2026-08-17\register-scheduled-task.skill' -Destination $dest -Force
  Get-ChildItem -LiteralPath $dest | ForEach-Object { Write-Output ("  COPIED " + $_.FullName + " " + $_.Length) }
  Write-Output ("  SHA256 " + (Get-FileHash (Join-Path $dest 'register-scheduled-task.skill') -Algorithm SHA256).Hash)
}
