$ErrorActionPreference = 'Continue'
$skill = 'acquisition-proposal-generation'
$repo  = 'C:\Users\Owner\ora-skills\acquisition-proposal-generation'
$cacheRoot = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'

Write-Output ("NOW=" + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'))
Write-Output ""
Write-Output "=== POST-INSTALL CACHE MIRROR ==="
$dirs = @(Get-ChildItem -LiteralPath $cacheRoot -Recurse -Directory -Filter $skill -ErrorAction SilentlyContinue)
Write-Output ("CACHE_DIR_COUNT=" + $dirs.Count)
foreach ($d in $dirs) {
    $i = Get-Item -LiteralPath $d.FullName
    Write-Output ("CACHE_DIR=" + $d.FullName)
    Write-Output ("CACHE_DIR_TIMES`tcreated={0:yyyy-MM-dd HH:mm:ss}`tmodified={1:yyyy-MM-dd HH:mm:ss}" -f $i.CreationTime, $i.LastWriteTime)
    $files = @(Get-ChildItem -LiteralPath $d.FullName -Recurse -File)
    Write-Output ("CACHE_FILE_COUNT=" + $files.Count)
    foreach ($f in $files) {
        $rel = $f.FullName.Substring($d.FullName.Length+1).Replace('\','/')
        $ch  = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLower()
        $rp  = Join-Path $repo ($rel.Replace('/','\'))
        $verdict = 'REPO-FILE-MISSING'
        if (Test-Path -LiteralPath $rp) {
            $rh = (Get-FileHash -LiteralPath $rp -Algorithm SHA256).Hash.ToLower()
            $verdict = if ($ch -eq $rh) { 'MATCH' } else { 'RAW-MISMATCH' }
            if ($verdict -eq 'RAW-MISMATCH' -and $rel -like '*.md') {
                $ct = ([IO.File]::ReadAllText($f.FullName)) -replace "`r`n","`n"
                $rt = ([IO.File]::ReadAllText($rp))         -replace "`r`n","`n"
                if ($ct.TrimEnd() -eq $rt.TrimEnd()) { $verdict = 'MATCH-NORMALIZED' } else { $verdict = 'REAL-DRIFT' }
            }
        }
        Write-Output ("CACHE`t{0}`t{1}`t{2}`tmtime={3:yyyy-MM-dd HH:mm:ss}`tcreated={4:yyyy-MM-dd HH:mm:ss}" -f $rel, $f.Length, $verdict, $f.LastWriteTime, $f.CreationTime)
    }
}

Write-Output ""
Write-Output "=== main.log SYNC EVIDENCE (2026-08-21 only) ==="
$ml = Join-Path $env:APPDATA 'Claude\logs\main.log'
$fi = Get-Item -LiteralPath $ml
Write-Output ("MAINLOG_MTIME={0:yyyy-MM-dd HH:mm:ss} bytes={1}" -f $fi.LastWriteTime, $fi.Length)
Get-Content -LiteralPath $ml -Tail 6000 |
    Select-String -Pattern '2026-08-21' |
    Select-String -Pattern 'SkillsPlugin|acquisition-proposal' |
    Select-Object -Last 40 | ForEach-Object { Write-Output ("LOG`t" + $_.Line) }
