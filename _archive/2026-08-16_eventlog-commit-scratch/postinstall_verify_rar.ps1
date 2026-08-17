Write-Output "=== CACHE FILE LIST + HASH: repo-architecture-review ==="
$cacheDir = "C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\repo-architecture-review"
Get-ChildItem -Path $cacheDir -Recurse -File | ForEach-Object {
    $h = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
    $rel = $_.FullName.Substring($cacheDir.Length+1)
    Write-Output ($rel + " | " + $_.Length + " bytes | modified " + $_.LastWriteTime + " | SHA256=" + $h)
}
Write-Output "=== REPO COMPARE ==="
$repoHash = (Get-FileHash "C:\Users\Owner\ora-skills\repo-architecture-review\SKILL.md" -Algorithm SHA256).Hash
Write-Output ("REPO_SKILLMD_SHA256=" + $repoHash)
Write-Output "=== PENDING_REIMPORT LEDGER CHECK ==="
Set-Location "C:\Users\Owner\ora-skills"
python tools\pending_reimport.py list
