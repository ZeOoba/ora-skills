#!/usr/bin/env python3
"""build_plugin.py - build a Cowork-importable .plugin bundle from repo sources.

WHY THIS EXISTS (2026-07-16): deal-retirement and submarket-spatial-analysis reach
the Cowork runtime as MEMBERS of the ora-operations-extensions plugin, not as
standalone Save-skill installs. A standalone .skill of a bundled skill is the WRONG
target (shadow copy; plugin's loaded copy stays stale). The bundle also had no
source in the repo. This builder version-controls the bundle: it reads
plugins/<name>/plugin-build.json and assembles the .plugin from each member skill's
canonical top-level repo dir.

TWO DELIBERATE MECHANICS (both learned 2026-07-16, both baked in here):
  1. In-memory zip, forward-slash entries. NEVER PowerShell Compress-Archive
     (backslash entries -> importer rejects, zip APPNOTE 4.4.17.1).
  2. Never materialize the bundle tree on disk. A nested copy under the deep Cowork
     session outputs path blows past Windows MAX_PATH (260 chars -> WinError 206);
     writing zip entries straight from source bytes sidesteps it entirely.

Usage:
  python tools/build_plugin.py <plugin-name> <outdir> [--bump patch|minor|major]
"""
import json
import re
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from package_skills import (  # noqa: E402
    REPO, PLUGINS_DIR, MAX_DESC, skill_source_files, resolve_outdir_collision,
    shared_dep_dirty_reason, _dep_pair,
)
import package_skills as _ps  # noqa: E402  (SHARED_ROOT_DEPS read at call time)

KEBAB = re.compile(r'^[a-z0-9]+(-[a-z0-9]+)*$')
# build-only keys that must NOT appear in the shipped .claude-plugin/plugin.json
BUILD_ONLY_KEYS = {'skills'}


def manifest_path(plugin: str) -> Path:
    return PLUGINS_DIR / plugin / 'plugin-build.json'


def load_manifest(plugin: str) -> dict:
    mf = manifest_path(plugin)
    if not mf.is_file():
        raise SystemExit(f'{plugin}: no build manifest at {mf}')
    return json.loads(mf.read_text(encoding='utf-8'))


def bump_version(version: str, part: str) -> str:
    try:
        major, minor, patch = (int(x) for x in version.split('.'))
    except ValueError:
        raise SystemExit(f'version {version!r} is not MAJOR.MINOR.PATCH; cannot --bump')
    if part == 'major':
        return f'{major + 1}.0.0'
    if part == 'minor':
        return f'{major}.{minor + 1}.0'
    if part == 'patch':
        return f'{major}.{minor}.{patch + 1}'
    raise SystemExit(f'--bump takes patch|minor|major, got {part!r}')


def shipped_manifest(build_manifest: dict) -> dict:
    """The .claude-plugin/plugin.json content: build manifest minus build-only keys."""
    return {k: v for k, v in build_manifest.items() if k not in BUILD_ONLY_KEYS}


def plugin_entries(plugin: str, repo_root: Path = REPO, bm: dict | None = None,
                   allow_dirty_shared: bool = False) -> dict[str, bytes]:
    """{zip arcname (forward-slash): file bytes} for the whole bundle, assembled in
    memory. Validates name kebab-case, description length, member skills present."""
    bm = bm if bm is not None else load_manifest(plugin)
    name = bm.get('name', plugin)
    if not KEBAB.match(name):
        raise SystemExit(f'{plugin}: plugin name {name!r} is not kebab-case')
    desc = bm.get('description', '')
    if len(desc) > MAX_DESC:
        raise SystemExit(f'{plugin}: description {len(desc)} chars > {MAX_DESC} limit')
    skills = bm.get('skills', [])
    if not skills:
        raise SystemExit(f'{plugin}: build manifest lists no skills')

    entries: dict[str, bytes] = {}
    entries['.claude-plugin/plugin.json'] = (
        json.dumps(shipped_manifest(bm), indent=2).encode('utf-8')
    )
    readme = PLUGINS_DIR / plugin / 'README.md'
    if readme.is_file():
        entries['README.md'] = readme.read_bytes()

    for skill in skills:
        src_files = skill_source_files(skill, repo_root)
        if 'SKILL.md' not in src_files:
            raise SystemExit(f'{plugin}: member skill {skill!r} has no SKILL.md at {repo_root / skill}')
        shared_src = {_dep_pair(d)[1]: _dep_pair(d)[0] for d in _ps.SHARED_ROOT_DEPS.get(skill, [])}
        private = set(_ps.PRIVATE_LOCAL_DEPS.get(skill, []))
        for name in private:  # refuse a member that would install without its private file
            src_files[name] = None
        for rel, path in src_files.items():
            if rel in private:
                entries[f'skills/{skill}/{rel}'] = _ps.private_dep_bytes(skill, rel, repo_root)
                continue
            data = path.read_bytes()  # read once: the bytes verified are the bytes shipped
            if rel in shared_src and not allow_dirty_shared:
                reason = shared_dep_dirty_reason(repo_root, shared_src[rel], data)
                if reason:
                    raise SystemExit(
                        f'{plugin}: REFUSING to bundle skill {skill!r} -- {reason}. The plugin '
                        f'would ship uncommitted or unverifiable content. Build from a clean '
                        f'checkout of the commit you mean to ship, or pass --allow-dirty-shared.')
            entries[f'skills/{skill}/{rel}'] = data

    bad = [a for a in entries if '\\' in a]
    if bad:
        raise SystemExit(f'{plugin}: backslash entries {bad}')
    return entries


def build_plugin(plugin: str, outdir: Path, bump: str | None = None,
                 repo_root: Path = REPO, allow_dirty_shared: bool = False) -> Path:
    # Mirrors package_skills.py's resolve_outdir_collision guard (2026-07-24 incident):
    # build_plugin() writes into `outdir` via the same skill_source_files() ->
    # rglob('*') -> is_bundled() path shared with the .skill packager, and
    # outdir.mkdir(exist_ok=True) below would silently succeed against an existing
    # skill's own source directory. Checked before load_manifest()/plugin_entries()
    # so a swapped-argument call fails before doing any work.
    collision = resolve_outdir_collision(outdir, repo=repo_root)
    if collision:
        raise SystemExit(
            f'{plugin}: outdir {outdir} resolves to {collision}. This is almost certainly '
            f'a swapped argument — usage is build_plugin.py <plugin-name> <outdir>, not '
            f'<outdir> <plugin-name>. Refusing to dump a .plugin bundle into a skill '
            f'source directory. Pick an outdir outside the repo.'
        )
    bm = load_manifest(plugin)
    # Validate + assemble against the CURRENT (pre-bump) manifest first, so a
    # validation failure (bad kebab name, oversized description, a member
    # skill's SKILL.md missing) never touches the tracked plugin-build.json --
    # and a retry after fixing the real problem doesn't compound a phantom
    # version bump from the failed attempt.
    entries = plugin_entries(plugin, repo_root, bm=bm, allow_dirty_shared=allow_dirty_shared)

    if bump:
        mf = manifest_path(plugin)
        bm['version'] = bump_version(bm.get('version', '0.0.0'), bump)
        mf.write_text(json.dumps(bm, indent=2) + '\n', encoding='utf-8')
        print(f'{plugin}: version bumped -> {bm["version"]}')
        entries['.claude-plugin/plugin.json'] = (
            json.dumps(shipped_manifest(bm), indent=2).encode('utf-8')
        )

    outdir.mkdir(parents=True, exist_ok=True)
    dest = outdir / f'{plugin}.plugin'
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as z:
        for arc in sorted(entries):
            z.writestr(arc, entries[arc])
    with zipfile.ZipFile(dest) as z:
        bad = [n for n in z.namelist() if '\\' in n]
        if bad:
            raise SystemExit(f'{plugin}: backslash entries {bad}')
    ver = json.loads(entries['.claude-plugin/plugin.json'])['version']
    print(f'{dest.name}: v{ver}, {len(entries)} entries OK')
    for arc in sorted(entries):
        print(f'   {arc}')
    return dest


def main() -> None:
    allow_dirty_shared = '--allow-dirty-shared' in sys.argv
    argv = [a for a in sys.argv[1:] if a != '--allow-dirty-shared']
    if not argv or argv[0] in ('-h', '--help') or len(argv) < 2:
        print(__doc__.strip())
        sys.exit(0)
    plugin, outdir = argv[0], Path(argv[1])
    bump = None
    if '--bump' in argv:
        i = argv.index('--bump')
        bump = argv[i + 1] if i + 1 < len(argv) else 'patch'
    build_plugin(plugin, outdir, bump, allow_dirty_shared=allow_dirty_shared)


if __name__ == '__main__':
    main()
