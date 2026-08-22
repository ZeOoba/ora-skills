Set-Location 'C:\Users\Owner\ora-skills'
python -m unittest tools.test_package_skills -v 2>&1 | Select-Object -Last 60
Write-Output "EXITCODE=$LASTEXITCODE"
