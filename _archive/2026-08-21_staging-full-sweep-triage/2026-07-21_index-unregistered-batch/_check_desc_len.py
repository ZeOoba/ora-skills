import re
t = open('acquisition-underwriting/SKILL.md', encoding='utf-8').read()
m = re.search(r'description: (.*)', t)
print('description length:', len(m.group(1)))
