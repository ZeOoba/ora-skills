#!/usr/bin/env python3
"""release_plugin.py - bump + build + commit a plugin bundle in one atomic step.

WHY (2026-07-17): `build_plugin.py --bump` writes the new version into the tracked
`plugins/<name>/plugin-build.json` but does NOT commit it. If the bumped `.plugin` is
then installed while the manifest bump is never committed, the runtime cache carries a
version the repo does not reflect -- the exact "version landed in the cache but not the
repo" gap the ora-operations-extensions reinstall close-out flagged. This wrapper keeps
the base builder side-effect-free on git and owns the commit itself: bump -> build ->
commit the manifest, so you can't bump without committing.

SCOPE / SAFETY:
  - Commits ONLY plugins/<name>/plugin-build.json (git commit <pathspec> form -- never
    stages or sweeps any other working-tree change into the release commit).
  - Refuses to run if that manifest already has uncommitted changes (would otherwise
    fold a pre-existing edit into the release commit).
  - Does NOT push. Push stays manual (mirrors the Netlify preview-default doctrine).
  - --dry-run computes and prints the bump + the exact git command, writes nothing,
    builds nothing, commits nothing.

Usage:
  python tools/release_plugin.py <plugin> <outdir> [--bump patch|minor|major] [--dry-run]
  (--bump defaults to patch)
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_plugin  # noqa: E402
from package_skills import REPO, PLUGINS_DIR  # noqa: E402


def _git(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(REPO), *args],
        capture_output=True, text=True,
    )


def _manifest_relpath(plugin: str) -> str:
    # Repo-relative, forward-slash pathspec for git.
    return (PLUGINS_DIR / plugin / "plugin-build.json").relative_to(REPO).as_posix()


def _current_version(plugin: str) -> str:
    return build_plugin.load_manifest(plugin).get("version", "0.0.0")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Bump + build + commit a plugin bundle atomically (no push).")
    ap.add_argument("plugin")
    ap.add_argument("outdir")
    ap.add_argument("--bump", choices=("patch", "minor", "major"), default="patch")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    rel = _manifest_relpath(a.plugin)
    cur = _current_version(a.plugin)
    nxt = build_plugin.bump_version(cur, a.bump)
    msg = f"chore(plugins): bump {a.plugin} -> v{nxt} (release_plugin --bump {a.bump})"

    if a.dry_run:
        print(f"[dry-run] {a.plugin}: v{cur} -> v{nxt} ({a.bump})")
        print(f"[dry-run] would build .plugin into: {a.outdir}")
        print(f"[dry-run] would run: git -C <repo> commit {rel} -m \"{msg}\"")
        print("[dry-run] nothing written, built, or committed.")
        return 0

    # Guard: the manifest must be clean going in, so the release commit contains ONLY
    # our version bump and not some pre-existing uncommitted edit to the same file.
    st = _git("status", "--porcelain", "--", rel)
    if st.returncode != 0:
        sys.stderr.write(f"git status failed:\n{st.stderr}")
        return 1
    if st.stdout.strip():
        sys.stderr.write(
            f"REFUSING: {rel} already has uncommitted changes:\n{st.stdout}"
            "Commit or revert them first, then re-run.\n")
        return 1

    # build_plugin.build_plugin validates against the CURRENT manifest BEFORE writing the
    # bump, so a validation failure (bad name, oversized description, missing member
    # SKILL.md) never touches the tracked file. Only after it returns has the manifest
    # been bumped and the .plugin built.
    dest = build_plugin.build_plugin(a.plugin, Path(a.outdir), bump=a.bump)

    cm = _git("commit", rel, "-m", msg)
    if cm.returncode != 0:
        sys.stderr.write(
            "\n*** BUMP BUILT BUT COMMIT FAILED ***\n"
            f"{cm.stderr}{cm.stdout}\n"
            f"The manifest is now bumped to v{nxt} on disk but UNCOMMITTED.\n"
            f"Recover with either:\n"
            f"  git -C \"{REPO}\" commit {rel} -m \"{msg}\"   (keep the bump)\n"
            f"  git -C \"{REPO}\" checkout -- {rel}            (discard the bump)\n")
        return 1

    head = _git("rev-parse", "--short", "HEAD").stdout.strip()
    print(f"committed {head}: {msg}")
    print(f"staged bundle: {dest}")
    print("NOT pushed -- run `git push` when ready.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
