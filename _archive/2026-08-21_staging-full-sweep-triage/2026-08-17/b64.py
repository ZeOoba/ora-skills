import base64, hashlib, io
p = r"C:\Users\Owner\ora-skills\_staging\2026-08-17\register-scheduled-task.skill"
b = open(p, "rb").read()
print("BYTES", len(b))
print("SHA256", hashlib.sha256(b).hexdigest())
e = base64.b64encode(b).decode()
io.open(r"C:\Users\Owner\ora-skills\_staging\2026-08-17\rst.b64", "w", encoding="ascii", newline="\n").write(
    "\n".join(e[i:i+200] for i in range(0, len(e), 200)))
print("B64CHARS", len(e))
