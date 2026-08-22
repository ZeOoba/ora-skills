$ErrorActionPreference = 'Continue'
$pkg   = 'C:\Users\Owner\ora-skills\_staging\2026-08-21_acquisition-proposal-generation-reimport\acquisition-proposal-generation.skill'
$repo  = 'C:\Users\Owner\ora-skills\acquisition-proposal-generation'
$skill = 'acquisition-proposal-generation'

Write-Output "=== STEP 0: PLUGIN MEMBERSHIP ==="
Push-Location 'C:\Users\Owner\ora-skills'
python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print('PLUGIN_OF=' + str(plugin_of('acquisition-proposal-generation')))" 2>&1 | ForEach-Object { Write-Output $_ }

Write-Output ""
Write-Output "=== GIT STATE ==="
git status --short -- "$skill/" 2>&1 | ForEach-Object { Write-Output ("GITSTATUS`t" + $_) }
git log -1 --format="GITLOG`t%H`t%ad`t%s" --date=iso -- "$skill/" 2>&1 | ForEach-Object { Write-Output $_ }
Pop-Location

Write-Output ""
Write-Output "=== ITEM 3: PACKAGED-ENTRY vs REPO SHA256 ==="
Add-Type -AssemblyName System.IO.Compression.FileSystem
$sha = [System.Security.Cryptography.SHA256]::Create()
$zip = [System.IO.Compression.ZipFile]::OpenRead($pkg)
foreach ($e in $zip.Entries) {
    $s  = $e.Open()
    $ms = New-Object System.IO.MemoryStream
    $s.CopyTo($ms); $s.Close()
    $bytes = $ms.ToArray(); $ms.Close()
    $ph = ([BitConverter]::ToString($sha.ComputeHash($bytes))).Replace('-','').ToLower()
    $rel = $e.FullName.Substring($skill.Length + 1)
    $rp  = Join-Path $repo ($rel.Replace('/','\'))
    if (Test-Path -LiteralPath $rp) {
        $rh = (Get-FileHash -LiteralPath $rp -Algorithm SHA256).Hash.ToLower()
        $v  = if ($ph -eq $rh) { 'MATCH' } else { 'RAW-MISMATCH' }
        if ($v -eq 'RAW-MISMATCH') {
            $pt = [Text.Encoding]::UTF8.GetString($bytes) -replace "`r`n","`n"
            $rt = [IO.File]::ReadAllText($rp) -replace "`r`n","`n"
            if ($pt.TrimEnd() -eq $rt.TrimEnd()) { $v = 'MATCH-NORMALIZED' } else { $v = 'REAL-DRIFT' }
        }
        Write-Output ("FRESH`t{0}`t{1}" -f $rel, $v)
    } else {
        Write-Output ("FRESH`t{0}`tREPO-FILE-MISSING" -f $rel)
    }
}
$zip.Dispose()

Write-Output ""
Write-Output "=== RUNTIME CACHE MIRROR (pre-click baseline) ==="
$cacheRoot = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'
Write-Output ("CACHE_ROOT=" + $cacheRoot + " exists=" + (Test-Path -LiteralPath $cacheRoot))
$dirs = @(Get-ChildItem -LiteralPath $cacheRoot -Recurse -Directory -Filter $skill -ErrorAction SilentlyContinue)
Write-Output ("CACHE_DIR_COUNT=" + $dirs.Count)
foreach ($d in $dirs) {
    Write-Output ("CACHE_DIR=" + $d.FullName)
    Get-ChildItem -LiteralPath $d.FullName -Recurse -File | ForEach-Object {
        $rel = $_.FullName.Substring($d.FullName.Length+1).Replace('\','/')
        $ch  = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()
        Write-Output ("CACHE`t{0}`t{1}`t{2}`t{3:yyyy-MM-dd HH:mm:ss}" -f $rel, $_.Length, $ch, $_.LastWriteTime)
    }
}

Write-Output ""
Write-Output "=== main.log SYNC EVIDENCE (last 60 sync lines) ==="
$ml = Join-Path $env:APPDATA 'Claude\logs\main.log'
Write-Output ("MAINLOG=" + $ml + " exists=" + (Test-Path -LiteralPath $ml))
if (Test-Path -LiteralPath $ml) {
    Get-Content -LiteralPath $ml -Tail 4000 |
        Select-String -Pattern 'Delta:|Sync complete|acquisition-proposal' |
        Select-Object -Last 60 | ForEach-Object { Write-Output ("LOG`t" + $_.Line) }
}
