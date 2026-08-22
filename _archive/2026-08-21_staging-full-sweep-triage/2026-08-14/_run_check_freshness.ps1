Set-Location "C:\Users\Owner\ora-skills"
python "_staging\2026-08-14\_check_freshness.py"
git log -1 --format="%H %ci %s"
git status --short -- register-scheduled-task/ daily-brief/
