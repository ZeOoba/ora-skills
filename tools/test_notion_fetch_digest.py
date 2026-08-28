"""Tests for tools/notion_fetch_digest.py.

Regression anchor: on 2026-08-28 a scheduled run searched a notion-fetch dump for
"?v=" view URLs, found none, and wrongly concluded the view-mode quota fallback was
unavailable. Notion emits view URLs as {{view://<uuid>}}. test_finds_view_urls and
test_rejects_query_string_view_assumption pin that behavior.
"""

import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import notion_fetch_digest as nfd  # noqa: E402

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      'notion_fetch_digest.py')

# Mirrors the real spilled-payload grammar: one line, backslash-escaped quotes.
ESCAPED = (
    r'<database url=\"https://app.notion.com/p/8dbbaec0611a4617be076a77d0d0307a\" '
    r'title=\"Tenant Database\"><data-sources>'
    r'<data-source url=\"{{collection://b12f4cfd-a995-4755-8341-6435ae8173b4}}\">'
    r'<sqlite-table>CREATE TABLE \"collection://b12f4cfd-a995-4755-8341-6435ae8173b4\" ('
    r'\"Tenant Name\" TEXT, \"Primary Contact\" TEXT, \"Contact Email\" TEXT, '
    r'\"Contact Source\" TEXT, \"Monthly Rent\" REAL, \"SF\" INTEGER)</sqlite-table>'
    r'<views>'
    r'<view url=\"{{view://3386ecd8-9e59-8163-b40b-000cad25e879}}\" name=\"All Tenants\" '
    r'type=\"table\"></view>'
    r'<view url=\"{{view://3396ecd8-9e59-818a-8c7a-000cfe954220}}\" name=\"Missing Contacts\" '
    r'type=\"table\"></view>'
    r'</views></data-source></data-sources></database>'
)

BARE = ESCAPED.replace('\\"', '"')


class TestExtract(unittest.TestCase):

    def test_finds_collection_url(self):
        d = nfd.extract(ESCAPED)
        self.assertEqual(
            [c['query_as'] for c in d['collections']],
            ['collection://b12f4cfd-a995-4755-8341-6435ae8173b4'],
        )

    def test_finds_view_urls(self):
        """The 2026-08-28 false negative. Views must be found via view://."""
        d = nfd.extract(ESCAPED)
        urls = [v['view_url'] for v in d['views']]
        self.assertEqual(len(urls), 2)
        self.assertIn('view://3386ecd8-9e59-8163-b40b-000cad25e879', urls)
        self.assertIn('view://3396ecd8-9e59-818a-8c7a-000cfe954220', urls)

    def test_rejects_query_string_view_assumption(self):
        """A '?v=' search finds nothing here. That is the trap, not an absence.

        Both assertions are load-bearing: the first pins the fixture as a faithful
        reproduction of the trap (no '?v=' anywhere), the second proves the parser
        still recovers every view despite that, which is the behavior a '?v=' search
        would have wrongly reported as 'no views available'.
        """
        self.assertNotIn('?v=', ESCAPED)
        self.assertEqual(
            sorted(v['view_url'] for v in nfd.extract(ESCAPED)['views']),
            ['view://3386ecd8-9e59-8163-b40b-000cad25e879',
             'view://3396ecd8-9e59-818a-8c7a-000cfe954220'],
        )

    def test_view_names_and_types(self):
        by_id = {v['view_url']: v for v in nfd.extract(ESCAPED)['views']}
        v = by_id['view://3396ecd8-9e59-818a-8c7a-000cfe954220']
        self.assertEqual(v['name'], 'Missing Contacts')
        self.assertEqual(v['type'], 'table')

    def test_schema_columns(self):
        cols = {c['name']: c['type'] for c in nfd.extract(ESCAPED)['columns']}
        self.assertEqual(cols['Tenant Name'], 'TEXT')
        self.assertEqual(cols['Monthly Rent'], 'REAL')
        self.assertEqual(cols['SF'], 'INTEGER')
        self.assertIn('Contact Source', cols)

    def test_bare_quotes_equivalent(self):
        """Payloads are sometimes unescaped; both forms must parse identically."""
        a, b = nfd.extract(ESCAPED), nfd.extract(BARE)
        self.assertEqual([v['view_url'] for v in a['views']],
                         [v['view_url'] for v in b['views']])
        self.assertEqual([c['name'] for c in a['columns']],
                         [c['name'] for c in b['columns']])

    def test_schema_never_truncates_long_names(self):
        """A silently shortened property name would be copied into a query verbatim.

        render() pads names to a 44-char column; it must not CLIP at 44. Regression
        for a `c['name'][:44]` slice that produced output indistinguishable from a
        genuinely short name.
        """
        long_name = 'Tenant Primary Contact Email Address For Renewal Notices'
        self.assertGreater(len(long_name), 44)
        payload = ESCAPED.replace('\\"Tenant Name\\" TEXT',
                                  '\\"{}\\" TEXT'.format(long_name))
        d = nfd.extract(payload)
        self.assertIn(long_name, [c['name'] for c in d['columns']])
        out = nfd.render(d, True, 'fixture.txt')
        self.assertIn(long_name, out)
        self.assertNotIn(long_name[:44] + ' ', out.replace(long_name, ''))

    def test_datasource_only_payload_has_no_views(self):
        """Documents why fetching the data source instead of the database misleads."""
        ds_only = ESCAPED.split('<views>')[0]
        d = nfd.extract(ds_only)
        self.assertTrue(d['collections'])
        self.assertEqual(d['views'], [])


class TestCli(unittest.TestCase):

    def _run(self, text, *args):
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False,
                                         encoding='utf-8') as fh:
            fh.write(text)
            path = fh.name
        try:
            p = subprocess.run([sys.executable, SCRIPT, path] + list(args),
                               capture_output=True, text=True)
            return p.returncode, p.stdout
        finally:
            os.unlink(path)

    def test_cli_ok(self):
        rc, out = self._run(ESCAPED)
        self.assertEqual(rc, 0)
        self.assertIn('view://3386ecd8-9e59-8163-b40b-000cad25e879', out)

    def test_cli_json(self):
        import json
        rc, out = self._run(ESCAPED, '--json')
        self.assertEqual(rc, 0)
        self.assertEqual(len(json.loads(out)['views']), 2)

    def test_cli_exit_2_on_garbage(self):
        rc, _ = self._run('nothing to see here')
        self.assertEqual(rc, 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
