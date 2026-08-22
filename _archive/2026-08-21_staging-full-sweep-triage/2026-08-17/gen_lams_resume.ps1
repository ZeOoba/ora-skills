cd C:\Users\Owner\ora-skills
python tools\pause_resume.py gen-resume `
  --fleet lams `
  --id ora-lams-routine-pause-resume-08-21 `
  --fire-at "2026-08-21 17:05" `
  --exclude ora-passed-deal-tracker `
  --pause-date 2026-08-17 `
  --gen-date 2026-08-17 `
  --out "C:\Users\Owner\ora-skills\_staging\2026-08-17\ora-lams-routine-pause-resume-08-21_GENERATED_SKILL.md"
Write-Output '--- diff (generated vs hand-written draft, id-list line only) ---'
Select-String -Path "C:\Users\Owner\ora-skills\_staging\2026-08-17\ora-lams-routine-pause-resume-08-21_GENERATED_SKILL.md" -Pattern '^ora-' | Select-Object -First 1
