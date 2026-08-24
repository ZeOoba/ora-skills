Set-Location C:\Users\Owner\ora-skills
Write-Output "=== GIT: did the v4.14 batch land? ==="
git log --oneline -5
Write-Output "--- working tree ---"
git status -sb
Write-Output "=== PENDING_REIMPORT ==="
if (Test-Path _staging\PENDING_REIMPORT.md) { Get-Content _staging\PENDING_REIMPORT.md -Tail 25 } else { Write-Output "(none)" }
Write-Output "=== CACHE DIR CreationTime (install discriminator) ==="
$base = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin"
foreach ($s in @('acquisition-underwriting','package-and-stage-skill')) {
  Get-ChildItem -Path $base -Recurse -Directory -Filter $s -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Output "$s  CreationTime=$($_.CreationTime.ToString('yyyy-MM-dd HH:mm:ss'))  LastWrite=$($_.LastWriteTime.ToString('HH:mm:ss'))  path=$($_.FullName)" }
}
Write-Output "=== LOCAL main.log liveness + recent SkillsPlugin sync ==="
$loc = "$env:LOCALAPPDATA\Claude\Logs\main.log"
if (Test-Path $loc) {
  Write-Output "local main.log mtime: $((Get-Item $loc).LastWriteTime.ToString('yyyy-MM-dd HH:mm:ss'))"
  Get-Content $loc -Tail 400 | Select-String -Pattern 'SkillsPlugin' | Select-Object -Last 12 | ForEach-Object { $_.Line }
} else { Write-Output "local main.log NOT FOUND" }
