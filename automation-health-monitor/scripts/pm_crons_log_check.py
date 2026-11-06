#!/usr/bin/env python3
"""Read-only verdict on the latest ora-pm-daily-crons run, from cron.log alone.

automation-health-monitor Step 1.8. Independent of the scheduler's session status
(`list_task_runs` "succeeded" means only that the session ended) and of Outlook COM
(the script's own CRON FAILURE alert can fail to send). Reads one file; never calls
the ora-pm endpoints, never re-runs the task, never writes anything.

Usage:
  python pm_crons_log_check.py --last-run-at <lastRunAt ISO> [--log PATH] [--now ISO] [--grace-min 60]

Prints one JSON object. Exit: 0 OK, 1 FAIL, 3 PENDING, 4 UNREADABLE/UNVERIFIABLE.

Window = [lastRunAt - 2 min, now]. Within it, FAIL when any of:
  - a `ping-crons  RUN FAILED:` line                                     -> RUN-FAILED
  - an endpoint result line `->  ERROR ...` or `->  HTTP <non-2xx>`       -> ENDPOINT-ERROR
  - no `->` result line at all for critical-dates-alerts / delinquency-check -> ENDPOINT-MISSING
ENDPOINT-MISSING only counts once `now` is past lastRunAt + grace (the run may still be
in flight); before that, a window with no failure line is PENDING.
The `cf_error=` notes and the `failure-alert=` result are carried verbatim.
"""
import argparse
import json
import re
import sys
from datetime import datetime, timedelta, timezone

DEFAULT_LOG = r'C:\Users\Owner\ora-pm-cron\cron.log'
ENDPOINTS = ('critical-dates-alerts', 'delinquency-check')
SLACK = timedelta(minutes=2)
ALERT_TOKEN_ABSENT = 'failure-alert=<absent: RUN FAILED line carries no failure-alert token>'
EXIT_OK, EXIT_FAIL, EXIT_PENDING, EXIT_UNREADABLE = 0, 1, 3, 4

LINE_RE = re.compile(r'^(\S+)  (\S+)  (.*)$')
RESULT_RE = re.compile(r'^->  (?:HTTP (\d{3})\b|ERROR\b ?(\S*))')
CF_RE = re.compile(r'cf_error=.*$')
ALERT_RE = re.compile(r'failure-alert=(?:SEND OK|SEND FAILED exit=-?\d+)')
FRAC_RE = re.compile(r'(\.\d{6})\d+')


def parse_ts(s):
    """ISO 8601 with offset or Z; PowerShell's 7-digit fraction is truncated to 6."""
    s = s.strip()
    if s.endswith('Z'):
        s = s[:-1] + '+00:00'
    s = FRAC_RE.sub(r'\1', s)
    d = datetime.fromisoformat(s)
    if d.tzinfo is None:
        raise ValueError('timestamp without offset: %r' % s)
    return d.astimezone(timezone.utc)


def check(lines, last_run_at, now, grace=timedelta(minutes=60)):
    start = last_run_at - SLACK
    findings, endpoint_lines, cf_errors = [], [], []
    seen = {ep: False for ep in ENDPOINTS}
    failure_alert = None
    unparsed = 0
    last_fail_at = None
    clean_after = {}

    for raw in lines:
        line = raw.rstrip('\r\n')
        if not line.strip():
            continue
        mt = LINE_RE.match(line)
        if not mt:
            unparsed += 1
            continue
        try:
            ts = parse_ts(mt.group(1))
        except ValueError:
            unparsed += 1
            continue
        if ts < start or ts > now:
            continue
        who, rest = mt.group(2), mt.group(3)

        if who == 'ping-crons' and rest.startswith('RUN FAILED:'):
            findings.append({'kind': 'RUN-FAILED', 'line': line})
            am = ALERT_RE.search(rest)
            failure_alert = am.group(0) if am else ALERT_TOKEN_ABSENT
            last_fail_at = ts
            continue

        if who in ENDPOINTS:
            rm = RESULT_RE.match(rest)
            if not rm:
                continue  # SEND OK / SEND SUPPRESSED / FEED STATE lines are not endpoint results
            seen[who] = True
            endpoint_lines.append(line)
            http = rm.group(1)
            if http is not None and http.startswith('2'):
                clean_after.setdefault(who, []).append(ts)
                continue
            status = http if http is not None else rm.group(2)
            findings.append({'kind': 'ENDPOINT-ERROR', 'endpoint': who, 'status': status, 'line': line})
            cm = CF_RE.search(rest)
            if cm and cm.group(0) not in cf_errors:
                cf_errors.append(cm.group(0))
            last_fail_at = ts

    in_grace = now < last_run_at + grace
    missing = [ep for ep in ENDPOINTS if not seen[ep]]
    if missing and not in_grace:
        findings.extend({'kind': 'ENDPOINT-MISSING', 'endpoint': ep} for ep in missing)

    if findings:
        verdict = 'FAIL'
    elif missing:
        verdict = 'PENDING'
    else:
        verdict = 'OK'

    later_clean = bool(last_fail_at) and all(
        any(t > last_fail_at for t in clean_after.get(ep, [])) for ep in ENDPOINTS)

    return {
        'verdict': verdict,
        'window_utc': [start.isoformat(), now.isoformat()],
        'findings': findings,
        'cf_errors': cf_errors,
        'failure_alert': failure_alert,
        'later_clean_pass': later_clean,
        'endpoint_lines': endpoint_lines,
        'unparsed_lines': unparsed,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--last-run-at', required=True, help='ora-pm-daily-crons lastRunAt from list_scheduled_tasks')
    ap.add_argument('--log', default=DEFAULT_LOG)
    ap.add_argument('--now', default=None, help='end of window (default: current time)')
    ap.add_argument('--grace-min', type=int, default=60)
    a = ap.parse_args(argv)

    try:
        last = parse_ts(a.last_run_at)
        now = parse_ts(a.now) if a.now else datetime.now(timezone.utc)
    except ValueError as e:
        return EXIT_UNREADABLE, {'verdict': 'UNVERIFIABLE', 'error': 'bad --last-run-at/--now: %s' % e}
    try:
        with open(a.log, encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()
    except OSError as e:
        return EXIT_UNREADABLE, {'verdict': 'UNREADABLE', 'error': '%s: %s' % (type(e).__name__, e), 'log': a.log}

    out = check(lines, last, now, timedelta(minutes=a.grace_min))
    out['log'] = a.log
    out['last_run_at'] = last.isoformat()
    rc = {'OK': EXIT_OK, 'FAIL': EXIT_FAIL, 'PENDING': EXIT_PENDING}[out['verdict']]
    return rc, out


if __name__ == '__main__':
    code, result = main()
    # ASCII-escaped on purpose: cron.log carries U+FFFD (PowerShell wrote an em dash as
    # cp1252), and printing it raw to a cp1252 console raised UnicodeEncodeError -> exit 1,
    # indistinguishable from FAIL by exit code alone (found 2026-11-05 on the real log).
    print(json.dumps(result, indent=2, ensure_ascii=True))
    sys.exit(code)
