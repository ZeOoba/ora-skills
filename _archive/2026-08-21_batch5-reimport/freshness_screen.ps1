$ErrorActionPreference = 'Stop'
$cacheRoot = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'
$repoRoot = 'C:\Users\Owner\ora-skills'
$skills = @('daily-brief','insurance-renewal-review','listing-agreement-qc','register-scheduled-task','settlement-basis-extraction')

$mainLog = 'C:\Users\Owner\AppData\Roaming\Claude\logs\main.log'
if (Test-Path $mainLog) {
    $mlInfo = Get-Item $mainLog
    Write-Output "=== main.log mtime: $($mlInfo.LastWriteTime) | now: $(Get-Date) ==="
} else {
    Write-Output "=== main.log NOT FOUND at $mainLog ==="
}

foreach ($s in $skills) {
    Write-Output "`n===== $s ====="
    $cacheDir = Join-Path $cacheRoot $s
    $repoDir = Join-Path $repoRoot $s
    if (-not (Test-Path $cacheDir)) {
        Write-Output "CACHE DIR MISSING: $cacheDir"
        continue
    }
    if (-not (Test-Path $repoDir)) {
        Write-Output "REPO DIR MISSING: $repoDir"
        continue
    }
    $dirInfo = Get-Item $cacheDir
    Write-Output "Cache dir CreationTime: $($dirInfo.CreationTime)  LastWriteTime: $($dirInfo.LastWriteTime)"

    $cacheFiles = Get-ChildItem -Path $cacheDir -Recurse -File | Sort-Object FullName
    Write-Output "-- Cache files ($($cacheFiles.Count)):"
    foreach ($f in $cacheFiles) {
        $rel = $f.FullName.Substring($cacheDir.Length + 1) -replace '\\','/'
        $h = (Get-FileHash -Path $f.FullName -Algorithm SHA256).Hash
        Write-Output "  $rel  $h  created:$($f.CreationTime)"
    }

    $repoFiles = Get-ChildItem -Path $repoDir -Recurse -File | Sort-Object FullName
    Write-Output "-- Repo files ($($repoFiles.Count)):"
    foreach ($f in $repoFiles) {
        $rel = $f.FullName.Substring($repoDir.Length + 1) -replace '\\','/'
        $h = (Get-FileHash -Path $f.FullName -Algorithm SHA256).Hash
        Write-Output "  $rel  $h"
    }
}

# shared deps
Write-Output "`n===== SHARED DEPS ====="
$sharedDeps = @{
    'daily-brief' = 'target-markets.json'
}
foreach ($k in $sharedDeps.Keys) {
    $depName = $sharedDeps[$k]
    $repoRootDep = Join-Path $repoRoot $depName
    $cacheDep = Join-Path (Join-Path $cacheRoot $k) $depName
    if ((Test-Path $repoRootDep) -and (Test-Path $cacheDep)) {
        $h1 = (Get-FileHash -Path $repoRootDep -Algorithm SHA256).Hash
        $h2 = (Get-FileHash -Path $cacheDep -Algorithm SHA256).Hash
        Write-Output "$k / $depName -- repo-root:$h1  cache:$h2  match:$($h1 -eq $h2)"
    } else {
        Write-Output "$k / $depName -- repoRootExists:$(Test-Path $repoRootDep) cacheExists:$(Test-Path $cacheDep)"
    }
}

# listing-agreement-qc shared script dep
$repoSharedScript = Join-Path $repoRoot 'tools\ora_doc_qc.py'
$cacheScript = Join-Path $cacheRoot 'listing-agreement-qc\scripts\ora_doc_qc.py'
Write-Output "`nlisting-agreement-qc / scripts/ora_doc_qc.py -- repoToolsExists:$(Test-Path $repoSharedScript) cacheExists:$(Test-Path $cacheScript)"
if ((Test-Path $repoSharedScript) -and (Test-Path $cacheScript)) {
    $h1 = (Get-FileHash -Path $repoSharedScript -Algorithm SHA256).Hash
    $h2 = (Get-FileHash -Path $cacheScript -Algorithm SHA256).Hash
    Write-Output "hash repo tools/ora_doc_qc.py:$h1  cache:$h2  match:$($h1 -eq $h2)"
}
