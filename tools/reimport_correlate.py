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
)

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
            extra = {'expected_version': _package_version(Path(package), skills[0])}
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


def _record_expected_version(skill: str, version: str | None) -> None:
    """Merge `expected_version` into this session's existing baseline (precheck keeps or
    recaptures one, and must not leave it without the package it just inspected)."""
    path = _baseline_path(skill)
    text = _read_baseline(path)
    if text is None:
        return
    try:
        data = json.loads(text)
        data['expected_version'] = version
    except (TypeError, ValueError):
        return
    # A consume may have claimed the baseline since the read: writing now would bring a
    # pre-install baseline back from the dead and CONFIRM the same install twice.
    if _read_baseline(path) != text:
        return
    _atomic_write_text(path, json.dumps(data, indent=2))


def _baseline_expected_version(skill: str):
    """(recorded, version): `recorded` is True when this session's baseline carries an
    `expected_version` key at all -- even null, meaning the package declared none."""
    text = _read_baseline(_baseline_path(skill))
    try:
        data = json.loads(text) if text is not None else None
    except (TypeError, ValueError):
        return False, None
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
    d = re.search(r'^description:\s*"?(.*?)"?\s*$', b, re.M | re.S)
    return (nm.group(1).strip('\'"') if nm else None, d.group(1) if d else None)


def _plugin_of(skill: str):
    try:
        from package_skills import plugin_of  # type: ignore
        return plugin_of(skill)
    except Exception as e:  # tool unavailable is a finding, not a pass
        return f'UNKNOWN ({type(e).__name__}: {e})'


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
            continue
        with zipfile.ZipFile(p) as z:
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
            shared = 0
            in_pkg = set()
            for n in names:
                rel = n.split('/', 1)[1] if '/' in n else n
                in_pkg.add(rel)
                rp = REPO / skill / Path(*rel.split('/'))
                if not rp.is_file() and '/' not in rel and (REPO / rel).is_file():
                    rp = REPO / rel  # SHARED_ROOT_DEPS injected from repo root
                    shared += 1
                if not rp.is_file():
                    fails.append(f'{rel}: no repo counterpart')
                    continue
                a, b = z.read(n), rp.read_bytes()
                if a != b and _norm(a) != _norm(b):
                    fails.append(f'{rel}: content MISMATCH vs repo (stale package)')
            sd = REPO / skill
            if sd.is_dir():
                for root, dirs, files in os.walk(sd):
                    dirs[:] = [d for d in dirs if d != '__pycache__' and not d.startswith('.')]
                    for f in files:
                        rel = Path(root, f).relative_to(sd).as_posix()
                        if (rel not in in_pkg and f not in IGNORED_REPO_FILES
                                and not rel.startswith('versions/') and not f.endswith('.pyc')):
                            warns.append(f'{rel}: in repo, not in package')
            else:
                fails.append(f'repo skill dir not found: {sd}')
        try:
            pkg_version = _package_version(p, skill)
        except (OSError, zipfile.BadZipFile, KeyError):
            pkg_version = None     # no readable SKILL.md: already a FAIL above
        note = _refresh_stale_baseline(skill)
        if note is not None:
            base_note = note
        else:
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_baseline([skill])
            base_note = 'baseline CAPTURED'
        if f'{skill}/SKILL.md' in names:
            _record_expected_version(skill, pkg_version)
        if fails:
            rc = 1
            print(f'{skill}: PRECHECK FAIL -- ' + '; '.join(fails))
        else:
            print(f'{skill}: PRECHECK OK -- {len(names)} entries ({shared} shared root dep), '
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


def _repo_expected_version(skill: str) -> str | None:
    """Version the repo checkout declares for `skill`, used as the expected install when
    no --version is given (reimport_cycle never passes one). Never raises: a missing or
    non-UTF-8 SKILL.md just means there is nothing to compare against."""
    try:
        return _skill_md_version((REPO / skill / 'SKILL.md').read_text(encoding='utf8', errors='replace'))
    except OSError:
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
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_verify([skill], baseline_override)
    verdict = buf.getvalue().strip()
    confirmed = f'{skill}: CONFIRMED' in verdict
    pkg_unversioned = False
    if confirmed and not version:
        # --version, then the PACKAGE recorded at baseline time, then the repo checkout. A
        # baseline that inspected a package declaring no version is final: the checkout is
        # not the package, so it must not stand in for it.
        recorded, version = _baseline_expected_version(skill)
        pkg_unversioned = recorded and not version
        if not recorded:
            version = _repo_expected_version(skill)
    cache_ver = _cache_version(skill) if confirmed else None
    want = _norm_ver(version) if version else None
    mismatch = bool(confirmed and cache_ver and (want or pkg_unversioned) and want != cache_ver)
    # A timing match proves SOME install happened, not WHICH version (2026-10-17: v4.28
    # was logged as CONFIRMED while the cache held v4.29). Never print CONFIRMED for it.
    print(verdict.replace(f'{skill}: CONFIRMED', f'{skill}: VERSION-MISMATCH', 1) if mismatch else verdict)
    _log_report(6)
    if not confirmed:
        print('STOP: verdict is not CONFIRMED. Nothing appended. Do not repackage, edit or commit; '
              'report the log state above.')
        return 1
    if mismatch:
        expected = f'v{want}' if want else 'version (the package declares none)'
        print(f'STOP: VERSION-MISMATCH -- the install moved, but the cache SKILL.md reads '
              f'v{cache_ver}, not the expected {expected}. Nothing appended, ledger and baseline '
              f'untouched. Find what was actually saved (a newer draft or a different package) '
              f'before logging or clearing anything.')
        return 1
    if want and cache_ver is None:
        print(f'WARNING: version not verified -- the cache SKILL.md has no readable version '
              f'(frontmatter `version:` or an H1 `(vX.Y)`); v{want} is taken on trust.')
    elif not want:
        print('WARNING: version not verified -- no expected version (no --version, and the '
              'repo SKILL.md declares none), so the installed version was not checked.')
    if no_append:
        print('CONFIRMED (--no-append: event log untouched).')
        return 0
    vtxt = f' v{_norm_ver(version)}' if version else ''
    today = datetime.now().strftime('%Y-%m-%d')
    ef = REPO / '_staging' / f'_eventlog_entry_{skill}.md'
    # Baselines live in the primary now, so nothing else creates this checkout's _staging/.
    ef.parent.mkdir(parents=True, exist_ok=True)
    ef.write_text(
        f'## {today} -- {skill}{vtxt} reimport confirmed\n\n'
        f'{skill}{vtxt} reimported via Cowork Save-skill; reimport_correlate CONFIRMED.\n',
        encoding='utf8')
    r = subprocess.run([sys.executable, str(APPEND_LOG), '--entry-file', str(ef)],
                       capture_output=True, text=True)
    print((r.stdout + r.stderr).strip())
    if r.returncode != 0:
        print(f'FAIL: append-event-log.py exited {r.returncode}; ledger NOT cleared.')
        return 1
    print('event log appended (exit 0).')
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


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ('baseline', 'verify', 'precheck', 'postclick', 'consume'):
        print(__doc__)
        return 2
    cmd, rest = args[0], args[1:]
    baseline_override, rest = _pop(rest, '--baseline', True)
    version, rest = _pop(rest, '--version', True)
    package, rest = _pop(rest, '--package', True)
    no_append, rest = _pop(rest, '--no-append', False)
    clear_ledger, rest = _pop(rest, '--clear-ledger', False)
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
        return cmd_postclick(rest[0], version, bool(no_append), bool(clear_ledger),
                             baseline_override)
    return cmd_verify(rest, baseline_override)


if __name__ == '__main__':
    sys.exit(main())
