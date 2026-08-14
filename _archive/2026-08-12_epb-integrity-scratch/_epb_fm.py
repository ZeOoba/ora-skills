import zipfile, os, re
STAGE = r"C:\Users\Owner\ora-skills\_staging\2026-08-12_pending-reimport-batch"
SK = ["tax-appeal", "fleet-advisory-remediation", "daily-brief", "deal-comparison", "market-monitor"]
for s in SK:
    p = os.path.join(STAGE, s + ".skill")
    z = zipfile.ZipFile(p)
    raw = z.read(s + "/SKILL.md")
    t = raw.decode("utf-8")
    fm = t.split("---")[1]
    nm = re.search(r"^name:\s*(.+)$", fm, re.M).group(1).strip()
    de = re.search(r"^description:\s*(.+)$", fm, re.M).group(1).strip()
    print("%-28s name_ok=%-5s desc=%4d/1024 utf8bom=%-5s crlf=%-5s firstbytes=%r" % (
        s, nm == s, len(de), raw[:3] == b"\xef\xbb\xbf", b"\r\n" in raw, raw[:5]))
    print("      zip: %s" % [(i.filename, i.compress_type, i.create_system) for i in z.infolist()])
    print("      testzip:", z.testzip())
