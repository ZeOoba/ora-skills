$skillPath = "C:\Users\Owner\ora-skills\_staging\2026-08-16\market-monitor.skill"
$extractDir = "C:\Users\Owner\ora-skills\_staging\2026-08-16\_extract_mm"
if (Test-Path $extractDir) { Remove-Item -Recurse -Force $extractDir }
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::ExtractToDirectory($skillPath, $extractDir)

Write-Output "=== HASH: packaged SKILL.md vs repo SKILL.md ==="
$pkgSkillHash = (Get-FileHash "$extractDir\market-monitor\SKILL.md" -Algorithm SHA256).Hash
$repoSkillHash = (Get-FileHash "C:\Users\Owner\ora-skills\market-monitor\SKILL.md" -Algorithm SHA256).Hash
Write-Output ("PKG_SKILLMD_SHA256=" + $pkgSkillHash)
Write-Output ("REPO_SKILLMD_SHA256=" + $repoSkillHash)
Write-Output ("RAW_MATCH=" + ($pkgSkillHash -eq $repoSkillHash))

Write-Output "=== HASH: packaged target-markets.json vs repo-root target-markets.json ==="
$pkgTmHash = (Get-FileHash "$extractDir\market-monitor\target-markets.json" -Algorithm SHA256).Hash
$repoTmHash = (Get-FileHash "C:\Users\Owner\ora-skills\target-markets.json" -Algorithm SHA256).Hash
Write-Output ("PKG_TM_SHA256=" + $pkgTmHash)
Write-Output ("REPO_TM_SHA256=" + $repoTmHash)
Write-Output ("RAW_MATCH=" + ($pkgTmHash -eq $repoTmHash))

Write-Output "=== HASH: cache copies vs repo (for reference) ==="
$cacheDir = "C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\market-monitor"
if (Test-Path "$cacheDir\SKILL.md") {
    $cacheSkillHash = (Get-FileHash "$cacheDir\SKILL.md" -Algorithm SHA256).Hash
    Write-Output ("CACHE_SKILLMD_SHA256=" + $cacheSkillHash)
} else { Write-Output "CACHE_SKILLMD: NOT FOUND" }
if (Test-Path "$cacheDir\target-markets.json") {
    $cacheTmHash = (Get-FileHash "$cacheDir\target-markets.json" -Algorithm SHA256).Hash
    Write-Output ("CACHE_TM_SHA256=" + $cacheTmHash)
} else { Write-Output "CACHE_TM: NOT FOUND" }
Get-ChildItem $cacheDir | ForEach-Object { Write-Output ("CACHE_FILE: " + $_.Name) }
