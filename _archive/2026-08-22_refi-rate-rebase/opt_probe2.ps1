Set-Location C:\Users\Owner\ora-skills
Write-Output "=== who calls 'git add' in tools/ ==="
Get-ChildItem tools -Recurse -File -Include *.py,pre-commit,post-commit -ErrorAction SilentlyContinue | Select-String -Pattern "git.{0,4}add|'add'|\"add\"" | ForEach-Object { "$($_.Filename):$($_.LineNumber): $($_.Line.Trim())" }
Write-Output "=== reflog (what actually happened) ==="
git reflog -8
Write-Output "=== was the harness staged before? check ORIG_HEAD-era index via reflog of index is N/A; show febb870 parent ==="
git log --oneline -3
