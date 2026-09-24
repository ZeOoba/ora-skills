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
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import catch_up_main as cum  # noqa: E402


def _rmtree(path) -> None:
    """git writes object files read-only, which rmtree cannot unlink on Windows --
    with ignore_errors=True every git-backed fixture here leaked silently into %TEMP%.
    Clear the bit and retry; still best-effort, so a locked file never fails a test.
    (Same helper as PR #79 adds to tools/test_pending_reimport.py.)"""
    def _retry(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:  # onexc can also hand over os.open/os.close
            pass
    shutil.rmtree(path, onexc=_retry)


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
        _rmtree(self.tmp)


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

    # --- command-position anchoring (review 2026-09-19) -------------------------
    # Every negative below runs with a cwd whose origin IS ora-skills, so the only
    # thing standing between it and a real fetch+merge is the matcher itself.
    def _in_ora_skills(self):
        _git(self.local, 'remote', 'set-url', 'origin', 'https://github.com/ZeOoba/ora-skills.git')
        return self.local

    def test_text_that_merely_mentions_the_command_is_ignored(self):
        cwd = self._in_ora_skills()
        for command in (
            'echo "remember to gh pr merge 99 later"',
            'echo gh pr merge 99 -R ZeOoba/ora-skills',        # unquoted: anchoring alone
            'CMD=(gh pr merge 5 -R ZeOoba/ora-skills)',        # array assignment, not a call
            'CMD=( gh pr merge 5 -R ZeOoba/ora-skills )',
            'A=(\ngh pr merge 5 -R ZeOoba/ora-skills\n)',
            'A=("x y" $(echo z)) B=( gh pr merge 5 -R ZeOoba/ora-skills )',
            'gh pr merge 5 -R ZeOoba/ora-skills)',             # stray `)`: no `depth` to close
            'echo done (gh pr merge 5 -R ZeOoba/ora-skills)',  # syntax error in bash
            "echo 'gh pr merge 99'",
            'git commit -m "prep for gh pr merge"',
            '# gh pr merge 123',
            'ls # gh pr merge 123 -R ZeOoba/ora-skills',
            'echo a; echo "x && gh pr merge 5"',
            'git commit -F - <<EOF\nprep\ngh pr merge 5 -R ZeOoba/ora-skills\nEOF',
        ):
            with self.subTest(command=command):
                self.assertFalse(cum.is_ora_skills_merge(self._payload(command, cwd=cwd)))

    def test_help_and_dry_run_are_not_merges(self):
        cwd = self._in_ora_skills()
        for command in ('gh pr merge --help', 'gh pr merge -h',
                        'gh pr merge 5 --dry-run -R ZeOoba/ora-skills'):
            with self.subTest(command=command):
                self.assertFalse(cum.is_ora_skills_merge(self._payload(command, cwd=cwd)))

    def test_repo_must_be_exactly_ora_skills_on_github(self):
        cwd = self._in_ora_skills()
        for spec in ('https://evil.example.com/zeooba/ora-skills',
                     'evil.example.com/ZeOoba/ora-skills',
                     'ZeOoba/ora-skills-evil', 'notzeooba/ora-skills', 'ora-skills'):
            with self.subTest(spec=spec):
                self.assertFalse(cum.is_ora_skills_merge(
                    self._payload(f'gh pr merge 123 -R {spec}', cwd=cwd)))
        # a PR URL names its repo too, and beats the cwd
        self.assertFalse(cum.is_ora_skills_merge(self._payload(
            'gh pr merge https://github.com/ZeOoba/Website/pull/3', cwd=cwd)))
        # every named repo must match, not just one of them
        self.assertFalse(cum.is_ora_skills_merge(self._payload(
            'gh pr merge -R ZeOoba/Website https://github.com/ZeOoba/ora-skills/pull/3',
            cwd=cwd)))

    def test_real_merges_still_match(self):
        self.assertTrue(cum.is_ora_skills_merge(
            self._payload('gh pr merge 63 --repo ZeOoba/ora-skills --squash')))
        for command in (
            'gh pr merge 63 -R https://github.com/ZeOoba/ora-skills.git',
            'gh pr merge 63 -RZeOoba/ora-skills',
            'gh pr merge https://github.com/ZeOoba/ora-skills/pull/63',
            'git status && gh pr merge 63 -R ZeOoba/ora-skills',
            'git status; gh pr merge 63 -R ZeOoba/ora-skills',
            'false || gh pr merge 63 -R ZeOoba/ora-skills',
            '(gh pr merge 63 -R ZeOoba/ora-skills)',
            '( cd x && gh pr merge 63 -R ZeOoba/ora-skills )',
            'out=$(gh pr merge 63 -R ZeOoba/ora-skills)',
            'git status | cat\ngh pr merge 63 -R ZeOoba/ora-skills',
            'GH_PROMPT_DISABLED=1 gh pr merge 63 -R ZeOoba/ora-skills',
            'X=(a b) gh pr merge 63 -R ZeOoba/ora-skills',     # bash runs it with the array set
            'gh pr merge 63 -R=ZeOoba/ora-skills',             # pflag accepts -R=SLUG
            'cat <<EOF\ngh pr merge 5 -R ZeOoba/other\nEOF\ngh pr merge 63 -R ZeOoba/ora-skills',
        ):
            with self.subTest(command=command):
                self.assertTrue(cum.is_ora_skills_merge(self._payload(command)))

    def test_array_literal_is_skipped_whole_but_the_next_command_still_matches(self):
        self.assertTrue(cum.is_ora_skills_merge(self._payload(
            'A=("x y" "$(echo z)"); gh pr merge 5 -R ZeOoba/ora-skills')))
        self.assertTrue(cum.is_ora_skills_merge(self._payload(
            'A+=(x)\ngh pr merge 5 -R ZeOoba/ora-skills')))

    def test_documented_misses_stay_on_the_safe_side(self):
        cwd = self._in_ora_skills()
        for command in (
            'case $x in\n  a) gh pr merge 63 -R ZeOoba/ora-skills ;;\nesac',
            'cat <(gh pr merge 63 -R ZeOoba/ora-skills)',
            'exec gh pr merge 63 -R ZeOoba/ora-skills',
            '! gh pr merge 63 -R ZeOoba/ora-skills',
            'bash -c "gh pr merge 63 -R ZeOoba/ora-skills"',
        ):
            with self.subTest(command=command):
                self.assertFalse(cum.is_ora_skills_merge(self._payload(command, cwd=cwd)))

    def test_malformed_heredoc_voids_the_whole_command(self):
        # bash rejects a `<<` with no delimiter and runs nothing -- same line or next.
        cwd = self._in_ora_skills()
        for command in ('cat <<-; gh pr merge 63 -R ZeOoba/ora-skills',
                        'cat <<\ngh pr merge 63 -R ZeOoba/ora-skills'):
            with self.subTest(command=command):
                self.assertFalse(cum.is_ora_skills_merge(self._payload(command, cwd=cwd)))

    def test_heredoc_ends_only_on_the_exact_delimiter_line(self):
        # An indented / trailing-space `EOF` does NOT end a plain heredoc in bash, so
        # the `gh pr merge` after it is still body text and never runs.
        cwd = self._in_ora_skills()
        for command in (
            'git commit -F - <<EOF\nnotes\n   EOF\ngh pr merge 5 -R ZeOoba/ora-skills\nEOF',
            'git commit -F - <<EOF\nnotes\nEOF \ngh pr merge 5 -R ZeOoba/ora-skills\nEOF',
            'git commit -F - <<-EOF\nnotes\n  EOF\ngh pr merge 5 -R ZeOoba/ora-skills\nEOF',
        ):
            with self.subTest(command=command):
                self.assertFalse(cum.is_ora_skills_merge(self._payload(command, cwd=cwd)))
        # ...and the exact terminator (tab-indented for <<-, CRLF tolerated) does end it
        for command in ('cat <<EOF\nx\nEOF\ngh pr merge 5 -R ZeOoba/ora-skills',
                        'cat <<-EOF\nx\n\tEOF\ngh pr merge 5 -R ZeOoba/ora-skills',
                        'cat <<EOF\r\nx\r\nEOF\r\ngh pr merge 5 -R ZeOoba/ora-skills'):
            with self.subTest(command=command):
                self.assertTrue(cum.is_ora_skills_merge(self._payload(command, cwd=cwd)))

    def test_cwd_origin_path_survives_a_cd_prefix(self):
        cwd = self._in_ora_skills()
        self.assertTrue(cum.is_ora_skills_merge(self._payload('cd x && gh pr merge 5', cwd=cwd)))


class TimeBudget(Fixture):
    """The hook is killed at HOOK_TIMEOUT_S (360s in settings.json); catch_up must
    finish or refuse inside its own budget, must never START a merge it could not
    finish, and must not mistake a spent budget for a git fact. The clock is injected
    so no test patches stdlib time."""

    def _behind(self):
        self._land_pr('demo-skill/SKILL.md', 'v2\n', 'change (#70)')
        return _git(self.local, 'rev-parse', 'HEAD')

    def _run(self, on_git=None, budget_s=cum.TOTAL_BUDGET_S, preflight=_clear):
        """catch_up under a fake clock; on_git(verb, now) may advance it after each git
        call. -> (status, detail, [(verb, timeout), ...])"""
        from unittest import mock
        now = [0.0]
        seen = []
        real = cum._git

        def spy(repo, *args, timeout=60):
            seen.append((args[0], timeout))
            result = real(repo, *args, timeout=timeout)
            if on_git:
                on_git(args[0], now)
            return result

        with mock.patch.object(cum, '_git', spy):
            status, detail = cum.catch_up(self.local, preflight=preflight,
                                          budget_s=budget_s, clock=lambda: now[0])
        return status, detail, seen

    def test_budget_fits_under_the_hook_timeout(self):
        # The merge starts with >= MERGE_TIMEOUT_S left, runs for at most that long, so
        # it ends inside TOTAL_BUDGET_S; only the post-merge read runs past the budget.
        worst_case = cum.TOTAL_BUDGET_S + cum.POST_MERGE_READ_TIMEOUT_S
        self.assertLess(worst_case + cum.HOOK_OVERHEAD_S, cum.HOOK_TIMEOUT_S)
        self.assertGreaterEqual(cum.TOTAL_BUDGET_S,
                                cum.PREFLIGHT_TIMEOUT_S + cum.MERGE_TIMEOUT_S)

    def test_too_little_budget_skips_before_preflight(self):
        head = self._behind()
        called = []
        status, detail, _ = self._run(
            budget_s=cum.PREFLIGHT_TIMEOUT_S - 1,
            preflight=lambda *a: called.append(a) or (True, 'CLEAR'))
        self.assertEqual(status, 'SKIPPED')
        self.assertIn('budget', detail)
        self.assertEqual(called, [])
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), head)

    def test_slow_preflight_leaves_no_room_to_merge(self):
        head = self._behind()
        clock = {}

        def slow_preflight(repo, paths, since):
            clock['now'][0] += cum.TOTAL_BUDGET_S - cum.MERGE_TIMEOUT_S + 1   # < 120 left
            return True, 'CLEAR'

        def grab(verb, now):
            clock['now'] = now

        status, detail, _ = self._run(on_git=grab, preflight=slow_preflight)
        self.assertEqual(status, 'SKIPPED')
        self.assertIn('start the merge', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), head)
        self.assertEqual(_git(self.local, 'status', '--short'), '')      # no half-merge

    def test_reads_are_clamped_to_the_time_left(self):
        self._behind()

        def burn(verb, now):
            if verb == 'fetch':
                now[0] += cum.TOTAL_BUDGET_S - 30       # 30s left for everything else

        _, _, seen = self._run(on_git=burn)
        after_fetch = dict(seen[seen.index(('fetch', cum.FETCH_TIMEOUT_S)) + 1:])
        self.assertEqual(after_fetch['rev-list'], 30)   # nominal 60, clamped to what is left

    def test_spent_budget_is_reported_as_such_not_as_a_git_fact(self):
        head = self._behind()
        for verb in ('fetch', 'rev-list', 'diff'):      # next read is rev-list/diff/merge-tree
            def burn(v, now, verb=verb, fired=[]):
                if v == verb and not fired:
                    fired.append(1)
                    now[0] += cum.TOTAL_BUDGET_S + 1
            with self.subTest(dies_after=verb):
                status, detail, _ = self._run(on_git=burn)
                self.assertEqual(status, 'SKIPPED')
                self.assertIn('budget exhausted', detail)
                self.assertNotIn('conflict', detail)
                self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), head)

    def test_spent_budget_after_a_landed_merge_still_reports_merged(self):
        # The merge and its verification bypass the clamped closure on purpose: a
        # budget that dies while the merge runs must not be reported as "nothing changed".
        self._behind()

        def burn(verb, now):
            if verb == 'merge':
                now[0] += cum.TOTAL_BUDGET_S + 1

        status, detail, _ = self._run(on_git=burn)
        self.assertEqual(status, 'MERGED', detail)
        self.assertEqual(_git(self.local, 'rev-list', '--count', 'HEAD..origin/main'), '0')

    def test_unreadable_head_skips_at_either_read(self):
        from unittest import mock
        head = self._behind()
        real = cum._git
        for nth, message in ((1, 'could not read HEAD'), (2, 're-read HEAD')):
            calls = []

            def spy(repo, *args, timeout=60, nth=nth, calls=calls):
                if args[0] == 'rev-parse':
                    calls.append(1)
                    if len(calls) == nth:
                        return 1, '', 'timed out'
                return real(repo, *args, timeout=timeout)

            with self.subTest(failing_read=nth), mock.patch.object(cum, '_git', spy):
                status, detail = cum.catch_up(self.local, preflight=_clear)
                self.assertEqual(status, 'SKIPPED')
                self.assertIn(message, detail)
                self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), head)

    def test_unreadable_uncommitted_state_skips_instead_of_assuming_clean(self):
        from unittest import mock
        head = self._behind()
        real = cum._git

        def spy(repo, *args, timeout=60):
            if args[0] == 'ls-files':
                return 1, '', 'timed out'
            return real(repo, *args, timeout=timeout)

        with mock.patch.object(cum, '_git', spy):
            status, detail = cum.catch_up(self.local, preflight=_clear)
        self.assertEqual(status, 'SKIPPED')
        self.assertIn('uncommitted', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), head)

    def test_failed_post_merge_read_does_not_undo_a_landed_merge(self):
        from unittest import mock
        self._behind()
        real = cum._git
        merged = []

        def spy(repo, *args, timeout=60):
            if args[0] == 'rev-list' and merged:
                return 1, '', 'timed out'
            result = real(repo, *args, timeout=timeout)
            if args[0] == 'merge':
                merged.append(1)
            return result

        with mock.patch.object(cum, '_git', spy):
            status, detail = cum.catch_up(self.local, preflight=_clear)
        self.assertEqual(status, 'MERGED')
        self.assertIn('verify', detail)
        self.assertEqual(_git(self.local, 'rev-list', '--count', 'HEAD..origin/main'), '0')


class FixtureTeardownRemovesGitRepos(unittest.TestCase):
    """git writes object files read-only; rmtree(ignore_errors=True) skipped them on
    Windows and every git-backed fixture in this file leaked into %TEMP%."""

    def test_teardown_removes_the_bare_origin_and_both_clones(self):
        fx = CatchUp('test_noop_when_already_caught_up')
        fx.setUp()
        fx.tearDown()

        self.assertFalse(fx.tmp.exists())


if __name__ == '__main__':
    unittest.main()
