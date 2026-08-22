Set-Location 'C:\Users\Owner\ora-skills'
git add tools\package_skills.py tools\test_package_skills.py package-and-stage-skill\SKILL.md
Write-Output "=== staged diff stat ==="
git diff --cached --stat
Write-Output "=== check-staged (frontmatter/description gate) ==="
python tools\package_skills.py --check-staged
Write-Output "CHECK_STAGED_EXIT=$LASTEXITCODE"
Write-Output "=== full test suite (re-run against staged working copy) ==="
python -m unittest tools.test_package_skills 2>&1 | Select-Object -Last 10
Write-Output "TEST_EXIT=$LASTEXITCODE"
