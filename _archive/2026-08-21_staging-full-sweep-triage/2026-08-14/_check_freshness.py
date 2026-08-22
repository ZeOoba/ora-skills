import zipfile, hashlib

def norm(b):
    return b.replace(b'\r\n', b'\n').rstrip()

def sha(b):
    return hashlib.sha256(b).hexdigest()

# --- register-scheduled-task: SKILL.md vs repo ---
with zipfile.ZipFile('_staging/2026-08-14/register-scheduled-task.skill') as z:
    pkg = z.read('register-scheduled-task/SKILL.md')
with open('register-scheduled-task/SKILL.md', 'rb') as f:
    repo = f.read()
print('register-scheduled-task/SKILL.md')
print('  raw match:', pkg == repo)
print('  normalized match:', norm(pkg) == norm(repo))
print('  pkg words:', len(pkg.decode("utf-8", "ignore").split()))
print('  repo words:', len(repo.decode("utf-8", "ignore").split()))

# --- daily-brief: SKILL.md vs repo ---
with zipfile.ZipFile('_staging/2026-08-14/daily-brief.skill') as z:
    pkg2 = z.read('daily-brief/SKILL.md')
    tm_pkg = z.read('daily-brief/target-markets.json')
with open('daily-brief/SKILL.md', 'rb') as f:
    repo2 = f.read()
print('daily-brief/SKILL.md')
print('  raw match:', pkg2 == repo2)
print('  normalized match:', norm(pkg2) == norm(repo2))
print('  pkg words:', len(pkg2.decode("utf-8", "ignore").split()))
print('  repo words:', len(repo2.decode("utf-8", "ignore").split()))

# --- shared root dep: target-markets.json ---
with open('target-markets.json', 'rb') as f:
    tm_repo = f.read()
print('target-markets.json (shared root dep)')
print('  raw match:', tm_pkg == tm_repo)
print('  normalized match:', norm(tm_pkg) == norm(tm_repo))
print('  pkg sha256:', sha(tm_pkg))
print('  repo sha256:', sha(tm_repo))
