import zipfile, hashlib, os, sys

STAGE = r'C:\Users\Owner\ora-skills\_staging\2026-07-21_index-unregistered-batch'
CACHE_ROOT = r'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'

def norm(b):
    return b.replace(b'\r\n', b'\n').rstrip()

def sha(b):
    return hashlib.sha256(b).hexdigest()

skills = sys.argv[1:]
results = {}

for skill in skills:
    skill_path = os.path.join(STAGE, skill + '.skill')
    cache_dir = os.path.join(CACHE_ROOT, skill)
    print('=' * 70)
    print(skill)
    if not os.path.isdir(cache_dir):
        print('  [NOT INSTALLED] no runtime cache dir at', cache_dir)
        results[skill] = 'NOT_INSTALLED'
        continue

    with zipfile.ZipFile(skill_path) as z:
        pkg_entries = {e[len(skill) + 1:]: e for e in z.namelist() if e != skill + '/'}
        missing = []
        mismatched = []
        for rel, entry in pkg_entries.items():
            cache_file = os.path.join(cache_dir, rel.replace('/', os.sep))
            if not os.path.exists(cache_file):
                missing.append(rel)
                continue
            with z.open(entry) as fh:
                pkg_bytes = fh.read()
            with open(cache_file, 'rb') as fh:
                cache_bytes = fh.read()
            if pkg_bytes == cache_bytes or norm(pkg_bytes) == norm(cache_bytes):
                continue
            mismatched.append(rel)

        # also check for extra files present in cache but not in package (informational)
        cache_files = []
        for root, dirs, files in os.walk(cache_dir):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), cache_dir).replace('\\', '/')
                cache_files.append(rel)
        extra = set(cache_files) - set(pkg_entries.keys())

        if missing:
            print('  [FAIL] missing in cache:', missing)
            results[skill] = 'MISSING_FILES'
        elif mismatched:
            print('  [FAIL] content mismatch (stale cache):', mismatched)
            results[skill] = 'STALE'
        else:
            print('  [OK] all packaged files present and content-identical in runtime cache')
            results[skill] = 'INSTALLED_VERIFIED'
        if extra:
            print('  [INFO] extra files in cache not in package:', extra)

print()
print('=' * 70)
print('SUMMARY')
for s, r in results.items():
    print(f'  {s}: {r}')
