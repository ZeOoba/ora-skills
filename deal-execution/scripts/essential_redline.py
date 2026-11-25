#!/usr/bin/env python3
"""essential_redline.py — apply an essential-only tracked-change redline (plus optional
margin comments) to a counterparty .docx from a JSON spec. Self-contained; stdlib only.

Usage:
  python3 essential_redline.py spec.json in.docx out.docx [--author "Gabriel Goldberg"] [--strip-comments]

Spec (JSON list; ops applied in order; every anchor must match EXACTLY ONCE in run text):
  {"op":"insert",   "anchor":"text", "at":"end"|"start"|<int offset into anchor>, "text":"new text"}
  {"op":"delete",   "anchor":"text containing the deletion", "text":"exact substring to strike"}
  {"op":"replace",  "anchor":"text containing old", "old":"old text", "new":"new text"}
  {"op":"new_para_after", "anchor":"text in the paragraph to follow",
                    "segments":[["Heading. ", true], ["Body text.", false]]}
  {"op":"comment",  "anchor":"text in the paragraph to annotate", "text":"note"}

Behaviour:
  * Merges adjacent identically-formatted runs first so visible text is findable.
  * Inserted runs copy the formatting of the run they split; new paragraphs copy the
    anchor paragraph's paragraph properties (so numbered lists auto-number) and mark the
    paragraph mark as inserted.
  * Anchors are matched against run text AFTER earlier ops — do not anchor on text that
    an earlier op split (anchor on text left intact, or order ops accordingly).
  * Fails loudly (exit 2) on any anchor that matches 0 or >1 times; nothing is written.
  * --strip-comments writes the same redline without comments (the outbound copy).
Validate afterwards with the docx skill: scripts/office/validate.py out.docx --original in.docx --author "<author>".
"""
import json, re, sys, zipfile, datetime, argparse
from xml.sax.saxutils import escape as xesc

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'

class SpecError(Exception):
    pass

RUN = re.compile(r'<w:r>(<w:rPr>(?:(?!</w:rPr>).)*</w:rPr>)?<w:t(?: xml:space="preserve")?>([^<]*)</w:t></w:r>', re.S)

def merge_runs(d):
    """Merge each chain of directly adjacent text-only runs that share identical rPr."""
    out, pos, prev = [], 0, None   # prev = [rpr, text, end_index] of a pending run
    for m in RUN.finditer(d):
        rpr = m.group(1) or ''
        if prev is not None and m.start() == prev[2] and rpr == prev[0]:
            prev[1] += m.group(2); prev[2] = m.end()
            continue
        if prev is not None:
            out.append(f'<w:r>{prev[0]}<w:t xml:space="preserve">{prev[1]}</w:t></w:r>')
            pos = prev[2]
        out.append(d[pos:m.start()])
        prev = [rpr, m.group(2), m.end()]
    if prev is not None:
        out.append(f'<w:r>{prev[0]}<w:t xml:space="preserve">{prev[1]}</w:t></w:r>')
        pos = prev[2]
    out.append(d[pos:])
    return ''.join(out)

class Redliner:
    def __init__(self, xml, author, date):
        # normalise run openings like <w:r w:rsidR="..."> to <w:r> so runs are uniform
        xml = re.sub(r'<w:r [^>]*?(?<!/)>', '<w:r>', xml)
        xml = re.sub(r'<w:proofErr [^>]*/>', '', xml)
        self.d = merge_runs(xml)
        self.A = f'w:author="{xesc(author, {chr(34): "&quot;"})}" w:date="{date}"'
        self.nid = 7000
        self.comments = []   # (anchor, text)

    def _id(self):
        self.nid += 1
        return self.nid

    def _find_once(self, anchor):
        a = xesc(anchor)
        n = self.d.count(a)
        if n != 1:
            raise SpecError(f'anchor matched {n} times (need exactly 1): {anchor[:80]!r}')
        return self.d.find(a), a

    def _run_at(self, i):
        rs = self.d.rfind('<w:r>', 0, i)
        re_ = self.d.find('</w:r>', i) + 6
        r = self.d[rs:re_]
        m_rpr = re.search(r'<w:rPr>.*?</w:rPr>', r, re.S)
        m_t = re.search(r'<w:t(?: [^>]*)?>(.*)</w:t>', r, re.S)
        if not m_t or (m_rpr and m_rpr.start() > m_t.start()):
            raise SpecError('anchor is not inside a single text run; shorten the anchor')
        return rs, re_, (m_rpr.group(0) if m_rpr else ''), m_t.group(1)

    @staticmethod
    def _run(rpr, t):
        return f'<w:r>{rpr}<w:t xml:space="preserve">{t}</w:t></w:r>' if t else ''

    def _ins(self, rpr, t_esc):
        return f'<w:ins w:id="{self._id()}" {self.A}>{self._run(rpr, t_esc)}</w:ins>'

    def _del(self, rpr, t_esc):
        return (f'<w:del w:id="{self._id()}" {self.A}><w:r>{rpr}'
                f'<w:delText xml:space="preserve">{t_esc}</w:delText></w:r></w:del>')

    def insert(self, anchor, text, at='end'):
        i, a = self._find_once(anchor)
        rs, re_, rpr, t = self._run_at(i)
        base = t.find(a)
        if base < 0:
            raise SpecError(f'anchor spans runs; shorten it: {anchor[:80]!r}')
        p = base + (len(a) if at == 'end' else 0 if at == 'start' else len(xesc(anchor[:int(at)])))
        self.d = self.d[:rs] + self._run(rpr, t[:p]) + self._ins(rpr, xesc(text)) + self._run(rpr, t[p:]) + self.d[re_:]

    def delete(self, anchor, text, new=None):
        i, a = self._find_once(anchor)
        rs, re_, rpr, t = self._run_at(i)
        s = xesc(text)
        if t.count(s) != 1:
            raise SpecError(f'deletion text must occur once in the anchor run: {text[:60]!r}')
        p = t.find(s)
        mid = self._del(rpr, s) + (self._ins(rpr, xesc(new)) if new else '')
        self.d = self.d[:rs] + self._run(rpr, t[:p]) + mid + self._run(rpr, t[p + len(s):]) + self.d[re_:]

    def _para_bounds(self, anchor):
        i, _ = self._find_once(anchor)
        ps = max(self.d.rfind('<w:p ', 0, i), self.d.rfind('<w:p>', 0, i))
        pe = self.d.find('</w:p>', i) + 6
        return ps, pe

    def new_para_after(self, anchor, segments):
        ps, pe = self._para_bounds(anchor)
        para = self.d[ps:pe]
        m = re.search(r'<w:pPr>.*?</w:pPr>', para, re.S)
        ppr = m.group(0) if m else '<w:pPr></w:pPr>'
        mark = f'<w:ins w:id="{self._id()}" {self.A}/>'
        if '<w:rPr>' in ppr:
            ppr = ppr.replace('<w:rPr>', '<w:rPr>' + mark, 1)
        else:
            ppr = ppr.replace('</w:pPr>', f'<w:rPr>{mark}</w:rPr></w:pPr>')
        # base run formatting = first text run of the anchor paragraph, minus bold
        m_r = re.search(r'<w:r>(<w:rPr>.*?</w:rPr>)?<w:t', para, re.S)
        base = (m_r.group(1) or '<w:rPr></w:rPr>') if m_r else '<w:rPr></w:rPr>'
        plain = re.sub(r'<w:b/>|<w:bCs/>|<w:i/>|<w:iCs/>|<w:u [^>]*/>', '', base)
        bold = plain.replace('<w:rPr>', '<w:rPr><w:b/><w:bCs/>', 1)
        body = ''.join(self._ins(bold if b else plain, xesc(t)) for t, b in segments)
        self.d = self.d[:pe] + f'<w:p>{ppr}{body}</w:p>' + self.d[pe:]

    def comment(self, anchor, text):
        self._find_once(anchor)  # validate now
        self.comments.append((anchor, text))

    def place_comments(self, files, author, initials, date):
        if not self.comments:
            return
        cx = files.get('word/comments.xml')
        start = 0
        if cx:
            ids = [int(x) for x in re.findall(r'<w:comment [^>]*w:id="(\d+)"', cx)]
            start = max(ids) + 1 if ids else 0
        else:
            cx = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:comments xmlns:w="{W}"></w:comments>'
            ct = files['[Content_Types].xml']
            if 'comments+xml' not in ct:
                files['[Content_Types].xml'] = ct.replace('</Types>',
                    '<Override PartName="/word/comments.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"/></Types>')
            rels = files['word/_rels/document.xml.rels']
            if 'relationships/comments"' not in rels:
                files['word/_rels/document.xml.rels'] = rels.replace('</Relationships>',
                    '<Relationship Id="rIdEssRedlineComments" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" Target="comments.xml"/></Relationships>')
        add = ''
        for k, (anchor, text) in enumerate(self.comments):
            cid = start + k
            add += (f'<w:comment w:id="{cid}" w:author="{xesc(author)}" w:date="{date}" w:initials="{xesc(initials)}">'
                    f'<w:p><w:r><w:t xml:space="preserve">{xesc(text)}</w:t></w:r></w:p></w:comment>')
            ps, pe = self._para_bounds(anchor)
            para = self.d[ps:pe]
            k2 = para.find('</w:pPr>')
            k2 = k2 + 8 if k2 >= 0 else para.find('>') + 1
            para = (para[:k2] + f'<w:commentRangeStart w:id="{cid}"/>' + para[k2:-6] +
                    f'<w:commentRangeEnd w:id="{cid}"/><w:r><w:commentReference w:id="{cid}"/></w:r></w:p>')
            self.d = self.d[:ps] + para + self.d[pe:]
        files['word/comments.xml'] = cx.replace('</w:comments>', add + '</w:comments>')

def run(spec_path, src, dst, author, initials, strip_comments):
    spec = json.load(open(spec_path, encoding='utf-8'))
    zin = zipfile.ZipFile(src)
    files = {n: zin.read(n) for n in zin.namelist() if not n.endswith('/')}
    text = {n: files[n].decode('utf-8') for n in
            ('word/document.xml', '[Content_Types].xml', 'word/_rels/document.xml.rels', 'word/comments.xml') if n in files}
    date = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    r = Redliner(text['word/document.xml'], author, date)
    for n, op in enumerate(spec, 1):
        try:
            o = op['op']
            if o == 'insert':
                r.insert(op['anchor'], op['text'], op.get('at', 'end'))
            elif o == 'delete':
                r.delete(op['anchor'], op['text'])
            elif o == 'replace':
                r.delete(op['anchor'], op['old'], op['new'])
            elif o == 'new_para_after':
                r.new_para_after(op['anchor'], op['segments'])
            elif o == 'comment':
                if not strip_comments:
                    r.comment(op['anchor'], op['text'])
            else:
                raise SpecError(f'unknown op {o!r}')
        except (SpecError, KeyError) as e:
            print(f'FAIL op #{n} ({op.get("op")}): {e}', file=sys.stderr)
            sys.exit(2)
        print(f'OK   op #{n} {op["op"]}: {str(op.get("anchor", ""))[:60]!r}')
    r.place_comments(text, author, initials, date)
    text['word/document.xml'] = r.d
    with zipfile.ZipFile(dst, 'w', zipfile.ZIP_DEFLATED) as z:
        for n, b in files.items():
            z.writestr(n, text[n].encode('utf-8') if n in text else b)
        for n in text:
            if n not in files:
                z.writestr(n, text[n].encode('utf-8'))
    print(f'WROTE {dst}  ({len(spec)} ops, {0 if strip_comments else len(r.comments)} comments, author {author!r})')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('spec'); ap.add_argument('src'); ap.add_argument('dst')
    ap.add_argument('--author', default='Gabriel Goldberg')
    ap.add_argument('--initials', default='GG')
    ap.add_argument('--strip-comments', action='store_true')
    a = ap.parse_args()
    run(a.spec, a.src, a.dst, a.author, a.initials, a.strip_comments)
