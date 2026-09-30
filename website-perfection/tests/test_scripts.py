"""Offline regression tests for website-perfection/scripts (no network, no key).

Each case pins a defect the 2026-09-30 adversarial merge gate confirmed on PR #96.
Run: python website-perfection/tests/test_scripts.py
"""
import importlib.util, os, sys, unittest

SCRIPTS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts")


def load(name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(SCRIPTS, name + ".py"))
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


crawl, psi = load("seo_crawl"), load("psi_check")


def parse(html):
    p = crawl.Page(); p.feed(html); return p


class ParserTests(unittest.TestCase):
    def test_title_without_head_tag(self):
        self.assertEqual(parse("<title>A | Oxford Realty Advisors</title><body>x</body>").title.strip(),
                         "A | Oxford Realty Advisors")

    def test_svg_title_in_body_ignored(self):
        p = parse("<html><head><title>Real</title></head><body><svg><title>Map</title></svg></body></html>")
        self.assertEqual(p.title, "Real")

    def test_stray_close_style_keeps_text(self):
        p = parse("<body></style><p>one two three four</p></body>")
        self.assertGreaterEqual(len(" ".join(p.text).split()), 4)

    def test_canonical_rel_case_and_tokens(self):
        links = [{"rel": "Canonical", "href": "https://x/"}, {"rel": "noncanonical", "href": "https://bad/"}]
        got = [l["href"] for l in links if "canonical" in (l.get("rel") or "").lower().split()]
        self.assertEqual(got, ["https://x/"])


class SitemapTests(unittest.TestCase):
    def test_cdata_prefix_and_order(self):
        xml = ("<urlset><url><loc><![CDATA[https://a.test/x]]></loc></url>"
               "<s:url><s:lastmod>2026-01-02</s:lastmod><s:changefreq>daily</s:changefreq><s:loc>https://a.test/y</s:loc></s:url>"
               "<url><loc>https://a.test/z</loc><lastmod>2026-02-03</lastmod></url></urlset>")
        self.assertEqual(crawl.parse_sitemap(xml), [("https://a.test/x", None),
                         ("https://a.test/y", "2026-01-02"), ("https://a.test/z", "2026-02-03")])

    def test_same_host_rejects_prefix_tricks(self):
        b = "https://oxfordra.net"
        self.assertTrue(crawl.same_host("https://oxfordra.net/about", b))
        for bad in ("https://oxfordra.net.evil.example/", "https://oxfordra.net@evil.example/",
                    "http://127.0.0.1/", "ftp://oxfordra.net/"):
            self.assertFalse(crawl.same_host(bad, b), bad)


class PsiTests(unittest.TestCase):
    def shape(self, score, dv=True):
        audit = {"scoreDisplayMode": "numeric", "score": 1}
        if dv: audit["displayValue"] = "1.0 s"
        return {"lighthouseResult": {"categories": {"performance": {"score": score}},
                "audits": {"largest-contentful-paint": audit}}}

    def test_null_score_does_not_crash(self):
        self.assertEqual(psi.summarise(self.shape(None))["cats"]["performance"], "n/a")

    def test_missing_display_value_does_not_crash(self):
        self.assertEqual(psi.summarise(self.shape(0.9, dv=False))["metrics"]["largest-contentful-paint"], "n/a")

    def test_scrub_before_truncate(self):
        key = "FAKEKEY123"
        body = "x" * 195 + key
        self.assertNotIn("FAKEK", " ".join(psi.scrub("HTTP 400: " + body, key).split())[:200])


if __name__ == "__main__":
    unittest.main()
