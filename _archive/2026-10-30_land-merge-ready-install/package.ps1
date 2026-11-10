Set-Location 'C:\Users\Owner\ora-skills'
$out = 'C:\Users\Owner\ora-skills\_staging\handoff\2026-10-30_land-merge-ready'
python tools\package_skills.py "$out" land merge-ready
"PACKAGE_EXIT=$LASTEXITCODE"
python tools\script_resource_lint.py land
"LINT_EXIT=$LASTEXITCODE"
Set-Location $out
python C:\Users\Owner\ora-skills\tools\stage_transfer.py emit .
"EMIT_EXIT=$LASTEXITCODE"
python C:\Users\Owner\ora-skills\tools\reimport_correlate.py precheck "$out\land.skill" "$out\merge-ready.skill"
"PRECHECK_EXIT=$LASTEXITCODE"
