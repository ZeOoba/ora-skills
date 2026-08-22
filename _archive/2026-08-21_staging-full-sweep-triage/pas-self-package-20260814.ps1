Set-Location C:\Users\Owner\ora-skills
Write-Output '--- STEP0 PLUGIN_OF ---'
python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print(plugin_of('package-and-stage-skill'))"
Write-Output '--- STEP1 SOURCE ---'
git status --short -- package-and-stage-skill/
git log -1 --format='%h %ci %s' -- package-and-stage-skill/
Write-Output '--- STEP2 MAINLOG SYNC CYCLES (tail) ---'
Select-String -Path 'C:\Users\Owner\AppData\Roaming\Claude\logs\main.log' -Pattern 'Delta: \d+ to download|Sync complete' | Select-Object -Last 6 | ForEach-Object { $_.Line.Substring(0, [Math]::Min(160, $_.Line.Length)) }
Write-Output '--- STEP3 PACKAGE ---'
python tools\package_skills.py C:\Users\Owner\ora-skills\_staging\2026-08-14 package-and-stage-skill
Write-Output '--- HASH+B64 ---'
$p = 'C:\Users\Owner\ora-skills\_staging\2026-08-14\package-and-stage-skill.skill'
(Get-Item $p).Length
(Get-FileHash $p -Algorithm SHA256).Hash
[Convert]::ToBase64String([IO.File]::ReadAllBytes($p)) | Out-File -Encoding ascii ($p + '.b64')
Write-Output '--- HOOK FORENSICS ---'
git worktree list
Select-String -Path .git\hooks\post-commit -Pattern 'pending_reimport' | ForEach-Object { $_.Line }
Test-Path .worktrees
Get-ChildItem .worktrees -Directory -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Name
git log --format='%h %ci %s' --all --since='2026-08-14 17:30' -- lease-addendum/ | Select-Object -First 6
