#!/usr/bin/env python
"""Automate the manual main.log <-> cache-CreationTime correlation that
package-and-stage-skill's step 7 has to do by hand every reimport.

Why this exists
----------------
package-and-stage-skill v1.22-v1.24 established that a confirmed Save-skill
install can be proven two ways: (a) the cache-directory CreationTime moves to
(approximately) click time, all files sharing it -- a real teardown/recreate,
not sync_appdata_mirror.py's in-place overwrite; (b) %LOCALAPPDATA%\\Claude\\Logs
\\main.log's "Delta: N to download" -> "Sync complete: N downloaded" pair lands
at that SAME second. Neither signal alone is conclusive (CreationTime can be of
uncertain provenance; the Local log's sync lines carry no skill name and the app
re-triggers the same pending sync 2-4x a few seconds apart) -- only an exact-
second match between the two is first-hand, skill-specific evidence. Doing this
by eye (register-scheduled-task v2.17, 2026-08-24) took a baseline capture, a
post-install re-listing, and a manual eyeball of ~40 SkillsPlugin log lines.
This scripts both halves.

Usage
-----
    python tools/reimport_correlate.py baseline <skill> [<skill> ...] [--package PATH.skill]
        Record each skill's current cache-directory CreationTime to
        <primary checkout>/_staging/reimport-baselines/<skill>/<session>.json. Run this
        during the pre-packaging pre-check, before presenting the Save-skill button.
        Baselines are scoped to the Claude session ($CLAUDE_CODE_SESSION_ID; runs
        outside a session share 'no-session'): the dir is shared by every checkout,
        and an unscoped baseline let one session CONFIRM another's install.
        --package (ONE skill) also stores the packaged SKILL.md's version as
        `expected_version`; postclick compares the cache to it. `precheck` records it too.

    python tools/reimport_correlate.py verify <skill> [<skill> ...] [--baseline TIME]
        Compare current CreationTime against the saved baseline (or an
        explicit --baseline "YYYY-MM-DD HH:MM:SS" for an ad hoc check with no
        prior `baseline` call). Prints one of:
          CONFIRMED    CreationTime moved AND a main.log Delta>=1/Sync-complete
                       pair lands at the same second -- install proven.
          MOVED-ONLY   CreationTime moved but no exact-second log line found
                       (main.log stale/rotated, or the match tolerance missed
                       it) -- treat as first-hand but uncorroborated.
          NO-CHANGE    CreationTime is unchanged from baseline -- no reimport
                       has happened since the baseline was taken. Also covers
                       a first-install skill whose cache dir is STILL absent
                       (baseline was recorded ABSENT and nothing has changed).
          ALREADY-RECORDED  no baseline, but the newest event_log entry naming
                       the skill (dated on/after the cache's CreationTime date)
                       logs `<skill> vX.Y reimport confirmed` for the installed
                       version, and a recorded-install marker matches the
                       cache CreationTime to the second -- another run's
                       postclick logged it and used the baseline up. postclick
                       appends nothing and exits 3 (never 0: reimport_cycle
                       reads 0 as CONFIRMED).
          NO-BASELINE  nothing to compare against; pass --baseline or run
                       `baseline` first.
          NO-CACHE     cache dir not found and no baseline exists either.

    python tools/reimport_correlate.py precheck <pkg.skill> [<pkg.skill> ...]
        Entry point B integrity pre-check (added 2026-09-23). Asserts the
        package EXISTS, entries use forward slashes with no directory records,
        one top-level dir == the skill name, SKILL.md is present, frontmatter
        name == dir and description <= 1024, plugin_of() is None, and every
        entry is byte-identical to the current repo copy (skill dir, or the
        repo-root shared dep) -- raw, then EOL-normalized; only a normalized
        mismatch fails. Repo files absent from the package are WARNed (some are
        intentional, e.g. PACKAGING-NOTE.md). Also captures the CreationTime
        baseline UNLESS this session already has one, which it keeps -- unless
        an install since has made it stale, then it recaptures. Run it BEFORE
        the Save-skill click. Exit 1 on FAIL.

    python tools/reimport_correlate.py postclick <skill> [--version X.Y]
                                        [--no-append] [--clear-ledger]
        Everything after "saved" in one call (added 2026-09-23): prints
        main.log liveness + the last sync events, runs `verify`, and ONLY on
        CONFIRMED appends the event-log line via append-event-log.py
        --entry-file (dated `## ` header, exit 0 required). On NO-CHANGE /
        MOVED-ONLY / any non-CONFIRMED verdict it STOPS: prints the log tail,
        appends nothing, exits 1. Expected version: --version, else the
        baseline's `expected_version` (the PACKAGE), else the repo SKILL.md. --clear-ledger runs
        `pending_reimport.py clear <skill>` only AFTER the append exited 0.
        --no-append verifies only (safe to re-run). After a successful append
        the baselines that predate this install are used up (see `consume`); if
        that fails it warns and exits 1 even though the append succeeded.
        ONE skill per call when it appends: several skills from one set of
        Save-skill clicks close through `reimport_cycle.py close <skill> ...`
        (one combined entry, a marker per skill, consume). With several skills
        postclick exits 2 and prints that command -- unless it is a plain
        --no-append verify, which runs per skill (2026-11-13: it used to verify
        the first skill and silently ignore the rest).

    python tools/reimport_correlate.py consume <skill> [<skill> ...]
        Once an install is recorded, use up EVERY session's baseline for the skill
        whose recorded CreationTime predates the current cache dir (kept, it would
        CONFIRM this same install again); a baseline recorded at the current
        CreationTime (captured after the install) is kept. precheck likewise
        recaptures its own baseline if an install has made it stale. Exit 1 if a
        baseline could not be removed. postclick does this itself after its append;
        reimport_cycle.py close calls it after its own combined append.

    A skill with no cache dir at baseline time (never installed) gets an
    explicit ABSENT baseline rather than being skipped (fixed 2026-09-11, ORA
    Setup Audit R25 remediation -- vendor-management's first-ever publish hit
    this exact gap and needed a manual `--baseline` override to verify). A
    later `verify` treats ABSENT -> a cache dir now existing as first-hand
    evidence of install, same as an ordinary CreationTime move, and labels the
    verdict CONFIRMED/MOVED-ONLY "(first install)".

Deliberately narrow: this is a correlation aid, not a new source of truth. It
reuses CACHE_ROOT from pending_reimport.py and reads the SAME two main.log
paths package-and-stage-skill documents (Local is the live one; Roaming is
checked too since it going stale is itself diagnostic -- see that skill's
"TWO main.log files" note, 2026-08-22).
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import struct
import subprocess
import sys
import uuid
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pending_reimport import (  # noqa: E402
    CACHE_ROOT, REPO, _atomic_write_text, _primary_checkout, _read_text_retry, _retry_locked,
    _normalized_hash, _normalized_hash_bytes,
    cache_digest, event_log_blocks, logged_install_entry, write_recorded_install,
)

import reimport_claims as _claims  # noqa: E402

ALREADY_RECORDED_RC = 3     # postclick: nothing to do, the install is already logged

# The PRIMARY checkout's _staging/, never a worktree's: a baseline taken during a
# packaging pre-check in a worktree must survive `git worktree remove` to be read
# back by `verify` after the reimport (same fix as pending_reimport's ledger, #78).
BASELINE_DIR = _primary_checkout(REPO) / '_staging' / 'reimport-baselines'

LOCAL_LOG = Path(r'C:\Users\Owner\AppData\Local\Claude\Logs\main.log')
ROAMING_LOG = Path(r'C:\Users\Owner\AppData\Roaming\Claude\logs\main.log')

LOG_LINE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) \[\w+\] \[SkillsPlugin\] (?P<msg>.*)$'
)
DELTA_RE = re.compile(r'Delta: (\d+) to download')
SYNC_RE = re.compile(r'Sync complete: (\d+) downloaded, (\d+) failed')

TOLERANCE = timedelta(seconds=1)  # exact-second match, +/-1s for line-ordering jitter


def _cache_dir(skill: str) -> Path:
    return CACHE_ROOT / skill


def _creation_time(skill: str) -> datetime | None:
    d = _cache_dir(skill)
    if not d.is_dir():
        return None
    return datetime.fromtimestamp(d.stat().st_ctime)


def _session_key() -> str:
    raw = os.environ.get('CLAUDE_CODE_SESSION_ID', '')
    return re.sub(r'[^A-Za-z0-9-]', '', raw)[:64] or 'no-session'


def _baseline_path(skill: str) -> Path:
    """One baseline per (skill, session): BASELINE_DIR is shared by every checkout, so
    an unscoped `<skill>.json` let one session read another's install -- or its own
    previous run's -- as a CONFIRMED move. Runs outside a Claude session share the
    'no-session' key (the pre-#79 behavior). Legacy `<skill>.json` files are ignored."""
    return BASELINE_DIR / skill / f'{_session_key()}.json'


def _legacy_hint(skill: str) -> None:
    """A flat pre-#79 `<skill>.json` is never read as a baseline (it could be another
    session's), but a reimport started before the merge still needs it -- say where it
    is and how to use it deliberately."""
    legacy = BASELINE_DIR / f'{skill}.json'
    if not legacy.is_file():
        return
    try:                                  # a hint must never break the verdict it annotates
        stored = json.loads(_read_text_retry(legacy))['creation_time']
        when = datetime.fromisoformat(stored).strftime('%Y-%m-%d %H:%M:%S') if stored else None
    except (OSError, ValueError, KeyError, TypeError):
        return
    if stored:
        print(f'  a pre-#79 unscoped baseline exists ({legacy}, {stored}); if it is YOUR '
              f'pre-click baseline, re-run with --baseline "{when}"')
    else:
        print(f'  a pre-#79 unscoped ABSENT baseline exists ({legacy}); if it is YOUR '
              f'pre-click baseline, re-run with --baseline "2000-01-01 00:00:00"')


def _read_baseline(path: Path) -> str | None:
    """The baseline's text, or None when there is none -- including one a concurrent
    consume deleted between the existence check and the read."""
    if not path.is_file():
        return None
    try:
        return _read_text_retry(path)
    except FileNotFoundError:
        return None


def _recorded(text: str | None):
    """(parsed, ok): a baseline's recorded CreationTime (None = ABSENT); ok=False if
    the file is unreadable as a baseline -- including a timezone-aware time, which this
    tool never writes and which cannot be compared with the naive CreationTime."""
    try:
        stored = json.loads(text)['creation_time']
        parsed = datetime.fromisoformat(stored) if stored else None
    except (TypeError, ValueError, KeyError):
        return None, False
    if parsed is not None and parsed.tzinfo is not None:
        return None, False
    return parsed, True


def _predates(recorded, installed) -> bool:
    """A baseline predates the install now in the cache unless it recorded that same
    CreationTime (to the second). Such a baseline can never tell its own future
    install from this one, so keeping it can only produce a false CONFIRMED."""
    return recorded is None or abs((installed - recorded).total_seconds()) >= 1


def consume_baseline(skill: str) -> int:
    """Once an install is recorded, use up EVERY session's baseline for the skill that
    predates it (the --baseline path verifies from another session, so "this
    session's" is not enough), and keep any captured after it (a subagent sharing
    this session re-capturing while the parent appends). Each file is claimed by
    rename before it is judged, so a baseline written concurrently is never deleted
    unseen. A rename is not exclusive on Windows -- two consumers can both "succeed",
    the second moving the first's claim on -- so a claim that vanishes belongs to the
    other consumer and is skipped. A file that is not a readable baseline (foreign,
    UTF-16, timezone-aware) is used up. Returns how many were used up; raises OSError
    if a file stays locked past the bounded retry -- callers must report that, never
    swallow it. A kept baseline whose put-back stays locked does not stop the sweep:
    it raises BaselineStranded (an OSError) at the end, naming the claim file."""
    installed = _creation_time(skill)
    skill_dir = BASELINE_DIR / skill
    if installed is None or not skill_dir.is_dir():
        return 0
    used, stranded = 0, []
    for path in sorted(skill_dir.glob('*.json')):
        claim = path.with_name(f'.{path.name}.claim-{os.getpid()}-{uuid.uuid4().hex[:8]}')
        try:
            _retry_locked(lambda: os.rename(path, claim))
            text = _read_text_retry(claim)
        except FileNotFoundError:                 # another consumer has it
            continue
        except UnicodeDecodeError:
            text = None
        recorded, ok = _recorded(text)
        if ok and not _predates(recorded, installed):
            try:                                  # post-install: put it back
                _retry_locked(lambda: os.rename(claim, path))
            except FileExistsError:               # a newer one landed meanwhile; it wins
                claim.unlink(missing_ok=True)
            except FileNotFoundError:             # another consumer moved it on
                pass
            except PermissionError:               # still locked: keep sweeping, report it
                stranded.append((claim, path))
            continue
        _retry_locked(lambda: claim.unlink(missing_ok=True))
        used += 1
    if stranded:
        raise BaselineStranded(stranded)
    return used


def install_snapshot(skill: str):
    """(CreationTime, content digest) of the install in the cache now, or None. Take it
    BEFORE verifying, and hand it to mark_logged: the marker must name the install that
    was verified, not whatever is in the cache by the time the append returns."""
    installed, digest = _creation_time(skill), cache_digest(skill, CACHE_ROOT)
    return None if installed is None or digest is None else (installed, digest)


def mark_logged(skill: str, snapshot, header: str, append_out: str = '') -> bool:
    """Record the verified install (`snapshot`, from install_snapshot before verify) as
    logged, for ALREADY-RECORDED and the ledger-clear fallback. Writes ONLY when (a) the
    cache still holds exactly that install -- a concurrent Save-skill between verify and
    here would otherwise be marked as logged (round-3 refute, C10) -- and (b) the append
    really landed: append-event-log.py also exits 0 when it SPOOLS a locked log, so its
    `append_out` must not say "spooled (log locked)" (headers are deterministic, so an
    earlier same-day run's identical header would otherwise pass check (c) -- round 4,
    C11), and (c) `header` is in the event log. Call it only after the append for
    this install exited 0 -- never from consume, which runs by hand too (round 2, C6).
    Fails closed and says why: without the marker neither consumer ever fires."""
    why = None
    if snapshot is None:
        why = 'no readable install was snapshotted before verify'
    elif install_snapshot(skill) != snapshot:
        why = 'the cache changed between verify and the append (another install?)'
    elif 'spooled (log locked):' in append_out:
        why = 'the append was spooled (event_log.md locked), not written'
    elif header.strip() not in {h.strip() for h, _ in event_log_blocks()}:
        why = 'the appended entry is not in event_log.md yet (spooled?)'
    if why:
        print(f'WARNING: recorded-install marker NOT written for {skill}: {why}. '
              f'A later postclick says NO-BASELINE, not ALREADY-RECORDED.')
        return False
    try:
        write_recorded_install(skill, *snapshot, base=BASELINE_DIR)
    except OSError as exc:
        print(f'WARNING: recorded-install marker not written for {skill} ({exc})')
        return False
    return True


class BaselineStranded(OSError):
    """Every baseline predating the install was used up, but one captured after it
    stayed locked and could not be renamed back -- it sits hidden as a claim file."""

    def __init__(self, stranded):
        self.stranded = stranded
        super().__init__('; '.join(f'{c} -> {p.name}' for c, p in stranded))

    def advice(self, skill: str) -> str:
        return (f'{skill}: every baseline predating the install was used up, but '
                f'{len(self.stranded)} kept one(s) could not be put back ({self}) -- rename '
                f'it back by hand, or that session\'s next verify says NO-BASELINE')


def cmd_consume(skills: list[str]) -> int:
    rc = 0
    for skill in skills:
        try:
            used = consume_baseline(skill)
        except BaselineStranded as exc:
            print(exc.advice(skill))
            rc = 1
            continue
        except OSError as exc:
            print(f'{skill}: baseline NOT used up ({exc}) -- re-run `consume {skill}` '
                  f'before the next reimport, or it will CONFIRM this install again')
            rc = 1
            continue
        print(f'{skill}: {used} baseline(s) predating the current install used up '
              f'({BASELINE_DIR / skill})')
    return rc


def _refresh_stale_baseline(skill: str) -> str | None:
    """precheck keeps an existing baseline (it may be the step-2 capture) -- unless an
    install has happened since it was taken, which makes it stale: kept, it would
    CONFIRM that install again. Returns the precheck note, or None if there is no
    baseline for this session."""
    text = _read_baseline(_baseline_path(skill))
    if text is None:
        return None
    recorded, ok = _recorded(text)
    current = _creation_time(skill)
    if current is not None and (not ok or _predates(recorded, current)):
        with contextlib.redirect_stdout(io.StringIO()):
            cmd_baseline([skill])
        return 'baseline was stale (an install since) -- recaptured'
    return f'baseline kept ({recorded.isoformat() if recorded else None})'


def cmd_baseline(skills: list[str], package: str | None = None) -> int:
    """Record each skill's current cache-directory CreationTime -- or, when no
    cache dir exists yet (the skill has never been installed), an explicit
    ABSENT baseline (creation_time: null) rather than skipping the skill
    entirely.

    Before this fix (found 2026-09-11, ORA Setup Audit R25 remediation:
    vendor-management's first-ever publish), a first-install skill had no cache
    dir at pre-check time, so this command wrote nothing for it and printed
    only a stderr note -- silently leaving `verify` with NO-BASELINE later and
    forcing a manual `--baseline "YYYY-MM-DD HH:MM:SS"` override for exactly the
    case (a brand-new publish) this correlation tool exists to make routine.
    Recording ABSENT explicitly lets `verify` treat "no dir -> a dir exists" as
    first-hand evidence of install, the same way it treats a CreationTime move
    for a skill that already existed.

    With `package` (a .skill zip), also record the version that package's SKILL.md
    declares as `expected_version`, which postclick then compares the cache against
    instead of whichever checkout runs it (#139's known limitation). The package is read
    BEFORE anything is written, so an unreadable one leaves no baseline behind. A package
    belongs to one skill, so `package` with several skills is refused (exit 2)."""
    extra: dict = {}
    if package is not None:
        if len(skills) != 1:
            print('--package names ONE package, so give exactly one skill', file=sys.stderr)
            return 2
        try:
            extra = {'expected_version': _package_version(Path(package), skills[0]),
                     'expected_files': _package_manifest(Path(package), skills[0])}
        except (OSError, zipfile.BadZipFile, KeyError) as exc:
            print(f'{skills[0]}: cannot read the package version from {package} '
                  f'({type(exc).__name__}: {exc}) -- no baseline written', file=sys.stderr)
            return 1
    for skill in skills:
        ct = _creation_time(skill)
        path = _baseline_path(skill)
        if ct is None:
            _atomic_write_text(path, json.dumps({'skill': skill, 'creation_time': None, **extra},
                                                indent=2))
            print(f'{skill}: baseline ABSENT (no cache dir yet -- first install) -> {path}')
            continue
        _atomic_write_text(path, json.dumps({'skill': skill, 'creation_time': ct.isoformat(),
                                             **extra}, indent=2))
        print(f'{skill}: baseline {ct.isoformat()} -> {path}')
    return 0


def _package_version(pkg: Path, skill: str) -> str | None:
    """Version the packaged SKILL.md declares (None = it declares none). Raises OSError /
    BadZipFile / KeyError when the package or its SKILL.md cannot be read."""
    with zipfile.ZipFile(pkg) as z:
        return _skill_md_version(z.read(f'{skill}/SKILL.md').decode('utf8', errors='replace'))


def _package_manifest(pkg: Path, skill: str) -> dict[str, str]:
    """{path under the skill dir: normalized hash} for every file the package ships. Uses
    the comparator's own rules, so what the platform does to an installed copy (CRLF to LF,
    quoting frontmatter scalars) is not a difference and a real content change is."""
    prefix = f'{skill}/'
    with zipfile.ZipFile(pkg) as z:
        return {n[len(prefix):]: _normalized_hash_bytes(z.read(n))
                for n in z.namelist() if n.startswith(prefix) and not n.endswith('/')}


_DROP = object()


def _record_expected_version(skill: str, version, files: dict[str, str] | None = None) -> None:
    """Merge `expected_version` and `expected_files` into this session's existing baseline
    (precheck keeps or recaptures one, and must not leave it without the package it just
    inspected). `_DROP` removes both: they describe the same package."""
    path = _baseline_path(skill)
    text = _read_baseline(path)
    if text is None:
        return
    try:
        data = json.loads(text)
        if version is _DROP:
            data.pop('expected_version', None)
            data.pop('expected_files', None)
        else:
            data['expected_version'] = version
            if files:
                data['expected_files'] = files
            else:
                data.pop('expected_files', None)
    except (TypeError, ValueError, AttributeError):
        return
    # A consume may have claimed the baseline since the read: writing now would bring a
    # pre-install baseline back from the dead and CONFIRM the same install twice.
    if _read_baseline(path) != text:
        return
    _atomic_write_text(path, json.dumps(data, indent=2))


def _expected_from(data):
    """(recorded, version) from a parsed baseline: `recorded` is True when it carries an
    `expected_version` key at all -- even null, meaning the package declared none."""
    if not isinstance(data, dict) or 'expected_version' not in data:
        return False, None
    v = data['expected_version']
    if v is None:
        return True, None
    if not isinstance(v, str) or not v.strip():
        # Hand-edited or foreign: never read as "no expected version" (that would CONFIRM
        # unchecked). A marker no cache version equals makes any readable cache a mismatch.
        return True, f'<malformed expected_version {v!r}>'
    return True, _norm_ver(v)


def _baseline_expected_version(skill: str):
    """(recorded, version) from THIS session's baseline."""
    text = _read_baseline(_baseline_path(skill))
    try:
        return _expected_from(json.loads(text) if text is not None else None)
    except (TypeError, ValueError):
        return False, None


def _baseline_expected_files(skill: str):
    """(recorded, manifest) from THIS session's baseline."""
    text = _read_baseline(_baseline_path(skill))
    try:
        data = json.loads(text) if text is not None else None
    except (TypeError, ValueError):
        return False, None
    if not isinstance(data, dict) or 'expected_files' not in data:
        return False, None
    return True, data['expected_files']


def _override_expected_files(skill: str, override: datetime):
    """(recorded, manifest) for `postclick --baseline TIME`: only from baselines, of any
    session, whose recorded CreationTime IS `override`. Matches that disagree yield a value
    _content_problems refuses, never one of them picked at random."""
    found = []
    d = BASELINE_DIR / skill
    for path in sorted(d.glob('*.json')) if d.is_dir() else []:
        try:
            text = _read_baseline(path)
            recorded, ok = _recorded(text) if text is not None else (None, False)
            data = json.loads(text) if ok else None
        except (OSError, ValueError):
            continue
        if (ok and recorded is not None and recorded.replace(microsecond=0) == override
                and isinstance(data, dict) and 'expected_files' in data):
            found.append(data['expected_files'])
    if not found:
        return False, None
    return True, found[0] if all(f == found[0] for f in found) else None


def _content_problems(skill: str, manifest) -> list[str]:
    """What differs between the cache and the package manifest. A timing match proves an
    install happened; this is what proves its content landed whole (2026-11-03: postclick
    said CONFIRMED and exit 0 with nothing having compared a single byte)."""
    if (not isinstance(manifest, dict) or not manifest
            or not all(isinstance(k, str) and isinstance(v, str) for k, v in manifest.items())):
        return ['the recorded package manifest is malformed or ambiguous']
    problems = []
    for rel, want in sorted(manifest.items()):
        try:
            got = _normalized_hash(_cache_dir(skill) / rel)
        except OSError:
            problems.append(f'{rel}: missing from the cache')
            continue
        if got != want:
            problems.append(f'{rel}: content differs from the package')
    return problems


def _override_expected_version(skill: str, override: datetime):
    """Expected version for `postclick --baseline TIME`: read from the baseline(s), of ANY
    session, whose recorded CreationTime IS `override` (to the second). Returns
    (version_or_None, unknown_reason): `unknown_reason` is set -- and the caller must STOP
    -- when no baseline matches, a match recorded no version, or matches disagree. Never
    consults this session's unrelated baseline or the repo checkout."""
    found = []
    d = BASELINE_DIR / skill
    for path in sorted(d.glob('*.json')) if d.is_dir() else []:
        try:
            text = _read_baseline(path)
            recorded, ok = _recorded(text) if text is not None else (None, False)
            data = json.loads(text) if ok else None
        except (OSError, ValueError):
            continue
        if ok and recorded is not None and recorded.replace(microsecond=0) == override:
            found.append(_expected_from(data))
    if not found:
        return None, f'no baseline records a CreationTime of {override:%Y-%m-%d %H:%M:%S}'
    if not all(rec for rec, _ in found):
        return None, 'the matching baseline recorded no packaged version'
    if len({v for _, v in found}) > 1:
        return None, 'matching baselines disagree on the packaged version'
    return found[0][1], None
def _sync_events(log_path: Path):
    """Yield (timestamp, delta_n, downloaded_n, failed_n) for every Delta-line
    followed within a few lines by its Sync-complete line. Pairs by proximity
    (Delta and its Sync-complete share the same or an adjacent timestamp in
    every observed sample) rather than assuming a fixed line offset."""
    if not log_path.is_file():
        return
    lines = log_path.read_text(errors='replace').splitlines()
    pending_delta = None  # (timestamp, n)
    for line in lines:
        m = LOG_LINE.match(line)
        if not m:
            continue
        ts = datetime.strptime(m.group('ts'), '%Y-%m-%d %H:%M:%S')
        msg = m.group('msg')
        dm = DELTA_RE.search(msg)
        if dm:
            pending_delta = (ts, int(dm.group(1)))
            continue
        sm = SYNC_RE.search(msg)
        if sm and pending_delta is not None:
            dts, dn = pending_delta
            if abs((ts - dts).total_seconds()) <= 5:
                yield (ts, dn, int(sm.group(1)), int(sm.group(2)))
            pending_delta = None


def _find_log_match(target: datetime) -> tuple[Path, datetime, int] | None:
    """First (log_path, timestamp, downloaded_n) with downloaded_n >= 1 whose
    Sync-complete timestamp is within TOLERANCE of `target`. Local checked
    first (it's the live one per the 2026-08-22 finding); Roaming as fallback."""
    for log_path in (LOCAL_LOG, ROAMING_LOG):
        for ts, delta_n, downloaded_n, failed_n in _sync_events(log_path):
            if downloaded_n < 1:
                continue
            if abs((ts - target).total_seconds()) <= TOLERANCE.total_seconds():
                return (log_path, ts, downloaded_n)
    return None


def _already_recorded(skill: str, current: datetime) -> str | None:
    """Header of the event_log entry that already logs the install now in the cache, or
    None. A baseline is used up once its install is logged (consume_baseline), so a
    second postclick -- the user's own after a Cowork session's, 2026-11-03 -- found no
    baseline and said NO-BASELINE, sending it looking for one. Rules:
    pending_reimport.logged_install_entry (recorded-install marker at this exact
    CreationTime + a confirming, never-negating entry at the installed version)."""
    header, _ = logged_install_entry(skill, base=BASELINE_DIR, cache_root=CACHE_ROOT)
    return header


def cmd_verify(skills: list[str], baseline_override: str | None) -> int:
    any_confirmed_missing = False
    for skill in skills:
        current = _creation_time(skill)

        # Resolve the baseline first (before deciding NO-CACHE) -- a skill whose
        # cache dir is STILL absent needs to tell "never installed, no baseline
        # was ever taken" (NO-BASELINE) apart from "never installed, and we
        # already know that from an explicit ABSENT baseline" (NO-CHANGE). The
        # old ordering treated `current is None` as an unconditional NO-CACHE
        # before a baseline was even consulted, which is right for the former
        # but wrong for the latter.
        baseline_is_absent = False
        if baseline_override:
            baseline = datetime.strptime(baseline_override, '%Y-%m-%d %H:%M:%S')
        else:
            text = _read_baseline(_baseline_path(skill))
            if text is None:
                if current is None:
                    print(f'{skill}: NO-CACHE -- cache dir not found under {CACHE_ROOT}')
                else:
                    already = _already_recorded(skill, current)
                    if already:
                        print(f'{skill}: ALREADY-RECORDED -- no baseline, but "{already}" already '
                              f'logs this install (cache CreationTime {current.isoformat()}). '
                              f"Another run's postclick used the baseline up; nothing to verify.")
                        continue
                    print(f'{skill}: NO-BASELINE -- run `baseline {skill}` first, or pass '
                          f'--baseline "YYYY-MM-DD HH:MM:SS"')
                    _legacy_hint(skill)
                any_confirmed_missing = True
                continue
            stored = json.loads(text)['creation_time']
            if stored is None:
                baseline_is_absent = True
                baseline = None
            else:
                baseline = datetime.fromisoformat(stored)

        if baseline_is_absent and current is None:
            print(f'{skill}: NO-CHANGE -- cache dir still absent (never installed; '
                  f'baseline recorded ABSENT)')
            continue

        if not baseline_is_absent and current is None:
            print(f'{skill}: NO-CACHE -- cache dir not found under {CACHE_ROOT} '
                  f'(was present at baseline {baseline.isoformat()} -- may have been '
                  f'uninstalled or the cache root moved)')
            any_confirmed_missing = True
            continue

        if not baseline_is_absent and abs((current - baseline).total_seconds()) < 1:
            print(f'{skill}: NO-CHANGE -- CreationTime still {current.isoformat()} '
                  f'(baseline {baseline.isoformat()})')
            continue

        # Either an ordinary CreationTime move, or the ABSENT -> present
        # transition of a first-ever install -- both are first-hand evidence a
        # cache dir was freshly created, so the log-correlation check and its
        # verdict wording are identical; only the printed baseline differs.
        baseline_label = 'ABSENT (never installed)' if baseline_is_absent else baseline.isoformat()
        first_install_note = ' (first install)' if baseline_is_absent else ''
        match = _find_log_match(current)
        if match:
            log_path, ts, n = match
            print(f'{skill}: CONFIRMED{first_install_note} -- CreationTime moved '
                  f'{baseline_label} -> {current.isoformat()}; {log_path.name} Sync complete: '
                  f'{n} downloaded @ {ts.isoformat()} (exact-second match)')
        else:
            print(f'{skill}: MOVED-ONLY{first_install_note} -- CreationTime moved '
                  f'{baseline_label} -> {current.isoformat()}, but no corroborating main.log '
                  f'Sync-complete line found within {TOLERANCE.total_seconds():.0f}s (main.log '
                  f'may be stale -- check its own mtime before treating this as a negative '
                  f'finding)')
    return 1 if any_confirmed_missing else 0


APPEND_LOG = Path(r'C:\Users\Owner\.claude\maintenance\append-event-log.py')
PENDING = Path(__file__).resolve().parent / 'pending_reimport.py'
IGNORED_REPO_FILES = {'PACKAGING-NOTE.md'}


def _norm(b: bytes) -> bytes:
    return b'\n'.join(l.rstrip() for l in b.replace(b'\r\n', b'\n').split(b'\n'))


def _fm_fields(skill_md: str) -> tuple[str | None, str | None]:
    m = re.match(r'^---\n(.*?)\n---\n', skill_md.replace('\r\n', '\n'), re.S)
    if not m:
        return None, None
    b = m.group(1)
    nm = re.search(r'^name:\s*(\S+)\s*$', b, re.M)
    # Same definition the packager and pre-commit gate use (package_skills.
    # frontmatter_description): the old one-line regex read a block-scalar
    # `description: >` as the single character '>' (1/1024 vs the packager's 641).
    from package_skills import frontmatter_description  # type: ignore
    return (nm.group(1).strip('\'"') if nm else None, frontmatter_description(b))


def _plugin_of(skill: str):
    try:
        from package_skills import plugin_of  # type: ignore
        return plugin_of(skill)
    except Exception as e:  # tool unavailable is a finding, not a pass
        return f'UNKNOWN ({type(e).__name__}: {e})'


def _packager_deps(skill: str) -> tuple[dict[str, str], list[str]]:
    """The packager's OWN record of what it injects into `skill`'s package, so precheck
    never re-derives it: ({packaged relpath: repo-root relpath} for SHARED_ROOT_DEPS --
    a renamed one such as tools/ora_doc_qc.py -> scripts/ora_doc_qc.py included -- and
    the PRIVATE_LOCAL_DEPS names, which have no repo copy at all). Before 2026-11-13
    precheck only knew same-named root files, so every RCT consumer and lease-form-qc
    FAILed "no repo counterpart" on a correct package."""
    import package_skills as ps  # type: ignore
    shared = {dst: src for src, dst in (ps._dep_pair(d) for d in ps.SHARED_ROOT_DEPS.get(skill, []))}
    return shared, list(ps.PRIVATE_LOCAL_DEPS.get(skill, []))


def _private_bytes(skill: str, name: str) -> bytes:
    """The exact bytes the packager ships for a private dep (validated, tied to the
    authoritative source), or SystemExit naming why not. Never prints a figure."""
    import package_skills as ps  # type: ignore
    return ps.private_dep_bytes(skill, name, REPO)


def _is_bundled(rel: str) -> bool:
    import package_skills as ps  # type: ignore
    return ps.is_bundled(rel)


def _raw_entry_names(path: Path) -> list[str]:
    """Entry names exactly as stored in the zip central directory.

    zipfile.ZipFile normalizes backslashes to '/' on Windows when it READS a
    name, so `z.namelist()` can never show the backslash-entry defect the
    importer rejects (APPNOTE 4.4.17.1) -- the check has to read the raw
    central directory. Returns [] if the EOCD cannot be located."""
    data = path.read_bytes()
    eocd = data.rfind(b'PK\x05\x06')
    if eocd < 0:
        return []
    total, _size, cd_off = struct.unpack_from('<HII', data, eocd + 10)
    names, pos = [], cd_off
    for _ in range(total):
        if data[pos:pos + 4] != b'PK\x01\x02':
            break
        nlen, elen, clen = struct.unpack_from('<HHH', data, pos + 28)
        names.append(data[pos + 46:pos + 46 + nlen].decode('utf8', 'replace'))
        pos += 46 + nlen + elen + clen
    return names


def cmd_precheck(pkgs: list[str]) -> int:
    rc = 0
    for pkg in pkgs:
        p = Path(pkg)
        skill = p.stem
        fails: list[str] = []
        warns: list[str] = []
        if not p.is_file():
            print(f'{skill}: FAIL -- package not found at {p}. MISSING, not stale: the handoff '
                  f'premise is false; route to Entry point A (first build) and say so.')
            rc = 1
            _record_expected_version(skill, _DROP)   # a failed precheck leaves no stale version
            continue
        try:
            zf = zipfile.ZipFile(p)
        except (OSError, zipfile.BadZipFile) as exc:
            print(f'{skill}: PRECHECK FAIL -- cannot open the package ({type(exc).__name__}: {exc})')
            rc = 1
            _record_expected_version(skill, _DROP)
            continue
        with zf as z:
            infos = z.infolist()
            names = [i.filename for i in infos]
            if any('\\' in n for n in _raw_entry_names(p)):
                fails.append('backslash zip entries (importer rejects)')
            if any(n.endswith('/') for n in names):
                fails.append('directory records present')
            tops = {n.split('/')[0] for n in names}
            if tops != {skill}:
                fails.append(f'top-level dir(s) {sorted(tops)} != {skill!r}')
            if f'{skill}/SKILL.md' not in names:
                fails.append('SKILL.md missing at expected path')
            else:
                nm, desc = _fm_fields(z.read(f'{skill}/SKILL.md').decode('utf8'))
                if nm != skill:
                    fails.append(f'frontmatter name {nm!r} != dir {skill!r}')
                if desc is None or len(desc) > 1024:
                    fails.append(f'description {None if desc is None else len(desc)}/1024')
                dlen = len(desc) if desc is not None else -1
            plug = _plugin_of(skill)
            if plug is not None:
                fails.append(f'plugin_of -> {plug!r}: NOT a standalone Save-skill target')
            shared = private_n = 0
            in_pkg = set()
            try:
                shared_map, private_names = _packager_deps(skill)
            except Exception as exc:  # packager unimportable is a finding, not a pass
                shared_map, private_names = {}, []
                fails.append(f'packager dep lists unreadable ({type(exc).__name__}: {exc})')
            for n in names:
                rel = n.split('/', 1)[1] if '/' in n else n
                in_pkg.add(rel)
                if rel in private_names:
                    # No repo copy by design: compare to the bytes the packager would ship.
                    try:
                        want = _private_bytes(skill, rel)
                    except SystemExit as exc:
                        fails.append(f'{rel}: private source not usable -- {exc}')
                        continue
                    private_n += 1
                    if z.read(n) != want:
                        fails.append(f'{rel}: content MISMATCH vs its validated private source '
                                     f'(stale package)')
                    continue
                if rel in shared_map:
                    rp = REPO / Path(*shared_map[rel].split('/'))   # declared SHARED_ROOT_DEPS
                    shared += 1
                else:
                    rp = REPO / skill / Path(*rel.split('/'))
                    if not rp.is_file() and '/' not in rel and (REPO / rel).is_file():
                        rp = REPO / rel  # same-named repo-root file (pre-declaration form)
                        shared += 1
                if not rp.is_file():
                    fails.append(f'{rel}: no repo counterpart')
                    continue
                a, b = z.read(n), rp.read_bytes()
                if a != b and _norm(a) != _norm(b):
                    fails.append(f'{rel}: content MISMATCH vs repo (stale package)')
            # A package without a dep the packager always injects would install broken (an
            # RCT consumer without its table fails closed on every basis test).
            for rel in sorted(set(shared_map) | set(private_names)):
                if rel not in in_pkg:
                    fails.append(f'{rel}: declared packager dep missing from the package')
            sd = REPO / skill
            if sd.is_dir():
                for root, dirs, files in os.walk(sd):
                    dirs[:] = [d for d in dirs if d != '__pycache__' and not d.startswith('.')]
                    for f in files:
                        rel = Path(root, f).relative_to(sd).as_posix()
                        # Only files the packager would ship can be "missing" from a package
                        # (tests/, runs/, versions/, PACKAGING-NOTE.md never are).
                        if (rel not in in_pkg and f not in IGNORED_REPO_FILES
                                and _is_bundled(rel)):
                            warns.append(f'{rel}: in repo, not in package')
            else:
                fails.append(f'repo skill dir not found: {sd}')
        try:
            pkg_version = _package_version(p, skill)
            pkg_files = _package_manifest(p, skill)
        except (OSError, zipfile.BadZipFile, KeyError):
            pkg_version = pkg_files = None     # no readable SKILL.md: already a FAIL above
        if not fails:
            # The installing session claims the reimport, so only it logs the install
            # (tools/reimport_claims.py; 2026-11-13 double-log). Another session's claim is
            # TAKEN OVER with a warning, never a FAIL: build-in-one-session, install-in-
            # another is the documented handoff (PR #260 review finding 1).
            notice = _claims.claim(skill, 'installing: precheck -> Save skill -> postclick/close')
            if notice:
                warns.append(notice)
        note = _refresh_stale_baseline(skill)
        if note is not None:
            base_note = note
        else:
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_baseline([skill])
            base_note = 'baseline CAPTURED'
        # Only a package that PASSED precheck is the one about to be installed; a stale
        # one's version would otherwise outlive the repo bump that made it stale.
        _record_expected_version(skill, _DROP if fails else pkg_version, pkg_files)
        if fails:
            rc = 1
            print(f'{skill}: PRECHECK FAIL -- ' + '; '.join(fails))
        else:
            print(f'{skill}: PRECHECK OK -- {len(names)} entries ({shared} shared root dep, '
                  f'{private_n} private dep), '
                  f'forward-slash, no dir records, all match repo, name==dir, '
                  f'description {dlen}/1024, plugin_of None; {base_note}')
        for w in warns:
            print(f'  WARN {w}')
    return rc


def _repo_version(skill: str) -> str | None:
    f = REPO / skill / 'SKILL.md'
    if not f.is_file():
        return None
    m = re.match(r'^---\n(.*?)\n---\n', f.read_text(encoding='utf8').replace('\r\n', '\n'), re.S)
    if not m:
        return None
    v = re.search(r'^version:\s*["\']?v?([\w.\-]+)["\']?\s*$', m.group(1), re.M)
    return v.group(1) if v else None


def _bad_version(v) -> bool:
    """True for a --version value that cannot name a version: blank, flag-like, or only
    'v' prefixes (which normalize to '' and would silently skip the version check)."""
    return not isinstance(v, str) or v.strip().startswith('-') or not _norm_ver(v)


def _norm_ver(v: str) -> str:
    return v.strip().lstrip('vV')


def _skill_md_version(text: str) -> str | None:
    """Version a SKILL.md declares: frontmatter `version:` first, else the first H1's
    `(vX.Y` token, else a trailing ` vX.Y`. None when it declares none."""
    text = text.replace('\r\n', '\n').lstrip('\ufeff')
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if m:
        v = re.search(r'^version:\s*["\']?v?([\w.\-]+)["\']?\s*(?:#.*)?$', m.group(1), re.M)
        if v:
            return _norm_ver(v.group(1))
        text = text[m.end():]
    h1 = next((l for l in text.split('\n') if l.startswith('# ')), None)
    if h1 is None:
        return None
    v = re.search(r'\(v?(\d+(?:\.\d+)+)', h1) or re.search(r'\bv(\d+(?:\.\d+)+)\b', h1)
    return _norm_ver(v.group(1)) if v else None


def _cache_version(skill: str) -> str | None:
    """Version of the INSTALLED copy, or None when the cache has no SKILL.md or no
    readable version -- the caller then cannot verify and says so."""
    try:
        return _skill_md_version((_cache_dir(skill) / 'SKILL.md').read_text(encoding='utf8', errors='replace'))
    except OSError:
        return None


def _version_at(root: Path, skill: str) -> str | None:
    """Version `root`/`skill`/SKILL.md declares. Never raises: a missing or non-UTF-8 file
    just means there is nothing to compare against."""
    try:
        return _skill_md_version((root / skill / 'SKILL.md').read_text(encoding='utf8', errors='replace'))
    except OSError:
        return None


def _repo_expected_version(skill: str) -> str | None:
    """Version the repo checkout declares for `skill`, used as the expected install when
    no --version is given (reimport_cycle never passes one)."""
    return _version_at(REPO, skill)


def ledger_clear_blocker(skill: str, installed: str | None) -> str | None:
    """Why the ledger entry must NOT be cleared, or None. The ledger clears by skill NAME and
    lives in the PRIMARY checkout, so clearing after any checkout moved past what was installed
    would also wipe the pending reimport of that newer version. Looks at the running checkout
    AND the primary; blocks when either declares a readable version that differs from the
    installed one, or when the installed version is unknown but a checkout is versioned. Only a
    checkout that declares no version fails open (nothing to compare)."""
    repos = sorted({v for v in (_version_at(REPO, skill), _version_at(_primary_checkout(REPO), skill)) if v})
    for repo in repos:
        if installed and _norm_ver(installed) == _norm_ver(repo):
            continue
        got = f'v{_norm_ver(installed)} was installed' if installed else 'no installed version could be read'
        return (f'ledger NOT cleared: repo is v{repo} but {got} -- '
                f'the pending reimport of the repo version stays in the ledger')
    return None


def _log_report(tail: int) -> None:
    now = datetime.now()
    for lp in (LOCAL_LOG, ROAMING_LOG):
        if not lp.is_file():
            print(f'  log {lp}: ABSENT')
            continue
        age = now - datetime.fromtimestamp(lp.stat().st_mtime)
        print(f'  log {lp}: last write {age.total_seconds() / 60:.0f} min ago')
        for ts, dn, downloaded, failed in list(_sync_events(lp))[-tail:]:
            print(f'    {ts.isoformat()} Delta {dn} / downloaded {downloaded} / failed {failed}')


def cmd_postclick(skill: str, version: str | None, no_append: bool, clear_ledger: bool,
                  baseline_override: str | None = None) -> int:
    if version is not None and _bad_version(version):
        print(f'--version needs a version value (e.g. 4.32), got {version!r}')
        return 2
    if baseline_override is not None and not baseline_override.strip():
        print('--baseline needs a time ("YYYY-MM-DD HH:MM:SS"), got a blank value')
        return 2
    snapshot = install_snapshot(skill)        # the install verify is about to judge
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_verify([skill], baseline_override)
    verdict = buf.getvalue().strip()
    confirmed = f'{skill}: CONFIRMED' in verdict
    pkg_unversioned = False
    unknown = None
    if confirmed and not version and baseline_override:
        # Override mode (prep ran in another session): this session's baseline and this
        # checkout are both unrelated to the package, so neither may stand in for it.
        version, unknown = _override_expected_version(
            skill, datetime.strptime(baseline_override, '%Y-%m-%d %H:%M:%S'))
        pkg_unversioned = unknown is None and not version
    elif confirmed and not version:
        # --version, then the PACKAGE recorded at baseline time, then the repo checkout. A
        # baseline that inspected a package declaring no version is final: the checkout is
        # not the package, so it must not stand in for it.
        recorded, version = _baseline_expected_version(skill)
        pkg_unversioned = recorded and not version
        if not recorded:
            version = _repo_expected_version(skill)
    cache_ver = _cache_version(skill) if confirmed else None
    want = _norm_ver(version) if version else None
    malformed = bool(want and want.startswith('<malformed'))   # never confirms, versioned cache or not
    mismatch = bool(confirmed and (malformed or (cache_ver and (want or pkg_unversioned)
                                                   and want != cache_ver)))
    # A timing match proves SOME install happened, not WHICH version (2026-10-17: v4.28
    # was logged as CONFIRMED while the cache held v4.29). Never print CONFIRMED for it.
    files_recorded, content_problems = False, []
    if confirmed and not (mismatch or unknown):
        files_recorded, manifest = (
            _override_expected_files(skill, datetime.strptime(baseline_override, '%Y-%m-%d %H:%M:%S'))
            if baseline_override else _baseline_expected_files(skill))
        if files_recorded:
            content_problems = _content_problems(skill, manifest)
    if mismatch or unknown or content_problems:
        word = ('VERSION-MISMATCH' if mismatch else
                'VERSION-UNKNOWN' if unknown else 'CONTENT-MISMATCH')
        verdict = verdict.replace(f'{skill}: CONFIRMED', f'{skill}: {word}', 1)
    print(verdict)
    _log_report(6)
    if f'{skill}: ALREADY-RECORDED' in verdict:
        # Its own exit code, never 0: reimport_cycle.cmd_close reads 0 as CONFIRMED and
        # would append a second entry for an install it never verified (2026-11-03 refute).
        print(f'Nothing appended: the install is already logged (exit {ALREADY_RECORDED_RC}).')
        if not clear_ledger:
            return ALREADY_RECORDED_RC
        blocker = ledger_clear_blocker(skill, _cache_version(skill))
        if blocker:
            print(blocker)
            return ALREADY_RECORDED_RC
        c = subprocess.run([sys.executable, str(PENDING), 'clear', skill],
                           capture_output=True, text=True)
        print((c.stdout + c.stderr).strip())
        return c.returncode or ALREADY_RECORDED_RC
    if not confirmed:
        print('STOP: verdict is not CONFIRMED. Nothing appended. Do not repackage, edit or commit; '
              'report the log state above.')
        return 1
    if unknown:
        print(f'STOP: expected version unknown -- {unknown}. The install moved, but nothing '
              f'says which version was packaged (this checkout is not the package), so it '
              f'is not logged. pass --version X.Y (the packaged version). Nothing appended, '
              f'ledger and baseline untouched.')
        return 1
    if mismatch:
        expected = f'v{want}' if want else 'version (the package declares none)'
        cache_txt = f'v{cache_ver}' if cache_ver else 'no readable version'
        print(f'STOP: VERSION-MISMATCH -- the install moved, but the cache SKILL.md reads '
              f'{cache_txt}, not the expected {expected}. Nothing appended, ledger and baseline '
              f'untouched. Find what was actually saved (a newer draft or a different package) '
              f'before logging or clearing anything.')
        return 1
    if content_problems:
        print('STOP: CONTENT-MISMATCH -- the install moved, but the cache does not hold what '
              'the package shipped: ' + '; '.join(content_problems) + '. Nothing appended, '
              'ledger and baseline untouched. Re-install through Cowork Save skill (desktop '
              'Settings drops subfolder files), or find what was actually saved.')
        return 1
    if files_recorded:
        print('content verified: every packaged file matches the cache.')
    else:
        print('WARNING: content not verified -- this baseline recorded no package manifest '
              '(no precheck or baseline --package ran first), so the cached files were not '
              'compared to the package.')
    if want and cache_ver is None:
        print(f'WARNING: version not verified -- the cache SKILL.md has no readable version '
              f'(frontmatter `version:` or an H1 `(vX.Y)`); v{want} is taken on trust.')
    elif not want:
        print('WARNING: version not verified -- no expected version (no --version, and the '
              'repo SKILL.md declares none), so the installed version was not checked.')
    if no_append:
        print('CONFIRMED (--no-append: event log untouched).')
        return 0
    holder = _claims.foreign_holder(skill)
    if holder:
        # 2026-11-13: two sessions logged the same 13 installs. The session holding the
        # reimport claim logs it; a verify here is fine, a second log entry is not.
        print('STOP: ' + _claims.describe(skill, holder) + ' Nothing appended, ledger and '
              'baseline untouched.')
        return 1
    vtxt = f' v{_norm_ver(version)}' if version else ''
    today = datetime.now().strftime('%Y-%m-%d')
    ef = REPO / '_staging' / f'_eventlog_entry_{skill}.md'
    # Baselines live in the primary now, so nothing else creates this checkout's _staging/.
    ef.parent.mkdir(parents=True, exist_ok=True)
    header = f'## {today} -- {skill}{vtxt} reimport confirmed'
    ef.write_text(
        f'{header}\n\n'
        f'{skill}{vtxt} reimported via Cowork Save-skill; reimport_correlate CONFIRMED.\n',
        encoding='utf8')
    r = subprocess.run([sys.executable, str(APPEND_LOG), '--entry-file', str(ef)],
                       capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    if r.returncode != 0:
        print(f'FAIL: append-event-log.py exited {r.returncode}; ledger NOT cleared.')
        return 1
    print('event log appended (exit 0).')
    mark_logged(skill, snapshot, header, r.stdout + r.stderr)
    _claims.release(skill)                # logged: this session's reimport is done
    consume_failed = 0
    try:
        consume_baseline(skill)
    except BaselineStranded as exc:
        print(f'WARNING: {exc.advice(skill)}')
        consume_failed = 1
    except OSError as exc:
        # A kept baseline would CONFIRM this same install again on the next reimport.
        print(f'WARNING: baseline NOT used up ({exc}) -- run '
              f'`reimport_correlate.py consume {skill}` before the next reimport.')
        consume_failed = 1
    blocker = ledger_clear_blocker(skill, cache_ver or want) if clear_ledger else None
    if blocker:
        print(blocker)
        return consume_failed
    if clear_ledger:
        c = subprocess.run([sys.executable, str(PENDING), 'clear', skill],
                           capture_output=True, text=True)
        print((c.stdout + c.stderr).strip())
        return c.returncode or consume_failed
    return consume_failed


def _pop(rest: list[str], flag: str, has_val: bool):
    if flag not in rest:
        return None, rest
    i = rest.index(flag)
    if has_val:
        return rest[i + 1], rest[:i] + rest[i + 2:]
    return True, rest[:i] + rest[i + 1:]


SUBCOMMANDS = ('baseline', 'verify', 'precheck', 'postclick', 'consume')
HELP_FLAGS = ('-h', '--help', 'help')


def usage(cmd: str | None = None) -> str:
    """The module docstring, or just one subcommand's section of it. A section runs from
    its `python tools/reimport_correlate.py <cmd>` line to the next subcommand's line."""
    doc = __doc__ or ''
    if cmd not in SUBCOMMANDS:
        return doc
    head = re.compile(r'^\s*python tools/reimport_correlate\.py (' + '|'.join(SUBCOMMANDS) + r')\b')
    lines, out, inside = doc.splitlines(), [], False
    for ln in lines:
        m = head.match(ln)
        if m:
            inside = m.group(1) == cmd
        if inside:
            out.append(ln)
    return '\n'.join(out).rstrip() + '\n' if out else doc


def main() -> int:
    args = sys.argv[1:]
    # -h/--help anywhere (2026-11-14): `postclick --help` used to be refused as an
    # unrecognised option, so the flags could only be found by reading the source.
    if any(a in HELP_FLAGS for a in args):
        print(usage(args[0] if args and args[0] in SUBCOMMANDS else None))
        return 0
    if len(args) < 2 or args[0] not in SUBCOMMANDS:
        print(__doc__)
        return 2
    cmd, rest = args[0], args[1:]
    baseline_override, rest = _pop(rest, '--baseline', True)
    version, rest = _pop(rest, '--version', True)
    package, rest = _pop(rest, '--package', True)
    if version is not None and _bad_version(version):
        print(f'--version needs a version value (e.g. 4.32), got {version!r}')
        return 2
    if baseline_override is not None and not baseline_override.strip():
        print('--baseline needs a time ("YYYY-MM-DD HH:MM:SS"), got a blank value')
        return 2
    no_append, rest = _pop(rest, '--no-append', False)
    clear_ledger, rest = _pop(rest, '--clear-ledger', False)
    stray = [t for t in rest if t.startswith('-')]
    if stray:
        # `--version=4.29` and typos would otherwise be taken as skill names and the flag's
        # check silently skipped.
        print(f'unrecognised option(s) {stray} -- flags take a SEPARATE value '
              f'(--version 4.29), not --flag=value')
        return 2
    if not rest:
        print('no skill name(s) given', file=sys.stderr)
        return 2
    if cmd == 'baseline':
        return cmd_baseline(rest, package)
    if cmd == 'consume':
        return cmd_consume(rest)
    if cmd == 'precheck':
        return cmd_precheck(rest)
    if cmd == 'postclick':
        if len(rest) > 1:
            if no_append and version is None and not clear_ledger:
                # Verify-only cannot log anything, so one skill at a time is harmless.
                # Worst result wins, ranked by meaning, not number: a failure (1) or a usage
                # error (2) must never be reported as ALREADY-RECORDED (3), which is "nothing
                # to do" (PR #260 review finding 5).
                codes = [cmd_postclick(s, None, True, False, baseline_override) for s in rest]
                return max(codes, key=lambda c: {0: 0, ALREADY_RECORDED_RC: 1, 2: 2}.get(c, 3))
            # 2026-11-13: `postclick a b c` used to verify `a` and silently ignore `b c`, and
            # a hand-written combined log entry then left no recorded-install marker, so no
            # baseline was ever used up. The batch path already exists: ONE combined entry,
            # a marker per skill, consume, ledger clear.
            print(f'postclick logs ONE skill per entry. For one set of Save-skill clicks use:\n'
                  f'  python tools/reimport_cycle.py close {" ".join(rest)}'
                  f'{chr(32) + "--baseline " + chr(34) + baseline_override + chr(34) if baseline_override else ""}\n'
                  f'(one combined entry, a recorded-install marker per skill, consume, ledger '
                  f'clear and the closing sweep). Verify only: postclick ... --no-append.')
            return 2
        return cmd_postclick(rest[0], version, bool(no_append), bool(clear_ledger),
                             baseline_override)
    return cmd_verify(rest, baseline_override)


if __name__ == '__main__':
    sys.exit(main())
