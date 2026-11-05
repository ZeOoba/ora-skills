#!/usr/bin/env python3
"""Tests for pm_crons_log_check. Stdlib only: python automation-health-monitor/tests/test_pm_crons_log_check.py

The REAL_LOG fixture is copied verbatim from C:\\Users\\Owner\\ora-pm-cron\\cron.log
(2026-10-05 .. 2026-11-02 runs; counters only, no tenant data). Run starts are the
ora-pm-daily-crons `list_task_runs` started_at values read 2026-11-05.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'scripts'))
import pm_crons_log_check as m  # noqa: E402

REAL_LOG = """\
2026-09-14T10:29:39.4503481-04:00  delinquency-check  SEND SUPPRESSED  reason=suppressed-repeat tracked=OI-278 absent_since=2026-09-13T09:47:13 last_notified=2026-09-13T09:47:13
2026-10-05T10:21:33.0055741-04:00  critical-dates-alerts  ->  HTTP 200  {"new_alerts":7,"skipped":31} email.subject="[ORA PM] 7 Critical Dates \ufffd 2026-10-05"
2026-10-05T10:21:34.3834715-04:00  critical-dates-alerts  SEND OK  subject="[ORA PM] 7 Critical Dates \ufffd 2026-10-05" attempt=1
2026-10-05T10:21:35.4568296-04:00  delinquency-check  ->  HTTP 200  {"late_fees_posted":0,"delinquent_count":139,"payments_feed_absent":true} email.subject="PAYMENTS FEED ABSENT"
2026-10-05T10:21:35.9986621-04:00  delinquency-check  SEND OK  subject="PAYMENTS FEED ABSENT" attempt=1
2026-10-13T10:11:48.4084685-04:00  critical-dates-alerts  ->  ERROR 500  The remote server returned an error: (500) Internal Server Error.
2026-10-13T10:11:48.9905673-04:00  delinquency-check  ->  ERROR 500  The remote server returned an error: (500) Internal Server Error.
2026-10-19T09:59:59.4527038-04:00  critical-dates-alerts  ->  ERROR 500  The remote server returned an error: (500) Internal Server Error.
2026-10-19T10:00:00.0291158-04:00  delinquency-check  ->  ERROR 500  The remote server returned an error: (500) Internal Server Error.
2026-10-26T11:00:25.9449401-04:00  critical-dates-alerts  ->  ERROR 500  The remote server returned an error: (500) Internal Server Error.
2026-10-26T11:00:26.5782204-04:00  delinquency-check  ->  ERROR 500  The remote server returned an error: (500) Internal Server Error.
2026-11-02T10:01:57.5674203-05:00  critical-dates-alerts  ->  ERROR 500  The remote server returned an error: (500) Internal Server Error.
2026-11-02T10:01:58.0182114-05:00  delinquency-check  ->  ERROR 500  The remote server returned an error: (500) Internal Server Error.
"""

# (run start = lastRunAt, end of that run's window = next run start)
RUNS = [
    ('2026-10-05T14:21:23.781Z', '2026-10-13T14:11:37.058Z'),
    ('2026-10-13T14:11:37.058Z', '2026-10-19T13:49:18.205Z'),
    ('2026-10-19T13:49:18.205Z', '2026-10-26T15:00:12.484Z'),
    ('2026-10-26T15:00:12.484Z', '2026-11-02T15:01:50.548Z'),
    ('2026-11-02T15:01:50.548Z', '2026-11-05T21:00:00Z'),
]

# Lines in the format ping-crons.ps1 writes since 2026-11-05 (built from its own
# format strings: ping-crons.ps1 lines 473 and 493, ping-crons-lib.ps1 lines 249/303).
NEW_FAIL = """\
2026-11-09T09:50:01.1000000-05:00  critical-dates-alerts  ->  ERROR 500  The remote server returned an error: (500) Internal Server Error.  cf_error=1016 (Supabase project likely PAUSED: Cloudflare origin DNS error inside the app's JSON error; restore it from the Supabase dashboard)
2026-11-09T09:50:01.6000000-05:00  delinquency-check  ->  ERROR 500  The remote server returned an error: (500) Internal Server Error.  cf_error=1016 (Supabase project likely PAUSED: Cloudflare origin DNS error inside the app's JSON error; restore it from the Supabase dashboard)
2026-11-09T09:50:03.2000000-05:00  run-failure-alert  SEND FAILED  exit=6 attempt=1 subject="CRON FAILURE - [ORA PM] 2 of 2 endpoints failed - Supabase project likely PAUSED - 2026-11-09"
2026-11-09T09:50:04.0000000-05:00  ping-crons  RUN FAILED: 2 of 2 ora-pm cron endpoints failed (critical-dates-alerts HTTP 500 cf_error=1016; delinquency-check HTTP 500 cf_error=1016). Supabase project likely PAUSED.  failure-alert=SEND FAILED exit=6
"""
NEW_START = '2026-11-09T14:48:31Z'
NEW_NOW = '2026-11-09T16:17:00Z'

OK_RUN = """\
2026-11-16T09:49:10.0000000-05:00  critical-dates-alerts  ->  HTTP 200  {"new_alerts":0,"skipped":38}
2026-11-16T09:49:11.0000000-05:00  delinquency-check  ->  HTTP 200  {"late_fees_posted":0,"delinquent_count":12}
"""


def run(text, start, until):
    return m.check(text.splitlines(), m.parse_ts(start), m.parse_ts(until))


class RealLogBacktest(unittest.TestCase):
    def test_1005_is_ok(self):
        r = run(REAL_LOG, *RUNS[0])
        self.assertEqual(r['verdict'], 'OK', r)
        self.assertEqual(r['findings'], [])

    def test_failed_weeks_flag(self):
        for start, until in RUNS[1:]:
            with self.subTest(start=start):
                r = run(REAL_LOG, start, until)
                self.assertEqual(r['verdict'], 'FAIL', r)
                kinds = sorted(f['kind'] for f in r['findings'])
                self.assertEqual(kinds, ['ENDPOINT-ERROR', 'ENDPOINT-ERROR'])
                self.assertEqual({f['endpoint'] for f in r['findings']},
                                 {'critical-dates-alerts', 'delinquency-check'})
                self.assertTrue(all(f['status'] == '500' for f in r['findings']))
                # pre-2026-11-05 script: no RUN FAILED line, so no alert token
                self.assertIsNone(r['failure_alert'])

    def test_previous_week_lines_excluded(self):
        # the 10-13 window must not see the 10-05 OK lines or the 10-19 errors
        r = run(REAL_LOG, *RUNS[1])
        self.assertEqual(len(r['endpoint_lines']), 2)
        self.assertTrue(all(l.startswith('2026-10-13') for l in r['endpoint_lines']))


class NewFormat(unittest.TestCase):
    def test_run_failed_line_and_verbatim_tokens(self):
        r = run(NEW_FAIL, NEW_START, NEW_NOW)
        self.assertEqual(r['verdict'], 'FAIL')
        self.assertIn('RUN-FAILED', [f['kind'] for f in r['findings']])
        self.assertEqual(r['failure_alert'], 'failure-alert=SEND FAILED exit=6')
        self.assertEqual(r['cf_errors'], [
            "cf_error=1016 (Supabase project likely PAUSED: Cloudflare origin DNS error inside the app's JSON error; restore it from the Supabase dashboard)"])
        rf = [f for f in r['findings'] if f['kind'] == 'RUN-FAILED'][0]
        self.assertTrue(rf['line'].startswith('2026-11-09T09:50:04'))

    def test_run_failed_alone_flags(self):
        line = NEW_FAIL.splitlines()[-1].replace('failure-alert=SEND FAILED exit=6', 'failure-alert=SEND OK')
        text = OK_RUN.replace('2026-11-16', '2026-11-09') + line + '\n'
        r = run(text, NEW_START, NEW_NOW)
        self.assertEqual(r['verdict'], 'FAIL')
        self.assertEqual([f['kind'] for f in r['findings']], ['RUN-FAILED'])
        self.assertEqual(r['failure_alert'], 'failure-alert=SEND OK')

    def test_run_failed_without_alert_token(self):
        text = '2026-11-09T09:50:04.0-05:00  ping-crons  RUN FAILED: 1 of 2 ora-pm cron endpoints failed (x).\n'
        r = run(text, NEW_START, NEW_NOW)
        self.assertEqual(r['verdict'], 'FAIL')
        self.assertEqual(r['failure_alert'], m.ALERT_TOKEN_ABSENT)

    def test_clean_run_ok(self):
        r = run(OK_RUN, '2026-11-16T14:48:00Z', '2026-11-16T16:20:00Z')
        self.assertEqual(r['verdict'], 'OK')
        self.assertIsNone(r['failure_alert'])
        self.assertEqual(r['cf_errors'], [])


class MissingAndPending(unittest.TestCase):
    def test_one_endpoint_missing(self):
        text = OK_RUN.splitlines()[0] + '\n'
        r = run(text, '2026-11-16T14:48:00Z', '2026-11-16T16:20:00Z')
        self.assertEqual(r['verdict'], 'FAIL')
        self.assertEqual(r['findings'], [{'kind': 'ENDPOINT-MISSING', 'endpoint': 'delinquency-check'}])

    def test_no_lines_after_grace_is_fail(self):
        r = run(REAL_LOG, '2026-11-16T14:48:00Z', '2026-11-16T16:20:00Z')
        self.assertEqual(r['verdict'], 'FAIL')
        self.assertEqual(sorted(f['endpoint'] for f in r['findings']),
                         ['critical-dates-alerts', 'delinquency-check'])

    def test_no_lines_inside_grace_is_pending(self):
        r = run('', '2026-11-16T14:48:00Z', '2026-11-16T15:10:00Z')
        self.assertEqual(r['verdict'], 'PENDING')

    def test_error_inside_grace_still_fails(self):
        r = run(NEW_FAIL, NEW_START, '2026-11-09T14:52:00Z')
        self.assertEqual(r['verdict'], 'FAIL')

    def test_send_lines_do_not_count_as_endpoint_result(self):
        text = ('2026-11-16T09:49:10.0-05:00  critical-dates-alerts  SEND OK  subject="x" attempt=1\n'
                + OK_RUN.splitlines()[1] + '\n')
        r = run(text, '2026-11-16T14:48:00Z', '2026-11-16T16:20:00Z')
        self.assertEqual(r['findings'], [{'kind': 'ENDPOINT-MISSING', 'endpoint': 'critical-dates-alerts'}])


class Parsing(unittest.TestCase):
    def test_transport_error_without_status(self):
        text = ("2026-06-24T09:00:03.3073279-04:00  critical-dates-alerts  ->  ERROR   The remote name could not be resolved: 'ora-pm.pages.dev'\n"
                "2026-06-24T09:00:03.3073279-04:00  delinquency-check  ->  HTTP 200  {}\n")
        r = run(text, '2026-06-24T12:59:00Z', '2026-06-25T12:00:00Z')
        self.assertEqual(r['findings'], [{'kind': 'ENDPOINT-ERROR', 'endpoint': 'critical-dates-alerts', 'status': '',
                                          'line': text.splitlines()[0]}])

    def test_non_2xx_http_line_is_error(self):
        text = OK_RUN.replace('HTTP 200  {"late', 'HTTP 302  {"late')
        r = run(text, '2026-11-16T14:48:00Z', '2026-11-16T16:20:00Z')
        self.assertEqual([(f['kind'], f['status']) for f in r['findings']], [('ENDPOINT-ERROR', '302')])

    def test_mixed_offsets_and_seven_digit_fraction(self):
        self.assertEqual(m.parse_ts('2026-09-02T12:41:42.7279553+02:00'), m.parse_ts('2026-09-02T10:41:42.727955Z'))

    def test_garbage_lines_counted_not_fatal(self):
        r = run('not a log line\n' + OK_RUN, '2026-11-16T14:48:00Z', '2026-11-16T16:20:00Z')
        self.assertEqual(r['verdict'], 'OK')
        self.assertEqual(r['unparsed_lines'], 1)

    def test_recovered_after_failure_still_fails_but_notes_it(self):
        text = NEW_FAIL + OK_RUN.replace('2026-11-16T09:49', '2026-11-09T10:30')
        r = run(text, NEW_START, NEW_NOW)
        self.assertEqual(r['verdict'], 'FAIL')
        self.assertTrue(r['later_clean_pass'])


class Cli(unittest.TestCase):
    def test_subprocess_cp1252_console_with_replacement_char(self):
        # regression: the real 10-05 line holds U+FFFD; a cp1252 stdout crashed with exit 1
        import json
        import os
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / 'cron.log'
            log.write_text(REAL_LOG, encoding='utf-8')
            env = dict(os.environ, PYTHONIOENCODING='cp1252')
            p = subprocess.run([sys.executable, str(Path(m.__file__)), '--last-run-at', RUNS[0][0],
                                '--log', str(log), '--now', RUNS[0][1]],
                               capture_output=True, env=env)
            self.assertEqual(p.returncode, m.EXIT_OK, p.stderr)
            self.assertEqual(json.loads(p.stdout)['verdict'], 'OK')

    def test_unreadable_log(self):
        rc, out = m.main(['--last-run-at', NEW_START, '--log', str(Path(__file__).parent / 'nope.log'), '--now', NEW_NOW])
        self.assertEqual(rc, m.EXIT_UNREADABLE)
        self.assertEqual(out['verdict'], 'UNREADABLE')

    def test_missing_last_run_at_is_unverifiable(self):
        rc, out = m.main(['--last-run-at', '', '--now', NEW_NOW])
        self.assertEqual(rc, m.EXIT_UNREADABLE)
        self.assertEqual(out['verdict'], 'UNVERIFIABLE')


if __name__ == '__main__':
    unittest.main()
