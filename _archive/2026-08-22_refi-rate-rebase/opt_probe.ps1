Set-Location C:\Users\Owner\ora-skills
Write-Output "=== HOOKS DIR ==="
Get-ChildItem tools\hooks -File | Select-Object Name,Length
Write-Output "=== CONSUMER SWEEP: refi rate in other skills ==="
Get-ChildItem -Path . -Directory | Where-Object { $_.Name -notmatch '^(_|\.|tools|plugins|versions)' } | ForEach-Object {
  $d = $_.Name
  Get-ChildItem -Path $_.FullName -Recurse -File -Include *.md -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -notlike '*\versions\*' -and $_.FullName -notlike '*\_archive\*' } |
    Select-String -Pattern '7\.00%|7\.0% fixed|refi rate|refinance rate|fixed rate' |
    ForEach-Object { "$d :: $($_.Filename):$($_.LineNumber): $($_.Line.Trim().Substring(0,[Math]::Min(150,$_.Line.Trim().Length)))" }
}
