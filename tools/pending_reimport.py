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
consumers (package-and-stage-skill Entry Point A) should call `candidates`,
not `list`, when building their work queue. NOTE 2026-09-07: this docstring and
cmd_candidates() both named `ora-skills-reimport-watch` as a consumer; that task
exists on NEITHER fleet (checked against both live registries) and is a dead
pointer -- do not go looking for it, and do not re-create it on the strength of
this reference alone. The live consumers are package-and-stage-skill Entry Point A
and, since 2026-09-07, the `ora-doctrine-integrity-guard` CC/MCP task, which runs
`backfill` daily as its ninth engine to catch drift from commits made in another
checkout (the post-commit hook only ever fires in the checkout that committed).

Ledger: <primary checkout>/_staging/PENDING_REIMPORT.md (UNTRACKED local state; see
.gitignore) -- the PRIMARY checkout's, even when run from a git worktree.

Usage:
  python tools/pending_reimport.py record [<commit>]     # default HEAD
  python tools/pending_reimport.py list                  # ledger only (raw)
  python tools/pending_reimport.py candidates             # ledger UNION full sweep (always-verify; read-only)
  python tools/pending_reimport.py backfill                # sweep + persist any drift missing from the ledger
  python tools/pending_reimport.py shared-deps             # reconcile shared repo-root deps, direction-aware (reimport vs commit)
  python tools/pending_reimport.py clear <skill> [...]    # after confirmed reimport
  python tools/pending_reimport.py clear --force <skill> [...]   # override the log-before-clear guard (see cmd_clear)

LOG-BEFORE-CLEAR GUARD (2026-09-07, Automation Audit systematization candidate):
`clear` refuses each named skill unless it is named in the NEWEST dated ('## '
YYYY-MM-DD) entry in memory/event_log.md -- mechanizing, rather than trusting to
discipline alone, package-and-stage-skill step 7's "log the confirmed install,
THEN clear -- never the reverse" ordering. Exists because a 2026-08-14 close-out
cleared the ledger while its own event_log append had failed on the header rule,
inverting that ordering silently. Fail-CLOSED by design (refuses on an unreadable
or headerless log) -- this is the opposite of append-event-log.py's fail-OPEN
philosophy, deliberately: a missing log entry is exactly the failure this guard
exists to catch, so silently proceeding would defeat its own purpose. `--force`
overrides it for a genuine edge case (skips the check for every skill named in
this invocation) and is never silent -- it prints why the guard would have
refused before proceeding.
"""
import contextlib
import hashlib
import os
import random
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# Reuse the packager's single source of truth for the shared-dep fan-out + skip set,
# so this helper and package_skills.py can never disagree about which skills bundle
# a repo-root dependency.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_skills import (  # noqa: E402
    REPO, SKIP, SHARED_ROOT_DEPS, DELIBERATELY_UNPUBLISHED, CODE_ONLY_SKILLS, is_bundled, plugin_of,
    skill_source_files, _dep_pair,
)
from skill_md_normalize import normalize_skill_md_text  # noqa: E402

def _primary_checkout(repo_root: Path) -> Path:
    """The primary checkout that `repo_root` shares its git dir with; repo_root
    itself when it IS the primary, or when git can't say (missing, not a repo,
    bare/submodule layout). The ledger is untracked gitignored state: resolved
    against a worktree it lands in that worktree's _staging/ and dies with
    `git worktree remove` (2026-09-23, isolated-commit #77's entry stranded)."""
    # No --path-format=absolute: git < 2.31 echoes an unknown rev-parse option
    # back on stdout with exit 0 instead of failing. A relative answer is
    # relative to repo_root (-C), so resolve it ourselves.
    try:
        r = subprocess.run(['git', '-C', str(repo_root), 'rev-parse', '--git-common-dir'],
                           capture_output=True, text=True)
    except (OSError, ValueError):
        return repo_root
    lines = r.stdout.strip().splitlines() if r.returncode == 0 else []
    if len(lines) != 1:
        return repo_root
    common = Path(lines[0])
    common = (common if common.is_absolute() else repo_root / common).resolve()
    if common.name != '.git' or not common.is_dir():
        return repo_root
    return common.parent


def _ledger_path(repo_root: Path) -> Path:
    return _primary_checkout(repo_root) / '_staging' / 'PENDING_REIMPORT.md'


LEDGER = _ledger_path(REPO)

# Same canonical event_log.md the append-event-log.py maintenance script writes
# (~/.claude/maintenance/append-event-log.py's own LOG constant) -- duplicated
# here rather than imported because that script lives in a sibling repo
# (~/.claude), not under ora-skills/tools. Not configurable by env var, same
# reasoning as CACHE_ROOT above: one machine, one canonical log, and a stray
# override would let the clear-guard below silently check the wrong file.
EVENT_LOG = Path(os.path.expanduser('~')) / '.claude' / 'projects' / \
    'C--Users-Owner-OneDrive---Oxford-Capital-Partners' / 'memory' / 'event_log.md'

_ENTRY_HEADER_RE = re.compile(r'^## \d{4}-\d{2}-\d{2}\b')

# Same physical store package-and-stage-skill and ora-skill-store-drift-check
# already treat as canonical (README "Dual-write discipline"; both SKILL.mds
# hardcode this path). Not configurable via env var by design -- one machine,
# one cache, and the doctrine already hardcodes it elsewhere; a stray override
# would let a sweep silently compare against the wrong store.
CACHE_ROOT = Path(
    r'C:\Users\Owner\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin'
    r'\583f08bc-0123-4111-8158-8fe3d927e350\a6ad2c61-c3c8-4a48-98a5-e40c1db22ad3\skills'
)

# reverse map: shared repo-root file -> [(consumer skill, skill-relative dest path)]
SHARED_CONSUMERS: dict[str, list[tuple[str, str]]] = {}
for _skill, _deps in SHARED_ROOT_DEPS.items():
    for _d in _deps:
        _src, _dest = _dep_pair(_d)
        SHARED_CONSUMERS.setdefault(_src, []).append((_skill, _dest))

HEADER = (
    '# PENDING REIMPORT — repo is ahead of the Cowork runtime cache\n'
    '#\n'
    '# UNTRACKED local state (see .gitignore). Written by tools/hooks/post-commit.\n'
    '# Each line = a skill whose PACKAGED content was committed but NOT yet reimported\n'
    '# into the runtime cache (Save-skill click is manual). Clear a line after a\n'
    '# CONFIRMED Save-skill install re-syncs the cache:\n'
    '#   python tools/pending_reimport.py clear <skill>\n'
    '# To act on a pending skill: package_skills.py -> present .skill -> Save-skill click.\n'
    '#\n'
    '# THIS IS NOT AN INSTALL ORACLE. The ledger is cleared BY HAND after the fact, so a\n'
    '# line here means only "nobody has cleared it yet" -- it does NOT mean the skill is\n'
    '# uninstalled. To decide whether an install actually happened, in this order:\n'
    '#   1. AppData\\Roaming\\Claude\\logs\\main.log -- a non-zero "Delta: N to download"\n'
    '#      followed by "Sync complete". The post-commit copy produces NO SkillsPlugin log\n'
    '#      activity, so a non-zero delta cannot be manufactured by this tooling.\n'
    '#   2. Runtime-cache mtime against a pre-click baseline.\n'
    '#   3. Hash vs repo -- confirms WHAT installed, never WHETHER.\n'
    '# 2026-08-03: a session read this ledger two minutes after a confirmed Save-skill\n'
    '# click and reported the skill uninstalled. See memory/reference_skill_reimport_sync_lag.md.\n'
    '\n'
)


def _git(*args: str) -> str:
    return subprocess.run(
        ['git', '-C', str(REPO), *args],
        capture_output=True, text=True, check=True,
    ).stdout


def changed_files(commit: str) -> list[str]:
    """Files a commit changed, MERGES INCLUDED.

    `-m --first-parent` is load-bearing (2026-09-07, Automation Audit R23
    close-out): without it `git diff-tree -r <merge>` prints NOTHING at all for a
    merge commit, so cmd_record() saw no hits and the post-commit hook wrote no
    PENDING-REIMPORT line for anything a branch brought in. That is how
    package-and-stage-skill (577397f, merged as db7ea76) and tenant-intelligence
    (00c553b, merged as 3a2f352) both landed changed packaged SKILL.md content
    with no ledger entry -- the store kept serving pre-merge bytes under a version
    token that already read current, which the token can never reveal.

    `--first-parent` (not `-c`/`--cc`) is the right diff for this consumer: the
    question is "what did this commit change on the branch it landed on", i.e.
    everything the merge brought in, not just conflict-resolved hunks. On a
    non-merge commit the pair is a no-op -- output is byte-identical to the plain
    form (covered by test_non_merge_commit_file_list_is_unchanged), and a root
    commit still yields [] rather than raising.

    NOTE this closes only the merge half of the R23 gap. The other half is not
    fixable here: those four branch commits were authored in a DIFFERENT working
    tree (this checkout's reflog never held them), and the ledger is gitignored
    local state, so whatever the hook recorded over there never travelled with the
    merge. Re-verify with `candidates` (ledger UNION sweep), never `list` alone.
    """
    out = _git('diff-tree', '--no-commit-id', '--name-only', '-r',
               '-m', '--first-parent', commit)
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
        if f in SHARED_CONSUMERS:
            for consumer, _dest in SHARED_CONSUMERS[f]:
                hits.setdefault(consumer, set()).add(f'{f} (shared dep)')
    return hits


def _retry_locked(op):
    """Run op(), retrying briefly on PermissionError. On Windows os.replace fails while
    any reader holds the target open, and a reader opening mid-rename fails the same
    way (Python's open() doesn't share delete access). Both sides hold the file for
    milliseconds, so a short bounded retry covers them; a persistent lock re-raises."""
    for attempt in range(5):
        try:
            return op()
        except PermissionError:
            if attempt == 4:
                raise
            time.sleep(0.05 * (attempt + 1))


def _read_text_retry(path: Path) -> str:
    return _retry_locked(lambda: path.read_text(encoding='utf-8'))


def _atomic_write_text(path: Path, text: str) -> None:
    """Write-then-rename: Path.write_text truncates the target before writing, so a
    write that died midway left an EMPTY file. A same-directory temp file plus
    os.replace leaves either the old content or the new, never a torn file. Atomic
    per write only -- a read-modify-write must go through update_entries(), which
    holds the ledger's cross-process lock, or a concurrent writer's update is lost."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f'.{path.name}.', suffix='.tmp')
    try:
        with open(fd, 'w', encoding='utf-8') as f:
            f.write(text)
        _retry_locked(lambda: os.replace(tmp, path))
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_entries(ledger_path: Path = LEDGER) -> dict[str, str]:
    """Parse existing ledger into {skill: full_line} (skips comments/blanks)."""
    entries: dict[str, str] = {}
    if not ledger_path.is_file():
        return entries
    try:
        text = _read_text_retry(ledger_path)
    except FileNotFoundError:        # a concurrent clear deleted it after is_file()
        return entries
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith('#'):
            continue
        if s.startswith('- '):
            skill = s[2:].split('|', 1)[0].strip()
            if skill:
                entries[skill] = s
    return entries


def write_entries(entries: dict[str, str], ledger_path: Path = LEDGER, header: str = HEADER) -> None:
    """`header` is parameterized (default = this module's own PENDING_REIMPORT
    header) so tools/repo_first_check.py can reuse this same read/write/empty-file-
    deletes convention for its own STORE_AHEAD_OF_REPO ledger -- the reverse-
    direction companion -- without writing the wrong header into it. A bare write
    with no lock: callers that read first go through update_entries()."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if not entries:
        # nothing pending -> remove the ledger so its mere presence always means "work to do"
        if ledger_path.is_file():
            _retry_locked(lambda: ledger_path.unlink(missing_ok=True))
        return
    body = '\n'.join(entries[k] for k in sorted(entries)) + '\n'
    _atomic_write_text(ledger_path, header + body)


# Cross-process lock for every ledger read-modify-write (2026-09-24). write_entries()
# is atomic per write, but read_entries -> mutate -> write_entries is not: two
# processes that both read before either writes each drop the other's update. The
# ledgers live in the PRIMARY checkout's _staging/, shared by every worktree's
# post-commit hook, the daily backfill and repo_first_check's sweep, so concurrent
# writers are routine. PR #79's merge gate (race finding F2, 3 processes x 200 cycles)
# measured 21.7-40.2% of updates lost.
#
# The lock is a kernel byte-range lock (msvcrt.locking / fcntl.flock) on a sidecar
# file that is never deleted. The OS releases it when the holder's handle closes or
# its process dies, so there is no stale-lock state to time out or break. Deleting
# the sidecar would let a waiter lock an unlinked file while a newcomer locks a fresh
# one, so it stays in place.
LOCK_TIMEOUT_S = 10.0

if os.name == 'nt':
    import msvcrt

    def _try_lock(fd: int) -> bool:
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except PermissionError:          # EACCES: another handle holds the byte
            return False
        return True

    def _unlock(fd: int) -> None:
        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _try_lock(fd: int) -> bool:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return False
        return True

    def _unlock(fd: int) -> None:
        fcntl.flock(fd, fcntl.LOCK_UN)


class LedgerLockTimeout(OSError):
    """The ledger's lock was not free within the bound. Nothing was written. An
    OSError so a caller that already degrades a failed ledger write to a warning
    (repo_first_check.run) treats it the same way."""


def _lock_path(ledger_path: Path) -> Path:
    return ledger_path.with_name(f'.{ledger_path.name}.lock')


@contextlib.contextmanager
def ledger_lock(ledger_path: Path, timeout: float | None = None):
    """Hold ledger_path's cross-process lock for the duration of the block. Polls
    for up to `timeout` seconds (default LOCK_TIMEOUT_S, read at call time), then
    raises LedgerLockTimeout. Never proceeds unlocked."""
    timeout = LOCK_TIMEOUT_S if timeout is None else timeout
    lock = _lock_path(ledger_path)
    lock.parent.mkdir(parents=True, exist_ok=True)
    fd = _retry_locked(lambda: os.open(lock, os.O_RDWR | os.O_CREAT, 0o644))
    try:
        deadline = time.monotonic() + timeout
        delay = 0.002
        while not _try_lock(fd):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise LedgerLockTimeout(
                    f'{ledger_path.name} is locked by another process; not acquired '
                    f'within {timeout:g}s ({lock})')
            # Jittered backoff so waiters released together don't retry in lockstep.
            # Capped low: a ledger write holds the lock ~10ms, and a long sleep leaves
            # it idle while every waiter naps.
            time.sleep(min(remaining, delay * (0.5 + random.random())))
            delay = min(delay * 2, 0.01)
        try:
            yield
        finally:
            try:
                _unlock(fd)
            except OSError:
                pass                     # os.close below releases it regardless
    finally:
        os.close(fd)


def update_entries(mutate, ledger_path: Path | None = None, header: str = HEADER,
                   timeout: float | None = None) -> None:
    """The ONLY sanctioned read-modify-write of a ledger: take its lock, read, call
    mutate(entries) to change the dict in place, write. mutate returning False
    skips the write (backfill's no-change case keeps hand annotations). Anything
    slow belongs BEFORE this call, never inside mutate, because every other writer
    waits on it. `ledger_path` defaults to LEDGER read at call time, so a test that
    patches LEDGER redirects the lock too."""
    ledger_path = LEDGER if ledger_path is None else ledger_path
    with ledger_lock(ledger_path, timeout):
        entries = read_entries(ledger_path)
        if mutate(entries) is not False:
            write_entries(entries, ledger_path, header)


def record_hits(hits, shorthash, subject, ledger_path: Path | None = None,
                timeout: float | None = None) -> None:
    """cmd_record's ledger write: one line per affected skill, replacing any prior
    line for that skill."""
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    lines = {skill: format_ledger_line(skill, now, shorthash, subject,
                                       ', '.join(sorted(triggers)), plugin_of(skill))
             for skill, triggers in hits.items()}
    update_entries(lambda entries: entries.update(lines), ledger_path, timeout=timeout)


def clear_entries(skills, ledger_path: Path | None = None,
                  timeout: float | None = None) -> list[str]:
    """cmd_clear's ledger write, after its log-before-clear guard. Returns the
    skills that were actually pending and are now cleared."""
    cleared: list[str] = []

    def mutate(entries):
        cleared[:] = [s for s in skills if entries.pop(s, None) is not None]

    update_entries(mutate, ledger_path, timeout=timeout)
    return cleared


def _ledger_failure_message(exc: OSError, not_done: str, remedy: str) -> str:
    label = 'LEDGER LOCK TIMEOUT' if isinstance(exc, LedgerLockTimeout) else 'LEDGER WRITE FAILED'
    return f'pending_reimport: {label} -- {exc}. {not_done}; the ledger is unchanged. {remedy}'


def _normalized_hash_bytes(data: bytes) -> str:
    """SHA256 of content, CRLF->LF normalized when it decodes as text, PLUS --
    for content shaped like a SKILL.md (opens with a '---' frontmatter fence) --
    YAML scalar-quoting and a trailing EOF blank line normalized away via
    skill_md_normalize.normalize_skill_md_text(), the same rules
    skill_drift_report.py's verdict already applies (PR #35, 2026-08-03:
    "YAML scalar quoting is serialization, not drift"). Ported here because this
    comparator feeds skill_drifted()/sweep_drift()/candidates() and was not
    updated alongside PR #35 -- a confirmed-correct Save-skill install that
    differed from the repo only in that quoting class (plus a trailing blank
    line) still read as a live-sweep candidate. Content with no frontmatter fence
    passes through this step unchanged, so non-SKILL.md bundled files (scripts,
    fixtures, shared repo-root JSON deps) hash exactly as before.

    Bytes form (see _normalized_hash) so a git blob's content can be hashed the
    same way a working-tree/cache file is, for the shared-dep direction check.
    """
    try:
        text = data.decode('utf-8').replace('\r\n', '\n')
    except UnicodeDecodeError:
        return hashlib.sha256(data).hexdigest()  # binary: raw bytes, no text rules apply
    return hashlib.sha256(normalize_skill_md_text(text).encode('utf-8')).hexdigest()


def _normalized_hash(path: Path) -> str:
    """SHA256 of a file's content, CRLF->LF normalized when the file decodes as text.

    Matches the EOL rule already codified in package-and-stage-skill and
    ora-skill-store-drift-check: git autocrlf gives Windows working copies CRLF
    while the platform import stores LF, so a raw-byte hash reads perpetually
    "drifted" on line endings alone. A raw-only mismatch is in-sync, not drift.
    """
    return _normalized_hash_bytes(_read_bytes_long(path))


def _win_long(path) -> str:
    """Windows long-path-safe string form of `path`, opting out of the legacy
    260-char MAX_PATH.

    CACHE_ROOT is a fixed, deeply-nested AppData path, and a skill's own bundled
    layout stacks a relative path on top of it -- the combination can legitimately
    exceed 260 chars while the file is genuinely present (confirmed 2026-08-03:
    masterlease-jurisdiction-rebase's bundled fixture
    scripts/fixtures/ORA_MasterLease_ShallowBayIndustrial_v2.4.1_TEMPLATE.docx
    resolves to a 265-char cache path). Plain pathlib silently reports such a path
    MISSING instead of raising, which is exactly the false "drifted" verdict
    skill_drifted() produced. The `\\\\?\\` prefix requires a fully resolved,
    backslash-separated absolute path -- which Path.resolve() already guarantees
    -- and is safe to apply unconditionally, short paths included.

    KNOWN LIMITATION -- UNC paths (noted 2026-08-03 by a second session verifying
    this fix; latent, NOT live). A UNC path needs the `\\\\?\\UNC\\server\\share`
    form, with the leading double backslash replaced by `UNC\\`. This function
    instead prepends the prefix verbatim, so `\\\\srv\\share\\f` becomes
    `\\\\?\\\\\\srv\\share\\f`, which Windows will not resolve -- the file then reads
    as MISSING, reintroducing exactly the false "drifted" verdict this helper
    exists to prevent, and in a form that is harder to spot because the path
    looks plausible.

    Harmless today: CACHE_ROOT is a drive-letter path under AppData and the repo
    side is local, so no caller reaches this branch. It matters only if the skill
    cache or the repo is ever moved to a network share. If that happens, special-
    case the UNC prefix here rather than at the call sites -- every long-path
    helper below routes through this one function, so it is the single point of
    repair.

    NON-WINDOWS NO-OP (found 2026-08-03, Cowork verification session on
    masterlease-jurisdiction-rebase): `\\\\?\\` is a Windows-only extended-length
    convention. This function previously applied it unconditionally, so a repo
    path resolved from a POSIX context (e.g. this script run via Cowork's
    `mcp__workspace__bash` sandbox against the mounted repo, rather than native
    Windows) became `\\\\?\\/sessions/.../target-markets.json` -- a string neither
    OS can resolve. `_read_bytes_long()` then raised a bare FileNotFoundError on
    a file that genuinely exists, which `candidates()`/`sweep_drift()` catches
    and prints as `pending_reimport: skipped (...)` -- silently dropping that
    shared-dep check rather than the loud failure this ledger exists to produce.
    Guarded below: MAX_PATH is a Windows-only limitation, so the prefix is now
    only applied when actually running on Windows (`os.name == 'nt'`).

    SEPARATE, LARGER GAP (same session, not fixed here -- flagging since it
    changes how much to trust a `candidates` run from Cowork bash): CACHE_ROOT
    is a hardcoded native-Windows AppData path. Inside the Cowork bash sandbox
    it doesn't exist under any mount, so `Path(CACHE_ROOT / skill).resolve()`
    silently produces a bogus (but exception-free) path, `_isdir_long()` returns
    False, and `skill_drifted()` short-circuits to `False` for EVERY skill --
    "no candidates" from a Cowork-bash-sandbox run currently means "the cache
    directory couldn't be found," not "verified in sync." This function's fix
    stops the loud target-markets.json crash; it does NOT make cache-side sweep
    results trustworthy from that environment. Until CACHE_ROOT resolution is
    made environment-aware (or the doctrine is updated to say `candidates`/
    `sweep_drift` must run from a real Windows shell, not Cowork bash), treat a
    Cowork-bash `candidates`/`sweep_drift` result as repo-side-only and verify
    cache state independently (e.g. Read tool directly against the cache path,
    which does have host access) before trusting a "no candidates" verdict.
    """
    s = str(Path(path).resolve())
    if os.name != 'nt':
        return s
    return s if s.startswith('\\\\?\\') else '\\\\?\\' + s


def _isfile_long(path) -> bool:
    return os.path.isfile(_win_long(path))


def _isdir_long(path) -> bool:
    return os.path.isdir(_win_long(path))



def code_only_uninstalled(skill: str, cache_root=None) -> bool:
    """True for a CODE_ONLY_SKILLS member that has NO Cowork cache dir: it was never
    installed, so there is nothing stale to reimport and no install to log. False the
    moment a cache dir exists (someone did install it), so recording and the
    log-before-clear guard resume on their own. `cache_root` defaults to the module's
    CACHE_ROOT, looked up at call time so tests can patch it."""
    root = CACHE_ROOT if cache_root is None else cache_root
    return skill in CODE_ONLY_SKILLS and not _isdir_long(Path(root) / skill)

def _read_bytes_long(path) -> bytes:
    with open(_win_long(path), 'rb') as f:
        return f.read()


def skill_drifted(repo_root: Path, cache_root: Path, skill: str) -> bool:
    """True if the skill is installed (has a cache dir) AND any shipped file
    differs (EOL-normalized) or is missing under it.

    A skill with NO cache dir at all was never installed -- that's
    ora-skill-store-drift-check's separate REPO-ONLY category (step 3), not
    "drifted, needs reimport". Confirmed against the live repo: 6 skills
    migrated from the ora-operations-extensions plugin (annual-cycle,
    capex-budgeting, cash-position-monitor, deal-retirement,
    investor-relations, submarket-spatial-analysis) plus cowork-settings and
    2 in-progress skills have no cache dir today and are not reimport
    candidates -- flagging them would flood the ledger with "never installed"
    noise indistinguishable from real "went stale" drift. (vendor-management
    left this list 2026-09-11 on Gabriel's explicit re-publish decision --
    it now has a cache dir like any other installed skill.)

    Existence and read checks against the cache are long-path-safe (see
    _win_long()) -- a deep bundled path past MAX_PATH must never read as
    "missing" when it's actually present.
    """
    cache_dir = cache_root / skill
    if not _isdir_long(cache_dir):
        return False
    for rel, src_path in skill_source_files(skill, repo_root).items():
        cache_file = cache_dir / rel
        if not _isfile_long(cache_file):
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
    writes the ledger (see backfill() to persist sweep findings).

    Skills in DELIBERATELY_UNPUBLISHED (package_skills.py) are filtered out
    unconditionally, from either source -- OI-157: a deliberately-unpublished
    skill's repo copy can still drift from its (stale or absent) cache entry
    for ordinary reasons (a docs fix, a shared repo-root dep changing), and
    that drift must never be surfaced as reimport work a Save-skill batch click
    could accidentally re-register. This is the single choke point every
    downstream caller (package-and-stage-skill Entry Point A, ora-skill-store-
    drift-check) already reads through, so filtering here closes the gap
    regardless of which of the two sources first detected the drift."""
    result = dict(read_entries(ledger_path))
    for skill in sweep_drift(repo_root, cache_root):
        result.setdefault(
            skill,
            f'- {skill} | source: sweep (no ledger entry) | trigger: full repo-vs-cache SHA256 sweep',
        )
    for skill in DELIBERATELY_UNPUBLISHED:
        result.pop(skill, None)
    return result


def backfill(
    repo_root: Path = REPO, cache_root: Path = CACHE_ROOT, ledger_path: Path | None = None,
    timeout: float | None = None,
) -> list[str]:
    """Run a full sweep and PERSIST any drifted skill missing from the ledger,
    so it becomes durably visible via `list` (not just a one-off union computed
    by `candidates`). Never touches an entry that's already in the ledger --
    a real commit-hash entry is never clobbered by a backfill stub."""
    # The sweep hashes every skill (seconds), so it runs BEFORE taking the lock; the
    # ledger is read under the lock, so a commit recorded mid-sweep is never dropped.
    drifted = sweep_drift(repo_root, cache_root)
    if not drifted:
        return []                        # nothing to seed: stay read-free and lock-free
    now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    seeded: list[str] = []

    def mutate(entries):
        seeded[:] = _seed(entries, drifted, now)
        # Do NOT rewrite when nothing was seeded. write_entries() reconstructs the file
        # from parsed "- <skill> |" lines only, so an unconditional write silently drops
        # any hand-added annotation. That was tolerable when this ran only on commit;
        # as of 2026-09-07 it also runs DAILY and unattended from the doctrine guard,
        # which would make the loss a recurring, invisible one.
        return bool(seeded)

    update_entries(mutate, ledger_path, timeout=timeout)
    return seeded


def _seed(entries: dict[str, str], drifted, now: str) -> list[str]:
    """backfill's mutation: add a stub line for each drifted skill not already in
    the ledger. Returns the skills it added."""
    seeded = []
    for skill in drifted:
        if skill in entries:
            continue
        # OI-157, extended to backfill 2026-09-07 (adversarial review of the
        # ora-doctrine-integrity-guard 9th-engine PR): candidates() already pops
        # DELIBERATELY_UNPUBLISHED, but backfill WRITES the ledger and cmd_list()
        # prints it unfiltered -- so seeding one of these puts a skill Gabriel
        # deliberately never published in front of a batch Save-skill click. That
        # is not hypothetical: capex-budgeting was revived exactly that way on
        # 2026-08-13. Their drift is real and stays visible via `candidates`'
        # separate suppressed-list line; it must never become ledger WORK.
        if skill in DELIBERATELY_UNPUBLISHED:
            continue
        entries[skill] = (
            f'- {skill} | pending since {now} | backfill sweep (predates hook or hook was bypassed) '
            f'| trigger: full repo-vs-cache SHA256 sweep'
        )
        seeded.append(skill)
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
    is unavailable, the path has NO history, or the repo is SHALLOW -- so
    classify_shared_copy -> UNKNOWN.

    The empty-history and shallow guards were added 2026-08-03 alongside the
    identical fix in skill_drift_report._part_history_hashes. `git rev-list HEAD --
    <path>` exits 0 with EMPTY stdout for an untracked path, and the first cut
    returned an empty SET, which classify_shared_copy accepts as a real search
    result and resolves to CACHE-AHEAD. That conflates "searched and found nothing"
    with "could not search". Lower blast radius here than in the drift report (no
    shared-dep remedy is a byte-exact copy), but it is the same defect and would
    otherwise mislabel an untracked shared dep as runtime-only content to commit
    back."""
    head = _git_text(repo_root, 'rev-list', 'HEAD', '--', relpath)
    if head is None or not head.strip():
        return None, None
    if (_git_text(repo_root, 'rev-parse', '--is-shallow-repository') or '').strip() == 'true':
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
        for skill, dest in sorted(SHARED_CONSUMERS[dep]):
            if not _isdir_long(cache_root / skill):
                rows[skill] = 'NOT-INSTALLED'
            elif not _isfile_long(cache_root / skill / dest):
                rows[skill] = 'MISSING-IN-CACHE'
            else:
                rows[skill] = classify_shared_copy(
                    _normalized_hash(cache_root / skill / dest),
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
    # A Code-only skill with no Cowork cache dir can never be satisfied by a Save-skill
    # click, so a ledger line for it is permanent noise. Skip it (and say so: post-commit's
    # stdout is the console of whoever just committed).
    code_only = sorted(sk for sk in hits if code_only_uninstalled(sk))
    if code_only:
        hits = {sk: trig for sk, trig in hits.items() if sk not in code_only}
        print(f'pending_reimport: Code-only skill(s) not recorded (never installed in Cowork, '
              f'so no reimport applies): {", ".join(code_only)}')
        if not hits:
            return
    shorthash = _git('rev-parse', '--short', commit).strip()
    subject = _git('log', '-1', '--format=%s', commit).strip().replace('|', '/')
    try:
        record_hits(hits, shorthash, subject)
    except OSError as exc:
        # Any OSError, not just LedgerLockTimeout: main()'s blanket except would route
        # the rest to stderr, which post-commit discards, so the row would vanish
        # silently. stdout is the console of whoever just ran `git commit`. The remedy
        # is re-running record, not backfill: backfill never seeds a skill with no
        # cache dir or a DELIBERATELY_UNPUBLISHED one, drops the plugin routing tag,
        # and loses the commit's hash and subject. record replaces each skill's line,
        # so re-running it is safe (if a later commit has recorded the same skill
        # since, the older hash replaces the newer one; the skill stays pending).
        print(_ledger_failure_message(
            exc, f'{", ".join(sorted(hits))} from commit {shorthash} NOT recorded',
            f'Re-run `python tools/pending_reimport.py record {shorthash}`.'))
        _warn_deliberately_unpublished(hits)
        sys.exit(1)
    print(f'pending_reimport: recorded {len(hits)} skill(s) -> {LEDGER}')
    for skill in sorted(hits):
        print(f'   {skill}')
    _warn_deliberately_unpublished(hits)


def _warn_deliberately_unpublished(hits) -> None:
    # Commit-time flag for OI-157 skills (added 2026-09-11, ORA Setup Audit R25
    # remediation). Before this, a commit touching a DELIBERATELY_UNPUBLISHED
    # skill's packaged files (e.g. today's vendor-contract-qc-into-vendor-
    # management merge) recorded the ledger line the same as any ordinary
    # skill, with no signal at commit time that it needed manual review before
    # ever reaching a Save-skill click -- the fact only surfaced later, and
    # only to whoever happened to run `candidates` (not `list`, and not the
    # commit's own console output) and read its suppressed-skill line. Since
    # post-commit's stdout IS the commit's own console output (only stderr is
    # redirected to /dev/null -- see tools/hooks/post-commit), printing here
    # puts the warning in front of whoever just ran `git commit`, at the
    # moment the risk was introduced, without requiring them to know to run
    # `candidates` afterward.
    suppressed_hits = sorted(s for s in hits if s in DELIBERATELY_UNPUBLISHED)
    if suppressed_hits:
        print(
            f'pending_reimport: WARNING -- this commit touched packaged files for '
            f'{len(suppressed_hits)} skill(s) in DELIBERATELY_UNPUBLISHED '
            f'(package_skills.py, OI-157): {", ".join(suppressed_hits)}. These will NOT '
            f'appear as `candidates` and must never be swept into an ordinary Save-skill '
            f'batch click -- review manually before touching them, and see '
            f'package_skills.py for the re-publish decision that would remove one.'
        )


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
    (package-and-stage-skill Entry Point A) should call to build its work queue
    instead of `list` alone. The former `ora-skills-reimport-watch` reference here
    was a dead pointer -- see the module docstring."""
    result = candidates()
    if not result:
        print('pending_reimport: no candidates (ledger empty and full sweep found no drift)')
    else:
        print(f'pending_reimport: {len(result)} candidate(s) (ledger UNION full sweep):')
        for skill in sorted(result):
            print(f'   {result[skill]}')
    # No silent caps: a DELIBERATELY_UNPUBLISHED skill's drift is real and worth
    # knowing about even though candidates() must never turn it into reimport
    # work (OI-157) -- report it as its own line rather than a bare omission.
    suppressed = sorted(
        s for s in DELIBERATELY_UNPUBLISHED
        if s in read_entries() or s in sweep_drift()
    )
    if suppressed:
        print(
            f'pending_reimport: {len(suppressed)} deliberately-unpublished skill(s) have repo '
            f'drift but are suppressed from candidates (package_skills.DELIBERATELY_UNPUBLISHED, '
            f'OI-157) -- not staged, not a candidate, review manually if this is unexpected: '
            f'{", ".join(suppressed)}'
        )
    # A shared-dep mismatch shows up in the sweep once per consumer with no direction;
    # append the deduped, direction-aware view so the audit says reimport vs commit.
    _print_shared_dep_advisory()


def cmd_backfill() -> None:
    try:
        seeded = backfill()
    except LedgerLockTimeout as exc:
        print(_ledger_failure_message(exc, 'Sweep-detected drift NOT seeded',
                                      'The next backfill run seeds it.'), file=sys.stderr)
        sys.exit(1)
    if not seeded:
        print('pending_reimport: backfill found no drift beyond what the ledger already tracks')
        return
    print(f'pending_reimport: backfill seeded {len(seeded)} skill(s) -> {LEDGER}')
    for skill in sorted(seeded):
        print(f'   {skill}')


def newest_event_log_block(log_path: Path = EVENT_LOG) -> tuple[str, str] | tuple[None, None]:
    """(header_line, full_block_text) of the newest dated '## YYYY-MM-DD' entry in
    event_log.md, or (None, None) if the log is missing, empty, or has no dated
    entry. Newest-first is append-event-log.py's own insertion convention
    (insert_newest()), so the FIRST dated header in the body is the newest entry --
    this does not need to parse dates, only find that first header.

    Skips YAML frontmatter the same way append-event-log.py's entry_blocks() does,
    so a '## ' inside the frontmatter block is never mistaken for an entry."""
    try:
        content = log_path.read_text(encoding='utf-8')
    except OSError:
        return None, None
    body_start = 0
    if content.startswith('---\n'):
        end = content.find('\n---\n', 4)
        if end != -1:
            body_start = end + len('\n---\n')
    lines = content[body_start:].split('\n')
    idxs = [i for i, ln in enumerate(lines) if _ENTRY_HEADER_RE.match(ln)]
    if not idxs:
        return None, None
    i = idxs[0]
    j = idxs[1] if len(idxs) > 1 else len(lines)
    return lines[i], '\n'.join(lines[i:j])


def _named_in_block(skill: str, block: str) -> bool:
    """Word-boundary (hyphen-aware) match -- a substring hit on 'county-parcel-screen'
    must not be satisfied by an unrelated mention of 'county-parcel-screen-eval-harness'
    or similar, and a plain regex \\b treats '-' as a boundary already, so hyphenated
    skill names need the lookaround spelled out explicitly."""
    return re.search(rf'(?<![\w-]){re.escape(skill)}(?![\w-])', block) is not None


# A confirmed-install log says so in words. Case-insensitive because entries write
# both "CONFIRMED" (per-skill, doctrinal) and "4 re-imports confirmed" (headers).
# The \b keeps "unconfirmed" from matching.
_CONFIRM_RE = re.compile(r'\bconfirmed\b', re.I)

# Phrases meaning "this skill was NOT installed", when they appear in the skill's
# OWN scope. Deliberately narrow: an over-broad list makes the guard cry wolf and
# trains sessions to reach for --force, which is worse than the hole it closes.
# Bare "stale" is excluded for exactly that reason -- these logs say "main.log
# stale" and "repo-ahead-of-cache" constantly; only a copular "is/now/remains/
# still stale" reads as a verdict on the install itself.
_NON_INSTALL_RES = tuple(re.compile(p, re.I) for p in (
    r'\bnot packaged\b', r'\bnot installed\b', r'\bnot presented\b',
    r'\bnever packaged\b', r'\bno action taken\b', r'\bpublish stopped\b',
    r'\bstopped rather than\b', r'\bdeliberately skipped\b',
    r'\bnot re-?imported\b', r'\bnot confirmed\b', r'\brefused\b',
    # Bare "X is stale" is NOT enough. The 2026-08-24 entry says a refi *workbook*
    # "is still stale" inside an acquisition-underwriting bullet, which the loose
    # form read as a verdict on that skill's install -- the one false positive the
    # refute pass over all 76 real entries turned up. Require install context.
    r'\b(?:install(?:ed|ation)?|cached?|store|runtime)\b[^.\n]{0,80}?'
    r'\b(?:is|now|remains|still)\s+stale\b',
))


def _scopes(block: str) -> list[str]:
    """Split an entry into the smallest units that can carry a per-skill verdict:
    blank-line-separated paragraphs, further split at each markdown bullet.

    The scoping matters more than the token test. Every real entry states its
    confirmation ONCE -- in the header or a preamble -- then gives each skill its
    own bullet, so an entry-WIDE token test cannot tell a confirmed skill from a
    deliberately-skipped one sitting three lines below it. Requiring a token in
    every bullet fails the other way: it would refuse the legitimate 2026-09-07
    batch entry, whose bullets carry timestamps and no repeated 'CONFIRMED'."""
    units: list[str] = []
    for para in re.split(r'\n\s*\n', block):
        cur: list[str] = []
        for line in para.split('\n'):
            if re.match(r'\s*[-*]\s', line) and cur:
                units.append('\n'.join(cur))
                cur = [line]
            else:
                cur.append(line)
        if cur:
            units.append('\n'.join(cur))
    return [u for u in units if u.strip()]


def _sole_subject(skill: str, unit: str, all_skills) -> bool:
    """True when `unit` is a verdict ABOUT this skill rather than prose that merely
    mentions it. A unit naming two or more skills is discussion -- a corrections
    paragraph, a lessons note, a dispatch list -- and a non-install phrase inside it
    belongs to whichever skill the sentence is about, which this cannot know.

    Learned from the 2026-09-07 refute pass over all 76 real entries: without this,
    one "still stale" in a closing analysis paragraph refused three unrelated
    skills, and a meta-note about the guard itself ("REFUSED register-scheduled-task
    ... county-parcel-screen") refused both. An over-firing guard trains --force,
    which is worse than the hole it closes."""
    named = [s for s in all_skills if _named_in_block(s, unit)]
    return named == [skill]


def clear_authorized(skill: str, block: str, all_skills=None) -> tuple[bool, str]:
    """(ok, reason) for the LOG-BEFORE-CLEAR guard.

    Three conditions, in the order of what each catches:
      1. the skill is named in the newest entry at all -- the original 2026-08-14
         check, for a clear that outran its own log entry;
      2. the entry records a confirmed install SOMEWHERE (an entry holding only
         packaging notes, or only a decision NOT to install, authorizes nothing);
      3. no scope mentioning this skill carries a non-install verdict.

    (2) and (3) are the 2026-09-07 fix. The old check was (1) alone, so an entry
    reading "county-parcel-screen: NOT packaged, staged, or presented this session
    ... no action taken on this skill" authorized clearing county-parcel-screen
    exactly as well as a confirmed install would -- it tested for the NAME, never
    for a claim about it, and a real session cleared three lines on that basis.

    EVERY mention is checked, not just the first: a skill listed in a dispatch
    preamble and then negated in its own bullet must still refuse, or the preamble
    silently launders the verdict."""
    if not _named_in_block(skill, block):
        return False, 'not named in'
    if not _CONFIRM_RE.search(block):
        return False, 'records no confirmed install in'
    if all_skills is None:
        all_skills = sorted(all_skill_dirs(REPO))
    for unit in _scopes(block):
        if not _sole_subject(skill, unit, all_skills):
            continue
        for rx in _NON_INSTALL_RES:
            m = rx.search(unit)
            if m:
                return False, f'named as NOT installed ("{m.group(0)}") in'
    return True, ''


def cmd_clear(skills: list[str], force: bool = False) -> None:
    """Clear pending-reimport ledger entries -- gated on the LOG-BEFORE-CLEAR guard
    (module docstring) unless `force` is set. Fail-CLOSED on an unreadable/headerless
    log: this guard exists specifically to catch a clear that outran its own log
    entry (2026-08-14), so silently waving it through on a read failure would defeat
    the point. A skill that clears fine but simply isn't named in the newest entry
    is refused with the same message REGARDLESS of whether it's actually pending --
    the guard runs before the pending/not-pending question is even asked, since a
    session should not learn "nothing to clear" as an excuse to skip the log step
    it was supposed to do first."""
    # Nothing was ever installed for a Code-only skill with no cache dir, so there is no
    # install to log and the log-before-clear guard has nothing to guard for it.
    gated = [sk for sk in skills if not code_only_uninstalled(sk)]
    if not force and gated:
        header, block = newest_event_log_block()
        if block is None:
            print(
                f'pending_reimport: REFUSED to clear {", ".join(gated)} -- '
                f'{EVENT_LOG} is unreadable or has no dated entry. Log the confirmed '
                f'Save-skill install FIRST (package-and-stage-skill step 7), THEN '
                f'clear -- never the reverse. Pass --force to override (states the '
                f'exact 2026-08-14 failure mode this guard exists to catch).',
                file=sys.stderr,
            )
            sys.exit(1)
        verdicts = {s: clear_authorized(s, block) for s in gated}
        unlogged = [s for s, (ok, _) in verdicts.items() if not ok]
        if unlogged:
            for s in unlogged:
                print(
                    f'pending_reimport: REFUSED to clear {s} -- {verdicts[s][1]} '
                    f'the newest event_log.md entry ("{header.strip()}"). Log the '
                    f'confirmed Save-skill install first (package-and-stage-skill '
                    f'step 7), THEN clear -- never the reverse. Pass --force to '
                    f'override.',
                    file=sys.stderr,
                )
            skills = [s for s in skills if s not in unlogged]
            if not skills:
                sys.exit(1)
    try:
        cleared = clear_entries(skills)
    except LedgerLockTimeout as exc:
        print(_ledger_failure_message(exc, f'{", ".join(skills)} NOT cleared',
                                      'Re-run the same clear.'), file=sys.stderr)
        sys.exit(1)
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
        rest = argv[1:]
        force = '--force' in rest
        skills = [a for a in rest if a != '--force']
        if not skills:
            raise SystemExit('usage: pending_reimport.py clear [--force] <skill> [...]')
        cmd_clear(skills, force=force)
    else:
        raise SystemExit(__doc__.strip())


if __name__ == '__main__':
    # post-commit must never disrupt the commit: swallow everything on the record path.
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        print(f'pending_reimport: skipped ({exc})', file=sys.stderr)
        sys.exit(0)
