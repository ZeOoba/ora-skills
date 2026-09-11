$ErrorActionPreference = 'Continue'
$stage = 'C:\Users\Owner\ora-skills\_staging\2026-09-07'
$pkgs = @('county-parcel-screen','county-sales-monitor')
Write-Output "=== EXISTS ==="
foreach ($p in $pkgs) {
  $f = Join-Path $stage "$p.skill"
  if (Test-Path $f) {
    $i = Get-Item $f
    $h = (Get-FileHash $f -Algorithm SHA256).Hash.ToLower()
    Write-Output "$p.skill EXISTS size=$($i.Length) sha256=$h mtime=$($i.LastWriteTime.ToString('s'))"
  } else { Write-Output "$p.skill MISSING at $f" }
}
Write-Output "=== CACHE DIRS (skills-plugin) ==="
$root = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'
foreach ($p in $pkgs) {
  $d = Get-ChildItem $root -Recurse -Directory -Filter $p -ErrorAction SilentlyContinue
  if ($d) { foreach ($x in $d) { Write-Output "$p CACHE-DIR PRESENT $($x.FullName) created=$($x.CreationTime.ToString('s'))" } }
  else { Write-Output "$p CACHE-DIR ABSENT under $root" }
}
Write-Output "=== REPO ==="
Set-Location 'C:\Users\Owner\ora-skills'
git rev-parse --short HEAD
git status --short -- county-parcel-screen/ county-sales-monitor/
Write-Output "--- last commit touching each skill ---"
git log -1 --format='%h %ci %s' -- county-parcel-screen/
git log -1 --format='%h %ci %s' -- county-sales-monitor/
Write-Output "=== main.log liveness ==="
foreach ($lp in @("$env:LOCALAPPDATA\Claude\Logs\main.log", "$env:APPDATA\Claude\logs\main.log")) {
  if (Test-Path $lp) { $li = Get-Item $lp; Write-Output "$lp mtime=$($li.LastWriteTime.ToString('s')) size=$($li.Length)" } else { Write-Output "$lp ABSENT" }
}
Write-Output "NOW=$((Get-Date).ToString('s'))"
