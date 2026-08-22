Set-Location 'C:\Users\Owner\ora-skills'
git log -1 --format="GITLOG`t%H`t%ad`t%s" --date=iso -- package-and-stage-skill/ | ForEach-Object { Write-Output $_ }
git status --short -- package-and-stage-skill/ | ForEach-Object { Write-Output ("STATUS`t" + $_) }
Write-Output ("CLEAN=" + ((git status --short -- package-and-stage-skill/).Count -eq 0))
