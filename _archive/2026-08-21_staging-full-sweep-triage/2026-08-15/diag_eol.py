import os
SCRATCH = r"C:\Users\Owner\ora-skills\_staging\2026-08-15"

for name in ["head_base.md", "my_entry.txt"]:
    p = os.path.join(SCRATCH, name)
    with open(p, "rb") as f:
        b = f.read()
    crlf = b.count(b"\r\n")
    lf = b.count(b"\n")
    lone_cr = b.count(b"\r") - crlf
    print(name, "bytes", len(b), "CRLF", crlf, "total-LF", lf, "lone-CR", lone_cr)
