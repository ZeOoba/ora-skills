Write-Output "=== main.log: market-monitor sync evidence ==="
$logPath = "$env:APPDATA\Claude\logs\main.log"
if (Test-Path $logPath) {
    Select-String -Path $logPath -Pattern "market-monitor" -Context 0,2 | Select-Object -Last 40
} else {
    Write-Output "main.log not found at $logPath"
}

Write-Output "=== CACHE DIR FILE LIST + HASHES ==="
$cacheDir = "C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\market-monitor"
Get-ChildItem $cacheDir | ForEach-Object {
    $h = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
    Write-Output ($_.Name + " | " + $_.Length + " bytes | modified " + $_.LastWriteTime + " | SHA256=" + $h)
}

Write-Output "=== REPO COMPARE ==="
$repoSkillHash = (Get-FileHash "C:\Users\Owner\ora-skills\market-monitor\SKILL.md" -Algorithm SHA256).Hash
$repoTmHash = (Get-FileHash "C:\Users\Owner\ora-skills\target-markets.json" -Algorithm SHA256).Hash
Write-Output ("REPO_SKILLMD_SHA256=" + $repoSkillHash)
Write-Output ("REPO_TM_SHA256=" + $repoTmHash)
