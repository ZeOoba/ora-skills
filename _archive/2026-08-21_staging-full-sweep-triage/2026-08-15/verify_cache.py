import zipfile, hashlib, os, json

skills = ['acquisition-underwriting','daily-brief','deal-comparison','deal-execution',
          'lease-abstraction-pipeline','market-monitor','owner-outreach',
          'parcel-data-recovery','solar-lease-underwriting','submarket-spatial-analysis',
          'tax-appeal','tenant-email']

staging = r'C:\Users\Owner\ora-skills\_staging\2026-08-15'
cache_root = (r'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions'
              r'\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350'
              r'\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills')

def norm_hash(b):
    return hashlib.sha256(b.replace(b'\r\n', b'\n')).hexdigest()

report = {}
for sk in skills:
    zpath = os.path.join(staging, sk + '.skill')
    with zipfile.ZipFile(zpath) as z:
        entries = {n[len(sk)+1:]: z.read(n) for n in z.namelist() if not n.endswith('/')}
    missing = []
    mismatched = []
    for rel, content in entries.items():
        cache_path = os.path.join(cache_root, sk, rel.replace('/', os.sep))
        if not os.path.isfile(cache_path):
            missing.append(rel)
            continue
        with open(cache_path, 'rb') as f:
            cache_content = f.read()
        if norm_hash(content) != norm_hash(cache_content):
            mismatched.append(rel)
    report[sk] = {'expected_files': len(entries), 'missing': missing, 'mismatched': mismatched}

print(json.dumps(report, indent=2))
