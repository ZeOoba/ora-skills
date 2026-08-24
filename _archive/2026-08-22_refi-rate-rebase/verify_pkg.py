import zipfile, hashlib, io, os
pkg = r"C:\Users\Owner\ora-skills\_staging\2026-08-22\acquisition-underwriting.skill"
repo = r"C:\Users\Owner\ora-skills\acquisition-underwriting"
root = r"C:\Users\Owner\ora-skills"

def norm(b):
    return b.replace(b"\r\n", b"\n").rstrip()

z = zipfile.ZipFile(pkg)
names = z.namelist()
bad = [n for n in names if "\\" in n]
print("entries:", len(names), "| backslash entries:", len(bad))
ok = True
for n in names:
    rel = n.split("/", 1)[1]
    if rel == "target-markets.json":
        disk = os.path.join(root, rel)
    else:
        disk = os.path.join(repo, rel)
    if not os.path.exists(disk):
        print("MISSING ON DISK:", rel); ok = False; continue
    a = hashlib.sha256(norm(z.read(n))).hexdigest()
    b = hashlib.sha256(norm(open(disk, "rb").read())).hexdigest()
    if a != b:
        print("MISMATCH:", rel); ok = False
print("PACKAGE MATCHES REPO:", ok)
body = z.read("acquisition-underwriting/SKILL.md").decode("utf8")
print("refi line contains 6.50%:", "fixed rate **6.50%**" in body)
print("band 6.25-6.75 present:", "band 6.25\u20136.75%" in body)
print("residual 7.00% refi default:", "fixed rate **7.00%**" in body)
print("ic-memo 6.50% fixed:", "6.50% fixed" in z.read("acquisition-underwriting/references/ic-memo-structure.md").decode("utf8"))
