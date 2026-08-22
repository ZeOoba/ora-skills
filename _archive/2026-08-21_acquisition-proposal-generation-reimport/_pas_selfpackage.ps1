Set-Location 'C:\Users\Owner\ora-skills'

Write-Output "=== STEP 0: PLUGIN MEMBERSHIP ==="
python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print('PLUGIN_OF=' + str(plugin_of('package-and-stage-skill')))"

Write-Output ""
Write-Output "=== BRIDGE-FIRST FRESHNESS SCREEN (pre-package baseline) ==="
$cacheRoot = Join-Path $env:APPDATA 'Claude\local-agent-mode-sessions\skills-plugin'
$dirs = @(Get-ChildItem -LiteralPath $cacheRoot -Recurse -Directory -Filter 'package-and-stage-skill' -ErrorAction SilentlyContinue)
foreach ($d in $dirs) {
    $i = Get-Item -LiteralPath $d.FullName
    Write-Output ("CACHE_DIR=" + $d.FullName)
    Write-Output ("CACHE_DIR_CREATED={0:yyyy-MM-dd HH:mm:ss}" -f $i.CreationTime)
    $ch = (Get-FileHash -LiteralPath (Join-Path $d.FullName 'SKILL.md') -Algorithm SHA256).Hash.ToLower()
    $rh = (Get-FileHash -LiteralPath 'C:\Users\Owner\ora-skills\package-and-stage-skill\SKILL.md' -Algorithm SHA256).Hash.ToLower()
    Write-Output ("CACHE_HASH=" + $ch)
    Write-Output ("REPO_HASH=" + $rh)
    Write-Output ("MATCH=" + ($ch -eq $rh))
}
Write-Output "(A MATCH here would be the mirror-sync-hook artifact just committed, per v1.13 doctrine -- NOT evidence of install. Proceeding to package regardless, per the revised step-2 gate.)"

Write-Output ""
Write-Output "=== PACKAGE (sanctioned tool) ==="
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-21_pas-v1.22-selfpackage" package-and-stage-skill 2>&1 | ForEach-Object { Write-Output ("PKG`t" + $_) }
Write-Output ("EXITCODE=" + $LASTEXITCODE)

Write-Output ""
Get-ChildItem -LiteralPath "C:\Users\Owner\ora-skills\_staging\2026-08-21_pas-v1.22-selfpackage" -File | ForEach-Object {
    $h = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLower()
    Write-Output ("OUT`t{0}`t{1}`t{2}" -f $_.Name, $_.Length, $h)
}
