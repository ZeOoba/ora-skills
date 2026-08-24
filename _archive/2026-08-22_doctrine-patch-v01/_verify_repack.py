import zipfile
z = zipfile.ZipFile(r"C:\Users\Owner\ora-skills\_staging\2026-08-22_doctrine-patch-v01\acquisition-underwriting.skill")
d = z.read("acquisition-underwriting/SKILL.md").decode("utf8")
r = open(r"C:\Users\Owner\ora-skills\acquisition-underwriting\SKILL.md", encoding="utf8").read()
print("match:", d == r)
print("\n".join(d.splitlines()[:6]))
