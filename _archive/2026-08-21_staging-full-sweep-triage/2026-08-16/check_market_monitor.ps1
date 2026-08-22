Set-Location "C:\Users\Owner\ora-skills"

Write-Output "=== STEP0: plugin_of ==="
python -c "import sys; sys.path.insert(0,'tools'); from package_skills import plugin_of; print('PLUGIN_OF_RESULT:', plugin_of('market-monitor'))"

Write-Output "=== STEP1: git status/log for market-monitor ==="
git status --short -- market-monitor/
git log -1 --format="COMMIT=%H DATE=%ad SUBJECT=%s" -- market-monitor/

Write-Output "=== STEP2: zip entries of staged .skill ==="
$skillPath = "C:\Users\Owner\ora-skills\_staging\2026-08-16\market-monitor.skill"
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead($skillPath)
foreach ($entry in $zip.Entries) {
    Write-Output ("ENTRY: " + $entry.FullName + " (" + $entry.Length + " bytes)")
}
$zip.Dispose()

Write-Output "=== STEP3: locate cache dir for market-monitor ==="
$cacheRoot = "$env:APPDATA\Claude\local-agent-mode-sessions\skills-plugin"
$cacheDirs = Get-ChildItem -Path $cacheRoot -Recurse -Directory -Filter "market-monitor" -ErrorAction SilentlyContinue
foreach ($d in $cacheDirs) { Write-Output ("CACHE_DIR: " + $d.FullName) }
