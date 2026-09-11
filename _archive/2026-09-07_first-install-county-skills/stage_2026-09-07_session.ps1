$ErrorActionPreference = 'Stop'
$stage = 'C:\Users\Owner\ora-skills\_staging\2026-09-07'
$out = 'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\583f08bc-0123-4111-8158-8fe3d927e350\local_cba9346d-b4e9-4ef6-82cb-3921ca480245\outputs'
if (-not (Test-Path $out)) { New-Item -ItemType Directory -Path $out | Out-Null }
foreach ($p in @('county-parcel-screen','county-sales-monitor')) {
  $src = Join-Path $stage "$p.skill"; $dst = Join-Path $out "$p.skill"
  Copy-Item $src $dst -Force
  $a = (Get-FileHash $src -Algorithm SHA256).Hash; $b = (Get-FileHash $dst -Algorithm SHA256).Hash
  $ok = if ($a -eq $b) { 'HASH-IDENTICAL' } else { 'HASH-DIFF' }
  Write-Output "$p.skill staged -> $dst  $ok  $($b.ToLower())"
}
Write-Output "=== BASELINE (pre-click) ==="
$root = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'
foreach ($p in @('county-parcel-screen','county-sales-monitor')) {
  $d = Get-ChildItem $root -Recurse -Directory -Filter $p -ErrorAction SilentlyContinue
  if ($d) { foreach ($x in $d) { Write-Output "$p BASELINE dir=$($x.FullName) created=$($x.CreationTime.ToString('s'))" } }
  else { Write-Output "$p BASELINE = NO DIRECTORY (absent)" }
}
Write-Output "BASELINE-STAMP=$((Get-Date).ToString('s'))"
