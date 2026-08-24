Set-Location C:\Users\Owner\ora-skills
Write-Output "=== FRONTMATTER GATE ==="
python -c "import os,re,sys; root='acquisition-underwriting'; want=os.path.basename(root); b=re.match(r'^---\n(.*?)\n---\n', open(os.path.join(root,'SKILL.md'),encoding='utf8').read(), re.S).group(1); nm=re.search(r'^name:\s*(\S+)\s*$', b, re.M).group(1); d=re.search(r'^description:\s*\"?(.*?)\"?\s*$', b, re.M|re.S).group(1); bad=([f'name {nm!r} != dir {want!r}'] if nm!=want else [])+([f'description {len(d)}/1024'] if len(d)>1024 else []); print(('FAIL: '+'; '.join(bad)) if bad else f'OK name={want} description={len(d)}/1024')"
Write-Output "=== RESIDUAL 7.00 / 6.75 / 7.25 IN SHIPPED FILES ==="
Get-ChildItem -Path acquisition-underwriting -File -Recurse -Include *.md | Where-Object { $_.FullName -notlike '*\versions\*' } | Select-String -Pattern '7\.00%|7\.0%|6\.75|7\.25%|6\.50%|6\.25' | ForEach-Object { "$($_.Filename):$($_.LineNumber): $($_.Line.Substring(0,[Math]::Min(160,$_.Line.Length)))" }
Write-Output "=== DIFFSTAT ==="
git diff --stat -- acquisition-underwriting/
