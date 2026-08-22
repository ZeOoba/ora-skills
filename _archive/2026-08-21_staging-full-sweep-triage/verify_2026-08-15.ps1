$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Owner\ora-skills'
Write-Output '=== git status ==='
git status --short
Write-Output '=== test_package_skills.py ==='
python tools\test_package_skills.py 2>&1 | Select-Object -Last 15
Write-Output '=== test_skill_drift_report.py ==='
python tools\test_skill_drift_report.py 2>&1 | Select-Object -Last 15
Write-Output '=== check-staged ==='
python tools\package_skills.py --check-staged
Write-Output "check-staged exit: $LASTEXITCODE"
Write-Output '=== check-tree-hygiene ==='
python tools\package_skills.py --check-tree-hygiene
Write-Output "check-tree-hygiene exit: $LASTEXITCODE"
Write-Output '=== insurance-renewal-review frontmatter validate ==='
python -c "import sys; sys.path.insert(0,'tools'); from package_skills import validate_skill_frontmatter; from pathlib import Path; e=validate_skill_frontmatter(Path('insurance-renewal-review')); print('OK' if not e else e)"
