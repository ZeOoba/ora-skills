$s = "legal-intelligence"
$repoRoot = "C:\Users\Owner\ora-skills"
$stagingDir = "C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch3"
$repoMd = Join-Path $repoRoot "$s\SKILL.md"
$skillFile = Join-Path $stagingDir "$s.skill"

Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($skillFile)
$entry = $zip.Entries | Where-Object { $_.FullName -eq "$s/SKILL.md" }
$ms = New-Object System.IO.MemoryStream
$entry.Open().CopyTo($ms)
$pkgBytes = $ms.ToArray()
$zip.Dispose()

$repoBytes = [System.IO.File]::ReadAllBytes($repoMd)

Write-Output "PKG_BYTES_LEN: $($pkgBytes.Length)"
Write-Output "REPO_BYTES_LEN: $($repoBytes.Length)"
Write-Output "PKG_FIRST8: $($pkgBytes[0..7] -join ',')"
Write-Output "REPO_FIRST8: $($repoBytes[0..7] -join ',')"

$pkgText = [System.Text.Encoding]::UTF8.GetString($pkgBytes)
$repoText = [System.Text.Encoding]::UTF8.GetString($repoBytes)
Write-Output "PKG_TEXT_LEN: $($pkgText.Length)"
Write-Output "REPO_TEXT_LEN: $($repoText.Length)"

$pkgNorm = ($pkgText -replace "`r`n","`n").TrimEnd().TrimStart([char]0xFEFF)
$repoNorm = ($repoText -replace "`r`n","`n").TrimEnd().TrimStart([char]0xFEFF)
Write-Output "NORM_EQUAL: $($pkgNorm -eq $repoNorm)"
Write-Output "NORM_PKG_LEN: $($pkgNorm.Length)  NORM_REPO_LEN: $($repoNorm.Length)"

if ($pkgNorm -ne $repoNorm) {
    $minLen = [Math]::Min($pkgNorm.Length, $repoNorm.Length)
    for ($i=0; $i -lt $minLen; $i++) {
        if ($pkgNorm[$i] -ne $repoNorm[$i]) {
            Write-Output "FIRST_DIFF_AT_INDEX: $i"
            $startCtx = [Math]::Max(0, $i-40)
            Write-Output "PKG_CTX: [$($pkgNorm.Substring($startCtx, [Math]::Min(80, $pkgNorm.Length-$startCtx)))]"
            Write-Output "REPO_CTX: [$($repoNorm.Substring($startCtx, [Math]::Min(80, $repoNorm.Length-$startCtx)))]"
            break
        }
    }
}
