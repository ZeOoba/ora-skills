$ErrorActionPreference = 'Stop'
$roaming = Join-Path $env:APPDATA 'Claude\logs\main.log'
$local = Join-Path $env:LOCALAPPDATA 'Claude\Logs\main.log'
foreach ($p in @($roaming, $local)) {
    if (Test-Path $p) { Write-Output ($p + " LastWriteTime = " + (Get-Item $p).LastWriteTime) }
    else { Write-Output ($p + " NOT FOUND") }
}
$cacheRoot = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'
$hits = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter 'package-and-stage-skill' -ErrorAction SilentlyContinue
if ($hits) {
    foreach ($h in $hits) { Write-Output ("package-and-stage-skill | " + $h.FullName + " | Created=" + $h.CreationTime) }
} else {
    Write-Output "package-and-stage-skill | NO CACHE DIRECTORY FOUND"
}
