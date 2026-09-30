#!/usr/bin/env python3
"""psi_check.py -- PageSpeed Insights (Lighthouse + field data) for oxfordra.net pages.

Read-only: sends public URLs to Google's PageSpeed Insights API and prints a markdown
table. The keyless API shares one daily quota and returns HTTP 429 (seen 2026-09-30), so
this reads a key from the PSI_API_KEY user environment variable. The key is never printed,
logged or written to a file; it is scrubbed from any error text.

Key setup (Gabriel, once): enable "PageSpeed Insights API" in a Google Cloud project,
create an API key restricted to that API only, then in PowerShell:
    setx PSI_API_KEY "<key>"
A running shell does not see a new setx value, so on Windows this falls back to reading
the persisted HKCU\\Environment value.

Usage:
  python psi_check.py                              # home + two key pages, mobile + desktop
  python psi_check.py --pages / /contact --strategies mobile
  python psi_check.py --json out.json
Rule: at most 3 attempts per call with backoff. A 429 or 4xx other than 5xx is recorded
as a blocker and NOT retried into the ground. Exit: 0 = all calls returned data,
1 = at least one call failed, 2 = no key (keyless mode only with --allow-keyless).
"""
import argparse, json, os, sys, time, urllib.error, urllib.parse, urllib.request

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
BASE = "https://oxfordra.net"
DEFAULT_PAGES = ["/", "/sell-your-building", "/resources/selling-industrial-building-without-a-broker"]
CATS = ("performance", "accessibility", "best-practices", "seo")
METRICS = ("first-contentful-paint", "largest-contentful-paint", "total-blocking-time",
           "cumulative-layout-shift", "speed-index")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):  # never follow a redirect with ?key= in the URL
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def norm_page(p):
    """Git Bash (MSYS) rewrites a leading-slash arg into a Windows path: "/" -> "C:/Program Files/Git/"."""
    if p[1:3] == ":/" and "/git/" in p.lower():
        return "/" + p[p.lower().index("/git/") + 5:]
    return p


def get_key():
    k = os.environ.get("PSI_API_KEY")
    if k:
        return k.strip()
    if sys.platform == "win32":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as h:
                return winreg.QueryValueEx(h, "PSI_API_KEY")[0].strip()
        except OSError:
            return None
    return None


def scrub(text, key):
    return text.replace(key, "<key>") if key else text


def call(url, strategy, key):
    params = [("url", url), ("strategy", strategy)] + [("category", c) for c in CATS]
    if key:
        params.append(("key", key))
    err = None
    for i in range(3):
        try:
            with _opener.open(API + "?" + urllib.parse.urlencode(params), timeout=120) as r:
                return json.loads(r.read(8_000_000))
        except urllib.error.HTTPError as e:
            try:
                body = e.read(4000).decode("utf-8", "replace")
            except Exception:
                body = ""
            # scrub the whole body BEFORE truncating: slicing first can leave a key fragment
            # order matters: scrub whole body -> slice -> collapse whitespace. Collapsing
            # BEFORE the slice pulls a key fragment (cut by the 4000-byte read cap) into view.
            err = " ".join(scrub(f"HTTP {e.code}: {body}", key)[:200].split())
            if e.code < 500:  # quota/auth/bad request will not fix itself by retrying
                break
        except Exception as e:
            err = " ".join(scrub(str(e), key)[:200].split())
        time.sleep(8 * (i + 1))
    return {"_error": err}


def summarise(d):
    lh = d["lighthouseResult"]; a = lh["audits"]
    # Lighthouse returns score null for a category/audit that errored (e.g. NO_FCP): keep the
    # row, mark it n/a, never crash the whole run
    cats = {k: (round(v["score"] * 100) if v.get("score") is not None else "n/a")
            for k, v in lh["categories"].items()}
    m = {k: (a[k].get("displayValue") or "n/a") for k in METRICS if k in a}
    opps = sorted(((v.get("details", {}).get("overallSavingsMs", 0), k, v.get("title"))
                   for k, v in a.items() if v.get("details", {}).get("type") == "opportunity"
                   and v.get("details", {}).get("overallSavingsMs", 0) > 100), reverse=True)[:5]
    fails = [(k, v.get("title")) for k, v in a.items()
             if v.get("score") is not None and v["score"] < 0.9
             and v.get("scoreDisplayMode") in ("numeric", "binary") and k not in dict((o[1], 0) for o in opps)][:8]
    le = d.get("loadingExperience", {})
    field = {k: v.get("category") for k, v in le.get("metrics", {}).items()}
    return dict(cats=cats, metrics=m, opportunities=opps, other_failing=fails,
                field_overall=le.get("overall_category"), field=field)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", nargs="+", default=DEFAULT_PAGES)
    ap.add_argument("--strategies", nargs="+", default=["mobile", "desktop"])
    ap.add_argument("--json"); ap.add_argument("--allow-keyless", action="store_true")
    a = ap.parse_args()
    key = get_key()
    if not key and not a.allow_keyless:
        print("PSI_API_KEY not set (user env var). See the docstring for setup; "
              "--allow-keyless uses the shared quota and usually returns 429.")
        return 2
    results, rows, failed = {}, [], 0
    for p in a.pages:
        p = norm_page(p)
        url = p if p.startswith("http") else BASE + p
        for s in a.strategies:
            d = call(url, s, key)
            name = f"{p} [{s}]"
            if "_error" in d:
                results[name] = d; failed += 1
                rows.append(f"| {name} | ERROR | {d['_error'][:90]} |"); continue
            try:
                r = summarise(d)
            except Exception as e:  # an unexpected response shape costs one row, not the run
                results[name] = {"_error": f"unparseable PSI response: {type(e).__name__}"}; failed += 1
                rows.append(f"| {name} | ERROR | unparseable PSI response: {type(e).__name__} |"); continue
            results[name] = r
            c = r["cats"]
            rows.append(f"| {name} | P{c.get('performance')} A{c.get('accessibility')} "
                        f"BP{c.get('best-practices')} SEO{c.get('seo')} | "
                        f"LCP {r['metrics'].get('largest-contentful-paint')} / TBT {r['metrics'].get('total-blocking-time')} / "
                        f"CLS {r['metrics'].get('cumulative-layout-shift')} / field {r['field_overall']} |")
            time.sleep(2)
    print("# PageSpeed Insights: " + BASE + "\n\n| Page | Scores | Lab metrics / field |\n|---|---|---|")
    print("\n".join(rows))
    for n, r in results.items():
        if "_error" in r: continue
        if r["opportunities"] or r["other_failing"]:
            print(f"\n## {n}")
            for ms, k, t in r["opportunities"]: print(f"- opportunity {ms:.0f} ms: {t}")
            for k, t in r["other_failing"]: print(f"- below 90: {t}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(results, fh, indent=1)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
