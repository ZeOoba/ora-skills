Set-Location C:\Users\Owner\ora-skills
Write-Output "=== GIT STATUS (skill dir) ==="
git status --short -- acquisition-underwriting/
Write-Output "=== GIT STATUS (repo overall) ==="
git status --short
Write-Output "=== LAST COMMIT ==="
git log -1 --oneline
Write-Output "=== PLUGIN MEMBERSHIP ==="
python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print(plugin_of('acquisition-underwriting'))"
Write-Output "=== RATE HITS ==="
Get-ChildItem -Path acquisition-underwriting -Recurse -Include *.md,*.json | Select-String -Pattern '7\.00%|7\.0%|6\.75|7\.25%|refi' | ForEach-Object { "$($_.Path.Replace('C:\Users\Owner\ora-skills\','')):$($_.LineNumber)" }
Write-Output "=== ROOT DEP ==="
Get-ChildItem -Path target-markets.json | Select-Object Name,Length,LastWriteTime
