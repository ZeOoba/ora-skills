import re, os, hashlib

P = r"C:\Users\Owner\ora-skills\package-and-stage-skill\SKILL.md"
S = r"C:\Users\Owner\ora-skills\_staging\2026-08-17"
raw = open(P, "rb").read()
crlf = b"\r\n" in raw
t = raw.replace(b"\r\n", b"\n").decode("utf8")
before = len(t)

assert "- v1.20 (2026-08-16: size fix" in t, "repo is not at the expected v1.20 baseline"
assert "2a. **Pre-flight" not in t, "step 2a already present"

DASH = r"[\u2014\u2013-]"
SUBS = [
 (r"Hash-prechecks the cache for content; short-circuits only on a corroborating main\.log install, never a bare hash match\.",
  "Hash-prechecks cache content; short-circuits only on a corroborating main.log install, never a bare hash."),
 (r"Stages it in session outputs and surfaces the Save-skill installer\.",
  "Stages it and surfaces the Save-skill installer."),
 (r"Does NOT register\s*" + DASH + r"\s*Gabriel clicks Save skill; cache re-syncs after import\.",
  "Does NOT register \u2014 Gabriel clicks Save skill."),
 (r"Plugin-bundled skills rebuild the plugin, not standalone\.",
  "Plugin-bundled skills rebuild the plugin."),
 (r"Never reuse a pre-staged `_staging` draft without a fresh verify\. v1\.20",
  "Pre-flight gate asserts name==dir and description <=1024 before packaging \u2014 both fail SILENTLY at import. "
  "Never reuse a pre-staged draft unverified. v1.21"),
]
for pat, rep in SUBS:
    t, n = re.subn(pat, rep.replace("\\", "\\\\"), t, count=1)
    if n != 1:
        raise SystemExit("ABORT: clause not matched -> " + pat[:60])

step2a = open(os.path.join(S, "step2a_tight.md"), encoding="utf8").read()
m = re.search(r"^3\. \*\*Package " + DASH + r" sanctioned tool ONLY\.\*\*", t, re.M)
assert m, "step 3 anchor not found"
t = t[:m.start()] + step2a + t[m.start():]

OLD_DONE = "packager exited 0 with `description N/1024 OK` + `N entries OK` + a forward-slash entry list"
assert t.count(OLD_DONE) == 1, "Done= anchor not found"
t = t.replace(OLD_DONE,
    "pre-flight frontmatter gate run and its `description N/1024` + `name`/dir pair REPORTED before packaging, "
    "on every path including cloud-authored and hand-built packages \u00b7 packager exited 0 with "
    "`description N/1024 OK` + `N entries OK` + a forward-slash entry list", 1)

entry = open(os.path.join(S, "changelog_v121.md"), encoding="utf8").read().strip() + "\n"
CL = "## Changelog\n\n"
assert t.count(CL) == 1
t = t.replace(CL, CL + entry, 1)

fm = re.match(r"^---\n(.*?)\n---\n", t, re.S).group(1)
nm = re.search(r"^name:\s*(\S+)\s*$", fm, re.M).group(1)
d = re.search(r"^description:\s*(.*)$", fm, re.M).group(1)
assert nm == "package-and-stage-skill", nm
assert len(d) <= 1024, "description %d/1024" % len(d)
assert "\n" not in d

open(P, "wb").write((t.replace("\n", "\r\n") if crlf else t).encode("utf8"))
print("OK  name=%s  description=%d/1024" % (nm, len(d)))
print("chars %d -> %d  (%+d)" % (before, len(t), len(t) - before))
print("lfnorm sha256:", hashlib.sha256(t.encode("utf8")).hexdigest()[:16])
