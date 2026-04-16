---
name: deploy-site
description: Build and deploy the oxfordra.net website to Netlify. Use when making site changes or deploying updates.
user-invocable: true
allowed-tools: Read Glob Grep Edit Write Bash WebFetch mcp__Claude_Preview__preview_start mcp__Claude_Preview__preview_screenshot mcp__a66aaa4a-ffcd-4066-b2af-79c4ce807809__netlify-deploy-services-reader mcp__a66aaa4a-ffcd-4066-b2af-79c4ce807809__netlify-deploy-services-updater
---

## Instructions

Build and deploy the Oxford RA website.

1. Ensure Node.js is on PATH: `export PATH="/c/Program Files/nodejs:$PATH"`
2. Navigate to the oxford-site directory in the Cowork OS folder
3. Run `node build-and-deploy.js --local` to build
4. Verify the build output in the deploy/ directory
5. Run `node build-and-deploy.js --deploy` to push to Netlify (site ID: 95ac0a0f-a84d-4400-b919-b8d7a8526646)
6. Verify the live site at https://oxfordra.net loads correctly
7. Open in Chrome: `start chrome "https://oxfordra.net"`

If deploying after edits, always verify the preview first before pushing to production.
