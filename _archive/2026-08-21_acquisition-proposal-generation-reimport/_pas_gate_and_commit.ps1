Set-Location 'C:\Users\Owner\ora-skills'

Write-Output "=== FRONTMATTER GATE (dogfooding step 2a) ==="
python -c "
import re
root = 'package-and-stage-skill'
b = re.match(r'^---\n(.*?)\n---\n', open('package-and-stage-skill/SKILL.md', encoding='utf8').read(), re.S).group(1)
nm = re.search(r'^name:\s*(\S+)\s*$', b, re.M).group(1)
d  = re.search(r'^description:\s*\"?(.*?)\"?\s*$', b, re.M | re.S).group(1)
bad = ([f'name {nm!r} != dir {root!r}'] if nm != root else []) + ([f'description {len(d)}/1024'] if len(d) > 1024 else [])
print(('FAIL: ' + '; '.join(bad)) if bad else f'OK name={root} description={len(d)}/1024')
"

Write-Output ""
Write-Output "=== DIFF STAT ==="
git diff --stat -- package-and-stage-skill/ | ForEach-Object { Write-Output $_ }

Write-Output ""
Write-Output "=== STAGE + COMMIT ==="
git add package-and-stage-skill/SKILL.md
git commit -m "docs(package-and-stage-skill): v1.22 - main.log liveness fallback + canonical .ps1 snippet" 2>&1 | ForEach-Object { Write-Output ("COMMIT`t" + $_) }
Write-Output ("EXITCODE=" + $LASTEXITCODE)

Write-Output ""
git log -1 --format="GITLOG`t%H`t%ad`t%s" --date=iso -- package-and-stage-skill/
git status --short -- package-and-stage-skill/
