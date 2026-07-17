#!/usr/bin/env python3
"""pending_reimport.py - record which skills a commit left cache-stale.

WHY THIS EXISTS (2026-07-16): the Cowork runtime skill cache only re-syncs after
Gabriel's manual Save-skill click. A session that commits (and pushes) a SKILL.md
or the shared target-markets.json WITHOUT repackaging + reimporting leaves the
runtime on the OLD version until the next drift audit happens to catch it -- this
is exactly how acquisition-underwriting sat at v4.0 after v4.1 (b76bf94) was
committed and pushed by a concurrent session.

This helper is invoked by tools/hooks/post-commit. It CANNOT reimport the cache
(the Save-skill click is manual) -- it DETECTS the repo-ahead-of-cache drift at
commit time and writes a durable, human-visible PENDING-REIMPORT ledger so the gap
can't sit silent. package-and-stage-skill (and the drift check) clear an entry once
a confirmed Save-skill install has re-synced the runtime cache.

RETROACTIVE-BLINDNESS FIX (2026-07-16): the ledger only ever records skills
touched by a commit AFTER this hook existed (e5903c2) -- drift that predates the
hook, or a hook run that failed/was bypassed, is invisible to a consumer that
reads the ledger as authoritative-or-nothing. `sweep_drift()` runs a full
repo-vs-runtime-cache SHA256 comparison (EOL-normalized, reusing is_bundled() so
the packager/hook/sweep can never disagree about what ships) across EVERY
packageable skill, not just ones the hook happened to see. `candidates()` is the
new consumption contract: the UNION of ledger entries and a fresh sweep, never
"ledger OR derive". `backfill()` persists sweep-detected drift into the ledger so
it's durably visible via `list`, not just a one-off in-memory union. Downstream
consumers (ora-skills-reimport-watch, package-and-stage-skill Entry Point A)
should call `candidates`, not `list`, when building their work queue.

Ledger: _staging/PENDING_REIMPORT.md (UNTRACKED local state; see .gitignore).

Usage:
  python tools/pending_reimport.py record [<commit>]     # default HEAD
  python tools/pending_reimport.py list                  # ledger only (raw)
  python tools/pending_reimport.py candidates             # ledger UNION full sweep (always-verify; read-only)
  python tools/pending_reimport.py backfill                # sweep + persist any drift missing from the ledger
  python tools/pending_reimport.py shared-deps             # reconcile shared repo-root deps, direction-aware (reimport vs commit)
  python tools/pending_reimport.py clear <skill> [...]    # after confirmed reimport
"""
import hashlib
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Reuse the packager's single source of truth for the shared-dep fan-out + skip set,
# so this helper and package_skills.py can never disagree about which skills bundle
# a repo-root dependency.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_skills import REPO, SKIP, SHARED_ROOT_DEPS, is_bundled, plugin_of  # noqa: E402

LEDGER = REPO / '_staging' / 'PENDING_REIMPORT.md'

# Same physical store package-and-stage-skill and ora-skill-store-drift-check
# already treat as canonical (README "Dual-write discipline"; both SKILL.mds
# hardcode this path). Not configurable via env var by design -- one machine,
# one cache, and the doctrine already hardcodes it elsewhere; a stray override
# would let a sweep silently compare against the wrong store.
CACHE_ROOT = Path(
    r'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin'
    r'\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'
)

# reverse map: shared repo-root file -> [consumer skills that bundle it]
SHARED_CONSUMERS: dict[str, list[str]] = {}
for _skill, _deps in SHARED_ROOT_DEPS.items():
    for _d in _deps:
        SHARED_CONSUMERS.setdefault(_d, []).append(_skill)

HEADER = (
    '# PENDING REIMPORT — repo is ahead of the Cowork runtime cache\n'
    '#\n'
    '# UNTRACKED local state (see .gitignore). Written by tools/hooks/post-commit.\n'
    '# Each line = a skill whose PACKAGED content was committed but NOT yet reimported\n'
    '# into the runtime cache (Save-skill click is manual). Clear a line after a\n'
    '# CONFIRMED Save-skill install re-syncs the cache:\n'
    '#   python tools/pending_reimport.py clear <skill>\n'
    '# To act on a pending skill: package_skills.py -> present .skill -> Save-skill click.\n'
    '\n'
)


def _git(*args: str) -> str:
    return subprocess.run(
        ['git', '-C', str(REPO), *args],
        capture_output=True, text=True, check=True,
    ).stdout


def changed_files(commit: str) -> list[str]:
    out = _git('diff-tree', '--no-commit-id', '--name-only', '-r', commit)
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def is_skill_dir(top: str) -> bool:
    return top not in SKIP and (REPO / top / 'SKILL.md').is_file()


def affected_skills(files: list[str]) -> dict[str, set[str]]:
    """Map committed files -> skills needing reimport, with the triggering paths."""
    hits: dict[str, set[str]] = {}
    for f in files:
        parts = f.split('/')
        top = parts[0]
        # (a) a bundled file inside a skill directory. is_bundled() (imported from the
        #     packager) is the shared rule for what ships — excludes PACKAGING-NOTE.md and
        #     top-level versions/ archives, so a versions/-only commit never falsely flags
        #     a reimport (2026-07-16: cowork-settings/versions/ snapshot did exactly that).
        if len(parts) > 1 and is_skill_dir(top) and is_bundled('/'.join(parts[1:])):
            hits.setdefault(top, set()).add(f)
        # (b) a repo-root shared dependency fans out to every consumer skill.
        if '/' not in f and f in SHARED_CONSUMERS:
            for consumer in SHARED_CONSUMERS[f]:
                hits.setdefault(consumer, set()).add(f'{f} (shared dep)')
    return hits


def read_entries(ledger_path: Path = LEDGER) -> dict[str, str]:
    """Parse existing ledger into {skill: full_line} (skips comments/blanks)."""
    entries: dict[str, str] = {}
    if not ledger_path.is_file():
        return entries
    for ln in ledger_path.read_text(encoding='utf-8').splitlines():
        s = ln.strip()
        if not s or s.startswith('#'):
            continue
        if s.startswith('- '):
            skill = s[2:].split('|', 1)[0].strip()
            if skill:
                entries[skill] = s
    return entries


def write_entries(entries: dict[str, str], ledger_path: Path = LEDGER) -> None:
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if not entries:
        # nothing pending -> remove the ledger so its mere presence always means "work to do"
        if ledger_path.is_file():
            ledger_path.unlink()
        return
    body = '\n'.join(entries[k] for k in sorted(entries)) + '\n'
    ledger_path.write_text(HEADER + body, encoding='utf-8')


def _normalized_hash_bytes(data: bytes) -> str:
    """SHA256 of content, CRLF->LF normalized when it decodes as text. Bytes form
    (see _normalized_hash) so a git blob's content can be hashed the same way a
    working-tree/cache file is, for the shared-dep direction check."""
    try:
        data = data.decode('utf-8').replace('\r\n', '\n').encode('utf-8')
    except UnicodeDecodeError:
        pass  # binary file: compare raw bytes, EOL normalization doesn't apply
    return hashlib.sha256(data).hexdigest()


def _normalized_hash(path: Path) -> str:
    """SHA256 of a file's content, CRLF->LF normalized when the file decodes as text.

    Matches the EOL rule already codified in package-and-stage-skill and
    ora-skill-store-drift-check: git autocrlf gives Windows working copies CRLF
    while the platform import stores LF, so a raw-byte hash reads perpetually
    "drifted" on line endings alone. A raw-only mismatch is in-sync, not drift.
    """
    return _normalized_hash_bytes(path.read_bytes())


def _skill_source_files(repo_root: Path, skill: str) -> dict[str, Path]:
    """{relative posix path: absolute path} for every file package_skills.py
    would ship for this skill -- its own bundled files plus any repo-root
    SHARED_ROOT_DEPS fan-out, the same two sources package() zips together."""
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


def skill_drifted(repo_root: Path, cache_root: Path, skill: str) -> bool:
    """True if the skill is installed (has a cache dir) AND any shipped file
    differs (EOL-normalized) or is missing under it.

    A skill with NO cache dir at all was never installed -- that's
    ora-skill-store-drift-check's separate REPO-ONLY category (step 3), not
    "drifted, needs reimport". Confirmed against the live repo: 7 skills
    migrated from the ora-operations-extensions plugin (annual-cycle,
    capex-budgeting, cash-position-monitor, deal-retirement,
    investor-relations, submarket-spatial-analysis, vendor-management) plus
    cowork-settings and 2 in-progress skills have no cache dir today and are
    not reimport candidates -- flagging them would flood the ledger with
    "never installed" noise indistinguishable from real "went stale" drift.
    """
    cache_dir = cache_root / skill
    if not cache_dir.is_dir():
        return False
    for rel, src_path in _skill_source_files(repo_root, skill).items():
        cache_file = cache_dir / rel
        if not cache_file.is_file():
            return True
        if _normalized_hash(src_path) != _normalized_hash(cache_file):
            return True
    return False


def all_skill_dirs(repo_root: Path) -> list[str]:
    return sorted(
        d.name for d in repo_root.iterdir()
        if d.is_dir() and d.name not in SKIP and (d / 'SKILL.md').is_file()
    )


def sweep_drift(repo_root: Path = REPO, cache_root: Path = CACHE_ROOT) -> list[str]:
    """Full repo-vs-cache SHA256 sweep across EVERY packageable skill -- not just
    ones a post-commit hook happened to see. Catches drift that predates the
    hook's existence or a hook run that failed/was bypassed. Never fabricates:
    an unreachable cache root (unattended session, wrong machine) yields no
    findings rather than flagging every skill as drifted."""
    if not cache_root.is_dir():
        return []
    return [s for s in all_skill_dirs(repo_root) if skill_drifted(repo_root, cache_root, s)]


def candidates(
    repo_root: Path = REPO, cache_root: Path = CACHE_ROOT, ledger_path: Path = LEDGER,
) -> dict[str, str]:
    """The consumption contract for every downstream consumer: UNION of ledger
    entries and a fresh full sweep, never "ledger OR derive". Read-only -- never
    writes the ledger (see backfill() to persist sweep findings)."""
    result = dict(read_entries(ledger_path))
    for skill in sweep_drift(repo_root, cache_root):
        result.setdefault(
            skill,
            f'- {skill} | source: sweep (no ledger entry) | trigger: full repo-vs-cache SHA256 sweep',
        )
    return result


def backfill(
    repo_root: Path = REPO, cache_root: Path = CACHE_ROOT, ledger_path: Path = LEDGER,
) -> list[str]:
    """Run a full sweep and PERSIST any drifted skill missing from the ledger,
    so it becomes durably visible via `list` (not just a one-off union computed
    by `candidates`). Never touches an entry that's already in the ledger --
    a real commit-hash entry is never clobbered by a backfill stub."""
    entries = read_entries(ledger_path)
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    seeded = []
    for skill in sweep_drift(repo_root, cache_root):
        if skill in entries:
            continue
        entries[skill] = (
            f'- {skill} | pending since {now} | backfill sweep (predates hook or hook was bypassed) '
            f'| trigger: full repo-vs-cache SHA256 sweep'
        )
        seeded.append(skill)
    write_entries(entries, ledger_path)
    return seeded


# ---------------------------------------------------------------------------
# Shared repo-root dependency reconciliation (2026-07-16).
#
# sweep_drift() already SEES a shared-dep mismatch, but reports it once per
# consuming skill with no direction -- so a reader can't tell a stale cache
# (fix = repackage + reimport) from runtime-only content that was never
# committed (fix = commit it back; a reimport would DOWNGRADE the runtime).
# That ambiguity is exactly what made the 2026-07-16 target-markets.json
# episode read the wrong way round by eye. This block reconciles each shared
# file ONCE and labels it with a git-history-derived direction.
# ---------------------------------------------------------------------------

# Actionable one-liner per direction, keyed by the classify_shared_copy() label.
SHARED_DEP_ACTION = {
    'IN-SYNC': 'in sync',
    'REPO-AHEAD': 'repackage + reimport (cache is a stale older version)',
    'CACHE-AHEAD': 'commit the runtime content back to the repo — do NOT reimport (would DOWNGRADE the runtime)',
    'DIVERGENT': 'manual review — cache matches an off-HEAD commit; do NOT auto-reimport',
    'REPO-MISSING': 'stale shared-dep declaration — repo file is gone (fix SHARED_ROOT_DEPS)',
    'MISSING-IN-CACHE': 'repackage + reimport (shared file absent from an installed skill)',
    'NOT-INSTALLED': 'consumer skill has no cache dir — never installed (not drift)',
    'UNKNOWN': 'git history unavailable — verify direction by hand',
}

# States that need no action: cache agrees with repo, or the skill was never installed.
SHARED_DEP_CLEAN = {'IN-SYNC', 'NOT-INSTALLED'}


def classify_shared_copy(cache_hash, repo_hash, ancestor_hashes, all_history_hashes):
    """Direction of ONE cached shared-dep copy vs the repo. PURE — no I/O, so the
    branch logic is unit-tested without a git fixture.

    ancestor_hashes/all_history_hashes are EOL-normalized content hashes of the
    repo file at, respectively, every commit on HEAD's ancestry and every commit
    on any branch. Passing ancestor_hashes=None means git was unavailable.

      IN-SYNC       cache == repo working file                     -> nothing to do
      REPO-AHEAD    cache is an older point on HEAD's own history   -> REIMPORT upgrades it
      CACHE-AHEAD   cache content was never committed anywhere      -> UPDATE REPO (reimport downgrades)
      DIVERGENT     cache matches a commit OFF HEAD's ancestry      -> manual; do not auto-reimport
      REPO-MISSING  repo has no such file                           -> shared-dep declaration is stale
      UNKNOWN       git history unavailable                         -> verify by hand
    """
    if repo_hash is None:
        return 'REPO-MISSING'
    if cache_hash == repo_hash:
        return 'IN-SYNC'
    if ancestor_hashes is None:
        return 'UNKNOWN'
    if cache_hash in ancestor_hashes:
        return 'REPO-AHEAD'
    if all_history_hashes and cache_hash in all_history_hashes:
        return 'DIVERGENT'
    return 'CACHE-AHEAD'


def _git_text(repo_root: Path, *args: str):
    """Run git in repo_root; stdout str, or None if git is missing or the command
    fails (untracked path, not a repo). Never raises -- callers degrade to UNKNOWN."""
    try:
        r = subprocess.run(['git', '-C', str(repo_root), *args],
                           capture_output=True, text=True)
    except (OSError, ValueError):
        return None
    return r.stdout if r.returncode == 0 else None


def _git_blob_bytes(repo_root: Path, rev: str, relpath: str):
    try:
        r = subprocess.run(['git', '-C', str(repo_root), 'show', f'{rev}:{relpath}'],
                           capture_output=True)
    except (OSError, ValueError):
        return None
    return r.stdout if r.returncode == 0 else None


def _file_history_hashes(repo_root: Path, relpath: str):
    """(ancestor_hashes, all_history_hashes) EOL-normalized content hashes of
    relpath across HEAD's ancestry and across all branches. (None, None) when git
    is unavailable or the file is untracked, so classify_shared_copy -> UNKNOWN."""
    head = _git_text(repo_root, 'rev-list', 'HEAD', '--', relpath)
    if head is None:
        return None, None

    def _hashes(rev_text):
        out = set()
        for rev in rev_text.split():
            data = _git_blob_bytes(repo_root, rev, relpath)
            if data is not None:
                out.add(_normalized_hash_bytes(data))
        return out

    all_text = _git_text(repo_root, 'rev-list', '--all', '--', relpath) or ''
    return _hashes(head), _hashes(all_text)


def shared_dep_report(repo_root: Path = REPO, cache_root: Path = CACHE_ROOT):
    """Reconcile every shared repo-root dependency (SHARED_ROOT_DEPS, reversed into
    SHARED_CONSUMERS) against each consumer skill's cached copy. Returns
    {dep_filename: {consumer_skill: STATUS}}, deduped to one shared file per row."""
    report: dict[str, dict[str, str]] = {}
    for dep in sorted(SHARED_CONSUMERS):
        repo_file = repo_root / dep
        repo_hash = _normalized_hash(repo_file) if repo_file.is_file() else None
        ancestor_hashes, all_history_hashes = _file_history_hashes(repo_root, dep)
        rows: dict[str, str] = {}
        for skill in sorted(SHARED_CONSUMERS[dep]):
            if not (cache_root / skill).is_dir():
                rows[skill] = 'NOT-INSTALLED'
            elif not (cache_root / skill / dep).is_file():
                rows[skill] = 'MISSING-IN-CACHE'
            else:
                rows[skill] = classify_shared_copy(
                    _normalized_hash(cache_root / skill / dep),
                    repo_hash, ancestor_hashes, all_history_hashes,
                )
        report[dep] = rows
    return report


def shared_dep_problems(report):
    """Flatten a shared_dep_report() into [(dep, skill, status)] for every copy that
    isn't clean -- the actionable rows a drift audit should surface."""
    return [
        (dep, skill, status)
        for dep, rows in report.items()
        for skill, status in sorted(rows.items())
        if status not in SHARED_DEP_CLEAN
    ]


def format_ledger_line(skill, when, shorthash, subject, trig, owner=None):
    """Build one ledger line. PURE (no I/O) so the plugin-routing branch is unit-
    tested without a git fixture. A plugin-bundled skill (owner not None) must NOT
    be routed to the standalone Save-skill remedy — that installs a shadow copy
    while the plugin's loaded copy stays stale (deal-retirement /
    submarket-spatial-analysis, 2026-07-16). It is tagged with its owning plugin
    and the plugin-rebuild remedy so package-and-stage-skill Entry A routes to
    tools/build_plugin.py instead."""
    line = f'- {skill} | pending since {when} | commit {shorthash} "{subject}" | trigger: {trig}'
    if owner:
        line += (
            f' | plugin: {owner} | remedy: rebuild plugin '
            f'(python tools/build_plugin.py {owner} <outdir>) — NOT a standalone Save-skill'
        )
    return line


def cmd_record(commit: str) -> None:
    files = changed_files(commit)
    hits = affected_skills(files)
    if not hits:
        return
    shorthash = _git('rev-parse', '--short', commit).strip()
    subject = _git('log', '-1', '--format=%s', commit).strip().replace('|', '/')
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    entries = read_entries()
    for skill, triggers in hits.items():
        trig = ', '.join(sorted(triggers))
        entries[skill] = format_ledger_line(
            skill, now, shorthash, subject, trig, plugin_of(skill)
        )
    write_entries(entries)
    print(f'pending_reimport: recorded {len(hits)} skill(s) -> {LEDGER}')
    for skill in sorted(hits):
        print(f'   {skill}')


def cmd_list() -> None:
    entries = read_entries()
    if not entries:
        print('pending_reimport: none pending (cache in sync with repo)')
        return
    print(f'pending_reimport: {len(entries)} skill(s) awaiting Save-skill reimport:')
    for skill in sorted(entries):
        print(f'   {entries[skill]}')


def cmd_candidates() -> None:
    """Read-only: ledger UNION full sweep. This is what a downstream consumer
    (ora-skills-reimport-watch STEP 1a, package-and-stage-skill Entry Point A)
    should call to build its work queue instead of `list` alone."""
    result = candidates()
    if not result:
        print('pending_reimport: no candidates (ledger empty and full sweep found no drift)')
    else:
        print(f'pending_reimport: {len(result)} candidate(s) (ledger UNION full sweep):')
        for skill in sorted(result):
            print(f'   {result[skill]}')
    # A shared-dep mismatch shows up in the sweep once per consumer with no direction;
    # append the deduped, direction-aware view so the audit says reimport vs commit.
    _print_shared_dep_advisory()


def cmd_backfill() -> None:
    seeded = backfill()
    if not seeded:
        print('pending_reimport: backfill found no drift beyond what the ledger already tracks')
        return
    print(f'pending_reimport: backfill seeded {len(seeded)} skill(s) -> {LEDGER}')
    for skill in sorted(seeded):
        print(f'   {skill}')


def cmd_clear(skills: list[str]) -> None:
    entries = read_entries()
    cleared = [s for s in skills if entries.pop(s, None) is not None]
    write_entries(entries)
    if cleared:
        print(f'pending_reimport: cleared {", ".join(cleared)}')
    missing = [s for s in skills if s not in cleared]
    if missing:
        print(f'pending_reimport: not pending (nothing to clear): {", ".join(missing)}')


def cmd_shared_deps() -> None:
    """Reconcile shared repo-root deps against the runtime cache, one row per file,
    with a direction so a reader never guesses reimport-vs-commit by eye."""
    report = shared_dep_report()
    problems = shared_dep_problems(report)
    print('pending_reimport: shared repo-root dependency reconciliation')
    for dep, rows in report.items():
        clean = all(s in SHARED_DEP_CLEAN for s in rows.values())
        print(f'  {dep}: {"OK" if clean else "DRIFT"}')
        for skill, status in sorted(rows.items()):
            if status in SHARED_DEP_CLEAN:
                continue
            print(f'     {skill}: {status} -> {SHARED_DEP_ACTION.get(status, status)}')
        in_sync = sorted(s for s, v in rows.items() if v == 'IN-SYNC')
        if in_sync:
            print(f'     in sync: {", ".join(in_sync)}')
    if not problems:
        print('  all shared-dep copies reconcile with the repo')


def _print_shared_dep_advisory() -> None:
    """Terse shared-dep drift block appended to `candidates` so the drift audit
    surfaces shared-file direction inline (dedup of the per-skill sweep rows)."""
    problems = shared_dep_problems(shared_dep_report())
    if not problems:
        return
    print(f'pending_reimport: {len(problems)} shared-dep advisory row(s) (direction-aware):')
    for dep, skill, status in problems:
        print(f'   {dep} @ {skill}: {status} -> {SHARED_DEP_ACTION.get(status, status)}')


def main() -> None:
    argv = sys.argv[1:]
    cmd = argv[0] if argv else 'list'
    if cmd == 'record':
        cmd_record(argv[1] if len(argv) > 1 else 'HEAD')
    elif cmd == 'list':
        cmd_list()
    elif cmd == 'candidates':
        cmd_candidates()
    elif cmd == 'backfill':
        cmd_backfill()
    elif cmd == 'shared-deps':
        cmd_shared_deps()
    elif cmd == 'clear':
        if len(argv) < 2:
            raise SystemExit('usage: pending_reimport.py clear <skill> [...]')
        cmd_clear(argv[1:])
    else:
        raise SystemExit(__doc__.strip())


if __name__ == '__main__':
    # post-commit must never disrupt the commit: swallow everything on the record path.
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f'pending_reimport: skipped ({exc})', file=sys.stderr)
        sys.exit(0)
