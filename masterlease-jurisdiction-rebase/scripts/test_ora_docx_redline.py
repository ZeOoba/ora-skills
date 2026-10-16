#!/usr/bin/env python3
"""Tests for ora_docx_redline.py v2 (2026-10-15): the four Phase-1 build workarounds
folded in as first-class ops, plus the Phase-1 equivalence proof.

  1. insert_paragraph_after -- tracked styled/numbered paragraph, pPr copied from the
     anchor or a reference paragraph (or given explicitly)
  2. delete                 -- tracked deletion inside an asserted context
  3. "part"                 -- ops on footer/header parts, count asserted across parts
  4. accept_all / accept    -- XML-level accept-all-changes (no LibreOffice round-trip)

Phase1EquivalenceTests re-runs the committed specs (../specs/power-rights_*.json, the
Phase-1 build.py edit list ported to these ops) on the v2.7 / v3.0 masters and asserts
the result reproduces the committed Phase-1 v2.8 / v3.1 TEMPLATE fixtures byte-for-byte
in every package part, with 29 / 28 tracked changes in the REDLINE, and lease_qc 0 of 68
/ 0 of 73 (power-rights ENFORCED) on the clean output.

Run:  python3 -I -B masterlease-jurisdiction-rebase/scripts/test_ora_docx_redline.py
"""
import io
import json
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from contextlib import redirect_stderr

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ora_docx_redline as odr  # noqa: E402

FIX = HERE / "fixtures"
SPECS = HERE.parent / "specs"
LEASE_QC = HERE.parent.parent / "lease-form-qc" / "scripts" / "lease_qc.py"
A, D = "Oxford Realty Advisors", "2026-10-15T00:00:00Z"

H2 = '<w:pStyle w:val="Heading2"/><w:numPr><w:ilvl w:val="1"/><w:numId w:val="1"/></w:numPr><w:rPr/>'
DOC = ('<w:document><w:body>'
       '<w:p><w:pPr>' + H2 + '</w:pPr><w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>Utilities</w:t></w:r>'
       '<w:r><w:rPr/><w:t xml:space="preserve">.  Landlord furnishes power; and (h) upon notice.</w:t></w:r></w:p>'
       '<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:rPr/></w:pPr><w:r><w:rPr/><w:t>PARKING.</w:t></w:r></w:p>'
       '<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:rPr/></w:pPr><w:r><w:rPr/><w:t>PARKING spaces.</w:t></w:r></w:p>'
       '<w:sectPr/></w:body></w:document>')
FOOT = '<w:ftr><w:p><w:r><w:rPr/><w:t>ORA Master Lease v2.7 — October 2026</w:t></w:r></w:p></w:ftr>'


def make_docx(path, doc=DOC, footers=(FOOT, FOOT, '<w:ftr><w:p/></w:ftr>')):
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("word/document.xml", doc)
        for i, f in enumerate(footers, 1):
            z.writestr(f"word/footer{i}.xml", f)
        z.writestr("word/styles.xml", "<w:styles/>")
    return path


def part(path, name):
    with zipfile.ZipFile(path) as z:
        return z.read(name).decode("utf-8")


def texts(path):
    with zipfile.ZipFile(path) as z:
        return {n: [odr.para_text(p) for p in re.findall(r"<w:p[ >].*?</w:p>", z.read(n).decode(), re.S)]
                for n in sorted(z.namelist()) if odr.XML_PARTS_RE.match(n)}


class Tmp(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.d = pathlib.Path(self._td.name)
        self.src = make_docx(self.d / "src.docx")

    def tearDown(self):
        self._td.cleanup()

    def run_spec(self, ops, accept=True, **kw):
        out, clean = self.d / "red.docx", self.d / "clean.docx"
        s = odr.apply_spec(str(self.src), str(out), {"author": A, "date": D, "ops": ops, **kw},
                           accept_out=str(clean) if accept else None)
        return s, out, clean

    def drift(self, ops):
        with self.assertRaises(SystemExit) as cm:
            self.run_spec(ops)
        self.assertIn("ANCHOR DRIFT", str(cm.exception))
        return str(cm.exception)


class InsertParagraphAfter(Tmp):
    def test_styled_numbered_paragraph_copied_from_anchor(self):
        s, out, clean = self.run_spec([{"op": "insert_paragraph_after", "anchor_text": "Landlord furnishes power",
                                        "ppr_from": "anchor",
                                        "runs": [{"text": "Electrical Capacity", "underline": True},
                                                 {"text": ".  Tenant & Landlord <agree>."}]}])
        x = part(out, "word/document.xml")
        new = re.findall(r"<w:p>.*?</w:p>", x, re.S)[1]            # [0] is the anchor paragraph
        # pPr copied incl. style + numPr; paragraph mark tracked first inside pPr/rPr
        self.assertIn('<w:pPr><w:pStyle w:val="Heading2"/><w:numPr><w:ilvl w:val="1"/><w:numId w:val="1"/>'
                      '</w:numPr><w:rPr><w:ins w:id="9001" w:author="Oxford Realty Advisors" '
                      'w:date="2026-10-15T00:00:00Z"/></w:rPr></w:pPr>', new)
        self.assertIn('<w:ins w:id="9002" w:author="Oxford Realty Advisors"', new)
        self.assertIn("Tenant &amp; Landlord &lt;agree&gt;.", new)       # text is XML-escaped
        self.assertEqual(s["tracked_changes"], 2)                        # paragraph mark + runs
        self.assertEqual(texts(clean)["word/document.xml"][1], "Electrical Capacity.  Tenant & Landlord <agree>.")
        self.assertNotIn("<w:ins", part(clean, "word/document.xml"))
        self.assertIn('<w:pPr><w:pStyle w:val="Heading2"/><w:numPr><w:ilvl w:val="1"/><w:numId w:val="1"/>'
                      '</w:numPr><w:rPr/></w:pPr>', part(clean, "word/document.xml"))

    def test_ppr_from_reference_paragraph_and_named_ppr(self):
        _, out, _ = self.run_spec([
            {"op": "insert_paragraph_after", "anchor_text": "Landlord furnishes", "ppr_from": "PARKING spaces",
             "runs": [{"text": "A"}]},
            {"op": "insert_paragraph_after", "anchor_text": "PARKING.", "ppr": "H9",
             "runs": [{"text": "B", "rpr": "BU"}]}],
            ppr={"H9": '<w:pStyle w:val="Heading9"/><w:rPr/>'}, rpr={"BU": "<w:rPr><w:b/></w:rPr>"})
        x = part(out, "word/document.xml")
        self.assertRegex(x, r'<w:p><w:pPr><w:pStyle w:val="Heading1"/><w:rPr><w:ins [^>]*/></w:rPr></w:pPr>'
                            r'<w:ins [^>]*><w:r><w:rPr/><w:t xml:space="preserve">A<')
        self.assertRegex(x, r'<w:pStyle w:val="Heading9"/><w:rPr><w:ins [^>]*/></w:rPr></w:pPr><w:ins [^>]*>'
                            r'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">B<')

    def test_anchor_must_name_exactly_count_paragraphs(self):
        msg = self.drift([{"op": "insert_paragraph_after", "anchor_text": "PARKING", "ppr_from": "anchor",
                           "runs": [{"text": "x"}]}])
        self.assertIn("found 2, expected 1", msg)
        self.drift([{"op": "insert_paragraph_after", "anchor_text": "NO SUCH TEXT", "ppr_from": "anchor",
                     "runs": [{"text": "x"}]}])
        # count=2 inserts after both
        s, out, clean = self.run_spec([{"op": "insert_paragraph_after", "anchor_text": "PARKING", "count": 2,
                                        "ppr_from": "anchor", "runs": [{"text": "x"}]}])
        self.assertEqual(texts(clean)["word/document.xml"], ["Utilities.  Landlord furnishes power; and (h) upon notice.",
                                                              "PARKING.", "x", "PARKING spaces.", "x"])

    def test_ambiguous_reference_paragraph_drifts(self):
        self.drift([{"op": "insert_paragraph_after", "anchor_text": "Landlord", "ppr_from": "PARKING",
                     "runs": [{"text": "x"}]}])

    def test_copied_ppr_drops_section_break_and_old_revisions(self):
        inner = odr.Redliner.ppr_inner_of('<w:p><w:pPr><w:pStyle w:val="X"/><w:sectPr><w:pgSz/></w:sectPr>'
                                          '<w:rPr><w:ins w:id="1" w:author="a" w:date="d"/></w:rPr>'
                                          '<w:pPrChange w:id="2"><w:pPr/></w:pPrChange></w:pPr></w:p>')
        self.assertEqual(inner, '<w:pStyle w:val="X"/><w:rPr/>')


class Delete(Tmp):
    def test_tracked_delete_inside_context(self):
        s, out, clean = self.run_spec([{"op": "delete", "context": "; and (h) upon", "target": "and "}])
        x = part(out, "word/document.xml")
        self.assertIn('<w:del w:id="9001" w:author="Oxford Realty Advisors" w:date="2026-10-15T00:00:00Z">'
                      '<w:r><w:rPr/><w:delText xml:space="preserve">and </w:delText></w:r></w:del>', x)
        self.assertEqual(s["tracked_changes"], 1)
        self.assertEqual(texts(clean)["word/document.xml"][0], "Utilities.  Landlord furnishes power; (h) upon notice.")

    def test_context_count_is_asserted(self):
        self.drift([{"op": "delete", "context": "no such context", "target": "no"}])
        self.drift([{"op": "delete", "context": "; and (h) upon", "target": "and ", "count": 2}])

    def test_target_must_be_inside_context(self):
        with self.assertRaises(SystemExit):
            self.run_spec([{"op": "delete", "context": "; and (h) upon", "target": "zzz"}])


class Parts(Tmp):
    def test_footer_glob_count_asserted_across_parts_with_separate_id_ranges(self):
        s, out, clean = self.run_spec([{"op": "replace", "part": "word/footer*.xml", "old": "v2.7", "new": "v2.8",
                                        "count": 2}])
        self.assertEqual(s["parts_changed"], ["word/footer1.xml", "word/footer2.xml"])
        f1, f2 = part(out, "word/footer1.xml"), part(out, "word/footer2.xml")
        self.assertIn('w:id="9601"', f1)          # footer1 = index 0 in the header/footer list
        self.assertIn('w:id="9701"', f2)          # footer2 = index 1: no id collision
        self.assertEqual(s["tracked_changes"], 4)  # del + ins in each footer
        self.assertEqual(part(out, "word/footer3.xml"), part(self.src, "word/footer3.xml"))
        self.assertEqual(part(out, "word/document.xml"), part(self.src, "word/document.xml"))
        self.assertEqual(texts(clean)["word/footer1.xml"], ["ORA Master Lease v2.8 — October 2026"])

    def test_footer_total_count_drift(self):
        msg = self.drift([{"op": "replace", "part": "word/footer*.xml", "old": "v2.7", "new": "v2.8", "count": 3}])
        self.assertIn("found 2, expected 3", msg)

    def test_unknown_part_drifts(self):
        self.drift([{"op": "replace", "part": "word/header*.xml", "old": "v2.7", "new": "v2.8", "count": 1}])

    def test_v1_list_spec_and_v1_ops_still_work(self):
        out = self.d / "v1.docx"
        odr.apply_spec(str(self.src), str(out), [{"op": "replace", "old": "furnishes", "new": "supplies", "count": 1},
                                                 {"op": "insert_after", "anchor": "upon notice", "text": " in writing",
                                                  "count": 1}], author=A, date=D)
        x = part(out, "word/document.xml")
        self.assertIn("<w:delText xml:space=\"preserve\">furnishes</w:delText>", x)
        self.assertIn(">supplies<", x)
        self.assertIn("> in writing<", x)
        msg = self.drift([{"op": "replace", "old": "furnishes", "new": "x", "count": 2}])
        self.assertIn("'furnishes': found 1, expected 2", msg)


class Accept(Tmp):
    def test_accept_keeps_every_other_byte(self):
        _, out, clean = self.run_spec([{"op": "replace", "old": "furnishes", "new": "supplies", "count": 1}])
        self.assertEqual(odr.tracked_change_count(str(clean)), 0)
        with zipfile.ZipFile(self.src) as a, zipfile.ZipFile(clean) as b:
            self.assertEqual(a.namelist(), b.namelist())             # member order kept
            for n in a.namelist():
                if n != "word/document.xml":
                    self.assertEqual(a.read(n), b.read(n), n)
        self.assertIn("Landlord supplies power", texts(clean)["word/document.xml"][0])

    def test_accept_refuses_unsupported_revisions(self):
        for bad in ('<w:rPrChange w:id="1"/>', '<w:moveFrom w:id="1">',
                    '<w:pPr><w:rPr><w:del w:id="1" w:author="a" w:date="d"/></w:rPr></w:pPr>'):
            with self.subTest(bad=bad), self.assertRaises(SystemExit) as cm:
                odr.accept_all(f"<w:p>{bad}</w:p>")
            self.assertIn("ACCEPT REFUSED", str(cm.exception))

    def test_accept_cli(self):
        _, out, _ = self.run_spec([{"op": "replace", "old": "furnishes", "new": "supplies", "count": 1}], accept=False)
        clean = self.d / "cli_clean.docx"
        r = subprocess.run([sys.executable, "-I", "-B", str(HERE / "ora_docx_redline.py"), "accept",
                            "--in", str(out), "--out", str(clean)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("accepted 2 tracked change(s)", r.stdout)
        self.assertEqual(odr.tracked_change_count(str(clean)), 0)

    def test_redline_cli_with_spec_author_and_accept_out(self):
        spec = self.d / "s.json"
        spec.write_text(json.dumps({"author": A, "date": D, "ops": [
            {"op": "replace", "part": "word/footer*.xml", "old": "v2.7", "new": "v2.8", "count": 2}]}))
        out, clean = self.d / "c_red.docx", self.d / "c_clean.docx"
        r = subprocess.run([sys.executable, "-I", "-B", str(HERE / "ora_docx_redline.py"), "--in", str(self.src),
                            "--out", str(out), "--spec", str(spec), "--accept-out", str(clean)],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("4 tracked change(s)", r.stdout)
        self.assertEqual(odr.tracked_change_count(str(clean)), 0)
        bad = self.d / "bad.json"
        bad.write_text(json.dumps({"author": A, "date": D, "ops": [
            {"op": "replace", "part": "word/footer*.xml", "old": "v2.7", "new": "v2.8", "count": 1}]}))
        r = subprocess.run([sys.executable, "-I", "-B", str(HERE / "ora_docx_redline.py"), "--in", str(self.src),
                            "--out", str(self.d / "x.docx"), "--spec", str(bad)], capture_output=True, text=True)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("ANCHOR DRIFT", r.stderr)


class Phase1EquivalenceTests(unittest.TestCase):
    """The Phase-1 power-rights edits, re-run through the built-in ops, reproduce
    the committed Phase-1 v2.8 / v3.1 TEMPLATE fixtures exactly."""

    CASES = [("power-rights_v2.7-to-v2.8.json", "ORA_MasterLease_ShallowBayIndustrial_v2.7_TEMPLATE.docx",
              "ORA_MasterLease_ShallowBayIndustrial_v2.8_TEMPLATE.docx", 29, 68),
             ("power-rights_v3.0-to-v3.1.json", "ORA_MasterLease_ShallowBay_MultiTenantMG_v3.0_TEMPLATE.docx",
              "ORA_MasterLease_ShallowBay_MultiTenantMG_v3.1_TEMPLATE.docx", 28, 73)]

    def test_specs_reproduce_phase1_outputs(self):
        with tempfile.TemporaryDirectory() as td:
            for spec, src, expected, n_changes, n_checks in self.CASES:
                with self.subTest(spec=spec):
                    red = pathlib.Path(td) / expected.replace("_TEMPLATE", "_REDLINE")
                    clean = pathlib.Path(td) / expected
                    s = odr.apply_spec(str(FIX / src), str(red), str(SPECS / spec), accept_out=str(clean))
                    self.assertEqual(s["tracked_changes"], n_changes)
                    self.assertEqual(s["parts_changed"], ["word/document.xml", "word/footer2.xml",
                                                          "word/footer3.xml"])
                    with zipfile.ZipFile(clean) as a, zipfile.ZipFile(FIX / expected) as b:
                        self.assertEqual(a.namelist(), b.namelist())
                        for n in a.namelist():
                            self.assertEqual(a.read(n), b.read(n), f"{expected}: {n} differs")
                    self.assertEqual(texts(clean), texts(FIX / expected))
                    r = subprocess.run([sys.executable, "-I", "-B", str(LEASE_QC), str(clean), "--json"],
                                       capture_output=True, text=True)
                    self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr)
                    rep = json.loads(r.stdout)
                    rep = rep[0] if isinstance(rep, list) else rep
                    self.assertEqual(rep["checks_run"], n_checks)
                    self.assertEqual(rep["failures"], [])
                    self.assertEqual(rep["form"]["power_rights"], "ENFORCED")

    def test_specs_fail_loudly_on_the_wrong_master(self):
        with tempfile.TemporaryDirectory() as td, redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as cm:
                odr.apply_spec(str(FIX / "ORA_MasterLease_ShallowBayIndustrial_v2.6_TEMPLATE.docx"),
                               str(pathlib.Path(td) / "x.docx"), str(SPECS / "power-rights_v2.7-to-v2.8.json"))
            self.assertIn("ANCHOR DRIFT", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
