Write-Output "=== repo SKILL.md version line ==="
Select-String -Path "C:\Users\Owner\ora-skills\repo-architecture-review\SKILL.md" -Pattern "v1\.0" | Select-Object -First 3

Write-Output "=== cache vs repo hash compare ==="
$cacheDir = "C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\repo-architecture-review"
Get-ChildItem -Path $cacheDir -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($cacheDir.Length+1)
    $cacheHash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
    $repoPath = "C:\Users\Owner\ora-skills\repo-architecture-review\$rel"
    if (Test-Path $repoPath) {
        $repoHash = (Get-FileHash $repoPath -Algorithm SHA256).Hash
        Write-Output ($rel + " | " + $_.Length + "B | modified " + $_.LastWriteTime + " | cache=" + $cacheHash + " | repo=" + $repoHash + " | MATCH=" + ($cacheHash -eq $repoHash))
    } else {
        Write-Output ($rel + " | NOT IN REPO")
    }
}
