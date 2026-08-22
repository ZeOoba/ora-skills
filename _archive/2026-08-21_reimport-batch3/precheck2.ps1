$skills = @("deal-execution","debt-management","document-assembly","estoppel-request-generation","lease-abstraction-pipeline","legal-intelligence")
$repoRoot = "C:\Users\Owner\ora-skills"
$stagingDir = "C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch3"
$cacheRoot = Join-Path $env:APPDATA "Claude\local-agent-mode-sessions\skills-plugin"

function Normalize($t) {
    return ($t -replace "`r`n","`n").TrimEnd().TrimStart([char]0xFEFF)
}

Set-Location $repoRoot
Add-Type -AssemblyName System.IO.Compression.FileSystem

foreach ($s in $skills) {
    Write-Output "=========================="
    Write-Output "SKILL: $s"
    $skillFile = Join-Path $stagingDir "$s.skill"
    if (-not (Test-Path $skillFile)) { Write-Output "PACKAGE MISSING"; continue }

    $zip = [System.IO.Compression.ZipFile]::OpenRead($skillFile)
    $allOk = $true
    foreach ($entry in $zip.Entries) {
        $rel = $entry.FullName.Substring($s.Length + 1)
        if ([string]::IsNullOrEmpty($rel)) { continue }
        $repoFile = Join-Path (Join-Path $repoRoot $s) $rel
        if (-not (Test-Path $repoFile)) {
            Write-Output "  MISSING_IN_REPO: $rel"
            $allOk = $false
            continue
        }
        $sr = New-Object System.IO.StreamReader($entry.Open())
        $pkgText = $sr.ReadToEnd()
        $sr.Close()
        $repoText = Get-Content $repoFile -Raw
        $match = (Normalize($pkgText)) -eq (Normalize($repoText))
        Write-Output "  $rel : NORMALIZED_MATCH=$match"
        if (-not $match) { $allOk = $false }
    }
    $zip.Dispose()
    Write-Output "PACKAGE_FRESH_VS_REPO: $allOk"
}
