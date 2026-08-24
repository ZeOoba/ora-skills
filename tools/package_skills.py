#!/usr/bin/env python3
"""package_skills.py - build Cowork-importable .skill packages from ora-skills.

WHY THIS EXISTS (2026-06-11): PowerShell 5.1 Compress-Archive writes zip entry
paths with BACKSLASHES, which violates the zip spec (APPNOTE 4.4.17.1) and makes
the Claude desktop skill importer reject the file with "Zip file contains path
with invalid characters". Python's zipfile always normalizes to forward slashes.
RULE: never package skills with Compress-Archive; always use this script.

Usage: python tools/package_skills.py <outdir> [skill ...]
       (no skill args = all top-level skill dirs containing SKILL.md; after every
       named skill packages successfully, writes a completion sentinel/manifest
       `<outdir>/_STAGED.ok` — JSON: staged_at, outdir, packages (one {skill, file,
       bytes} entry per package, ACCUMULATED across every batch ever written into
       this outdir — fixed 2026-08-15, see write_staging_manifest() docstring), and
       last_batch (just this call's skill names). Added 2026-08-15 so a downstream
       consumer can tell "not staged yet" from "staged, zero packages" from "staged
       at a different path than expected" without walking the tree by hand.)
       python tools/package_skills.py --check-staged
       (validates frontmatter for every skill dir with staged changes; used by
       tools/hooks/pre-commit — exit 0 clean, exit 1 blocked)
"""
import json
import re
import subprocess
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKIP = {'_archive', 'tools', '.git'}
MAX_DESC = 1024  # platform limit: importer rejects 'description' > 1024 chars (hit 2026-06-11)

# Skills deliberately unpublished from the Cowork/claude.ai skill store (Gabriel's
# own ruling 2026-08-09) that must NEVER resurface as a pending_reimport candidate
# just because their repo copy gets an ordinary edit. OI-157: a 2026-08-12 docs-only
# commit to capex-budgeting (already unpublished 3 days earlier) made it look like
# routine reimport drift to pending_reimport.candidates(), got it packaged and
# staged, and Gabriel accidentally re-registered it in an unrelated 2026-08-13
# Save-skill batch click. A skill leaves this set only on Gabriel's explicit
# re-publish decision -- do not add/remove entries speculatively.
DELIBERATELY_UNPUBLISHED: frozenset[str] = frozenset({
    'annual-cycle',
    'capex-budgeting',
    'cash-position-monitor',
    'deal-retirement',
    'investor-relations',
    'vendor-management',
})


def _scan_named_counts(text: str) -> tuple[list[str], list[str]]:
    """Core 'N-Point'/'N-item' header-vs-actual-count scan, shared by check_named_counts
    (CLI, prints OK lines + raises) and validate_skill_frontmatter (returns errors only)
    so the counting logic itself can never drift between the two callers.

    Only fires on Markdown headers (lines starting with #) that contain the
    pattern — inline prose references are ignored. Catches name-vs-count drift
    like the 43-vs-42 discrepancy found 2026-06-11.

    Returns (oks, errors): oks are "N-Suffix (N items) OK" strings for headers whose
    claimed count matches; errors are "line N: ..." mismatch descriptions.
    """
    HEADER_PAT = re.compile(r'^(#{1,6})\s+.*?\b(\d+)-((?:[Pp]oint|[Ii]tem))\b', re.M)
    CHECKBOX = re.compile(r'^\s*-\s+(?:\\\[|\[)')   # - \[ \] or - [ ] (escaped or plain)
    NUMBERED = re.compile(r'^\s{0,3}\d+\.\s+\S')
    TABLE_ITEM = re.compile(r'^\s*\|\s*\d+\s*\|')   # numbered table row: | 1 | ... |
    HRULE = re.compile(r'^-{3,}\s*$')
    lines = text.splitlines()
    oks: list[str] = []
    errors: list[str] = []
    for m in HEADER_PAT.finditer(text):
        level, claimed, suffix = len(m.group(1)), int(m.group(2)), m.group(3)
        start = text[:m.start()].count('\n')
        stop_hdr = re.compile(r'^#{1,' + str(level) + r'}\s')
        count = 0
        for ln in lines[start + 1:]:
            if stop_hdr.match(ln) or HRULE.match(ln):
                break
            if CHECKBOX.match(ln) or NUMBERED.match(ln) or TABLE_ITEM.match(ln):
                count += 1
        if count == 0:
            continue  # no checklist found under this header; skip silently
        if count != claimed:
            errors.append(
                f'  line {start + 1}: "{claimed}-{suffix}" claims {claimed}, '
                f'found {count} items'
            )
        else:
            oks.append(f'{claimed}-{suffix} ({count} items) OK')
    return oks, errors


def check_named_counts(skill: str, text: str) -> None:
    """CLI-facing wrapper: print per-header OK lines, raise SystemExit on any mismatch."""
    oks, errors = _scan_named_counts(text)
    for ok in oks:
        print(f'{skill}: {ok}')
    if errors:
        raise SystemExit(f'{skill}: named-count mismatch:\n' + '\n'.join(errors))


def is_skill_dir(top: str) -> bool:
    """True if `top` (a top-level repo dir name) is a packageable skill directory."""
    return top not in SKIP and (REPO / top / 'SKILL.md').is_file()


def _description_has_unescaped_inner_quote(raw: str) -> bool:
    """True iff `raw` (the unparsed text captured after 'description:') is a double-quoted
    YAML scalar whose first unescaped closing '"' lands BEFORE the end of the value, leaving
    trailing content that corrupts the surrounding block mapping.

    This is the ONE install-blocking frontmatter defect class found in a 2026-08-13
    repo-wide sweep (parcel-data-recovery v1.7, commit d03fe62) -- the platform's importer
    rejects it at packaging time with a bare 'malformed yaml' and no main.log line at all,
    while package_skills.py's regex-based description extraction sailed past it printing
    'description N/1024 chars OK'.

    Deliberately narrower than "does the whole frontmatter block parse as strict YAML":
    two OTHER strict-YAML failure modes are common and benign, tolerated by the platform --
    an unquoted description containing ': ' (mapping-values-not-allowed), and a double-quoted
    description that never closes at all (unexpected-end-of-stream, missing closing quote
    entirely). A 2026-08-13 sweep found 19 live skills in those two benign classes; gating on
    strict validity alone would flag and needlessly churn all of them. This function returns
    False for both -- only an early, non-trailing-empty close is treated as a real defect.
    """
    s = raw.strip()
    if not s.startswith('"'):
        return False
    i = 1
    while i < len(s):
        c = s[i]
        if c == '\\':
            i += 2
            continue
        if c == '"':
            return s[i + 1:].strip() != ''
        i += 1
    return False  # never closes -- unterminated scalar, not this defect class


def validate_skill_frontmatter(skill_dir: Path, *, read_text=None, md_files=None) -> list[str]:
    """Validate one skill dir's SKILL.md frontmatter plus every *.md's named-count headers.

    Returns a list of error strings; empty means valid. This is the single source of
    truth for the frontmatter defect class — package_skills.py's validate_frontmatter()
    (packaging time) and tools/hooks/pre-commit's check_staged() (commit time) both call
    this, so the two gates can never validate different rules (psa-reconciliation's
    1274-char description reaching the repo untouched by either gate, 2026-07-17).

    `read_text`/`md_files` are internal overrides: check_staged() passes a reader backed
    by the git INDEX so a commit is validated against what's actually STAGED, not whatever
    happens to be on disk in the working tree (code review finding, 2026-07-17 — without
    this, staging a good description then further editing SKILL.md without re-staging could
    pass a hook check that has nothing to do with the content being committed, and vice
    versa). `read_text(rel: str) -> str` reads one skill-dir-relative file; `md_files` is
    the skill-dir-relative *.md path list to scan for named-count headers. Both default to
    None, meaning "read disk" — the packaging call site (validate_frontmatter -> package())
    omits them because packaging always operates on the working tree as it stands.
    """
    skill = skill_dir.name
    errors: list[str] = []

    def _read(rel: str) -> str:
        if read_text is not None:
            return read_text(rel)
        return (skill_dir / rel).read_text(encoding='utf-8', errors='replace')

    try:
        text = _read('SKILL.md')
    except (FileNotFoundError, subprocess.CalledProcessError):
        return [f'{skill}: no SKILL.md at {skill_dir}']
    m = re.search(r'^---\s*\n(.*?)\n---', text, re.S)
    if not m:
        return [f'{skill}: SKILL.md has no YAML frontmatter']
    fm = m.group(1)
    nm = re.search(r'^name:\s*(\S+)', fm, re.M)
    if not nm or nm.group(1).strip("'\"") != skill:
        errors.append(f"{skill}: frontmatter 'name' missing or != directory name")
    dm = re.search(r"^description:\s*(.*?)(?=\n[a-zA-Z_-]+:|\Z)", fm, re.S | re.M)
    if not dm:
        errors.append(f"{skill}: frontmatter has no 'description'")
    else:
        if _description_has_unescaped_inner_quote(dm.group(1)):
            errors.append(
                f"{skill}: description is a double-quoted YAML scalar with an unescaped "
                f'inner \'"\' that closes the scalar early, corrupting the frontmatter block '
                f"mapping. The platform's importer rejects this at packaging time with a bare "
                f"'malformed yaml' and NO main.log line (parcel-data-recovery v1.7, "
                f'2026-08-13). Escape inner quotes as \\" or switch them to single quotes.'
            )
        raw_desc = dm.group(1).strip()
        # An unterminated quoted description with NO closing quote anywhere is benign --
        # the value simply runs to the '---' and every reader recovers it (see
        # test_unterminated_double_quoted_description_is_not_flagged). What is NOT benign
        # is an unterminated scalar whose closing quote sits in the BODY: a reader that
        # does not stop at the fence swallows the fence and the body text into the value.
        # Only that shape is flagged here.
        for _q in ('"', "'"):
            if not (len(raw_desc) > 1 and raw_desc.startswith(_q) and not raw_desc.endswith(_q)):
                continue
            body_head = text[m.end():].split('\n')[:16]
            orphan = next(
                (i for i, ln in enumerate(body_head)
                 if ln.rstrip().endswith(_q) and ln.count(_q) % 2 == 1),
                None,
            )
            if orphan is None:
                continue
            errors.append(
                f"{skill}: description opens a {_q}-quoted YAML scalar, does not close it on its "
                f"own line, and an orphaned closing {_q} sits {orphan + 1} line(s) into the BODY. "
                f"A reader that does not stop at the closing '---' swallows the fence and the body "
                f"text into the description. This repo's own regex reader DOES stop at the fence, "
                f"so description_budget.py and this packager both report OK while the platform "
                f"reads something else: on 2026-08-24 ora-flood-zoning-dd, document-assembly and "
                f"exception-detection each listed their body changelog heading as their "
                f"description, meaning none of their trigger vocabulary was routing. All three "
                f"were damaged by the 2026-07-29 Phase-4 description lint, which moved the "
                f"changelog into the body and left the quote open behind it. Fix: close the quote "
                f"at the end of the description line and delete the orphaned quote from the body."
            )
            break
        desc = raw_desc.strip("'\"")
        if len(desc) > MAX_DESC:
            errors.append(
                f"{skill}: description is {len(desc)} chars — exceeds the {MAX_DESC}-char "
                f"platform limit; the importer will reject it. Trim it before packaging."
            )
        tag = re.search(r'</?[A-Za-z][^>]*>', desc)
        if tag:
            errors.append(
                f"{skill}: description contains an XML-like tag {tag.group(0)!r} — the platform "
                f"importer rejects angle-bracket tags in 'description' (hit 2026-06-22). Replace it "
                f"(e.g. <skill> -> [skill]) before packaging."
            )
    # Scan EVERY Markdown file under the skill dir, not just SKILL.md, so named-count
    # headers in references/ are validated too (gap found 2026-06-11:
    # loi-generation/references/qc-gate.md was silently unscanned). Label each finding
    # with the relative path so the source file is obvious.
    rel_paths = md_files if md_files is not None else sorted(
        p.relative_to(skill_dir).as_posix() for p in skill_dir.rglob('*.md')
    )
    for rel in rel_paths:
        if rel == 'SKILL.md':
            md_text = text
        else:
            try:
                md_text = _read(rel)
            except (FileNotFoundError, subprocess.CalledProcessError) as exc:
                # A staged/working file `rel_paths` names but `_read` can't retrieve --
                # e.g. a merge-conflicted file with no stage-0 index entry (git show
                # exits non-zero). Surface it as a validation error (commit stays
                # blocked, same as today) instead of letting the exception propagate
                # as a raw traceback (code review finding, 2026-07-17).
                errors.append(f'{skill}/{rel}: could not read content to scan ({exc})')
                continue
        _, mismatches = _scan_named_counts(md_text)
        if mismatches:
            errors.append(f'{skill}/{rel}: named-count mismatch:\n' + '\n'.join(mismatches))
    return errors


def validate_frontmatter(skill: str, src: Path) -> None:
    """CLI-facing wrapper used by package(): validates via validate_skill_frontmatter()
    (the shared gate) and, on success, reprints the same per-check OK lines the packager
    has always printed at packaging time."""
    errors = validate_skill_frontmatter(src)
    if errors:
        raise SystemExit('\n'.join(errors))
    text = (src / 'SKILL.md').read_text(encoding='utf-8', errors='replace')
    fm = re.search(r'^---\s*\n(.*?)\n---', text, re.S).group(1)
    desc = re.search(
        r"^description:\s*(.*?)(?=\n[a-zA-Z_-]+:|\Z)", fm, re.S | re.M
    ).group(1).strip().strip("'\"")
    print(f'{skill}: description {len(desc)}/{MAX_DESC} chars OK')
    for md in sorted(src.rglob('*.md')):
        rel = md.relative_to(src).as_posix()
        md_text = text if rel == 'SKILL.md' else md.read_text(encoding='utf-8', errors='replace')
        check_named_counts(f'{skill}/{rel}', md_text)


def staged_skill_dirs(files: list[str] | None = None) -> list[Path]:
    """Map staged (git diff --cached --name-only) file paths to their skill root dirs,
    deduped and sorted. Pass `files` explicitly (as tests do) to bypass the live git call.
    """
    if files is None:
        out = subprocess.run(
            ['git', '-C', str(REPO), 'diff', '--cached', '--name-only'],
            capture_output=True, text=True, check=True,
        ).stdout
        files = [ln.strip() for ln in out.splitlines() if ln.strip()]
    roots = {REPO / f.split('/')[0] for f in files if is_skill_dir(f.split('/')[0])}
    return sorted(roots)


def _staged_content(repo_rel_path: str) -> str:
    """Content of a repo-relative posix path from the git INDEX (staged), not the working
    tree. `git show :path` — a bare ':' before the path means the index, not HEAD.

    Explicit encoding='utf-8', errors='replace' matches every disk-based reader in this
    file (e.g. validate_skill_frontmatter's default _read). Without it, subprocess.run's
    text=True decodes with the locale encoding -- commonly cp1252 on Windows -- which can
    both decode malformed bytes differently than the disk path would and raise an uncaught
    UnicodeDecodeError on some byte sequences, breaking the guarantee that packaging-time
    and commit-time validation can never disagree (code review finding, 2026-07-17)."""
    return subprocess.run(
        ['git', '-C', str(REPO), 'show', f':{repo_rel_path}'],
        capture_output=True, text=True, encoding='utf-8', errors='replace', check=True,
    ).stdout


def _parse_staged_md_files(ls_files_null_output: str, repo_rel_root: str) -> list[str]:
    """Pure parser: `git ls-files -z` NUL-delimited output -> skill-dir-relative *.md paths.
    Split from _staged_md_files() so the path-filtering logic is unit-testable without a
    git sandbox."""
    prefix = repo_rel_root + '/'
    return sorted(
        p[len(prefix):] for p in ls_files_null_output.split('\0')
        if p.endswith('.md') and p.startswith(prefix)
    )


def _staged_md_files(skill_dir: Path) -> list[str]:
    """Skill-dir-relative posix paths of every *.md the git INDEX has under skill_dir — the
    STAGED tree, not the working tree (a disk-only untracked file isn't here; a file staged
    for deletion isn't either)."""
    repo_rel_root = skill_dir.relative_to(REPO).as_posix()
    out = subprocess.run(
        ['git', '-C', str(REPO), 'ls-files', '--cached', '-z', '--', repo_rel_root],
        capture_output=True, text=True, check=True,
    ).stdout
    return _parse_staged_md_files(out, repo_rel_root)


def check_staged(files: list[str] | None = None) -> int:
    """tools/hooks/pre-commit entry point: validate frontmatter for every skill dir with
    staged changes, against the STAGED git-index content (not the working tree — see
    validate_skill_frontmatter's read_text/md_files doc). Prints errors verbatim to stderr;
    returns a process exit code (0 clean, 1 blocked) rather than raising, since a hook needs
    a plain exit status.
    """
    errors: list[str] = []
    for skill_dir in staged_skill_dirs(files):
        repo_rel_root = skill_dir.relative_to(REPO).as_posix()

        def _read(rel: str, _root: str = repo_rel_root) -> str:
            return _staged_content(f'{_root}/{rel}')

        errors.extend(validate_skill_frontmatter(
            skill_dir, read_text=_read, md_files=_staged_md_files(skill_dir),
        ))
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    return 0


def check_tree_hygiene(repo: Path = REPO, max_bytes: int = 5 * 1024 * 1024) -> list[str]:
    """Flag build-artifact contamination in skill source directories.

    A *.skill or *.plugin file has no business living inside a skill's own top-level
    directory — packaged output belongs outside the repo entirely. `repo` is
    parameterized (rather than always using the global REPO) so this is unit-testable
    against a scratch directory tree; real callers use the default.

    Motivation (2026-07-24): a swapped outdir/skill argument to package_skills.py dumped
    44 sibling .skill packages into register-scheduled-task/, and because that directory
    is 'r'-alphabetically late among top-level dirs, by the time register-scheduled-task
    itself was packaged most of its siblings' output already sat beside it — rglob('*')
    picked those up as bundleable source content, so register-scheduled-task.skill
    recursively rebundled them and ballooned to 15GB before anyone noticed. *.skill is
    gitignored (never tracked), so git status alone never surfaces this class of
    contamination — hence a dedicated tree-hygiene check independent of what's staged.
    *.plugin (tools/build_plugin.py's output) is the identical risk one level up: it is
    built via the same skill_source_files() -> rglob('*') -> is_bundled() path shared
    with the .skill packager, and build_plugin()'s outdir.mkdir(exist_ok=True) has the
    same silent-success-against-an-existing-skill-dir behavior — so both extensions are
    scanned here rather than just the one the original incident happened to produce.
    Every hit is reported regardless of size; hits at/above `max_bytes` are called out as
    especially urgent so runaway growth surfaces immediately rather than silently filling
    the disk.
    """
    errors: list[str] = []
    if not repo.is_dir():
        return errors
    for d in sorted(repo.iterdir()):
        if not d.is_dir() or d.name in SKIP or not (d / 'SKILL.md').is_file():
            continue
        strays = sorted(d.rglob('*.skill')) + sorted(d.rglob('*.plugin'))
        for stray in strays:
            size = stray.stat().st_size
            rel = stray.relative_to(repo).as_posix()
            kind = stray.suffix.lstrip('.')
            if size >= max_bytes:
                errors.append(
                    f'{rel}: {size / (1024 * 1024):.1f} MB .{kind} package found inside a '
                    f'skill source directory — almost certainly outdir/skill argument '
                    f'contamination (usage: package_skills.py <outdir> [skill ...] / '
                    f'build_plugin.py <plugin-name> <outdir>, never a skill\'s own dir as '
                    f'the outdir). Move it out of the repo.'
                )
            else:
                errors.append(
                    f'{rel}: .{kind} package found inside a skill source directory — '
                    f'packaged output must never live beside its source. Move it out of '
                    f'the repo.'
                )
    return errors


def check_hygiene_cli() -> int:
    """tools/hooks/pre-commit entry point (Check 3): exit 1 if any skill source
    directory contains a stray .skill build artifact; prints findings to stderr."""
    errors = check_tree_hygiene()
    if errors:
        for e in errors:
            print(e, file=sys.stderr)
        return 1
    return 0


def resolve_outdir_collision(outdir: Path, repo: Path = REPO) -> str | None:
    """If `outdir` resolves to `repo` itself or to one of its skill directories, return a
    human-readable description of the collision; else None. `repo` is parameterized for
    unit-testing against a scratch tree; real callers use the default.

    Guards the 2026-07-24 footgun: package_skills.py's usage is
    `<outdir> [skill ...]`, not `<skill> [outdir]`. Swapping the two args sets outdir to a
    skill's own directory; since that path already exists, `outdir.mkdir(exist_ok=True)`
    silently succeeds, and with no skill filter the run packages EVERY skill straight into
    that skill's source tree (see check_tree_hygiene for how that then compounds).
    """
    resolved = outdir.resolve()
    if resolved == repo.resolve():
        return f'the repo root ({repo})'
    for d in sorted(repo.iterdir()):
        if d.is_dir() and d.name not in SKIP and (d / 'SKILL.md').is_file():
            if resolved == d.resolve():
                return f"the '{d.name}' skill's own source directory"
    return None


# Repo-root files a skill's own directory doesn't contain but declares as its canonical
# data source (2026-07-09 — target-markets.json was never reaching the Cowork cache because
# package() only ever walked the skill's own folder; these 5 cite it as authoritative).
# Bundled fresh from this single source on every package() call, so there's one file to
# maintain, not N drifting copies.
SHARED_ROOT_DEPS = {
    'daily-brief': ['target-markets.json'],
    'deal-comparison': ['target-markets.json'],
    'market-monitor': ['target-markets.json'],
    'acquisition-underwriting': ['target-markets.json'],
    'pma-qc': [('tools/ora_doc_qc.py', 'scripts/ora_doc_qc.py')],
    'listing-agreement-qc': [('tools/ora_doc_qc.py', 'scripts/ora_doc_qc.py')],
    'lease-form-qc': [('tools/ora_doc_qc.py', 'scripts/ora_doc_qc.py')],
    'lease-addendum': [('tools/ora_doc_qc.py', 'scripts/ora_doc_qc.py')],
}


def _dep_pair(dep) -> tuple[str, str]:
    """Normalize one SHARED_ROOT_DEPS list entry to (repo_root_relpath,
    skill_relpath). A plain string means source and destination share the same
    relative name (the target-markets.json pattern — fans out to the skill's
    own root under the identical name). A 2-tuple is (source, dest) for a
    shared file whose repo-root location differs from where it must land
    inside the skill."""
    if isinstance(dep, tuple):
        return dep
    return dep, dep


def is_bundled(rel_posix: str) -> bool:
    """Single source of truth for 'does this skill-relative file ship in the .skill?'.

    rel_posix is a forward-slash path relative to the skill dir (e.g. 'SKILL.md',
    'references/qc-gate.md', 'versions/20260716_...md'). Excluded from every bundle:
      - PACKAGING-NOTE.md (any level): repo-reader documentation only (2026-07-16 false-
        missing-file incident) — bundling it flips consumers to repo-newer on drift checks.
      - a top-level versions/ directory: dated version archives (several skills use
        this pattern today) — historical snapshots, never shippable skill content. The drift-check
        has always SKIPped cowork-settings\versions; excluding it here keeps packager, the
        post-commit hook (tools/pending_reimport.py imports this), and the drift-check in
        agreement so a versions/-only commit never falsely flags a reimport (2026-07-16).
      - a top-level tests/ directory: developer-side regression fixtures and harnesses
        (pma-qc, listing-agreement-qc, lease-form-qc all added one on the
        shared-doc-qc-module-retrofit branch, 2026-08-17) — never shippable skill
        content, same reasoning as versions/ above. Before that branch no skill had a
        tests/ dir, so this gap went unnoticed; left unexcluded, a 52KB test file
        outweighing the skill's own SKILL.md would ship inside the runtime-installed
        .skill, and every edit to a test file would mark the skill's cache stale for
        reimport purposes (pending_reimport.py's drift detection also calls
        is_bundled()).
      - Python bytecode caches (__pycache__/ at any level, and any *.pyc/*.pyo): build
        residue from running a skill's own scripts/ locally. .gitignore already keeps
        these out of git, so they are invisible to a repo diff — but the packager walked
        the working tree, not the index, and would happily ship them. A bundled .pyc also
        makes the cache file-count differ from the repo's, which reads as permanent drift
        on every subsequent hash pre-check. Found 2026-08-01 packaging deal-execution
        after test-running its new scripts (audit_completeness.cpython-310.pyc shipped).
    """
    parts = rel_posix.split('/')
    if parts[-1] == 'PACKAGING-NOTE.md':
        return False
    if parts[0] == 'versions':
        return False
    if parts[0] == 'tests':
        return False
    if '__pycache__' in parts:
        return False
    if parts[-1].endswith(('.pyc', '.pyo')):
        return False
    return True


# ---------------------------------------------------------------------------
# Plugin membership (2026-07-16). Some skills reach the Cowork runtime as members
# of a plugin BUNDLE (plugins/<name>/plugin-build.json), not as standalone
# Save-skill installs. A standalone .skill install of a bundled skill is the WRONG
# target — it lands a shadow copy while the plugin's loaded copy stays stale
# (deal-retirement / submarket-spatial-analysis, 2026-07-16). This block is the
# single source of truth for "is this skill plugin-bundled?" so the packager, the
# post-commit ledger (tools/pending_reimport.py imports plugin_of), and
# tools/build_plugin.py can never disagree. Defensive: no plugins/ dir -> empty
# maps -> zero behavior change to standalone packaging.
# ---------------------------------------------------------------------------
PLUGINS_DIR = REPO / 'plugins'


def load_plugin_manifests() -> dict[str, dict]:
    """{plugin_name: manifest dict} from every plugins/*/plugin-build.json.
    Never raises on a malformed/missing manifest — a broken build manifest must
    not break standalone .skill packaging or the commit hook that imports this."""
    import json
    manifests: dict[str, dict] = {}
    if not PLUGINS_DIR.is_dir():
        return manifests
    for mf in sorted(PLUGINS_DIR.glob('*/plugin-build.json')):
        try:
            d = json.loads(mf.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        name = d.get('name') or mf.parent.name
        manifests[name] = d
    return manifests


def _build_plugin_members(manifests: dict[str, dict]) -> dict[str, str]:
    members: dict[str, str] = {}
    for name, d in manifests.items():
        for skill in d.get('skills', []):
            members[skill] = name
    return members


PLUGIN_MANIFESTS: dict[str, dict] = load_plugin_manifests()
# reverse map: member skill -> owning plugin name
PLUGIN_MEMBERS: dict[str, str] = _build_plugin_members(PLUGIN_MANIFESTS)


def plugin_of(skill: str) -> str | None:
    """Owning plugin name if `skill` is bundled in a version-controlled plugin,
    else None (skill installs standalone via Save-skill)."""
    return PLUGIN_MEMBERS.get(skill)


def skill_source_files(skill: str, repo_root: Path = REPO) -> dict[str, Path]:
    """{skill-relative posix path: absolute path} for every file this skill ships:
    its own bundled files (is_bundled) plus repo-root SHARED_ROOT_DEPS fan-out.
    Shared by the .skill packager and tools/build_plugin.py so a plugin bundle and
    a standalone .skill agree byte-for-byte on a skill's shipped content."""
    src = repo_root / skill
    files = {
        p.relative_to(src).as_posix(): p
        for p in sorted(src.rglob('*'))
        if p.is_file() and is_bundled(p.relative_to(src).as_posix())
    }
    for dep in SHARED_ROOT_DEPS.get(skill, []):
        dep_src, dep_dest = _dep_pair(dep)
        dep_path = repo_root / dep_src
        if dep_path.is_file():
            files[dep_dest] = dep_path
    return files


def package(skill: str, outdir: Path) -> Path:
    src = REPO / skill
    if not (src / 'SKILL.md').is_file():
        raise SystemExit(f'{skill}: no SKILL.md at {src}')
    validate_frontmatter(skill, src)
    dest = outdir / f'{skill}.skill'
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob('*')):
            # is_bundled() is the single source of truth for what ships (PACKAGING-NOTE.md
            # and top-level versions/ archives are excluded); tools/pending_reimport.py
            # imports the same function so the post-commit hook and the packager can never
            # disagree about which file changes warrant a reimport.
            if p.is_file() and is_bundled(p.relative_to(src).as_posix()):
                arc = f'{skill}/' + p.relative_to(src).as_posix()
                assert '\\' not in arc, arc
                z.write(p, arc)
        for shared_name in SHARED_ROOT_DEPS.get(skill, []):
            dep_src, dep_dest = _dep_pair(shared_name)
            shared_path = REPO / dep_src
            if not shared_path.is_file():
                raise SystemExit(f'{skill}: declared shared dep {dep_src} not found at {shared_path}')
            z.write(shared_path, f'{skill}/{dep_dest}')
    with zipfile.ZipFile(dest) as z:
        bad = [n for n in z.namelist() if '\\' in n]
        if bad:
            raise SystemExit(f'{skill}: backslash entries {bad}')
        print(f'{dest.name}: {len(z.namelist())} entries OK')
        for n in z.namelist():
            print(f'   {n}')
    return dest


def write_staging_manifest(outdir: Path, packaged: list[Path]) -> Path:
    """Write a completion sentinel into outdir after a packaging batch finishes, so a
    downstream consumer (e.g. package-and-stage-skill, or a Cowork remediation pass
    reading a handoff folder cold) can tell "nothing has been staged here yet" apart
    from "staging finished and produced zero packages" or "staging is still running."

    Motivated 2026-08-15 (Rev 10 remediation): a Cowork session was pointed at an
    outdir that this script never wrote to — at least one package from that batch had
    actually landed in a DIFFERENT outdir (a plain argument-path mismatch upstream of
    this script, not a packaging bug) — and had no way to distinguish "not run yet"
    from "ran, wrong target, folder legitimately doesn't exist" without a human
    walking the whole tree by hand. A sentinel makes that a one-file check.

    Always written last, after every package() in the batch has succeeded — package()
    raises SystemExit on any failure, so a manifest's presence is itself proof every
    named skill in `packaged` packaged cleanly, not just that the script started.

    ACCUMULATES across batches into the same outdir, never overwrites (fixed
    2026-08-15, same day as the field's introduction). The first cut wrote a fresh
    `packages` list from just this call's `packaged` arg every time — so a SECOND
    batch into a shared outdir (e.g. `_staging/<date>/`, which routinely collects
    multiple unrelated packaging runs across a day) silently erased the first
    batch's entries from the manifest, even though the .skill files themselves were
    still sitting right there on disk untouched. Caught live: an
    `automation-health-monitor.skill` packaged ~24 minutes before a later
    `insurance-renewal-review` + `package-and-stage-skill` batch had its manifest
    line vanish from `_STAGED.ok` — a downstream Cowork session doing freshness
    triage read the missing entry as "not corroborated as packaged today" and had to
    fall back to a manual per-file git-log/hash check to confirm it wasn't stale.
    Now: prior entries for skills NOT in this batch are preserved; a skill named in
    both the prior manifest and this batch is refreshed to the new entry (repackaged
    = newer, never older); `last_batch` records just the current call's skills so a
    caller can still tell "this specific invocation packaged zero things" (e.g. a
    typo'd skill filter) apart from "the accumulated outdir has zero packages ever."
    A corrupt or unreadable prior sentinel is never fatal — this manifest is a
    convenience index, not a source of truth (repo/cache hash comparisons remain
    authoritative) — treated as no prior entries and overwritten cleanly.
    """
    sentinel = outdir / '_STAGED.ok'
    existing_packages: dict[str, dict] = {}
    if sentinel.is_file():
        try:
            prior = json.loads(sentinel.read_text(encoding='utf-8'))
            for entry in prior.get('packages', []):
                name = entry.get('skill')
                if name:
                    existing_packages[name] = entry
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            existing_packages = {}
    this_batch = [
        {'skill': p.stem, 'file': p.name, 'bytes': p.stat().st_size}
        for p in packaged
    ]
    for entry in this_batch:
        existing_packages[entry['skill']] = entry
    manifest = {
        'staged_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'outdir': str(outdir.resolve()),
        'packages': list(existing_packages.values()),
        'last_batch': [entry['skill'] for entry in this_batch],
    }
    sentinel.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    return sentinel


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__.strip())
        sys.exit(0)
    if sys.argv[1] == '--check-staged':
        # tools/hooks/pre-commit entry point: validate frontmatter of every skill dir
        # with staged changes; exit 1 blocks the commit.
        sys.exit(check_staged())
    if sys.argv[1] == '--check-tree-hygiene':
        # tools/hooks/pre-commit entry point (Check 3): flag stray .skill build
        # artifacts sitting inside skill source directories; exit 1 blocks the commit.
        sys.exit(check_hygiene_cli())
    outdir = Path(sys.argv[1])
    collision = resolve_outdir_collision(outdir)
    if collision:
        sys.exit(
            f'error: outdir {outdir} resolves to {collision}. This is almost certainly a '
            f'swapped argument — usage is package_skills.py <outdir> [skill ...], not '
            f'<skill> [outdir]. Refusing to dump .skill packages into a skill source '
            f'directory (2026-07-24 incident: this exact mistake packaged all skills into '
            f'register-scheduled-task/, and one output recursively rebundled the others, '
            f'ballooning to 15GB). Pick an outdir outside the repo.'
        )
    outdir.mkdir(parents=True, exist_ok=True)
    skills = sys.argv[2:] or [
        d.name for d in REPO.iterdir() if d.is_dir() and is_skill_dir(d.name)
    ]
    packaged = [package(s, outdir) for s in skills]
    sentinel = write_staging_manifest(outdir, packaged)
    print(f'staged {len(packaged)} package(s); manifest: {sentinel.name}')


if __name__ == '__main__':
    main()
