$src = "C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\01_Workspace\outputs\2026-08-14_rev10-skill-packages\package-and-stage-skill.skill"
$dst = "C:\Users\Owner\ora-skills\_staging\2026-08-14\package-and-stage-skill.skill"
Copy-Item -Path $src -Destination $dst -Force
Get-FileHash -Algorithm SHA256 $dst
