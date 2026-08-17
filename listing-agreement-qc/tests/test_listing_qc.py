#!/usr/bin/env python3
"""
Regression tests for listing_qc.py's L24 check ("Template residue in header /
footer") — specifically pinning the production wiring commit 7e88341 fixed.

Stdlib only — run with `python listing-agreement-qc/tests/test_listing_qc.py`.
No pytest, matching tools/test_*.py and lease-form-qc/tests/test_lease_qc.py.

WHY THIS FILE EXISTS
--------------------
listing_qc.py's own former extract() joined both word/header*.xml and
word/footer*.xml into meta["headers"], so L24 genuinely scanned both. The
shared ora_doc_qc.py retrofit (2026-08-17) narrowed meta["headers"] to headers
only and routes footer text to a separate meta["footer"] field gated behind
extract(..., want_footer=True) — pma_qc.py and lease_qc.py both opt in via
their own run_cli(...) call, but listing_qc.py's __main__ block never did, so
meta["footer"] was permanently empty for this scanner and L24 silently went
blind to footer-only template residue. Commit 7e88341 fixed both L24's body
(scan headers + footer) and the run_cli(..., want_footer=True) wiring that
feeds it — the same false-negative shape already fixed as Critical on
lease-form-qc's T1 check earlier in this branch (commit 900ad05), which
shipped with a purpose-built regression test in the same commit. 7e88341 did
not.

Worse: none of this branch's three scanners' test suites exercised the
production run_cli(..., want_footer=True) call site through the real
CLI/subprocess path before this file — lease-form-qc's own footer tests call
extract(path, want_footer=True) directly (see test_lease_qc.py's
_new_verdicts()), not lease_qc.py's actual __main__ wiring. That means
deleting `want_footer=True` from any of the three scanners' run_cli(...) calls
today would leave every existing test green. The tests below close that gap
for listing_qc.py specifically: they invoke the real listing_qc.py script as a
subprocess (subprocess.run([sys.executable, 'listing_qc.py', ...])), the same
style test_lease_qc.py's run_cli() helper uses, so they pin the actual
production wiring — not a helper that supplies want_footer itself.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
REPO = SKILL.parent
LISTING_QC = SCRIPTS / "listing_qc.py"

sys.path.insert(0, str(SCRIPTS))


# --------------------------------------------------------------------------
# Synthetic DOCX construction — mirrors lease-form-qc/tests/test_lease_qc.py's
# make_docx(), extended to also write a header part. ora_doc_qc.extract()
# discovers header/footer parts by scanning the zip's namelist for
# word/header\d*.xml / word/footer\d*.xml directly (see extract()'s docx
# branch) — it never consults [Content_Types].xml or a sectPr
# headerReference/footerReference to decide what "counts" as a header or
# footer, so a minimal zip with those parts present is sufficient; no
# document.xml.rels wiring is required for the extraction path under test.
# --------------------------------------------------------------------------

_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
    '<Default Extension="xml" ContentType="application/xml"/>'
    '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
    '</Types>'
)
_RELS = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    '<Relationship Id="rId1" Target="word/document.xml" '
    'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"/>'
    '</Relationships>'
)

# ~190 words of neutral listing-agreement-ish filler. extract() drops anything
# under DEFAULT_MIN_WORDS (150) as UNREADABLE, so every synthetic DOCX must
# clear that floor or the fixture tests silently stop testing what they claim
# to (same discipline as lease-form-qc's _FILLER).
_FILLER = " ".join([
    "This Listing Agreement is made and entered into by and between Owner and",
    "Broker, and the parties agree as follows for all purposes set forth herein",
    "and for the mutual covenants exchanged between them under this instrument.",
    "Owner represents that Owner holds fee title to the Property described below",
    "and has full authority to engage Broker on the terms set forth in this",
    "Agreement without the further consent of any third party or lienholder.",
    "Broker agrees to use commercially reasonable efforts to market the Property",
    "and to procure a ready, willing, and able purchaser or tenant on terms",
    "acceptable to Owner during the term of this engagement as described herein.",
    "The parties acknowledge that the provisions of this instrument have been",
    "reviewed and that each party has had the opportunity to consult with counsel",
    "of its own choosing prior to execution of this instrument by the parties.",
    "Any capitalized term used but not otherwise given an operative definition",
    "shall carry the meaning ordinarily ascribed to it in commercial practice.",
    "The headings used throughout this instrument are inserted for convenience",
    "of reference only and shall not affect the construction or interpretation",
    "of any provision hereof by any court of competent jurisdiction hereafter.",
    "If any provision of this instrument is held to be invalid or unenforceable",
    "the remaining provisions shall nevertheless continue in full force and",
    "effect to the maximum extent permitted by applicable law in this instance.",
])


def _esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _paras(texts):
    return "".join(f'<w:p><w:r><w:t xml:space="preserve">{_esc(x)}</w:t></w:r></w:p>'
                   for x in texts)


def make_docx(path, body_paras, header_text=None, footer_text=None):
    """Write a minimal but structurally real .docx.

    body_paras: list of paragraph strings (filler is appended automatically so
    the document clears extract()'s 150-word UNREADABLE floor).
    header_text / footer_text: None omits that part entirely; a string writes
    one paragraph into word/header1.xml / word/footer1.xml respectively.
    """
    paras = list(body_paras) + [_FILLER]
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{_paras(paras)}</w:body></w:document>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", doc)
        if header_text is not None:
            z.writestr("word/header1.xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                       f'{_paras([header_text])}</w:hdr>')
        if footer_text is not None:
            z.writestr("word/footer1.xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                       f'{_paras([footer_text])}</w:ftr>')
    return str(path)


def run_cli(*args):
    """Invoke listing_qc.py as a REAL subprocess — the point of this file.
    Returns (returncode, stdout+stderr). This goes through the script's actual
    __main__ block and its run_cli(CHECKS, ..., want_footer=True) call, not a
    helper that supplies want_footer itself."""
    p = subprocess.run([sys.executable, str(LISTING_QC), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp(prefix="listing_qc_test_")
        self.tmp = Path(self._td)

    def tearDown(self):
        shutil.rmtree(self._td, ignore_errors=True)


# --------------------------------------------------------------------------
# L24 — the footer-blindness fix (commit 7e88341) and its regression coverage
# --------------------------------------------------------------------------

class TestL24HeaderFooterResidue(TempDirCase):

    def test_l24_fires_on_footer_only_residue(self):
        """THE regression this file exists to catch. No header at all; the
        only template artifact lives in the footer. Before 7e88341,
        listing_qc.py's __main__ never passed want_footer=True, so
        meta["footer"] was permanently "" and this fixture would have scored
        L24 silent — a scanned/negotiated document going out with unremoved
        template boilerplate in the footer and nothing in the report saying
        so. Red-checked: reverting only run_cli(...)'s want_footer=True
        (leaving L24's own header+footer body untouched) makes this test
        fail — see task report for the transcript."""
        p = make_docx(
            self.tmp / "footer_residue.docx",
            ["LISTING AGREEMENT FOR SALE between Owner and Broker, an "
             "exclusive right to sell the Property described in Exhibit A."],
            header_text=None,
            footer_text="DRAFT -- [Property] Listing Agreement Template",
        )
        rc, out = run_cli(p)
        self.assertIn("] L24 ", out, out)
        self.assertIn("template residue", out.lower(), out)
        self.assertIn("DRAFT", out, out)

    def test_l24_fires_on_footer_only_residue_json_mode(self):
        """Same fixture, asserted through --json instead of stdout scraping —
        a more robust check that L24 specifically is in the failures list
        (not just that *some* text resembling the phrase appears anywhere in
        human-readable output)."""
        import json
        p = make_docx(
            self.tmp / "footer_residue_json.docx",
            ["LISTING AGREEMENT FOR SALE between Owner and Broker, an "
             "exclusive right to sell the Property described in Exhibit A."],
            header_text=None,
            footer_text="DRAFT -- [Property] Listing Agreement Template",
        )
        rc, out = run_cli(p, "--json")
        payload = json.loads(out)
        self.assertEqual(len(payload), 1)
        ids = [f["id"] for f in payload[0]["failures"]]
        self.assertIn("L24", ids, payload)

    def test_l24_still_fires_on_header_only_residue(self):
        """Regression coverage for the PRE-EXISTING behavior, not just the
        newly-added footer half. A template artifact left only in the header
        (the shape L24 always caught, even before this retrofit and even
        before 7e88341) must keep firing exactly as before. Footer here
        carries realistic, non-triggering brokerage boilerplate so this test
        cannot pass by accident via footer content."""
        p = make_docx(
            self.tmp / "header_residue.docx",
            ["LISTING AGREEMENT FOR SALE between Owner and Broker, an "
             "exclusive right to sell the Property described in Exhibit A."],
            header_text="A PROPOSAL FOR listing agreement for sale",
            footer_text="123 Main Street, Columbus, OH 43215  |  "
                        "Cushman & Wakefield  |  Page 1 of 6",
        )
        rc, out = run_cli(p)
        self.assertIn("] L24 ", out, out)
        self.assertIn("template residue", out.lower(), out)

    def test_l24_silent_on_a_realistic_clean_header_and_footer(self):
        """Guards the false-positive side, using a REALISTIC brokerage-form
        header and footer (property address, firm name, pagination) rather
        than an empty string — an empty-string fixture would pass trivially
        without proving anything about L24's actual quote window / match
        precision, the concern a reviewer separately raised. Both header and
        footer are populated and non-trivial; neither should trip L24."""
        p = make_docx(
            self.tmp / "clean_header_footer.docx",
            ["LISTING AGREEMENT FOR SALE between Owner and Broker, an "
             "exclusive right to sell the Property described in Exhibit A, "
             "fully negotiated and ready for execution by both parties."],
            header_text="Cushman & Wakefield  |  Listing Agreement for Sale",
            footer_text="2000-2002 Zettler Rd, Columbus, OH 43207  |  "
                        "Cushman & Wakefield  |  Page 1 of 6",
        )
        rc, out = run_cli(p)
        self.assertNotIn("] L24 ", out, out)

    def test_l24_silent_on_a_realistic_clean_footer_json_mode(self):
        """Same clean fixture, asserted through --json for robustness."""
        import json
        p = make_docx(
            self.tmp / "clean_footer_json.docx",
            ["LISTING AGREEMENT FOR SALE between Owner and Broker, an "
             "exclusive right to sell the Property described in Exhibit A, "
             "fully negotiated and ready for execution by both parties."],
            header_text="Cushman & Wakefield  |  Listing Agreement for Sale",
            footer_text="2000-2002 Zettler Rd, Columbus, OH 43207  |  "
                        "Cushman & Wakefield  |  Page 1 of 6",
        )
        rc, out = run_cli(p, "--json")
        payload = json.loads(out)
        self.assertEqual(len(payload), 1)
        ids = [f["id"] for f in payload[0]["failures"]]
        self.assertNotIn("L24", ids, payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
