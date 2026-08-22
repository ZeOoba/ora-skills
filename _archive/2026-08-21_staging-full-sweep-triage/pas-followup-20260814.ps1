Set-Location C:\Users\Owner\ora-skills
Write-Output '--- NEW HEAD ---'
git log --format='%h %ci %s' -3
git diff --name-only 899b10b..de0ac95
Write-Output '--- HOOKSPATH ---'
git config core.hooksPath
Write-Output '--- HOOK MERGE HANDLING ---'
Select-String -Path tools\hooks\post-commit -Pattern 'record|merge|HEAD' | ForEach-Object { ('L' + $_.LineNumber + ': ' + $_.Line.Trim()) }
Write-Output '--- LEDGER NOW ---'
python tools\pending_reimport.py list
Write-Output '--- MAINLOG CONTEXT 18:09 / 18:14 ---'
Select-String -Path 'C:\Users\Owner\AppData\Roaming\Claude\logs\main.log' -Pattern 'SkillsPlugin' | Select-Object -Last 20 | ForEach-Object { $_.Line.Substring(0, [Math]::Min(170, $_.Line.Length)) }
