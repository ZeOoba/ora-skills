$skills = @("deal-execution","debt-management","document-assembly","estoppel-request-generation","lease-abstraction-pipeline","legal-intelligence")
$repoRoot = "C:\Users\Owner\ora-skills"
$stagingDir = "C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch3"
$cacheRoot = Join-Path $env:APPDATA "Claude\local-agent-mode-sessions\skills-plugin"

Set-Location $repoRoot

foreach ($s in $skills) {
    Write-Output "=========================="
    Write-Output "SKILL: $s"

    $gitStatus = git status --short -- "$s/" 2>&1
    Write-Output "GIT_STATUS: [$gitStatus]"
    $gitLog = git log -1 --format="%H %ci %s" -- "$s/" 2>&1
    Write-Output "GIT_LOG: $gitLog"

    $repoMd = Join-Path $repoRoot "$s\SKILL.md"
    if (Test-Path $repoMd) {
        $content = Get-Content $repoMd -Raw
        $vm = [regex]::Matches($content, 'v(\d+\.\d+(\.\d+)?)')
        if ($vm.Count -gt 0) {
            Write-Output "REPO_VERSION_MATCHES: $($vm | ForEach-Object {$_.Value} | Select-Object -Unique | Select-Object -First 5)"
        } else { Write-Output "REPO_VERSION: not found" }
    } else { Write-Output "REPO SKILL.md MISSING" }

    $skillFile = Join-Path $stagingDir "$s.skill"
    if (Test-Path $skillFile) {
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $zip = [System.IO.Compression.ZipFile]::OpenRead($skillFile)
        $entryNames = $zip.Entries | ForEach-Object { $_.FullName }
        Write-Output "ENTRIES: $($entryNames -join ' | ')"

        $skillMdEntry = $zip.Entries | Where-Object { $_.FullName -eq "$s/SKILL.md" }
        if ($skillMdEntry -and (Test-Path $repoMd)) {
            $sr = New-Object System.IO.StreamReader($skillMdEntry.Open())
            $pkgContent = $sr.ReadToEnd()
            $sr.Close()
            $repoContent = Get-Content $repoMd -Raw
            $rawMatch = ($pkgContent -eq $repoContent)
            $normPkg = ($pkgContent -replace "`r`n","`n").TrimEnd()
            $normRepo = ($repoContent -replace "`r`n","`n").TrimEnd()
            $normMatch = ($normPkg -eq $normRepo)
            Write-Output "SKILLMD_RAW_MATCH: $rawMatch  NORMALIZED_MATCH: $normMatch"
        } else {
            Write-Output "SKILLMD_COMPARE: could not locate SKILL.md in package or repo"
        }
        $zip.Dispose()
    } else { Write-Output "PACKAGE MISSING at $skillFile" }

    $cacheDirs = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter $s -ErrorAction SilentlyContinue
    if ($cacheDirs) {
        foreach ($cd in $cacheDirs) {
            Write-Output "CACHE_DIR: $($cd.FullName)  CreationTime=$($cd.CreationTime)  LastWriteTime=$($cd.LastWriteTime)"
        }
    } else { Write-Output "CACHE_DIR: none found under $cacheRoot" }
}

Write-Output "=========================="
Write-Output "MAIN_LOG_CHECK:"
$mainLog = Join-Path $env:APPDATA "Claude\logs\main.log"
if (Test-Path $mainLog) {
    $fi = Get-Item $mainLog
    Write-Output "main.log LastWriteTime: $($fi.LastWriteTime)  Now: $(Get-Date)"
} else {
    Write-Output "main.log not found at $mainLog"
}
