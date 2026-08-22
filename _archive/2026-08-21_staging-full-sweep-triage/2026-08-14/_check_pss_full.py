import zipfile, hashlib

def norm(b):
    return b.replace(b'\r\n', b'\n').rstrip()

path = r'C:\Users\Owner\OneDrive - Oxford Capital Partners\Claude_Workspace\01_Workspace\outputs\2026-08-14_rev10-skill-packages\package-and-stage-skill.skill'
with zipfile.ZipFile(path) as z:
    for info in z.infolist():
        print(f'  {info.filename}  ({info.file_size} bytes)')
    pkg = z.read('package-and-stage-skill/SKILL.md')

with open('package-and-stage-skill/SKILL.md', 'rb') as f:
    repo = f.read()

print('raw match:', pkg == repo)
print('normalized match:', norm(pkg) == norm(repo))
print('pkg words:', len(pkg.decode("utf-8","ignore").split()))
print('repo words:', len(repo.decode("utf-8","ignore").split()))
print('pkg sha256:', hashlib.sha256(pkg).hexdigest())
print('repo sha256:', hashlib.sha256(repo).hexdigest())
