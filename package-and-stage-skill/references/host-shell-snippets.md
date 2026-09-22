# package-and-stage-skill — Host-shell & fallback-checker snippets

Copy-paste snippets and their full justification, referenced from `SKILL.md` steps 2a and 3 — original wording, verbatim, extracted 2026-09-22. Read the section `SKILL.md` points at before running the corresponding step by hand.

## Pre-flight frontmatter gate snippet (step 2a)

2a. **Pre-flight frontmatter gate (added v1.21).** Two defects make the platform importer reject a `.skill` with **no error text anywhere** — the Save-skill click is simply a no-op: a `description` over **1024 characters**, or a frontmatter `name` not byte-identical to its directory. `tools/package_skills.py` catches both, so this only bites on the paths where that tool cannot run — a cloud Cowork session with no Desktop Commander bridge, a hand-built `_staging` package, any `.skill` assembled without the repo. Assert it yourself there:

    ```python
    import os, re, sys
    root = sys.argv[1].rstrip("/\\"); want = os.path.basename(root)
    b = re.match(r"^---\n(.*?)\n---\n",
                 open(os.path.join(root, "SKILL.md"), encoding="utf8").read(), re.S).group(1)
    nm = re.search(r"^name:\s*(\S+)\s*$", b, re.M).group(1).strip("'\"")   # quotes are legal
    d  = re.search(r'^description:\s*"?(.*?)"?\s*$', b, re.M | re.S).group(1)
    bad = ([f"name {nm!r} != dir {want!r}"] if nm != want else []) + \
          ([f"description {len(d)}/1024"] if len(d) > 1024 else [])
    print(("FAIL: " + "; ".join(bad)) if bad else f"OK name={want} description={len(d)}/1024")
    sys.exit(1 if bad else 0)
    ```

    **`.strip("'\"")` in the snippet above is load-bearing.** `name: "debt-management"` is a
    legal quoted YAML scalar and installs fine; `package_skills.py` strips quotes before
    comparing (its line 179). Through v1.26 this snippet did NOT, so it reported a false
    `NAME MISMATCH` on the two skills that quote their name — `debt-management` and
    `masterlease-revision-cycle` — both of which are installed and working. A fallback
    checker that disagrees with the real packager is worse than no fallback checker.
    A hand-built archive also skips the entry rules step 3 delegates to the packager — assert those too: forward-slash entries only (backslash → importer rejects, APPNOTE 4.4.17.1), no directory records, `<skill>/SKILL.md` at the expected path. `zipfile.ZipInfo` with explicit arcnames satisfies all three; `shutil.make_archive` and `Compress-Archive` do not. **Report `description N/1024` and the `name`/dir pair rather than a verdict**, so a silent rejection downstream is ruled out by reading the report instead of rebuilding.

## Description budget (step 2a)

    **Check the budget BEFORE editing a description, not after (v1.27).** Run
    `python tools/description_budget.py <skill>` — it reports `N/1024` and remaining headroom,
    and `--budget <chars>` exits non-zero unless the skill can absorb an edit of that size.
    Run with no arguments it ranks every skill tightest-first. The 1024 ceiling is not
    theoretical: `settlement-basis-extraction` sits at 1019 (**5 characters of headroom**),
    `package-and-stage-skill` at 1015, and six more are under 30. Learning this at package
    time costs an edit-trim-recheck cycle every time (twice in one session, 2026-08-22).

## Host-shell discipline (step 3)

3. **Package — sanctioned tool ONLY.** Via Desktop Commander on Windows: `python tools\package_skills.py "<session outputs dir>" <skill ...>`. NEVER PowerShell `Compress-Archive` (writes backslash zip entries → importer rejects per zip-spec APPNOTE 4.4.17.1; ruling 2026-06-11). The tool validates frontmatter (`name` == dir, `description` ≤ 1024 chars), scans named-count headers across every `*.md`, and asserts forward-slash entries. A non-zero exit is a real defect — surface it verbatim, do not work around it. **Host-shell discipline — SKILL-WIDE, not just this step.** Every Desktop Commander PowerShell invocation ANYWHERE in this skill — packaging here in step 3, but just as much the verification/hash-compare, `main.log` reads, `append-event-log.py`, and `pending_reimport.py clear` calls in step 7 — that uses `$` variables or spans multiple statements goes in a `.ps1` file run via `powershell -NoProfile -ExecutionPolicy Bypass -File <path>`, never an inline `powershell -Command` one-shot. `$` tokens are stripped in transit and the command arrives mangled or throws a parser error. Default to the `.ps1`-file pattern for every DC PowerShell call in this skill; do not attempt inline first and fall back only on error. Full incident (recurred 5 times across two sessions before being scoped skill-wide): Changelog v1.18(b).
   **Canonical invocation (copy this, don't re-derive it — added 2026-08-21).** Write the script with Desktop Commander `write_file` to an absolute path under the repo or `_staging` (never a temp path the host can't resolve), then run it:
   Inside the `.ps1`, use one `Set-Location` line (or fully-qualified paths) instead of chaining commands — Windows PowerShell 5.1, the default host shell here, has no `&&` statement separator and throws `InvalidEndOfLine` on `cmd1 && cmd2` (confirmed live 2026-08-21). `$` variables and multi-statement logic are unrestricted inside the file.

## Start-Process -ArgumentList (step 3)

   **`Start-Process -ArgumentList` splits on spaces — and EVERY ORA root has spaces (v1.27).** The array form silently mangles paths:
   ```powershell
   # WRONG -- "C:\Users\Owner\OneDrive - Oxford Capital Partners\Business" arrives as
   # three arguments, and the script runs against "C:\Users\Owner\OneDrive"
   Start-Process python -ArgumentList @($script, $root, "--quiet")

   # RIGHT -- one string, every path quoted inside it
   $a = '"{0}" "{1}" --quiet' -f $script, $root
   Start-Process python -ArgumentList $a -RedirectStandardOutput $out -NoNewWindow
   ```
   This is the same failure class as the inline-`-Command` `$`-stripping rule above: the command is not rejected, it is quietly rewritten. **It does not error — it succeeds against the wrong target and prints a confident result.** A sweep that reported `1 workbook(s) | 0 dead-or-partial` had walked `C:\Users\Owner\OneDrive`, not the Business tree; it took two occurrences in one session (2026-08-22) to spot, because both looked like clean runs. Sanity-check the item count any detached job reports before believing its verdict.
