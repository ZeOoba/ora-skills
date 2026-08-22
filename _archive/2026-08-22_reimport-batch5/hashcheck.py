import hashlib
p = r"C:\Users\Owner\ora-skills\_staging\2026-08-22_reimport-batch5\register-scheduled-task.skill"
h = hashlib.sha256()
with open(p, "rb") as f:
    h.update(f.read())
print("SHA256:", h.hexdigest())
