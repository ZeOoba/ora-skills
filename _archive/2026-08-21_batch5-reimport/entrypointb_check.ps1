$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.IO.Compression.FileSystem

$stagingDir = 'C:\Users\Owner\ora-skills\_staging\2026-08-21_batch5-reimport'
$repoRoot = 'C:\Users\Owner\ora-skills'
$tmpExtract = 'C:\Users\Owner\ora-skills\_staging\2026-08-21_batch5-reimport\_extract_check'

if (Test-Path $tmpExtract) { Remove-Item -Recurse -Force $tmpExtract }
New-Item -ItemType Directory -Path $tmpExtract | Out-Null

$expectedHashes = @{
    'daily-brief.skill' = '66d3f4d713570eed37b23411ac476a6c175360babe4b2914c560310e5ac66a49'
    'insurance-renewal-review.skill' = '2dc7c9465f7249d2e87a95a512b811ec3605ff6438b7bb8fe76aeb1435624c32'
    'listing-agreement-qc.skill' = '65b54bb39cae1119267324b7f04def49d64e817e70989b3121d19a4a6fa429b7'
    'register-scheduled-task.skill' = 'ec66e12f97e6f890475d109a592bef075db2d180d13219e631e2a1463f63b902'
    'settlement-basis-extraction.skill' = '4fe8b463c3422a660e521143d6ad2e9d6925ebfb603bae37c92346c5d526dea4'
}

foreach ($kv in $expectedHashes.GetEnumerator()) {
    $fname = $kv.Key
    $expected = $kv.Value
    $skillName = $fname -replace '\.skill$',''
    $fpath = Join-Path $stagingDir $fname
    Write-Output "`n===== $fname ====="
    Write-Output "expected length: $($expected.Length)"
    if (-not (Test-Path $fpath)) {
        Write-Output "MISSING FILE: $fpath"
        continue
    }
    $actual = (Get-FileHash -Path $fpath -Algorithm SHA256).Hash
    Write-Output "actual sha256 (upper): $actual"
    Write-Output "expected (as given)  : $expected"
    Write-Output "match (case-insens)   : $($actual.ToLower() -eq $expected.ToLower())"

    $extractPath = Join-Path $tmpExtract $skillName
    [System.IO.Compression.ZipFile]::ExtractToDirectory($fpath, $extractPath)

    $entries = Get-ChildItem -Path $extractPath -Recurse -File | Sort-Object FullName
    Write-Output "-- Extracted entries ($($entries.Count)):"
    foreach ($e in $entries) {
        $rel = $e.FullName.Substring($extractPath.Length + 1) -replace '\\','/'
        $h = (Get-FileHash -Path $e.FullName -Algorithm SHA256).Hash
        Write-Output "  $rel  $h"
    }

    $repoDir = Join-Path $repoRoot $skillName
    $repoFiles = Get-ChildItem -Path $repoDir -Recurse -File | Sort-Object FullName
    Write-Output "-- Repo files ($($repoFiles.Count)) [current repo dir]:"
    foreach ($f in $repoFiles) {
        $rel = $f.FullName.Substring($repoDir.Length + 1) -replace '\\','/'
        $h = (Get-FileHash -Path $f.FullName -Algorithm SHA256).Hash
        Write-Output "  $rel  $h"
    }
}
