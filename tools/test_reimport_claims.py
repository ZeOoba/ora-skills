"""tools/reimport_claims.py: ONE session logs a Save-skill reimport (2026-11-13: two sessions
logged the same 13 installs). The installing session's precheck claims it, taking over any
earlier claim (PR #260 review finding 1); loggers refuse another session's claim.

Most tests use a fake claim library. RealClaimWork runs the real ~/.claude/hooks/lib/
claim_work.py against a TEMPORARY claims dir (ORA_ACTIVE_WORK_DIR), and is skipped where that
file does not exist (CI). No test touches the real claims directory."""
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reimport_claims as claims  # noqa: E402


class FakeLib:
    """The slice of claim_work.py reimport_claims uses, with claim_work's ownership rules."""

    def __init__(self, me='session-me'):
        self.me = me
        self.claims = {}
        self.released = []

    def own_session_id(self):
        return self.me

    def own_host_session_id(self):
        return ''

    def attributable_session(self, c):
        sid = (c or {}).get('session_id')
        if not isinstance(sid, str):
            return None
        sid = sid.strip()
        return sid if sid and sid != '?' else None

    def find_claim(self, slug):
        return self.claims.get(slug)

    def write_claim(self, slug, session_id, description, title=None, cwd=None, base_dir=None,
                    now=None, paths=None, host_session_id=None, prior_claim=None,
                    prior_claim_reason=None):
        # Same signature as claim_work.write_claim, so an API drift fails here, not silently.
        c = {'slug': slug, 'session_id': session_id, 'description': description,
             'age_minutes': 0.0, 'paths': paths or []}
        if prior_claim:
            c['prior_claim'] = prior_claim
            c['prior_claim_reason'] = prior_claim_reason
        self.claims[slug] = c

    def release_claim(self, slug, base_dir=None):
        self.released.append(slug)
        return self.claims.pop(slug, None) is not None


class Claim(unittest.TestCase):
    def test_unclaimed_reimport_is_claimed_without_paths(self):
        lib = FakeLib()
        self.assertIsNone(claims.claim('daily-brief', 'install', lib=lib))
        c = lib.claims['reimport-daily-brief']
        self.assertEqual(c['session_id'], 'session-me')
        self.assertEqual(c['paths'], [], 'paths would make shared-checkout-guard warn others')

    def test_another_sessions_claim_is_taken_over_and_recorded(self):
        lib = FakeLib()
        prior = {'session_id': 'cb36d24b', 'description': 'build', 'age_minutes': 4.0}
        lib.claims['reimport-daily-brief'] = prior
        notice = claims.claim('daily-brief', 'install', lib=lib)
        self.assertIn('TAKEN OVER from session cb36d24b', notice)
        c = lib.claims['reimport-daily-brief']
        self.assertEqual(c['session_id'], 'session-me')
        self.assertEqual(c['prior_claim'], prior)
        self.assertEqual(c['prior_claim_reason'], 'force')

    def test_own_claim_is_renewed_quietly(self):
        lib = FakeLib()
        lib.claims['reimport-x'] = {'session_id': 'session-me', 'description': 'old'}
        self.assertIsNone(claims.claim('x', 'new', lib=lib))
        self.assertEqual(lib.claims['reimport-x']['description'], 'new')
        self.assertNotIn('prior_claim', lib.claims['reimport-x'])

    def test_claim_write_failure_never_blocks(self):
        lib = FakeLib()
        lib.write_claim = lambda *a, **k: (_ for _ in ()).throw(OSError('locked'))
        self.assertIn('not written', claims.claim('x', 'p', lib=lib))


class ForeignHolder(unittest.TestCase):
    def test_unknown_bridge_session_claim_is_foreign_to_a_code_session(self):
        lib = FakeLib(me='cb36d24b')
        lib.claims['reimport-x'] = {'session_id': 'unknown', 'description': 'bridge install'}
        self.assertIsNotNone(claims.foreign_holder('x', lib=lib))

    def test_unattributable_claim_is_not_foreign(self):
        lib = FakeLib()
        lib.claims['reimport-x'] = {'session_id': '?', 'description': 'malformed'}
        self.assertIsNone(claims.foreign_holder('x', lib=lib))

    def test_describe_offers_a_claim_only_takeover_never_a_precheck_rerun(self):
        # PR #260 re-review finding A: after the click, re-running precheck resets the
        # baseline and the install can no longer be logged.
        msg = claims.describe('x', {'session_id': 'abc', 'description': 'd', 'age_minutes': 2})
        self.assertIn('CLAIMED by session abc', msg)
        self.assertIn('claim reimport-x "logging the install" --force', msg)
        self.assertIn('do NOT re-run precheck', msg)


class ReleaseAndFailOpen(unittest.TestCase):
    def test_release_only_our_own_claim(self):
        lib = FakeLib()
        lib.claims['reimport-x'] = {'session_id': 'other', 'description': 'd'}
        self.assertFalse(claims.release('x', lib=lib))
        self.assertIn('reimport-x', lib.claims)
        lib.claims['reimport-x'] = {'session_id': 'session-me', 'description': 'd'}
        self.assertTrue(claims.release('x', lib=lib))
        self.assertNotIn('reimport-x', lib.claims)

    def test_no_claim_library_is_fail_open(self):
        with mock.patch.object(claims, 'load_lib', lambda: None):
            self.assertIsNone(claims.claim('x', 'p'))
            self.assertIsNone(claims.foreign_holder('x'))
            self.assertFalse(claims.release('x'))

    def test_loader_does_not_put_the_claim_dir_on_sys_path(self):
        # PR #260 review finding 8: no module shadowing.
        with mock.patch.object(claims, '_lib_cache', claims._UNLOADED):
            claims.load_lib()
        self.assertNotIn(str(claims.CLAIM_LIB), sys.path)


REAL = claims.CLAIM_LIB / 'claim_work.py'


@unittest.skipUnless(REAL.is_file(), 'claim_work.py not on this machine (CI)')
class RealClaimWork(unittest.TestCase):
    """PR #260 review finding 9: the fake must not hide an API drift in the real library."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='reimport_claims_test_')
        env = mock.patch.dict(os.environ, {'ORA_ACTIVE_WORK_DIR': self.tmp,
                                           'CLAUDE_CODE_SESSION_ID': 'test-session-A'})
        env.start()
        self.addCleanup(env.stop)
        spec = importlib.util.spec_from_file_location('_claim_work_under_test', REAL)
        self.lib = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.lib)           # CLAIMS_DIR is read now: the temp dir
        self.assertEqual(os.path.normcase(self.lib.CLAIMS_DIR), os.path.normcase(self.tmp))

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_claim_takeover_foreign_check_and_release_against_the_real_library(self):
        self.assertIsNone(claims.claim('demo-skill', 'install', lib=self.lib))
        self.assertIsNone(claims.foreign_holder('demo-skill', lib=self.lib))
        with mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': 'test-session-B'}):
            self.assertIsNotNone(claims.foreign_holder('demo-skill', lib=self.lib))
            notice = claims.claim('demo-skill', 'install', lib=self.lib)
            self.assertIn('TAKEN OVER from session test-session-A', notice)
            self.assertEqual(self.lib.read_prior_claim('reimport-demo-skill')['session_id'],
                             'test-session-A')
        self.assertIsNotNone(claims.foreign_holder('demo-skill', lib=self.lib))
        self.assertFalse(claims.release('demo-skill', lib=self.lib))
        with mock.patch.dict(os.environ, {'CLAUDE_CODE_SESSION_ID': 'test-session-B'}):
            self.assertTrue(claims.release('demo-skill', lib=self.lib))
        self.assertEqual(os.listdir(self.tmp), [])


if __name__ == '__main__':
    unittest.main()
