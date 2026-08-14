import subprocess, os, re
R = r"C:\Users\Owner\ora-skills"
RET = ["census-acs-extract", "code-debugging-optimizations", "maintenance-analytics",
       "oxford-cc-strategic-audit", "re-operations", "rent-comp"]
CACHE = r"C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills"

def git(*a):
    return subprocess.run(["git"] + list(a), capture_output=True, text=True, cwd=R).stdout

for s in RET:
    print("=" * 70)
    print("RETIRED SKILL:", s)
    print("  repo dir still present:", os.path.isdir(os.path.join(R, s)))
    print("  RUNTIME CACHE dir present:", os.path.isdir(os.path.join(CACHE, s)))
    out = git("grep", "-n", s, "--", "*.py", "*.json", "*.md", "*.ps1", "*.toml", "*.yml", "*.yaml")
    live = [l for l in out.splitlines() if not l.startswith("_archive/")]
    # classify
    tooling = [l for l in live if l.split(":")[0].startswith("tools/") or l.split(":")[0].startswith("plugins/")]
    skillrefs = [l for l in live if l.split(":")[0].endswith("SKILL.md")]
    other = [l for l in live if l not in tooling and l not in skillrefs]
    print("  -- TOOLING/PLUGIN refs (%d) [these drive automation]" % len(tooling))
    for l in tooling:
        print("     ", l[:150].encode("ascii", "replace").decode())
    print("  -- SKILL.md cross-refs (%d)" % len(skillrefs))
    for l in skillrefs[:12]:
        print("     ", l[:150].encode("ascii", "replace").decode())
    print("  -- other live refs (%d)" % len(other))
    for l in other[:12]:
        print("     ", l[:150].encode("ascii", "replace").decode())
