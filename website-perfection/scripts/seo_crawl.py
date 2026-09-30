#!/usr/bin/env python3
"""seo_crawl.py -- read-only SEO crawl of the live oxfordra.net sitemap (stdlib only).

Checks every <loc> in sitemap.xml against the SEO invariants in SKILL.md section 4.D,
then the domain-level files and redirects. It only issues GET/HEAD requests and never
writes to the site, so invariant 2 (no edit/deploy) is not engaged.

Why it parses HTML itself: fetching a page through a summarising web-fetch tool misreported
"no structured data" and "title not visible" on a page that has both (2026-09-30). Only
raw HTML is evidence for head-tag checks.

Usage:
  python seo_crawl.py                      # report to stdout (markdown)
  python seo_crawl.py --json out.json      # also dump per-page data
  python seo_crawl.py --base https://oxfordra.net --max-pages 60 --max-links 400
Exit: 0 = crawl completed (findings are advisory), 2 = sitemap unreachable.
"""
import argparse, collections, json, re, sys, time, urllib.error, urllib.parse, urllib.request
from html.parser import HTMLParser

UA = {"User-Agent": "ORA-seo-crawl/1.0 (read-only)"}
MAX_BYTES = 3_000_000
BRAND = "Oxford Realty Advisors"


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def fetch(url, method="GET", retries=3):
    """(status, headers, body). At most 3 attempts with backoff; status 0 on failure."""
    last = (0, {}, "")
    for i in range(retries):
        req = urllib.request.Request(url, headers=UA, method=method)
        try:
            r = _opener.open(req, timeout=25)
            body = r.read(MAX_BYTES).decode("utf-8", "replace") if method == "GET" else ""
            return r.status, {k.lower(): v for k, v in r.headers.items()}, body
        except urllib.error.HTTPError as e:
            body = e.read(MAX_BYTES).decode("utf-8", "replace") if method == "GET" else ""
            return e.code, {k.lower(): v for k, v in e.headers.items()}, body
        except Exception as e:  # network/timeouts: back off and retry
            last = (0, {}, str(e))
            time.sleep(1.5 * (i + 1))
    return last


class Page(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""; self.in_title = False; self.in_body = False; self.title_done = False
        self.meta = {}; self.links = []; self.h1 = []; self.h2 = 0; self.h3 = 0
        self.cur = None; self.buf = ""; self.imgs = []; self.ld = []; self.in_ld = False
        self.ldbuf = ""; self.lang = None; self.text = []; self.skip = 0; self.hrefs = []
        self.scripts = []

    def handle_starttag(self, tag, at):
        a = dict(at)
        if tag == "html": self.lang = a.get("lang")
        if tag == "body": self.in_body = True
        # only a title before <body> counts (the optional <head> tag may be omitted in HTML5):
        # inline SVG <title> elements in the body would otherwise be appended to it
        # (false 207-char title on /markets/)
        if tag == "title" and not self.in_body and not self.title_done: self.in_title = True
        if tag == "meta":
            k = a.get("name") or a.get("property") or a.get("http-equiv")
            if k: self.meta[k.lower()] = a.get("content", "")
        if tag == "link": self.links.append(a)
        if tag in ("h1", "h2", "h3"): self.cur = tag; self.buf = ""
        if tag == "img": self.imgs.append(a)
        if tag == "a" and a.get("href"): self.hrefs.append(a["href"])
        if tag == "script":
            if a.get("type") == "application/ld+json": self.in_ld = True; self.ldbuf = ""
            elif a.get("src"): self.scripts.append(a["src"])
            self.skip += 1
        if tag == "style": self.skip += 1

    def handle_endtag(self, tag):
        if tag == "title" and self.in_title: self.in_title = False; self.title_done = True
        if tag == self.cur:
            if tag == "h1": self.h1.append(self.buf.strip())
            elif tag == "h2": self.h2 += 1
            else: self.h3 += 1
            self.cur = None
        if tag == "script":
            if self.in_ld: self.ld.append(self.ldbuf); self.in_ld = False
            self.skip = max(0, self.skip - 1)  # a stray close tag must not drop later text
        if tag == "style": self.skip = max(0, self.skip - 1)

    def handle_data(self, d):
        if self.in_title: self.title += d
        if self.in_ld: self.ldbuf += d
        if self.cur: self.buf += d
        if not self.skip: self.text.append(d)


def analyse(url):
    st, hdr, body = fetch(url)
    p = Page(); p.feed(body)
    canon = [l.get("href") for l in p.links if "canonical" in (l.get("rel") or "").lower().split()]
    types, bad_ld = [], 0
    for blob in p.ld:
        try:
            j = json.loads(blob)
            for n in (j if isinstance(j, list) else j.get("@graph", [j])):
                types.append(n.get("@type"))
        except Exception:
            bad_ld += 1
    imgs = p.imgs
    return dict(
        url=url, status=st, title=p.title.strip(), desc=p.meta.get("description", ""),
        canonical=canon, robots=p.meta.get("robots"), lang=p.lang,
        viewport="viewport" in p.meta, og=sorted(k for k in p.meta if k.startswith("og:")),
        tw=sorted(k for k in p.meta if k.startswith("twitter:")), ld_types=types, ld_bad=bad_ld,
        h1=p.h1, h2=p.h2, n_img=len(imgs), no_alt=sum(1 for i in imgs if "alt" not in i),
        no_dim=sum(1 for i in imgs if not (i.get("width") and i.get("height"))),
        words=len(re.findall(r"\w+", " ".join(p.text))), hrefs=p.hrefs, scripts=p.scripts,
        xrobots=hdr.get("x-robots-tag"), cache=hdr.get("cache-control"))


def findings_for(pg, sitemap_urls):
    f = []
    u = pg["url"]; path = urllib.parse.urlparse(u).path or "/"
    t, d = pg["title"], pg["desc"]
    if pg["status"] != 200: f.append(("HIGH", f"status {pg['status']}"))
    if not t: f.append(("HIGH", "missing <title>"))
    elif len(t) > 60: f.append(("MED", f"title {len(t)} chars (>60)"))
    elif path != "/" and not t.endswith(f"| {BRAND}"): f.append(("LOW", f"title lacks '| {BRAND}' suffix"))
    if not (140 <= len(d) <= 160): f.append(("MED", f"meta description {len(d)} chars (want 140-160)"))
    if pg["canonical"] != [u]: f.append(("HIGH", f"canonical {pg['canonical']} != sitemap loc"))
    if len(pg["h1"]) != 1: f.append(("MED", f"{len(pg['h1'])} H1 tags"))
    if not pg["robots"]: f.append(("LOW", "no robots meta"))
    elif "noindex" in pg["robots"].lower(): f.append(("HIGH", "noindex page is listed in sitemap"))
    if not all(k in pg["og"] for k in ("og:title", "og:description", "og:image", "og:url", "og:type")):
        f.append(("MED", "incomplete Open Graph set"))
    if len(pg["tw"]) < 3: f.append(("LOW", "thin Twitter card tags"))
    if pg["no_alt"]: f.append(("MED", f"{pg['no_alt']} images missing alt attribute"))
    if pg["no_dim"]: f.append(("MED", f"{pg['no_dim']} images missing width/height (CLS)"))
    if pg["ld_bad"]: f.append(("HIGH", f"{pg['ld_bad']} invalid JSON-LD block(s)"))
    if not pg["ld_types"]: f.append(("LOW", "no JSON-LD"))
    if not pg["lang"]: f.append(("LOW", "no <html lang>"))
    if not pg["viewport"]: f.append(("MED", "no viewport meta"))
    if pg["words"] < 300: f.append(("LOW", f"thin content ({pg['words']} words)"))
    return f


_TAG = r"<(?:\w+:)?%s>\s*(?:<!\[CDATA\[)?\s*(.*?)\s*(?:\]\]>)?\s*</(?:\w+:)?%s>"


def parse_sitemap(xml):
    """[(loc, lastmod|None)] from <url> blocks; tolerates CDATA, prefixed tags, any child order."""
    out = []
    for blk in re.findall(r"<(?:\w+:)?url>(.*?)</(?:\w+:)?url>", xml, re.S):
        loc = re.search(_TAG % ("loc", "loc"), blk, re.S)
        lm = re.search(_TAG % ("lastmod", "lastmod"), blk, re.S)
        if loc:
            out.append((loc.group(1), lm.group(1) if lm else None))
    return out


def same_host(url, base):
    """True only for the exact scheme+host of base (a text-prefix test also passes
    oxfordra.net.evil.example and oxfordra.net@evil.example)."""
    u, b = urllib.parse.urlparse(url), urllib.parse.urlparse(base)
    return u.scheme in ("http", "https") and u.hostname == b.hostname and u.port == b.port


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="https://oxfordra.net")
    ap.add_argument("--json"); ap.add_argument("--max-pages", type=int, default=60)
    ap.add_argument("--max-links", type=int, default=400)
    a = ap.parse_args(); base = a.base.rstrip("/")

    st, _, sm = fetch(base + "/sitemap.xml")
    if st != 200:
        print(f"sitemap.xml unreachable (status {st})"); return 2
    entries = [(u, lm) for u, lm in parse_sitemap(sm) if same_host(u, base)][: a.max_pages]
    if not entries:
        print("sitemap.xml has no parseable same-host <loc> entries; refusing to report a clean crawl")
        return 2
    urls = [u for u, _ in entries]
    lastmod = {u: lm for u, lm in entries if lm}
    pages = [analyse(u) for u in urls]

    out = [f"# SEO crawl: {base}  ({time.strftime('%Y-%m-%d')}, {len(pages)} sitemap pages)\n"]
    rows, sev = [], collections.Counter()
    for pg in pages:
        for s, m in findings_for(pg, urls):
            rows.append((s, pg["url"].replace(base, "") or "/", m)); sev[s] += 1
    dup_t = [t for t, c in collections.Counter(p["title"] for p in pages).items() if c > 1]
    dup_d = [t for t, c in collections.Counter(p["desc"] for p in pages).items() if c > 1]
    if dup_t: rows.append(("HIGH", "*", f"duplicate titles: {dup_t}")); sev["HIGH"] += 1
    if dup_d: rows.append(("HIGH", "*", f"duplicate descriptions: {dup_d[:3]}")); sev["HIGH"] += 1

    # domain-level
    dom = []
    for label, path in (("robots.txt", "/robots.txt"), ("llms.txt", "/llms.txt"),
                        ("manifest.json", "/manifest.json"), ("favicon.ico", "/favicon.ico")):
        s, _, body = fetch(base + path)
        dom.append(f"{label}: {s}")
        if path == "/robots.txt" and "Sitemap:" not in body: rows.append(("MED", "/robots.txt", "no Sitemap: line"))
    s, _, _ = fetch(base + "/zz-not-a-page-seo-crawl")
    dom.append(f"unknown path: {s}" + ("" if s == 404 else "  <-- soft 404"))
    if s != 404: rows.append(("HIGH", "/zz-not-a-page", f"unknown path returns {s}, not 404"))
    host = urllib.parse.urlparse(base).netloc
    for probe in (f"http://{host}/", f"https://www.{host}/", f"http://www.{host}/"):
        s, h, _ = fetch(probe, "HEAD")
        dom.append(f"{probe} -> {s} {h.get('location', '')}")
        if s != 301: rows.append(("HIGH", probe, f"expected 301, got {s}"))

    # stale lastmod: a hub older than its own children
    for u, lm in lastmod.items():
        kids = [v for k, v in lastmod.items() if k != u and k.startswith(u.rstrip("/") + "/")]
        if kids and lm[:10] < max(kids)[:10]:  # compare dates only; a datetime vs date same-day is not stale
            rows.append(("LOW", u.replace(base, ""), f"lastmod {lm} older than children ({max(kids)})"))

    # internal links: bounded HEAD sweep, plus linked-but-not-in-sitemap
    sm_norm = {u.rstrip("/") for u in urls}; seen = {}
    for pg in pages:
        for h in pg["hrefs"]:
            if h.startswith(("mailto:", "tel:", "#", "javascript:")): continue
            full = urllib.parse.urljoin(pg["url"], h).split("#")[0]
            if same_host(full, base): seen.setdefault(full, pg["url"])
    bad, orphans = [], []
    for full, src in list(seen.items())[: a.max_links]:
        if re.search(r"\.(png|jpe?g|avif|webp|svg|css|js|woff2?|pdf|ico|xml|txt|json)(\?|$)", full): continue
        s, h, _ = fetch(full, "HEAD")
        if s >= 400 or s == 0: bad.append((full, s, src))
        if full.rstrip("/") not in sm_norm: orphans.append((full, s))
    for full, s, src in bad: rows.append(("HIGH", full.replace(base, ""), f"broken internal link ({s}) from {src.replace(base, '')}"))
    for full, s in orphans:
        if s and s < 400: rows.append(("LOW", full.replace(base, ""), "linked page not in sitemap (confirm noindex is intended)"))

    order = {"HIGH": 0, "MED": 1, "LOW": 2}
    sev = collections.Counter(r[0] for r in rows)  # tally after every check has added rows
    out.append(f"Findings: HIGH {sev['HIGH']} / MED {sev['MED']} / LOW {sev['LOW']}\n")
    out.append("| Sev | Page | Finding |\n|---|---|---|")
    for s, p, m in sorted(rows, key=lambda r: (order[r[0]], r[1])): out.append(f"| {s} | {p} | {m} |")
    if not rows: out.append("| - | - | no findings |")
    out.append("\n## Domain checks\n" + "\n".join(f"- {d}" for d in dom))
    out.append(f"\n## Per-page\n| Page | T | D | words | schema |\n|---|---|---|---|---|")
    for pg in pages:
        out.append(f"| {pg['url'].replace(base, '') or '/'} | {len(pg['title'])} | {len(pg['desc'])} | {pg['words']} | {','.join(str(x) for x in pg['ld_types'])} |")
    out.append("\nNot covered: Core Web Vitals, backlinks, keyword demand, AI visibility, indexing status, "
               "client-rendered content (listings.js/chat.js). Those need PageSpeed, GSC/Bing/AWT exports, "
               "and a browser.")
    print("\n".join(out))
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump([{k: v for k, v in p.items() if k != "hrefs"} for p in pages], fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
