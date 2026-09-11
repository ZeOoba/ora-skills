$log = "$env:LOCALAPPDATA\Claude\Logs\main.log"
Get-Content $log | Select-String "SkillsPlugin" | Where-Object { $_ -match "19:48:2[5-9]|19:48:3[0-9]|19:48:4[0-5]" }
