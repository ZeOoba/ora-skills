import zipfile, os
SKILL_PATH = r"C:\Users\Owner\ora-skills\_staging\2026-08-22_reimport-batch5\register-scheduled-task.skill"
zf = zipfile.ZipFile(SKILL_PATH)
b = zf.read("register-scheduled-task/SKILL.md")
print("First 400 bytes repr:")
print(repr(b[:400]))
print("\nHas BOM:", b[:3] == b'\xef\xbb\xbf')
print("CRLF count in first 400:", b[:400].count(b'\r\n'))
print("LF count in first 400:", b[:400].count(b'\n'))
