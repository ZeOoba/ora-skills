#!/usr/bin/env python3 -I
"""Extract the embedded JSON dataset from a saved artifact page and print its schema.
Usage: extract_artifact_data.py <index.html> <out.json> [script_id=data]
Dashboards embed data as <script type="application/json" id="data">...</script>.
Get index.html with: Artifact action:read url:<link> path:index.html  (the plain read truncates at ~16K chars)."""
import re, sys, json
src, out = sys.argv[1], sys.argv[2]
sid = sys.argv[3] if len(sys.argv) > 3 else 'data'
html = open(src, encoding='utf8').read()
m = re.search(r'<script[^>]*type="application/json"[^>]*id="%s"[^>]*>(.*?)</script>' % re.escape(sid), html, re.S) \
    or re.search(r'<script[^>]*id="%s"[^>]*type="application/json"[^>]*>(.*?)</script>' % re.escape(sid), html, re.S)
if not m:
    ids = re.findall(r'<script[^>]*type="application/json"[^>]*id="([^"]+)"', html)
    sys.exit(f'No JSON script with id={sid!r}. JSON script ids found: {ids or "none"}. '
             'If the page renders from inline JS objects, grep the HTML for the data literal instead.')
d = json.loads(m.group(1))
json.dump(d, open(out, 'w'), indent=1)
def show(o, depth=0, maxd=2):
    if isinstance(o, dict):
        for k, v in o.items():
            n = len(v) if hasattr(v, '__len__') and not isinstance(v, str) else v
            print('  ' * depth + f'{k}  <{type(v).__name__}>  {n if not isinstance(n, str) else n[:60]}')
            if depth < maxd: show(v, depth + 1, maxd)
    elif isinstance(o, list) and o:
        print('  ' * depth + f'[0] sample: {json.dumps(o[0])[:200]}')
show(d, 0, 1)
print(f'\nwrote {out}')
