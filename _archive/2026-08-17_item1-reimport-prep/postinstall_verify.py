import zipfile, hashlib, os

STAGING = r'C:\Users\Owner\ora-skills\_staging\2026-08-17_item1-reimport-prep'
CACHE_BASE = r'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'

PACKAGES = {
    'daily-brief': os.path.join(STAGING, 'daily-brief.skill'),
    'ora-setup-audit': os.path.join(STAGING, 'ora-setup-audit.skill'),
    'register-scheduled-task': os.path.join(STAGING, 'register-scheduled-task.skill'),
}

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def norm(b):
    return b.decode('utf-8', errors='replace').replace('\r\n', '\n').rstrip()

for skill, pkg_path in PACKAGES.items():
    print('=' * 70)
    print(skill)
    cache_dir = os.path.join(CACHE_BASE, skill)
    with zipfile.ZipFile(pkg_path) as z:
        entries = [e for e in z.namelist() if not e.endswith('/')]
        print(f'  packaged file count: {len(entries)}')
        all_ok = True
        for e in entries:
            rel = '/'.join(e.split('/')[1:])
            cache_path = os.path.join(cache_dir, *rel.split('/'))
            if not os.path.isfile(cache_path):
                print(f'  !! MISSING IN CACHE: {rel}')
                all_ok = False
                continue
            pkg_data = z.read(e)
            with open(cache_path, 'rb') as f:
                cache_data = f.read()
            pkg_hash = sha256_bytes(pkg_data)
            cache_hash = sha256_bytes(cache_data)
            if pkg_hash == cache_hash:
                print(f'  MATCH (raw)  {rel}')
            elif norm(pkg_data) == norm(cache_data):
                print(f'  MATCH (norm) {rel}')
            else:
                print(f'  !! MISMATCH  {rel}')
                all_ok = False
        print(f'  RESULT: {"COMPLETE + VERIFIED" if all_ok else "INCOMPLETE / MISMATCH"}')
print('=' * 70)
print('done')
