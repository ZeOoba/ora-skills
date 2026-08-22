$ErrorActionPreference = 'Continue'
Set-Location 'C:\Users\Owner\ora-skills'
Write-Output '=== git status --short (whole repo) ==='
git status --short
Write-Output '=== git log -1 (register-scheduled-task) ==='
git log -1 --format='%h %ad %s' --date=short -- register-scheduled-task/
Write-Output '=== description length ==='
python -c "import re,io;b=re.match(r'^---\n(.*?)\n---\n',io.open(r'C:\Users\Owner\ora-skills\register-scheduled-task\SKILL.md',encoding='utf8').read(),re.S).group(1);d=re.search(r'^description:\s*(.*?)\s*$',b,re.M|re.S).group(1);n=re.search(r'^name:\s*(\S+)',b,re.M).group(1);print('name=',n);print('description chars =',len(d),'/1024')"
Write-Output '=== file sizes ==='
Get-ChildItem 'C:\Users\Owner\ora-skills\register-scheduled-task' -Recurse -File | ForEach-Object { Write-Output ("  " + $_.FullName.Replace('C:\Users\Owner\ora-skills\','') + "  " + $_.Length) }
