#!/usr/bin/env python3
"""package_skills.py - build Cowork-importable .skill packages from ora-skills.

WHY THIS EXISTS (2026-06-11): PowerShell 5.1 Compress-Archive writes zip entry
paths with BACKSLASHES, which violates the zip spec (APPNOTE 4.4.17.1) and makes
the Claude desktop skill importer reject the file with "Zip file contains path
with invalid characters". Python's zipfile always normalizes to forward slashes.
RULE: never package skills with Compress-Archive; always use this script.

Usage: python tools/package_skills.py <outdir> [skill ...]
       (no skill args = all top-level skill dirs containing SKILL.md)
"""
import re
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKIP = {'_archive', 'tools', '.git'}
MAX_DESC = 1024  # platform limit: importer rejects 'description' > 1024 chars (hit 2026-06-11)


def check_named_counts(skill: str, text: str) -> None:
    """Fail if any 'N-Point' / 'N-item' section header names the wrong item count.

    Only fires on Markdown headers (lines starting with #) that contain the
    pattern — inline prose references are ignored. Catches name-vs-count drift
    like the 43-vs-42 discrepancy found 2026-06-11.
    """
    HEADER_PAT = re.compile(r'^(#{1,6})\s+.*?\b(\d+)-((?:[Pp]oint|[Ii]tem))\b', re.M)
    CHECKBOX = re.compile(r'^\s*-\s+(?:\\\[|\[)')   # - \[ \] or - [ ] (escaped or plain)
    NUMBERED = re.compile(r'^\s{0,3}\d+\.\s+\S')
    TABLE_ITEM = re.compile(r'^\s*\|\s*\d+\s*\|')   # numbered table row: | 1 | ... |
    HRULE = re.compile(r'^-{3,}\s*$')
    lines = text.splitlines()
    errors = []
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
            print(f'{skill}: {claimed}-{suffix} ({count} items) OK')
    if errors:
        raise SystemExit(f'{skill}: named-count mismatch:\n' + '\n'.join(errors))


def validate_frontmatter(skill: str, src: Path) -> None:
    text = (src / 'SKILL.md').read_text(encoding='utf-8', errors='replace')
    m = re.search(r'^---\s*\n(.*?)\n---', text, re.S)
    if not m:
        raise SystemExit(f'{skill}: SKILL.md has no YAML frontmatter')
    fm = m.group(1)
    nm = re.search(r'^name:\s*(\S+)', fm, re.M)
    if not nm or nm.group(1).strip("'\"") != skill:
        raise SystemExit(f"{skill}: frontmatter 'name' missing or != directory name")
    dm = re.search(r"^description:\s*(.*?)(?=\n[a-zA-Z_-]+:|\Z)", fm, re.S | re.M)
    if not dm:
        raise SystemExit(f"{skill}: frontmatter has no 'description'")
    desc = dm.group(1).strip().strip("'\"")
    if len(desc) > MAX_DESC:
        raise SystemExit(
            f"{skill}: description is {len(desc)} chars — exceeds the {MAX_DESC}-char "
            f"platform limit; the importer will reject it. Trim it before packaging."
        )
    tag = re.search(r'</?[A-Za-z][^>]*>', desc)
    if tag:
        raise SystemExit(
            f"{skill}: description contains an XML-like tag {tag.group(0)!r} — the platform "
            f"importer rejects angle-bracket tags in 'description' (hit 2026-06-22). Replace it "
            f"(e.g. <skill> -> [skill]) before packaging."
        )
    print(f'{skill}: description {len(desc)}/{MAX_DESC} chars OK')
    # Scan EVERY Markdown file under the skill dir, not just SKILL.md, so named-count
    # headers in references/ are validated too (gap found 2026-06-11:
    # loi-generation/references/qc-gate.md was silently unscanned). Label each finding
    # with the relative path so the source file is obvious.
    for md in sorted(src.rglob('*.md')):
        rel = md.relative_to(src).as_posix()
        md_text = text if rel == 'SKILL.md' else md.read_text(encoding='utf-8', errors='replace')
        check_named_counts(f'{skill}/{rel}', md_text)


# Repo-root files a skill's own directory doesn't contain but declares as its canonical
# data source (2026-07-09 — target-markets.json was never reaching the Cowork cache because
# package() only ever walked the skill's own folder; these 5 cite it as authoritative).
# Bundled fresh from this single source on every package() call, so there's one file to
# maintain, not N drifting copies.
SHARED_ROOT_DEPS = {
    'daily-brief': ['target-markets.json'],
    'deal-comparison': ['target-markets.json'],
    'market-monitor': ['target-markets.json'],
    'rent-comp': ['target-markets.json'],
    'acquisition-underwriting': ['target-markets.json'],
}


def is_bundled(rel_posix: str) -> bool:
    """Single source of truth for 'does this skill-relative file ship in the .skill?'.

    rel_posix is a forward-slash path relative to the skill dir (e.g. 'SKILL.md',
    'references/qc-gate.md', 'versions/20260716_...md'). Excluded from every bundle:
      - PACKAGING-NOTE.md (any level): repo-reader documentation only (2026-07-16 false-
        missing-file incident) — bundling it flips consumers to repo-newer on drift checks.
      - a top-level versions/ directory: dated version archives (only cowork-settings uses
        one today) — historical snapshots, never shippable skill content. The drift-check
        has always SKIPped cowork-settings\versions; excluding it here keeps packager, the
        post-commit hook (tools/pending_reimport.py imports this), and the drift-check in
        agreement so a versions/-only commit never falsely flags a reimport (2026-07-16).
    """
    parts = rel_posix.split('/')
    if parts[-1] == 'PACKAGING-NOTE.md':
        return False
    if parts[0] == 'versions':
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
        dep_path = repo_root / dep
        if dep_path.is_file():
            files[dep] = dep_path
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
            shared_path = REPO / shared_name
            if not shared_path.is_file():
                raise SystemExit(f'{skill}: declared shared dep {shared_name} not found at {shared_path}')
            z.write(shared_path, f'{skill}/{shared_name}')
    with zipfile.ZipFile(dest) as z:
        bad = [n for n in z.namelist() if '\\' in n]
        if bad:
            raise SystemExit(f'{skill}: backslash entries {bad}')
        print(f'{dest.name}: {len(z.namelist())} entries OK')
        for n in z.namelist():
            print(f'   {n}')
    return dest


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(__doc__.strip())
        sys.exit(0)
    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    skills = sys.argv[2:] or [
        d.name for d in REPO.iterdir()
        if d.is_dir() and d.name not in SKIP and (d / 'SKILL.md').is_file()
    ]
    for s in skills:
        package(s, outdir)


if __name__ == '__main__':
    main()
