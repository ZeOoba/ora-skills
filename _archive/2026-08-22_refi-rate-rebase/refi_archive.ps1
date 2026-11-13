$ErrorActionPreference = "Stop"
$ROOT = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Business"
$stamp = "2026-08-22_refi-rebase-6.50"
$targets = @(
 "Investment Candidates -- 2026\20260610_GS-F_Model_v03.xlsx",
 "Investment Candidates -- 2026\2262-112th-Ave-Holland-MI IRR Model.xlsx",
 "Investment Candidates -- 2026\8025-8009 IRR Model.xlsx",
 "Investment Candidates -- 2026\[deal] Columbus IRR Model.xlsx",
 "Investment Candidates -- 2026\IRR Model Pike Plaza Indy Car Dealerships 7.27.2026.xlsx",
 "Investment Candidates -- 2026\ORA_UnderwritingModel_125DouglasPike_v2.0.xlsx",
 "Investment Candidates -- 2026\ORA_Underwriting_2900-Northridge-Dr-NW_v1.0.xlsx",
 "Investment Candidates -- 2026\ORA_Underwriting_4331-Brockton-Dr-SE_v1.0.xlsx",
 "Investment Candidates -- 2026\outputs\2026-07-18_2900-Northridge-Dr-NW_Underwriting-Model_v01.xlsx",
 "Investment Candidates -- 2026\outputs\2026-07-18_4331-Brockton-Dr-SE_Underwriting-Model_v01.xlsx"
)
Write-Output "=== EXCEL AVAILABILITY ==="
try { $x = New-Object -ComObject Excel.Application; Write-Output "Excel COM OK version $($x.Version)"; $x.Quit(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($x) }
catch { Write-Output "EXCEL COM UNAVAILABLE: $($_.Exception.Message)" }
Write-Output "=== ARCHIVE ==="
foreach ($t in $targets) {
  $src = Join-Path $ROOT $t
  if (-not (Test-Path $src)) { Write-Output "MISSING: $t"; continue }
  $dir = Split-Path $src -Parent
  $arch = Join-Path $dir "_archive\$stamp"
  New-Item -ItemType Directory -Force -Path $arch | Out-Null
  $dst = Join-Path $arch (Split-Path $src -Leaf)
  if (Test-Path $dst) { Write-Output "ALREADY ARCHIVED: $(Split-Path $src -Leaf)"; continue }
  Copy-Item $src -Destination $dst -Force
  $h1 = (Get-FileHash $src -Algorithm SHA256).Hash
  $h2 = (Get-FileHash $dst -Algorithm SHA256).Hash
  $ok = if ($h1 -eq $h2) { "OK" } else { "HASH MISMATCH" }
  Write-Output "$ok  $(Split-Path $src -Leaf)  -> _archive\$stamp"
}
