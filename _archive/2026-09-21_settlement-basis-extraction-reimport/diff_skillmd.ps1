$ErrorActionPreference = 'Stop'
$cachePath = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\settlement-basis-extraction\SKILL.md'
$repoPath = 'C:\Users\Owner\ora-skills\settlement-basis-extraction\SKILL.md'

$cacheBytes = [IO.File]::ReadAllBytes($cachePath)
$repoBytes = [IO.File]::ReadAllBytes($repoPath)
Write-Output ("cache bytes: {0}" -f $cacheBytes.Length)
Write-Output ("repo bytes: {0}" -f $repoBytes.Length)

function NormLines($path) {
    $text = [IO.File]::ReadAllText($path)
    $lines = $text -split "`r`n|`n"
    return ($lines | ForEach-Object { $_.TrimEnd() })
}
$c = NormLines $cachePath
$r = NormLines $repoPath
Write-Output ("cache line count: {0}" -f $c.Count)
Write-Output ("repo line count: {0}" -f $r.Count)

$max = [Math]::Max($c.Count, $r.Count)
$diffCount = 0
for ($i = 0; $i -lt $max; $i++) {
    $cl = if ($i -lt $c.Count) { $c[$i] } else { "<<MISSING>>" }
    $rl = if ($i -lt $r.Count) { $r[$i] } else { "<<MISSING>>" }
    if ($cl -ne $rl) {
        $diffCount++
        if ($diffCount -le 10) {
            Write-Output ("Line {0} DIFFERS:" -f $i)
            Write-Output ("  cache: {0}" -f $cl)
            Write-Output ("  repo:  {0}" -f $rl)
        }
    }
}
Write-Output ("Total differing lines: {0}" -f $diffCount)

Write-Output "=== git log -1 for repo SKILL.md ==="
Set-Location 'C:\Users\Owner\ora-skills'
git log -1 --format="%H %ci %s" -- settlement-basis-extraction/SKILL.md
Write-Output "=== git status for skill dir ==="
git status --short -- settlement-basis-extraction/
