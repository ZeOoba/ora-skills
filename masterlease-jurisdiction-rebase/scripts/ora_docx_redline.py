#!/usr/bin/env python3
"""
ora_docx_redline.py — ORA shared tracked-change editor for Word XML.

Extracted 2026-08-04 from the master-lease v2.6 build (third ad-hoc reimplementation
of the same machinery: v2.3 build, v2.5 build, v2.6 build). Applies asserted-count
edits to a .docx as REAL tracked changes (<w:ins>/<w:del> with author + date), per
lease-form-qc Output doctrine. Any count mismatch aborts loudly with the anchor named
(ANCHOR DRIFT) — never loosen an assertion to make a run pass; re-key the anchor.

v2 (2026-10-15): the four workarounds the Phase-1 power-rights build (v2.7 -> v2.8,
v3.0 -> v3.1) had to bolt on in a wrapper script are now first-class:
  1. insert_paragraph_after  — a tracked NEW paragraph with its own pPr (style +
     numbering, e.g. Heading1/Heading2 with numPr), copied from the anchor or any
     reference paragraph, or given explicitly; paragraph mark and every run tracked.
  2. delete                  — tracked deletion of a target inside an asserted context.
  3. "part"                  — every op can target any XML part (default
     word/document.xml), including globs such as word/footer*.xml; the count is
     asserted across all matching parts, each part gets its own w:id range.
  4. accept_all / `accept`   — XML-level accept-all-changes producing the clean
     template directly (drop <w:del>, unwrap <w:ins>, drop paragraph-mark <w:ins/>);
     every other byte of every package part is kept, so the clean file keeps the
     source's run structure (no LibreOffice re-serialisation).

Spec (JSON): either a list of ops (v1 form, all on word/document.xml), or
  {"author": ..., "date": ..., "start_id": 9000,
   "rpr":  {"U": "<w:rPr><w:u w:val=\\"single\\"/></w:rPr>", ...},   # named run props
   "ppr":  {"H2": "<w:pStyle .../><w:numPr>...</w:numPr><w:rPr/>", ...},  # named pPr inners
   "ops":  [ ... ]}
Ops (applied in order; every op takes optional "part", default "word/document.xml"):
  {"op": "replace",  "old": "...", "new": "...", "count": N}
  {"op": "insert_after", "anchor": "...", "text": "...", "count": N}
  {"op": "delete", "context": "...", "target": "...", "count": N}
        tracked deletion of `target` (a substring of `context`) in each run holding `context`
  {"op": "insert_paragraph_after", "anchor_text": "...", "count": 1,
   "ppr": "<name or raw pPr inner xml>" | "ppr_from": "anchor" | "<text snippet of a reference paragraph>",
   "runs": [{"text": "...", "rpr": "<name or raw <w:rPr> xml>"} | {"text": "...", "bold": true, "underline": true}]}
        `count` = number of paragraphs whose text contains anchor_text (asserted);
        a new paragraph is inserted after each.
  {"op": "insert_paragraphs_after", "anchor_xml": "<exact xml substring>",
   "paragraphs": [{"label": "Bold lead-in:", "text": " value"}], "count": 1}   (v1, BodyText)

Usage:
  python3 -I ora_docx_redline.py --in master.docx --out REDLINE.docx --spec edits.json \
      [--author "Oxford Realty Advisors" --date 2026-10-15T00:00:00Z] [--accept-out TEMPLATE.docx]
  python3 -I ora_docx_redline.py accept --in REDLINE.docx --out TEMPLATE.docx
(--author/--date are required unless the spec carries them.)

Then ALWAYS validate:  docx skill scripts/office/validate.py <out> --original <in> --author "<author>"
Known limits: in-run anchors (replace / insert_after / delete) must be contiguous inside
one <w:t> (run merge_runs.py first if not); anchor text must not recur inside an inserted
string. accept_all refuses documents carrying revision types it does not handle
(formatting changes, moves, deleted paragraph marks) rather than guess.
"""
import argparse, fnmatch, html, json, os, re, shutil, sys, tempfile, zipfile

XML_PARTS_RE = re.compile(r'word/(document|footer\d+|header\d+)\.xml$')
HF_PARTS_RE = re.compile(r'word/(footer|header)\d+\.xml$')
_PARA_RE = re.compile(r'<w:p[ >].*?</w:p>', re.S)
_T_RE = re.compile(r'<w:t(?:\s[^>]*)?>([^<]*)</w:t>')


def _drift(msg):
    raise SystemExit(f'ANCHOR DRIFT {msg}')


def para_text(p_xml):
    """Visible text of one <w:p> (w:t only, entity-decoded)."""
    return html.unescape(''.join(_T_RE.findall(p_xml)))


def _esc(s):
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


class Redliner:
    def __init__(self, xml, author, date, start_id=9000):
        self.x, self.a, self.d, self.i = xml, author, date, start_id
    def _nid(self):
        self.i += 1
        return self.i
    def _run(self, rpr, txt):
        return f'<w:r>{rpr}<w:t xml:space="preserve">{txt}</w:t></w:r>' if txt else ''
    def _ins(self, rpr, txt):
        return (f'<w:ins w:id="{self._nid()}" w:author="{self.a}" w:date="{self.d}">'
                f'<w:r>{rpr}<w:t xml:space="preserve">{txt}</w:t></w:r></w:ins>')
    def _del(self, rpr, txt):
        return (f'<w:del w:id="{self._nid()}" w:author="{self.a}" w:date="{self.d}">'
                f'<w:r>{rpr}<w:delText xml:space="preserve">{txt}</w:delText></w:r></w:del>')
    def _mark(self):
        return f'<w:ins w:id="{self._nid()}" w:author="{self.a}" w:date="{self.d}"/>'
    def _find_run(self, idx):
        rs = max(self.x.rfind('<w:r>', 0, idx), self.x.rfind('<w:r ', 0, idx))
        return rs, self.x.find('</w:r>', idx) + len('</w:r>')
    def _parts(self, run):
        m = re.search(r'(<w:rPr\b.*?</w:rPr>|<w:rPr/>)', run, re.S)
        rpr = m.group(1) if m else '<w:rPr/>'
        m = re.search(r'<w:t[^>]*>(.*?)</w:t>', run, re.S)
        return rpr, m.group(1)

    # ---- in-run ops (v1) -------------------------------------------------
    def replace(self, old, new, expect):
        n = self.replace_count(old, new)
        if n != expect:
            _drift(f'{old[:60]!r}: found {n}, expected {expect}')
    def replace_count(self, old, new):
        n = pos = 0
        while True:
            j = self.x.find(old, pos)
            if j < 0:
                break
            rs, re_ = self._find_run(j)
            run = self.x[rs:re_]
            if old not in run:
                sys.exit(f'SPAN FAIL (run merge needed): {old[:60]}')
            rpr, txt = self._parts(run)
            pre, _, post = txt.partition(old)
            rep = self._run(rpr, pre) + self._del(rpr, old) + self._ins(rpr, new) + self._run(rpr, post)
            self.x = self.x[:rs] + rep + self.x[re_:]
            pos = rs + len(rep) - len(self._run(rpr, post))   # rescan from start of post run
            n += 1
        return n
    def insert_after(self, anchor, text, expect):
        n = self.insert_after_count(anchor, text)
        if n != expect:
            _drift(f'{anchor[:60]!r}: found {n}, expected {expect}')
    def insert_after_count(self, anchor, text):
        n = pos = 0
        while True:
            j = self.x.find(anchor, pos)
            if j < 0:
                break
            rs, re_ = self._find_run(j)
            run = self.x[rs:re_]
            if anchor not in run:
                sys.exit(f'SPAN FAIL (run merge needed): {anchor[:60]}')
            rpr, txt = self._parts(run)
            pre, _, post = txt.partition(anchor)
            pre_run = self._run(rpr, pre + anchor)
            rep = pre_run + self._ins(rpr, text) + self._run(rpr, post)
            self.x = self.x[:rs] + rep + self.x[re_:]
            pos = rs + len(pre_run)                            # rescan from after the kept anchor
            n += 1
        return n
    def insert_paragraphs_after(self, anchor_xml, paragraphs, expect=1,
                                pstyle='BodyText'):
        n = self.x.count(anchor_xml)
        if n != expect:
            _drift(f'(xml) {anchor_xml[:60]!r}: found {n}, expected {expect}')
        rows = ''
        for p in paragraphs:
            rows += (f'<w:p><w:pPr><w:pStyle w:val="{pstyle}"/>'
                     f'<w:rPr><w:ins w:id="{self._nid()}" w:author="{self.a}" w:date="{self.d}"/></w:rPr></w:pPr>'
                     f'<w:ins w:id="{self._nid()}" w:author="{self.a}" w:date="{self.d}">'
                     f'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{p["label"]}</w:t></w:r>'
                     f'<w:r><w:rPr/><w:t xml:space="preserve">{p["text"]}</w:t></w:r></w:ins></w:p>')
        self.x = self.x.replace(anchor_xml, anchor_xml + rows, 1)

    # ---- v2 ops ----------------------------------------------------------
    def delete(self, context, target, expect=1):
        """Tracked deletion of `target` inside each run that holds `context`.
        `context` must occur exactly `expect` times in the part (asserted) and
        `target` must be a substring of it."""
        n = self.delete_count(context, target)
        if n != expect:
            _drift(f'{context[:60]!r}: found {n}, expected {expect}')
    def delete_count(self, context, target):
        if target not in context:
            sys.exit(f'delete: target {target!r} is not inside context {context[:60]!r}')
        n = pos = 0
        while True:
            j = self.x.find(context, pos)
            if j < 0:
                break
            rs, re_ = self._find_run(j)
            run = self.x[rs:re_]
            if context not in run:
                sys.exit(f'SPAN FAIL (run merge needed): {context[:60]}')
            rpr, txt = self._parts(run)
            k = txt.find(context) + context.find(target)
            pre, post = txt[:k], txt[k + len(target):]
            rep = self._run(rpr, pre) + self._del(rpr, target) + self._run(rpr, post)
            self.x = self.x[:rs] + rep + self.x[re_:]
            pos = rs + len(rep) - len(self._run(rpr, post))
            n += 1
        return n

    def paragraphs(self):
        return list(_PARA_RE.finditer(self.x))

    def find_paragraphs(self, snippet):
        return [m for m in self.paragraphs() if snippet in para_text(m.group(0))]

    @staticmethod
    def ppr_inner_of(p_xml):
        """The pPr inner XML of a paragraph, cleaned for reuse on a NEW paragraph:
        existing paragraph-mark revisions, pPrChange and any sectPr (a section break
        must never be duplicated) are dropped; an absent rPr becomes <w:rPr/>."""
        m = re.match(r'<w:p\b[^>]*>\s*<w:pPr>(.*?)</w:pPr>', p_xml, re.S)
        inner = m.group(1) if m else ''
        inner = re.sub(r'<w:pPrChange\b.*?</w:pPrChange>', '', inner, flags=re.S)
        inner = re.sub(r'<w:sectPr\b.*?</w:sectPr>', '', inner, flags=re.S)
        inner = re.sub(r'<w:(?:ins|del)\b[^>]*/>', '', inner)
        inner = inner.replace('<w:rPr></w:rPr>', '<w:rPr/>')
        if '<w:rPr' not in inner:
            inner += '<w:rPr/>'
        return inner

    def insert_paragraph_after(self, anchor_text, runs, ppr=None, ppr_from=None, expect=1):
        """Insert a tracked new paragraph after each paragraph whose text contains
        `anchor_text` (asserted: exactly `expect` such paragraphs). Its pPr is
        `ppr` (inner XML), or copied from `ppr_from` ('anchor' = the anchor
        paragraph, else a text snippet naming exactly one reference paragraph).
        runs: [(rPr_xml, text), ...] — text is XML-escaped here."""
        hits = self.find_paragraphs(anchor_text)
        if len(hits) != expect:
            _drift(f'(paragraph) {anchor_text[:60]!r}: found {len(hits)}, expected {expect}')
        if (ppr is None) == (ppr_from is None):
            sys.exit('insert_paragraph_after: give exactly one of ppr / ppr_from')
        if ppr_from is not None and ppr_from != 'anchor':
            refs = self.find_paragraphs(ppr_from)
            if len(refs) != 1:
                _drift(f'(ppr_from) {ppr_from[:60]!r}: found {len(refs)} paragraphs, expected 1')
            ppr = self.ppr_inner_of(refs[0].group(0))
        for m in reversed(hits):
            inner = ppr if ppr is not None else self.ppr_inner_of(m.group(0))
            mark = self._mark()
            # paragraph-mark revision goes first inside pPr/rPr (schema order)
            if '<w:rPr/>' in inner:
                p_ppr = inner.replace('<w:rPr/>', f'<w:rPr>{mark}</w:rPr>', 1)
            elif '<w:rPr>' in inner:
                p_ppr = inner.replace('<w:rPr>', f'<w:rPr>{mark}', 1)
            else:
                p_ppr = inner + f'<w:rPr>{mark}</w:rPr>'
            body = ''.join(f'<w:r>{rpr}<w:t xml:space="preserve">{_esc(t)}</w:t></w:r>' for rpr, t in runs)
            p = (f'<w:p><w:pPr>{p_ppr}</w:pPr><w:ins w:id="{self._nid()}" w:author="{self.a}" '
                 f'w:date="{self.d}">{body}</w:ins></w:p>')
            end = m.end()
            self.x = self.x[:end] + p + self.x[end:]


# ---------------------------------------------------------------------------
# Accept-all (XML level)
# ---------------------------------------------------------------------------
_UNSUPPORTED = re.compile(r'<w:(?:rPrChange|pPrChange|sectPrChange|tblPrChange|trPrChange|tcPrChange|'
                          r'numberingChange|moveFrom|moveTo|moveFromRangeStart|moveToRangeStart|'
                          r'cellIns|cellDel|cellMerge)\b')


def accept_all(xml, part='part'):
    """Accept every <w:ins>/<w:del> in one XML part. Returns (xml, n_ins, n_del).
    Refuses (SystemExit) on revision types it does not implement — formatting
    changes, moves, table-cell revisions, or a deleted paragraph mark — so a
    'clean' template can never silently keep a pending revision."""
    if _UNSUPPORTED.search(xml):
        sys.exit(f'ACCEPT REFUSED {part}: unsupported revision type '
                 f'{_UNSUPPORTED.search(xml).group(0)!r} -- accept it in Word first.')
    if re.search(r'<w:rPr>(?:(?!</w:rPr>).)*<w:del\b[^>]*/>', xml, re.S):
        sys.exit(f'ACCEPT REFUSED {part}: deleted paragraph mark (paragraph merge) is not supported.')
    n_ins = len(re.findall(r'<w:ins\b', xml))
    n_del = len(re.findall(r'<w:del\b', xml))
    x = re.sub(r'<w:del\b[^>]*>.*?</w:del>', '', xml, flags=re.S)
    x = re.sub(r'<w:ins\b[^>]*/>', '', x)
    x = re.sub(r'<w:ins\b[^>]*>(.*?)</w:ins>', r'\1', x, flags=re.S)
    x = x.replace('<w:rPr></w:rPr>', '<w:rPr/>')
    if re.search(r'<w:(?:ins|del)\b|<w:delText\b', x):
        sys.exit(f'ACCEPT FAILED {part}: tracked-change markup remains after acceptance.')
    return x, n_ins, n_del


def tracked_change_count(path):
    """Number of <w:ins>/<w:del> elements (incl. paragraph-mark revisions) across
    the document, header and footer parts -- the figure validate.py reports."""
    n = 0
    with zipfile.ZipFile(path) as z:
        for name in z.namelist():
            if XML_PARTS_RE.match(name):
                x = z.read(name).decode('utf-8')
                n += len(re.findall(r'<w:ins\b', x)) + len(re.findall(r'<w:del\b', x))
    return n


def _rezip(src_zip, out, replaced):
    """Write `out` with src_zip's member order, every member byte-identical except `replaced`."""
    tmp = out + '.tmp'
    with zipfile.ZipFile(src_zip) as zi, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zo:
        for info in zi.infolist():
            data = replaced[info.filename] if info.filename in replaced else zi.read(info.filename)
            zo.writestr(info.filename, data, compress_type=zipfile.ZIP_DEFLATED)
    shutil.move(tmp, out)


def accept_docx(src, out, quiet=False):
    """Clean copy of a redline: every tracked change in document/header/footer parts
    accepted at the XML level; all other package members byte-identical."""
    replaced, total = {}, 0
    with zipfile.ZipFile(src) as z:
        for name in z.namelist():
            if XML_PARTS_RE.match(name):
                x = z.read(name).decode('utf-8')
                nx, ni, nd = accept_all(x, name)
                if ni or nd:
                    replaced[name] = nx.encode('utf-8')
                    total += ni + nd
                    if not quiet:
                        print(f'  {name}: accepted {ni} ins / {nd} del')
    _rezip(src, out, replaced)
    return total


# ---------------------------------------------------------------------------
# Spec application
# ---------------------------------------------------------------------------
def _load_spec(spec):
    if isinstance(spec, (str, os.PathLike)):
        with open(spec, encoding='utf-8') as fh:
            spec = json.load(fh)
    if isinstance(spec, list):
        spec = {'ops': spec}
    return spec


def _rpr(spec, r):
    if 'rpr' in r:
        v = r['rpr']
        return spec.get('rpr', {}).get(v, v)
    props = ''.join(tag for key, tag in (('bold', '<w:b/>'), ('italic', '<w:i/>'),
                                          ('underline', '<w:u w:val="single"/>')) if r.get(key))
    return f'<w:rPr>{props}</w:rPr>' if props else '<w:rPr/>'


def _part_names(names, pattern):
    if any(c in pattern for c in '*?['):
        return sorted(n for n in names if fnmatch.fnmatch(n, pattern))
    return [pattern] if pattern in names else []


def apply_spec(src, out, spec, author=None, date=None, accept_out=None, log=None):
    """Apply a spec (path, list or dict) to `src`, writing the tracked-change
    REDLINE to `out` (and, with accept_out, the XML-accepted clean copy).
    Returns a summary dict. Raises SystemExit on any ANCHOR DRIFT."""
    spec = _load_spec(spec)
    author = author or spec.get('author')
    date = date or spec.get('date')
    if not author or not date:
        sys.exit('apply_spec: author and date are required (CLI flags or spec keys)')
    start_id = int(spec.get('start_id', 9000))
    log = [] if log is None else log
    with zipfile.ZipFile(src) as z:
        names = z.namelist()
        xml = {n: z.read(n).decode('utf-8') for n in names if XML_PARTS_RE.match(n)}
    hf = sorted(n for n in names if HF_PARTS_RE.match(n))
    liners = {}

    def liner(part):
        if part not in liners:
            base = start_id if part == 'word/document.xml' else start_id + 600 + 100 * hf.index(part)
            liners[part] = Redliner(xml[part], author, date, start_id=base)
        return liners[part]

    for k, e in enumerate(spec['ops']):
        op = e['op']
        pattern = e.get('part', 'word/document.xml')
        parts = _part_names(xml, pattern)
        if not parts:
            _drift(f'(part) op #{k} {op}: no XML part matches {pattern!r}')
        label = e.get('label', '')
        expect = e.get('count', 1)
        if op in ('replace', 'insert_after', 'delete'):
            found = 0
            for part in parts:
                r = liner(part)
                if op == 'replace':
                    found += r.replace_count(e['old'], e['new'])
                elif op == 'insert_after':
                    found += r.insert_after_count(e['anchor'], e['text'])
                else:
                    found += r.delete_count(e['context'], e['target'])
            key = e.get('old') or e.get('anchor') or e.get('context')
            if found != expect:
                _drift(f'op #{k} {op} {key[:60]!r}: found {found}, expected {expect}'
                       + (f' across {len(parts)} part(s) {pattern!r}' if len(parts) > 1 else ''))
        elif op == 'insert_paragraph_after':
            if len(parts) != 1:
                sys.exit(f'op #{k} insert_paragraph_after: needs exactly one part, {pattern!r} matched {parts}')
            ppr = e.get('ppr')
            if ppr is not None and not ppr.lstrip().startswith('<'):
                if ppr not in spec.get('ppr', {}):
                    sys.exit(f'op #{k}: unknown ppr name {ppr!r}')
                ppr = spec['ppr'][ppr]
            runs = [(_rpr(spec, r), r['text']) for r in e['runs']]
            liner(parts[0]).insert_paragraph_after(e['anchor_text'], runs, ppr=ppr,
                                                   ppr_from=e.get('ppr_from'), expect=expect)
        elif op == 'insert_paragraphs_after':
            liner(parts[0]).insert_paragraphs_after(e['anchor_xml'], e['paragraphs'], expect)
        else:
            sys.exit(f'unknown op {op}')
        log.append((op, label, pattern))

    replaced = {p: r.x.encode('utf-8') for p, r in liners.items() if r.x != xml[p]}
    _rezip(src, out, replaced)
    summary = {'ops': len(spec['ops']), 'parts_changed': sorted(replaced),
               'tracked_changes': tracked_change_count(out)}
    if accept_out:
        accept_docx(out, accept_out, quiet=True)
        summary['accepted'] = accept_out
    return summary


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ['accept']:
        ap = argparse.ArgumentParser(prog='ora_docx_redline.py accept')
        ap.add_argument('--in', dest='src', required=True)
        ap.add_argument('--out', required=True)
        a = ap.parse_args(argv[1:])
        n = accept_docx(a.src, a.out)
        print(f'OK: accepted {n} tracked change(s) -> {a.out}')
        return
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--author')
    ap.add_argument('--date')
    ap.add_argument('--spec', required=True)
    ap.add_argument('--accept-out', help='also write the XML-accepted clean copy here')
    a = ap.parse_args(argv)
    s = apply_spec(a.src, a.out, a.spec, a.author, a.date, a.accept_out)
    print(f'OK: {s["ops"]} ops applied, {s["tracked_changes"]} tracked change(s) in '
          f'{", ".join(s["parts_changed"]) or "no part"} -> {a.out}'
          + (f'; clean copy -> {a.accept_out}' if a.accept_out else '')
          + '  (validate with validate.py before use)')


if __name__ == '__main__':
    main()
