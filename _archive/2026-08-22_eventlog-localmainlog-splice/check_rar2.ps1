$ErrorActionPreference = 'Stop'
$cacheRoot = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'
foreach ($s in @('repo-architecture-review','package-and-stage-skill','debt-management')) {
    $hits = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter $s -ErrorAction SilentlyContinue
    if ($hits) {
        foreach ($h in $hits) { Write-Output ($s + " | " + $h.FullName + " | Created=" + $h.CreationTime) }
    } else {
        Write-Output ($s + " | NO CACHE DIRECTORY FOUND")
    }
}
