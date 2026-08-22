import os, re, hashlib, sys, json

ROOT = r"C:\Users\Owner\ora-skills"
CACHE_ROOT = r"C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin"

skills = [
    "automation-health-monitor","deal-execution","debt-management","document-assembly",
    "estoppel-request-generation","lease-abstraction-pipeline","legal-intelligence",
    "repo-architecture-review",
]

def sha256_file(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()

def norm_hash(p):
    with open(p, "rb") as f:
        data = f.read()
    try:
        text = data.decode("utf-8")
        norm = text.replace("\r\n", "\n").rstrip()
        return hashlib.sha256(norm.encode("utf-8")).hexdigest()
    except Exception:
        return None

# find cache dir for each skill: skills-plugin/<outer>/<inner>/skills/<skill>
cache_map = {}
for outer in os.listdir(CACHE_ROOT):
    outer_p = os.path.join(CACHE_ROOT, outer)
    if not os.path.isdir(outer_p):
        continue
    for inner in os.listdir(outer_p):
        skills_p = os.path.join(outer_p, inner, "skills")
        if os.path.isdir(skills_p):
            for s in os.listdir(skills_p):
                cache_map.setdefault(s, []).append(os.path.join(skills_p, s))

for s in skills:
    print(f"--- {s} ---")
    repo_md = os.path.join(ROOT, s, "SKILL.md")
    with open(repo_md, encoding="utf-8") as f:
        content = f.read()
    fm = re.match(r"^---\n(.*?)\n---\n", content, re.S)
    body = fm.group(1) if fm else ""
    desc_m = re.search(r'description:\s*"(.*?)"\s*\n\S', body + "\n$", re.S)
    # fallback: grab whole description value between description: and next top-level key
    desc_m2 = re.search(r'description:\s*"?(.*?)"?\s*\n(name:|license:|$)', body, re.S)
    desc_text = (desc_m2.group(1) if desc_m2 else "")[-200:]
    vtoks = re.findall(r"v\d+\.\d+(?:\.\d+)?[a-z]?", desc_text)
    print("repo description tail:", desc_text.strip()[-160:])
    print("repo version (last token in desc):", vtoks[-1] if vtoks else "NOT FOUND")
    print("repo description length:", len(desc_m2.group(1)) if desc_m2 else -1)

    paths = cache_map.get(s, [])
    if not paths:
        print("CACHE: not found (never installed on this device, or not yet re-imported)")
        continue
    for cp in paths:
        cache_md = os.path.join(cp, "SKILL.md")
        if not os.path.exists(cache_md):
            print(f"CACHE at {cp}: SKILL.md MISSING")
            continue
        raw_match = None
        try:
            rh = sha256_file(repo_md)
            ch = sha256_file(cache_md)
            raw_match = (rh == ch)
        except Exception as e:
            print("hash error:", e)
        norm_match = None
        if not raw_match:
            rn = norm_hash(repo_md)
            cn = norm_hash(cache_md)
            norm_match = (rn == cn)
        try:
            ctime = os.stat(cp).st_ctime
            import datetime
            ctime_s = datetime.datetime.fromtimestamp(ctime).isoformat()
        except Exception:
            ctime_s = "?"
        print(f"CACHE at {cp}")
        print(f"  raw_hash_match={raw_match} norm_match={norm_match} dir_ctime={ctime_s}")
        with open(cache_md, encoding="utf-8") as f:
            ccontent = f.read()
        cfm = re.match(r"^---\n(.*?)\n---\n", ccontent, re.S)
        cbody = cfm.group(1) if cfm else ""
        cdesc_m2 = re.search(r'description:\s*"?(.*?)"?\s*\n(name:|license:|$)', cbody, re.S)
        cdesc_text = (cdesc_m2.group(1) if cdesc_m2 else "")[-200:]
        cvtoks = re.findall(r"v\d+\.\d+(?:\.\d+)?[a-z]?", cdesc_text)
        print("  cache version (last token in desc):", cvtoks[-1] if cvtoks else "NOT FOUND")
    print()
