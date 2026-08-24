Set-Location C:\Users\Owner\ora-skills
Write-Output "=== claim_work / isolated-commit helpers ==="
Get-ChildItem C:\Users\Owner\.claude -Recurse -File -Include claim_work.py,*isolated*.py -ErrorAction SilentlyContinue | Select-Object FullName | Select-Object -First 10
Get-ChildItem C:\Users\Owner\ora-skills\tools -File -ErrorAction SilentlyContinue | Select-Object Name
Write-Output "=== UNDERWRITING WORKBOOK CANDIDATES ==="
$roots = @("C:\Users\Owner\OneDrive - Oxford Capital Partners")
foreach ($r in $roots) {
  Get-ChildItem -Path $r -Recurse -File -Include *.xlsx -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -match 'ORA_|[Uu]nderwrit|[Mm]odel|[Rr]eturns' -and $_.FullName -notlike '*\_archive\*' -and $_.Name -notlike '~$*' } |
    Select-Object FullName,Length,LastWriteTime | Sort-Object LastWriteTime -Descending | Select-Object -First 25
}
