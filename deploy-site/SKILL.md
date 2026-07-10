---
name: deploy-site
description: Build and deploy the oxfordra.net website to Netlify. Use when making site changes or deploying updates.
user-invocable: true
allowed-tools: Read Glob Grep Edit Write Bash WebFetch mcp__Claude_Preview__preview_start mcp__Claude_Preview__preview_screenshot mcp__a66aaa4a-ffcd-4066-b2af-79c4ce807809__netlify-deploy-services-reader mcp__a66aaa4a-ffcd-4066-b2af-79c4ce807809__netlify-deploy-services-updater
---

## Instructions

Deploy the Oxford RA website (oxfordra.net) from its canonical git repo.
Hard Invariant 2 applies: never build/edit/deploy without explicit per-deploy
permission from Gabriel, given live and naming exactly what will change.

**Canonical source is the git repo, not a build script.** The repo at
`C:\Users\Owner\website-canonical` (git `ZeOoba/Website`, `= OXFORDRA_REPO`)
IS the deploy tree — static HTML/CSS/JS, no build step, `netlify.toml` sets
`publish = "."`. There is no "oxford-site" staging copy to sync from; any
folder named `oxford-site` you find elsewhere (including
`Claude_Workspace/.../oxford-site/build-and-deploy.js`) is a pre-redesign
relic — it fetches the LIVE site and rewrites it with April-era regex
patches (hyphenated nav classes, PNG logo assumptions) that predate the
BEM/inline-SVG redesign now in `website-canonical`. Running it would
corrupt the current site. Do not use it; do not "sync" from it.

1. `git -C "C:/Users/Owner/website-canonical" status` — confirm the tree is
   clean and you know which branch/commit is being shipped.
2. Make/verify the edits on a feature branch, commit, push (push is
   invariant-safe — it doesn't touch the live site or reach prod).
3. Ensure Node.js is on PATH: `export PATH="/c/Program Files/nodejs:$PATH"`.
4. **Draft deploy (default, no gate trip):**
   `npx -y netlify-cli deploy --cwd "C:/Users/Owner/website-canonical" --dir "C:/Users/Owner/website-canonical" --site 95ac0a0f-a84d-4400-b919-b8d7a8526646 --message "<branch@sha>"`
   Returns a `*.netlify.app` preview URL. Verify the change there —
   Claude_Preview or a manual click-through — before going further.
5. **Ask Gabriel explicitly**, naming the branch/commit and exactly what
   will change on prod. Do not proceed without that confirmation, live,
   in this turn.
6. Only after confirmation: create the 60-minute override sentinel at
   `~/.claude/hooks/overrides/allow-website-change` (never self-create this
   in a scheduled/headless session — flag and stop instead), then run the
   same command with `--prod` appended. Delete the sentinel immediately
   after the deploy completes.
7. Post-verify: `curl -s -o /dev/null -w "%{http_code}" https://oxfordra.net/`
   expect 200; spot-check the changed page(s) in Chrome.
8. Append the release to `memory/event_log.md` (target, what shipped,
   verification result).

If the Netlify CLI reports 401/"could not retrieve project", the stored
token is stale — `npx netlify-cli login` (interactive OAuth; the user
approves in a browser tab) re-seeds it. Site ID `95ac0a0f-a84d-4400-b919-b8d7a8526646`
(prod name `snazzy-frangipane-de3841`) is fixed; never create a new site.

Full canon + gotchas: `memory/reference_oxfordra_deploy_canon.md` in the
ORA memory index.
