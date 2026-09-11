$ErrorActionPreference = 'Continue'
$root = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'
$expect = @{ 'county-parcel-screen' = 16; 'county-sales-monitor' = 1 }
$stamps = @()
foreach ($p in $expect.Keys) {
  Write-Output "=== $p ==="
  $dirs = Get-ChildItem $root -Recurse -Directory -Filter $p -ErrorAction SilentlyContinue
  if (-not $dirs) { Write-Output "CACHE-DIR STILL ABSENT"; continue }
  foreach ($d in $dirs) {
    $files = Get-ChildItem $d.FullName -Recurse -File
    Write-Output "dir=$($d.FullName)"
    Write-Output "dir.CreationTime=$($d.CreationTime.ToString('s'))  files=$($files.Count) expected=$($expect[$p])"
    $stamps += $d.CreationTime.ToString('HH:mm:ss')
    foreach ($f in $files) {
      $rel = $f.FullName.Substring($d.FullName.Length + 1).Replace('\','/')
      $h = (Get-FileHash $f.FullName -Algorithm SHA256).Hash.ToLower().Substring(0,12)
      Write-Output "  $rel  created=$($f.CreationTime.ToString('s'))  sha=$h"
    }
  }
}
Write-Output "=== main.log (Local) tail, SkillsPlugin lines since baseline 11:57:55 ==="
$lp = "$env:LOCALAPPDATA\Claude\Logs\main.log"
$li = Get-Item $lp
Write-Output "main.log mtime=$($li.LastWriteTime.ToString('s'))"
Get-Content $lp -Tail 4000 | Where-Object { $_ -match 'SkillsPlugin' -and $_ -match '(Delta|Sync complete)' } | Select-Object -Last 20
Write-Output "NOW=$((Get-Date).ToString('s'))"
