# ora-operations-extensions — RETIRED 2026-08-05

> **This bundle is retired.** It was archived here during the 2026-08-05
> automation audit, on Gabriel's explicit decision. Nothing was deleted — this
> directory is the intact manifest, preserved as the audit trail. The original
> README follows the retirement notes below.

## If you were mid-work on this bundle: read this

Uncommitted work existed in the working tree when this was archived — a
`plugin-build.json` version bump **v0.1.5 → v0.1.6**, plus an untracked scratch
script `_check_plugin.py` calling `plugin_of('deal-retirement')`.

**That bump is preserved.** It is in the `plugin-build.json` next to this file,
exactly as written — carried through the `git mv` rather than discarded. The
scratch script was left in the repo root, untouched.

Gabriel authorized proceeding over concurrent sessions' work in that turn. Edits
were kept strictly additive; no tree was `checkout`/`reset`/`stash`ed.

## What actually changed — less than it looks

The bundle was a **manifest-only overlay**. All seven member skills already lived
as standalone directories at the repo root, and still do. There were never
duplicate copies under `plugins/`. Retiring the manifest removes no skill; it
changes only how they reach the runtime — `plugin_of()` now returns `None` for
every skill, so they install standalone via Save-skill rather than as members.

Six of the seven are disabled at the consumer via `~/.claude/settings.json`
`skillOverrides`. **`submarket-spatial-analysis` stays ACTIVE** — it is named in
CLAUDE.md's market-research tie-break.

## The namespace trap, if you re-enable any of these

The six were first disabled under `ora-operations-extensions:<skill>` keys. Once
the bundle is retired those keys stop matching, which would have **silently
re-enabled all six**. Both namespaces (`ora-operations-extensions:` AND
`anthropic-skills:`) are therefore keyed off in settings.json. Do not "tidy up"
the apparently-redundant keys without re-verifying which namespace the platform
actually resolves for a given skill.

## Why it was retired

`.claude.json` `pluginUsage` recorded a lifetime invocation count of **1** for
this bundle (last used 2026-06-13), against 128 for the 60-skill
`anthropic-skills` catalog and 1,240 for `superpowers`.

Caveat worth carrying: that counter measures **invocations of the bundle as a
plugin**, not whether member skills are wired into live workflows. Three of seven
demonstrably were — `investor-relations` and `submarket-spatial-analysis` were
named in CLAUDE.md, and `deal-retirement` had been edited two days prior. The
original instruction was to retire all seven; it was narrowed once that surfaced.
`investor-relations` and `deal-retirement` were retired anyway as an informed
call, and CLAUDE.md line 38's `investor-relations` routing reference was removed
in the same change.

## Restoring

`git mv _archive/plugins/ora-operations-extensions plugins/` restores the bundle —
`load_plugin_manifests()` globs `plugins/*/plugin-build.json`, so `plugin_of()`
picks it up immediately. Then remove the matching `skillOverrides` entries.

Tests were updated to SURVIVE this retirement rather than depend on it:
`tools/test_build_plugin.py` builds a synthetic fixture plugin
(`make_fixture_plugin`), so the 8-vs-7 membership, outdir-collision and
validate-before-bump regression coverage stays live with no bundle in the repo.

Full context: `~/.claude/projects/.../memory/event_log.md`, 2026-08-05.

---

# (original README, retained verbatim)

# ORA Operations Extensions

Seven institutional skills extending Oxford Realty Advisors' Cowork environment. Each skill's canonical source is its top-level directory in the `ora-skills` repo; this plugin bundles them for Cowork install. The bundle is built from `plugins/ora-operations-extensions/plugin-build.json` by `tools/build_plugin.py` — never hand-edit the installed copy.

## Skills

1. **annual-cycle** — twin to monthly-close; Nov budget kickoff through April K-1 close
2. **capex-budgeting** — multi-year capital plans, reserve studies, refi reserve negotiation
3. **cash-position-monitor** — multi-entity cash consolidation, distribution headroom
4. **deal-retirement** — lifecycle cleanup on close or kill
5. **investor-relations** — capital calls, distribution notices, K-1 cover letters, LP letters
6. **submarket-spatial-analysis** — location scoring, drive-time, intermodal proximity, last-mile
7. **vendor-management** — RFP, vendor scoring, COI/W-9, concentration audits

> `debt-management` is a standalone ORA skill, NOT bundled here. The pre-2026-07-16 manifest and README both wrongly listed it as an eighth bundled skill; corrected in v0.1.2.

## Build & install

Rebuild the `.plugin` after any member skill's SKILL.md changes:

```
python tools/build_plugin.py ora-operations-extensions <outputs-dir> [--bump patch|minor|major]
```

Install in Cowork by accepting the presented `.plugin` (updates the loaded plugin copies in place). A standalone Save-skill `.skill` is the WRONG target for these skills — it installs a shadow copy and leaves the plugin's loaded copies stale.
