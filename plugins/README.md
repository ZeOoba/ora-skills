# plugins/ — version-controlled Cowork plugin bundles

Some ORA skills reach the Cowork runtime as members of a **plugin bundle**, not as
standalone Save-skill installs. This directory version-controls those bundles.

## Why this exists (2026-07-16)

`deal-retirement` and `submarket-spatial-analysis` are bundled in the
`ora-operations-extensions` plugin. When their SKILL.md was committed, the
post-commit ledger routed them through the standalone Save-skill remedy — the
WRONG target: a Save-skill `.skill` installs a shadow standalone copy and leaves
the plugin's loaded copies stale. The bundle also had no source in the repo; the
only bundle structure was the installed copy, so it wasn't version-controlled.

## The pattern

- Each bundle is a directory here: `plugins/<plugin-name>/`.
- `plugin-build.json` is the build manifest: plugin metadata plus a `skills` array
  naming the member skills. Member SKILL.md content is NOT duplicated here — it is
  pulled from each skill's canonical top-level repo dir at build time (same
  `is_bundled()` + `SHARED_ROOT_DEPS` fan-out the `.skill` packager uses).
- `README.md` (optional) ships as the bundle's README.
- `tools/build_plugin.py` reads the manifest and produces the `.plugin`.
- `tools/package_skills.py` reads every `plugin-build.json` at import to expose
  `PLUGIN_MEMBERS` / `plugin_of(skill)` — the single source of truth for "is this
  skill plugin-bundled?". The post-commit ledger (`tools/pending_reimport.py`)
  consults it so plugin members are tagged with a plugin-rebuild remedy instead of
  the standalone Save-skill remedy.

## Build

```
python tools/build_plugin.py <plugin-name> <outputs-dir> [--bump patch|minor|major]
```

The builder writes the `.plugin` zip entirely in memory with forward-slash entries
(never PowerShell `Compress-Archive`, which writes backslash entries the importer
rejects). In-memory assembly is also deliberate: a nested on-disk copy under the
deep Cowork session outputs path blows past the Windows MAX_PATH (260-char) limit
(`WinError 206`), so the builder never materializes the tree on disk.
