#!/usr/bin/env python3
"""Report SKILL.md frontmatter description lengths across the repo."""
import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKIP = {'_archive', 'tools', '.git'}

for d in sorted(REPO.iterdir()):
    if not d.is_dir() or d.name in SKIP:
        continue
    f = d / 'SKILL.md'
    if not f.is_file():
        continue
    text = f.read_text(encoding='utf-8', errors='replace')
    m = re.search(r'^---\s*\n(.*?)\n---', text, re.S)
    if not m:
        print(f'{d.name}: NO FRONTMATTER')
        continue
    dm = re.search(r"^description:\s*(.*?)(?=\n[a-zA-Z_-]+:|\Z)", m.group(1), re.S | re.M)
    if not dm:
        print(f'{d.name}: NO DESCRIPTION')
        continue
    desc = dm.group(1).strip().strip("'\"")
    flag = ' <-- OVER 1024' if len(desc) > 1024 else ''
    print(f'{d.name}: {len(desc)}{flag}')
