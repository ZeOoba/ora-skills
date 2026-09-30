"""Offline regression tests for website-perfection/scripts (no network, no real key).

Every case calls the PRODUCTION function and pins a defect the 2026-09-30 adversarial merge
gate confirmed on PR #96 (round 1: robustness; round 2: the round-1 fixes themselves).
Run: python website-perfection/tests/test_scripts.py
"""
import contextlib, importlib.util, io, os, sys, time, unittest, urllib.error
from unittest import mock

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


crawl, psi = load("seo_crawl"), load("psi_check")
BASE = "https://oxfordra.net"


def an(html, url=BASE + "/x"):
    return crawl.analyse_html(url, 200, {}, html)


class ParserTests(unittest.TestCase):
    def test_title_without_head_tag(self):
        self.assertEqual(an("<title>A | Oxford Realty Advisors</title><body>x</body>")["title"],
                         "A | Oxford Realty Advisors")

    def test_svg_title_in_body_ignored(self):
        self.assertEqual(an("<html><head><title>Real</title></head><body><svg><title>Map</title></svg></body></html>")["title"], "Real")

    def test_stray_title_inside_body_is_not_the_page_title(self):
        self.assertEqual(an("<html><head></head><body><p>x</p><title>Late</title></body></html>")["title"], "")

    def test_svg_title_with_no_body_tag_is_not_the_page_title(self):
        self.assertEqual(an("<div><svg><title>Map pin</title></svg></div>")["title"], "")

    def test_stray_close_style_keeps_text(self):
        self.assertGreaterEqual(an("<body></style><p>one two three four</p></body>")["words"], 4)

    def test_stray_close_script_keeps_text(self):
        self.assertGreaterEqual(an("<body></script><p>one two three four</p></body>")["words"], 4)

    def test_canonical_rel_is_case_insensitive_and_token_exact(self):
        self.assertEqual(an('<link rel="Canonical" href="https://x/">')["canonical"], ["https://x/"])
        self.assertEqual(an('<link rel="noncanonical" href="https://bad/">')["canonical"], [])
        self.assertEqual(an('<link rel="Alternate CANONICAL" href="https://y/">')["canonical"], ["https://y/"])


class SitemapTests(unittest.TestCase):
    def test_cdata_prefix_order_and_comments(self):
        xml = ("<urlset><!-- c --><url><loc><![CDATA[https://a.test/x]]></loc></url>"
               "<s:url><s:lastmod>2026-01-02</s:lastmod><s:changefreq>daily</s:changefreq><s:loc>https://a.test/y</s:loc></s:url>"
               "<url><loc>https://a.test/z</loc><lastmod>2026-02-03</lastmod></url></urlset>")
        self.assertEqual(crawl.parse_sitemap(xml), [("https://a.test/x", None),
                         ("https://a.test/y", "2026-01-02"), ("https://a.test/z", "2026-02-03")])

    def test_image_loc_is_not_a_page_loc(self):
        # real <loc> first, image <loc> after: a parser that ignores the prefix would let the
        # later image loc overwrite the page loc
        xml = ("<url><loc>https://a.test/a</loc><image:image><image:loc>https://a.test/i.png</image:loc></image:image></url>")
        self.assertEqual(crawl.parse_sitemap(xml), [("https://a.test/a", None)])

    def test_malformed_input_is_linear_time(self):
        for bad in ("<url>" * 60000, "<url><loc>" + " " * 6000 + "</url>", "<loc>" * 30000,
                    "<url><loc><![CDATA[" * 20000, "<!--" * 30000):
            t = time.time(); crawl.parse_sitemap(bad)
            self.assertLess(time.time() - t, 2.0, bad[:20])

    def test_sitemapindex_yields_nothing(self):
        self.assertEqual(crawl.parse_sitemap("<sitemapindex><sitemap><loc>https://a.test/s.xml</loc></sitemap></sitemapindex>"), [])

    def test_same_host(self):
        for ok in ("https://oxfordra.net/about", "http://oxfordra.net/about", "https://OXFORDRA.net/x"):
            self.assertTrue(crawl.same_host(ok, BASE), ok)
        for bad in ("https://oxfordra.net.evil.example/", "https://oxfordra.net@evil.example/", "http://127.0.0.1/",
                    "ftp://oxfordra.net/", "https://oxfordra.net:8443/", "http://oxfordra.net:abc/x", "http://oxfordra.net:99999/x",
                    "https://[::1]/"):
            self.assertFalse(crawl.same_host(bad, BASE), bad)

    def test_stale_lastmod_compares_dates_only(self):
        self.assertEqual(crawl.stale_lastmods({BASE + "/r/": "2026-09-28T10:00:00Z", BASE + "/r/a": "2026-09-28"}, BASE), [])
        # hub is a plain date, child a same-day datetime: string compare would call the hub stale
        self.assertEqual(crawl.stale_lastmods({BASE + "/r/": "2026-09-28", BASE + "/r/a": "2026-09-28T10:00:00Z"}, BASE), [])
        rows = crawl.stale_lastmods({BASE + "/r/": "2026-08-12", BASE + "/r/a": "2026-09-28"}, BASE)
        self.assertEqual(len(rows), 1)


class CrawlMainTests(unittest.TestCase):
    """main() end to end over a fake fetch(): no sockets."""

    PAGE = ('<html lang="en"><head><title>Home | Oxford Realty Advisors</title><meta name="description" content="%s">'
            '<link rel="canonical" href="%s"><meta name="robots" content="index, follow"><meta name="viewport" content="x">'
            '<meta property="og:title" content="t"><meta property="og:description" content="d"><meta property="og:image" content="i">'
            '<meta property="og:url" content="u"><meta property="og:type" content="website">'
            '<meta name="twitter:card" content="c"><meta name="twitter:title" content="t"><meta name="twitter:image" content="i">'
            '<script type="application/ld+json">{"@type":"Organization"}</script></head><body><h1>H</h1>%s</body></html>')

    def run_main(self, sitemap, pages, extra=None):
        desc = "d" * 150
        table = {BASE + "/sitemap.xml": (200, {}, sitemap), BASE + "/robots.txt": (200, {}, "Sitemap: x"),
                 BASE + "/llms.txt": (200, {}, ""), BASE + "/manifest.json": (200, {}, ""),
                 BASE + "/favicon.ico": (200, {}, ""), BASE + "/zz-not-a-page-seo-crawl": (404, {}, "")}
        for u, links in pages.items():
            table[u] = (200, {}, self.PAGE % (desc, u, " ".join('<a href="%s">l</a>' % l for l in links) + "word " * 320))
        table.update(extra or {})

        def fake(url, method="GET", retries=3):
            return table.get(url, (301, {"location": "x"}, "") if "www." in url or url.startswith("http://") else (200, {}, ""))
        out = io.StringIO()
        with mock.patch.object(crawl, "fetch", fake), mock.patch.object(sys, "argv", ["seo_crawl.py", "--base", BASE]), \
                contextlib.redirect_stdout(out):
            rc = crawl.main()
        return rc, out.getvalue()

    def test_clean_site_reports_clean(self):
        rc, out = self.run_main("<urlset><url><loc>%s/</loc></url></urlset>" % BASE, {BASE + "/": []})
        self.assertEqual(rc, 0); self.assertIn("HIGH 0 / MED 0 / LOW 0", out)

    def test_sitemapindex_exits_2_not_clean(self):
        rc, out = self.run_main("<sitemapindex><sitemap><loc>%s/s.xml</loc></sitemap></sitemapindex>" % BASE, {})
        self.assertEqual(rc, 2); self.assertNotIn("no findings", out)

    def test_offhost_sitemap_loc_is_a_high_finding_and_not_fetched(self):
        sm = "<urlset><url><loc>%s/</loc></url><url><loc>https://www.oxfordra.net/contact</loc></url></urlset>" % BASE
        rc, out = self.run_main(sm, {BASE + "/": []})
        self.assertEqual(rc, 0); self.assertIn("| HIGH | https://www.oxfordra.net/contact | sitemap <loc> is on another host", out)

    def test_http_internal_link_is_reported(self):
        rc, out = self.run_main("<urlset><url><loc>%s/</loc></url></urlset>" % BASE, {BASE + "/": ["http://oxfordra.net/about"]})
        self.assertIn("internal link uses http://", out)

    def test_malformed_port_link_does_not_crash(self):
        rc, out = self.run_main("<urlset><url><loc>%s/</loc></url></urlset>" % BASE, {BASE + "/": ["http://oxfordra.net:abc/x"]})
        self.assertEqual(rc, 0)


def http_error(code, body):
    return urllib.error.HTTPError("https://x/?key=K", code, "m", {}, io.BytesIO(body))


class PsiTests(unittest.TestCase):
    KEY = "FAKEKEY123QWERTYUIOPASDFGHJKLZXCVBNM12"  # 38 chars

    def shape(self, score, dv="1.0 s"):
        audit = {"scoreDisplayMode": "numeric", "score": 1, "displayValue": dv}
        return {"lighthouseResult": {"categories": {"performance": {"score": score}},
                "audits": {"largest-contentful-paint": audit}}}

    def test_null_score_does_not_crash(self):
        self.assertEqual(psi.summarise(self.shape(None))["cats"]["performance"], "n/a")

    def test_null_or_missing_display_value_is_na(self):
        self.assertEqual(psi.summarise(self.shape(0.9, dv=None))["metrics"]["largest-contentful-paint"], "n/a")
        s = self.shape(0.9); del s["lighthouseResult"]["audits"]["largest-contentful-paint"]["displayValue"]
        self.assertEqual(psi.summarise(s)["metrics"]["largest-contentful-paint"], "n/a")

    def call_with(self, exc_factory):
        with mock.patch.object(psi._opener, "open", side_effect=exc_factory), mock.patch.object(psi.time, "sleep"):
            return psi.call("https://oxfordra.net/", "mobile", self.KEY)

    def test_key_never_survives_in_error_text(self):
        for pad in (0, 150, 185, 195, 199, 200, 250, 3950, 3962, 3970, 3990, 3999):
            for filler in (b"x", b" ", b"\n", b"x "):
                body = (filler * pad)[:pad] + self.KEY.encode() + b" tail" * 50
                err = self.call_with(lambda *a, **k: (_ for _ in ()).throw(http_error(400, body)))["_error"]
                self.assertNotIn("\n", err)
                for n in range(5, len(self.KEY) + 1):  # any 5+ char prefix of the key
                    self.assertNotIn(self.KEY[:n], err, (pad, filler, n))

    def test_generic_exception_text_is_scrubbed(self):
        err = self.call_with(lambda *a, **k: (_ for _ in ()).throw(OSError("fail https://g/?key=" + self.KEY)))["_error"]
        self.assertNotIn(self.KEY[:8], err)

    def test_4xx_is_not_retried_5xx_is_retried_three_times(self):
        for code, calls in ((429, 1), (400, 1), (500, 3)):
            with mock.patch.object(psi._opener, "open", side_effect=http_error(code, b"{}")) as m, mock.patch.object(psi.time, "sleep"):
                psi.call("https://oxfordra.net/", "mobile", self.KEY)
            self.assertEqual(m.call_count, calls, code)

    def test_msys_path_normaliser(self):
        for raw, want in (("C:/Program Files/Git/", "/"), ("C:/Program Files/git/contact", "/contact"),
                          ("D:/tools/git/sell-your-building", "/sell-your-building"), ("/contact", "/contact"),
                          ("https://oxfordra.net/", "https://oxfordra.net/"), ("C:/github/x", "C:/github/x")):
            self.assertEqual(psi.norm_page(raw), want, raw)

    def test_main_survives_one_unparseable_response(self):
        good = self.shape(0.9); good["lighthouseResult"]["categories"]["performance"]["score"] = 0.91
        bad = {"lighthouseResult": {"categories": None, "audits": {}}}  # summarise() raises AttributeError, not KeyError
        out = io.StringIO()
        with mock.patch.object(psi, "get_key", return_value=self.KEY), mock.patch.object(psi, "call", side_effect=[good, bad]), \
                mock.patch.object(psi.time, "sleep"), mock.patch.object(sys, "argv", ["p", "--pages", "/", "--strategies", "mobile", "desktop"]), \
                contextlib.redirect_stdout(out):
            rc = psi.main()
        self.assertEqual(rc, 1); self.assertIn("unparseable PSI response", out.getvalue()); self.assertIn("P91", out.getvalue())


if __name__ == "__main__":
    unittest.main()
