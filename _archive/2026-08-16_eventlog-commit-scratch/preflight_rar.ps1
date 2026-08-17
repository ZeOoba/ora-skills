Set-Location "C:\Users\Owner\ora-skills"
$s = "repo-architecture-review"

Write-Output "=== plugin_of ==="
python -c "import sys; sys.path.insert(0,'tools'); from package_skills import plugin_of; print('PLUGIN_OF_RESULT:', plugin_of('$s'))"

Write-Output "=== git status --short ==="
git status --short -- "$s/"

Write-Output "=== git log -1 ==="
git log -1 --format="COMMIT=%H DATE=%ad SUBJECT=%s" -- "$s/"

Write-Output "=== repo dir listing ==="
Get-ChildItem -Path "$s" -Recurse -File | ForEach-Object { Write-Output ("REPOFILE: " + $_.FullName.Substring((Get-Item $s).FullName.Length+1)) }

Write-Output "=== cache dir check (expect NOT FOUND -- first install) ==="
$cacheRoot = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin"
$cacheDirs = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter $s -ErrorAction SilentlyContinue
if ($cacheDirs) {
    foreach ($d in $cacheDirs) { Write-Output ("CACHE_DIR: " + $d.FullName) }
} else {
    Write-Output "CACHE_DIR: NOT FOUND"
}
