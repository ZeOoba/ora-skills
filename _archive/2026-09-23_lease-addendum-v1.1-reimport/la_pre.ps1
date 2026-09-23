Set-Location C:\Users\Owner\ora-skills
Write-Output "== H1"; Select-String -Path lease-addendum\SKILL.md -Pattern '^# ' | Select-Object -First 1 | ForEach-Object { $_.Line }
Write-Output "== plugin_of"; python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print(plugin_of('lease-addendum'))"
Write-Output "== git status"; git status --short -- lease-addendum/
Write-Output "== git log"; git log -1 --format="%h %ci %s" -- lease-addendum/
Write-Output "== baseline"; python tools\reimport_correlate.py baseline lease-addendum; Write-Output "exit=$LASTEXITCODE"
Write-Output "== shared-deps"; python tools\pending_reimport.py shared-deps; Write-Output "exit=$LASTEXITCODE"
Write-Output "== budget"; python tools\description_budget.py lease-addendum
Write-Output "== lint"; python tools\script_resource_lint.py lease-addendum
Write-Output "== mainlog"; Get-Item "$env:LOCALAPPDATA\Claude\Logs\main.log" | Select-Object LastWriteTime
