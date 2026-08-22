$ErrorActionPreference = 'Stop'
$skillPath = "C:\Users\Owner\ora-skills\_staging\2026-08-22_reimport-batch6\package-and-stage-skill.skill"
$repoMd = "C:\Users\Owner\ora-skills\package-and-stage-skill\SKILL.md"

Write-Output "=== ZIP ENTRIES ==="
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($skillPath)
foreach ($e in $zip.Entries) {
    Write-Output ("{0}  ({1} bytes)" -f $e.FullName, $e.Length)
}

Write-Output "=== SKILL.md HASH COMPARE ==="
$entry = $zip.Entries | Where-Object { $_.FullName -eq "package-and-stage-skill/SKILL.md" }
if (-not $entry) {
    Write-Output "MISSING expected entry package-and-stage-skill/SKILL.md"
} else {
    $tmp = Join-Path $env:TEMP "pkgcheck_SKILL.md"
    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $tmp, $true)
    $hZip = (Get-FileHash -Algorithm SHA256 -Path $tmp).Hash
    $hRepo = (Get-FileHash -Algorithm SHA256 -Path $repoMd).Hash
    Write-Output "Zip SKILL.md SHA256:  $hZip"
    Write-Output "Repo SKILL.md SHA256: $hRepo"
    if ($hZip -eq $hRepo) {
        Write-Output "RAW MATCH"
    } else {
        $normZip = ((Get-Content $tmp -Raw) -replace "`r`n","`n").TrimEnd()
        $normRepo = ((Get-Content $repoMd -Raw) -replace "`r`n","`n").TrimEnd()
        if ($normZip -eq $normRepo) {
            Write-Output "RAW MISMATCH but NORMALIZED MATCH (EOL-only diff) -- content in sync"
        } else {
            Write-Output "NORMALIZED MISMATCH -- REAL DRIFT"
        }
    }
}
$zip.Dispose()

Write-Output "=== CACHE DIRECTORY DISCOVERY + CREATIONTIME BASELINE ==="
$cacheRoot = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin"
if (Test-Path $cacheRoot) {
    $dirs = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter "package-and-stage-skill" -ErrorAction SilentlyContinue
    if ($dirs) {
        foreach ($d in $dirs) {
            Write-Output ("CacheDir: {0}" -f $d.FullName)
            Write-Output ("CreationTime: {0}" -f $d.CreationTime)
            Write-Output ("LastWriteTime: {0}" -f $d.LastWriteTime)
            Get-ChildItem -Path $d.FullName -File | ForEach-Object {
                Write-Output ("  file: {0}  hash: {1}" -f $_.Name, (Get-FileHash -Algorithm SHA256 -Path $_.FullName).Hash)
            }
        }
    } else {
        Write-Output "No cache dir found under $cacheRoot for package-and-stage-skill"
    }
} else {
    Write-Output "Cache root not found: $cacheRoot"
}

Write-Output "=== GIT STATUS (skill dir) ==="
Set-Location "C:\Users\Owner\ora-skills"
git status --short -- package-and-stage-skill/
Write-Output "=== GIT LOG -1 ==="
git log -1 -- package-and-stage-skill/
