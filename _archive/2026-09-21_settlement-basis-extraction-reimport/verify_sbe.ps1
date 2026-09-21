$ErrorActionPreference = 'Stop'
$pkg = 'C:\Users\Owner\ora-skills\_staging\2026-09-21-sbe\settlement-basis-extraction.skill'
$expectedHash = '1E6105D402DCCB1A2F7AE751277737D6DF6119382F5861B5B1B348E1C7343811'.Substring(0,64)

Write-Output "=== HASH ==="
$h = Get-FileHash -Path $pkg -Algorithm SHA256
Write-Output $h.Hash

Write-Output "=== ZIP ENTRIES ==="
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($pkg)
foreach ($e in $zip.Entries) {
    Write-Output ("{0}  ({1} bytes)" -f $e.FullName, $e.Length)
}

Write-Output "=== SKILL.md FRONTMATTER ==="
$entry = $zip.Entries | Where-Object { $_.FullName -eq 'settlement-basis-extraction/SKILL.md' }
if ($entry) {
    $sr = New-Object System.IO.StreamReader($entry.Open())
    $content = $sr.ReadToEnd()
    $sr.Close()
    $fmMatch = [regex]::Match($content, '(?s)^---\r?\n(.*?)\r?\n---')
    Write-Output $fmMatch.Groups[1].Value
    Write-Output "--- title/changelog v1.3 grep ---"
    ($content -split "`n") | Select-String -Pattern 'v1\.3' | Select-Object -First 10
} else {
    Write-Output "SKILL.md entry not found"
}
$zip.Dispose()

Write-Output "=== SKILLS-PLUGIN CACHE SEARCH ==="
$cacheRoot = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin"
if (Test-Path $cacheRoot) {
    $dirs = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter 'settlement-basis-extraction' -ErrorAction SilentlyContinue
    if ($dirs) {
        foreach ($d in $dirs) {
            Write-Output ("Found cache dir: {0}" -f $d.FullName)
            Write-Output ("CreationTime: {0}" -f $d.CreationTime.ToString("o"))
            Get-ChildItem -Path $d.FullName -Recurse -File | ForEach-Object {
                Write-Output ("  {0} ({1} bytes, modified {2})" -f $_.FullName, $_.Length, $_.LastWriteTime.ToString("o"))
            }
        }
    } else {
        Write-Output "No cache dir found for settlement-basis-extraction under skills-plugin"
    }
} else {
    Write-Output "Cache root not found: $cacheRoot"
}

Write-Output "=== main.log LOCAL (preferred) ==="
$localLog = "$env:LOCALAPPDATA\Claude\Logs\main.log"
if (Test-Path $localLog) {
    $fi = Get-Item $localLog
    Write-Output ("Local main.log LastWriteTime: {0}" -f $fi.LastWriteTime.ToString("o"))
    Select-String -Path $localLog -Pattern 'SkillsPlugin' | Select-Object -Last 20 | ForEach-Object { Write-Output $_.Line }
} else {
    Write-Output "Local main.log not found at $localLog"
}

Write-Output "=== main.log ROAMING ==="
$roamLog = "$env:APPDATA\Claude\logs\main.log"
if (Test-Path $roamLog) {
    $fi2 = Get-Item $roamLog
    Write-Output ("Roaming main.log LastWriteTime: {0}" -f $fi2.LastWriteTime.ToString("o"))
} else {
    Write-Output "Roaming main.log not found at $roamLog"
}

Write-Output "=== PENDING_REIMPORT.md status (read-only check) ==="
$pending = 'C:\Users\Owner\ora-skills\_staging\PENDING_REIMPORT.md'
if (Test-Path $pending) {
    Select-String -Path $pending -Pattern 'settlement-basis-extraction' | ForEach-Object { Write-Output $_.Line }
} else {
    Write-Output "PENDING_REIMPORT.md not found"
}
