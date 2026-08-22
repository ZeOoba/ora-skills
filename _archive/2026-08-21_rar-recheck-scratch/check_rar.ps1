$ErrorActionPreference = 'Stop'
$cacheRoot = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'
$hits = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter 'repo-architecture-review' -ErrorAction SilentlyContinue
if ($hits) {
    foreach ($h in $hits) { Write-Output ($h.FullName + " | Created=" + $h.CreationTime) }
} else {
    Write-Output "NO CACHE DIRECTORY FOUND"
}
