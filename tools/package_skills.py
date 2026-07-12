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


def package(skill: str, outdir: Path) -> Path:
    src = REPO / skill
    if not (src / 'SKILL.md').is_file():
        raise SystemExit(f'{skill}: no SKILL.md at {src}')
    validate_frontmatter(skill, src)
    dest = outdir / f'{skill}.skill'
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src.rglob('*')):
            if p.is_file():
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
