$skills = @("legal-intelligence")
$repoRoot = "C:\Users\Owner\ora-skills"
$stagingDir = "C:\Users\Owner\ora-skills\_staging\2026-08-21_reimport-batch3"

function Normalize($t) {
    return ($t -replace "`r`n","`n").TrimEnd().TrimStart([char]0xFEFF)
}

Add-Type -AssemblyName System.IO.Compression.FileSystem

foreach ($s in $skills) {
    $skillFile = Join-Path $stagingDir "$s.skill"
    $zip = [System.IO.Compression.ZipFile]::OpenRead($skillFile)
    foreach ($entry in $zip.Entries) {
        $rel = $entry.FullName.Substring($s.Length + 1)
        if ([string]::IsNullOrEmpty($rel)) { continue }
        $repoFile = Join-Path (Join-Path $repoRoot $s) $rel
        Write-Output "REL: [$rel]  REPOFILE: [$repoFile]  EXISTS: $(Test-Path $repoFile)"
        $stream = $entry.Open()
        $sr = New-Object System.IO.StreamReader($stream)
        $pkgText = $sr.ReadToEnd()
        $sr.Close()
        $stream.Close()
        $repoText = Get-Content $repoFile -Raw
        $np = Normalize($pkgText)
        $nr = Normalize($repoText)
        Write-Output "PKG_LEN=$($pkgText.Length) REPO_LEN=$($repoText.Length) NORM_PKG_LEN=$($np.Length) NORM_REPO_LEN=$($nr.Length) EQUAL=$($np -eq $nr)"
        if ($np -ne $nr) {
            $minLen = [Math]::Min($np.Length, $nr.Length)
            $diffIdx = -1
            for ($i=0; $i -lt $minLen; $i++) { if ($np[$i] -ne $nr[$i]) { $diffIdx = $i; break } }
            Write-Output "DIFF_IDX: $diffIdx"
            if ($diffIdx -ge 0) {
                $st = [Math]::Max(0,$diffIdx-30)
                Write-Output "PKG_CTX:[$($np.Substring($st,[Math]::Min(60,$np.Length-$st)))]"
                Write-Output "REPO_CTX:[$($nr.Substring($st,[Math]::Min(60,$nr.Length-$st)))]"
            }
        }
    }
    $zip.Dispose()
}
