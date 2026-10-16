"""Tests for tools/capture_runtime_cache.py: pure helpers, plus an end-to-end run against
a synthetic git repo / origin / cache (never the live repo or runtime cache)."""
import io
import os
import subprocess
import sys
from contextlib import redirect_stdout
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import capture_runtime_cache as crc  # noqa: E402


class FingerprintTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name) / 'demo-skill'
        self.d.mkdir()
        (self.d / 'SKILL.md').write_text('---\nname: demo-skill\n---\nbody\n', encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def test_stable_when_nothing_changes(self):
        self.assertEqual(crc.fingerprint(self.d), crc.fingerprint(self.d))

    def test_changes_when_a_file_is_added(self):
        before = crc.fingerprint(self.d)
        (self.d / 'references').mkdir()
        (self.d / 'references' / 'x.md').write_text('x', encoding='utf-8')
        self.assertNotEqual(before, crc.fingerprint(self.d))

    def test_changes_when_content_size_changes(self):
        before = crc.fingerprint(self.d)
        (self.d / 'SKILL.md').write_text('---\nname: demo-skill\n---\nlonger body\n',
                                         encoding='utf-8')
        self.assertNotEqual(before, crc.fingerprint(self.d))

    def test_changes_when_mtime_moves(self):
        before = crc.fingerprint(self.d)
        t = time.time() + 120
        os.utime(self.d / 'SKILL.md', (t, t))
        self.assertNotEqual(before, crc.fingerprint(self.d))


class SelectionTests(unittest.TestCase):
    def test_changed_skills_new_and_moved_only(self):
        cur = {'a': '1', 'b': '2', 'c': '3'}
        prev = {'a': '1', 'b': 'old'}
        self.assertEqual(crc.changed_skills(cur, prev), ['b', 'c'])

    def test_changed_skills_first_run_is_everything(self):
        self.assertEqual(crc.changed_skills({'x': '1', 'y': '2'}, {}), ['x', 'y'])

    def test_files_to_capture_only_never_committed_verdicts(self):
        per = [('SKILL.md', 'CACHE-AHEAD'), ('scripts/a.py', 'IN-SYNC'),
               ('references/new.md', 'REPO-MISSING'), ('b.md', 'DIVERGENT'),
               ('c.md', 'MAIN-BEHIND-ORIGIN'), ('d.md', 'REPO-AHEAD'), ('e.md', 'UNKNOWN')]
        self.assertEqual(crc.files_to_capture(per), ['SKILL.md', 'references/new.md'])

    def test_files_to_capture_empty(self):
        self.assertEqual(crc.files_to_capture([('SKILL.md', 'IN-SYNC')]), [])

    def test_files_to_capture_drops_tool_debris(self):
        per = [('.pytest_cache/v/cache/nodeids', 'REPO-MISSING'),
               ('scripts/__pycache__/x.cpython-313.pyc', 'REPO-MISSING'),
               ('scripts/x.pyc', 'REPO-MISSING'),
               ('runs/summary.csv', 'CACHE-AHEAD')]
        self.assertEqual(crc.files_to_capture(per), ['runs/summary.csv'])


class IgnoreTests(unittest.TestCase):
    def test_parse_ignore_skips_comments_and_blanks(self):
        text = '# header\n\ndocx\n  pdf  # trailing note\n#xlsx\n'
        self.assertEqual(crc.parse_ignore(text), {'docx', 'pdf'})

    def test_shipped_ignore_file_parses_and_excludes_no_repo_skill(self):
        names = crc.load_ignore()
        self.assertIn('docx', names)
        repo = Path(__file__).resolve().parent.parent
        clashes = sorted(n for n in names if (repo / n / 'SKILL.md').is_file())
        self.assertEqual(clashes, [], 'an ORA repo skill must never be ignored')

    def test_installed_skills_honours_ignore(self):
        with tempfile.TemporaryDirectory() as t:
            root = Path(t)
            for name in ('ora-a', 'docx', 'not-a-skill'):
                (root / name).mkdir()
            (root / 'ora-a' / 'SKILL.md').write_text('x', encoding='utf-8')
            (root / 'docx' / 'SKILL.md').write_text('x', encoding='utf-8')
            self.assertEqual(crc.installed_skills(root, {'docx'}), ['ora-a'])


class DedupTests(unittest.TestCase):
    def test_capture_then_identical_key_is_skipped(self):
        state = {}
        key = {'SKILL.md': 'abc'}
        self.assertFalse(crc.already_captured(state, 's', key))
        crc.record_capture(state, 's', key, 'capture/runtime-cache-1', 'now')
        self.assertTrue(crc.already_captured(state, 's', key))

    def test_new_content_is_not_treated_as_captured(self):
        state = {}
        crc.record_capture(state, 's', {'SKILL.md': 'abc'}, 'b1', 'now')
        self.assertFalse(crc.already_captured(state, 's', {'SKILL.md': 'def'}))
        self.assertFalse(crc.already_captured(state, 'other', {'SKILL.md': 'abc'}))


class TextTests(unittest.TestCase):
    def test_commit_message_names_files_verdicts_and_trailer(self):
        m = crc.commit_message('loi-generation', ['templates/T.docx'],
                               {'templates/T.docx': 'CACHE-AHEAD'}, '2026-09-24T18:19:43Z')
        self.assertTrue(m.startswith('capture(loi-generation): '))
        self.assertIn('- templates/T.docx: CACHE-AHEAD', m)
        self.assertIn('NOT\nreconciled', m)
        self.assertTrue(m.rstrip().endswith(crc.TRAILER))

    def test_pr_body_flags_do_not_merge_and_lists_rows(self):
        body = crc.pr_body([('annual-cycle', ['SKILL.md'], '2026-10-16T00:04:57Z'),
                            ('rent-roll-qc', ['SKILL.md', 'scripts/x.py'], 't2')], 'STAMP')
        self.assertIn('DO NOT MERGE AS-IS', body)
        self.assertIn('| annual-cycle | SKILL.md | 2026-10-16T00:04:57Z |', body)
        self.assertIn('| rent-roll-qc | SKILL.md, scripts/x.py | t2 |', body)
        self.assertIn('STAMP', body)


class ConfidentialGateTests(unittest.TestCase):
    def test_prepush_stdin_is_a_new_ref_line(self):
        line = crc.prepush_stdin('capture/runtime-cache-X', 'a' * 40)
        local_ref, local_sha, remote_ref, remote_sha = line.split()
        self.assertEqual(local_ref, 'refs/heads/capture/runtime-cache-X')
        self.assertEqual(remote_ref, local_ref)
        self.assertEqual(local_sha, 'a' * 40)
        self.assertEqual(remote_sha, '0' * 40)
        self.assertTrue(line.endswith('\n'))

    def test_missing_scanner_fails_closed(self):
        ok, detail = crc.confidential_gate('any-branch', scanner=Path('Z:/no/such/scan.py'))
        self.assertFalse(ok)
        self.assertIn('fail-closed', detail)


def _g(cwd, *args):
    r = subprocess.run(['git', '-C', str(cwd), *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'git {args}: {r.stderr}')
    return r.stdout


class EndToEndTests(unittest.TestCase):
    """Real git, synthetic repo + origin + cache: proves a run commits exactly the
    cache-only files to a capture branch, with the repo's hooks disabled, removes its
    worktree, and that an identical second run captures nothing."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = Path(self.tmp.name)
        self.repo, self.cache, self.marker = t / 'repo', t / 'cache', t / 'hook-fired.txt'
        self.repo.mkdir()
        _g(self.repo, 'init', '-q', '-b', 'main')
        _g(self.repo, 'config', 'user.email', 't@example.com')
        _g(self.repo, 'config', 'user.name', 't')
        _g(self.repo, 'config', 'core.autocrlf', 'false')
        hooks = t / 'hooks'
        hooks.mkdir()
        for name in ('pre-commit', 'post-commit'):
            h = hooks / name
            h.write_text(f'#!/bin/sh\necho {name} >> "{self.marker.as_posix()}"\n',
                         encoding='utf-8', newline='\n')
            h.chmod(0o755)
        _g(self.repo, 'config', 'core.hooksPath', hooks.as_posix())
        (self.repo / 'alpha').mkdir()
        (self.repo / 'alpha' / 'SKILL.md').write_text(
            '---\nname: alpha\ndescription: d\n---\nv1\n', encoding='utf-8', newline='\n')
        _g(self.repo, 'add', '-A')
        _g(self.repo, 'commit', '-q', '-m', 'init')
        self.hooks_fire_normally = self.marker.exists()
        if self.marker.exists():
            self.marker.unlink()
        origin = t / 'origin.git'
        _g(t, 'init', '-q', '--bare', str(origin))
        _g(self.repo, 'remote', 'add', 'origin', str(origin))
        _g(self.repo, 'push', '-q', 'origin', 'main')
        _g(self.repo, 'fetch', '-q', 'origin')
        # cache: alpha edited platform-side (CACHE-AHEAD); beta created platform-side
        (self.cache / 'alpha').mkdir(parents=True)
        (self.cache / 'alpha' / 'SKILL.md').write_text(
            '---\nname: alpha\ndescription: d\n---\nv1\nv2 saved from Cowork\n',
            encoding='utf-8', newline='\n')
        (self.cache / 'beta' / 'references').mkdir(parents=True)
        (self.cache / 'beta' / 'SKILL.md').write_text(
            '---\nname: beta\ndescription: new\n---\nbody\n', encoding='utf-8', newline='\n')
        (self.cache / 'beta' / 'references' / 'r.md').write_text('ref\n', encoding='utf-8')
        (self.cache / 'beta' / '.pytest_cache').mkdir()
        (self.cache / 'beta' / '.pytest_cache' / 'README.md').write_text('x', encoding='utf-8')

        self.saved = {k: getattr(crc, k) for k in
                      ('REPO', 'WORKTREE_PARENT', 'STATE_DIR', 'STATE_FILE', 'LOG_FILE',
                       'LOCK_FILE', 'push_and_pr')}
        crc.REPO = self.repo
        crc.WORKTREE_PARENT = t / 'wts'
        crc.STATE_DIR = t / 'state'
        crc.STATE_FILE = crc.STATE_DIR / 'state.json'
        crc.LOG_FILE = crc.STATE_DIR / 'capture.log'
        crc.LOCK_FILE = crc.STATE_DIR / '.lock'
        self.pushed = []
        crc.push_and_pr = lambda entry: (self.pushed.append(entry), 'https://example/pr/1')[1]

    def tearDown(self):
        for k, v in self.saved.items():
            setattr(crc, k, v)
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'prune'], capture_output=True)
        self.tmp.cleanup()

    def test_capture_run(self):
        self.assertTrue(self.hooks_fire_normally, 'control: repo hooks must fire on a normal commit')
        with redirect_stdout(io.StringIO()):
            rc = crc.run(full=True, dry_run=False, cache_root=self.cache)
        self.assertEqual(rc, 0)
        self.assertEqual(len(self.pushed), 1)
        entry = self.pushed[0]
        self.assertEqual([r[0] for r in entry['rows']], ['alpha', 'beta'])
        self.assertEqual(entry['rows'][1][1], ['SKILL.md', 'references/r.md'])
        branch = entry['branch']
        self.assertTrue(branch.startswith(crc.BRANCH_PREFIX))
        self.assertIn('v2 saved from Cowork', _g(self.repo, 'show', f'{branch}:alpha/SKILL.md'))
        self.assertEqual(_g(self.repo, 'show', f'{branch}:beta/references/r.md'), 'ref\n')
        files = _g(self.repo, 'ls-tree', '-r', '--name-only', branch).split()
        self.assertNotIn('beta/.pytest_cache/README.md', files)
        self.assertEqual(_g(self.repo, 'rev-list', '--count', f'origin/main..{branch}').strip(), '2')
        msg = _g(self.repo, 'log', '-1', '--format=%B', branch)
        self.assertIn(crc.TRAILER, msg)
        self.assertFalse(self.marker.exists(), 'capture commits must run with hooks disabled')
        self.assertNotIn('_runtime-capture-', _g(self.repo, 'worktree', 'list'))
        state = crc.load_state()
        self.assertEqual(state['pending_push'], [])
        self.assertEqual(sorted(state['captured']), ['alpha', 'beta'])
        # identical second run: fingerprints unchanged, nothing new to capture
        with redirect_stdout(io.StringIO()):
            self.assertEqual(crc.run(full=False, dry_run=False, cache_root=self.cache), 0)
            self.assertEqual(crc.run(full=True, dry_run=False, cache_root=self.cache), 0)
        self.assertEqual(len(self.pushed), 1, 'already-captured content must not be re-captured')

    def test_dry_run_writes_nothing(self):
        with redirect_stdout(io.StringIO()):
            rc = crc.run(full=True, dry_run=True, cache_root=self.cache)
        self.assertEqual(rc, 0)
        self.assertEqual(self.pushed, [])
        self.assertFalse(crc.STATE_FILE.exists())
        self.assertNotIn(crc.BRANCH_PREFIX, _g(self.repo, 'branch', '--list'))


if __name__ == '__main__':
    unittest.main()
