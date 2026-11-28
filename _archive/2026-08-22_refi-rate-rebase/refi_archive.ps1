$ErrorActionPreference = "Stop"
$ROOT = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Business"
$stamp = "2026-08-22_refi-rebase-6.50"
$targets = @(
 "Investment Candidates -- 2026\20260610_GS-F_Model_v03.xlsx",
 "Investment Candidates -- 2026\[P-34] IRR Model.xlsx",
 "Investment Candidates -- 2026\[P-36] IRR Model.xlsx",
 "Investment Candidates -- 2026\[deal] Columbus IRR Model.xlsx",
 "Investment Candidates -- 2026\[P-10] IRR Model.xlsx",
 "Investment Candidates -- 2026\ORA_UnderwritingModel_[P-35]_v2.0.xlsx",
 "Investment Candidates -- 2026\ORA_Underwriting_[P-08]_v1.0.xlsx",
 "Investment Candidates -- 2026\ORA_Underwriting_[P-09]_v1.0.xlsx",
 "Investment Candidates -- 2026\outputs\2026-07-18_[P-08]_Underwriting-Model_v01.xlsx",
 "Investment Candidates -- 2026\outputs\2026-07-18_[P-09]_Underwriting-Model_v01.xlsx"
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
