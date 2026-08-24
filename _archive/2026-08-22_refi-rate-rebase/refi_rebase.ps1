$ErrorActionPreference = "Continue"
$ROOT = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Business\Investment Candidates -- 2026"
$jobs = @(
 @{f="20260610_470-REDACTED-148_Model_v03.xlsx";                                   s="Inputs"; c="B49"},
 @{f="2262-112th-Ave-Holland-MI IRR Model.xlsx";                                s="Inputs"; c="B59"},
 @{f="8025-8009 IRR Model.xlsx";                                                s="Inputs"; c="B30"},
 @{f="808 REDACTED-165 Columbus IRR Model.xlsx";                                      s="Inputs"; c="B34"},
 @{f="IRR Model Pike Plaza Indy Car Dealerships 7.27.2026.xlsx";                s="Inputs"; c="B24"},
 @{f="ORA_UnderwritingModel_125DouglasPike_v2.0.xlsx";                          s="Inputs"; c="B38"},
 @{f="ORA_Underwriting_2900-Northridge-Dr-NW_v1.0.xlsx";                        s="Inputs"; c="B36"},
 @{f="ORA_Underwriting_4331-Brockton-Dr-SE_v1.0.xlsx";                          s="Inputs"; c="B36"},
 @{f="outputs\2026-07-18_2900-Northridge-Dr-NW_Underwriting-Model_v01.xlsx";    s="Inputs"; c="B37"},
 @{f="outputs\2026-07-18_4331-Brockton-Dr-SE_Underwriting-Model_v01.xlsx";      s="Inputs"; c="B37"}
)
$xl = New-Object -ComObject Excel.Application
$xl.Visible = $false
$xl.DisplayAlerts = $false
$xl.AskToUpdateLinks = $false
$xl.EnableEvents = $false
foreach ($j in $jobs) {
  $p = Join-Path $ROOT $j.f
  $name = Split-Path $p -Leaf
  if (-not (Test-Path $p)) { Write-Output "MISSING $name"; continue }
  try {
    $wb = $xl.Workbooks.Open($p, 0, $false)
    $ws = $wb.Worksheets.Item($j.s)
    $cell = $ws.Range($j.c)
    $before = $cell.Value2
    if ([Math]::Abs([double]$before - 0.07) -gt 0.0000001) {
      Write-Output "SKIP $name -- $($j.s)!$($j.c) is $before, not 0.07 (unexpected; not touched)"
      $wb.Close($false); continue
    }
    $cell.Value2 = 0.065
    $xl.CalculateFullRebuild()
    $wb.Save()
    $after = $ws.Range($j.c).Value2
    $wb.Close($false)
    Write-Output "REBASED $name -- $($j.s)!$($j.c): $before -> $after"
  } catch {
    Write-Output "ERROR $name -- $($_.Exception.Message)"
    try { $wb.Close($false) } catch {}
  }
}
$xl.Quit()
[void][Runtime.InteropServices.Marshal]::ReleaseComObject($xl)
Write-Output "DONE"
