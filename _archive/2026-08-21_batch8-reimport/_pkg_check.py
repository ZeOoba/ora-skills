import zipfile, hashlib, os, re

STAGE = r"C:\Users\Owner\ora-skills\_staging\2026-08-21_batch8-reimport"
ROOT = r"C:\Users\Owner\ora-skills"

skills = [
    "automation-health-monitor","deal-execution","debt-management","document-assembly",
    "estoppel-request-generation","lease-abstraction-pipeline","legal-intelligence",
    "repo-architecture-review",
]

def sha256_bytes(b):
    return hashlib.sha256(b).hexdigest()

def norm_hash(b):
    try:
        t = b.decode("utf-8").replace("\r\n", "\n").rstrip()
        return hashlib.sha256(t.encode("utf-8")).hexdigest()
    except Exception:
        return None

for s in skills:
    print(f"--- {s} ---")
    zp = os.path.join(STAGE, f"{s}.skill")
    with zipfile.ZipFile(zp) as z:
        names = z.namelist()
        bad_slash = [n for n in names if "\\" in n]
        dirs = [n for n in names if n.endswith("/")]
        print("entries:", names)
        print("backslash entries (should be empty):", bad_slash)
        print("directory records (should be empty):", dirs)
        skmd_name = f"{s}/SKILL.md"
        if skmd_name not in names:
            print("MISSING expected SKILL.md at", skmd_name)
            continue
        pkg_bytes = z.read(skmd_name)
        repo_path = os.path.join(ROOT, s, "SKILL.md")
        with open(repo_path, "rb") as f:
            repo_bytes = f.read()
        raw_match = sha256_bytes(pkg_bytes) == sha256_bytes(repo_bytes)
        nm = raw_match or (norm_hash(pkg_bytes) == norm_hash(repo_bytes))
        print(f"packaged SKILL.md vs repo SKILL.md: raw_match={raw_match} norm_match_ok={nm}")
        # frontmatter checks on packaged copy
        text = pkg_bytes.decode("utf-8")
        fm = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        body = fm.group(1) if fm else ""
        name_m = re.search(r"(?m)^name:\s*(\S+)\s*$", body)
        desc_m = re.search(r'description:\s*"?(.*?)"?\s*\n(name:|license:|$)', body, re.S)
        dtext = desc_m.group(1) if desc_m else ""
        print("packaged name:", name_m.group(1) if name_m else "NOT FOUND", " (dir:", s, ")")
        print("packaged description length:", len(dtext), "/1024")
    print()
