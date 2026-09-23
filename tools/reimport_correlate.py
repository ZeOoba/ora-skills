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
    python tools/reimport_correlate.py baseline <skill> [<skill> ...]
        Record each skill's current cache-directory CreationTime to
        _staging/reimport-baselines/<skill>.json. Run this during the
        pre-packaging pre-check, before presenting the Save-skill button.

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
        baseline UNLESS one already exists (never overwritten). Exit 1 on FAIL.

    python tools/reimport_correlate.py postclick <skill> [--version X.Y]
                                        [--no-append] [--clear-ledger]
        Everything after "saved" in one call (added 2026-09-23): prints
        main.log liveness + the last sync events, runs `verify`, and ONLY on
        CONFIRMED appends the event-log line via append-event-log.py
        --entry-file (dated `## ` header, exit 0 required). On NO-CHANGE /
        MOVED-ONLY / any non-CONFIRMED verdict it STOPS: prints the log tail,
        appends nothing, exits 1. --version defaults to the repo SKILL.md
        `version:` frontmatter token if present. --clear-ledger runs
        `pending_reimport.py clear <skill>` only AFTER the append exited 0.
        --no-append verifies only (safe to re-run).

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
import zipfile
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pending_reimport import CACHE_ROOT, REPO  # noqa: E402

BASELINE_DIR = REPO / '_staging' / 'reimport-baselines'

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


def cmd_baseline(skills: list[str]) -> int:
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
    for a skill that already existed."""
    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    for skill in skills:
        ct = _creation_time(skill)
        path = BASELINE_DIR / f'{skill}.json'
        if ct is None:
            path.write_text(json.dumps({'skill': skill, 'creation_time': None}, indent=2))
            print(f'{skill}: baseline ABSENT (no cache dir yet -- first install) -> {path}')
            continue
        path.write_text(json.dumps({'skill': skill, 'creation_time': ct.isoformat()}, indent=2))
        print(f'{skill}: baseline {ct.isoformat()} -> {path}')
    return 0


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
            path = BASELINE_DIR / f'{skill}.json'
            if not path.is_file():
                if current is None:
                    print(f'{skill}: NO-CACHE -- cache dir not found under {CACHE_ROOT}')
                else:
                    print(f'{skill}: NO-BASELINE -- run `baseline {skill}` first, or pass '
                          f'--baseline "YYYY-MM-DD HH:MM:SS"')
                any_confirmed_missing = True
                continue
            stored = json.loads(path.read_text())['creation_time']
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
        bp = BASELINE_DIR / f'{skill}.json'
        if bp.is_file():
            base_note = f'baseline kept ({json.loads(bp.read_text())["creation_time"]})'
        else:
            with contextlib.redirect_stdout(io.StringIO()):
                cmd_baseline([skill])
            base_note = 'baseline CAPTURED'
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


def cmd_postclick(skill: str, version: str | None, no_append: bool, clear_ledger: bool) -> int:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        cmd_verify([skill], None)
    verdict = buf.getvalue().strip()
    print(verdict)
    _log_report(6)
    if f'{skill}: CONFIRMED' not in verdict:
        print('STOP: verdict is not CONFIRMED. Nothing appended. Do not repackage, edit or commit; '
              'report the log state above.')
        return 1
    if no_append:
        print('CONFIRMED (--no-append: event log untouched).')
        return 0
    version = version or _repo_version(skill)
    vtxt = f' v{version}' if version else ''
    today = datetime.now().strftime('%Y-%m-%d')
    ef = REPO / '_staging' / f'_eventlog_entry_{skill}.md'
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
    if clear_ledger:
        c = subprocess.run([sys.executable, str(PENDING), 'clear', skill],
                           capture_output=True, text=True)
        print((c.stdout + c.stderr).strip())
        return c.returncode
    return 0


def _pop(rest: list[str], flag: str, has_val: bool):
    if flag not in rest:
        return None, rest
    i = rest.index(flag)
    if has_val:
        return rest[i + 1], rest[:i] + rest[i + 2:]
    return True, rest[:i] + rest[i + 1:]


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ('baseline', 'verify', 'precheck', 'postclick'):
        print(__doc__)
        return 2
    cmd, rest = args[0], args[1:]
    baseline_override, rest = _pop(rest, '--baseline', True)
    version, rest = _pop(rest, '--version', True)
    no_append, rest = _pop(rest, '--no-append', False)
    clear_ledger, rest = _pop(rest, '--clear-ledger', False)
    if not rest:
        print('no skill name(s) given', file=sys.stderr)
        return 2
    if cmd == 'baseline':
        return cmd_baseline(rest)
    if cmd == 'precheck':
        return cmd_precheck(rest)
    if cmd == 'postclick':
        return cmd_postclick(rest[0], version, bool(no_append), bool(clear_ledger))
    return cmd_verify(rest, baseline_override)


if __name__ == '__main__':
    sys.exit(main())
