"""Tests for scripts/essential_redline.py (Workflow 2C). Stdlib unittest (repo gate: bare
pytest-style functions never run under `python <file>`)."""
import json, os, shutil, subprocess, sys, tempfile, unittest, zipfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "..", "scripts", "essential_redline.py")
if not os.path.exists(SCRIPT):  # allow running beside the script
    SCRIPT = os.path.join(HERE, "essential_redline.py")

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NUM = '<w:pPr><w:numPr><w:ilvl w:val="1"/><w:numId w:val="3"/></w:numPr><w:rPr><w:sz w:val="22"/></w:rPr></w:pPr>'
R = '<w:rPr><w:sz w:val="22"/></w:rPr>'
B = '<w:rPr><w:b/><w:sz w:val="22"/></w:rPr>'


def _docx(path):
    body = (
        f'<w:p w:rsidR="00AA">{NUM}<w:r w:rsidR="00AB">{B}<w:t xml:space="preserve">Waiver. </w:t></w:r>'
        f'<w:r>{R}<w:t>Each Owner waives </w:t></w:r><w:r>{R}<w:t>claims as provided herein.</w:t></w:r></w:p>'
        f'<w:p>{NUM}<w:r>{B}<w:t xml:space="preserve">Counterparts. </w:t></w:r>'
        f'<w:r>{R}<w:t>This Agreement may be signed in counterparts.</w:t></w:r></w:p>'
        f'<w:p><w:r>{R}<w:t>Owner , at its sole cost, shall restripe.</w:t></w:r></w:p>'
    )
    doc = f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document xmlns:w="{W}"><w:body>{body}</w:body></w:document>'
    ct = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
          '<Default Extension="xml" ContentType="application/xml"/>'
          '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
          '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
    drels = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"></Relationships>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", ct)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", drels)


def _run(tmp_path, spec, *extra):
    src, out, sp = tmp_path / "in.docx", tmp_path / "out.docx", tmp_path / "spec.json"
    _docx(src)
    sp.write_text(json.dumps(spec), encoding="utf-8")
    res = subprocess.run([sys.executable, SCRIPT, str(sp), str(src), str(out), "--author", "Tester", *extra],
                         capture_output=True, text=True)
    return res, out


def _xml(out, part="word/document.xml"):
    with zipfile.ZipFile(out) as z:
        return z.read(part).decode("utf-8")


SPEC = [
    {"op": "insert", "anchor": "claims as provided herein.", "at": "end", "text": " Added sentence."},
    {"op": "replace", "anchor": "may be signed in counterparts", "old": "signed", "new": "executed"},
    {"op": "insert", "anchor": "Owner , at its sole cost", "at": 6, "text": "1"},
    {"op": "new_para_after", "anchor": "Waiver. ", "segments": [["Insurance. ", True], ["Each Owner shall insure.", False]]},
    {"op": "comment", "anchor": "Counterparts. ", "text": "Note for review copy."},
]


class EssentialRedline(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="essential_redline_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_tracked_ops_and_comment(self):
        res, out = _run(self.tmp, SPEC)
        assert res.returncode == 0, res.stderr
        d = _xml(out)
        assert d.count('w:author="Tester"') >= 6
        assert "Each Owner waives claims as provided herein." in d  # runs merged
        assert "<w:ins" in d and " Added sentence." in d
        assert '<w:delText xml:space="preserve">signed</w:delText>' in d and ">executed<" in d
        assert "Owner 1" not in d.replace("</w:t></w:r><w:ins", "")  # inserted, not rewritten in place
        i = d.find("Insurance. ")
        assert i > d.find("Waiver. ") and i < d.find("Counterparts. ")
        assert '<w:numId w:val="3"/>' in d[d.rfind("<w:p>", 0, i):i]  # numbering copied
        assert "commentReference" in d
        c = _xml(out, "word/comments.xml")
        assert "Note for review copy." in c and 'w:author="Tester"' in c
        with zipfile.ZipFile(out) as z:
            assert "comments+xml" in z.read("[Content_Types].xml").decode()
            assert "relationships/comments" in z.read("word/_rels/document.xml.rels").decode()


    def test_strip_comments(self):
        res, out = _run(self.tmp, SPEC, "--strip-comments")
        assert res.returncode == 0, res.stderr
        assert "commentReference" not in _xml(out)
        with zipfile.ZipFile(out) as z:
            assert "word/comments.xml" not in z.namelist()


    def test_anchor_must_match_once(self):
        res, out = _run(self.tmp, [{"op": "insert", "anchor": "Owner", "text": "x"}])
        assert res.returncode == 2 and "op #1" in res.stderr and not out.exists()
        res, out = _run(self.tmp, [{"op": "insert", "anchor": "no such text", "text": "x"}])
        assert res.returncode == 2 and not out.exists()


if __name__ == "__main__":
    unittest.main()
