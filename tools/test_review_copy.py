"""Tests for tools/review_copy.py: bundle on the host, clone on the review box."""
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import review_copy as rc  # noqa: E402


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class ReviewCopyRoundTrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.origin = root / "origin"
        self.repo = root / "repo"
        self.origin.mkdir()
        git(self.origin, "init", "-q", "--bare")
        self.repo.mkdir()
        git(self.repo, "init", "-q")
        for k, v in (("user.email", "t@t"), ("user.name", "t"), ("core.autocrlf", "false")):
            git(self.repo, "config", k, v)
        (self.repo / "a.txt").write_bytes(b"one\n")
        git(self.repo, "add", "a.txt")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "remote", "add", "origin", str(self.origin))
        git(self.repo, "push", "-q", "origin", "HEAD:refs/heads/main")
        git(self.repo, "fetch", "-q", "origin")
        (self.repo / "a.txt").write_bytes(b"one\ntwo\n")
        git(self.repo, "commit", "-q", "-am", "pr head")
        self.sha = git(self.repo, "rev-parse", "HEAD")
        self.bundle = root / "x.bundle"

    def tearDown(self):
        for dirpath, dirnames, filenames in os.walk(self.tmp.name):
            os.chmod(dirpath, 0o755)
            for n in filenames:
                p = os.path.join(dirpath, n)
                if not os.path.islink(p):
                    os.chmod(p, 0o644)
        self.tmp.cleanup()

    def test_clone_has_history_base_and_exact_bytes(self):
        rc.bundle(self.sha, self.bundle, "origin/main", str(self.repo))
        dest = Path(self.tmp.name) / "review"
        self.assertEqual(rc.clone(self.bundle, self.sha, dest), self.sha)
        self.assertEqual(git(dest, "rev-list", "--count", "HEAD"), "2")
        self.assertEqual(git(dest, "diff", "--name-only", "origin/main..HEAD"), "a.txt")
        self.assertEqual((dest / "a.txt").read_bytes(), b"one\ntwo\n")

    def test_temp_ref_is_removed_from_the_host(self):
        rc.bundle(self.sha, self.bundle, "origin/main", str(self.repo))
        refs = git(self.repo, "for-each-ref", "refs/review/")
        self.assertEqual(refs, "")

    def test_read_only_clears_write_bits(self):
        rc.bundle(self.sha, self.bundle, "origin/main", str(self.repo))
        dest = Path(self.tmp.name) / "ro"
        rc.clone(self.bundle, self.sha, dest, read_only=True)
        for p in (dest / "a.txt", dest, dest / ".git" / "HEAD"):
            self.assertFalse(os.stat(p).st_mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH), p)

    def test_refuses_non_empty_dest(self):
        rc.bundle(self.sha, self.bundle, None, str(self.repo))
        dest = Path(self.tmp.name) / "busy"
        dest.mkdir()
        (dest / "f").write_text("x")
        with self.assertRaises(RuntimeError):
            rc.clone(self.bundle, self.sha, dest)

    def test_local_branch_base_keeps_its_name(self):
        git(self.repo, "branch", "basebr", "origin/main")
        rc.bundle(self.sha, self.bundle, "basebr", str(self.repo))
        dest = Path(self.tmp.name) / "lb"
        rc.clone(self.bundle, self.sha, dest)
        self.assertEqual(git(dest, "diff", "--name-only", "basebr..HEAD"), "a.txt")

    def test_raw_sha_base_is_refused(self):
        base_sha = git(self.repo, "rev-parse", "origin/main")
        self.assertEqual(rc.main(["bundle", "--rev", self.sha, "--out", str(self.bundle),
                                  "--base", base_sha, "--repo", str(self.repo)]), 1)

    def test_clone_rev_head_is_refused(self):
        rc.bundle(self.sha, self.bundle, None, str(self.repo))
        with self.assertRaises(RuntimeError):
            rc.clone(self.bundle, "HEAD", Path(self.tmp.name) / "h")

    def test_unknown_rev_fails_cleanly(self):
        self.assertEqual(rc.main(["bundle", "--rev", "deadbeef" * 5, "--out", str(self.bundle),
                                  "--repo", str(self.repo)]), 1)


if __name__ == "__main__":
    unittest.main()
