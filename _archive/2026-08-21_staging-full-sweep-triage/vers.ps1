Select-String -Path 'C:\Users\Owner\ora-skills\document-assembly\SKILL.md','C:\Users\Owner\ora-skills\exception-detection\SKILL.md' -Pattern '^- v[0-9]' |
  Select-Object -First 6 |
  ForEach-Object { $_.Filename + ' :: ' + $_.Line.Substring(0, [Math]::Min(110, $_.Line.Length)) }
