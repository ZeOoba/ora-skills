import hashlib, zipfile, pathlib, sys
sys.path.insert(0, r"C:\Users\Owner\ora-skills\tools")
import package_skills as ps
R = pathlib.Path(r"C:\Users\Owner\ora-skills")
z = zipfile.ZipFile(R / r"_staging\handoff\2026-10-06_lease-v27-skills\lease-form-qc.skill")
n = lambda b: hashlib.sha256(b.replace(b"\r\n", b"\n")).hexdigest()[:16]
print("pkg ora_doc_qc   ", n(z.read("lease-form-qc/scripts/ora_doc_qc.py")))
print("repo tools copy  ", n((R / "tools/ora_doc_qc.py").read_bytes()))
for f in ["SKILL.md", "scripts/lease_qc.py"]:
    print(f, n(z.read("lease-form-qc/" + f)) == n((R / "lease-form-qc" / f).read_bytes()))
print("SHARED_ROOT_DEPS:", getattr(ps, "SHARED_ROOT_DEPS", None))
