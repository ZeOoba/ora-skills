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

import json
import re
import sys
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


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2 or args[0] not in ('baseline', 'verify'):
        print(__doc__)
        return 2
    cmd, rest = args[0], args[1:]
    baseline_override = None
    if '--baseline' in rest:
        i = rest.index('--baseline')
        baseline_override = rest[i + 1]
        rest = rest[:i] + rest[i + 2:]
    skills = rest
    if not skills:
        print('no skill name(s) given', file=sys.stderr)
        return 2
    if cmd == 'baseline':
        return cmd_baseline(skills)
    return cmd_verify(skills, baseline_override)


if __name__ == '__main__':
    sys.exit(main())
