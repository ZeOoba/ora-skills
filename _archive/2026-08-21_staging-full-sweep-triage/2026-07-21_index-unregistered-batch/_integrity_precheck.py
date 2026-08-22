import zipfile, hashlib, os, sys

REPO = r'C:\Users\Owner\ora-skills'
STAGE = r'C:\Users\Owner\ora-skills\_staging\2026-07-21_index-unregistered-batch'
SHARED_DEP_CONSUMERS = {'acquisition-underwriting', 'daily-brief', 'deal-comparison', 'market-monitor', 'rent-comp'}

def norm(b):
    return b.replace(b'\r\n', b'\n').rstrip()

skills = sys.argv[1:]

for skill in skills:
    print('=' * 70)
    print(skill)
    skill_path = os.path.join(STAGE, skill + '.skill')
    if not os.path.exists(skill_path):
        print('  [FAIL] .skill file missing at', skill_path)
        continue
    print('  [OK] exists:', skill_path)

    repo_dir = os.path.join(REPO, skill)
    if not os.path.isdir(repo_dir):
        print('  [FAIL] repo skill dir missing:', repo_dir)
        continue

    expected = []
    for root, dirs, files in os.walk(repo_dir):
        for f in files:
            if f == 'PACKAGING-NOTE.md':
                continue
            rel = os.path.relpath(os.path.join(root, f), repo_dir).replace('\\', '/')
            expected.append(skill + '/' + rel)
    expected_set = set(expected)
    if skill in SHARED_DEP_CONSUMERS:
        expected_set.add(skill + '/target-markets.json')

    with zipfile.ZipFile(skill_path) as z:
        entries = z.namelist()
        bad_slash = [e for e in entries if '\\' in e]
        print('  entries:', entries)
        if bad_slash:
            print('  [FAIL] backslash entries found:', bad_slash)
        else:
            print('  [OK] all entries forward-slash')

        entry_set = set(entries)
        missing = expected_set - entry_set
        extra = entry_set - expected_set
        if missing:
            print('  [WARN] expected-but-missing:', missing)
        if extra:
            print('  [INFO] extra-in-package:', extra)
        if not missing:
            print('  [OK] expected file set present')

        skillmd_entry = skill + '/SKILL.md'
        with z.open(skillmd_entry) as fh:
            pkg_skillmd = fh.read()
        with open(os.path.join(repo_dir, 'SKILL.md'), 'rb') as fh:
            repo_skillmd = fh.read()
        if pkg_skillmd == repo_skillmd:
            print('  [OK] SKILL.md byte-identical to repo')
        elif norm(pkg_skillmd) == norm(repo_skillmd):
            print('  [OK] SKILL.md EOL-normalized match (raw CRLF/LF diff only)')
        else:
            print('  [FAIL] SKILL.md DRIFT vs repo -- STOP, reject to Entry point A')

        if skill in SHARED_DEP_CONSUMERS:
            dep_entry = skill + '/target-markets.json'
            dep_repo_path = os.path.join(REPO, 'target-markets.json')
            if dep_entry in entry_set:
                with z.open(dep_entry) as fh:
                    pkg_dep = fh.read()
                with open(dep_repo_path, 'rb') as fh:
                    repo_dep = fh.read()
                if pkg_dep == repo_dep:
                    print('  [OK] target-markets.json byte-identical to repo root')
                elif norm(pkg_dep) == norm(repo_dep):
                    print('  [OK] target-markets.json EOL-normalized match')
                else:
                    print('  [FAIL] target-markets.json DRIFT vs repo root -- STOP, check direction')
            else:
                print('  [FAIL] shared-dep consumer but target-markets.json NOT in package')
