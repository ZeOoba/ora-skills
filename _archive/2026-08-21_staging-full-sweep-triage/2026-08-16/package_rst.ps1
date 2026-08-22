Set-Location "C:\Users\Owner\ora-skills"
python tools\package_skills.py "C:\Users\Owner\ora-skills\_staging\2026-08-16" register-scheduled-task
Write-Output ("PACKAGE_EXIT_CODE=" + $LASTEXITCODE)
