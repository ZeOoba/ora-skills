import zipfile, hashlib, re, os, json, sys

PKG = r"C:\Users\Owner\ora-skills\_staging\2026-08-21_insurance-renewal-review-desclen-fix\insurance-renewal-review.skill"
REPO_DIR = r"C:\Users\Owner\ora-skills\insurance-renewal-review"
CACHE_DIR = r"C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills\insurance-renewal-review"
EXPECTED_SHA256 = "4678af968a5fe3e39af61d1bb7d49c83340fc35c3a0d5c257ae57cc9e9f5e3e2"

out = {}

with open(PKG, "rb") as f:
    pkg_bytes = f.read()
pkg_sha = hashlib.sha256(pkg_bytes).hexdigest()
out["package_sha256"] = pkg_sha
out["expected_sha256"] = EXPECTED_SHA256
out["sha256_match"] = (pkg_sha == EXPECTED_SHA256)

zf = zipfile.ZipFile(PKG)
entries = zf.namelist()
out["entries"] = entries
out["backslash_entries"] = [e for e in entries if "\\" in e]
out["dir_records"] = [e for e in entries if e.endswith("/")]

def norm(b):
    return b.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

def sha_norm(b):
    return hashlib.sha256(norm(b)).hexdigest()

results = {}
for entry in entries:
    if entry.endswith("/"):
        continue
    data = zf.read(entry)
    rel = entry.split("/", 1)[1] if "/" in entry else entry
    repo_path = os.path.join(REPO_DIR, rel.replace("/", os.sep))
    cache_path = os.path.join(CACHE_DIR, rel.replace("/", os.sep))
    entry_result = {"pkg_sha_raw": hashlib.sha256(data).hexdigest(), "pkg_sha_norm": sha_norm(data)}
    if os.path.exists(repo_path):
        with open(repo_path, "rb") as f:
            rdata = f.read()
        entry_result["repo_sha_raw"] = hashlib.sha256(rdata).hexdigest()
        entry_result["repo_sha_norm"] = sha_norm(rdata)
        entry_result["pkg_vs_repo_norm_match"] = (entry_result["pkg_sha_norm"] == entry_result["repo_sha_norm"])
    else:
        entry_result["repo_missing"] = True
    if os.path.exists(cache_path):
        with open(cache_path, "rb") as f:
            cdata = f.read()
        entry_result["cache_sha_norm"] = sha_norm(cdata)
        entry_result["pkg_vs_cache_norm_match"] = (entry_result["pkg_sha_norm"] == entry_result["cache_sha_norm"])
        if "repo_sha_norm" in entry_result:
            entry_result["repo_vs_cache_norm_match"] = (entry_result["repo_sha_norm"] == entry_result["cache_sha_norm"])
    else:
        entry_result["cache_missing"] = True
    results[entry] = entry_result

out["entry_comparisons"] = results

skill_entry = [e for e in entries if e.endswith("SKILL.md")][0]
top = skill_entry.split("/")[0]
out["top_level_dir"] = top
out["name_matches_dirname"] = (top == "insurance-renewal-review")
skill_bytes = zf.read(skill_entry)
skill_text = skill_bytes.decode("utf-8-sig").replace("\r\n", "\n")
m = re.match(r"^---\n(.*?)\n---\n", skill_text, re.S)
if m is None:
    out["frontmatter_parse_error"] = skill_text[:200]
else:
    fm = m.group(1)
    nm = re.search(r"^name:\s*(\S+)\s*$", fm, re.M).group(1)
    dm = re.search(r'^description:\s*"?(.*?)"?\s*$', fm, re.M | re.S)
    desc = dm.group(1)
    out["frontmatter_name"] = nm
    out["frontmatter_name_matches_dir"] = (nm == top)
    out["description_len"] = len(desc)
    out["description_under_1024"] = len(desc) <= 1024
    out["description_is_940"] = (len(desc) == 940)
    out["description_tail"] = desc[-120:]

print(json.dumps(out, indent=2))
