"""Tests for leased_push.py (stdlib unittest; gated by tools/run_skill_suites.sh).

The rewrite under test is a real `git filter-repo` run on a mirror clone of the backup,
exactly as SKILL.md Step 3 makes it (copy made with `leased_push.py prepare`), so ref-map and
purge-backup-refs.txt are the real files.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "leased_push.py")
ENV = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_AUTHOR_NAME="t",
           GIT_AUTHOR_EMAIL="t@example.com", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")


def git(repo, *args):
    return subprocess.run(["git", "-C", repo] + list(args), capture_output=True, text=True, check=True,
                          env=ENV).stdout.strip()


def write(path, text):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


class Base(unittest.TestCase):
    CLEAN_ROOT = False      # True: the first commit holds nothing private, so the purge keeps its SHA
    BRANCH = "main"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.remote = os.path.join(t, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "-b", self.BRANCH, self.remote], check=True, env=ENV)
        src = self.src = os.path.join(t, "src")
        subprocess.run(["git", "init", "-q", "-b", self.BRANCH, src], check=True, env=ENV)
        if self.CLEAN_ROOT:
            write(os.path.join(src, "README.md"), "readme\n")
            git(src, "add", "README.md")
            git(src, "commit", "-q", "-m", "init")
        for i in range(5):
            write(os.path.join(src, "f.txt"), "secret v%d\n" % i)
            git(src, "add", "f.txt")
            git(src, "commit", "-q", "-m", "c%d" % i)
            git(src, "branch", "b%d" % i)
        git(src, "tag", "-a", "v1", "-m", "release")
        git(src, "push", "-q", self.remote, "refs/heads/*:refs/heads/*", "refs/tags/*:refs/tags/*")
        self.mirror = os.path.join(t, "mirror.git")
        subprocess.run(["git", "clone", "-q", "--mirror", self.remote, self.mirror], check=True, env=ENV)
        self.rules = os.path.join(t, "rules.txt")
        write(self.rules, "secret==>[private]\n")
        self.work = os.path.join(t, "work.git")
        self.rewrite()
        self.before = git(self.remote, "for-each-ref")

    def rewrite(self, extra=(), backup=None):
        """Step 3: fresh copy of the backup made with `prepare`, ONE filter-repo run."""
        if os.path.isdir(self.work):
            shutil.move(self.work, self.work + "-old%d" % len(os.listdir(self.tmp.name)))
        subprocess.run([sys.executable, "-I", SCRIPT, "prepare", backup or self.mirror, self.work],
                       check=True, env=ENV, capture_output=True)
        git(self.work, "filter-repo", "--force", "--replace-text", self.rules, "--replace-message", self.rules,
            *extra)

    def new_backup(self, name="mirror2.git"):
        """Step 1 again after a leaked push: a NEW backup directory; the old one is never fetched into."""
        path = os.path.join(self.tmp.name, name)
        subprocess.run(["git", "clone", "-q", "--mirror", self.remote, path], check=True, env=ENV)
        return path

    def tearDown(self):
        self.tmp.cleanup()

    def run_push(self, *extra, env=None, mirror=None, work=None, url=None):
        e = dict(ENV, **(env or {}))
        return subprocess.run([sys.executable, "-I", SCRIPT, mirror or self.mirror, work or self.work,
                               url or self.remote] + list(extra), capture_output=True, text=True, env=e)

    def late_push(self, branch="b1"):
        other = os.path.join(self.tmp.name, "other-" + branch)
        if not os.path.isdir(other):
            subprocess.run(["git", "clone", "-q", self.remote, other], check=True, env=ENV)
        git(other, "checkout", "-q", branch)
        git(other, "pull", "-q", "origin", branch)
        write(os.path.join(other, "late.txt"), "late %s\n" % len(os.listdir(other)))
        git(other, "add", "late.txt")
        git(other, "commit", "-q", "-m", "late push")
        git(other, "push", "-q", "origin", branch)
        return git(other, "rev-parse", "HEAD")

    def hook_cmd(self, code):
        path = os.path.join(self.tmp.name, "hook.py")
        write(path, code)
        return path

    def reject_on_remote(self, ref):
        mark = os.path.join(self.tmp.name, "reject")
        write(mark, "x")
        hook = os.path.join(self.remote, "hooks", "update")
        write(hook, '#!/bin/sh\nif [ "$1" = %s ] && [ -f "%s" ]; then echo no >&2; exit 1; fi\n'
              % (ref, mark.replace("\\", "/")))
        os.chmod(hook, 0o755)
        return mark

    def assert_remote_matches_work(self):
        for ref in git(self.work, "for-each-ref", "--format=%(refname)").split():
            self.assertEqual(git(self.work, "rev-parse", ref), git(self.remote, "rev-parse", ref), ref)


class LeasedPushTest(Base):
    def test_pushes_everything_with_main_alone_and_last(self):
        r = self.run_push("--batch", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_remote_matches_work()
        pushes = [l for l in r.stdout.splitlines() if l.startswith(("batch ", "main:"))]
        self.assertEqual(pushes[-1], "main: refs/heads/main")
        self.assertNotIn("refs/heads/main", " ".join(pushes[:-1]))

    def test_rejection_holds_main_at_default_batch_size(self):
        self.reject_on_remote("refs/heads/b2")
        r = self.run_push()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("HELD refs/heads/main", r.stdout)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/main"), git(self.mirror, "rev-parse", "refs/heads/main"))

    def test_partial_push_then_rerun_skips_done_refs_and_finishes(self):
        mark = self.reject_on_remote("refs/heads/b2")
        self.assertEqual(self.run_push("--batch", "2").returncode, 1)
        os.remove(mark)
        again = self.run_push("--batch", "2")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertRegex(again.stdout, r"refs: 2 to push, [1-9]\d* already done")
        self.assert_remote_matches_work()

    def test_push_after_backup_stops_everything_before_any_push(self):
        late = self.late_push("b1")
        r = self.run_push()
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("MOVED refs/heads/b1", r.stdout)
        for phrase in ("nothing pushed", "find who (the freeze leaked)",       # R4-04: the recovery text
                       "Never fetch into the existing backup", "Make a NEW backup directory",
                       "pass both backups to local_cleanup.py changed"):
            self.assertIn(phrase, r.stdout)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/b1"), late)
        self.assertEqual(self.before.replace(git(self.mirror, "rev-parse", "refs/heads/b1"), late),
                         git(self.remote, "for-each-ref"))

    def test_push_landing_during_the_run_is_rejected_and_rerun_refuses(self):
        other = os.path.join(self.tmp.name, "other-b1")
        subprocess.run(["git", "clone", "-q", self.remote, other], check=True, env=ENV)
        code = ("import subprocess\n"
                "g = ['git', '-C', %r]\n"
                "subprocess.run(g + ['checkout', '-q', 'b1'], check=True)\n"
                "open(%r, 'w').write('late\\n')\n"
                "subprocess.run(g + ['add', 'late.txt'], check=True)\n"
                "subprocess.run(g + ['commit', '-q', '-m', 'late'], check=True)\n"
                "subprocess.run(g + ['push', '-q', 'origin', 'b1'], check=True)\n"
                % (other, os.path.join(other, "late.txt")))
        r = self.run_push(env={"LEASED_PUSH_TEST_BEFORE_PUSH": self.hook_cmd(code)})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        late = git(other, "rev-parse", "HEAD")
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/b1"), late)
        self.assertIn("HELD refs/heads/main", r.stdout)
        again = self.run_push()
        self.assertEqual(again.returncode, 3, again.stdout + again.stderr)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/b1"), late)

    def test_recovery_with_stale_rewrite_is_refused(self):
        late = self.late_push("b1")
        self.assertEqual(self.run_push().returncode, 3)
        git(self.mirror, "fetch", "-q", self.remote, "+refs/heads/b1:refs/heads/b1")   # the forbidden recovery
        r = self.run_push()                                                           # work.git was NOT redone
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("STALE refs/heads/b1", r.stdout)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/b1"), late)
        second = self.new_backup()                                                    # the documented recovery
        self.rewrite(backup=second)
        ok = self.run_push(mirror=second)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertIn("late.txt", git(self.remote, "ls-tree", "--name-only", "refs/heads/b1"))

    def test_branch_added_to_backup_after_copy_is_stale_and_nothing_deleted(self):
        # R4-01: the old code inferred "deleted by the rewrite" from the LIVE backup, so a branch
        # added to the backup after the copy was made looked deleted and --delete-removed deleted it.
        other = os.path.join(self.tmp.name, "other-legit")
        subprocess.run(["git", "clone", "-q", self.remote, other], check=True, env=ENV)
        git(other, "push", "-q", "origin", "HEAD:refs/heads/legit")
        git(self.mirror, "fetch", "-q", self.remote, "+refs/heads/*:refs/heads/*")
        on_remote = git(self.remote, "for-each-ref")
        r = self.run_push("--delete-removed")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("STALE refs/heads/legit", r.stdout)
        self.assertIn("the backup changed after the copy was made", r.stdout)
        self.assertEqual(git(self.remote, "for-each-ref"), on_remote)

    def test_ref_removed_from_backup_after_copy_is_stale(self):
        git(self.mirror, "update-ref", "-d", "refs/tags/v1")
        r = self.run_push()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("STALE refs/tags/v1", r.stdout)
        self.assertEqual(self.before, git(self.remote, "for-each-ref"))

    def test_copy_not_made_with_prepare_is_refused(self):
        plain = os.path.join(self.tmp.name, "plain-rewrite.git")
        subprocess.run(["git", "clone", "-q", "--mirror", "--no-local", self.mirror, plain], check=True, env=ENV)
        git(plain, "filter-repo", "--force", "--replace-text", self.rules, "--replace-message", self.rules)
        r = self.run_push(work=plain)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("make the copy with `prepare`", r.stdout)
        self.assertEqual(self.before, git(self.remote, "for-each-ref"))

    def test_second_filter_repo_pass_on_same_copy_is_allowed(self):
        second = os.path.join(self.tmp.name, "rules2.txt")
        write(second, "v3==>vX\n")       # e.g. a separate mailmap pass: ref-map keeps the backup as "old"
        git(self.work, "filter-repo", "--force", "--replace-text", second)
        r = self.run_push()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_remote_matches_work()

    def test_missing_ref_map_is_refused(self):
        bare = os.path.join(self.tmp.name, "plain.git")
        subprocess.run(["git", "clone", "-q", "--mirror", self.mirror, bare], check=True, env=ENV)
        r = self.run_push(work=bare)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(self.before, git(self.remote, "for-each-ref"))

    def add_notes_only_branch(self):
        """A branch whose every commit the rewrite purges: filter-repo deletes it from work.git."""
        git(self.src, "checkout", "-q", "--orphan", "notesonly")
        git(self.src, "rm", "-q", "-rf", ".")
        os.makedirs(os.path.join(self.src, "notes"))
        write(os.path.join(self.src, "notes", "x.md"), "secret\n")
        git(self.src, "add", "notes")
        git(self.src, "commit", "-q", "-m", "notes only")
        git(self.src, "push", "-q", self.remote, "notesonly")
        git(self.mirror, "fetch", "-q", self.remote, "+refs/heads/*:refs/heads/*")
        self.rewrite(extra=("--invert-paths", "--path", "notes"))

    def test_ref_deleted_by_rewrite_needs_explicit_delete(self):
        self.add_notes_only_branch()
        r = self.run_push()
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("DELETED-BY-REWRITE refs/heads/notesonly", r.stdout)
        self.assertEqual(git(self.remote, "for-each-ref", "--format=%(refname)", "refs/heads/notesonly"),
                         "refs/heads/notesonly")
        d = self.run_push("--delete-removed")
        self.assertEqual(d.returncode, 0, d.stdout + d.stderr)
        self.assertEqual(git(self.remote, "for-each-ref", "--format=%(refname)", "refs/heads/notesonly"), "")
        self.assert_remote_matches_work()

    def test_ref_deleted_by_rewrite_then_moved_on_remote_is_moved(self):
        self.add_notes_only_branch()
        late = self.late_push("notesonly")
        r = self.run_push("--delete-removed")
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("MOVED refs/heads/notesonly", r.stdout)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/notesonly"), late)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/main"), git(self.mirror, "rev-parse", "refs/heads/main"))

    def test_branch_created_after_backup_stops_everything(self):
        other = os.path.join(self.tmp.name, "other-new")
        subprocess.run(["git", "clone", "-q", self.remote, other], check=True, env=ENV)
        git(other, "push", "-q", "origin", "HEAD~1:refs/heads/late-new")      # old history, new name
        r = self.run_push()
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("MOVED refs/heads/late-new", r.stdout)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/main"), git(self.mirror, "rev-parse", "refs/heads/main"))

    def test_batch_failing_without_porcelain_is_a_failure(self):
        code = "import os\nos.rename(%r, %r)\n" % (self.remote, self.remote + ".gone")
        r = self.run_push(env={"LEASED_PUSH_TEST_BEFORE_PUSH": self.hook_cmd(code)})
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("batch 1 failed", r.stdout)

    def test_dry_run_changes_nothing(self):
        r = self.run_push("--dry-run")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(self.before, git(self.remote, "for-each-ref"))

    def test_bad_paths_and_url_are_errors(self):
        for kw in ({"work": self.work + "-typo"}, {"mirror": self.mirror + "-typo"},
                   {"url": os.path.join(self.tmp.name, "nope.git")}):
            r = self.run_push(**kw)
            self.assertEqual(r.returncode, 2, "%s: %s" % (kw, r.stdout + r.stderr))
        self.assertEqual(self.before, git(self.remote, "for-each-ref"))


class PrepareTest(Base):
    def run_prepare(self, backup, work):
        return subprocess.run([sys.executable, "-I", SCRIPT, "prepare", backup, work],
                              capture_output=True, text=True, env=ENV)

    def test_prepare_clones_and_snapshots_the_backup_refs(self):
        work = os.path.join(self.tmp.name, "fresh.git")
        r = self.run_prepare(self.mirror, work)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with open(os.path.join(work, "purge-backup-refs.txt"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(lines[0], "# backup " + os.path.abspath(self.mirror))
        self.assertEqual(lines[1:], git(self.mirror, "for-each-ref", "--format=%(objectname) %(refname)",
                                        "refs/heads", "refs/tags").splitlines())
        self.assertEqual(git(work, "for-each-ref"), git(self.mirror, "for-each-ref"))

    def test_prepare_refuses_an_existing_directory(self):
        before = sorted(os.listdir(self.work))
        r = self.run_prepare(self.mirror, self.work)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("already exists", r.stdout)
        self.assertEqual(sorted(os.listdir(self.work)), before)
        empty = os.path.join(self.tmp.name, "empty.git")     # git itself would clone into an empty dir
        os.mkdir(empty)
        r = self.run_prepare(self.mirror, empty)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("already exists", r.stdout)
        self.assertEqual(os.listdir(empty), [])


class MasterBranchTest(Base):
    BRANCH = "master"

    def test_main_ref_option_holds_the_default_branch(self):
        self.reject_on_remote("refs/heads/b2")
        r = self.run_push("--main-ref", "refs/heads/master")
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("HELD refs/heads/master", r.stdout)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/master"),
                         git(self.mirror, "rev-parse", "refs/heads/master"))

    def test_default_branch_is_read_from_the_remote_and_pushed_last(self):
        # R4-09: without --main-ref the old code assumed refs/heads/main and batched master
        r = self.run_push("--batch", "2")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assert_remote_matches_work()
        pushes = [l for l in r.stdout.splitlines() if l.startswith(("batch ", "main:"))]
        self.assertEqual(pushes[-1], "main: refs/heads/master")
        self.assertNotIn("refs/heads/master", " ".join(pushes[:-1]))

    def test_detected_default_branch_is_held_on_rejection(self):
        self.reject_on_remote("refs/heads/b2")
        r = self.run_push()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("HELD refs/heads/master", r.stdout)
        self.assertEqual(git(self.remote, "rev-parse", "refs/heads/master"),
                         git(self.mirror, "rev-parse", "refs/heads/master"))

    def test_main_ref_that_differs_from_the_remote_head_is_refused(self):
        r = self.run_push("--main-ref", "refs/heads/main")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("refs/heads/master", r.stdout)
        self.assertEqual(self.before, git(self.remote, "for-each-ref"))


class NoRemoteHeadTest(Base):
    def test_remote_without_a_head_needs_main_ref_and_it_must_exist(self):
        git(self.remote, "symbolic-ref", "HEAD", "refs/heads/nothere")     # dangling: ls-remote reports no HEAD
        r = self.run_push()
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("--main-ref", r.stdout)
        self.assertEqual(self.before, git(self.remote, "for-each-ref"))
        r = self.run_push("--main-ref", "refs/heads/nothere")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("not in the rewritten copy", r.stdout)
        self.assertEqual(self.before, git(self.remote, "for-each-ref"))
        ok = self.run_push("--main-ref", "refs/heads/main")
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assert_remote_matches_work()


if __name__ == "__main__":
    unittest.main()
