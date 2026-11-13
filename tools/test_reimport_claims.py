"""tools/reimport_claims.py: one session owns a Save-skill reimport from pre-check to log
(2026-11-13: two sessions logged the same 13 installs). Uses a fake claim library, so no
test ever touches the real ~/.claude claims directory."""
import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path

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

    def write_claim(self, slug, session_id, description, **kw):
        self.claims[slug] = {'slug': slug, 'session_id': session_id, 'description': description,
                             'age_minutes': 0.0, 'paths': kw.get('paths', [])}

    def release_claim(self, slug):
        self.released.append(slug)
        return self.claims.pop(slug, None) is not None


class Claim(unittest.TestCase):
    def test_unclaimed_reimport_is_claimed_for_this_session(self):
        lib = FakeLib()
        self.assertIsNone(claims.claim('daily-brief', 'prep', lib=lib))
        c = lib.claims['reimport-daily-brief']
        self.assertEqual(c['session_id'], 'session-me')
        self.assertTrue(c['paths'][0].endswith('daily-brief'))

    def test_another_sessions_claim_blocks_and_names_the_holder_and_the_override(self):
        lib = FakeLib()
        lib.claims['reimport-daily-brief'] = {'session_id': 'cb36d24b', 'description': 'install',
                                              'age_minutes': 4.0}
        msg = claims.claim('daily-brief', 'prep', lib=lib)
        self.assertIn('CLAIMED by session cb36d24b', msg)
        self.assertIn('release reimport-daily-brief --force', msg)
        self.assertEqual(lib.claims['reimport-daily-brief']['session_id'], 'cb36d24b')

    def test_unknown_bridge_session_claim_blocks_a_code_session(self):
        # The 2026-11-13 collision: a Desktop Commander bridge session has no session id.
        lib = FakeLib(me='cb36d24b')
        lib.claims['reimport-x'] = {'session_id': 'unknown', 'description': 'bridge install'}
        self.assertIsNotNone(claims.claim('x', 'p', lib=lib))
        self.assertIsNotNone(claims.foreign_holder('x', lib=lib))

    def test_own_claim_is_renewed_not_blocked(self):
        lib = FakeLib()
        lib.claims['reimport-x'] = {'session_id': 'session-me', 'description': 'old'}
        self.assertIsNone(claims.claim('x', 'new', lib=lib))
        self.assertEqual(lib.claims['reimport-x']['description'], 'new')

    def test_unattributable_claim_does_not_block(self):
        lib = FakeLib()
        lib.claims['reimport-x'] = {'session_id': '?', 'description': 'malformed'}
        self.assertIsNone(claims.claim('x', 'p', lib=lib))

    def test_claim_write_failure_never_blocks(self):
        lib = FakeLib()
        lib.write_claim = lambda *a, **k: (_ for _ in ()).throw(OSError('locked'))
        buf = io.StringIO()
        with redirect_stdout(buf):
            self.assertIsNone(claims.claim('x', 'p', lib=lib))
        self.assertIn('not written', buf.getvalue())


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
        orig = claims.load_lib
        claims.load_lib = lambda: None
        try:
            self.assertIsNone(claims.claim('x', 'p'))
            self.assertIsNone(claims.foreign_holder('x'))
            self.assertFalse(claims.release('x'))
        finally:
            claims.load_lib = orig


if __name__ == '__main__':
    unittest.main()
