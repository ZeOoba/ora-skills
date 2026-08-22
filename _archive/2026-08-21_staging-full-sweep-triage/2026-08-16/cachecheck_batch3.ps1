Set-Location "C:\Users\Owner\ora-skills"
$skills = @("insurance-renewal-review","package-and-stage-skill","register-scheduled-task")
$cacheRoot = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin"

foreach ($s in $skills) {
    Write-Output "`n=== $s : cache dir + hash compare ==="
    $cacheDirs = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter $s -ErrorAction SilentlyContinue
    if (-not $cacheDirs) {
        Write-Output "CACHE_DIR: NOT FOUND (never installed)"
        continue
    }
    foreach ($cd in $cacheDirs) {
        Write-Output ("CACHE_DIR: " + $cd.FullName)
        Get-ChildItem -Path $cd.FullName -Recurse -File | ForEach-Object {
            $relPath = $_.FullName.Substring($cd.FullName.Length+1)
            $cacheHash = (Get-FileHash $_.FullName -Algorithm SHA256).Hash
            $repoPath = Join-Path "C:\Users\Owner\ora-skills\$s" $relPath
            if (Test-Path $repoPath) {
                $repoHash = (Get-FileHash $repoPath -Algorithm SHA256).Hash
                Write-Output ("  " + $relPath + " | cache=" + $cacheHash + " | repo=" + $repoHash + " | MATCH=" + ($cacheHash -eq $repoHash))
            } else {
                Write-Output ("  " + $relPath + " | NOT IN REPO at expected path: " + $repoPath)
            }
        }
    }
}

Write-Output "`n=== main.log tail (last 15 lines, unfiltered) ==="
$logPath = "$env:APPDATA\Claude\logs\main.log"
if (Test-Path $logPath) {
    Get-Content $logPath -Tail 15
} else {
    Write-Output "main.log not found"
}
