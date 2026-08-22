$ErrorActionPreference = 'Continue'
$skill = 'acquisition-proposal-generation'
$cdir  = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\acquisition-proposal-generation'

Write-Output "=== CACHE DIR TIMESTAMPS ==="
foreach ($p in @($cdir, (Split-Path -Parent $cdir), (Split-Path -Parent (Split-Path -Parent $cdir)))) {
    if (Test-Path -LiteralPath $p) {
        $i = Get-Item -LiteralPath $p
        Write-Output ("DIR`t{0}`tcreated={1:yyyy-MM-dd HH:mm:ss}`tmodified={2:yyyy-MM-dd HH:mm:ss}" -f $i.FullName, $i.CreationTime, $i.LastWriteTime)
    }
}

Write-Output ""
Write-Output "=== SIBLING SKILL DIRS IN SAME CACHE BUNDLE (count) ==="
$sib = Get-ChildItem -LiteralPath (Split-Path -Parent $cdir) -Directory -ErrorAction SilentlyContinue
Write-Output ("SIBLING_COUNT=" + $sib.Count)

Write-Output ""
Write-Output "=== main.log FILE STATE + ROTATIONS ==="
Get-ChildItem -LiteralPath (Join-Path $env:APPDATA 'Claude\logs') -Filter 'main*.log' -ErrorAction SilentlyContinue |
  ForEach-Object { Write-Output ("LOGFILE`t{0}`t{1}`t{2:yyyy-MM-dd HH:mm:ss}" -f $_.Name, $_.Length, $_.LastWriteTime) }

$ml = Join-Path $env:APPDATA 'Claude\logs\main.log'
Write-Output "--- last 5 raw lines of main.log ---"
Get-Content -LiteralPath $ml -Tail 5 | ForEach-Object { Write-Output ("TAIL`t" + $_) }

Write-Output ""
Write-Output "=== ANY 2026-08-21 SkillsPlugin ACTIVITY IN ANY LOG ==="
Get-ChildItem -LiteralPath (Join-Path $env:APPDATA 'Claude\logs') -Filter '*.log' -ErrorAction SilentlyContinue | ForEach-Object {
    $hits = Select-String -LiteralPath $_.FullName -Pattern '2026-08-21.*(SkillsPlugin|acquisition-proposal)' -ErrorAction SilentlyContinue
    if ($hits) { $hits | Select-Object -Last 25 | ForEach-Object { Write-Output ("HIT`t" + $_.Filename + "`t" + $_.Line) } }
}

Write-Output ""
Write-Output "=== MIRROR-SYNC HOOK PRESENT? ==="
foreach ($f in @('C:\Users\Owner\ora-skills\tools\sync_appdata_mirror.py','C:\Users\Owner\ora-skills\.git\hooks\pre-commit','C:\Users\Owner\ora-skills\tools\hooks\post-commit')) {
    Write-Output ("HOOKFILE`t{0}`texists={1}" -f $f, (Test-Path -LiteralPath $f))
}

Write-Output ""
Write-Output "=== PENDING_REIMPORT LEDGER ==="
Push-Location 'C:\Users\Owner\ora-skills'
python tools/pending_reimport.py list 2>&1 | ForEach-Object { Write-Output ("LEDGER`t" + $_) }
Pop-Location
