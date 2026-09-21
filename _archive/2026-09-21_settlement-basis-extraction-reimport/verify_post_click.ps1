$ErrorActionPreference = 'Stop'
$repoDir = 'C:\Users\Owner\ora-skills\settlement-basis-extraction'
$cacheDir = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\settlement-basis-extraction'

Write-Output "=== CACHE DIR CURRENT STATE ==="
if (Test-Path $cacheDir) {
    $d = Get-Item $cacheDir
    Write-Output ("CreationTime: {0}" -f $d.CreationTime.ToString("o"))
    Get-ChildItem -Path $cacheDir -Recurse -File | ForEach-Object {
        Write-Output ("  {0} ({1} bytes, modified {2})" -f $_.FullName, $_.Length, $_.LastWriteTime.ToString("o"))
    }
} else {
    Write-Output "CACHE DIR MISSING: $cacheDir"
}

Write-Output "=== CONTENT COMPARISON: cache vs repo (CRLF/LF normalized) ==="
function NormRead($path) {
    $bytes = [IO.File]::ReadAllText($path)
    return ($bytes -replace "`r`n", "`n").TrimEnd()
}
$files = @('SKILL.md', 'references\charge-capitalization-taxonomy.md')
foreach ($f in $files) {
    $cachePath = Join-Path $cacheDir $f
    $repoPath = Join-Path $repoDir $f
    if ((Test-Path $cachePath) -and (Test-Path $repoPath)) {
        $c = NormRead $cachePath
        $r = NormRead $repoPath
        $match = ($c -eq $r)
        Write-Output ("{0}: content-identical(normalized)={1}" -f $f, $match)
    } else {
        Write-Output ("{0}: MISSING (cache exists={1}, repo exists={2})" -f $f, (Test-Path $cachePath), (Test-Path $repoPath))
    }
}

Write-Output "=== main.log LOCAL tail (SkillsPlugin) ==="
$localLog = "$env:LOCALAPPDATA\Claude\Logs\main.log"
if (Test-Path $localLog) {
    Select-String -Path $localLog -Pattern 'SkillsPlugin' | Select-Object -Last 15 | ForEach-Object { Write-Output $_.Line }
} else {
    Write-Output "Local main.log not found"
}
