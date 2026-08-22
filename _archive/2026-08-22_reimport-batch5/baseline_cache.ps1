$ErrorActionPreference = 'Stop'
$mainLog = Join-Path $env:APPDATA 'Claude\logs\main.log'
if (Test-Path $mainLog) {
    $f = Get-Item $mainLog
    Write-Output ("main.log LastWriteTime = " + $f.LastWriteTime)
} else {
    Write-Output "main.log NOT FOUND at $mainLog"
}

$cacheRoot = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'
$hits = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter 'register-scheduled-task' -ErrorAction SilentlyContinue
if ($hits) {
    foreach ($h in $hits) { Write-Output ("register-scheduled-task | " + $h.FullName + " | Created=" + $h.CreationTime) }
} else {
    Write-Output "register-scheduled-task | NO CACHE DIRECTORY FOUND"
}
