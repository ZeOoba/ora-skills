Set-Location C:\Users\Owner\ora-skills
Write-Output "=== tools/ callers of git add ==="
Get-ChildItem tools -Recurse -File -Include *.py -ErrorAction SilentlyContinue | Select-String -SimpleMatch -Pattern '"add"' | ForEach-Object { "$($_.Filename):$($_.LineNumber): $($_.Line.Trim())" }
Get-ChildItem tools -Recurse -File -ErrorAction SilentlyContinue | Select-String -SimpleMatch -Pattern 'git add' | ForEach-Object { "$($_.Filename):$($_.LineNumber): $($_.Line.Trim())" }
Write-Output "=== timing of the concurrent harness commit ==="
git log -1 --format='%H%n%an%n%ai%n%s' 7d10e3f
Write-Output "=== timing of my commits ==="
git log -1 --format='%H %ai %s' 5b1f319
git log -1 --format='%H %ai %s' febb870
Write-Output "=== does isolated-commit expose commit_isolated_replacement? ==="
Get-ChildItem . -Recurse -File -Include *.py -ErrorAction SilentlyContinue | Select-String -SimpleMatch -Pattern 'commit_isolated_replacement' | ForEach-Object { "$($_.Path.Replace('C:\Users\Owner\ora-skills\','')):$($_.LineNumber)" } | Select-Object -First 12
Write-Output "=== current tree ==="
git status -sb
