#!/usr/bin/env python3
"""Move a pinned commit, WITH its git history, from the host checkout to a review box.

Host (Windows, the shared checkout):
    python tools/review_copy.py bundle --rev <sha> --out <file.bundle> [--base <ref>]
Review box (the cloud container, any POSIX shell):
    python3 tools/review_copy.py clone --bundle <file.bundle> --rev <sha> --dest <dir> [--read-only]

WHY: merge-gate rounds were built from `git archive` zips: CRLF files (the Windows
checkout's autocrlf) and NO git history, so every round needed a hand-run CRLF strip
plus a throwaway `git init`, and history-dependent suites (lease-form-qc's frozen-
original tests, skill_drift_report ancestry) still failed for environmental reasons --
two wasted suite runs per PR (2026-11-02, PR #199). A bundle carries the real objects,
so the clone has the exact committed bytes (LF as stored) and full ancestry.

bundle: points a temporary ref refs/review/<sha> at --rev, bundles it plus --base
        (default origin/main, so the reviewer can `git diff origin/main..<sha>`),
        then deletes the temp ref. Prints the path, size and sha256.
clone:  clones the bundle with core.autocrlf=false, detaches at --rev, verifies HEAD,
        and with --read-only clears every write bit (tree and .git) so reviewers must
        copy it before probing.
"""
import argparse
import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path


def _git(*args, cwd=None):
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()}")
    return r.stdout.strip()


def bundle(rev, out, base="origin/main", repo="."):
    sha = _git("rev-parse", "--verify", f"{rev}^{{commit}}", cwd=repo)
    ref = f"refs/review/{sha}-{os.getpid()}"  # per-process: concurrent runs never delete each other's ref
    refs = [ref]
    if base:
        _git("rev-parse", "--verify", base, cwd=repo)
        full = _git("rev-parse", "--symbolic-full-name", base, cwd=repo)
        if not full:
            raise RuntimeError(f"--base {base!r} must be a ref name (a raw SHA cannot be bundled as a ref)")
        refs.append(full)
    _git("update-ref", ref, sha, cwd=repo)
    try:
        out = Path(out).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        _git("bundle", "create", str(out), *refs, cwd=repo)
    finally:
        _git("update-ref", "-d", ref, cwd=repo)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    print(f"bundle {out} rev={sha} base={refs[1] if len(refs) > 1 else '-'} "
          f"bytes={out.stat().st_size} sha256={digest}")
    return sha, digest


def _clear_write_bits(root):
    for dirpath, dirnames, filenames in os.walk(root):
        for n in filenames:
            p = os.path.join(dirpath, n)
            if not os.path.islink(p):
                os.chmod(p, os.stat(p).st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        os.chmod(dirpath, os.stat(dirpath).st_mode & ~(stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH))


def clone(bundle_path, rev, dest, read_only=False):
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise RuntimeError(f"{dest} exists and is not empty")
    # init + fetch, not clone: the bundle carries refs/review/* and refs/remotes/*, no
    # refs/heads/*, so a plain clone would map nothing and check out nothing.
    dest.mkdir(parents=True, exist_ok=True)
    _git("init", "-q", str(dest))
    _git("config", "core.autocrlf", "false", cwd=dest)
    # every bundle ref under refs/review-bundle/, plus refs/remotes/* kept at their usual
    # names so `git diff origin/main..HEAD` works as on the host.
    if rev == "HEAD" or rev.startswith("-"):
        raise RuntimeError("clone --rev needs the pinned SHA the bundle step printed, not HEAD")
    # local-branch bases keep their names too (`--base main` -> `git diff main..HEAD`)
    _git("fetch", "-q", "--update-head-ok", str(Path(bundle_path).resolve()),
         "refs/*:refs/review-bundle/*", "refs/remotes/*:refs/remotes/*", "refs/heads/*:refs/heads/*",
         cwd=dest)
    _git("-c", "advice.detachedHead=false", "checkout", "-q", "--detach", rev, cwd=dest)
    head = _git("rev-parse", "HEAD", cwd=dest)
    want = _git("rev-parse", "--verify", f"{rev}^{{commit}}", cwd=dest)
    if head != want:
        raise RuntimeError(f"HEAD {head} != requested {want}")
    depth = _git("rev-list", "--count", "HEAD", cwd=dest)
    if read_only:
        _clear_write_bits(dest)
    print(f"clone {dest} HEAD={head} commits={depth} read_only={read_only}")
    return head


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("bundle", help="host side: bundle a pinned commit with history")
    b.add_argument("--rev", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--base", default="origin/main", help="extra ref to include ('' for none)")
    b.add_argument("--repo", default=".")
    c = sub.add_parser("clone", help="review side: clone the bundle at the pinned commit")
    c.add_argument("--bundle", required=True)
    c.add_argument("--rev", required=True)
    c.add_argument("--dest", required=True)
    c.add_argument("--read-only", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "bundle":
            bundle(a.rev, a.out, a.base or None, a.repo)
        else:
            clone(a.bundle, a.rev, a.dest, a.read_only)
    except (RuntimeError, OSError) as e:
        print(f"review_copy: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
