Set-Location 'C:\Users\Owner\ora-skills'
$H = '_staging\handoff\2026-10-06_lease-v27-skills'
New-Item -ItemType Directory -Force -Path "$H\moved_pytest_cache" | Out-Null
foreach ($s in @('lease-form-qc','masterlease-jurisdiction-rebase')) { if (Test-Path "$s\.pytest_cache") { Move-Item "$s\.pytest_cache" "$H\moved_pytest_cache\$s" } }
if (Test-Path '.pytest_cache') { "repo-root .pytest_cache present (left in place)" }
New-Item -ItemType Directory -Force -Path "$H\superseded_pkg" | Out-Null
Move-Item "$H\lease-form-qc.skill" "$H\superseded_pkg\lease-form-qc.skill" -Force
Move-Item "$H\masterlease-jurisdiction-rebase.skill" "$H\superseded_pkg\masterlease-jurisdiction-rebase.skill" -Force
python tools\package_skills.py "$H" lease-form-qc masterlease-jurisdiction-rebase
python tools\stage_transfer.py emit "$H"
git status --short -- lease-form-qc/ masterlease-jurisdiction-rebase/
git log -1 --oneline
