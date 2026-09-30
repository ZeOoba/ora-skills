---
name: website-perfection
description: "Use when the user mentions: PageSpeed, Lighthouse, Core Web Vitals, website fixes, site performance, image optimization, SEO audit, meta tags, structured data, JSON-LD, sitemap, redirects, soft 404, duplicate URLs, analytics installation, GA4, LinkedIn pixel, AI search visibility, llms.txt, accessibility, WCAG, Netlify headers, CSP, CLS, LCP, TBT, oxfordra.net improvements, or any task related to auditing, optimizing, or improving the Oxford Realty Advisors website."
---

# Website Perfection — Oxford Realty Advisors (v1.2)

**v1.2 (2026-09-30):** Added §4a Phase 0 (`scripts/seo_crawl.py`, a read-only live crawl against the §4.D invariants; `scripts/psi_check.py`, PageSpeed Insights via a keyed API; plus the monthly off-site data pull from GSC, Bing Webmaster Tools and Ahrefs Webmaster Tools) and a common-mistakes row on summarising fetch tools. Replaces evaluating third-party SEO plugins: SearchFit SEO and Manifold were SUPERSEDED by this skill plus the script. No financial or governor constants involved.
**v1.1 (2026-09-13):** Rebased on the live site after the 2026-09-13 SEO audit (website-canonical PR #77). Removed stale v1.0 premises: the www host (the site is non-www), Indianapolis as a market (a false claim, removed from the site in PR #56), placeholder GA4/LinkedIn IDs, the "Score Your Deal" CTA, Google Fonts guidance (fonts are self-hosted), and a sample CSP that would have broken reCAPTCHA, the map tiles and SharePoint uploads. Added: repo/build/verify pipeline, the local vs. deploy-preview verification split, a live-state baseline, an AI-search section, and SEO invariants pinned by `tests/site/seo.test.mjs`. No financial or governor constants involved.
**v1.0:** initial PageSpeed-100 audit prompt.

Senior full-stack / performance engineer on oxfordra.net: a static Netlify site (vanilla HTML/CSS/JS plus Netlify Functions and an edge chat function). Design system is immutable: DM Sans (body/UI) + EB Garamond (display), Oxford Navy `#1B2A4A`, Oxford Gold `#C9A96E` (use `--gold-accessible` `#806339` for gold text on light grounds), Parchment `#F5F3EF`. Goal: 100 on Lighthouse Performance / Accessibility / Best Practices / SEO (mobile and desktop) with zero regressions.

---

## 0. Guardrails (read first)

- **Invariant 2:** auditing (reading repo + live site) is free. **Editing** `website-canonical` requires Gabriel's in-turn go-ahead. **Production deploy** requires a separate per-deploy confirmation, even after a PR merges; merging is not deploying. Deploys route through `deploy-site` / `/ship`. Run the `site-qc-reviewer` agent before any deploy.
- **Confidential deals:** never put an active confidential deal on any page (roster in `~/.claude/hooks/confidential-terms.json`).
- **Never fabricate firm figures** (SF, building counts, tenants, markets, close speed). Copy on the site is the claim of record for the site. Changing a claim is Gabriel's decision: ask via `AskUserQuestion` (recommended option first), in audits and ad-hoc requests alike, and don't normalize silently.
- **Content/IA changes** (new sections, headline copy, navigation, forms, portfolio) are flagged and confirmed before editing.

## 1. Where things live

| Thing | Location / fact |
|---|---|
| Repo (canonical) | `C:/Users/Owner/website-canonical` → `github.com/ZeOoba/Website`. `oxford-site` is a no-git deploy copy, not a source. |
| Shared checkout | Work in a git worktree on a branch, then open a PR. Never edit `main` directly. |
| Build | `npm run build` = `build-kb.mjs` (chat knowledge base from pages + `scripts/meta.md`) + `build-dist.mjs` (publishes an **allowlist** into `dist/`; a new root file must be classified or the build fails). |
| Verify (CI gate) | `npm run verify`: build → JSON-LD validation → unit → site tests (`recaptcha-sitekey`, `csp-smoke`, **`seo.test.mjs`**) → shim → functions. |
| Headers / CSP | `_headers` is canonical. Never paste a template CSP; add origins one at a time and prove them with `csp-smoke.test.mjs`. |
| Redirects | `_redirects` is canonical (non-www 301, legacy Squarespace/Wix paths, `.html` → clean-URL `301!`, `/404` → `404!`, catch-all `/* /404.html 404` **last**). |
| Chat facts | `scripts/meta.md` feeds the chat assistant. A site claim change must also change it, or the bot contradicts the page. |
| Deploy previews | Every PR builds `deploy-preview-<PR>--snazzy-frangipane-de3841.netlify.app`. |

## 2. Verification split (where each check is actually valid)

| Check | Local `serve-dist` | Netlify deploy preview | Live site |
|---|---|---|---|
| Page content, layout, console errors | ✅ | ✅ | ✅ |
| `_headers` / CSP | ✅ (serve-dist applies `_headers`) | ✅ | ✅ |
| `_redirects`, status codes (301/404), redirect loops | ❌ **not emulated** | ✅ required | ✅ after deploy |
| Lighthouse / PageSpeed field data | ❌ | lab only | ✅ |

**Local preview:** `npm run build` in the worktree, then `node scripts/serve-dist.mjs --port=8788 --root=<abs>/dist` (use `--port=N`, with the equals sign). The Browser pane's `preview_start` reads `.claude/launch.json` from the **main** checkout, not the worktree. Use its `worktree` config and retarget `--root` to the active worktree first. A bare `python -m http.server` is **not** a valid preview: it skips `_headers` and pretty URLs.

**Redirect proof on a preview:** `curl -s -o /dev/null -w "%{http_code} -> %{redirect_url}"` for each `/page.html`, `/404` and an unknown path, plus `curl -sL --max-redirs 5` on one `.html` path to prove there is no loop.

## 3. Live-state baseline (verified 2026-09-13; re-verify before relying on it)

- Host `https://oxfordra.net` (www and http both 301 to it). HSTS preload is on.
- Markets on the site: **Maryland** and **Columbus, OH** (core, each with a market page); **Kansas City, MO** is a one-building holding (portfolio + markets hub note, no market page by Gabriel's decision). No Indianapolis.
- Close-speed claim: **30–45 days** everywhere (pinned by `seo.test.mjs`).
- GA4 `G-YDSX0RW5HC` is installed with a deferred loader (first interaction / page-hide / 3s). LinkedIn Insight Tag is **not** installed; its CSP origins are already allowed. Ask Gabriel for the Partner ID, then load it inside the existing deferred `loadAnalytics()` block on every page (never as a render-blocking head script).
- Fonts are self-hosted `/fonts/*.woff2` (`font-src 'self'`), preloaded via `Link` headers; no Google Fonts.
- Primary CTA: "Submit Your Deal" → `/for-brokers#broker-network` (reCAPTCHA v2-gated upload).
- Organization JSON-LD on home and about; `images/oxford-logo-512.png` (navy on white). A white or sub-112px logo fails Google's logo requirements.
- `sitemap.xml` (19 URLs), `robots.txt` (allow all + sitemap), `llms.txt`, custom `404.html`, `manifest.json` and the favicon suite all exist.
- Internal Netlify Forms shells (`*-form.html`) are published and noindexed by design.

## 4. Audit dimensions

Catalog pages from `sitemap.xml` plus repo HTML, excluding `dist/`, `node_modules/` and `.netlify/`. Findings are ranked by impact; each gets evidence (file:line or a curl result) and a proposed fix.

**A. Performance:** LCP image preloaded + `fetchpriority="high"`; AVIF/WebP `<picture>` with explicit `width`/`height`; below-fold `loading="lazy"`; critical CSS inline with async `styles.css` (cache-busted `?v=N`, and bump N on change); no render-blocking JS; immutable caching on hashed/static assets. Targets: LCP ≤ 2.5s, CLS 0, INP ≤ 200ms, TBT ≤ 200ms.

**B. Accessibility:** one skip link; landmarks; one H1 and no skipped heading levels; alt text on every `<img>` (decorative → `alt=""`); gold text on light grounds uses `--gold-accessible`; visible `:focus-visible`; labelled form controls; keyboard-operable accordions and sliders.

**C. Best practices:** no console errors; HTTPS only; CSP holds with no violations (`csp-smoke`); SRI on third-party scripts.

**D. SEO invariants** (the ones marked 🔒 are enforced by `tests/site/seo.test.mjs`; extend that test when adding one):
- 🔒 Every sitemap page's `/x.html` path has a `301!` to the clean URL, placed before the catch-all (Netlify otherwise serves both as 200).
- 🔒 `/404` returns a real 404; `404.html` has no canonical.
- 🔒 Indexable pages have a 140–160 character meta description; titles follow `Page | Oxford Realty Advisors` (≤ 60 chars).
- 🔒 Organization `logo` is a non-white PNG ≥ 112×112.
- 🔒 Owner-guide `Article` JSON-LD has ISO `datePublished`/`dateModified` (sourced from `git log --follow`, never invented).
- 🔒 Home, for-brokers and market pages link ≥ 2 owner guides from `<main>` (not just nav/footer).
- 🔒 No page contradicts the canonical close-speed claim.
- Canonical + `og:url` match the sitemap `<loc>` exactly (trailing slash for directory indexes); `og:*` and `twitter:*` on every indexable page; `robots` meta on every page.
- `sitemap.xml` `<lastmod>` bumped for pages whose content changed; noindex pages stay out of it.
- Claims agree across meta description, visible copy, FAQ JSON-LD and `scripts/meta.md`.

**E. AI search / answer engines:**
- Keep `llms.txt` current with the claims above; it's what LLM crawlers read first.
- FAQPage JSON-LD **no longer earns Google FAQ rich results for commercial sites** (Google Search Central, "Changes to HowTo and FAQ rich results," 2023-08-08). Keep existing blocks for AI engines and answer extraction, but never pitch new FAQ markup as a SERP gain.
- Consistent entity facts (name, address, phone, `sameAs`) across Organization JSON-LD, footer and `llms.txt` strengthen entity resolution.

**F. Visual / content:** check at 375 / 768 / 1024 / 1440 px with no horizontal scroll (fix the root cause; `overflow-x:hidden` is not a fix). New sections reuse existing tokens and classes. Portfolio/track-record figures must match the source of record, never placeholders.

**G. Infrastructure:** `_headers` security set (HSTS, CSP, nosniff, Referrer-Policy, Permissions-Policy); legacy-path 301s; branded 404; favicon suite + manifest; analytics per §3.

## 4a. Phase 0: live crawl and off-site data (run before §5; read-only)

**Live crawl.** `python website-perfection/scripts/seo_crawl.py [--json out.json]` fetches every `sitemap.xml` URL as raw HTML and checks the §4.D invariants (title/description length, canonical = sitemap loc, one H1, OG/Twitter, alt + dimensions, JSON-LD validity, noindex-in-sitemap, stale `lastmod`), then `robots.txt`/`llms.txt`/`manifest.json`/favicon, the unknown-path 404, the http/www 301s, and a bounded internal-link HEAD sweep. Stdlib only, GET/HEAD only, 3 attempts with backoff per request, bodies capped at 3 MB. Baseline 2026-09-30: 0 HIGH, 0 MED, 3 LOW (`/contact` thin, `/resources/` lastmod, `/tenant-application` linked but noindexed by design). A regression from that baseline is a finding. It does **not** measure Core Web Vitals, backlinks, keyword demand, AI visibility, indexing, or client-rendered content.

**Core Web Vitals.** `python website-perfection/scripts/psi_check.py` runs PageSpeed Insights (Lighthouse scores, lab metrics, field data, top opportunities) on the home page and two key pages, mobile and desktop. It needs `PSI_API_KEY` as a user environment variable (a Google Cloud API key restricted to the PageSpeed Insights API; Gabriel creates it, it is never pasted into chat or stored in the repo). The keyless API and the pagespeed.web.dev UI both failed on 2026-09-30 (HTTP 429 / "failed to retrieve the LHR"), so keyless is not a usable default (`--allow-keyless` exists but expect 429). Max 3 attempts per call; a 4xx is recorded as a blocker, not retried. Verify on the first keyed run that the "opportunity" list is populated; newer Lighthouse may report insight audits instead, in which case the "below 90" list carries the findings.

**Off-site data (monthly, manual, free).** Domain property in Google Search Console (verified by DNS TXT on Netlify DNS, never a meta tag or file, which would need a deploy), imported into Bing Webmaster Tools, plus Ahrefs Webmaster Tools on the same verified domain. Gabriel exports the CSVs (GSC queries/pages, AWT backlinks + Site Audit, Bing keyword research); the session reads them and returns one ranked table of keyword gaps, backlink gaps and audit issues, each with a proposed site change. GSC is the ranking and demand source; web-search spot checks are signals only, never rank evidence. No third-party OAuth intermediaries (hosted GSC MCPs) and no paid data MCPs.

**Off-site consistency.** Directory and listing profiles (LoopNet, Realty.com, Nestfully, Crunchbase, LinkedIn) must match the site's claims of record (SF, markets, tenants, phone). A mismatch is reported to Gabriel; fixing a profile needs no deploy, but which figure is right is his call (§0).

**Kill test.** If two consecutive monthly pulls yield fewer than two actionable site changes, drop the monthly routine and keep only the crawl.

## 5. Fix workflow

1. **Audit read-only** (repo + live curl). Present ranked findings; ask Gabriel about any claim or content decision with `AskUserQuestion` (recommended option first).
2. **Worktree + branch** off `origin/main`. Write or extend `tests/site/seo.test.mjs` first and watch it fail.
3. Edit with the Edit tool; preserve line endings (the repo stores LF, and some working copies are CRLF).
4. `npm run verify` must exit 0. Then run the local visual check (§2) at desktop and mobile widths.
5. Commit explicit paths → PR → wait for CI and the Netlify preview → run the **redirect/status proof on the preview**.
6. Report with evidence. Deploy only on Gabriel's per-deploy confirmation, then verify the **served** asset on oxfordra.net before calling it done.

## 6. Common mistakes (each has happened)

| Mistake | Fix |
|---|---|
| Declaring `_redirects` fixes verified from a local server | Local servers don't run `_redirects`; prove it on the deploy preview. |
| Pasting a "standard" CSP into `_headers` | It drops live origins (reCAPTCHA, unpkg, OSM tiles, SharePoint, Netlify RUM). Edit incrementally and run `csp-smoke`. |
| Reporting a copy inconsistency as meta-only | Grep visible copy, JSON-LD, `llms.txt` and `scripts/meta.md` too before scoping the fix. |
| Normalizing a firm claim (markets, close speed, counts) without asking | Claims are Gabriel's call; ask, then pin the answer in `seo.test.mjs`. |
| Rewriting a file with Python `read_text`/`write_text` | That silently converts CRLF→LF; use the Edit tool or byte-level I/O. |
| Reading head tags, schema or titles through a summarising web-fetch tool | It reported "no structured data" and "title not visible" on a page with both. Use raw HTML (`seo_crawl.py` or `curl`). |
| Treating a merged PR as live | Verify the served HTML/headers on oxfordra.net after the confirmed deploy. |
