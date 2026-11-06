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
                           tools/run_suite.sh: every test_*.py under a skill dir, minus any
                           file declaring a top-level CI_EXCLUDE = "<reason>" (listed on stderr).
  suite-continuity --base R  fail if a skill test file present at R is no longer discovered on HEAD
                           (renamed, deleted, or its SKILL.md removed), unless it moved to
                           (a) some file added in R..HEAD under `_archive/` has a path ending
                           `<skill>/<rest>` or `<skill>_retired-YYYY-MM-DD/<rest>` (any depth;
                           path-only, content not compared), or (b) any commit in R..HEAD has a
                           line starting `Suite-Removed: <path>`. (Recommended practice is a git mv
                           to `_archive/<skill>_retired-YYYY-MM-DD` and a trailer on the removing
                           commit; the gate is looser.) Excused
                           suites are listed on stdout. Also fails if the AST-parsed SKIP
                           (last top-level assignment) of HEAD's tools/package_skills.py differs
                           from the imported value (e.g. a mutation via .add/.discard/|=/rebind). R may be `auto`, as for
                           target-markets. Runs in CI only, not in tools/run_skill_suites.sh.
  packaged-layout          package() every skill that declares a SHARED_ROOT_DEPS .py file into
                           a temp dir OUTSIDE the repo (so the dev-checkout sys.path fallback
                           to tools/ cannot resolve), extract it, and confirm each staged
                           script that imports the shared module resolves the packaged copy.
"""
import ast
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


# ---------------------------------------------------------------------------
# Skill-level test suites (F1; auto-discovery since 2026-11-05, maintenance-reduction
# bundle 1 -- the hand-kept GATED/EXCLUDED lists were a recurring follow-up-commit source).
# Every test_*.py under a skill directory is gated automatically. To keep one out of CI,
# put a top-level assignment in that file (parsed with ast, so docstring text never counts):
#     CI_EXCLUDE = "<reason>"
# An exclusion is a follow-up, not a permanent exemption: fix the cause, delete the line.
# The suite-continuity gate (below) catches suites that vanish versus the PR base.
# ---------------------------------------------------------------------------
def ci_exclude_reason(path: Path) -> str | None:
    """The stripped CI_EXCLUDE reason of `path`, or None if it declares none.

    A reason exists only when the module body has a top-level plain assignment
    `CI_EXCLUDE = <str literal>` (single target; trailing comments are fine). Anything else --
    marker text inside a docstring, expressions, annotated assignments, non-str values, a
    nested assignment, a file that does not parse -- leaves the file gated; a syntax error
    surfaces when the suite runs. The returned reason may be '' (callers treat it as an error)."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
    except (SyntaxError, ValueError):
        return None
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == 'CI_EXCLUDE'
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            return node.value.value.strip()
    return None


def excluded_suites(repo: Path = REPO) -> dict[str, str]:
    """Skill test files carrying a CI_EXCLUDE marker -> their (possibly empty) reason."""
    out = {}
    for rel in discover_skill_test_files(repo):
        reason = ci_exclude_reason(repo / rel)
        if reason is not None:
            out[rel] = reason
    return out


def suite_coverage(repo: Path = REPO) -> tuple[list[str], list[str]]:
    """Return (gated_files, errors). Gated = every discovered skill test file without a
    CI_EXCLUDE marker. errors lists any marker whose reason is empty -- an exclusion must
    say why, or it is indistinguishable from an accident."""
    excluded = excluded_suites(repo)
    errors = [f'{rel}: CI_EXCLUDE has an empty reason -- state why it is excluded, or delete '
              f'the line to gate it' for rel, reason in excluded.items() if not reason]
    gated = [rel for rel in discover_skill_test_files(repo) if rel not in excluded]
    return gated, errors


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
    'verified-deal-recon': 'cites the file only as the source its inlined recon-prompt cluster list '
                           'is checked against (tools/doctrine_consistency.py, run in CI on the repo '
                           'copy); the workflow reads nothing at run time',
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


def skills_missing_from_readme(repo: Path = REPO) -> list[str]:
    """CLAUDE.md requires the README skill inventory to be updated whenever a skill is added; this makes
    the rule mechanical. A skill counts as listed when its name appears in backticks anywhere in README.md."""
    readme_path = repo / 'README.md'
    if not readme_path.is_file():
        return []
    readme = readme_path.read_text(encoding='utf-8')
    return [f'{d.name}: not listed in README.md (add it to the skill inventory, in backticks)'
            for d in skill_dirs(repo) if f'`{d.name}`' not in readme]


def cmd_frontmatter() -> int:
    dirs = [d for d in skill_dirs() if is_skill_dir(d.name)]
    fm = [e for d in dirs for e in validate_skill_frontmatter(d)]
    hy = check_tree_hygiene()
    sd = undeclared_shared_deps()
    rd = skills_missing_from_readme()
    for e in fm + hy + sd + rd:
        print(e, file=sys.stderr)
    print(f'frontmatter: {len(dirs)} skills, {len(fm)} error(s); tree hygiene: {len(hy)} '
          f'finding(s); shared-root-dep declarations: {len(sd)} finding(s); '
          f'README inventory: {len(rd)} finding(s)')
    return 1 if (fm or hy or sd or rd) else 0


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
# Suite continuity vs the PR base: auto-discovery gates what exists, so a renamed or deleted
# suite file (or a deleted SKILL.md, which stops discovery of its tests) would otherwise drop
# out of CI silently.
# ---------------------------------------------------------------------------
_SUITE_REMOVED = re.compile(r'^Suite-Removed:[ \t]*(\S.*?)[ \t]*$', re.M)


def _archived_as(rel: str, head_archive_paths: set[str]) -> bool:
    """True if some added archive path is `rel` re-homed under `_archive/`: the skill dir keeps its
    name or takes the standard `<skill>_retired-YYYY-MM-DD` form, and the skill-relative rest is
    identical. Anchored at a path-segment boundary so `_archive/ab/...` never excuses skill `a`."""
    skill, _, rest = rel.partition('/')
    pat = re.compile(rf'(?:^|/){re.escape(skill)}(?:_retired-[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}})?/'
                     rf'{re.escape(rest)}$')
    return any(pat.search(a) for a in head_archive_paths)


def suite_continuity_report(base_files: set[str], head_files: set[str],
                            head_archive_paths: set[str], declared_removed: set[str]
                            ) -> tuple[list[str], dict[str, str]]:
    """(errors, excused). Each base suite file absent from head is excused when a commit declared
    its removal via a Suite-Removed trailer ('Suite-Removed') or it moved under `_archive/` in this
    range ('archive'); otherwise it is an error."""
    errors, excused = [], {}
    for rel in sorted(base_files - head_files):
        if rel in declared_removed:
            excused[rel] = 'Suite-Removed'
        elif _archived_as(rel, head_archive_paths):
            excused[rel] = 'archive'
        else:
            errors.append(f'{rel}: suite present at the PR base is no longer discovered on HEAD '
                          f'(renamed, deleted, or its SKILL.md removed). Restore it, move it to '
                          f'_archive/<skill>/ or _archive/<skill>_retired-YYYY-MM-DD/, or add a '
                          f'"Suite-Removed: {rel}" trailer to the removing commit')
    return errors, excused


def vanished_suites(base_files: set[str], head_files: set[str], head_archive_paths: set[str],
                    declared_removed: set[str]) -> list[str]:
    """Errors only; see suite_continuity_report."""
    return suite_continuity_report(base_files, head_files, head_archive_paths, declared_removed)[0]


_DEFAULT_SKIP = frozenset({'_archive', 'tools', '.git'})


def _parse_skip(source: str) -> set[str] | None:
    """The LAST top-level `SKIP = <literal>` (or annotated) assignment in `source`, evaluated with
    literal_eval (last wins, as Python rebinding does); None if there is none or it is not a
    literal collection of str. `SKIP.add(...)`-style mutation is invisible here by design; the
    head self-consistency check in cmd_suite_continuity catches it."""
    try:
        nodes = ast.parse(source).body
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return None
    value = None
    for node in nodes:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'SKIP' for t in node.targets):
            value = node.value
        elif (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
              and node.target.id == 'SKIP' and node.value is not None):
            value = node.value
    if value is None:
        return None
    if (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
            and value.func.id in ('set', 'frozenset') and len(value.args) == 1
            and not value.keywords):
        value = value.args[0]
    try:
        got = ast.literal_eval(value)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None
    if isinstance(got, (set, frozenset, list, tuple)) and all(isinstance(x, str) for x in got):
        return set(got)
    return None


def base_skip_set(base: str, repo: Path = REPO) -> set[str]:
    """SKIP as written in `tools/package_skills.py` AT `base` (the last top-level assignment,
    parsed with ast and evaluated with literal_eval). Falls back to the default set on ANY
    `git show` failure (file absent at base, bad ref, git error) and when the assignment is
    absent or not a literal. Deliberately not head's SKIP: a head edit that adds a skill to SKIP
    must not hide that skill's base suites."""
    r = _git('show', f'{base}:tools/package_skills.py', repo=repo)
    if r.returncode == 0:
        got = _parse_skip(r.stdout)
        if got is not None:
            return got
    return set(_DEFAULT_SKIP)


def head_skip_inconsistency(repo: Path = REPO) -> bool:
    """True if HEAD's tools/package_skills.py SKIP, as the AST sees it, differs from the SKIP the
    running tool imported (a mutation via `.add`/`.discard`/`|=`, a rebind inside a block, or a computed value would make the
    base-side AST parse untrustworthy). False when the file is absent at HEAD (nothing to check)."""
    r = _git('show', 'HEAD:tools/package_skills.py', repo=repo)
    if r.returncode != 0:
        return False
    return _parse_skip(r.stdout) != set(package_skills.SKIP)


def base_suite_files(base: str, repo: Path = REPO) -> set[str]:
    """test_*.py paths at `base` under a top-level skill dir (one that held a SKILL.md at base),
    minus the dirs in the BASE commit's SKIP (so a merged SKIP addition stops being reported on
    later PRs, while a SKIP edit made on head cannot hide suites). Raises RuntimeError if
    `git ls-tree` fails."""
    r = _git('ls-tree', '-r', '--name-only', '-z', base, repo=repo)
    if r.returncode != 0:
        raise RuntimeError(f'git ls-tree -r {base} failed (rc {r.returncode}): {r.stderr.strip()}')
    skip = base_skip_set(base, repo)
    names = [n for n in r.stdout.split('\0') if n]
    skills = {n.split('/')[0] for n in names if n.count('/') == 1 and n.endswith('/SKILL.md')} - skip
    return {n for n in names
            if n.split('/')[0] in skills and '/' in n and '__pycache__' not in n.split('/')
            and n.rsplit('/', 1)[-1].startswith('test_') and n.endswith('.py')}


def declared_removed_suites(base: str, repo: Path = REPO) -> set[str]:
    """Paths named by `Suite-Removed: <repo-relative path>` lines in base..HEAD commit messages.
    Matches at any line start, not only the final trailer block, deliberately: GitHub squash
    bodies concatenate the PR's commit messages, so a trailer lands mid-body. Raises RuntimeError
    if `git log` fails."""
    r = _git('log', '--format=%B', f'{base}..HEAD', repo=repo)
    if r.returncode != 0:
        raise RuntimeError(f'git log {base}..HEAD failed (rc {r.returncode}): {r.stderr.strip()}')
    return {m.group(1) for m in _SUITE_REMOVED.finditer(r.stdout)}


def archived_suite_paths(base: str, repo: Path = REPO) -> set[str]:
    """`_archive/` test files ADDED in base..HEAD (-M, A only). With the `_archive/` pathspec a
    move from outside the archive always shows as A, never R; an R would only be a copy that
    already lived under `_archive/` at base, which cannot account for a suite deleted in this
    range. Raises RuntimeError if `git diff` fails."""
    r = _git('diff', '--name-only', '-z', '-M', '--diff-filter=A', base, 'HEAD', '--', '_archive/',
             repo=repo)
    if r.returncode != 0:
        raise RuntimeError(f'git diff {base} HEAD -- _archive/ failed (rc {r.returncode}): '
                           f'{r.stderr.strip()}')
    return {n for n in r.stdout.split('\0')
            if n and '__pycache__' not in n.split('/')
            and n.rsplit('/', 1)[-1].startswith('test_') and n.endswith('.py')}


def cmd_suite_continuity(base_arg: str, repo: Path = REPO) -> int:
    base = resolve_base(base_arg, repo=repo)
    ok = _git('rev-parse', '--verify', '--quiet', f'{base}^{{commit}}', repo=repo)
    if ok.returncode != 0:
        print(f'suite-continuity: base {base!r} is not a commit in this clone (fetch-depth: 0?)',
              file=sys.stderr)
        return 2
    try:
        base_files = base_suite_files(base, repo)
        archived = archived_suite_paths(base, repo)
        declared = declared_removed_suites(base, repo)
    except RuntimeError as e:
        print(f'suite-continuity: {e}', file=sys.stderr)
        return 2
    if head_skip_inconsistency(repo):
        print('tools/package_skills.py SKIP must be a single top-level literal set (AST parse '
              'disagrees with the imported value)', file=sys.stderr)
        return 1
    errors, excused = suite_continuity_report(
        base_files, set(discover_skill_test_files(repo)), archived, declared)
    for e in errors:
        print(e, file=sys.stderr)
    if errors:
        return 1
    sha = _git('rev-parse', base, repo=repo).stdout.strip() or base
    for rel, how in sorted(excused.items()):
        print(f'excused: {rel} ({how})')
    if excused:
        print(f'suite-continuity: {len(base_files)} base suite(s), {len(excused)} excused, '
              f'{len(base_files) - len(excused)} present versus base {sha[:12]}')
    else:
        print(f'suite-continuity: {len(base_files)} base suite(s) all present versus base {sha[:12]}')
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
                pkg = package_skills.package(skill, out, allow_dirty_shared=True)  # the real packager, frontmatter gate included; tests staging layout, not what is committed
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
    if cmd == 'suite-continuity':
        if len(argv) != 3 or argv[1] != '--base':
            print('usage: skill_ci_gates.py suite-continuity --base <ref|auto>', file=sys.stderr)
            return 2
        return cmd_suite_continuity(argv[2])
    if cmd == 'suites':
        files, errors = suite_coverage()
        for e in errors:
            print(e, file=sys.stderr)
        if errors:
            return 1
        for rel, reason in sorted(excluded_suites().items()):
            print(f'excluded (CI_EXCLUDE): {rel} -- {reason}', file=sys.stderr)
        print('\n'.join(files))
        return 0
    if cmd == 'packaged-layout':
        return cmd_packaged_layout()
    print(f'unknown subcommand {cmd!r}', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main())
