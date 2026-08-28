#!/usr/bin/env python3
"""
notion_fetch_digest.py - extract the useful skeleton from an oversized notion-fetch dump.

WHY THIS EXISTS
---------------
notion-fetch on a large ORA database (e.g. the Tenant Database, 8dbbaec0-...) returns
52-84K characters and overflows the tool-result token cap. The MCP layer then spills the
whole payload to a tool-results .txt file as ONE line, which Read cannot chunk and which
is expensive to grep blind.

Almost always the only things actually needed from that payload are:
  * the data-source (collection://) URLs, for notion-query-data-sources SQL mode
  * the view (view://) URLs, for notion-query-data-sources VIEW mode (the no-quota fallback)
  * the property schema, to get exact property names and types right before a write

This script pulls exactly those and prints them in a few hundred tokens.

VERIFIED FACTS THIS ENCODES (2026-08-28, against the live ORA Tenant Database)
-----------------------------------------------------------------------------
1. View URLs are emitted as {{view://<uuid>}} - NOT as https://...?v=<id>. Grepping a dump
   for "?v=" finds nothing and produces the false conclusion that no view exists. That
   exact false negative caused a scheduled run to report the view-mode fallback as
   unavailable when it was in fact available.
2. <view> tags appear ONLY in the fetch of the DATABASE wrapper id (e.g. 8dbbaec0-...).
   The fetch of the data source (collection://b12f4cfd-...) contains NO view tags. If you
   need a view URL, fetch the database, not the data source.
3. notion-query-data-sources accepts the bare "view://<uuid>" string as view_url.
4. View mode returns a per-row "url" field, so it can drive writes. SQL mode does NOT
   return page ids unless you explicitly SELECT id, url.
5. Attribute quotes in the spilled file are backslash-escaped (url=\"{{...}}\"), so any
   parser must tolerate both \" and " forms.

USAGE
-----
    python notion_fetch_digest.py <path-to-dump.txt> [--schema] [--json]

    --schema   print every column as "name  TYPE", one per line
               (default: comma-separated names only, capped at 60)
    --json     emit machine-readable JSON instead of the human summary

Exit codes: 0 ok, 1 file unreadable, 2 nothing recognizable found.
"""

import argparse
import json
import os
import re
import sys

# Tolerate both escaped (\") and bare (") attribute quotes.
Q = r'\\?"'

RE_COLLECTION = re.compile(r'collection://([0-9a-fA-F-]{36})')
RE_VIEW = re.compile(r'view://([0-9a-fA-F-]{36})')
RE_VIEW_TAG = re.compile(
    r'<view\s+url=' + Q + r'\{\{view://([0-9a-fA-F-]{36})\}\}' + Q + r'([^>]{0,400}?)>',
    re.DOTALL,
)
RE_ATTR = re.compile(r'(\w[\w-]*)=' + Q + r'(.*?)' + Q, re.DOTALL)
RE_TITLE = re.compile(r'<(?:database|page|data-source)[^>]*?title=' + Q + r'(.*?)' + Q, re.DOTALL)
RE_SQLITE_BLOCK = re.compile(r'<sqlite-table>(.*?)</sqlite-table>', re.DOTALL)
RE_ENTITY = re.compile(r'<(database|page|data-source)\b')
# A schema line looks like:  "Tenant Name" TEXT,  /  "Monthly Rent" REAL,
RE_COLUMN = re.compile(
    r'(?:\\?"|`)(?P<name>[^"`\\]{1,120})(?:\\?"|`)\s+'
    r'(?P<type>TEXT|REAL|INTEGER|NUMERIC|BLOB|BOOLEAN|DATE|DATETIME)\b',
    re.IGNORECASE,
)


def read_dump(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        return fh.read()


def unescape(s):
    return s.replace('\\"', '"').replace('\\n', ' ').replace('\\/', '/').strip()


def extract(raw):
    out = {
        'entity_types': sorted(set(RE_ENTITY.findall(raw))),
        'titles': [],
        'collections': [],
        'views': [],
        'columns': [],
        'char_count': len(raw),
    }

    seen = set()
    for t in RE_TITLE.findall(raw):
        t = unescape(t)
        if t and t not in seen:
            seen.add(t)
            out['titles'].append(t)

    for cid in dict.fromkeys(RE_COLLECTION.findall(raw)):
        out['collections'].append({
            'id': cid,
            'query_as': 'collection://{}'.format(cid),
        })

    # Prefer full <view> tags (they carry name/type attrs); fall back to bare view:// hits.
    tagged = {}
    for vid, attrs in RE_VIEW_TAG.findall(raw):
        parsed = {k: unescape(v) for k, v in RE_ATTR.findall(attrs)}
        tagged[vid] = parsed
    for vid in dict.fromkeys(RE_VIEW.findall(raw)):
        meta = tagged.get(vid, {})
        out['views'].append({
            'id': vid,
            'view_url': 'view://{}'.format(vid),
            'name': meta.get('name') or meta.get('title') or '',
            'type': meta.get('type', ''),
        })

    for block in RE_SQLITE_BLOCK.findall(raw):
        for m in RE_COLUMN.finditer(block):
            name = unescape(m.group('name'))
            col = {'name': name, 'type': m.group('type').upper()}
            if col not in out['columns']:
                out['columns'].append(col)

    # Fallback: some payloads inline the schema without a <sqlite-table> wrapper.
    if not out['columns']:
        for m in RE_COLUMN.finditer(raw):
            name = unescape(m.group('name'))
            col = {'name': name, 'type': m.group('type').upper()}
            if col not in out['columns']:
                out['columns'].append(col)

    return out


def render(d, show_schema, path):
    L = []
    L.append('notion-fetch digest - {}'.format(os.path.basename(path)))
    L.append('source size: {:,} chars'.format(d['char_count']))
    if d['entity_types']:
        L.append('entity tags: {}'.format(', '.join(d['entity_types'])))
    if d['titles']:
        L.append('title(s): {}'.format(' | '.join(d['titles'][:5])))
    L.append('')

    L.append('DATA SOURCES ({}) - use as table names in SQL mode'.format(len(d['collections'])))
    if d['collections']:
        for c in d['collections']:
            L.append('  {}'.format(c['query_as']))
    else:
        L.append('  (none found)')
    L.append('')

    L.append('VIEWS ({}) - pass as view_url for VIEW mode (no SQL quota)'.format(len(d['views'])))
    if d['views']:
        for v in d['views'][:40]:
            label = v['name'] or '(unnamed)'
            typ = ' [{}]'.format(v['type']) if v['type'] else ''
            L.append('  {}  {}{}'.format(v['view_url'], label, typ))
        if len(d['views']) > 40:
            L.append('  ... {} more'.format(len(d['views']) - 40))
    else:
        L.append('  (none found - note: views appear only in the DATABASE fetch,')
        L.append('   never in the data-source fetch. Fetch the database wrapper id.)')
    L.append('')

    cols = d['columns']
    L.append('PROPERTY SCHEMA ({} columns)'.format(len(cols)))
    if not cols:
        L.append('  (none found)')
    elif show_schema:
        for c in cols:
            # Pad to 44 but NEVER truncate: a silently shortened property name is
            # indistinguishable from a real one and would be copied into a query or
            # a write verbatim. Exact names are this tool's entire purpose.
            L.append('  {:<44} {}'.format(c['name'], c['type']))
    else:
        L.append('  ' + ', '.join(c['name'] for c in cols[:60]))
        if len(cols) > 60:
            L.append('  ... {} more (use --schema for the full list)'.format(len(cols) - 60))
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('dump', help='path to the spilled notion-fetch tool-result .txt')
    ap.add_argument('--schema', action='store_true', help='print every column, one per line')
    ap.add_argument('--json', action='store_true', dest='as_json', help='emit JSON')
    args = ap.parse_args()

    try:
        raw = read_dump(args.dump)
    except OSError as exc:
        sys.stderr.write('cannot read {}: {}\n'.format(args.dump, exc))
        return 1

    d = extract(raw)
    if args.as_json:
        print(json.dumps(d, indent=2))
    else:
        print(render(d, args.schema, args.dump))

    if not d['collections'] and not d['views'] and not d['columns']:
        sys.stderr.write('warning: nothing recognizable extracted - is this a notion-fetch dump?\n')
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
