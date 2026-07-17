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
