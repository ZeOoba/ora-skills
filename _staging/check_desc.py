import re, pathlib
paths = [
    r'C:\Users\Owner\ora-skills\document-assembly\SKILL.md',
    r'C:\Users\Owner\ora-skills\portfolio-reporting\SKILL.md',
    r'C:\Users\Owner\ora-skills\acquisition-underwriting\SKILL.md',
]
for path in paths:
    t = pathlib.Path(path).read_text(encoding='utf-8')
    m = re.search(r'^---\s*\n(.*?)\n---', t, re.S)
    fm = m.group(1)
    dm = re.search(r'^description:\s*(.*?)(?=\n[a-zA-Z_-]+:|\Z)', fm, re.S|re.M)
    desc = dm.group(1).strip().strip("'\"")
    print(path, len(desc))
