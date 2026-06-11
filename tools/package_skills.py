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
    print(f'{skill}: description {len(desc)}/{MAX_DESC} chars OK')


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
    with zipfile.ZipFile(dest) as z:
        bad = [n for n in z.namelist() if '\\' in n]
        if bad:
            raise SystemExit(f'{skill}: backslash entries {bad}')
        print(f'{dest.name}: {len(z.namelist())} entries OK')
        for n in z.namelist():
            print(f'   {n}')
    return dest


def main() -> None:
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
