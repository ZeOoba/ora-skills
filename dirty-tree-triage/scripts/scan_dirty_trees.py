#!/usr/bin/env python3
"""Enumerate and classify dirty git working trees across ORA's known checkouts.

Mechanical scan only -- no attribution, no settlement judgment, no commits.
Those steps need session-roster + provenance + mtime-over-time evidence that
this script has no access to; see dirty-tree-triage/SKILL.md Standard Workflow
steps 3-6 for how a Claude session should follow up on this script's output.

Usage:
    python scan_dirty_trees.py [--repo PATH ...] [--json]

With no --repo given, scans the default ORA repo set below. Pass --repo one
or more times to scan a different/additional set instead.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_REPOS = [
    r"C:\Users\Owner\.claude",
    r"C:\Users\Owner\ora-skills",
    r"C:\Users\Owner\website-canonical",
    r"C:\Users\Owner\oxford-command-center",
]

# Name fragments that make an untracked entry read as obvious scratch/throwaway
# content rather than someone's real WIP. Conservative on purpose -- anything
# not matching one of these stays in the "modified/untracked, needs review"
# bucket rather than being auto-labeled trivial.
TRIVIAL_HINTS = ("scratch", "preview-deploy", "_archive/", ".tmp", "tmpindex")
# Matched against the DIRECTORY part of a path only -- a file's own name is
# content ("..._scratch-exclusion_spec.md" is a spec, not scratch). Only these
# temp-file markers are also checked against the filename itself.
FILENAME_TRIVIAL_HINTS = (".tmp", "tmpindex")


CLONE_ROOT = r"C:\Users\Owner"

# Path substrings that mark a clone as a managed build root rather than a
# stray -- e.g. Sync-DeployBuildRoot's own `-deploy-build` convention. Expected
# to sit detached from a branch; never flagged.
MANAGED_BUILD_ROOT_HINTS = ("-deploy-build",)


def _git_remote_origin(repo_path):
    proc = subprocess.run(
        ["git", "-C", str(repo_path), "remote", "get-url", "origin"],
        capture_output=True, text=True, check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _is_linked_worktree(repo_path):
    """True for a `git worktree add` checkout: its private git dir
    (.git/worktrees/<name>) differs from the shared common dir. A submodule
    also has a `.git` file, but its git dir IS its common dir."""
    out = _git_out(repo_path, "rev-parse", "--path-format=absolute",
                   "--git-dir", "--git-common-dir")
    if not out:
        return False
    lines = out.splitlines()
    return len(lines) == 2 and _path_key(lines[0]) != _path_key(lines[1])


def _normalize_remote(url):
    if not url:
        return url
    u = url.strip().lower()
    if u.endswith(".git"):
        u = u[:-4]
    return u


def _path_key(path):
    return os.path.normcase(os.path.normpath(os.path.abspath(path)))


def _git_out(repo_path, *args):
    proc = subprocess.run(
        ["git", "-C", str(repo_path), *args],
        capture_output=True, text=True, check=False,
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def _main_worktree(repo_path):
    """First entry of `git worktree list --porcelain` is always the main
    worktree (the checkout that owns the shared .git directory)."""
    out = _git_out(repo_path, "worktree", "list", "--porcelain")
    if not out:
        return None
    for line in out.splitlines():
        if line.startswith("worktree "):
            return line[len("worktree "):]
    return None


def _default_branch_ref(repo_path):
    ref = _git_out(repo_path, "symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD")
    if ref:
        return ref
    for candidate in ("origin/main", "origin/master"):
        if _git_out(repo_path, "rev-parse", "-q", "--verify", candidate) is not None:
            return candidate
    return None


def _worktree_details(repo_path):
    """Branch + merge state for a linked worktree. None = could not tell.

    `merged` means only "HEAD has no commits beyond origin's default branch" --
    a freshly created worktree is merged=True, so read it with `dirty`. A
    squash-merged PR branch reads merged=False; `upstream_gone` (tracking
    branch deleted on the remote, as of the last fetch --prune) is consistent
    with that but also with a branch deleted unmerged -- confirm the PR state
    before treating either as finished."""
    branch = _git_out(repo_path, "symbolic-ref", "-q", "--short", "HEAD")
    status = _git_out(repo_path, "status", "--porcelain=v1")
    dirty = None if status is None else bool(status)
    default_ref = _default_branch_ref(repo_path)
    merged = None
    if default_ref:
        proc = subprocess.run(
            ["git", "-C", str(repo_path), "merge-base", "--is-ancestor", "HEAD", default_ref],
            capture_output=True, text=True, check=False,
        )
        merged = {0: True, 1: False}.get(proc.returncode)
    upstream_gone = None
    if branch:
        track = _git_out(repo_path, "for-each-ref", "--format=%(upstream)|%(upstream:track)",
                         f"refs/heads/{branch}")
        if track is not None:
            upstream, _, state = track.partition("|")
            upstream_gone = (state == "[gone]") if upstream else None
    return {
        "branch": branch,
        "dirty": dirty,
        "merged": merged,
        "merged_against": default_ref,
        "upstream_gone": upstream_gone,
        "main_worktree": _main_worktree(repo_path),
    }


def discover_clones_by_remote(root=CLONE_ROOT, roster=None):
    """Enumerate every direct child of `root` holding a `.git`, group by
    normalized `origin` remote, and classify each member of a group sharing
    one remote:

    - `managed-build-root` -- path matches MANAGED_BUILD_ROOT_HINTS.
    - `worktree` -- a registered linked worktree (`.git` FILE whose git dir
      differs from the common dir); reported with branch + merge state.
    - `primary` -- first match of: a full clone on `roster` (DEFAULT_REPOS),
      the main worktree owning a linked worktree in the group, else the first
      full clone found.
    - `stray` -- any other full clone (an independent re-clone).

    Does not recurse past one level (repo internals are not walked)."""
    root_path = Path(root)
    if not root_path.is_dir():
        return {"error": f"not a directory: {root}"}
    roster_keys = {_path_key(p) for p in (DEFAULT_REPOS if roster is None else roster)}

    by_remote = {}
    unreachable = []
    for child in sorted(root_path.iterdir()):
        if not child.is_dir():
            continue
        if not (child / ".git").exists():
            continue
        remote = _git_remote_origin(child)
        if remote is None:
            unreachable.append(str(child))
            continue
        key = _normalize_remote(remote)
        by_remote.setdefault(key, []).append(str(child))

    groups = []
    for remote, paths in sorted(by_remote.items()):
        if len(paths) < 2:
            continue
        entries = []
        for p in paths:
            entry = {"path": p}
            if any(hint in p.lower() for hint in MANAGED_BUILD_ROOT_HINTS):
                entry["role"] = "managed-build-root"
            elif (Path(p) / ".git").is_file() and _is_linked_worktree(p):
                entry["role"] = "worktree"
                entry.update(_worktree_details(p))
            entries.append(entry)

        full_clones = [e for e in entries if "role" not in e]
        main_keys = {_path_key(e["main_worktree"]) for e in entries
                     if e.get("role") == "worktree" and e.get("main_worktree")}
        primary = (
            next((e for e in full_clones if _path_key(e["path"]) in roster_keys), None)
            or next((e for e in full_clones if _path_key(e["path"]) in main_keys), None)
            or (full_clones[0] if full_clones else None)
        )
        for e in full_clones:
            e["role"] = "primary" if e is primary else "stray"
        classified = [{"path": e.pop("path"), "role": e.pop("role"), **e} for e in entries]
        groups.append({"remote": remote, "clones": classified})

    return {
        "root": str(root_path),
        "remote_groups_with_duplicates": groups,
        "unreachable": unreachable,
    }


def classify(porcelain_line):
    """One `git status --porcelain=v1` line -> (category, path)."""
    status = porcelain_line[:2]
    path = porcelain_line[3:].strip()
    if status == "??":
        is_dir = path.endswith("/")
        norm = path.lower().replace("\\", "/")
        if is_dir:
            dir_part, name = norm.rstrip("/"), ""
        else:
            dir_part, _, name = norm.rpartition("/")
        is_trivial = (any(hint in dir_part + "/" for hint in TRIVIAL_HINTS)
                      or any(hint in name for hint in FILENAME_TRIVIAL_HINTS))
        category = "untracked-trivial" if is_trivial else (
            "untracked-dir" if is_dir else "untracked-file"
        )
    elif status[0] not in (" ", "?"):
        category = "staged"
    else:
        category = "modified-tracked"
    return category, path


def scan_repo(repo_path):
    repo = Path(repo_path)
    if not (repo / ".git").exists():
        return {"repo": str(repo), "error": "not a git repo (no .git)"}

    branch_proc = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "--branch"],
        capture_output=True, text=True, check=False,
    )
    if branch_proc.returncode != 0:
        return {"repo": str(repo), "error": branch_proc.stderr.strip()}

    lines = branch_proc.stdout.splitlines()
    branch_line = lines[0] if lines and lines[0].startswith("##") else "## (unknown)"
    entries = []
    for line in lines[1:]:
        if not line.strip():
            continue
        category, path = classify(line)
        entries.append({"category": category, "path": path, "raw": line})

    by_category = {}
    for e in entries:
        by_category.setdefault(e["category"], 0)
        by_category[e["category"]] += 1

    return {
        "repo": str(repo),
        "branch": branch_line.lstrip("#").strip(),
        "dirty_count": len(entries),
        "by_category": by_category,
        "entries": entries,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", action="append", dest="repos", default=None,
                         help="Repo path to scan (repeatable). Default: the ORA known set.")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of a text table.")
    parser.add_argument("--no-clone-discovery", action="store_true",
                         help="Skip the stray-clone-by-remote scan (runs by default alongside the dirty scan).")
    args = parser.parse_args()

    repos = args.repos or DEFAULT_REPOS
    results = [scan_repo(r) for r in repos]
    clone_discovery = None if args.no_clone_discovery else discover_clones_by_remote()

    if args.json:
        print(json.dumps({"dirty_scan": results, "clone_discovery": clone_discovery}, indent=2))
        return

    for r in results:
        print(f"=== {r['repo']} ===")
        if "error" in r:
            print(f"  {r['error']}")
            continue
        print(f"  branch: {r['branch']}")
        print(f"  dirty:  {r['dirty_count']} entr{'y' if r['dirty_count'] == 1 else 'ies'}")
        for cat, count in sorted(r["by_category"].items()):
            print(f"    {cat}: {count}")
        print()

    total = sum(r.get("dirty_count", 0) for r in results)
    print(f"TOTAL across {len(results)} repo(s): {total} dirty entries")
    if total:
        print("Next: attribute + settle before touching anything -- see SKILL.md steps 3-6. "
              "This script does not commit, archive, or delete anything.")

    if clone_discovery is not None:
        print()
        print(f"=== stray-clone discovery ({clone_discovery.get('root', '?')}) ===")
        if "error" in clone_discovery:
            print(f"  {clone_discovery['error']}")
        else:
            groups = clone_discovery["remote_groups_with_duplicates"]
            if not groups:
                print("  no remote shared by 2+ clones -- nothing to flag.")
            for g in groups:
                print(f"  remote: {g['remote']}")
                for c in g["clones"]:
                    line = f"    [{c['role']}] {c['path']}"
                    if c["role"] == "worktree":
                        merged = {True: "yes", False: "no", None: "unknown"}[c["merged"]]
                        dirty = {True: "yes", False: "no", None: "unknown"}[c["dirty"]]
                        line += (f"  branch={c['branch'] or '(detached)'}  dirty={dirty}"
                                 f"  merged={merged} (vs {c['merged_against'] or '?'})")
                        if c["upstream_gone"]:
                            line += "  upstream=gone"
                    print(line)
            if clone_discovery["unreachable"]:
                print(f"  unreachable (no readable origin remote): {clone_discovery['unreachable']}")


if __name__ == "__main__":
    sys.exit(main())
