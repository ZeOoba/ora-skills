$ErrorActionPreference = 'Stop'
$mainLog = Join-Path $env:APPDATA 'Claude\logs\main.log'
if (Test-Path $mainLog) {
    $f = Get-Item $mainLog
    Write-Output ("main.log LastWriteTime = " + $f.LastWriteTime)
} else {
    Write-Output "main.log NOT FOUND at $mainLog"
}

$skills = @('insurance-renewal-review','package-and-stage-skill','dirty-tree-triage')
$cacheRoot = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'
if (Test-Path $cacheRoot) {
    foreach ($s in $skills) {
        $hits = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter $s -ErrorAction SilentlyContinue
        if ($hits) {
            foreach ($h in $hits) {
                Write-Output ($s + " | " + $h.FullName + " | Created=" + $h.CreationTime)
            }
        } else {
            Write-Output ($s + " | NO CACHE DIRECTORY FOUND")
        }
    }
} else {
    Write-Output "cache root not found: $cacheRoot"
}
