Set-Location C:\Users\Owner\ora-skills
Write-Output "=== PLUGIN_OF ==="
python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print(plugin_of('lease-addendum'))"
Write-Output "=== GIT STATUS (skill dir) ==="
git status --short -- lease-addendum/
Write-Output "=== GIT STATUS (repo) ==="
git status --short
Write-Output "=== HEAD ==="
git log -1 --format="%h %ad %s" --date=iso
Write-Output "=== LAST COMMIT TOUCHING SKILL ==="
git log -1 --format="%h %ad %s" --date=iso -- lease-addendum/
Write-Output "=== SKILL DIR ENTRIES ==="
Get-ChildItem -Recurse -File lease-addendum | ForEach-Object { $_.FullName.Replace("C:\Users\Owner\ora-skills\","") }
Write-Output "=== CACHE_ROOT ==="
python -c "import sys;sys.path.insert(0,'tools');import pending_reimport as p;print(getattr(p,'CACHE_ROOT','NO CACHE_ROOT ATTR'))"
Write-Output "=== CACHE MIRROR SEARCH ==="
$root = "C:\Users\Owner\AppData\Roaming\Claude"
Get-ChildItem -Path $root -Recurse -Directory -Filter "lease-addendum" -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
Write-Output "=== LEDGER ==="
python tools/pending_reimport.py list
Write-Output "=== DONE ==="
