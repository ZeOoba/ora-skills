Set-Location C:\Users\Owner\ora-skills
Write-Output '--- PLUGIN_OF ---'
python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print(plugin_of('lease-addendum'))"
Write-Output '--- LEDGER ---'
python tools\pending_reimport.py list
Write-Output '--- GIT ---'
git rev-parse --short HEAD
git status --porcelain
Write-Output '--- STAGE CANON ---'
New-Item -ItemType Directory -Force -Path C:\Users\Owner\ora-skills\_staging\2026-08-14 | Out-Null
Copy-Item C:\Users\Owner\ora-skill-packages\lease-addendum.skill C:\Users\Owner\ora-skills\_staging\2026-08-14\lease-addendum.skill -Force
(Get-FileHash C:\Users\Owner\ora-skills\_staging\2026-08-14\lease-addendum.skill -Algorithm SHA256).Hash
