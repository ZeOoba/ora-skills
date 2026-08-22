import zipfile, hashlib, os, sys

STAGING = r'C:\Users\Owner\ora-skills\_staging\2026-08-17_item1-reimport-prep'
REPO = r'C:\Users\Owner\ora-skills'

PACKAGES = {
    'daily-brief': os.path.join(STAGING, 'daily-brief.skill'),
    'ora-setup-audit': os.path.join(STAGING, 'ora-setup-audit.skill'),
    'register-scheduled-task': os.path.join(STAGING, 'register-scheduled-task.skill'),
}

SHARED_ROOT_DEPS_CONSUMERS = {'daily-brief'}  # target-markets.json injected from repo root

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def norm(b):
    text = b.decode('utf-8', errors='replace').replace('\r\n', '\n')
    return text.rstrip()

for skill, pkg_path in PACKAGES.items():
    print('=' * 70)
    print(skill, '->', pkg_path)
    if not os.path.isfile(pkg_path):
        print('  MISSING PACKAGE FILE')
        continue
    with zipfile.ZipFile(pkg_path) as z:
        entries = z.namelist()
        print('  entries:')
        bad_slash = []
        for e in entries:
            print('   ', e)
            if '\\' in e:
                bad_slash.append(e)
        if bad_slash:
            print('  !! BACKSLASH ENTRIES FOUND:', bad_slash)
        else:
            print('  OK: all forward-slash entries')

        expected_root = f'{skill}/SKILL.md'
        if expected_root not in entries:
            print(f'  !! MISSING EXPECTED ROOT ENTRY {expected_root}')
        else:
            print(f'  OK: {expected_root} present')

        # hash-compare every entry (except pure dir markers) against repo copy
        for e in entries:
            if e.endswith('/'):
                continue
            data = z.read(e)
            pkg_hash = sha256_bytes(data)
            # map zip entry path (skill/rest...) to repo path
            parts = e.split('/')
            assert parts[0] == skill, f'unexpected top-level dir in entry {e}'
            rel = parts[1:]
            if rel and rel[0] == 'target-markets.json':
                repo_path = os.path.join(REPO, 'target-markets.json')
            else:
                repo_path = os.path.join(REPO, skill, *rel)
            if not os.path.isfile(repo_path):
                print(f'  !! entry {e}: NO REPO COUNTERPART at {repo_path}')
                continue
            with open(repo_path, 'rb') as f:
                repo_data = f.read()
            repo_hash = sha256_bytes(repo_data)
            if repo_hash == pkg_hash:
                print(f'  MATCH (raw)   {e}')
            else:
                if norm(repo_data) == norm(data):
                    print(f'  MATCH (norm)  {e}  [raw differs, EOL-normalized matches]')
                else:
                    print(f'  !! MISMATCH   {e}  repo_hash={repo_hash[:12]} pkg_hash={pkg_hash[:12]} -- REAL DRIFT')
print('=' * 70)
print('done')
