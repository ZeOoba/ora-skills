import re, os, sys

REPO = r'C:\Users\Owner\ora-skills'
skills = sys.argv[1:]
for skill in skills:
    path = os.path.join(REPO, skill, 'SKILL.md')
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()
    parts = text.split('---', 2)
    fm = parts[1] if len(parts) > 2 else text
    # own-version marker is always immediately followed by '(' -- e.g. "v1.3 (2026-07-15: ...)"
    m = re.findall(r'v(\d+\.\d+(?:\.\d+)?)\s*\(', fm)
    if not m:
        m = re.findall(r'v(\d+\.\d+(?:\.\d+)?)', fm)
    print(skill, '->', m[0] if m else 'UNKNOWN')
