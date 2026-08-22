2a. **Pre-flight frontmatter gate (added v1.21).** Two defects make the platform importer reject a `.skill` with **no error text anywhere** — the Save-skill click is simply a no-op: a `description` over **1024 characters**, or a frontmatter `name` not byte-identical to its directory. `tools/package_skills.py` catches both, so this only bites on the paths where that tool cannot run — a cloud Cowork session with no Desktop Commander bridge, a hand-built `_staging` package, any `.skill` assembled without the repo. Assert it yourself there:

    ```python
    import os, re, sys
    root = sys.argv[1].rstrip("/\\"); want = os.path.basename(root)
    b = re.match(r"^---\n(.*?)\n---\n",
                 open(os.path.join(root, "SKILL.md"), encoding="utf8").read(), re.S).group(1)
    nm = re.search(r"^name:\s*(\S+)\s*$", b, re.M).group(1)
    d  = re.search(r'^description:\s*"?(.*?)"?\s*$', b, re.M | re.S).group(1)
    bad = ([f"name {nm!r} != dir {want!r}"] if nm != want else []) + \
          ([f"description {len(d)}/1024"] if len(d) > 1024 else [])
    print(("FAIL: " + "; ".join(bad)) if bad else f"OK name={want} description={len(d)}/1024")
    sys.exit(1 if bad else 0)
    ```

    A hand-built archive also skips the entry rules step 3 delegates to the packager — assert those too: forward-slash entries only (backslash → importer rejects, APPNOTE 4.4.17.1), no directory records, `<skill>/SKILL.md` at the expected path. `zipfile.ZipInfo` with explicit arcnames satisfies all three; `shutil.make_archive` and `Compress-Archive` do not. **Report `description N/1024` and the `name`/dir pair rather than a verdict**, so a silent rejection downstream is ruled out by reading the report instead of rebuilding.

    Authoring a skill cloud-side does not exempt step 1: the repo is still the basis. Read `C:\Users\Owner\ora-skills\<skill>\SKILL.md` over the bridge before editing — never the `~/.claude/skills/synced/` mirror, which serves the last *imported* version and silently lags any repo commit not yet re-installed.

