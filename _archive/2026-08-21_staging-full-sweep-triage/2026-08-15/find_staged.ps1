Select-String -Path 'C:\Users\Owner\ora-skills\tools\package_skills.py' -Pattern '_STAGED|staged_at' | ForEach-Object { "$($_.LineNumber): $($_.Line)" }
