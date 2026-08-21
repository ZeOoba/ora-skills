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


def _normalize_remote(url):
    if not url:
        return url
    u = url.strip().lower()
    if u.endswith(".git"):
        u = u[:-4]
    return u


def discover_clones_by_remote(root=CLONE_ROOT):
    """Enumerate every direct child of `root` holding a `.git`, group by
    normalized `origin` remote. Two or more clones sharing one remote is the
    signal -- everything past the first is a candidate stray. Does not
    recurse past one level (repo internals are not walked)."""
    root_path = Path(root)
    if not root_path.is_dir():
        return {"error": f"not a directory: {root}"}

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
        classified = []
        for i, p in enumerate(paths):
            path_lower = p.lower()
            if any(hint in path_lower for hint in MANAGED_BUILD_ROOT_HINTS):
                role = "managed-build-root"
            elif i == 0:
                role = "primary"
            else:
                role = "stray"
            classified.append({"path": p, "role": role})
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
        is_trivial = any(hint in path.lower() for hint in TRIVIAL_HINTS)
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
                    print(f"    [{c['role']}] {c['path']}")
            if clone_discovery["unreachable"]:
                print(f"  unreachable (no readable origin remote): {clone_discovery['unreachable']}")


if __name__ == "__main__":
    sys.exit(main())
