import re, os, sys

REPO = r'C:\Users\Owner\ora-skills'
skills = sys.argv[1:]
for skill in skills:
    path = os.path.join(REPO, skill, 'SKILL.md')
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    parts = text.split('---', 2)
    body = parts[2] if len(parts) > 2 else text
    # find first markdown H1 heading line
    h1 = None
    for line in body.splitlines():
        line = line.strip()
        if line.startswith('# '):
            h1 = line
            break
    print('---', skill, '---')
    print('  H1:', h1)
