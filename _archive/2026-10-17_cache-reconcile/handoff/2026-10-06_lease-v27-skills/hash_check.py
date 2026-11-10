import hashlib, pathlib
R = pathlib.Path(r"C:\Users\Owner\ora-skills")
for f in ["masterlease-jurisdiction-rebase/scripts/rebase.py", "masterlease-jurisdiction-rebase/scripts/test_rebase.py",
          "masterlease-jurisdiction-rebase/scripts/ora_docx_redline.py", "masterlease-jurisdiction-rebase/config/properties.json",
          "lease-form-qc/scripts/lease_qc.py", "masterlease-jurisdiction-rebase/SKILL.md", "lease-form-qc/SKILL.md"]:
    b = (R / f).read_bytes().replace(b"\r\n", b"\n")
    print(hashlib.sha256(b).hexdigest()[:16], len(b), f)
