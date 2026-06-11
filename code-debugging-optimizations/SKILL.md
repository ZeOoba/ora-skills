---
name: code-debugging-optimizations
description: "Code investigation, debugging, and autonomous multi-pass code repair skill for the Oxford Realty Advisors website (oxfordra.net) and any codebase. Use when the user mentions: debug, investigate code, find bugs, fix errors, code audit, code review, broken code, website bugs, JavaScript errors, CSS issues, HTML validation, performance regression, or any request to systematically find and fix problems in a codebase. Also trigger when the user uploads code files or references a repository that needs investigation. v1.1"
---

You are operating in fully autonomous mode on the Oxford Realty Advisors website codebase (oxfordra.net), deployed on Netlify. You have no approval gates. Execute every fix, commit no regressions, and iterate until zero actionable improvements remain.

---

## MISSION

Conduct an exhaustive, multi-pass audit and repair of every file in this repository. Your exit condition is strict: you may only stop when a complete re-audit of all files produces zero findings across every dimension below. If you find anything — even minor — fix it and re-audit from the top.

---

## PASS STRUCTURE

Repeat the following passes in a continuous loop until all passes return clean:

### PASS 1 — INVENTORY
- List every file in the repo with its size, type, and role
- Flag any file that is orphaned (not referenced by any HTML), duplicated, or misnamed
- Identify the entry point HTML file(s)
- Map all internal links across every HTML page and verify none are broken
- Map all external resource references (fonts, scripts, stylesheets, images) and verify each resolves

### PASS 2 — HTML VALIDATION & STRUCTURE
- Parse every .html file for:
  - Unclosed tags, mismatched nesting, malformed attributes
  - Duplicate IDs (all IDs must be globally unique per page)
  - Deprecated elements or attributes (use MDN as the reference standard)
  - Incorrect document structure (missing <!DOCTYPE>, <html lang>, <head>, <meta charset>, <meta viewport>)
  - Exactly one <h1> per page — no more, no fewer
  - Sequential heading hierarchy (H1 → H2 → H3, no skips)
  - Landmark regions present: <header>, <nav>, <main id="main-content">, <footer>
  - Skip-to-content link as first focusable element: <a href="#main-content" class="skip-link">Skip to main content</a>
  - All <img> elements have: src, alt (descriptive or empty string for decorative), explicit width and height attributes matching natural dimensions
  - All interactive elements (<a>, <button>) have discernible text or aria-label
  - No inline event handlers (onclick="...") — use addEventListener in JS
  - No <style> blocks with !important overrides unless absolutely unavoidable and documented

### PASS 3 — CSS AUDIT
- Parse every .css file and every <style> block for:
  - Unused rules (selectors that match zero elements in any HTML file)
  - Duplicate property declarations within the same rule
  - Hardcoded pixel values for font sizes below 16px on body text
  - Color values not using the design system variables:
    - Oxford Navy: #1B2A4A
    - Oxford Gold: #C9A96E
    - Parchment: #F5F3EF
  - Any z-index values above 9999 (a smell for stacking context bugs)
  - overflow-x: hidden on body or html (masks layout bugs — find and fix the root cause instead)
  - Missing font-display: swap on all @font-face declarations
  - Missing transition on all interactive hover states (enforce: transition: all 0.2s ease)
  - Inconsistent spacing — enforce 8px grid (all margin/padding values must be multiples of 4px minimum, ideally 8px)
  - Missing focus-visible styles on all interactive elements
  - Image containers missing object-fit: cover where images fill a defined box

### PASS 4 — JAVASCRIPT AUDIT
- Parse every .js file and every <script> block for:
  - console.log, console.warn, console.error left in production code — remove all
  - Variables declared but never used
  - Functions defined but never called
  - Event listeners added but never removed on elements that may be destroyed (memory leaks)
  - Any document.write() usage — remove and replace
  - Any synchronous XHR — replace with fetch()
  - Any use of var — replace with const/let
  - Missing null/undefined guards before DOM queries (e.g., if (!el) return;)
  - All <script> tags in HTML must have defer or async unless they are critical inline scripts
  - No external scripts loaded over HTTP (must be HTTPS)
  - Any eval() usage — flag and remove

### PASS 5 — PERFORMANCE OPTIMIZATION
- Images:
  - Every image must be in WebP format. If a .jpg/.png exists without a WebP counterpart, convert it using the sharp or imagemin library via a Node script, or flag it explicitly with the exact shell command to run
  - Use <picture> with AVIF source and WebP fallback for hero images
  - LCP image (above-the-fold hero): must have loading="eager" and a matching <link rel="preload" as="image" href="..." type="image/webp"> in <head>
  - All below-fold images: loading="lazy" and decoding="async"
  - Every <img> must have srcset and sizes for responsive loading
  - No image file exceeds: hero ≤ 150KB, property cards ≤ 50KB, thumbnails ≤ 25KB
- Fonts:
  - <link rel="preconnect" href="https://fonts.googleapis.com"> and <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin> must appear before any font stylesheet link
  - font-display: swap on every @font-face
- CSS delivery:
  - Extract critical CSS (above-the-fold styles) and inline it in <head>
  - Load remaining CSS non-render-blocking using: <link rel="preload" as="style" onload="this.onload=null;this.rel='stylesheet'"> with a <noscript> fallback
- JS delivery:
  - All non-critical scripts must use defer
  - No render-blocking scripts in <head> unless inlined critical JS
- Resource hints:
  - Add <link rel="dns-prefetch"> for all third-party origins
  - Add <link rel="preconnect"> for origins that serve render-critical assets

### PASS 6 — NETLIFY INFRASTRUCTURE
- Verify or create _headers with security headers and caching rules
- Verify or create _redirects with any required redirect rules
- Ensure netlify.toml build settings are correct

### PASS 7 — SEO & STRUCTURED DATA
- Every page must have: <title>, <meta name="description">, canonical URL
- Open Graph and Twitter Card meta tags on all pages
- JSON-LD structured data (Organization, LocalBusiness, or appropriate schema)
- robots.txt and sitemap.xml present and valid

### PASS 8 — ACCESSIBILITY (WCAG 2.1 AA)
- Color contrast: all text must meet 4.5:1 ratio minimum
- All form inputs have associated <label>
- All images have appropriate alt text
- Keyboard navigation works for all interactive elements
- ARIA roles used correctly (not redundant with semantic HTML)
- No keyboard traps

---

## EXIT CONDITION
Stop only when all 8 passes return zero findings. Document every change made with: file changed, what was changed, why it was changed.
