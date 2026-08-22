$repo = 'C:\Users\Owner\ora-skills\package-and-stage-skill\SKILL.md'
$cache = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\package-and-stage-skill\SKILL.md'
$repoHash = (Get-FileHash -Path $repo -Algorithm SHA256).Hash
$cacheHash = (Get-FileHash -Path $cache -Algorithm SHA256).Hash
Write-Output "RepoHash:  $repoHash"
Write-Output "CacheHash: $cacheHash"
if ($repoHash -eq $cacheHash) {
    Write-Output "RAW MATCH"
} else {
    Write-Output "RAW MISMATCH -- normalizing"
    $repoText = (Get-Content -Raw -Path $repo) -replace "`r`n", "`n"
    $cacheText = (Get-Content -Raw -Path $cache) -replace "`r`n", "`n"
    $repoText = $repoText.TrimEnd()
    $cacheText = $cacheText.TrimEnd()
    if ($repoText -eq $cacheText) {
        Write-Output "NORMALIZED MATCH"
    } else {
        Write-Output "NORMALIZED MISMATCH -- real drift"
    }
}
$cacheItem = Get-Item -Path $cache
Write-Output "CacheLastWriteTime: $($cacheItem.LastWriteTime)"
