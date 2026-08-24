Set-Location C:\Users\Owner\ora-skills
Write-Output "=== HARNESS HITS ==="
Get-ChildItem -Path acquisition-underwriting-eval-harness -Recurse -File -Include *.py,*.md,*.json,*.yaml,*.yml -ErrorAction SilentlyContinue | Select-String -Pattern '7\.00%|6\.75|7\.25%|refi_rate|refi rate' | ForEach-Object { "$($_.Path.Replace('C:\Users\Owner\ora-skills\','')):$($_.LineNumber): $($_.Line.Trim())" }
Write-Output "=== VERSIONS DIR ==="
Get-ChildItem -Path acquisition-underwriting -Recurse -File | Select-Object FullName,Length
