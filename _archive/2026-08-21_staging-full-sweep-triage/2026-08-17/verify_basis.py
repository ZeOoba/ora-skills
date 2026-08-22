import hashlib, os
p = r"C:\Users\Owner\ora-skills\package-and-stage-skill\SKILL.md"
b = open(p, "rb").read()
n = b.replace(b"\r\n", b"\n")
print("bytes  ", len(b))
print("raw    ", hashlib.sha256(b).hexdigest())
print("lfnorm ", hashlib.sha256(n).hexdigest())
t = n.decode("utf8")
i = t.find("## Changelog")
print("top changelog entry:", t[i:i+400].split("\n")[2][:70])
print("laq dir present:", os.path.isdir(r"C:\Users\Owner\ora-skills\listing-agreement-qc"))
