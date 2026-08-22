import hashlib, os, re, zipfile

pkg_path = r"C:\Users\Owner\ora-skills\_staging\2026-08-21_insurance-renewal-review-desclen-fix\insurance-renewal-review.skill"
repo_dir = r"C:\Users\Owner\ora-skills\insurance-renewal-review"

with open(pkg_path, 'rb') as f:
    data = f.read()
print("PACKAGE_SHA256:", hashlib.sha256(data).hexdigest())
print("PACKAGE_SIZE:", len(data))

zf = zipfile.ZipFile(pkg_path)
entries = zf.namelist()
print("ENTRIES:")
for e in entries:
    flag = "BACKSLASH" if "\\" in e else "ok"
    print(" ", e, flag)

def normalize(b):
    return b.replace(b'\r\n', b'\n').rstrip()

for e in entries:
    if e.endswith('/'):
        continue
    content = zf.read(e)
    rel = e.split('/', 1)[1] if '/' in e else e
    repo_file = os.path.join(repo_dir, rel.replace('/', os.sep))
    if os.path.exists(repo_file):
        with open(repo_file, 'rb') as f:
            repo_content = f.read()
        raw_match = content == repo_content
        norm_match = normalize(content) == normalize(repo_content)
        print("PKG-vs-REPO", rel, "raw_match=", raw_match, "norm_match=", norm_match)
    else:
        print("PKG-vs-REPO", rel, "REPO FILE MISSING at", repo_file)

skill_md = zf.read('insurance-renewal-review/SKILL.md').decode('utf-8')
m = re.match(r"^---\n(.*?)\n---\n", skill_md, re.S)
body = m.group(1)
nm = re.search(r"^name:\s*(\S+)\s*$", body, re.M).group(1)
dm = re.search(r'^description:\s*"?(.*?)"?\s*$', body, re.M | re.S)
desc = dm.group(1)
print("NAME:", nm)
print("DESC_LEN:", len(desc))
print("NAME_MATCHES_DIR:", nm == os.path.basename(repo_dir))

def desc_len_of(text):
    mm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not mm:
        return -1
    bb = mm.group(1)
    ddm = re.search(r'^description:\s*"?(.*?)"?\s*$', bb, re.M | re.S)
    return len(ddm.group(1)) if ddm else -1

appdata = os.environ['APPDATA']
cache_root = os.path.join(appdata, 'Claude', 'local-agent-mode-sessions', 'skills-plugin')
cache_dirs = []
for root, dirs, files in os.walk(cache_root):
    if os.path.basename(root) == 'insurance-renewal-review':
        cache_dirs.append(root)
print("CACHE_ROOT_EXISTS:", os.path.isdir(cache_root))
print("CACHE_DIRS:", cache_dirs)

for d in cache_dirs:
    st = os.stat(d)
    print("CACHE_DIR_BASELINE", d, "ctime=", st.st_ctime, "mtime=", st.st_mtime)
    for rel in ['SKILL.md', os.path.join('references', 'ocr-and-extraction-checklist.md')]:
        cache_file = os.path.join(d, rel)
        repo_file = os.path.join(repo_dir, rel)
        ce = os.path.exists(cache_file)
        re_ = os.path.exists(repo_file)
        if ce and re_:
            with open(cache_file, 'rb') as f:
                cf = f.read()
            with open(repo_file, 'rb') as f:
                rf = f.read()
            extra = ""
            if rel == 'SKILL.md':
                extra = " cache_desc_len=" + str(desc_len_of(cf.decode('utf-8', 'ignore')))
            print("CACHE-vs-REPO", rel, "in", d, "raw=", cf == rf, "norm=", normalize(cf) == normalize(rf), extra)
        else:
            print("CACHE-vs-REPO", rel, "in", d, "missing cache_exists=", ce, "repo_exists=", re_)
