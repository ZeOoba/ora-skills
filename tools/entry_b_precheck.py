#!/usr/bin/env python3
"""entry_b_precheck.py - package-and-stage-skill Entry Point B, mechanized.

WHY THIS EXISTS (2026-09-07, Automation Audit systematization candidate from the
county-parcel-screen / county-sales-monitor first-install session): Entry Point
B's four-item integrity pre-check (exists / entries / freshness-vs-repo /
stage+baseline) was being re-derived by hand every session that processed a
pre-built .skill handoff -- ad hoc PowerShell plus a one-off Python script,
rewritten from scratch each time, with no shared source of truth for the EOL-
normalization rule, the shared-dep fan-out, or the plugin-routing gate. This is
that check, generalized and parameterized on skill name. It reuses the SAME
comparators package_skills.py / pending_reimport.py already use
(skill_source_files, _normalized_hash, plugin_of, validate_skill_frontmatter),
so this tool can never quietly disagree with the packager or the drift ledger
about what "fresh" means.

Per named skill, in order:
  0. Plugin-membership routing gate (plugin_of). A plugin-bundled skill must
     never be treated as a standalone Save-skill target (2026-07-16
     wrong-target class: deal-retirement / submarket-spatial-analysis lands a
     shadow copy while the plugin's loaded copy stays stale). REJECTED unless
     --allow-plugin is passed, which still prints a loud warning.
  1. EXISTS. Assert the .skill file at the stated (or resolved) path. If not
     found at the stated path, sweep --search dirs before declaring MISSING.
     MISSING (never built) and STALE (built, no longer matches repo) are
     different findings with different remedies -- see package-and-stage-skill
     Entry Point B item 1. This tool only ever detects; it never repackages.
  2. ENTRIES. Forward-slash paths only, zero directory records, entry count
     matches len(skill_source_files(skill)) (which already includes the
     SHARED_ROOT_DEPS fan-out).
  2a. FRONTMATTER. validate_skill_frontmatter() -- name==dir, description
     <=1024 chars, no unescaped-inner-quote / orphaned-closing-quote defect,
     no named-count header mismatch.
  3. FRESHNESS. SHA256 each packaged file vs its repo counterpart via
     pending_reimport._normalized_hash (CRLF/LF and SKILL.md YAML-quoting
     normalized before a mismatch counts as real drift).
  4. STAGE + BASELINE. Copy the verified package into --stage-to, hash-verify
     the copy, and record the runtime cache directory's current CreationTime
     (or "absent") into a per-skill manifest JSON
     (<stage-to>/<skill>.precheck.json). tools/verify_install.ps1 reads that
     manifest after the Save-skill click to do the post-install verification.
     Skipped (with a note) if --stage-to is omitted.

Usage:
  python tools/entry_b_precheck.py <skill> [<skill> ...] --stage-to <dir>
  python tools/entry_b_precheck.py <path\\to\\name.skill> --stage-to <dir>
  python tools/entry_b_precheck.py <skill> --search <dir> [<dir> ...] --stage-to <dir>
  python tools/entry_b_precheck.py <skill> --allow-plugin --stage-to <dir>

A bare name is resolved to <name>.skill by searching (in order): the path as
given, the current directory, REPO/_staging and its immediate subdirectories,
then any --search dirs (recursive). Exit 0 iff every named skill's verdict is
OK; exit 1 on any MISSING / STALE / entry-check failure / frontmatter error /
unresolved plugin-routing mismatch, printed per skill -- never silently
averaged into one batch verdict.
"""
import argparse
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_skills import (  # noqa: E402
    REPO, MAX_DESC, plugin_of, skill_source_files, validate_skill_frontmatter,
)
from pending_reimport import (  # noqa: E402
    CACHE_ROOT, _normalized_hash, _normalized_hash_bytes, _isdir_long, _win_long,
)


def _default_search_dirs() -> list[Path]:
    dirs = [Path.cwd(), REPO / '_staging']
    staging = REPO / '_staging'
    if staging.is_dir():
        dirs.extend(p for p in sorted(staging.iterdir()) if p.is_dir())
    return dirs


def resolve_package(name_or_path: str, search: list[Path]) -> Path | None:
    """Resolve a skill name or explicit path to an existing .skill file.
    Returns None (never raises) when nothing is found anywhere -- the MISSING
    finding is the caller's job to report, per the exists-vs-stale distinction."""
    p = Path(name_or_path)
    if p.is_file():
        return p
    filename = name_or_path if name_or_path.endswith('.skill') else f'{name_or_path}.skill'
    for base in _default_search_dirs() + search:
        cand = base / filename
        if cand.is_file():
            return cand
    for base in search:
        if base.is_dir():
            hits = sorted(base.rglob(filename))
            if hits:
                return hits[0]
    return None


def skill_name_from_package(path: Path) -> str:
    return path.stem


def check_entries(z: zipfile.ZipFile, skill: str) -> tuple[list[str], list[str]]:
    """(names, problems). problems is empty iff entries are clean: forward-slash
    only, no directory records, every name under '<skill>/'."""
    names = z.namelist()
    problems = []
    backslash = [n for n in names if '\\' in n]
    dir_recs = [n for n in names if n.endswith('/')]
    wrong_root = [n for n in names if not n.startswith(f'{skill}/')]
    if backslash:
        problems.append(f'{len(backslash)} backslash entr(y/ies) (APPNOTE 4.4.17.1 violation)')
    if dir_recs:
        problems.append(f'{len(dir_recs)} directory record(s)')
    if wrong_root:
        problems.append(f'{len(wrong_root)} entr(y/ies) not under {skill}/')
    return names, problems


def check_freshness(z: zipfile.ZipFile, skill: str) -> dict:
    """SHA256-compare every packaged entry against its repo counterpart. A raw
    byte mismatch is re-compared EOL-normalized (via pending_reimport's own
    comparator, so this can never disagree with the drift ledger about what
    counts as real drift) before it is called drift -- package-and-stage-skill
    step 3's rule. Returns a report dict; never raises on a missing repo file
    (recorded as missing_in_repo instead)."""
    import hashlib
    expected = skill_source_files(skill)  # {rel: abs_path}, repo_root=REPO default
    per_file = []
    real_mismatch = raw_only_eol = missing_in_repo = 0
    for n in z.namelist():
        rel = n[len(skill) + 1:] if n.startswith(f'{skill}/') else n
        pkg_bytes = z.read(n)
        repo_path = expected.get(rel)
        if repo_path is None or not repo_path.is_file():
            missing_in_repo += 1
            per_file.append({'entry': n, 'status': 'REPO-FILE-MISSING'})
            continue
        repo_bytes = repo_path.read_bytes()
        pkg_sha = hashlib.sha256(pkg_bytes).hexdigest()
        if pkg_sha == hashlib.sha256(repo_bytes).hexdigest():
            status = 'MATCH'
        elif _normalized_hash_bytes(pkg_bytes) == _normalized_hash(repo_path):
            status = 'MATCH-EOL-NORMALIZED'
            raw_only_eol += 1
        else:
            status = 'MISMATCH'
            real_mismatch += 1
        # sha256 of the PACKAGED bytes (what actually lands in the runtime cache
        # on install) -- verify_install.ps1 compares the post-click cache copy
        # against this, not the repo file, since a MATCH-EOL-NORMALIZED case can
        # legitimately have a cache byte sequence that differs from the repo's.
        per_file.append({'entry': n, 'rel': rel, 'status': status, 'sha256': pkg_sha})
    packaged_rels = {n[len(skill) + 1:] if n.startswith(f'{skill}/') else n for n in z.namelist()}
    repo_only = sorted(set(expected) - packaged_rels)
    verdict = 'FRESH' if (real_mismatch == 0 and missing_in_repo == 0 and not repo_only) else 'STALE'
    return {
        'per_file': per_file, 'real_mismatch': real_mismatch, 'raw_only_eol': raw_only_eol,
        'missing_in_repo': missing_in_repo, 'repo_only_files': repo_only,
        'expected_count': len(expected), 'verdict': verdict,
    }


def baseline_cache(skill: str) -> dict:
    """Cache-dir CreationTime baseline for the CreationTime discriminator
    verify_install.ps1 uses post-click (package-and-stage-skill step 2/7).
    None means 'no directory' -- the cleanest possible baseline (proves any
    later directory existence is first-hand install evidence)."""
    cache_dir = CACHE_ROOT / skill
    captured_at = datetime.now(timezone.utc).isoformat()
    if not _isdir_long(cache_dir):
        return {'cache_dir': str(cache_dir), 'creation_time': None, 'captured_at': captured_at}
    import os
    ct = datetime.fromtimestamp(os.path.getctime(_win_long(cache_dir)), tz=timezone.utc).isoformat()
    return {'cache_dir': str(cache_dir), 'creation_time': ct, 'captured_at': captured_at}


def precheck_one(name_or_path: str, search: list[Path], stage_to: Path | None,
                  allow_plugin: bool) -> dict:
    import hashlib
    result = {'input': name_or_path, 'verdict': 'REJECT'}
    pkg_path = resolve_package(name_or_path, search)
    if pkg_path is None:
        result['finding'] = 'MISSING'
        result['detail'] = (
            f'no .skill found for {name_or_path!r} at the stated path or under any '
            f'searched dir -- this is MISSING (never built), not STALE. Route back '
            f'through Entry Point A to build it; do not repackage on the strength of '
            f'a handoff claim alone.'
        )
        return result
    skill = skill_name_from_package(pkg_path)
    result['skill'] = skill
    result['package_path'] = str(pkg_path)

    owner = plugin_of(skill)
    if owner and not allow_plugin:
        result['finding'] = 'WRONG-TARGET'
        result['detail'] = (
            f'{skill} is a member of plugin {owner!r} -- a standalone Save-skill '
            f'install lands a shadow copy while the plugin cache stays stale. '
            f'Rebuild via tools/build_plugin.py {owner} <outdir>, or pass '
            f'--allow-plugin if this really is the intended standalone target.'
        )
        return result
    result['plugin_of'] = owner


    pkg_bytes = pkg_path.read_bytes()
    result['package_sha256'] = hashlib.sha256(pkg_bytes).hexdigest()
    result['package_bytes'] = len(pkg_bytes)

    fm_errors = validate_skill_frontmatter(REPO / skill)
    result['frontmatter_errors'] = fm_errors

    with zipfile.ZipFile(pkg_path) as z:
        names, entry_problems = check_entries(z, skill)
        result['entries'] = names
        result['entry_problems'] = entry_problems
        result.update(check_freshness(z, skill))

    ok = (
        not entry_problems and not fm_errors
        and result['verdict'] == 'FRESH'  # set by check_freshness's update() above
    )
    result['verdict'] = 'OK' if ok else 'REJECT'
    if not ok:
        result['finding'] = 'STALE' if result.get('real_mismatch') or result.get('missing_in_repo') \
            or result.get('repo_only_files') else 'ENTRY-OR-FRONTMATTER-DEFECT'

    if ok and stage_to is not None:
        stage_to.mkdir(parents=True, exist_ok=True)
        dest = stage_to / pkg_path.name
        dest.write_bytes(pkg_bytes)
        staged_sha = hashlib.sha256(dest.read_bytes()).hexdigest()
        result['staged_path'] = str(dest)
        result['staged_sha256'] = staged_sha
        result['stage_hash_identical'] = staged_sha == result['package_sha256']
        result['baseline'] = baseline_cache(skill)
        manifest_path = stage_to / f'{skill}.precheck.json'
        manifest_path.write_text(json.dumps(result, indent=2, default=str), encoding='utf-8')
        result['manifest_path'] = str(manifest_path)
    elif stage_to is None:
        result['staged_path'] = None
        result['note'] = 'no --stage-to given; skipped stage + baseline (step 4)'
    return result


def print_report(r: dict) -> None:
    skill = r.get('skill', r['input'])
    print(f'=== {skill} ===')
    if r['verdict'] == 'REJECT' and 'entries' not in r:
        print(f"  {r.get('finding', 'REJECT')}: {r.get('detail', '(no detail)')}")
        return
    print(f"  package: {r['package_path']}  ({r['package_bytes']} bytes, "
          f"sha256 {r['package_sha256'][:16]}...)")
    print(f"  plugin_of: {r.get('plugin_of')}")
    if r['entry_problems']:
        print(f"  ENTRY CHECK: FAIL -- {'; '.join(r['entry_problems'])}")
    else:
        print(f"  ENTRY CHECK: OK ({len(r['entries'])} entries, expected {r['expected_count']})")
    if r['frontmatter_errors']:
        print('  FRONTMATTER: FAIL')
        for e in r['frontmatter_errors']:
            print(f'    {e}')
    else:
        print('  FRONTMATTER: OK')
    print(f"  FRESHNESS: real_mismatch={r['real_mismatch']} raw_only_eol={r['raw_only_eol']} "
          f"missing_in_repo={r['missing_in_repo']} repo_only_files={r['repo_only_files']}")
    for pf in r['per_file']:
        if pf['status'] != 'MATCH':
            print(f"    {pf['entry']}: {pf['status']}")
    if r.get('staged_path'):
        b = r['baseline']
        print(f"  STAGED -> {r['staged_path']}  hash_identical={r['stage_hash_identical']}")
        print(f"  BASELINE cache_dir={b['cache_dir']} creation_time={b['creation_time']} "
              f"(captured {b['captured_at']})")
        print(f"  MANIFEST -> {r['manifest_path']}")
    elif r.get('note'):
        print(f"  {r['note']}")
    print(f"  VERDICT: {r['verdict']}" + (f" ({r['finding']})" if r.get('finding') else ''))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('skills', nargs='+', help='skill name(s) or explicit path(s) to a .skill file')
    ap.add_argument('--search', nargs='*', default=[], type=Path,
                     help='extra directories to sweep (recursively) when a bare name is given')
    ap.add_argument('--stage-to', type=Path, default=None,
                     help='stage verified packages here + write <skill>.precheck.json manifests '
                          '(omit to run checks 0-3/2a only, no step 4)')
    ap.add_argument('--allow-plugin', action='store_true',
                     help='override the plugin-membership routing gate (loud warning, still proceeds)')
    args = ap.parse_args()

    results = [precheck_one(s, args.search, args.stage_to, args.allow_plugin) for s in args.skills]
    for r in results:
        print_report(r)
        if r.get('plugin_of') and args.allow_plugin:
            print(f"  WARNING: --allow-plugin overrode the routing gate for plugin {r['plugin_of']!r}. "
                  f"This installs a standalone shadow copy; the plugin's own loaded copy will NOT update.")
        print()

    ok_count = sum(1 for r in results if r['verdict'] == 'OK')
    print(f'OVERALL: {ok_count}/{len(results)} OK')
    sys.exit(0 if ok_count == len(results) else 1)


if __name__ == '__main__':
    main()
