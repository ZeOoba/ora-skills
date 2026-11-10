Set-Location 'C:\Users\Owner\ora-skills'
"--plugin_of--"
python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print('land', plugin_of('land'));print('merge-ready', plugin_of('merge-ready'))"
"--git--"
git log -1 --format="%h %s"
git status --short -- land/ merge-ready/
"--files--"
foreach ($s in 'land','merge-ready') { "$s : " + ((Get-ChildItem $s -Recurse -File | ForEach-Object { $_.FullName.Substring((Resolve-Path $s).Path.Length+1) }) -join ', ') }
"--description budget--"
python tools\description_budget.py land merge-ready
"--ledger candidates--"
python tools\pending_reimport.py candidates 2>&1 | Select-String -Pattern 'land|merge-ready|candidate' | Select-Object -First 8
"--baseline--"
python tools\reimport_correlate.py baseline land merge-ready
