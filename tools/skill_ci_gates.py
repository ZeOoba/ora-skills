#!/usr/bin/env python3
"""skill_ci_gates.py - repo-wide skill gates for CI (.github/workflows/skill-gates.yml).

WHY (2026-10-03): every skill gate in this repo ran only at commit time
(tools/hooks/pre-commit) or packaging time. core.hooksPath is set per clone, a raw
runtime-cache sync skips both, and `--no-verify` skips the hook outright -- so nothing
server-side ever re-checked the tree, and 13 skill-level test files never ran in CI at
all. This module is the CI-side entry point for those gates. It deliberately reuses the
existing validators (package_skills.validate_skill_frontmatter / check_tree_hygiene /
package / SHARED_ROOT_DEPS) rather than re-implementing any rule, so commit time,
packaging time and CI can never disagree about what is valid.

Subcommands (each exits 0 clean, 1 on a finding, 2 on a usage/environment error):

  frontmatter              validate_skill_frontmatter() over EVERY skill dir (the pre-commit
                           hook only checks dirs with staged changes), plus
                           --check-tree-hygiene, plus the shared-root-dep declaration check.
  target-markets --base R  fail if target-markets.json differs between R and HEAD while its
                           parsed "version" value is unchanged (the pre-commit Check 1 rule,
                           re-run against the PR base so a --no-verify commit can't skip it).
                           R may be `auto` (resolved from GITHUB_REF / GITHUB_EVENT_BEFORE).
  suites                   print the gated skill test files (repo-relative, one per line) for
                           tools/run_suite.sh, after checking that every test_*.py under a
                           skill dir is either gated or explicitly excluded.
  packaged-layout          package() every skill that declares a SHARED_ROOT_DEPS .py file into
                           a temp dir OUTSIDE the repo (so the dev-checkout sys.path fallback
                           to tools/ cannot resolve), extract it, and confirm each staged
                           script that imports the shared module resolves the packaged copy.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import package_skills  # noqa: E402
from package_skills import (  # noqa: E402
    REPO,
    SHARED_ROOT_DEPS,
    _dep_pair,
    check_tree_hygiene,
    is_skill_dir,
    validate_skill_frontmatter,
)

TARGET_MARKETS = 'target-markets.json'

# ---------------------------------------------------------------------------
# Skill-level test suites (F1). Every test_*.py that lives under a skill directory
# must appear in exactly one of these two lists -- `suites` fails on any file in
# neither, so a newly added suite can never silently go ungated.
# Entries are repo-relative globs, expanded by tools/run_suite.sh.
# ---------------------------------------------------------------------------
GATED_SKILL_SUITES = [
    'lease-form-qc/tests/test_*.py',
    'lease-addendum/tests/test_*.py',
    'listing-agreement-qc/tests/test_*.py',
    'lease-generation/tests/test_*.py',
    'dirty-tree-triage/tests/test_*.py',
    'rent-roll-reconciliation/tests/test_*.py',
    'website-perfection/tests/test_*.py',
    'masterlease-jurisdiction-rebase/scripts/test_*.py',
    'acquisition-underwriting-eval-harness/lib/test_aggregate_replays.py',
    'acquisition-underwriting-eval-harness/lib/test_diff_verdict.py',
    'acquisition-underwriting-eval-harness/lib/test_doctrine_skip_gate.py',
]

# path-glob -> reason. Excluded suites are follow-ups, not permanent exemptions: fix the
# cause, then move the entry to GATED_SKILL_SUITES. (pma-qc/tests and vendor-management/tests
# hold fixture .txt files only, no test_*.py, so there is nothing to gate or exclude there.)
EXCLUDED_SKILL_SUITES: dict[str, str] = {
    # Both pass on Windows (local, 2026-10-03) and fail on ubuntu-latest (first skill-gates
    # run, 2026-10-03): the code/tests lean on Windows' case-insensitive filesystem.
    'acquisition-underwriting-eval-harness/lib/test_parse_replays.py':
        'Linux-only FAIL: test_case_differing_duplicate_agent_id_is_still_one_sample '
        'expects duplicate_agent_ids == ["A1B2C3"], gets [] on a case-sensitive FS',
    'acquisition-underwriting-eval-harness/lib/test_record_run.py':
        'Linux-only FAIL: test_refuses_to_clobber_same_timestamp and '
        'test_no_orphaned_tmp_file_after_clobber_refusal -- ValueError not raised',
}


def skill_dirs(repo: Path = REPO) -> list[Path]:
    return [d for d in sorted(repo.iterdir())
            if d.is_dir() and d.name not in package_skills.SKIP and (d / 'SKILL.md').is_file()]


def discover_skill_test_files(repo: Path = REPO) -> list[str]:
    """Every test_*.py under a skill dir (repo-relative posix), excluding bytecode dirs."""
    found = []
    for d in skill_dirs(repo):
        for p in sorted(d.rglob('test_*.py')):
            if '__pycache__' in p.parts:
                continue
            found.append(p.relative_to(repo).as_posix())
    return found


def _expand(globs, repo: Path) -> dict[str, list[str]]:
    return {g: sorted(p.relative_to(repo).as_posix() for p in repo.glob(g) if p.is_file())
            for g in globs}


def suite_coverage(repo: Path = REPO, gated=None, excluded=None) -> tuple[list[str], list[str]]:
    """Return (gated_files, errors). errors lists: a gated/excluded glob matching nothing
    (a renamed suite must not silently vanish), a file both gated and excluded, and a
    discovered skill test file in neither list."""
    gated = GATED_SKILL_SUITES if gated is None else gated
    excluded = EXCLUDED_SKILL_SUITES if excluded is None else excluded
    errors = []
    g_map, x_map = _expand(gated, repo), _expand(list(excluded), repo)
    for label, m in (('gated', g_map), ('excluded', x_map)):
        for glob, files in m.items():
            if not files:
                errors.append(f'{label} suite glob {glob!r} matches no file')
    g_files = sorted({f for fs in g_map.values() for f in fs})
    x_files = {f for fs in x_map.values() for f in fs}
    for f in sorted(set(g_files) & x_files):
        errors.append(f'{f}: listed as both gated and excluded')
    for f in discover_skill_test_files(repo):
        if f not in g_files and f not in x_files:
            errors.append(f'{f}: skill test file is neither gated nor excluded -- add it to '
                          f'GATED_SKILL_SUITES (or EXCLUDED_SKILL_SUITES with a reason) in '
                          f'tools/skill_ci_gates.py')
    return g_files, errors


# ---------------------------------------------------------------------------
# Shared-root-dep declarations (F7). A skill that relies on a repo-root shared file
# at run time must declare it in package_skills.SHARED_ROOT_DEPS, or the packaged
# .skill ships without it (target-markets.json never reached the Cowork cache before
# 2026-07-09 for exactly this reason).
# ---------------------------------------------------------------------------
# Skills whose SKILL.md names target-markets.json without consuming the bundled copy.
TARGET_MARKETS_CITATION_EXEMPT = {
    'owner-outreach': 'its scripts live in a project folder with their own copy and are '
                      'deliberately not bundled (SKILL.md "Scripts" section)',
    'pma-qc': 'mentions target-markets.json only as the precedent for the ora_doc_qc '
              'SHARED_ROOT_DEPS pattern',
    'package-and-stage-skill': 'documents how SHARED_ROOT_DEPS consumers are compared; '
                               'not a consumer itself',
}
_SHARED_PY_IMPORT = re.compile(r'^\s*(?:from\s+ora_doc_qc\s+import|import\s+ora_doc_qc\b)', re.M)


def declared_sources(skill: str, deps=None) -> set[str]:
    deps = SHARED_ROOT_DEPS if deps is None else deps
    return {_dep_pair(d)[0] for d in deps.get(skill, [])}


def undeclared_shared_deps(repo: Path = REPO, deps=None, exempt=None) -> list[str]:
    """Findings for skills that cite a shared root file but do not declare it, and for
    declared deps whose repo-root source is missing (package() would hard-fail)."""
    deps = SHARED_ROOT_DEPS if deps is None else deps
    exempt = TARGET_MARKETS_CITATION_EXEMPT if exempt is None else exempt
    errors = []
    for d in skill_dirs(repo):
        skill = d.name
        have = declared_sources(skill, deps)
        skill_md = (d / 'SKILL.md').read_text(encoding='utf-8', errors='replace')
        if TARGET_MARKETS in skill_md and skill not in exempt and TARGET_MARKETS not in have:
            errors.append(f'{skill}: SKILL.md cites {TARGET_MARKETS} but SHARED_ROOT_DEPS does '
                          f'not declare it (add it, or exempt it with a reason in '
                          f'tools/skill_ci_gates.py TARGET_MARKETS_CITATION_EXEMPT)')
        importers = [p.relative_to(repo).as_posix() for p in sorted(d.rglob('*.py'))
                     if p.relative_to(d).parts[0] != 'tests' and '__pycache__' not in p.parts
                     and _SHARED_PY_IMPORT.search(p.read_text(encoding='utf-8', errors='replace'))]
        if importers and 'tools/ora_doc_qc.py' not in have:
            errors.append(f'{skill}: {", ".join(importers)} import ora_doc_qc but SHARED_ROOT_DEPS '
                          f'does not declare tools/ora_doc_qc.py')
    for skill in sorted(deps):
        if not (repo / skill / 'SKILL.md').is_file():
            errors.append(f'SHARED_ROOT_DEPS key {skill!r} is not a skill directory')
        for src in sorted(declared_sources(skill, deps)):
            if not (repo / src).is_file():
                errors.append(f'{skill}: declared shared dep {src} does not exist')
    return errors


def cmd_frontmatter() -> int:
    dirs = [d for d in skill_dirs() if is_skill_dir(d.name)]
    fm = [e for d in dirs for e in validate_skill_frontmatter(d)]
    hy = check_tree_hygiene()
    sd = undeclared_shared_deps()
    for e in fm + hy + sd:
        print(e, file=sys.stderr)
    print(f'frontmatter: {len(dirs)} skills, {len(fm)} error(s); tree hygiene: {len(hy)} '
          f'finding(s); shared-root-dep declarations: {len(sd)} finding(s)')
    return 1 if (fm or hy or sd) else 0


# ---------------------------------------------------------------------------
# target-markets.json version bump vs base (F2)
# ---------------------------------------------------------------------------
def _git(*args, repo: Path = REPO) -> subprocess.CompletedProcess:
    return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True,
                          encoding='utf-8')


def resolve_base(arg: str, env=None, repo: Path = REPO) -> str:
    """`auto`: push to main -> GITHUB_EVENT_BEFORE (the pre-push tip); any other ref ->
    the fork point with origin/main (what a PR into main is diffed against). Falls back
    to HEAD~1 when the before-sha is absent/all-zero (a new branch, workflow_dispatch)."""
    if arg != 'auto':
        return arg
    env = os.environ if env is None else env
    before = env.get('GITHUB_EVENT_BEFORE', '')
    if env.get('GITHUB_REF') == 'refs/heads/main':
        if before and set(before) != {'0'}:
            return before
        return 'HEAD~1'
    r = _git('merge-base', 'origin/main', 'HEAD', repo=repo)
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip()
    return 'HEAD~1'


def _version_of(text: str):
    return json.loads(text).get('version')


def check_target_markets_version(base_text: str | None, head_text: str | None) -> str | None:
    """Pure rule: None if OK, else an error string. base_text None = file absent at base."""
    if base_text == head_text or head_text is None:
        return None
    try:
        head_v = _version_of(head_text)
    except (ValueError, AttributeError) as e:
        return f'{TARGET_MARKETS}: not valid JSON at HEAD ({e})'
    if head_v in (None, ''):
        return f'{TARGET_MARKETS}: no top-level "version" field at HEAD'
    if base_text is None:
        return None
    try:
        base_v = _version_of(base_text)
    except (ValueError, AttributeError):
        return None  # base was unparseable; HEAD parses and carries a version -- a fix
    if base_v == head_v:
        return (f'{TARGET_MARKETS} changed versus base but "version" is still {head_v!r} -- '
                f'bump "version" (and "updated"); see tools/hooks/pre-commit Check 1')
    return None


def cmd_target_markets(base_arg: str) -> int:
    base = resolve_base(base_arg)
    ok = _git('rev-parse', '--verify', '--quiet', f'{base}^{{commit}}')
    if ok.returncode != 0:
        print(f'target-markets: base {base!r} is not a commit in this clone (fetch-depth: 0?)',
              file=sys.stderr)
        return 2
    b = _git('show', f'{base}:{TARGET_MARKETS}')
    h = _git('show', f'HEAD:{TARGET_MARKETS}')
    err = check_target_markets_version(b.stdout if b.returncode == 0 else None,
                                       h.stdout if h.returncode == 0 else None)
    if err:
        print(err, file=sys.stderr)
        return 1
    state = 'unchanged' if b.stdout == h.stdout else 'changed with version bump'
    print(f'target-markets: {state} versus base {base[:12]}')
    return 0


# ---------------------------------------------------------------------------
# Packaged-layout import check (F1 shared-file staging)
# ---------------------------------------------------------------------------
def staged_import_targets(skill: str, staged_root: Path, deps=None) -> list[tuple[Path, str]]:
    """(script_path, module_name) for each staged *.py that imports a shared .py dep."""
    deps = SHARED_ROOT_DEPS if deps is None else deps
    out = []
    for dep in deps.get(skill, []):
        _src, dest = _dep_pair(dep)
        if not dest.endswith('.py'):
            continue
        mod = Path(dest).stem
        pat = re.compile(rf'^\s*(?:from\s+{mod}\s+import|import\s+{mod}\b)', re.M)
        for p in sorted((staged_root / skill).rglob('*.py')):
            if p.name != f'{mod}.py' and pat.search(p.read_text(encoding='utf-8', errors='replace')):
                out.append((p, mod))
    return out


def cmd_packaged_layout() -> int:
    skills = sorted(s for s, ds in SHARED_ROOT_DEPS.items()
                    if any(_dep_pair(d)[1].endswith('.py') for d in ds))
    errors, checked = [], 0
    with tempfile.TemporaryDirectory(prefix='ora-skill-stage-') as td:
        out, root = Path(td) / 'pkg', Path(td) / 'staged'
        out.mkdir()
        for skill in skills:
            with redirect_stdout(StringIO()):
                pkg = package_skills.package(skill, out)  # the real packager, frontmatter gate included
            with zipfile.ZipFile(pkg) as z:
                z.extractall(root)
            targets = staged_import_targets(skill, root)
            if not targets:
                errors.append(f'{skill}: declares a shared .py dep but no staged script imports it')
            for script, mod in targets:
                checked += 1
                expect = (script.parent / f'{mod}.py').resolve()
                r = subprocess.run(
                    [sys.executable, '-c',
                     f'import sys; sys.path.insert(0, sys.argv[1]); import {script.stem}, {mod}; '
                     f'print({mod}.__file__)', str(script.parent)],
                    capture_output=True, text=True, cwd=td)
                got = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ''
                rel = script.relative_to(root).as_posix()
                if r.returncode != 0:
                    errors.append(f'{rel}: import failed in packaged layout:\n{r.stderr.strip()}')
                elif not got or Path(got).resolve() != expect:
                    errors.append(f'{rel}: {mod} resolved to {got!r}, expected the packaged copy {expect}')
                else:
                    print(f'ok  {rel} -> {Path(got).relative_to(root).as_posix()}')
    for e in errors:
        print(e, file=sys.stderr)
    print(f'packaged-layout: {len(skills)} skill(s), {checked} import(s) checked, {len(errors)} error(s)')
    return 1 if errors else 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__.strip())
        return 0 if argv else 2
    cmd = argv[0]
    if cmd == 'frontmatter':
        return cmd_frontmatter()
    if cmd == 'target-markets':
        if len(argv) != 3 or argv[1] != '--base':
            print('usage: skill_ci_gates.py target-markets --base <ref|auto>', file=sys.stderr)
            return 2
        return cmd_target_markets(argv[2])
    if cmd == 'suites':
        files, errors = suite_coverage()
        for e in errors:
            print(e, file=sys.stderr)
        if errors:
            return 1
        print('\n'.join(files))
        return 0
    if cmd == 'packaged-layout':
        return cmd_packaged_layout()
    print(f'unknown subcommand {cmd!r}', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
