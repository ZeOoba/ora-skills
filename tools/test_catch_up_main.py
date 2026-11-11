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


class SquashRealign(Fixture):
    """Seen live 2026-11-10 on #236: the PR was squash-merged to keep its commits out
    of public main, but those same commits sat on the shared checkout's local main.
    The forward-merge then wrote a merge commit, leaving local main ahead with the
    pre-squash commits still reachable -- a later push of main would publish them.
    When local main's tree already equals origin/main's, catch_up must move main to
    origin/main by ref (old tip kept on a backup ref), never merge."""

    def _squash_scenario(self):
        """Local main carries two unpushed commits; origin lands their squash."""
        _commit(self.local, 'notes/entry.md', 'draft\n', 'wip entry')
        _commit(self.local, 'notes/entry.md', 'final\n', 'finish entry')
        _commit(self.seed, 'notes/entry.md', 'final\n', 'land entry (#236)')
        _git(self.seed, 'push', '-q', 'origin', 'main')
        return _git(self.local, 'rev-parse', 'HEAD')

    def _backup_refs(self):
        out = _git(self.local, 'for-each-ref', '--format=%(refname) %(objectname)',
                   'refs/backup/catch-up/')
        return [ln.split() for ln in out.splitlines() if ln]

    def test_squash_with_identical_tree_realigns_by_ref(self):
        old_tip = self._squash_scenario()

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'REALIGNED', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'),
                         _git(self.local, 'rev-parse', 'origin/main'))
        self.assertEqual(_git(self.local, 'symbolic-ref', '--short', 'HEAD'), 'main')
        # the pre-squash commits are no longer reachable from main...
        r = subprocess.run(['git', '-C', str(self.local), 'merge-base', '--is-ancestor',
                            old_tip, 'main'], capture_output=True)
        self.assertNotEqual(r.returncode, 0)
        # ...but are kept on exactly one named backup ref
        backups = self._backup_refs()
        self.assertEqual(len(backups), 1, backups)
        self.assertEqual(backups[0][1], old_tip)
        self.assertIn(backups[0][0], detail)
        self.assertEqual(_git(self.local, 'status', '--porcelain'), '')
        self.assertEqual((self.local / 'notes' / 'entry.md').read_text(), 'final\n')
        self.assertFalse(_git(self.local, 'log', '-1', '--format=%s').startswith('merge '))

    def test_hook_reports_realigned_in_additional_context(self):
        import io
        import json
        from unittest import mock
        self._squash_scenario()
        real = cum.catch_up
        payload = json.dumps({'tool_name': 'Bash', 'tool_input': {
            'command': 'gh pr merge 236 --squash -R ZeOoba/ora-skills'}}).encode()
        out = io.StringIO()
        with mock.patch.object(cum, 'catch_up',
                               lambda repo: real(repo, preflight=_clear)), \
                mock.patch.object(cum.sys, 'stdin', mock.Mock(buffer=io.BytesIO(payload))), \
                mock.patch.object(cum.sys, 'stdout', out):
            self.assertEqual(cum._hook(self.local), 0)
        ctx = json.loads(out.getvalue())['hookSpecificOutput']['additionalContext']
        self.assertTrue(ctx.startswith('ora-skills local main catch-up: REALIGNED -- '), ctx)

    def test_cli_exit_code_for_realigned_is_success(self):
        from unittest import mock
        import io
        with mock.patch.object(cum, 'catch_up', lambda repo: ('REALIGNED', 'x')),                 mock.patch.object(cum.sys, 'stdout', io.StringIO()):
            self.assertEqual(cum.main(['--repo', str(self.local)]), 0)

    def test_extra_unrelated_local_commit_merges_as_today(self):
        self._squash_scenario()
        _commit(self.local, 'local-only.md', 'mine\n', 'unrelated unpushed commit')
        old_tip = _git(self.local, 'rev-parse', 'HEAD')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'MERGED', detail)
        _git(self.local, 'merge-base', '--is-ancestor', old_tip, 'HEAD')
        self.assertEqual(_git(self.local, 'rev-list', '--count', 'HEAD..origin/main'), '0')
        self.assertEqual(_git(self.local, 'log', '-1', '--format=%s'),
                         'merge origin/main into local main (forward-merge #236)')
        self.assertEqual(self._backup_refs(), [])

    def test_dirty_tree_never_moves_main(self):
        for label, dirty in (
                ('untracked file', lambda: (self.local / 'scratch.txt').write_text('x\n')),
                ('modified file', lambda: (self.local / 'demo-skill' / 'SKILL.md')
                 .write_text('wip\n')),
                ('staged-only change', lambda: (
                    (self.local / 'demo-skill' / 'SKILL.md').write_text('staged\n'),
                    _git(self.local, 'add', 'demo-skill/SKILL.md'),
                    (self.local / 'demo-skill' / 'SKILL.md').write_text('v1\n')))):
            with self.subTest(dirty=label):
                self.tearDown()
                self.setUp()
                old_tip = self._squash_scenario()
                dirty()

                status, detail = cum.catch_up(self.local, preflight=_clear)

                self.assertEqual(status, 'SKIPPED', detail)
                self.assertIn('squash', detail)
                self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), old_tip)
                self.assertEqual(self._backup_refs(), [])
                self.assertFalse((self.local / '.git' / 'MERGE_HEAD').exists())

    def _spy(self, before=None, after=None):
        """Patch cum._git; before(args)/after(args, result) run around each real call."""
        from unittest import mock
        real = cum._git

        def spy(repo, *args, timeout=60, **kw):
            if before:
                before(args)
            result = real(repo, *args, timeout=timeout, **kw)
            if after:
                after(args, result)
            return result
        return mock.patch.object(cum, '_git', spy)

    @staticmethod
    def _is_transaction(args):
        return args[0] == 'update-ref' and '--stdin' in args

    def _refs_at(self, sha):
        out = _git(self.local, 'for-each-ref', '--points-at', sha, '--format=%(refname)')
        return [ln for ln in out.splitlines() if ln]

    def test_main_moved_by_another_writer_is_not_clobbered(self):
        # The transaction's old-value guard must refuse when main no longer holds the
        # tip that was checked -- and, being atomic, must write no backup ref either.
        old_tip = self._squash_scenario()
        racer = {}

        def before(args):
            if self._is_transaction(args) and not racer:
                _commit(self.local, 'race.md', 'r\n', 'concurrent commit')
                racer['tip'] = _git(self.local, 'rev-parse', 'HEAD')

        with self._spy(before=before):
            status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'SKIPPED', detail)
        self.assertIn('could not move main', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), racer['tip'])
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD^'), old_tip)
        self.assertEqual(self._backup_refs(), [])        # all-or-nothing

    # --- gate rounds 1-2 (2026-11-10) --------------------------------------------
    def test_unwritable_backup_ref_moves_nothing(self):
        # `refs/backup/catch-up` as a REF blocks every ref beneath it (D/F conflict),
        # so the backup cannot be created -- main must not move without its backup.
        old_tip = self._squash_scenario()
        _git(self.local, 'update-ref', 'refs/backup/catch-up', old_tip)

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'SKIPPED', detail)
        self.assertIn('nothing moved', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), old_tip)
        self.assertEqual(_git(self.local, 'rev-parse', 'refs/backup/catch-up'), old_tip)

    def test_operation_in_progress_never_moves_main(self):
        git_dir = lambda: self.local / '.git'                      # noqa: E731

        def cherry_pick_now_empty():
            # picking origin/main's squash onto a main that already has its content
            # stops "now empty" with CHERRY_PICK_HEAD set and a perfectly clean tree
            subprocess.run(['git', '-C', str(self.local), 'cherry-pick', 'origin/main'],
                           capture_output=True)
            self.assertTrue((git_dir() / 'CHERRY_PICK_HEAD').exists())

        def marker_file(name):
            return lambda: (git_dir() / name).write_text(
                _git(self.local, 'rev-parse', 'HEAD') + '\n')

        def marker_dir(name):
            return lambda: (git_dir() / name).mkdir()

        cases = [('cherry-pick', cherry_pick_now_empty, 'CHERRY_PICK_HEAD')]
        cases += [(name, marker_file(name), name)
                  for name in ('MERGE_HEAD', 'REVERT_HEAD', 'REBASE_HEAD')]
        cases += [(name, marker_dir(name), name)
                  for name in ('rebase-apply', 'rebase-merge', 'sequencer')]
        self.assertEqual({c[2] for c in cases}, set(cum._IN_PROGRESS))  # every marker
        for label, start, marker in cases:
            with self.subTest(op=label):
                self.tearDown()
                self.setUp()
                old_tip = self._squash_scenario()
                _git(self.local, 'fetch', '-q', 'origin')
                start()

                status, detail = cum.catch_up(self.local, preflight=_clear)

                self.assertEqual(status, 'SKIPPED', detail)
                self.assertIn(marker, detail)
                self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), old_tip)
                self.assertEqual(self._backup_refs(), [])

    def test_operation_started_after_the_checks_still_stops_the_move(self):
        from unittest import mock
        old_tip = self._squash_scenario()
        real = cum._in_progress
        calls = []

        def in_progress(git_dir):
            calls.append(1)
            if len(calls) == 2:                  # the act-time re-check
                (self.local / '.git' / 'MERGE_HEAD').write_text(old_tip + '\n')
            return real(git_dir)

        with mock.patch.object(cum, '_in_progress', in_progress):
            status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(len(calls), 2)
        self.assertEqual(status, 'SKIPPED', detail)
        self.assertIn('MERGE_HEAD', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), old_tip)
        self.assertEqual(self._backup_refs(), [])

    def test_stale_main_lock_writes_nothing_and_retries_succeed(self):
        old_tip = self._squash_scenario()
        lock = self.local / '.git' / 'refs' / 'heads' / 'main.lock'
        lock.write_text('')
        for _ in range(2):
            status, detail = cum.catch_up(self.local, preflight=_clear)
            self.assertEqual(status, 'SKIPPED', detail)
            self.assertIn('could not move main', detail)
            self.assertIn('no backup ref written', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), old_tip)
        self.assertEqual(self._backup_refs(), [])       # no orphans pile up
        lock.unlink()
        status, detail = cum.catch_up(self.local, preflight=_clear)
        self.assertEqual(status, 'REALIGNED', detail)
        self.assertEqual(len(self._backup_refs()), 1)

    def test_each_realign_keeps_its_own_old_tip_on_a_backup_ref(self):
        # Two squash cycles: each old tip must stay on a ref of its own -- an existing
        # backup at another commit must never stand in for this one.
        tips = [self._squash_scenario()]
        status, detail = cum.catch_up(self.local, preflight=_clear)
        self.assertEqual(status, 'REALIGNED', detail)
        _commit(self.local, 'notes/two.md', 'a\n', 'wip two')
        _commit(self.local, 'notes/two.md', 'b\n', 'finish two')
        tips.append(_git(self.local, 'rev-parse', 'HEAD'))
        _git(self.seed, 'pull', '-q', 'origin', 'main')
        _commit(self.seed, 'notes/two.md', 'b\n', 'land two (#237)')
        _git(self.seed, 'push', '-q', 'origin', 'main')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'REALIGNED', detail)
        for tip in tips:
            refs = [r for r in self._refs_at(tip) if r.startswith('refs/backup/catch-up/')]
            self.assertEqual(len(refs), 1, (tip, refs))
        self.assertIn(tips[1][:12], detail)
        self.assertEqual(len(self._backup_refs()), 2)

    def test_symbolic_ref_in_the_backup_namespace_is_never_the_backup(self):
        old_tip = self._squash_scenario()
        _git(self.local, 'symbolic-ref', 'refs/backup/catch-up/keep', 'refs/heads/main')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'REALIGNED', detail)
        holders = [r for r in self._refs_at(old_tip) if r != 'refs/backup/catch-up/keep']
        self.assertEqual(len(holders), 1, holders)
        self.assertIn(holders[0], detail)

    def test_concurrent_second_run_changes_nothing(self):
        # Both hooks fire: run B lands entirely inside run A, just before A's write.
        old_tip = self._squash_scenario()
        inner = {}

        def before(args):
            if self._is_transaction(args) and not inner:
                inner['result'] = 'running'
                inner['result'] = cum.catch_up(self.local, preflight=_clear)

        with self._spy(before=before):
            status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(inner['result'][0], 'REALIGNED', inner['result'])
        self.assertEqual(status, 'SKIPPED', detail)
        self.assertIn('nothing moved', detail)
        backups = self._backup_refs()
        self.assertEqual(len(backups), 1, backups)       # B's only, A wrote none
        self.assertEqual(backups[0][1], old_tip)

    def test_main_lands_on_the_pinned_sha_even_if_origin_moves(self):
        self._squash_scenario()
        pinned = {}

        def before(args):
            if self._is_transaction(args) and not pinned:
                pinned['sha'] = _git(self.local, 'rev-parse', 'origin/main')
                self._land_pr('later.md', 'x\n', 'later PR (#238)')
                _git(self.local, 'fetch', '-q', 'origin')

        with self._spy(before=before):
            status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'REALIGNED', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'main'), pinned['sha'])
        self.assertNotEqual(_git(self.local, 'rev-parse', 'origin/main'), pinned['sha'])
        self.assertEqual(_git(self.local, 'status', '--porcelain'), '')

    def test_commit_on_top_of_the_realigned_main_is_still_success(self):
        self._squash_scenario()
        moved = []

        def after(args, result):
            if self._is_transaction(args) and not moved:
                moved.append(1)
                _commit(self.local, 'after.md', 'a\n', 'commit on realigned main')

        with self._spy(after=after):
            status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'REALIGNED', detail)
        _git(self.local, 'merge-base', '--is-ancestor', 'origin/main', 'main')

    def test_main_rewound_below_origin_after_the_move_is_an_error(self):
        self._squash_scenario()
        done = []

        def after(args, result):
            if self._is_transaction(args) and not done:
                done.append(1)
                _git(self.local, 'update-ref', 'refs/heads/main', 'origin/main^')

        with self._spy(after=after):
            status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'ERROR', detail)
        self.assertIn('does not contain origin/main', detail)

    def test_unreadable_containment_check_still_reports_the_landed_realign(self):
        from unittest import mock
        self._squash_scenario()
        real = cum._git

        def spy(repo, *args, timeout=60, **kw):
            if args[0] == 'merge-base':
                return 128, '', 'timed out'
            return real(repo, *args, timeout=timeout, **kw)

        with mock.patch.object(cum, '_git', spy):
            status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'REALIGNED', detail)
        self.assertIn('verify', detail)
        self.assertEqual(_git(self.local, 'rev-parse', 'main'),
                         _git(self.local, 'rev-parse', 'origin/main'))

    def test_clean_check_takes_no_optional_index_lock(self):
        self._squash_scenario()
        calls = []
        with self._spy(before=calls.append):
            cum.catch_up(self.local, preflight=_clear)
        status_calls = [a for a in calls if 'status' in a]
        self.assertTrue(status_calls)
        self.assertTrue(all(a[0] == '--no-optional-locks' for a in status_calls), status_calls)

    def _budget_run(self, left_after_preflight, cost=1.0):
        """catch_up with a fake clock: every git READ after the preflight costs `cost`
        seconds; writes (merge, update-ref) are free and record the time left when
        they START. -> (status, detail, [seconds left at each write])"""
        from unittest import mock
        now = [0.0]
        started = []
        writes = []
        real = cum._git

        def spy(repo, *args, timeout=60, **kw):
            if args[0] in ('merge', 'update-ref'):
                writes.append(cum.TOTAL_BUDGET_S - now[0])
            result = real(repo, *args, timeout=timeout, **kw)
            if started and args[0] not in ('merge', 'update-ref'):
                now[0] += cost
            return result

        def preflight(repo, paths, since):
            started.append(1)
            now[0] = cum.TOTAL_BUDGET_S - left_after_preflight
            return True, 'CLEAR'

        with mock.patch.object(cum, '_git', spy):
            status, detail = cum.catch_up(self.local, preflight=preflight,
                                          clock=lambda: now[0])
        return status, detail, writes

    def test_no_clamped_read_runs_between_the_reservation_and_a_write(self):
        # 1s per read. With MERGE_TIMEOUT_S + 3 left after the preflight, the two reads
        # that precede the reservation in every version (HEAD re-read, log) leave
        # MERGE_TIMEOUT_S + 1 -- enough to pass a reservation placed there -- and the
        # squash reads that follow would then start the write below MERGE_TIMEOUT_S.
        # Correct order: those reads come first, so the reservation itself refuses.
        for shape in ('squash', 'diverged'):
            with self.subTest(shape=shape, case='tight'):
                self.tearDown()
                self.setUp()
                old_tip = self._squash_scenario()
                if shape == 'diverged':
                    _commit(self.local, 'local-only.md', 'mine\n', 'unrelated')
                    old_tip = _git(self.local, 'rev-parse', 'HEAD')

                status, detail, writes = self._budget_run(cum.MERGE_TIMEOUT_S + 3)

                self.assertEqual(writes, [], (shape, writes, detail))
                self.assertEqual(status, 'SKIPPED', detail)
                self.assertIn('start the merge', detail)
                self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), old_tip)
                self.assertEqual(self._backup_refs(), [])
            with self.subTest(shape=shape, case='roomy'):
                self.tearDown()
                self.setUp()
                self._squash_scenario()
                if shape == 'diverged':
                    _commit(self.local, 'local-only.md', 'mine\n', 'unrelated')

                status, detail, writes = self._budget_run(cum.MERGE_TIMEOUT_S + 20)

                self.assertEqual(status, 'REALIGNED' if shape == 'squash' else 'MERGED',
                                 detail)
                self.assertTrue(writes)
                self.assertTrue(all(left >= cum.MERGE_TIMEOUT_S for left in writes),
                                (shape, writes))


class OvertakenSquash(Fixture):
    """The squash of local main's unpushed commits landed, then another PR landed on
    top before the hook ran, so the trees differ and the realign does not apply. A
    forward-merge would put the pre-squash commits back into history: catch_up must
    move nothing and say so."""

    def _overtaken(self):
        _commit(self.local, 'notes/entry.md', 'draft\n', 'wip entry')
        _commit(self.local, 'notes/entry.md', 'final\n', 'finish entry')
        _commit(self.seed, 'notes/entry.md', 'final\n', 'land entry (#236)')
        _commit(self.seed, 'other/SKILL.md', 'x\n', 'other skill (#237)')
        _git(self.seed, 'push', '-q', 'origin', 'main')
        return _git(self.local, 'rev-parse', 'HEAD')

    def _assert_untouched(self, head):
        self.assertEqual(_git(self.local, 'rev-parse', 'HEAD'), head)
        self.assertEqual(_git(self.local, 'for-each-ref', 'refs/backup/'), '')
        self.assertEqual(_git(self.local, 'status', '--porcelain'), '')
        self.assertFalse((self.local / '.git' / 'MERGE_HEAD').exists())

    def test_overtaken_squash_moves_nothing(self):
        head = self._overtaken()

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'SKIPPED', detail)
        self.assertIn('squashed upstream as', detail)
        self.assertIn('git reset --keep origin/main', detail)
        self._assert_untouched(head)

    def test_overtaken_rebase_merge_moves_nothing(self):
        _commit(self.local, 'notes/a.md', 'a\n', 'local a')
        _commit(self.local, 'notes/b.md', 'b\n', 'local b')
        head = _git(self.local, 'rev-parse', 'HEAD')
        _commit(self.seed, 'notes/a.md', 'a\n', 'local a (#236)')
        _commit(self.seed, 'notes/b.md', 'b\n', 'local b (#236)')
        _commit(self.seed, 'other/SKILL.md', 'x\n', 'other skill (#237)')
        _git(self.seed, 'push', '-q', 'origin', 'main')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'SKIPPED', detail)
        self.assertIn('each already upstream', detail)
        self._assert_untouched(head)

    def test_extra_unrelated_local_commit_still_merges(self):
        self._overtaken()
        _commit(self.local, 'local-only.md', 'mine\n', 'unrelated unpushed commit')
        old_tip = _git(self.local, 'rev-parse', 'HEAD')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'MERGED', detail)
        _git(self.local, 'merge-base', '--is-ancestor', old_tip, 'HEAD')

    def test_partially_squashed_local_work_still_merges(self):
        _commit(self.local, 'notes/entry.md', 'final\n', 'entry')
        _commit(self.local, 'notes/second.md', 'two\n', 'second, never pushed')
        _commit(self.seed, 'notes/entry.md', 'final\n', 'land entry (#236)')
        _commit(self.seed, 'other/SKILL.md', 'x\n', 'other skill (#237)')
        _git(self.seed, 'push', '-q', 'origin', 'main')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'MERGED', detail)

    def test_unrelated_upstream_with_no_local_commits_fast_forwards(self):
        self._land_pr('other/SKILL.md', 'x\n', 'other skill (#237)')

        status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'MERGED', detail)

    def test_unreadable_detection_falls_back_to_the_merge(self):
        from unittest import mock
        self._overtaken()
        real = cum._git

        def broken(repo, *args, **kw):
            if args and args[0] in ('patch-id', 'cherry'):
                return 1, '', 'boom'
            return real(repo, *args, **kw)

        with mock.patch.object(cum, '_git', broken):
            status, detail = cum.catch_up(self.local, preflight=_clear)

        self.assertEqual(status, 'MERGED', detail)

    def test_overtaken_squash_cli_exit_code_is_skipped(self):
        import io
        from unittest import mock
        self._overtaken()
        out = io.StringIO()
        real = cum.catch_up
        with mock.patch.object(cum, 'catch_up', lambda repo: real(repo, preflight=_clear)), \
                mock.patch.object(cum.sys, 'stdout', out):
            self.assertEqual(cum.main(['--repo', str(self.local)]), 3)
        self.assertIn('SKIPPED', out.getvalue())


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
