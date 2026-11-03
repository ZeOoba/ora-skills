#!/usr/bin/env python3
"""Regression tests for repo_first_check.py — the reverse-direction (cache-ahead-of-
repo) drift detector and its STORE_AHEAD_OF_REPO ledger.

Stdlib only — run with `python tools/test_repo_first_check.py` (no pytest). Builds a
real git repo fixture (classify_skill's direction verdict needs real ancestry, the same
way pending_reimport.classify_shared_copy's own tests do) plus a synthetic AppData-
shaped cache tree; never touches the live ora-skills repo or the live runtime cache.

WHY THIS EXISTS (2026-08-04): repo_first_check.py shipped 2026-08-03 with the correct
per-file, git-ancestry-based bidirectional classifier (classify_skill(), reusing
pending_reimport.classify_shared_copy across every bundled file, not just SKILL.md) but
shipped with ZERO test coverage, and its findings were never persisted anywhere — only
printed to a pre-commit console that scrolls away, and only for skills already staged in
that commit. masterlease-jurisdiction-rebase drifted cache-ahead of the repo THREE TIMES
in one session that day, twice requiring manual diffing to even discover, because
nothing ran the (already-correct) full-sweep path automatically and nothing durable
recorded what it found. This file locks in classify_skill()'s per-file direction
behavior and covers record_ledger(), the new durable _staging/STORE_AHEAD_OF_REPO.md
companion to _staging/PENDING_REIMPORT.md (which only ever tracked the opposite
direction — repo-ahead-of-cache).
"""
import importlib
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_reimport as pr  # noqa: E402
import repo_first_check as rfc  # noqa: E402
from pending_reimport import read_entries  # noqa: E402
from unittest import mock  # noqa: E402


def _git(repo: Path, *args: str) -> None:
    subprocess.run(['git', '-C', str(repo), *args], check=True, capture_output=True)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='')


def _rmtree(path: Path) -> None:
    """git writes object files read-only; on Windows rmtree cannot unlink them and
    ignore_errors=True leaks the whole fixture silently. Clear the bit and retry;
    still best-effort, so a locked file never fails a test."""
    def _retry(func, p, _exc):
        try:
            os.chmod(p, stat.S_IWRITE)
            func(p)
        except Exception:  # onexc can also hand over os.open/os.close
            pass
    shutil.rmtree(rfc._win_long(path), onexc=_retry)


def _commit(repo: Path, rel: str, text: str, message: str) -> None:
    _write(repo / rel, text)
    _git(repo, 'add', rel)
    _git(repo, 'commit', '-m', message)


class FixtureTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='repo_first_check_test_'))
        self.repo = self.tmp / 'repo'
        self.cache = self.tmp / 'cache'
        self.repo.mkdir()
        self.cache.mkdir()
        _git(self.repo, 'init', '-q', '-b', 'main')
        _git(self.repo, 'config', 'user.email', 'test@example.com')
        _git(self.repo, 'config', 'user.name', 'Test')

    def tearDown(self):
        _rmtree(self.tmp)


class ClassifySkill(FixtureTestCase):
    """classify_skill() must see drift across EVERY bundled file (scripts/, fixtures/,
    config), not just SKILL.md — that's the gap pending_reimport.skill_drifted() and
    skill_drift_report.py both leave open (the former has no direction, the latter is
    SKILL.md-only)."""

    def test_in_sync_when_cache_matches_repo(self):
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')

        verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'IN-SYNC')
        self.assertEqual(per_file, [('SKILL.md', 'IN-SYNC')])

    def test_cache_ahead_on_a_bundled_script_never_committed(self):
        # This is the masterlease-jurisdiction-rebase shape: SKILL.md itself is fine,
        # but a scripts/ file was edited platform-side (create-skill / a direct cache
        # write) and never committed anywhere.
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _commit(self.repo, 'demo-skill/scripts/run.py', 'print("v1")\n', 'add script')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'run.py', 'print("v2 - never committed")\n')

        verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'CACHE-AHEAD')
        self.assertIn(('scripts/run.py', 'CACHE-AHEAD'), per_file)
        self.assertIn(('SKILL.md', 'IN-SYNC'), per_file)

    def test_repo_ahead_is_not_a_repo_first_violation(self):
        # Cache holds an older committed point on HEAD's own history — normal,
        # reimport-pending state, not a violation.
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\nv1\n', 'v1')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\nv1\n')
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\nv2\n', 'v2')

        verdict, _ = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'REPO-AHEAD')

    def test_divergent_worse_than_cache_ahead_in_worst_ordering(self):
        # A skill with one CACHE-AHEAD file and one DIVERGENT file must report the
        # worse of the two, never silently prefer the milder finding.
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _commit(self.repo, 'demo-skill/scripts/a.py', 'a-v1\n', 'a v1')
        _git(self.repo, 'checkout', '-q', '-b', 'other')
        _commit(self.repo, 'demo-skill/scripts/b.py', 'b-off-branch\n', 'b off-branch')
        _git(self.repo, 'checkout', '-q', 'main')
        _write(self.repo / 'demo-skill' / 'scripts' / 'b.py', 'b-main\n')
        _git(self.repo, 'add', 'demo-skill/scripts/b.py')
        _git(self.repo, 'commit', '-q', '-m', 'b on main')

        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'a.py', 'a-cache-only-never-committed\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'b.py', 'b-off-branch\n')

        verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'DIVERGENT')
        self.assertIn(('scripts/a.py', 'CACHE-AHEAD'), per_file)
        self.assertIn(('scripts/b.py', 'DIVERGENT'), per_file)

    def test_not_installed_when_no_cache_dir(self):
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')

        verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'NOT-INSTALLED')
        self.assertEqual(per_file, [])

    def test_missing_in_cache_file_is_not_a_finding_here(self):
        # A file the repo ships that the cache lacks entirely is the reimport path's
        # finding (pending_reimport/skill_drift_report), not this detector's — this
        # detector only classifies files present on BOTH sides.
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _commit(self.repo, 'demo-skill/scripts/new.py', 'new\n', 'add new script')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        # cache never got scripts/new.py

        verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'IN-SYNC')
        self.assertNotIn('scripts/new.py', [rel for rel, _ in per_file])

    def test_cache_only_file_with_no_repo_counterpart_is_a_finding(self):
        # _packaged_rel_paths() only ever walks the REPO side -- a file created
        # platform-side (create-skill / a direct cache write) that never existed in
        # the repo at all was previously invisible to classify_skill() entirely
        # (2026-08-04 review finding: this is exactly the masterlease-jurisdiction-
        # rebase v1.6 shape, a brand-new scripts/ file appearing cache-side).
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'brand_new.py', 'never in the repo\n')

        verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertIn(verdict, rfc.BAD_VERDICTS)
        self.assertIn(('scripts/brand_new.py', 'REPO-MISSING'), per_file)

    def test_shared_root_dep_in_cache_is_not_a_false_positive(self):
        # Found via live smoke test against the real repo: a SHARED_ROOT_DEPS file
        # (e.g. target-markets.json) is injected into a consuming skill's cache copy
        # from the REPO ROOT at packaging time -- it has no same-named file under
        # repo_root/<skill>/, so the cache-only scan misclassified it as
        # REPO-MISSING for all 5 real consuming skills before this exclusion was
        # added. pending_reimport.shared_dep_report() already direction-checks these
        # correctly against their true repo-root source.
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'shared.json', '{"version": 1}\n')
        # no repo_root/demo-skill/shared.json, and no repo_root/shared.json either --
        # this test only needs to prove the DECLARED name is excluded, not that the
        # shared file's own content is separately checked (that's shared_dep_report's job)

        with mock.patch.object(rfc, 'SHARED_ROOT_DEPS', {'demo-skill': ['shared.json']}):
            verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'IN-SYNC')
        self.assertNotIn('shared.json', [rel for rel, _ in per_file])

    def test_shared_root_dep_tuple_form_dest_is_not_a_false_positive(self):
        # Tuple-form SHARED_ROOT_DEPS entry (source != dest, e.g. ora_doc_qc.py landing at
        # scripts/) must exclude by DEST path, not the raw tuple -- the plain-string case
        # above puts the string itself into shared_deps and it matches rel directly, but a
        # 2-tuple put into that set unnormalized would never match a string rel and the
        # exclusion would silently stop working for every tuple-form consumer.
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'shared.py', 'x = 1\n')

        with mock.patch.object(
            rfc, 'SHARED_ROOT_DEPS', {'demo-skill': [('tools/shared.py', 'scripts/shared.py')]}
        ):
            verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'IN-SYNC')
        self.assertNotIn('scripts/shared.py', [rel for rel, _ in per_file])


class RecordLedger(FixtureTestCase):
    """The durable STORE_AHEAD_OF_REPO ledger — the reverse-direction companion to
    _staging/PENDING_REIMPORT.md that never existed before, which is why both
    2026-08-04 masterlease incidents needed a human to manually diff the two stores."""

    def setUp(self):
        super().setUp()
        self.ledger = self.tmp / 'STORE_AHEAD_OF_REPO.md'

    def test_cache_ahead_finding_is_written_to_the_ledger(self):
        findings = [('demo-skill', 'CACHE-AHEAD', [('scripts/run.py', 'CACHE-AHEAD')])]

        rfc.record_ledger(findings, ledger_path=self.ledger)

        entries = read_entries(self.ledger)
        self.assertIn('demo-skill', entries)
        self.assertIn('CACHE-AHEAD', entries['demo-skill'])
        self.assertIn('scripts/run.py', entries['demo-skill'])

    def test_no_findings_means_no_ledger_file(self):
        rfc.record_ledger([], ledger_path=self.ledger)

        self.assertFalse(self.ledger.is_file())

    def test_writes_its_own_header_not_pending_reimports(self):
        # write_entries()'s header param was newly generalized (previously hardcoded
        # to PENDING_REIMPORT.md's own text) specifically so this ledger gets ITS
        # OWN header. Reverting that generalization (or dropping the LEDGER_HEADER
        # argument at the call site) would silently write the wrong file's header
        # into this one -- confirmed by no other test, per code review.
        findings = [('demo-skill', 'CACHE-AHEAD', [('scripts/run.py', 'CACHE-AHEAD')])]

        rfc.record_ledger(findings, ledger_path=self.ledger)

        raw = self.ledger.read_text(encoding='utf-8')
        self.assertIn('STORE AHEAD OF REPO', raw)
        self.assertNotIn('PENDING REIMPORT', raw)

    def test_ledger_self_clears_once_a_skill_reconciles(self):
        findings = [('demo-skill', 'CACHE-AHEAD', [('scripts/run.py', 'CACHE-AHEAD')])]
        rfc.record_ledger(findings, ledger_path=self.ledger)
        self.assertTrue(self.ledger.is_file())

        cleared = rfc.record_ledger([], ledger_path=self.ledger)

        self.assertEqual(cleared, ['demo-skill'])
        self.assertFalse(self.ledger.is_file())

    def test_pending_since_timestamp_survives_across_runs(self):
        findings = [('demo-skill', 'CACHE-AHEAD', [('scripts/run.py', 'CACHE-AHEAD')])]
        rfc.record_ledger(findings, ledger_path=self.ledger)
        first = read_entries(self.ledger)['demo-skill']

        # Second run, same skill still drifted (e.g. it moved again in the runtime
        # cache before anyone reconciled it — the actual 2026-08-04 sequence) — the
        # ORIGINAL "pending since" must not reset to now, so staleness stays visible.
        rfc.record_ledger(findings, ledger_path=self.ledger)
        second = read_entries(self.ledger)['demo-skill']

        self.assertEqual(first, second)

    def test_two_skills_independently_tracked(self):
        findings = [
            ('skill-a', 'CACHE-AHEAD', [('scripts/a.py', 'CACHE-AHEAD')]),
            ('skill-b', 'DIVERGENT', [('scripts/b.py', 'DIVERGENT')]),
        ]

        rfc.record_ledger(findings, ledger_path=self.ledger)

        entries = read_entries(self.ledger)
        self.assertEqual(set(entries), {'skill-a', 'skill-b'})
        self.assertIn('DIVERGENT', entries['skill-b'])


_HOLDER = r"""
import sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import pending_reimport as pr
ledger, held, release = Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
with pr.ledger_lock(ledger):
    held.write_text('held')
    while not release.exists():
        time.sleep(0.005)
"""


class RecordLedgerTakesTheLedgerLock(FixtureTestCase):
    """record_ledger's read (to carry "pending since" forward) and its replace-write
    run under the same cross-process lock as pending_reimport's writers. Held past
    its bound, the lock raises instead of writing unlocked, and run() already turns
    that OSError into a warning."""

    def setUp(self):
        super().setUp()
        self.ledger = self.tmp / 'STORE_AHEAD_OF_REPO.md'
        rfc.record_ledger([('kept-skill', 'CACHE-AHEAD', [('SKILL.md', 'CACHE-AHEAD')])],
                          ledger_path=self.ledger)
        self.before = self.ledger.read_bytes()
        held, self.release = self.tmp / 'held', self.tmp / 'release'
        self.holder = subprocess.Popen(
            [sys.executable, '-c', _HOLDER, str(Path(pr.__file__).parent),
             str(self.ledger), str(held), str(self.release)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        while not held.exists():
            if self.holder.poll() is not None:
                err = self.holder.stderr.read()
                super().tearDown()       # a failing setUp skips tearDown
                self.fail(f'lock holder died: {err}')
            time.sleep(0.01)

    def tearDown(self):
        # Release before super().tearDown() removes the temp dir the release file lives in.
        self.release.write_text('release')
        self.holder.communicate()
        super().tearDown()

    def test_held_lock_raises_and_leaves_the_ledger_untouched(self):
        with mock.patch.object(pr, 'LOCK_TIMEOUT_S', 0), \
                self.assertRaises(pr.LedgerLockTimeout):
            rfc.record_ledger([], ledger_path=self.ledger)

        self.assertEqual(self.ledger.read_bytes(), self.before)


class FullSweepIntegration(FixtureTestCase):
    """End-to-end: the full-sweep path (no --check-staged) must see a skill that has
    NO staged repo change at all — the exact scenario --check-staged structurally
    cannot catch, since _staged_skills() only ever returns skills touched by the
    commit about to happen."""

    def test_full_sweep_finds_drift_with_nothing_staged(self):
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill-EDITED-IN-COWORK\n')
        # nothing staged in the repo — git status is clean

        status = subprocess.run(['git', '-C', str(self.repo), 'status', '--porcelain'],
                                 capture_output=True, text=True, check=True).stdout
        self.assertEqual(status.strip(), '')

        findings = rfc._sweep_findings(repo_root=self.repo, cache_root=self.cache)

        skills = {f[0] for f in findings}
        self.assertIn('demo-skill', skills)


class RunIntegration(FixtureTestCase):
    """End-to-end coverage of run() (main()'s thin CLI wrapper just forwards to this)
    — every store it touches is parameterized, so these exercise the WHOLE control
    flow (reachability guard, per-file remedy text, ledger write) against a
    disposable fixture tree, never the live repo/cache/ledger."""

    def setUp(self):
        super().setUp()
        self.ledger = self.tmp / 'STORE_AHEAD_OF_REPO.md'
        self.rescue_dir = self.tmp / 'rescue'

    def _run(self, check_staged=False):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            code = rfc.run(check_staged, repo_root=self.repo, cache_root=self.cache,
                            ledger_path=self.ledger, rescue_dir=self.rescue_dir)
        return code, buf.getvalue()

    def test_unreachable_cache_root_never_touches_an_existing_ledger(self):
        # The critical bug found in code review: record_ledger([]) reads an empty
        # findings list as "everything reconciled" and deletes the ledger. A full
        # sweep against an UNREACHABLE cache root (e.g. a Cowork bash sandbox, per
        # _win_long's own docstring) produces exactly that empty list for every
        # skill via classify_skill's NOT-INSTALLED short-circuit -- so without a
        # guard, losing the cache mid-run would silently erase real findings instead
        # of leaving them untouched.
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        stale_findings = [('demo-skill', 'CACHE-AHEAD', [('scripts/run.py', 'CACHE-AHEAD')])]
        rfc.record_ledger(stale_findings, ledger_path=self.ledger)
        self.assertTrue(self.ledger.is_file())
        before = self.ledger.read_text(encoding='utf-8')

        unreachable_cache = self.tmp / 'does-not-exist'
        code = rfc.run(False, repo_root=self.repo, cache_root=unreachable_cache,
                        ledger_path=self.ledger, rescue_dir=self.rescue_dir)

        self.assertEqual(code, 0)
        self.assertTrue(self.ledger.is_file())
        self.assertEqual(self.ledger.read_text(encoding='utf-8'), before)

    def test_per_file_remedy_text_matches_each_files_own_verdict(self):
        # main()'s print loop used to look up why[]/fix[] by the skill-level
        # aggregate verdict for EVERY bad file, so a DIVERGENT file was told to
        # "commit it to the repo first" (CACHE-AHEAD's remedy) whenever the same
        # skill also had a CACHE-AHEAD file. Reproduce that exact shape end-to-end.
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _commit(self.repo, 'demo-skill/scripts/a.py', 'a-v1\n', 'a v1')
        _git(self.repo, 'checkout', '-q', '-b', 'other')
        _commit(self.repo, 'demo-skill/scripts/b.py', 'b-off-branch\n', 'b off-branch')
        _git(self.repo, 'checkout', '-q', 'main')
        _write(self.repo / 'demo-skill' / 'scripts' / 'b.py', 'b-main\n')
        _git(self.repo, 'add', 'demo-skill/scripts/b.py')
        _git(self.repo, 'commit', '-q', '-m', 'b on main')

        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'a.py', 'a-cache-only-never-committed\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'b.py', 'b-off-branch\n')

        code, stderr = self._run(check_staged=False)

        self.assertEqual(code, 0)
        a_line = next(ln for ln in stderr.splitlines() if 'scripts/a.py' in ln)
        b_line = next(ln for ln in stderr.splitlines() if 'scripts/b.py' in ln)
        self.assertIn('never committed on ANY branch', a_line)
        self.assertIn("matches a commit OFF this branch's ancestry", b_line)
        self.assertIn('commit it to the repo first', stderr)
        self.assertIn('reconcile the branches, do not auto-reimport', stderr)

    def test_findings_are_ledgered_and_rescued(self):
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _commit(self.repo, 'demo-skill/scripts/run.py', 'v1\n', 'add script')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'run.py', 'v2-never-committed\n')

        code, stderr = self._run(check_staged=False)

        self.assertEqual(code, 0)
        entries = read_entries(self.ledger)
        self.assertIn('demo-skill', entries)
        run_dir = rfc._newest_rescue(self.rescue_dir / 'demo-skill')
        self.assertTrue(run_dir.name.endswith('-' + self.repo.resolve().name))
        rescued = run_dir / 'scripts' / 'run.py'
        self.assertTrue(rescued.is_file())
        self.assertEqual(rescued.read_text(encoding='utf-8'), 'v2-never-committed\n')
        self.assertIn('Rescued the cache copy', stderr)

    def test_ledger_write_failure_is_reported_and_still_exits_0(self):
        # The tool never blocks (module docstring; the doctrine guard relies on exit 0).
        # write_entries can now raise PermissionError after its bounded retry when a
        # reader holds the ledger, so run() must degrade that to a warning.
        _commit(self.repo, 'demo-skill/SKILL.md', 'name: demo-skill\n', 'init')
        _commit(self.repo, 'demo-skill/scripts/run.py', 'v1\n', 'add script')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'run.py', 'v2-never-committed\n')

        with mock.patch.object(rfc, 'record_ledger', side_effect=PermissionError(13, 'locked')):
            code, stderr = self._run(check_staged=False)

        self.assertEqual(code, 0)
        self.assertIn('ledger write failed', stderr)
        self.assertFalse(self.ledger.exists())


class RescueNeverOverwrites(FixtureTestCase):
    """Every checkout's pre-commit and sweep now share ONE rescue dir (the primary's),
    and a rescue is the only surviving copy of clobbered cache content. A later rescue
    of different content must never overwrite an earlier one, nor leave a half-copied
    mix of two builds (merge-gate race finding F2)."""

    def setUp(self):
        super().setUp()
        self.rescue_dir = self.tmp / 'rescue'

    def _rescue(self, rels):
        import contextlib
        import io
        with contextlib.redirect_stderr(io.StringIO()):
            return rfc.rescue('demo-skill', rels, cache_root=self.cache,
                              rescue_dir=self.rescue_dir)

    def test_a_later_different_rescue_keeps_the_earlier_one(self):
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'X: platform edit\n')
        _write(self.cache / 'demo-skill' / 'references' / 'notes.md', 'X-notes\n')
        first = self._rescue(['SKILL.md', 'references/notes.md'])
        (self.cache / 'demo-skill' / 'references' / 'notes.md').unlink()
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'Z: another build\n')

        second = self._rescue(['SKILL.md'])

        self.assertNotEqual(first, second)
        self.assertEqual((first / 'SKILL.md').read_text(encoding='utf-8'), 'X: platform edit\n')
        self.assertEqual((second / 'SKILL.md').read_text(encoding='utf-8'), 'Z: another build\n')
        self.assertFalse((second / 'references' / 'notes.md').exists())

    def test_a_rescue_that_fails_mid_copy_is_never_visible(self):
        # A missing source fails before any dir exists; this fails AFTER the first file
        # is written, so only the temp-dir-then-rename step keeps the half-copy out of
        # sight (merge-gate round 2, test-validity F1).
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'X\n')
        _write(self.cache / 'demo-skill' / 'references' / 'notes.md', 'X-notes\n')
        real_write = Path.write_bytes
        writes = []

        def disk_full_on_second(path, data):
            writes.append(path)
            if len(writes) == 2:
                raise OSError(28, 'No space left on device')
            return real_write(path, data)

        with mock.patch.object(Path, 'write_bytes', disk_full_on_second):
            self.assertIsNone(self._rescue(['SKILL.md', 'references/notes.md']))

        self.assertEqual([p.name for p in (self.rescue_dir / 'demo-skill').iterdir()
                          if not p.name.startswith('.')], [])
        self.assertIsNone(rfc._newest_rescue(self.rescue_dir / 'demo-skill'))

    def test_a_cache_replaced_after_the_read_still_rescues_everything_read(self):
        # Round 3 MEDIUM: copystat re-stat'ed the cache after the bytes were read; a
        # concurrent Save-skill reimport replacing the dir in that window aborted the
        # rescue and lost bytes that were the only copy.
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'X: platform edit\n')
        _write(self.cache / 'demo-skill' / 'references' / 'notes.md', 'X-notes\n')
        real_mkdtemp = rfc.tempfile.mkdtemp

        def reimport_lands_first(*a, **kw):
            _rmtree(self.cache / 'demo-skill')
            return real_mkdtemp(*a, **kw)

        with mock.patch.object(rfc.tempfile, 'mkdtemp', reimport_lands_first):
            dest = self._rescue(['SKILL.md', 'references/notes.md'])

        self.assertIsNotNone(dest)
        self.assertEqual((dest / 'SKILL.md').read_text(encoding='utf-8'), 'X: platform edit\n')
        self.assertEqual((dest / 'references' / 'notes.md').read_text(encoding='utf-8'),
                         'X-notes\n')

    def test_a_cache_replaced_mid_read_still_rescues_the_files_already_read(self):
        # Round 4 MEDIUM (race): reading every file before writing any meant one file
        # vanishing mid-read threw away the bytes already read -- a regression on the
        # base's file-by-file copy, which kept what it had copied.
        import contextlib
        import io
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'X: platform edit\n')
        _write(self.cache / 'demo-skill' / 'references' / 'notes.md', 'X-notes\n')
        real_read = rfc._read_with_stat
        reads = []

        def reimport_lands_mid_read(path):
            reads.append(path)
            if len(reads) == 2:
                _rmtree(self.cache / 'demo-skill')
            return real_read(path)

        err = io.StringIO()
        with mock.patch.object(rfc, '_read_with_stat', reimport_lands_mid_read), \
                contextlib.redirect_stderr(err):
            dest = rfc.rescue('demo-skill', ['SKILL.md', 'references/notes.md'],
                              cache_root=self.cache, rescue_dir=self.rescue_dir)

        self.assertIsNotNone(dest, err.getvalue())
        self.assertEqual((dest / 'SKILL.md').read_text(encoding='utf-8'), 'X: platform edit\n')
        self.assertIn('references/notes.md', err.getvalue())

    def test_a_failed_mtime_copy_never_costs_the_bytes(self):
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'X: platform edit\n')

        with mock.patch.object(rfc.os, 'utime', side_effect=PermissionError(13, 'denied')):
            dest = self._rescue(['SKILL.md'])

        self.assertIsNotNone(dest)
        self.assertEqual((dest / 'SKILL.md').read_text(encoding='utf-8'), 'X: platform edit\n')

    def test_a_rescue_keeps_the_cache_files_mtime(self):
        # The rescue is the only surviving copy, and its mtime records when the
        # platform-side edit happened (merge-gate round 2, scope auditor F-1).
        src = self.cache / 'demo-skill' / 'SKILL.md'
        _write(src, 'X: platform edit\n')
        os.utime(src, (1577836800, 1577836800))

        dest = self._rescue(['SKILL.md'])

        self.assertEqual(int((dest / 'SKILL.md').stat().st_mtime), 1577836800)

    def test_an_identical_rescue_is_not_duplicated(self):
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'X: platform edit\n')

        first = self._rescue(['SKILL.md'])
        second = self._rescue(['SKILL.md'])

        self.assertEqual(first, second)
        self.assertEqual(len([p for p in (self.rescue_dir / 'demo-skill').iterdir()
                              if p.is_dir()]), 1)

    def test_a_missing_file_keeps_the_rest_and_never_touches_an_earlier_rescue(self):
        # Round 4 changed the contract: a file gone from the cache no longer costs the
        # files that could be read (the rescue is their only copy); it is reported.
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'X: platform edit\n')
        first = self._rescue(['SKILL.md'])
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'Z: another build\n')

        second = self._rescue(['SKILL.md', 'missing.md'])

        self.assertEqual((first / 'SKILL.md').read_text(encoding='utf-8'), 'X: platform edit\n')
        self.assertEqual((second / 'SKILL.md').read_text(encoding='utf-8'), 'Z: another build\n')
        self.assertFalse((second / 'missing.md').exists())

    def test_a_rescue_with_nothing_readable_makes_no_dir(self):
        self.assertIsNone(self._rescue(['missing.md']))
        self.assertIsNone(rfc._newest_rescue(self.rescue_dir / 'demo-skill'))


class MainBehindOrigin(unittest.TestCase):
    """A skill installed from a PR that already merged to origin/main, while the
    long-lived local main has not caught up yet, is routine -- not DIVERGENT.

    WHY (2026-09-17): #55/#56, #57 and #58/#59 each produced `!! REPO-FIRST DIVERGENT`
    alarms that were nothing but local main lagging origin/main; tools/catch_up_main.py
    is the fix, and this verdict keeps the daily sweep from alarming in the meantime.
    A cache copy from a branch that is NOT on origin/main must stay DIVERGENT."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix='repo_first_check_origin_'))
        self.cache = self.tmp / 'cache'
        self.cache.mkdir()
        origin = self.tmp / 'origin.git'
        subprocess.run(['git', 'init', '-q', '--bare', '-b', 'main', str(origin)],
                       check=True, capture_output=True)
        self.seed, self.repo = self.tmp / 'seed', self.tmp / 'repo'
        for path in (self.seed, self.repo):
            if path == self.repo:
                _git(self.seed, 'push', '-q', 'origin', 'main')
            subprocess.run(['git', 'clone', '-q', str(origin), str(path)],
                           check=True, capture_output=True)
            _git(path, 'config', 'user.email', 'test@example.com')
            _git(path, 'config', 'user.name', 'Test')
            if path == self.seed:
                _commit(path, 'demo-skill/SKILL.md', 'name: demo-skill\nv1\n', 'init')
        _commit(self.repo, 'local-only.md', 'unpushed\n', 'unpushed local commit')

    def tearDown(self):
        _rmtree(self.tmp)

    def _merge_pr_on_origin(self, rel, text):
        _commit(self.seed, rel, text, 'merged PR (#99)')
        _git(self.seed, 'push', '-q', 'origin', 'main')
        _git(self.repo, 'fetch', '-q', 'origin')

    def test_cache_from_merged_pr_is_main_behind_origin(self):
        self._merge_pr_on_origin('demo-skill/SKILL.md', 'name: demo-skill\nv2\n')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\nv2\n')

        verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'MAIN-BEHIND-ORIGIN')
        self.assertEqual(per_file, [('SKILL.md', 'MAIN-BEHIND-ORIGIN')])
        self.assertNotIn('MAIN-BEHIND-ORIGIN', rfc.BAD_VERDICTS)

    def test_new_file_from_merged_pr_is_main_behind_origin_not_repo_missing(self):
        self._merge_pr_on_origin('demo-skill/scripts/new.py', 'print(1)\n')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\nv1\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'new.py', 'print(1)\n')

        verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'MAIN-BEHIND-ORIGIN')
        self.assertIn(('scripts/new.py', 'MAIN-BEHIND-ORIGIN'), per_file)

    def test_unmerged_feature_branch_stays_divergent(self):
        _git(self.seed, 'checkout', '-q', '-b', 'feat/x')
        _commit(self.seed, 'demo-skill/SKILL.md', 'name: demo-skill\nfeature\n', 'feature')
        _git(self.seed, 'push', '-q', 'origin', 'feat/x')
        _git(self.repo, 'fetch', '-q', 'origin')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\nfeature\n')

        verdict, _ = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'DIVERGENT')

    def test_divergent_provenance_names_the_introducing_commit_and_branch(self):
        """2026-11-03: the rescue dir's `-pr167` suffix (the sweeping checkout) was read
        as the installing branch. The finding now names the commit the cache matches."""
        _git(self.seed, 'checkout', '-q', '-b', 'capture/x')
        _commit(self.seed, 'demo-skill/SKILL.md', 'name: demo-skill\ncaptured\n', 'capture: verbatim')
        _commit(self.seed, 'demo-skill/SKILL.md', 'name: demo-skill\nlater\n', 'later edit')
        _git(self.seed, 'push', '-q', 'origin', 'capture/x')
        _git(self.repo, 'fetch', '-q', 'origin')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\ncaptured\n')

        where = rfc._divergent_provenance(self.repo, self.cache / 'demo-skill' / 'SKILL.md')

        self.assertIn('"capture: verbatim"', where)     # introducer, not the later replacer
        self.assertIn('origin/capture/x', where)

    def test_divergent_provenance_finds_a_blob_born_in_a_merge(self):
        """Refute C3a: a blob first created by a conflict resolution is invisible to
        `log --find-object` without -m, so the later replacer looked earliest."""
        _git(self.seed, 'checkout', '-q', '-b', 'side')
        _commit(self.seed, 'demo-skill/SKILL.md', 'name: demo-skill\nside\n', 'side')
        _git(self.seed, 'checkout', '-q', '-b', 'capture', 'main')
        _commit(self.seed, 'demo-skill/SKILL.md', 'name: demo-skill\nmain-side\n', 'capture base')
        subprocess.run(['git', '-C', str(self.seed), 'merge', '-q', 'side'], capture_output=True)
        _write(self.seed / 'demo-skill' / 'SKILL.md', 'name: demo-skill\nresolved\n')
        _git(self.seed, 'add', 'demo-skill/SKILL.md')
        _git(self.seed, 'commit', '-q', '-m', 'merge side (resolved)')
        _commit(self.seed, 'demo-skill/SKILL.md', 'name: demo-skill\nreplaced\n', 'later replacer')
        _git(self.seed, 'push', '-q', 'origin', 'capture')
        _git(self.repo, 'fetch', '-q', 'origin')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\nresolved\n')

        where = rfc._divergent_provenance(self.repo, self.cache / 'demo-skill' / 'SKILL.md')

        self.assertIn('"merge side (resolved)"', where)

    def test_divergent_provenance_is_none_for_unknown_content(self):
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'never committed\n')
        self.assertIsNone(rfc._divergent_provenance(self.repo, self.cache / 'demo-skill' / 'SKILL.md'))

    def test_divergent_provenance_never_raises_outside_a_repo(self):
        _write(self.tmp / 'loose.md', 'x\n')
        self.assertIsNone(rfc._divergent_provenance(self.tmp / 'nope', self.tmp / 'loose.md'))

    def test_file_deleted_by_already_merged_pr_stays_repo_missing(self):
        # Review finding 2026-09-17: matching ALL of origin/main's history relabeled a
        # stale cache-only file as MAIN-BEHIND-ORIGIN even with local main fully caught
        # up -- masking a real REPO-MISSING forever (catch_up_main.py would be a NOOP).
        _commit(self.seed, 'demo-skill/scripts/old.py', 'old\n', 'add old.py (#98)')
        _git(self.seed, 'rm', '-q', 'demo-skill/scripts/old.py')
        _git(self.seed, 'commit', '-q', '-m', 'remove old.py (#99)')
        _git(self.seed, 'push', '-q', 'origin', 'main')
        _git(self.repo, 'fetch', '-q', 'origin')
        _git(self.repo, 'merge', '-q', '--no-edit', 'origin/main')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\nv1\n')
        _write(self.cache / 'demo-skill' / 'scripts' / 'old.py', 'old\n')

        verdict, per_file = rfc.classify_skill('demo-skill', self.repo, self.cache)

        self.assertEqual(verdict, 'REPO-MISSING')
        self.assertIn(('scripts/old.py', 'REPO-MISSING'), per_file)

    def test_sweep_fetch_never_prompts_for_credentials(self):
        with mock.patch.object(rfc.subprocess, 'run') as run:
            rfc._fetch_origin_main(self.repo)
        env = run.call_args.kwargs['env']
        self.assertEqual(env['GIT_TERMINAL_PROMPT'], '0')
        self.assertEqual(env['GCM_INTERACTIVE'], 'never')

    def test_full_sweep_fetches_first_and_does_not_alarm(self):
        # Merged on GitHub, never fetched locally -- the daily sweep's real situation.
        _commit(self.seed, 'demo-skill/SKILL.md', 'name: demo-skill\nv2\n', 'merged PR (#99)')
        _git(self.seed, 'push', '-q', 'origin', 'main')
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'name: demo-skill\nv2\n')
        ledger, rescue_dir = self.tmp / 'ledger.md', self.tmp / 'rescue'
        import contextlib
        import io
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = rfc.run(False, repo_root=self.repo, cache_root=self.cache,
                           ledger_path=ledger, rescue_dir=rescue_dir)

        self.assertEqual(code, 0)
        self.assertNotIn('!! REPO-FIRST', err.getvalue())
        self.assertIn('MAIN-BEHIND-ORIGIN', out.getvalue())
        self.assertIn('catch_up_main.py', out.getvalue())
        self.assertFalse(ledger.is_file())
        self.assertFalse(rescue_dir.exists())



class StagingResolvesToPrimaryCheckout(FixtureTestCase):
    """RESCUE_DIR and LEDGER are untracked durable state, and the rescue copy is the
    ONLY surviving copy of clobbered cache content. Resolved against a git worktree
    they land in that worktree's _staging/ and die with `git worktree remove` -- and
    the pre-commit hook runs --check-staged (so rescue()) inside whichever worktree is
    committing. The module is reloaded with REPO pointed at a real fixture worktree,
    so a revert to REPO-relative paths fails whether the suite itself runs from a
    worktree or from the primary checkout."""

    def setUp(self):
        super().setUp()
        _git(self.repo, 'commit', '-q', '--allow-empty', '-m', 'init')
        self.wt = self.tmp / 'wt'
        _git(self.repo, 'worktree', 'add', '-q', str(self.wt))
        self.addCleanup(importlib.reload, rfc)
        with mock.patch.object(pr, 'REPO', self.wt):
            importlib.reload(rfc)

    def test_rescued_copy_survives_worktree_remove(self):
        _write(self.cache / 'demo-skill' / 'SKILL.md', 'cache-only content\n')

        dest = rfc.rescue('demo-skill', ['SKILL.md'], cache_root=self.cache)
        self.assertIsNotNone(dest)
        _git(self.repo, 'worktree', 'remove', '--force', str(self.wt))

        rescued = self.repo / '_staging' / 'repo-first-rescue' / 'demo-skill' / dest.name / 'SKILL.md'
        self.assertEqual(rescued.read_text(encoding='utf-8'), 'cache-only content\n')

    def test_ledger_survives_worktree_remove(self):
        rfc.record_ledger([('demo-skill', 'CACHE-AHEAD', [('SKILL.md', 'CACHE-AHEAD')])])
        _git(self.repo, 'worktree', 'remove', '--force', str(self.wt))

        self.assertIn('demo-skill',
                      read_entries(self.repo / '_staging' / 'STORE_AHEAD_OF_REPO.md'))

    def test_repo_stays_the_checkouts_own_root(self):
        # The sweep reads the checkout's OWN content; only the untracked state moves.
        self.assertEqual(rfc.REPO, self.wt)

    def test_worktree_sweep_leaves_the_primary_ledger_untouched(self):
        # The ledger is DERIVED -- each full sweep replaces it -- and verdicts are
        # branch-relative. A clean sweep from a feature worktree must not read as
        # "resolved" and wipe what the primary's sweep recorded (nor reset its
        # carried-forward "pending since").
        rfc.record_ledger([('demo-skill', 'DIVERGENT', [('SKILL.md', 'DIVERGENT')])])
        before = rfc.LEDGER.read_bytes()
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as out, \
                contextlib.redirect_stderr(io.StringIO()):
            rfc.run(False, repo_root=self.wt, cache_root=self.cache)

        self.assertEqual(rfc.LEDGER.read_bytes(), before)
        self.assertIn('not the primary checkout', out.getvalue())


class CodeOnlySkills(FixtureTestCase):
    """Code-surface-only skills (git/gh/worktree work, local ~/.claude) are installed under
    ~/.claude/skills and are never meant for the Cowork runtime cache. With no cache dir they
    must read CODE-ONLY (expected), not NOT-INSTALLED (looks like a gap) -- but ONLY while
    there is no cache dir: once a copy IS in the cache its drift is real and must show."""

    def setUp(self):
        super().setUp()
        _commit(self.repo, 'codey/SKILL.md', 'name: codey\n', 'init codey')
        _commit(self.repo, 'plain/SKILL.md', 'name: plain\n', 'init plain')
        p = mock.patch.object(rfc, 'CODE_ONLY_SKILLS', frozenset({'codey'}))
        p.start()
        self.addCleanup(p.stop)

    def test_listed_skill_without_a_cache_dir_is_code_only(self):
        verdict, per_file = rfc.classify_skill('codey', self.repo, self.cache)
        self.assertEqual(verdict, 'CODE-ONLY')
        self.assertEqual(per_file, [])

    def test_unlisted_skill_without_a_cache_dir_is_still_not_installed(self):
        verdict, _ = rfc.classify_skill('plain', self.repo, self.cache)
        self.assertEqual(verdict, 'NOT-INSTALLED')

    def test_code_only_skill_that_IS_cached_is_classified_normally_in_sync(self):
        _write(self.cache / 'codey' / 'SKILL.md', 'name: codey\n')
        verdict, _ = rfc.classify_skill('codey', self.repo, self.cache)
        self.assertEqual(verdict, 'IN-SYNC')

    def test_code_only_skill_that_IS_cached_still_reports_real_drift(self):
        _write(self.cache / 'codey' / 'SKILL.md', 'name: codey-EDITED-IN-COWORK\n')
        verdict, _ = rfc.classify_skill('codey', self.repo, self.cache)
        self.assertEqual(verdict, 'CACHE-AHEAD')

    def test_code_only_is_not_a_bad_verdict(self):
        self.assertNotIn('CODE-ONLY', rfc.BAD_VERDICTS)

    def test_full_sweep_prints_code_only_and_never_ledgers_it(self):
        import contextlib
        import io
        ledger = self.tmp / 'STORE_AHEAD_OF_REPO.md'
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = rfc.run(False, repo_root=self.repo, cache_root=self.cache,
                           ledger_path=ledger, rescue_dir=self.tmp / 'rescue')
        text = out.getvalue()
        self.assertEqual(code, 0)
        self.assertRegex(text, r'codey\s+CODE-ONLY')
        self.assertRegex(text, r'plain\s+NOT-INSTALLED')
        # REFUTE round 1 (low): the old ledger-text assertion could not fail, because
        # NOT-INSTALLED was never ledgered either. Bind it to the real mechanism instead:
        # CODE-ONLY must never be a finding (those are what get ledgered and rescued).
        findings = rfc._sweep_findings(repo_root=self.repo, cache_root=self.cache)
        self.assertNotIn('codey', {f[0] for f in findings})
        # ...and that same sweep DOES find a listed skill once its cached copy has drifted.
        _write(self.cache / 'codey' / 'SKILL.md', 'name: codey-EDITED-IN-COWORK\n')
        findings = rfc._sweep_findings(repo_root=self.repo, cache_root=self.cache)
        self.assertIn('codey', {f[0] for f in findings})


if __name__ == '__main__':
    unittest.main()
