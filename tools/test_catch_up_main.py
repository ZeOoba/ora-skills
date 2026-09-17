#!/usr/bin/env python3
"""Regression tests for catch_up_main.py -- the safe automatic forward-merge of
origin/main into the long-lived local main checkout.

Stdlib only -- run with `python tools/test_catch_up_main.py`. Builds a real bare
origin + two clones (a "seed" that lands merged PRs, and the "local" long-lived
checkout that carries unpushed commits); never touches the live ora-skills repo.
The shared-checkout preflight is injected, so no test depends on ~/.claude.

WHY THIS EXISTS (2026-09-17): local main fell behind origin/main four times in four
days (#55/#56, #57, #58/#59). Each time repo_first_check.py --all flagged skills
installed from those merged PRs as DIVERGENT, and each catch-up was a hand-run
`git merge origin/main`. These tests pin the one property that matters for an
unattended writer into a shared single-writer checkout: it merges ONLY when every
safety condition holds, and otherwise leaves HEAD exactly where it was.
"""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catch_up_main as cum  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(['git', '-C', str(repo), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, rel: str, text: str, message: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding='utf-8', newline='')
    _git(repo, 'add', rel)
    _git(repo, 'commit', '-q', '-m', message)


def _clear(repo, paths, since):
    return True, 'CLEAR'


class Fixture(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='catch_up_main_test_'))
        self.origin = self.tmp / 'origin.git'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(self.origin)],
                       check=True, capture_output=True)
        self.seed = self._clone('seed')
        _commit(self.seed, 'demo-skill/SKILL.md', 'v1\n', 'init')
        _git(self.seed, 'push', '-q', 'origin', 'main')
        self.local = self._clone('local')

    def _clone(self, name):
        path = self.tmp / name
        subprocess.run(['git', 'clone', '-q', str(self.origin), str(path)],
                       check=True, capture_output=True)
        _git(path, 'config', 'user.email', 'test@example.com')
        _git(path, 'config', 'user.name', 'Test')
        return path

    def _land_pr(self, rel, text, subject):
        _commit(self.seed, rel, text, subject)
        _git(self.seed, 'push', '-q', 'origin', 'main')

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class CatchUp(Fixture):
    def test_noop_when_already_caught_up(self):
        status, _ = cum.catch_up(self.local, preflight=_clear)
        self.assertEqual(status, 'NOOP')

    def test_merges_merged_prs_and_keeps_unpushed_local_commits(self):
        _commit(self.local, 'local-only.md', 'mine\n', 'unpushed local commit')
        local_tip = _git(self.local, 'rev-parse', 'HEAD')
        self._land_pr('demo-skill/SKILL.md', 'v2\n', 'demo-skill v2 (#58)')
        self._land_pr('other/SKILL.md', 'x\n', 'other skill (#59)')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'MERGED', detail)
        self.assertEqual(_git(self.local, 'rev-list', '--count', 'main..origin/main'), '0')
        _git(self.local, 'merge-base', '--is-ancestor', local_tip, 'HEAD')
        self.assertEqual((self.local / 'demo-skill' / 'SKILL.md').read_text(), 'v2\n')
        subject = _git(self.local, 'log', '-1', '--format=%s')
        self.assertEqual(subject, 'merge origin/main into local main (forward-merge #58, #59)')

    def test_skips_when_not_on_main(self):
        self._land_pr('demo-skill/SKILL.md', 'v2\n', 'v2 (#58)')
        _git(self.local, 'checkout', '-q', '-b', 'feature')
        head = _git(self.local, 'rev-parse', 'HEAD')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'SKIPPED')
        self.assertIn('not on main', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), head)

    def test_skips_on_conflict_without_starting_a_merge(self):
        _commit(self.local, 'demo-skill/SKILL.md', 'local edit\n', 'local conflicting edit')
        head = _git(self.local, 'rev-parse', 'HEAD')
        self._land_pr('demo-skill/SKILL.md', 'v2\n', 'v2 (#58)')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'SKIPPED')
        self.assertIn('conflict', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), head)
        self.assertFalse((self.local / '.git' / 'MERGE_HEAD').exists())

    def test_skips_when_uncommitted_edit_overlaps_incoming_file(self):
        self._land_pr('demo-skill/SKILL.md', 'v2\n', 'v2 (#58)')
        (self.local / 'demo-skill' / 'SKILL.md').write_text('wip\n', encoding='utf-8')
        head = _git(self.local, 'rev-parse', 'HEAD')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'SKIPPED')
        self.assertIn('uncommitted', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), head)
        self.assertEqual((self.local / 'demo-skill' / 'SKILL.md').read_text(), 'wip\n')

    def test_skips_when_preflight_not_clear_and_passes_incoming_paths(self):
        self._land_pr('demo-skill/SKILL.md', 'v2\n', 'v2 (#58)')
        head = _git(self.local, 'rev-parse', 'HEAD')
        seen = {}

        def blocked(repo, paths, since):
            seen['paths'], seen['since'] = paths, since
            return False, 'STOP competing claim'

        status, detail = cum.catch_up(self.local, preflight=blocked)

        self.assertEqual(status, 'SKIPPED')
        self.assertIn('STOP competing claim', detail)
        self.assertEqual(seen['paths'], ['demo-skill/SKILL.md'])
        self.assertEqual(seen['since'], head)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), head)

    def test_skips_when_fetch_fails(self):
        _git(self.local, 'remote', 'set-url', 'origin', str(self.tmp / 'missing.git'))

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'SKIPPED')
        self.assertIn('fetch', detail)

    def test_fast_forwards_when_local_has_no_unpushed_commits(self):
        self._land_pr('demo-skill/SKILL.md', 'v2\n', 'v2 (#58)')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'MERGED', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'),
                         _git(self.local, 'rev-parse', 'origin/main'))

    def test_message_without_pr_numbers(self):
        _commit(self.local, 'local-only.md', 'mine\n', 'unpushed local commit')
        self._land_pr('demo-skill/SKILL.md', 'v2\n', 'direct push, no PR')

        status, _ = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'MERGED')
        self.assertEqual(_git(self.local, 'log', '-1', '--format=%s'),
                         'merge origin/main into local main (forward-merge)')


class NonInteractiveGit(unittest.TestCase):
    def test_git_never_prompts_for_credentials(self):
        # Review finding 2026-09-17: an unattended fetch (hook / daily sweep) must fail
        # fast on expired credentials, not stall on a Git Credential Manager prompt.
        from unittest import mock
        with mock.patch.object(cum.subprocess, 'run') as run:
            run.return_value = mock.Mock(returncode=0, stdout='', stderr='')
            cum._git(Path('.'), 'fetch', 'origin', 'main')
        env = run.call_args.kwargs['env']
        self.assertEqual(env['GIT_TERMINAL_PROMPT'], '0')
        self.assertEqual(env['GCM_INTERACTIVE'], 'never')


class HookDetection(Fixture):
    def _payload(self, command, cwd=None, tool='Bash'):
        return {'tool_name': tool, 'tool_input': {'command': command},
                'cwd': str(cwd or self.tmp)}

    def test_repo_flag_names_ora_skills(self):
        self.assertTrue(cum.is_ora_skills_merge(
            self._payload('gh pr merge 57 --squash -R ZeOoba/ora-skills')))
        self.assertTrue(cum.is_ora_skills_merge(
            self._payload('gh pr merge 57 --repo=ZeOoba/ora-skills --merge')))

    def test_cwd_remote_is_ora_skills(self):
        _git(self.local, 'remote', 'set-url', 'origin', 'https://github.com/ZeOoba/ora-skills.git')
        self.assertTrue(cum.is_ora_skills_merge(
            self._payload('cd somewhere && gh pr merge 57 --squash', cwd=self.local)))

    def test_other_repo_is_ignored(self):
        _git(self.local, 'remote', 'set-url', 'origin', 'https://github.com/ZeOoba/Website.git')
        self.assertFalse(cum.is_ora_skills_merge(self._payload('gh pr merge 3', cwd=self.local)))
        self.assertFalse(cum.is_ora_skills_merge(
            self._payload('gh pr merge 3 -R ZeOoba/ora-pm', cwd=self.local)))

    def test_repo_flag_wins_over_cwd(self):
        _git(self.local, 'remote', 'set-url', 'origin', 'https://github.com/ZeOoba/ora-skills.git')
        self.assertFalse(cum.is_ora_skills_merge(
            self._payload('gh pr merge 3 -R ZeOoba/Website', cwd=self.local)))

    def test_non_merge_commands_and_tools_are_ignored(self):
        self.assertFalse(cum.is_ora_skills_merge(
            self._payload('gh pr view 57 -R ZeOoba/ora-skills')))
        self.assertFalse(cum.is_ora_skills_merge(
            self._payload('gh pr merge 57 -R ZeOoba/ora-skills', tool='Edit')))
        self.assertFalse(cum.is_ora_skills_merge({}))


if __name__ == '__main__':
    unittest.main()
