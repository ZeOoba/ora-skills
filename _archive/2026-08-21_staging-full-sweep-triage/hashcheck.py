import hashlib
import os

def norm_hash(path):
    with open(path, 'rb') as f:
        data = f.read()
    text = data.decode('utf-8', errors='replace')
    normalized = '\n'.join(line.rstrip() for line in text.replace('\r\n', '\n').split('\n'))
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

repo_root = r'C:\Users\Owner\ora-skills'
cache_root = r'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'

pairs = [
    os.path.join('register-scheduled-task', 'SKILL.md'),
    os.path.join('register-scheduled-task', 'references', 'incident-history.md'),
    os.path.join('daily-brief', 'SKILL.md'),
]
for rel in pairs:
    r = norm_hash(os.path.join(repo_root, rel))
    c = norm_hash(os.path.join(cache_root, rel))
    print(rel, '-> MATCH' if r == c else '-> MISMATCH', r[:12], c[:12])

r = norm_hash(os.path.join(repo_root, 'target-markets.json'))
c = norm_hash(os.path.join(cache_root, 'daily-brief', 'target-markets.json'))
print('target-markets.json', '-> MATCH' if r == c else '-> MISMATCH', r[:12], c[:12])
