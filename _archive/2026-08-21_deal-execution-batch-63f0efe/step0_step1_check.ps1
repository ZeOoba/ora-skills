Set-Location "C:\Users\Owner\ora-skills"

$skills = @("deal-execution","document-assembly","estoppel-request-generation","lease-abstraction-pipeline","legal-intelligence","package-and-stage-skill")

Write-Output "=== STEP 0: plugin_of check ==="
foreach ($s in $skills) {
    $out = python -c "import sys;sys.path.insert(0,'tools');from package_skills import plugin_of;print(plugin_of('$s'))"
    Write-Output "$s -> $out"
}

Write-Output ""
Write-Output "=== STEP 1: git status --short per skill ==="
foreach ($s in $skills) {
    Write-Output "-- $s --"
    git status --short -- "$s/"
}

Write-Output ""
Write-Output "=== STEP 1: git log -1 per skill ==="
foreach ($s in $skills) {
    Write-Output "-- $s --"
    git log -1 --format="%H %ad %s" --date=iso -- "$s/"
}

Write-Output ""
Write-Output "=== overall git status --short (full repo) ==="
git status --short
