#!/usr/bin/env python3
"""
Regression tests for lease_qc.py's retrofit onto the shared ora_doc_qc module.

Stdlib only (plus reportlab, for regenerating the PDF fixture) — run with
`python lease-form-qc/tests/test_lease_qc.py`. No pytest, matching tools/test_*.py.

WHY THIS FILE EXISTS
--------------------
lease-form-qc is a live, per-outbound-lease compliance gate. Its pre-retrofit
extraction had two defects:

  1. text_of() branched on `.docx` only. Every other path — a PDF included —
     fell through to open(path, encoding='utf-8', errors='replace').read(),
     reading a PDF's binary container as prose. Measured on
     no_text_layer_fixture.pdf before the retrofit: 16 of 51 checks "FAILED",
     including 2 BLOCK, exit 1 — a catastrophic-looking verdict on a document
     the scanner never read, with nothing in the output saying so.
  2. F18 depended on text_of() splicing '\\n[[FOOTER]] ' + footer text onto the
     body unconditionally, which also leaked footer boilerplate into every
     other check's body-text matching.

The retrofit moves extraction to ora_doc_qc.extract() (real PDF handling, OCR
fallback, and a hard UNREADABLE floor) and reads meta["footer"] directly.

THE PARITY TEST IS THE CENTRE OF THIS FILE
------------------------------------------
_original_text_of() and _ORIGINAL_CHECKS below are FROZEN VERBATIM COPIES of
the pre-retrofit implementation (worktree commit 5a8a98f). They exist only so
the tests can evaluate every one of the 51 original checks the OLD way and the
NEW way over the same fixtures and assert the verdicts match. They are
reference oracles for equivalence testing — never import them, never let them
drift toward the live file, and never "fix" them.

Two check bodies could NOT be mechanically wrapped with bool_check(), because
bool_check feeds them ctx["t"] (ora_doc_qc.norm()'d) and norm() destroys the
exact signal they test. Both are caught by the parity test if regressed:

  A2  uses re.M with a '^' anchor to prove a section HEADING exists. norm()
      collapses \\s+ to single spaces, erasing every newline, so '^' can only
      match offset 0 — A2 then fires on every lease that merely mentions the
      section. Measured on the real v2.6 master: old=pass, mechanically-wrapped
      new=FAIL (HIGH). A spurious HIGH on ORA's own current paper.
  F9  tests `'\\xa0' in t`. norm() rewrites \\xa0 to a plain space, so a
      mechanically-wrapped F9 can never fire again — a silent false-negative in
      a gate whose whole purpose is catching what silently passes.

Both read ctx["raw"] (the shared module's own un-normalized body text) instead.
That is not a second extraction path: ctx["raw"] is populated by
ora_doc_qc.scan() from ora_doc_qc.extract(), same as ctx["t"], and
unfilled_token_check() in the shared module reads it the same way.
"""

import json
import os
import re
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
LEASE_QC = SCRIPTS / "lease_qc.py"
PDF_FIXTURE = HERE / "no_text_layer_fixture.pdf"
MASTER_V26 = (REPO / "masterlease-jurisdiction-rebase" / "scripts" / "fixtures"
              / "ORA_MasterLease_ShallowBayIndustrial_v2.6_TEMPLATE.docx")
# v2.7 (2026-10-06) is the clean-benchmark master: v2.6 now fails exactly the
# three v2.7-standard checks F19-F21 by design (TestV27Standards below).
MASTER_V27 = (REPO / "masterlease-jurisdiction-rebase" / "scripts" / "fixtures"
              / "ORA_MasterLease_ShallowBayIndustrial_v2.7_TEMPLATE.docx")
V27_IDS = {"F19", "F20", "F21"}

sys.path.insert(0, str(SCRIPTS))

import lease_qc                                                # noqa: E402
from ora_doc_qc import extract, norm                           # noqa: E402


# --------------------------------------------------------------------------
# Frozen pre-retrofit reference oracle (commit 5a8a98f). Do not modify.
# --------------------------------------------------------------------------

def _original_text_of(path):
    """VERBATIM copy of lease_qc.text_of() as of 5a8a98f. Reference only."""
    if path.lower().endswith('.docx'):
        with zipfile.ZipFile(path) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'replace')
            has_ins = '<w:ins ' in xml
            has_del = '<w:del ' in xml
            has_strike = 'w:strike' in xml
            has_cmt = any(n.endswith('word/comments.xml') for n in z.namelist())
            ftr = ''.join(z.read(n).decode('utf-8', 'replace')
                          for n in z.namelist() if re.search(r'word/footer\d*\.xml$', n))
        t = re.sub(r'<w:p[ >]', '\n<w:p ', xml)
        t = re.sub(r'<[^>]+>', '', t)
        for a, b in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                     ('&quot;', '"'), ('&apos;', "'")]:
            t = t.replace(a, b)
        ftr_t = re.sub(r'<[^>]+>', '', ftr)
        t += '\n[[FOOTER]] ' + ftr_t
    else:
        t = open(path, encoding='utf-8', errors='replace').read()
        has_ins = has_del = has_strike = has_cmt = False
    return re.sub(r'[ \t]+', ' ', t), (has_ins, has_del, has_strike, has_cmt)


_OQ = '["“”‘’«»]'


def _orig_defined(t, term):
    return bool(re.search(_OQ + r'\s*' + term + r'\s*' + _OQ + r'\s*(shall\s+)?means?\b', t))


# The 51 pre-retrofit (id, test) pairs, lambdas copied verbatim from 5a8a98f.
_ORIGINAL_CHECKS = [
    ("A1", lambda t: len({z for z in re.findall(r'\b4\d{4}\b', t)} - {'43215'}) > 1),
    ("A6", lambda t: not re.search(r'reconcil', t, re.I)),
    ("A7", lambda t: bool(re.search(r'net base rent', t, re.I)) and bool(re.search(r'increase over base year', t, re.I))),
    ("A11", lambda t: bool(re.search(r'audited by a certified public accountant', t, re.I))),
    ("B7", lambda t: not re.search(r'TENANT NOTICE ADDRESS|Tenant.{0,40}notice address', t, re.I)),
    ("A2", lambda t: 'RIGHTS RESERVED BY LANDLORD' in t.upper()
                     and not re.search(r'^\s*RIGHTS RESERVED BY LANDLORD\.', t, re.M | re.I)),
    ("A2b", lambda t: bool(re.search(r'entitled[,]?\s*[""]?\s*INSPECTIONS,\s*REPAIRS', t, re.I))
                      or bool(re.search(r'REPAIRS AND INSTALLATION[,""]', t))),
    ("A3", lambda t: bool(re.search(r'entitled[,]?\s*[""]?\s*ALL RISK PROPERTY INSURANCE', t, re.I))),
    ("A9", lambda t: bool(re.search(r'Except as set forth in the section of this Lease entitled\s*[""]?DEFAULT OF TENANT', t, re.I))),
    ("A5a", lambda t: 'Project' in t and not _orig_defined(t, 'Project')),
    ("A5b", lambda t: 'Building' in t and not _orig_defined(t, 'Building')),
    ("A5c", lambda t: 'Business Day' in t and not _orig_defined(t, 'Business Days?')),
    ("A4a", lambda t: '9061' in t),
    ("A4b", lambda t: bool(re.search(r'49 U\.?\s?S\.?\s?C\.?\s*(Section|§)?\s*1802', t))),
    ("A8", lambda t: bool(re.search(r'If Tenant is or will be a corporation', t, re.I))),
    ("A10", lambda t: bool(re.search(r'Delay in Commencement', t, re.I))),
    ("B2", lambda t: bool(re.search(r'no obligation to relet', t, re.I))
                     and not re.search(r'required by applicable law', t, re.I)),
    ("B3", lambda t: bool(re.search(r'accelerate and recover', t, re.I))
                     and not re.search(r'net proceeds of any reletting|fair rental value', t, re.I)),
    ("B4", lambda t: bool(re.search(r'two hundred percent \(200%\) of the amount of \(a\)', t, re.I))),
    ("B5", lambda t: not re.search(r'responsible for replacement of the heating', t, re.I)),
    ("B6a", lambda t: not re.search(r'general aggregate', t, re.I)),
    ("B6b", lambda t: not re.search(r"Employer.s Liability", t, re.I)),
    ("B6c", lambda t: not re.search(r'renewal certificates|annually during the Lease Term', t, re.I)),
    ("B8", lambda t: bool(re.search(r'water sufficient for drinking', t, re.I))
                     and not re.search(r'flat rate of \$', t, re.I)),
    ("B11", lambda t: bool(re.search(r'any guarantor of this Lease', t, re.I))
                      and not re.search(r'Guaranty of Lease|GUARANTY', t)
                      and not re.search(r'any person or entity comprising Tenant', t, re.I)),
    ("C1", lambda t: not re.search(r'shall not record this Lease', t, re.I)),
    ("C2", lambda t: not re.search(r'Landlord shall not be in default', t, re.I)),
    ("C3", lambda t: not re.search(r'force majeure', t, re.I)),
    ("C4", lambda t: not re.search(r'Foreign Assets Control|OFAC', t, re.I)),
    ("C5", lambda t: not re.search(r'counterpart', t, re.I)),
    ("C6", lambda t: not re.search(r'[Tt]ime is of the essence', t)),
    ("C7", lambda t: not re.search(r'taxes and assessments levied on Tenant', t, re.I)),
    ("C8", lambda t: not re.search(r'Exhibit A', t)),
    ("F1", lambda t: 'his agents, employees and invitees' in t),
    ("F2", lambda t: bool(re.search(r'succeeding Lease or succeeding tenant', t, re.I))),
    ("F3", lambda t: 'a comparable publications' in t),
    ("F4", lambda t: 'Interior lighting' in t),
    ("F5", lambda t: bool(re.search(r'under seal', t, re.I))),
    ("F7", lambda t: bool(re.search(r'this Section \d+', t))),
    ("F8", lambda t: bool(re.search(r'eighteen percent \(18%\) per annum', t))
                     and not re.search(r'maximum rate permitted by', t, re.I)),
    ("F9", lambda t: '\xa0' in t),
    ("F10", lambda t: 'Venue for any action' not in t),
    ("F11", lambda t: 'waived pursuant to the waiver of subrogation' not in t),
    ("F12", lambda t: (('Governmental Agency' in t and not _orig_defined(t, 'Governmental Agency'))
                       or (re.search(r'[Bb]uilding [Ss]tandard', t) and not _orig_defined(t, 'Building Standard')))),
    ("F13", lambda t: 'increase over base year' in t and 'shall not include amounts separately billed' not in t),
    ("F6", lambda t: bool(re.search(r'five \(5\) Business Days following the date when due', t, re.I))
                     and not _orig_defined(t, 'Business Days?')),
    ("F14", lambda t: 'All Risk' in t and '(Special Form)' not in t),
    ("F15", lambda t: 'No other person or entity shall be liable' in t
                      and 'manager, member, officer, employee or agent of Landlord' not in t),
    ("F16", lambda t: bool(re.search(r'assign or otherwise transfer this Lease', t, re.I))
                      and 'of such excess' not in t),
    ("F17", lambda t: bool(re.search(r'serviced on a semiannual basis', t, re.I))
                      and 'preventative-maintenance contract' not in t),
    ("F18", lambda t: '[[FOOTER]]' in t and 'ORA Master Lease v' not in t.split('[[FOOTER]]')[1]),
]

_ORIGINAL_IDS = [cid for cid, _ in _ORIGINAL_CHECKS]

# A2b / A3 / A9 match an ASCII '"' character class against DOCUMENT text.
# norm() folds the curly quotes Word actually emits into ASCII ones, so these
# three become MORE sensitive after the retrofit (they start catching
# smart-quoted cross-references they used to miss). That is the check finally
# working as its author wrote it, not a regression — but it is a real behavior
# change, so it is excluded from strict parity and asserted explicitly instead
# by test_smartquote_divergence_is_intended.
_SMART_QUOTE_SENSITIVE = {"A2b", "A3", "A9"}


def _original_verdicts(path):
    """{id: bool} for all 51 checks, computed the pre-retrofit way."""
    t, _flags = _original_text_of(path)
    return {cid: bool(fn(t)) for cid, fn in _ORIGINAL_CHECKS}


def _new_verdicts(path):
    """{id: bool} for the retrofitted checks, driven through the shared ctx."""
    body, meta = extract(path, want_footer=True)
    if body is None:
        raise AssertionError(f"fixture {path} extracted as UNREADABLE "
                             f"({meta['words']} words); pad it past the floor")
    ctx = {"t": norm(body), "raw": body, "meta": meta,
           "name": os.path.basename(path), "allow_tokens": False,
           "is_template": "_TEMPLATE" in os.path.basename(path).upper()}
    out = {}
    for cid, _sev, _title, _pos, fn in lease_qc.CHECKS:
        if cid in ("T1", "T2", "T3", "T4", "D1", "D2") or cid in V27_IDS:   # not among the 51 originals
            continue
        out[cid] = fn(ctx) not in (None, False)
    return out


# --------------------------------------------------------------------------
# Synthetic DOCX construction
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

# ~190 words of neutral lease-ish filler. extract() drops anything under
# DEFAULT_MIN_WORDS (150) as UNREADABLE, so every synthetic DOCX must clear
# that floor or the fixture tests silently stop testing what they claim to.
_FILLER = " ".join([
    "This Lease Agreement is made and entered into by and between the parties",
    "identified in the preamble hereto, and the parties agree as follows for all",
    "purposes set forth herein and for the mutual covenants exchanged between them.",
    "The parties acknowledge that the provisions of this instrument have been",
    "reviewed and that each party has had the opportunity to consult with counsel",
    "of its own choosing prior to execution of this instrument by the parties.",
    "The recitals set forth above are incorporated into the operative provisions",
    "of this instrument by this reference as though fully rewritten herein.",
    "Any capitalized term used but not otherwise given an operative definition",
    "shall carry the meaning ordinarily ascribed to it in commercial practice.",
    "The headings used throughout this instrument are inserted for convenience",
    "of reference only and shall not affect the construction or interpretation",
    "of any provision hereof by any court of competent jurisdiction hereafter.",
    "If any provision of this instrument is held to be invalid or unenforceable",
    "by a court of competent jurisdiction, the remaining provisions shall",
    "nevertheless continue in full force and effect to the maximum extent",
    "permitted by applicable law, and the parties shall negotiate in good faith",
    "a substitute provision that most nearly achieves the intended result.",
    "This instrument may be executed and delivered in the manner the parties",
    "elect, and constitutes the entire understanding between them on its subject.",
])


def _esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def _paras(texts):
    return "".join(f"<w:p><w:r><w:t xml:space=\"preserve\">{_esc(x)}</w:t></w:r></w:p>"
                   for x in texts)


def make_docx(path, body_paras, footer_text=None, extra_parts=None, filler_first=False):
    """Write a minimal but structurally real .docx.

    body_paras: list of paragraph strings (filler is appended automatically so
    the document clears extract()'s 150-word UNREADABLE floor).
    footer_text: None omits word/footer1.xml entirely (the "document has no
    footer part at all" case); a string writes one footer paragraph.
    """
    paras = ([_FILLER] + list(body_paras)) if filler_first else (list(body_paras) + [_FILLER])
    doc = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f'<w:body>{_paras(paras)}</w:body></w:document>')
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("_rels/.rels", _RELS)
        z.writestr("word/document.xml", doc)
        if footer_text is not None:
            z.writestr("word/footer1.xml",
                       '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                       '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                       f'{_paras([footer_text])}</w:ftr>')
        for name, payload in (extra_parts or {}).items():
            z.writestr(name, payload)
    return str(path)


def run_cli(*args):
    """Invoke lease_qc.py as a subprocess. Returns (returncode, stdout+stderr)."""
    p = subprocess.run([sys.executable, str(LEASE_QC), *args],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.mkdtemp(prefix="lease_qc_test_")
        self.tmp = Path(self._td)

    def tearDown(self):
        shutil.rmtree(self._td, ignore_errors=True)


# --------------------------------------------------------------------------
# 1. Extraction / the UNREADABLE gate — the bug this retrofit exists to close
# --------------------------------------------------------------------------

class TestUnreadableGate(TempDirCase):

    def test_pdf_without_usable_text_layer_is_unreadable_not_scored(self):
        """Pre-retrofit this PDF scored 16 of 51 FAILED (2 BLOCK) at exit 1 —
        a verdict on a document the scanner never read. It must now refuse to
        return a QC result at all."""
        self.assertTrue(PDF_FIXTURE.exists(), "run build_no_text_layer_fixture.py")
        rc, out = run_cli(str(PDF_FIXTURE))
        self.assertEqual(rc, 2, f"expected exit 2 (UNREADABLE), got {rc}\n{out}")
        self.assertIn("UNREADABLE", out)
        self.assertNotIn("FAIL", out)
        # The specific mojibake findings the old code emitted must be gone.
        for stale in ("A6", "B7", "C8", "F11"):
            self.assertNotIn(f"] {stale} ", out,
                             f"{stale} still reported on an unreadable PDF:\n{out}")

    def test_unreadable_result_is_not_reported_as_clean(self):
        rc, out = run_cli(str(PDF_FIXTURE))
        self.assertNotIn("clean - no defects detected", out)
        self.assertNotEqual(rc, 0)

    def test_pdf_is_detected_as_pdf_not_read_as_utf8_text(self):
        rc, out = run_cli(str(PDF_FIXTURE))
        self.assertIn("[pdf]", out, f"format detection missing:\n{out}")

    def test_missing_file_exits_2(self):
        rc, out = run_cli(str(self.tmp / "does_not_exist.docx"))
        self.assertEqual(rc, 2)
        self.assertIn("no such file", out.lower())


# --------------------------------------------------------------------------
# 2. F18 — the marker-splicing rewrite
# --------------------------------------------------------------------------

class TestF18FooterRewrite(TempDirCase):
    """The original F18 was:

        '[[FOOTER]]' in t and 'ORA Master Lease v' not in t.split('[[FOOTER]]')[1]

    text_of() appended '\\n[[FOOTER]] ' + footer_text UNCONDITIONALLY for every
    .docx, so clause 1 was True for every .docx and False for every non-docx
    (which never got a marker). Clause 2 then asked whether the version tag
    appeared after the marker — and with no footer part the tail is empty,
    which does not contain the tag, so F18 fired.

    Hand-derived truth table for the original:
        docx, footer has tag        -> False (pass)
        docx, footer lacks tag      -> True  (fail)
        docx, no footer part at all -> True  (fail)   [empty tail lacks the tag]
        non-docx                    -> False (pass)   [no marker ever appended]

    The rewrite (`meta["format"] != "docx"` -> pass, else tag-in-meta["footer"])
    must reproduce all four rows. Each is asserted below against the FROZEN
    original as well as against the expected literal, so the derivation is
    machine-checked rather than argued.
    """

    def _f18(self, path):
        return _new_verdicts(path)["F18"]

    def test_docx_footer_with_version_tag_passes(self):
        p = make_docx(self.tmp / "with_tag.docx", ["LEASE AGREEMENT"],
                      footer_text="123 Main St - Tenant LLC - ORA Master Lease v2.6 - August 2026")
        self.assertFalse(self._f18(p))
        self.assertEqual(self._f18(p), _original_verdicts(p)["F18"])

    def test_docx_footer_without_version_tag_fails(self):
        p = make_docx(self.tmp / "no_tag.docx", ["LEASE AGREEMENT"],
                      footer_text="123 Main St - Tenant LLC - Page 1 of 19")
        self.assertTrue(self._f18(p))
        self.assertEqual(self._f18(p), _original_verdicts(p)["F18"])

    def test_docx_with_no_footer_part_at_all_fails(self):
        """The subtle row. The old marker was appended even with no footer, so
        the tail was empty and F18 fired. meta["footer"] defaults to "" and ""
        does not contain the tag, so the rewrite fires too."""
        p = make_docx(self.tmp / "no_footer.docx", ["LEASE AGREEMENT"], footer_text=None)
        with zipfile.ZipFile(p) as z:
            self.assertFalse([n for n in z.namelist() if re.match(r"word/footer\d*\.xml", n)],
                             "fixture was supposed to have no footer part")
        self.assertTrue(self._f18(p))
        self.assertEqual(self._f18(p), _original_verdicts(p)["F18"])

    def test_docx_with_empty_footer_text_fails(self):
        p = make_docx(self.tmp / "empty_footer.docx", ["LEASE AGREEMENT"], footer_text="")
        self.assertTrue(self._f18(p))
        self.assertEqual(self._f18(p), _original_verdicts(p)["F18"])

    def test_non_docx_never_fires(self):
        p = self.tmp / "lease.txt"
        p.write_text("LEASE AGREEMENT\n" + _FILLER, encoding="utf-8")
        self.assertFalse(self._f18(str(p)))
        self.assertEqual(self._f18(str(p)), _original_verdicts(str(p))["F18"])

    def test_real_master_lease_footer_carries_the_tag(self):
        self.assertTrue(MASTER_V26.exists())
        self.assertFalse(self._f18(str(MASTER_V26)))

    def test_footer_text_is_no_longer_spliced_into_the_body(self):
        """The marker hack leaked footer boilerplate into every check's body
        text. ctx["t"]/ctx["raw"] must now be footer-free."""
        marker = "ZZQQ FOOTERONLY SENTINEL PHRASE"
        p = make_docx(self.tmp / "sentinel.docx", ["LEASE AGREEMENT"], footer_text=marker)
        body, meta = extract(p, want_footer=True)
        self.assertIn(marker, meta["footer"])
        self.assertNotIn(marker, body)
        self.assertNotIn("[[FOOTER]]", body)
        self.assertNotIn(marker, norm(body))


# --------------------------------------------------------------------------
# 3. The two checks that could NOT be mechanically wrapped
# --------------------------------------------------------------------------

class TestNormalizationSensitiveChecks(TempDirCase):

    def test_A2_does_not_false_positive_when_the_heading_exists(self):
        """A2 flags a DEAD cross-reference. With the heading present it must
        stay silent. A bool_check()-wrapped A2 reading norm()'d text fires
        here, because norm() erases the newlines its '^' anchor needs."""
        p = make_docx(self.tmp / "a2_ok.docx", [
            # The heading must NOT be the first paragraph. With it at offset 0
            # a naive '^' matches even without re.M, and the fixture would
            # accidentally hide the very regression it is meant to expose.
            "LEASE AGREEMENT made as of the date first written above.",
            "RIGHTS RESERVED BY LANDLORD. Landlord reserves the rights described below.",
            "As set forth in the section entitled RIGHTS RESERVED BY LANDLORD, Landlord may enter.",
        ])
        self.assertFalse(_new_verdicts(p)["A2"])
        self.assertEqual(_new_verdicts(p)["A2"], _original_verdicts(p)["A2"])
        # Prove the mechanical wrap really would have regressed here.
        body, _m = extract(p)
        mechanical = dict(_ORIGINAL_CHECKS)["A2"](norm(body))
        self.assertTrue(mechanical,
                        "expected the naive norm()'d A2 to false-positive; if this "
                        "assertion fails the deviation may no longer be needed")

    def test_A2_still_fires_when_the_heading_is_absent(self):
        p = make_docx(self.tmp / "a2_dead.docx", [
            "As set forth in the section entitled RIGHTS RESERVED BY LANDLORD, Landlord may enter.",
        ])
        self.assertTrue(_new_verdicts(p)["A2"])
        self.assertEqual(_new_verdicts(p)["A2"], _original_verdicts(p)["A2"])

    def test_A2_silent_when_the_phrase_is_absent_entirely(self):
        p = make_docx(self.tmp / "a2_absent.docx", ["LEASE AGREEMENT"])
        self.assertFalse(_new_verdicts(p)["A2"])

    def test_F9_still_detects_non_breaking_spaces(self):
        """norm() rewrites \\xa0 to a plain space, so a bool_check()-wrapped F9
        can never fire. F9 must read ctx["raw"]."""
        p = make_docx(self.tmp / "f9_nbsp.docx",
                      ["Base Rent shall be   payable monthly in advance."])
        self.assertTrue(_new_verdicts(p)["F9"])
        self.assertEqual(_new_verdicts(p)["F9"], _original_verdicts(p)["F9"])
        body, _m = extract(p)
        self.assertFalse(dict(_ORIGINAL_CHECKS)["F9"](norm(body)),
                         "expected the naive norm()'d F9 to be blind to nbsp; if this "
                         "assertion fails the deviation may no longer be needed")

    def test_F9_silent_when_no_non_breaking_spaces(self):
        p = make_docx(self.tmp / "f9_clean.docx", ["Base Rent shall be payable monthly."])
        self.assertFalse(_new_verdicts(p)["F9"])
        self.assertEqual(_new_verdicts(p)["F9"], _original_verdicts(p)["F9"])

    def test_smartquote_divergence_is_intended(self):
        """A3 (and A2b/A9) match an ASCII '"' class against document text.
        Word emits curly quotes; norm() folds them to ASCII. The retrofit
        therefore starts catching smart-quoted dead cross-references the old
        code silently missed. Documented widening, asserted so it cannot change
        again unnoticed."""
        p = make_docx(self.tmp / "a3_smart.docx", [
            "as more particularly set forth in the section entitled "
            "“ALL RISK PROPERTY INSURANCE” of this Lease.",
        ])
        self.assertFalse(_original_verdicts(p)["A3"],
                         "pre-retrofit A3 was blind to curly quotes")
        self.assertTrue(_new_verdicts(p)["A3"],
                        "post-retrofit A3 should catch the curly-quoted reference")

    def test_F6_nbsp_folding_repairs_a_pre_existing_false_negative(self):
        """ORA's own paper writes the late-fee trigger as "five\\xa0(5) Business
        Days ...". F6's pattern has a plain space, and the pre-retrofit
        pipeline never folded \\xa0, so F6 silently never fired — measured on 8
        of the 10 real executed leases regression-tested for this retrofit.
        norm() folds it, so F6 now reports the defect it was written to catch.
        Widening, and correct: A5c independently confirms 'Business Day' is
        undefined in those same leases."""
        p = make_docx(self.tmp / "f6_nbsp.docx", [
            "A late charge accrues five (5) Business Days following the "
            "date when due, without further notice to Tenant.",
        ])
        self.assertFalse(_original_verdicts(p)["F6"],
                         "pre-retrofit F6 was blind to the nbsp")
        self.assertTrue(_new_verdicts(p)["F6"])

    def test_defined_term_detection_survives_quote_folding(self):
        """_defined()'s Q class contains both curly and ASCII double quotes, so
        folding is a no-op for the normal (double-quoted) definition style used
        throughout ORA paper. A5b must agree before and after."""
        p = make_docx(self.tmp / "defined.docx", [
            "The “Building” means the structure located at 123 Main Street.",
            "Tenant shall not alter the Building without consent.",
        ])
        self.assertFalse(_new_verdicts(p)["A5b"])
        self.assertEqual(_new_verdicts(p)["A5b"], _original_verdicts(p)["A5b"])


# --------------------------------------------------------------------------
# 4. Full 51-check parity against the frozen original
# --------------------------------------------------------------------------

class TestFullParity(TempDirCase):
    """The load-bearing test. Any check whose retrofitted verdict drifts from
    the pre-retrofit verdict on any fixture shows up here, named."""

    def _parity(self, path, label):
        old, new = _original_verdicts(path), _new_verdicts(path)
        self.assertEqual(set(old), set(new), "check-ID sets diverged")
        drift = {cid: (old[cid], new[cid]) for cid in old
                 if old[cid] != new[cid] and cid not in _SMART_QUOTE_SENSITIVE}
        self.assertEqual(drift, {},
                         f"{label}: retrofitted verdicts drifted from the frozen "
                         f"original (id: (old, new)) -> {drift}")

    def test_parity_on_the_real_v26_master_lease(self):
        self.assertTrue(MASTER_V26.exists(), f"missing fixture {MASTER_V26}")
        self._parity(str(MASTER_V26), "ORA Master Lease v2.6 TEMPLATE")

    def test_parity_on_a_defect_laden_synthetic_lease(self):
        p = make_docx(self.tmp / "dirty.docx", [
            "LEASE AGREEMENT for the premises at 123 Main Street, Columbus, Ohio 43215.",
            "The property is also described as being located in 44113 and 45202.",
            "Tenant shall pay net base rent equal to the increase over base year amounts.",
            "Tenant shall deliver statements audited by a certified public accountant.",
            "As set forth in the section entitled RIGHTS RESERVED BY LANDLORD, Landlord may enter.",
            "Pursuant to 42 U.S.C. 9061 and 49 U.S.C. 1802 the Tenant shall comply.",
            "If Tenant is or will be a corporation, Tenant shall deliver a resolution.",
            "Delay in Commencement shall not extend the Term.",
            "Landlord shall have no obligation to relet the Premises.",
            "Landlord may accelerate and recover all rent for the balance of the Term.",
            "his agents, employees and invitees shall have access at all times.",
            "This Lease is executed under seal by the parties as of the date first written.",
            "Nothing in this Section 14 shall limit the foregoing.",
            "Interest shall accrue at eighteen percent (18%) per annum on late amounts.",
            "Tenant shall maintain All Risk property insurance during the Term.",
            "Tenant shall not assign or otherwise transfer this Lease without consent.",
            "The HVAC shall be serviced on a semiannual basis by a licensed contractor.",
            "The Project and the Building shall be maintained in Building Standard condition.",
            "Late charges accrue five (5) Business Days following the date when due.",
            "Tenant shall pay a flat rate of $50 for water sufficient for drinking purposes.",
            "No other person or entity shall be liable for Landlord's obligations.",
        ], footer_text="123 Main Street - Page 1")
        self._parity(p, "defect-laden synthetic lease")

    def test_parity_on_a_minimal_clean_synthetic_lease(self):
        p = make_docx(self.tmp / "sparse.docx", ["LEASE AGREEMENT"],
                      footer_text="ORA Master Lease v2.6")
        self._parity(p, "sparse synthetic lease")

    def test_parity_on_plain_text_input(self):
        p = self.tmp / "historical_lease.txt"
        p.write_text(
            "LEASE AGREEMENT\nTENANT NOTICE ADDRESS: 1 Elm St.\n"
            "Landlord shall not be in default unless notice is given.\n" + _FILLER,
            encoding="utf-8")
        self._parity(str(p), "plain-text historical lease")

    def test_parity_on_a_nbsp_and_heading_bearing_lease(self):
        """Exercises A2 and F9 together inside the parity harness."""
        p = make_docx(self.tmp / "combo.docx", [
            "RIGHTS RESERVED BY LANDLORD. Landlord reserves the following rights.",
            "See the section entitled RIGHTS RESERVED BY LANDLORD for details.",
            "Base Rent of  $5,000 shall be payable monthly in advance.",
        ], footer_text="ORA Master Lease v2.6")
        self._parity(p, "nbsp + heading lease")


# --------------------------------------------------------------------------
# 5. T1 — now a first-class registered check
# --------------------------------------------------------------------------

class TestTokenGate(TempDirCase):

    def _dirty(self, name):
        return make_docx(self.tmp / name, [
            "LEASE AGREEMENT between [LANDLORD ENTITY] and [TENANT ENTITY].",
            "The premises are located at [PREMISES ADDRESS] in [CITY, STATE].",
        ], footer_text="ORA Master Lease v2.6")

    def test_t1_is_registered_once_in_the_static_registry(self):
        ids = [c[0] for c in lease_qc.CHECKS]
        self.assertEqual(ids.count("T1"), 1)

    def test_unfilled_tokens_block_a_non_template_file(self):
        rc, out = run_cli(self._dirty("draft_lease.docx"))
        self.assertEqual(rc, 1, out)
        self.assertIn("T1", out)
        self.assertIn("BLOCK", out)

    def test_allow_tokens_suppresses_the_block(self):
        rc, out = run_cli(self._dirty("draft_lease2.docx"), "--allow-tokens")
        self.assertNotIn("] T1 ", out, out)

    def test_template_filename_suppresses_the_block(self):
        rc, out = run_cli(self._dirty("ORA_Lease_v9_TEMPLATE.docx"))
        self.assertNotIn("] T1 ", out, out)

    def test_local_token_regex_is_preserved_not_the_shared_default(self):
        """This file's TOKEN_RE is r"\\[[A-Z][A-Z0-9 /,.'&-]{2,}\\]" — no
        underscore in the class and no 40-char cap. The shared module's default
        pattern has both. Swapping would be an unverified behavior change, so
        assert the local one is still in force: an underscored token must NOT
        match, and a >40-char token MUST."""
        self.assertEqual(lease_qc.TOKEN_RE.pattern, r"\[[A-Z][A-Z0-9 /,.'&-]{2,}\]")
        self.assertIsNone(lease_qc.TOKEN_RE.search("[TENANT_ENTITY]"))
        long_tok = "[" + "A" * 45 + "]"
        self.assertIsNotNone(lease_qc.TOKEN_RE.search(long_tok))
        # and the registered check actually uses it
        p = make_docx(self.tmp / "underscore.docx",
                      ["LEASE AGREEMENT between [LANDLORD_ENTITY] and Tenant."],
                      footer_text="ORA Master Lease v2.6")
        rc, out = run_cli(p)
        self.assertNotIn("] T1 ", out, out)

    def test_t1_no_longer_fires_on_the_scanners_own_footer_marker(self):
        """The most consequential thing this retrofit fixes after the PDF bug.

        text_of() appended '[[FOOTER]]' to EVERY .docx, and TOKEN_RE
        (\\[[A-Z][A-Z0-9 /,.'&-]{2,}\\]) happily matched the inner '[FOOTER]'.
        Across all ten real executed ORA leases regression-tested for this
        retrofit, '[FOOTER]' was the ONLY token the old T1 ever found — i.e.
        the live pre-signature gate raised a spurious BLOCK on its own marker
        for every non-_TEMPLATE lease it had ever scanned, and a reader had to
        know to ignore it. No marker, no false BLOCK."""
        p = make_docx(self.tmp / "fully_filled_lease.docx",
                      ["LEASE AGREEMENT between Acme Holdings LLC and Beta Tools LLC.",
                       "The premises are 4,200 square feet at 123 Main Street."],
                      footer_text="123 Main Street - Page 1 of 19")
        old_t, _flags = _original_text_of(p)
        self.assertEqual(sorted(set(lease_qc.TOKEN_RE.findall(old_t))), ["[FOOTER]"],
                         "fixture should carry no real tokens, only the old marker")
        rc, out = run_cli(p)
        # Other BLOCKs (A6/B7) legitimately fire on so sparse a fixture; only
        # the token gate is under test here.
        self.assertNotIn("] T1 ", out, out)
        self.assertNotIn("Unfilled template tokens", out, out)

    def test_master_template_is_clean_including_t1(self):
        rc, out = run_cli(str(MASTER_V27))
        self.assertEqual(rc, 0, out)
        self.assertIn("0 of 60 checks FAILED", out)

    # ---- T1 must scan the FOOTER, not only the body -----------------------
    #
    # The retrofit's removal of text_of()'s '[[FOOTER]]' splice fixed a real
    # false BLOCK (above) but, registered via the shared
    # unfilled_token_check(), it also silently dropped the footer from T1's
    # coverage: that helper reads ctx["raw"] only, and extract(want_footer=True)
    # routes footer text to ctx["meta"]["footer"]. lease_qc._t1 restores it.

    # Real footer text of ORA's own v2.6 master (word/footer2.xml and
    # word/footer3.xml), tokens and all.
    _REAL_TEMPLATE_FOOTER = ("[PREMISES ADDRESS]  •  [TENANT ENTITY]  "
                             "•  Page 3 of 19  •  "
                             "ORA Master Lease v2.6 – August 2026")

    def test_the_real_master_template_footer_really_does_carry_tokens(self):
        """Premise check for the two tests below — if ORA ever detokenizes the
        master's footer this stops being a live hazard, and this test says so
        rather than letting the others quietly test nothing."""
        _body, meta = extract(str(MASTER_V26), want_footer=True)
        found = sorted(set(lease_qc.TOKEN_RE.findall(meta["footer"])))
        self.assertIn("[PREMISES ADDRESS]", found, meta["footer"][:300])
        self.assertIn("[TENANT ENTITY]", found, meta["footer"][:300])

    def test_unfilled_footer_tokens_block_a_filled_body_lease(self):
        """THE regression this deviation exists to prevent.

        A lease drafted from the v2.6 master with the BODY filled in and the
        FOOTER left untouched. Under a body-only T1 it scores clean on the
        token gate and goes out for signature with '[PREMISES ADDRESS]' and
        '[TENANT ENTITY]' printed on every page."""
        p = make_docx(self.tmp / "Lease_AcmeHoldings_08172026.docx", [
            "LEASE AGREEMENT between Oxford Realty Advisors LLC and Acme Holdings LLC.",
            "The premises are 4,200 square feet at 123 Main Street, Columbus, Ohio.",
        ], footer_text=self._REAL_TEMPLATE_FOOTER)

        # The body itself is clean — this is not a body-token test in disguise.
        body, meta = extract(p, want_footer=True)
        self.assertEqual(lease_qc.TOKEN_RE.findall(body), [],
                         "fixture body was supposed to be fully filled")
        self.assertTrue(lease_qc.TOKEN_RE.findall(meta["footer"]))

        rc, out = run_cli(p)
        self.assertEqual(rc, 1, out)
        self.assertIn("] T1 ", out, out)
        self.assertIn("BLOCK", out)
        self.assertIn("[PREMISES ADDRESS]", out, out)
        self.assertIn("[TENANT ENTITY]", out, out)
        self.assertIn("2 unfilled token(s)", out, out)

    def test_the_shared_body_only_helper_would_have_missed_it(self):
        """Pins WHY T1 is not registered via unfilled_token_check(): run the
        shared helper over the same ctx and show it returns clean. If the
        shared helper ever learns to read meta["footer"], this test fails and
        the local _t1 can be retired — which is the point."""
        from ora_doc_qc import unfilled_token_check
        p = make_docx(self.tmp / "footer_tokens_only.docx", [
            "LEASE AGREEMENT between Oxford Realty Advisors LLC and Acme Holdings LLC.",
            "The premises are 4,200 square feet at 123 Main Street, Columbus, Ohio.",
        ], footer_text=self._REAL_TEMPLATE_FOOTER)
        body, meta = extract(p, want_footer=True)
        ctx = {"t": norm(body), "raw": body, "meta": meta,
               "name": os.path.basename(p), "allow_tokens": False,
               "is_template": False}

        shared_fn = unfilled_token_check(pattern=lease_qc.TOKEN_RE.pattern)[4]
        self.assertIsNone(shared_fn(ctx),
                          "shared helper unexpectedly saw the footer — "
                          "if it now reads meta['footer'], retire lease_qc._t1")

        local_fn = {c[0]: c[4] for c in lease_qc.CHECKS}["T1"]
        self.assertIsNotNone(local_fn(ctx))

    def test_footer_scanning_does_not_reintroduce_the_false_block(self):
        """Re-verification of the original fix, now that T1 reads the footer
        again. A lease with a filled body AND a filled footer — the real
        template footer with its tokens replaced — must NOT fire T1. The old
        '[[FOOTER]]' marker that used to trip it is gone entirely, so there is
        no artifact left for the widened scan to match."""
        filled_footer = ("123 Main Street, Columbus, Ohio  •  "
                         "Acme Holdings LLC  •  Page 3 of 19  •  "
                         "ORA Master Lease v2.6 – August 2026")
        p = make_docx(self.tmp / "Lease_AcmeHoldings_filled.docx", [
            "LEASE AGREEMENT between Oxford Realty Advisors LLC and Acme Holdings LLC.",
            "The premises are 4,200 square feet at 123 Main Street, Columbus, Ohio.",
        ], footer_text=filled_footer)
        body, meta = extract(p, want_footer=True)
        self.assertNotIn("[[FOOTER]]", body)
        self.assertNotIn("[FOOTER]", body + meta["footer"])
        rc, out = run_cli(p)
        self.assertNotIn("] T1 ", out, out)
        self.assertNotIn("Unfilled template tokens", out, out)

    def test_footer_tokens_still_honor_both_gates(self):
        """--allow-tokens and the _TEMPLATE filename must suppress a
        footer-sourced BLOCK exactly as they do a body-sourced one — the gate
        logic is copied from the shared helper, so prove the copy is faithful."""
        body_paras = ["LEASE AGREEMENT between Oxford Realty Advisors LLC and Acme Holdings LLC.",
                      "The premises are 4,200 square feet at 123 Main Street, Columbus, Ohio."]
        p1 = make_docx(self.tmp / "draft_footer_tokens.docx", body_paras,
                       footer_text=self._REAL_TEMPLATE_FOOTER)
        rc, out = run_cli(p1, "--allow-tokens")
        self.assertNotIn("] T1 ", out, out)

        p2 = make_docx(self.tmp / "ORA_Lease_v9_TEMPLATE.docx", body_paras,
                       footer_text=self._REAL_TEMPLATE_FOOTER)
        rc, out = run_cli(p2)
        self.assertNotIn("] T1 ", out, out)


# --------------------------------------------------------------------------
# 6. Registry integrity + CLI contract
# --------------------------------------------------------------------------

class TestRegistryAndCli(TempDirCase):

    def test_registry_holds_the_51_original_checks_plus_t1_t2_and_v28_additions(self):
        ids = [c[0] for c in lease_qc.CHECKS]
        self.assertEqual(len(ids), 60)
        self.assertEqual(len(set(ids)), 60, "duplicate check IDs")
        self.assertEqual(set(ids), set(_ORIGINAL_IDS) | {"T1", "T2", "T3", "T4", "D1", "D2"} | V27_IDS)

    def test_every_entry_is_a_valid_five_tuple(self):
        for entry in lease_qc.CHECKS:
            self.assertEqual(len(entry), 5, entry)
            cid, sev, title, pos, fn = entry
            self.assertIsInstance(cid, str)
            self.assertIn(sev, ("BLOCK", "HIGH", "MED", "LOW"))
            self.assertTrue(title and isinstance(title, str))
            self.assertIsNone(pos, f"{cid}: lease-form-qc has no standing-positions doc")
            self.assertTrue(callable(fn))

    def test_severities_match_the_frozen_original(self):
        src = subprocess.run(
            ["git", "show", "5a8a98f:lease-form-qc/scripts/lease_qc.py"],
            cwd=str(REPO), capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(src.returncode, 0, src.stderr)
        old_sev = dict(re.findall(r'\("([A-Z0-9a-z]+)","(BLOCK|HIGH|MED|LOW)"', src.stdout))
        self.assertEqual(len(old_sev), 51)
        new_sev = {c[0]: c[1] for c in lease_qc.CHECKS}
        for cid, sev in old_sev.items():
            self.assertEqual(new_sev.get(cid), sev, f"{cid} severity changed")

    def test_titles_match_the_frozen_original(self):
        src = subprocess.run(
            ["git", "show", "5a8a98f:lease-form-qc/scripts/lease_qc.py"],
            cwd=str(REPO), capture_output=True, text=True, encoding="utf-8")
        old_titles = dict(re.findall(r'\("([A-Z0-9a-z]+)","(?:BLOCK|HIGH|MED|LOW)","([^"]+)"',
                                     src.stdout))
        self.assertEqual(len(old_titles), 51)
        new_titles = {c[0]: c[2] for c in lease_qc.CHECKS}
        for cid, title in old_titles.items():
            self.assertEqual(new_titles.get(cid), title, f"{cid} label changed")

    def test_clean_document_exits_0(self):
        rc, out = run_cli(str(MASTER_V27))
        self.assertEqual(rc, 0, out)

    def test_failing_document_exits_1(self):
        p = make_docx(self.tmp / "fail.docx", ["LEASE AGREEMENT"])
        rc, out = run_cli(p)
        self.assertEqual(rc, 1, out)

    def test_no_arguments_exits_nonzero(self):
        rc, out = run_cli()
        self.assertNotEqual(rc, 0)

    def test_json_mode_emits_parsable_output(self):
        import json
        rc, out = run_cli(str(MASTER_V27), "--json")
        payload = json.loads(out)
        self.assertEqual(len(payload), 1)
        self.assertEqual(payload[0]["checks_run"], 60)
        self.assertFalse(payload[0]["unreadable"])
        self.assertEqual(payload[0]["failures"], [])

    def test_report_states_the_revision_encoding(self):
        """SKILL.md Step 2 requires the detected encoding at the top of every
        report. The shared print_report() supplies the ENC line."""
        rc, out = run_cli(str(MASTER_V26))
        self.assertIn("ENC", out)
        self.assertIn("comments.xml", out)

    def test_module_imports_nothing_from_a_local_extraction_path(self):
        """The retrofit's whole point: no bespoke text_of() may come back.

        Matched against EXECUTABLE code only. The module and _f18 docstrings
        legitimately quote the removed '[[FOOTER]]' marker to explain what was
        replaced; a naive substring scan would punish the file for documenting
        its own history, so comments and triple-quoted strings are stripped
        first."""
        import io
        import tokenize
        full = LEASE_QC.read_text(encoding="utf-8")
        kept = []
        for tok in tokenize.generate_tokens(io.StringIO(full).readline):
            if tok.type == tokenize.COMMENT:
                continue
            if tok.type == tokenize.STRING and tok.string.lstrip("rbuRBUf")[:3] in ('"""', "'''"):
                continue
            kept.append(tok.string)
        code = "\n".join(kept)
        # zipfile/ZipFile were banned with the retrofit; v2.8's T4 uses them ONLY
        # to count word/media/ parts (ctx carries no drawing signal) -- never to
        # extract text, which is what this guard exists to keep out.
        for banned in ("def text_of", "[[FOOTER]]"):
            self.assertFalse(banned in code,
                             f"{banned!r} is back in lease_qc.py's executable code")
        self.assertIn("ora_doc_qc", code)

    def test_ora_doc_qc_resolves_to_the_repo_root_canonical_copy(self):
        """2026-08-17 retrofit: pma-qc, listing-agreement-qc, and lease-form-qc no
        longer vendor their own committed copy of ora_doc_qc.py -- it fans out from
        tools/ora_doc_qc.py at packaging time via package_skills.py's
        SHARED_ROOT_DEPS (landing at scripts/ora_doc_qc.py inside the packaged
        .skill). In a dev checkout with no packaged copy present, lease_qc.py's own
        sys.path fallback (see its module docstring) must resolve the import to the
        canonical repo-root copy -- not silently fail, and not pick up a stray
        leftover file that would then drift unnoticed. Replaces the old drift-check
        (hash-compared two committed copies) now that there is only ever one."""
        import ora_doc_qc
        self.assertFalse(
            (SCRIPTS / "ora_doc_qc.py").exists(),
            "in-skill vendored copy should no longer be committed -- "
            "see package_skills.SHARED_ROOT_DEPS")
        self.assertEqual(
            Path(ora_doc_qc.__file__).resolve(),
            (REPO / "tools" / "ora_doc_qc.py").resolve(),
            "ora_doc_qc import did not resolve to the repo-root canonical copy")


# --------------------------------------------------------------------------
# 6b. T2 -- footer FILENAME/DOCPROPERTY tenant-mismatch (lease-generation handoff)
# --------------------------------------------------------------------------

def _field_footer_xml(paragraphs_xml):
    """Raw word/footerN.xml body -- same shape make_docx()'s own footer_text
    path writes, but with caller-supplied paragraph XML instead of a single
    plain-text run. Written via make_docx()'s extra_parts= (with
    footer_text=None, so make_docx does not also write its own
    word/footer1.xml and collide)."""
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            + paragraphs_xml + '</w:ftr>')


def _complex_field_para(instr, result_text):
    """One footer <w:p> holding a COMPLEX Word field
    (fldChar begin/instrText/separate/result/end) -- the kind T2 can see.
    `instr` is the raw field instruction text, e.g. ' FILENAME  \\* MERGEFORMAT '
    or ' DOCPROPERTY "TenantName" \\* MERGEFORMAT '."""
    return (
        '<w:p>'
        '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
        f'<w:r><w:instrText xml:space="preserve">{_esc(instr)}</w:instrText></w:r>'
        '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
        f'<w:r><w:t>{_esc(result_text)}</w:t></w:r>'
        '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
        '</w:p>'
    )


class TestT2FooterTenantMismatch(TempDirCase):
    """T2's three required behaviors per the lease-generation handoff:
    a footer FILENAME/DOCPROPERTY field naming a DIFFERENT tenant BLOCKs;
    no such field at all (lease-generation's own output, which replaces the
    field with static text) passes cleanly; and a field matching ANY one
    name in a co-tenant list does not false-fire (ratified position 2 --
    co-tenants, never a guaranty)."""

    _ACME_BODY = [
        'THIS LEASE AGREEMENT is made and entered into by and between '
        '2203 Northwood, LLC ("Landlord") and Acme Holdings LLC ("Tenant").',
        'Tenant shall use the Premises for general office and warehouse purposes.',
    ]

    def test_filename_field_naming_a_different_tenant_blocks(self):
        p = self.tmp / "Lease_AcmeHoldings_09072026.docx"
        make_docx(p, self._ACME_BODY, footer_text=None, extra_parts={
            "word/footer1.xml": _field_footer_xml(_complex_field_para(
                ' FILENAME  \\* MERGEFORMAT ', 'Lease_BetaTools_09072026.docx')),
        })
        rc, out = run_cli(str(p))
        self.assertEqual(rc, 1, out)
        self.assertIn("] T2 ", out, out)
        self.assertIn("BLOCK", out)
        self.assertIn("BetaTools", out, out)
        self.assertIn("Acme Holdings LLC", out, out)

    def test_docproperty_field_naming_a_different_tenant_blocks(self):
        p = self.tmp / "some_lease.docx"
        make_docx(p, self._ACME_BODY, footer_text=None, extra_parts={
            "word/footer1.xml": _field_footer_xml(_complex_field_para(
                ' DOCPROPERTY "TenantName" \\* MERGEFORMAT ', 'Beta Tools LLC')),
        })
        rc, out = run_cli(str(p))
        self.assertEqual(rc, 1, out)
        self.assertIn("] T2 ", out, out)
        self.assertIn('DOCPROPERTY "TenantName"', out, out)

    def test_unquoted_docproperty_name_naming_a_different_tenant_blocks(self):
        """Word writes a custom property name unquoted just as often as
        quoted (' DOCPROPERTY  TenantName  \\* MERGEFORMAT ...'). The
        quoted-only parse silently never matched this form -- caught in
        independent re-review -- leaving the tenant-labeled-property gate
        unreachable for the likely MORE common real-world encoding."""
        p = self.tmp / "some_lease.docx"
        make_docx(p, self._ACME_BODY, footer_text=None, extra_parts={
            "word/footer1.xml": _field_footer_xml(_complex_field_para(
                ' DOCPROPERTY  TenantName  \\* MERGEFORMAT ', 'Beta Tools LLC')),
        })
        rc, out = run_cli(str(p))
        self.assertEqual(rc, 1, out)
        self.assertIn("] T2 ", out, out)

    def test_no_field_in_footer_passes_cleanly(self):
        """lease-generation's own end-state: the field is replaced with
        static text. Must not fire, must not error."""
        p = self.tmp / "no_field_lease.docx"
        make_docx(p, self._ACME_BODY,
                  footer_text="2203 Northwood, LLC - Acme Holdings LLC - Page 1 of 12")
        rc, out = run_cli(str(p))
        self.assertNotIn("] T2 ", out, out)
        self.assertNotIn("does not match this lease's defined Tenant", out, out)

    def test_no_footer_part_at_all_passes_cleanly(self):
        p = self.tmp / "totally_footerless_lease.docx"
        make_docx(p, self._ACME_BODY, footer_text=None)
        rc, out = run_cli(str(p))
        self.assertNotIn("] T2 ", out, out)

    def test_field_matching_one_of_several_cotenants_does_not_false_fire(self):
        """Ratified position 2: individuals are joined as joint-and-several
        co-tenants, so "the Tenant" can legitimately be a list. A field that
        resolves to any ONE of the listed names is not stale boilerplate."""
        body = [
            'THIS LEASE AGREEMENT is made and entered into by and between '
            '2203 Northwood, LLC ("Landlord") and Acme Widget Technology LLC '
            'and Jordan Avery Example, individually (individually and collectively, "Tenant").',
            'Tenant, any person or entity comprising Tenant, or any guarantor '
            'of this Lease shall be jointly and severally liable.',
        ]
        p = self.tmp / "cotenant_lease.docx"
        make_docx(p, body, footer_text=None, extra_parts={
            "word/footer1.xml": _field_footer_xml(_complex_field_para(
                ' DOCPROPERTY "TenantName" \\* MERGEFORMAT ', 'Jordan Avery Example')),
        })
        rc, out = run_cli(str(p))
        self.assertNotIn("] T2 ", out, out)

    def test_field_matching_the_tenant_exactly_does_not_fire(self):
        p = self.tmp / "matching_lease.docx"
        make_docx(p, self._ACME_BODY, footer_text=None, extra_parts={
            "word/footer1.xml": _field_footer_xml(_complex_field_para(
                ' FILENAME  \\* MERGEFORMAT ', 'Lease_AcmeHoldings_09072026.docx')),
        })
        rc, out = run_cli(str(p))
        self.assertNotIn("] T2 ", out, out)

    # ---- false-positive surface: only a genuine tenant-slotted field may
    # fire T2. Reproduced in independent review; each of these is a
    # signature-ready lease that must NOT block. -----------------------

    def test_filename_with_no_tenant_token_after_lease_marker_does_not_fire(self):
        """'<Address> Suite <X> Lease <MM-YYYY> v0N.docx' -- an address-based
        filename with nothing in the tenant slot at all (the field was
        never filled with a tenant token to begin with)."""
        for fname in ("2203 Northwood Suite 15A Lease 09-2026 v01.docx",
                      "Northwood 15A Lease v01.docx"):
            with self.subTest(fname=fname):
                p = self.tmp / f"lease_{abs(hash(fname))}.docx"
                make_docx(p, self._ACME_BODY, footer_text=None, extra_parts={
                    "word/footer1.xml": _field_footer_xml(_complex_field_para(
                        ' FILENAME  \\* MERGEFORMAT ', fname)),
                })
                rc, out = run_cli(str(p))
                self.assertNotIn("] T2 ", out, out)

    def test_docproperty_field_not_labeled_tenant_never_fires(self):
        """An arbitrary custom DOCPROPERTY (doc ID, ORA's own company name,
        a manager, a title) is not a tenant claim just because it has some
        text value -- only a tenant/lessee-labeled property is."""
        for prop, value in (("Company", "Oxford Realty Advisors"),
                            ("DocID", "ORA-2026-0417"),
                            ("Title", "Lease Agreement"),
                            ("Manager", "Gabriel Goldberg")):
            with self.subTest(prop=prop):
                p = self.tmp / f"lease_{prop}.docx"
                make_docx(p, self._ACME_BODY, footer_text=None, extra_parts={
                    "word/footer1.xml": _field_footer_xml(_complex_field_para(
                        f' DOCPROPERTY "{prop}" \\* MERGEFORMAT ', value)),
                })
                rc, out = run_cli(str(p))
                self.assertNotIn("] T2 ", out, out)

    def test_empty_field_followed_by_page_numbering_on_the_same_line_does_not_fire(self):
        """No <w:fldChar 'end'/> delimiter survives text-stripping, so an
        EMPTY field immediately followed by page-numbering text on the same
        footer line must not have that trailing text mistaken for its
        cached result."""
        footer_xml = _field_footer_xml(
            '<w:p>'
            '<w:r><w:fldChar w:fldCharType="begin"/></w:r>'
            '<w:r><w:instrText xml:space="preserve"> FILENAME  \\* MERGEFORMAT </w:instrText></w:r>'
            '<w:r><w:fldChar w:fldCharType="separate"/></w:r>'
            '<w:r><w:fldChar w:fldCharType="end"/></w:r>'
            '<w:r><w:t xml:space="preserve"> Page 1 of 12</w:t></w:r>'
            '</w:p>')
        p = self.tmp / "empty_field_lease.docx"
        make_docx(p, self._ACME_BODY, footer_text=None,
                  extra_parts={"word/footer1.xml": footer_xml})
        rc, out = run_cli(str(p))
        self.assertNotIn("] T2 ", out, out)

    def test_master_template_footers_carry_only_page_numpage_fields_not_t2_relevant(self):
        """Premise check: the real v2.6 master's footer complex fields are
        PAGE/NUMPAGES (page numbering), never FILENAME/DOCPROPERTY -- so T2
        has nothing to catch there, and test_master_template_is_clean_
        including_t1 (0 of 57) is not accidentally vacuous for T2."""
        self.assertTrue(MASTER_V26.exists())
        _body, meta = extract(str(MASTER_V26), want_footer=True)
        self.assertEqual(lease_qc._footer_field_candidates(meta["footer"]), [])

    def test_t2_registered_once_as_block(self):
        entries = [c for c in lease_qc.CHECKS if c[0] == "T2"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][1], "BLOCK")

    def test_extract_tenant_names_handles_cotenant_list(self):
        text = ('between 2203 Northwood, LLC ("Landlord") and Acme Widget Technology LLC '
                'and Jordan Avery Example, individually (individually and collectively, "Tenant").')
        names = lease_qc._extract_tenant_names(text)
        self.assertEqual(names, ["Acme Widget Technology LLC", "Jordan Avery Example"])

    def test_extract_tenant_names_returns_empty_when_unconfident(self):
        self.assertEqual(lease_qc._extract_tenant_names("LEASE AGREEMENT with no parties clause."), [])

    def test_extract_tenant_names_no_anchor_fallback_rejects_verb_phrase_fragments(self):
        """No ('Landlord') parenthetical precedes the Tenant quote here, so
        extraction falls back to a bounded lookback window -- which must
        reject a captured fragment ('This Lease is made by') containing a
        sentence stopword, not just accept anything starting with a
        capital letter. Caught in independent review; regression-tested
        here since the original bug report exercised only the anchored
        path."""
        text = 'This Lease is made by and between Landco X, LLC and Acme Holdings LLC ("Tenant").'
        names = lease_qc._extract_tenant_names(text)
        self.assertNotIn("This Lease is made by", names)
        for n in names:
            self.assertFalse(any(w.lower() in lease_qc._TENANT_NAME_STOPWORDS for w in n.split()),
                             f"stopword survived in extracted name: {n!r}")

    def test_normalize_entity_name_strips_suffix_and_whitespace(self):
        self.assertEqual(lease_qc._normalize_entity_name("Acme Holdings LLC"),
                         lease_qc._normalize_entity_name("AcmeHoldings"))
        self.assertNotEqual(lease_qc._normalize_entity_name("Acme Holdings LLC"),
                            lease_qc._normalize_entity_name("Beta Tools LLC"))


# --------------------------------------------------------------------------
# 6c. --loi-conformance mode (lease-generation handoff)
# --------------------------------------------------------------------------

class TestLoiConformanceMode(TempDirCase):
    """Builds a register with at least one field deliberately PARTIAL, one
    MISSING, one CONFLICT, and the rest CONFORMS/CONFORMS+, and asserts
    build_conformance_matrix()/the CLI mode reports exactly that."""

    REGISTER = {
        "deal_id": "TESTPROP-5B-TEST-2026-09",
        "source_documents": [{"name": "Test LOI.pdf", "type": "LOI", "date": "2026-09-01"}],
        "landlord": {"entity": "2203 Northwood, LLC", "state_of_formation": "Maryland",
                     "notice_address": "c/o Test"},
        "tenant": {"entity": "Acme Holdings LLC", "co_tenants": []},
        "premises": {"address": "100 Test Drive", "suite": "5B", "rsf": 2400},
        "use": {"permitted_use": "office and warehouse"},
        "term": {"months": 36, "target_commencement": "2026-10-01"},
        "options": [],
        "rent": {"schedule": [{"lease_year": 1, "monthly": 2000.00}],
                 "escalation": {"type": "fixed_pct", "value": 3.0}},
        "expense_structure": {"type": "gross"},
        "utilities": {"electric": "separately_metered_tenant_direct",
                      "water_sewer": "pro_rata_building_meter"},
        "security_deposit": {"amount": 1800.00, "months": 1.0},
        "parking": {"overnight_vehicles": 4},
        "landlord_work": {"items": []},
        "maintenance": {"allocation": "ORA_form_default_tenant_hvac"},
        "insurance": {"cgl_aggregate": 2000000},
        "broker": {"dual_agency": False},
    }

    LEASE_BODY = [
        'THIS LEASE AGREEMENT is made and entered into by and between '
        '2203 Northwood, LLC ("Landlord") and Acme Holdings LLC ("Tenant").',
        'The Premises are located at 100 Test Drive, Suite 5B, containing '
        'approximately 2,400 rentable square feet.',
        'The Premises shall be used solely for office and warehouse purposes '
        'and for no other purpose without Landlord\'s prior written consent.',
        'The Term of this Lease shall be thirty-six (36) months commencing on '
        'the Commencement Date, with early access granted to Tenant for '
        'fixturing purposes prior to the Commencement Date.',
        'Base Rent for Lease Year 1 shall be $2,000.00 per month, payable in advance.',
        'Base Rent hereunder is calculated on a full-service gross basis, with '
        'no separate reconciliation of Operating Costs.',
        'Electric service to the Premises is separately metered and billed '
        'directly to Tenant. Water and sewer service is charged to Tenant as '
        'its pro rata share of the Building\'s master water meter, with sewer '
        'charges billed on the same basis.',
        'Tenant shall deposit with Landlord a Security Deposit in the amount '
        'of $2,500.00 upon execution of this Lease.',
        'Tenant shall be responsible for maintenance of the HVAC system '
        'serving the Premises.',
        'Tenant shall carry commercial general liability insurance with a '
        'general aggregate limit of $2,000,000.',
    ]

    def setUp(self):
        super().setUp()
        self.register_path = self.tmp / "register.json"
        self.register_path.write_text(json.dumps(self.REGISTER), encoding="utf-8")
        self.lease_path = make_docx(self.tmp / "test_lease.docx", self.LEASE_BODY,
                                    footer_text="Page 1 of 4")

    def test_matrix_has_the_required_status_mix(self):
        body, _meta = extract(self.lease_path)
        rows = lease_qc.build_conformance_matrix(self.REGISTER, norm(body))
        by_cat = {r["category"]: r["status"] for r in rows}
        self.assertEqual(by_cat["rent"], "PARTIAL", by_cat)
        self.assertEqual(by_cat["parking"], "MISSING", by_cat)
        self.assertEqual(by_cat["security_deposit"], "CONFLICT", by_cat)
        self.assertEqual(by_cat["term"], "CONFORMS+", by_cat)
        for cat in ("landlord", "tenant", "co_tenants", "premises", "use",
                    "options", "expense_structure", "utilities", "maintenance",
                    "insurance", "broker", "signage"):
            self.assertIn(by_cat[cat], ("CONFORMS", "CONFORMS+"),
                          f"{cat}: expected CONFORMS/CONFORMS+, got {by_cat[cat]}")
        self.assertEqual(len(rows), 17, rows)

    def test_cli_mode_reports_the_matrix_and_exits_1_on_blocking_rows(self):
        rc, out = run_cli("--loi-conformance", str(self.register_path), self.lease_path)
        self.assertEqual(rc, 1, out)
        self.assertIn("PARTIAL", out)
        self.assertIn("MISSING", out)
        self.assertIn("CONFLICT", out)
        self.assertIn("rent", out)
        self.assertIn("parking", out)
        self.assertIn("security_deposit", out)

    def test_cli_mode_json_output(self):
        rc, out = run_cli("--loi-conformance", str(self.register_path), self.lease_path, "--json")
        payload = json.loads(out)
        self.assertEqual(payload["lease_file"], "test_lease.docx")
        statuses = {r["category"]: r["status"] for r in payload["rows"]}
        self.assertEqual(statuses["rent"], "PARTIAL")
        self.assertEqual(statuses["parking"], "MISSING")
        self.assertEqual(statuses["security_deposit"], "CONFLICT")

    def test_cli_mode_exits_0_when_nothing_blocks(self):
        """A register/lease pair with no PARTIAL/MISSING/CONFLICT rows."""
        clean_register = dict(self.REGISTER)
        clean_register["parking"] = {"overnight_vehicles": None}
        clean_register["rent"] = {"schedule": [{"lease_year": 1, "monthly": 2000.00}],
                                  "escalation": {"type": "none"}}
        clean_register["security_deposit"] = {"amount": 2500.00, "months": 1.0}
        reg_path = self.tmp / "clean_register.json"
        reg_path.write_text(json.dumps(clean_register), encoding="utf-8")
        rc, out = run_cli("--loi-conformance", str(reg_path), self.lease_path)
        self.assertEqual(rc, 0, out)

    def test_unreadable_lease_exits_2(self):
        rc, out = run_cli("--loi-conformance", str(self.register_path), str(PDF_FIXTURE))
        self.assertEqual(rc, 2, out)

    def test_bad_register_path_exits_2(self):
        rc, out = run_cli("--loi-conformance", str(self.tmp / "does_not_exist.json"), self.lease_path)
        self.assertEqual(rc, 2, out)

    def test_missing_lease_file_exits_2_not_1(self):
        """Was a raw FileNotFoundError -> exit 1 (indistinguishable from a
        real 'the matrix has blocking rows' verdict) before the extraction
        guard was added; caught in independent review."""
        rc, out = run_cli("--loi-conformance", str(self.register_path),
                          str(self.tmp / "does_not_exist.docx"))
        self.assertEqual(rc, 2, out)

    def test_malformed_register_field_degrades_that_row_instead_of_crashing(self):
        """A register field of the wrong shape (a bare string instead of an
        object) must not crash the whole run -- it degrades to a MISSING
        row for that category only, and every other category still
        computes normally. Caught in independent review (was an uncaught
        AttributeError, exit 1, no report at all)."""
        bad_register = dict(self.REGISTER)
        bad_register["landlord"] = "2203 Northwood, LLC"  # should be an object
        reg_path = self.tmp / "malformed_register.json"
        reg_path.write_text(json.dumps(bad_register), encoding="utf-8")
        rc, out = run_cli("--loi-conformance", str(reg_path), self.lease_path)
        self.assertEqual(rc, 1, out)          # still a real matrix, just one bad row
        self.assertIn("could not evaluate", out, out)
        self.assertIn("rent", out)            # other categories still ran

    def test_non_object_register_exits_2(self):
        reg_path = self.tmp / "list_register.json"
        reg_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
        rc, out = run_cli("--loi-conformance", str(reg_path), self.lease_path)
        self.assertEqual(rc, 2, out)


class TestLoiConformanceRegressionFixes(TempDirCase):
    """Targeted coverage for defects found in independent review, isolated
    from TestLoiConformanceMode's larger fixture so each is legible on its
    own."""

    def test_rent_with_matching_cents_conforms(self):
        register = {"rent": {"schedule": [{"lease_year": 1, "monthly": 3458.99}],
                             "escalation": {"type": "none"}}}
        row = lease_qc._check_rent(register, "Base Rent for Lease Year 1 shall be $3,458.99 per month.")
        self.assertEqual(row["status"], "CONFORMS", row)

    def test_rent_with_different_cents_does_not_false_conform(self):
        """int()-truncating the register figure before matching let a lease
        stating different CENTS (the common case -- register rents are
        routinely rsf * rate / 12) silently read as a match. Caught in
        independent review."""
        register = {"rent": {"schedule": [{"lease_year": 1, "monthly": 3458.33}],
                             "escalation": {"type": "none"}}}
        row = lease_qc._check_rent(register, "Base Rent for Lease Year 1 shall be $3,458.99 per month.")
        self.assertNotEqual(row["status"], "CONFORMS", row)

    def test_security_deposit_with_different_cents_is_not_masked(self):
        register = {"security_deposit": {"amount": 4587.50}}
        row = lease_qc._check_security_deposit(
            register, "Tenant shall deposit with Landlord a Security Deposit in the "
                       "amount of $4,587.00 upon execution of this Lease.")
        self.assertEqual(row["status"], "CONFLICT", row)

    def test_gross_negligence_does_not_satisfy_gross_expense_structure(self):
        """A bare \\bgross\\b match fired on every ORA lease's exculpation
        clause ('gross negligence'), regardless of the lease's actual
        expense structure. Caught in independent review."""
        register = {"expense_structure": {"type": "gross"}}
        text = ("Landlord shall not be liable except for its own gross negligence or "
                "willful misconduct. Tenant shall pay its proportionate share of "
                "Operating Costs in excess of the Base Year as Additional Rent.")
        row = lease_qc._check_expense_structure(register, text)
        self.assertNotEqual(row["status"], "CONFORMS", row)

    def test_nnn_lease_with_no_gross_language_does_not_false_conflict(self):
        register = {"expense_structure": {"type": "nnn"}}
        text = "Tenant shall pay Base Rent on a triple net basis, plus its share of Taxes, Insurance and CAM."
        row = lease_qc._check_expense_structure(register, text)
        self.assertEqual(row["status"], "CONFORMS", row)

    def test_term_conforms_plus_only_when_register_does_not_require_early_access(self):
        register = {"term": {"months": 36, "target_commencement": "2026-10-01"}}
        text = "The Term of this Lease shall be thirty-six (36) months, with early access granted to Tenant."
        row = lease_qc._check_term(register, text)
        self.assertEqual(row["status"], "CONFORMS+", row)

    def test_term_required_early_access_present_is_plain_conforms_not_plus(self):
        """When the register ITSELF requires early access and the lease has
        it, that is ordinary conformance, not 'beyond the register's
        baseline' -- the prior text-only search could not tell the two
        apart. Caught in independent review."""
        register = {"term": {"months": 36, "target_commencement": "2026-10-01",
                             "early_access": "30 days prior to Commencement"}}
        text = "The Term of this Lease shall be thirty-six (36) months, with early access granted to Tenant."
        row = lease_qc._check_term(register, text)
        self.assertEqual(row["status"], "CONFORMS", row)

    def test_term_required_early_access_missing_is_partial(self):
        register = {"term": {"months": 36, "target_commencement": "2026-10-01",
                             "early_access": "30 days prior to Commencement"}}
        text = "The Term of this Lease shall be thirty-six (36) months."
        row = lease_qc._check_term(register, text)
        self.assertEqual(row["status"], "PARTIAL", row)

    def test_premises_suite_one_does_not_match_inside_a_longer_suite_number(self):
        """suite='1' matched anywhere in the lease text (no word boundary),
        so a suite of '1' was un-failable regardless of the real suite
        mentioned. Caught in independent review."""
        register = {"premises": {"address": "100 Test Drive", "suite": "1", "rsf": 2400}}
        text = "The Premises are located at 100 Test Drive, Suite 15A, containing 2,400 rentable square feet."
        row = lease_qc._check_premises(register, text)
        self.assertNotEqual(row["status"], "CONFORMS", row)

    def test_utilities_bare_key_name_no_longer_satisfies_the_row(self):
        register = {"utilities": {"electric": "landlord_provided_included_in_rent"}}
        text = "Tenant shall pay for electric service directly to the utility provider."
        row = lease_qc._check_utilities(register, text)
        self.assertNotEqual(row["status"], "CONFORMS", row)

    def test_rent_cpi_escalation_is_partial_not_silently_conforms(self):
        """A CPI-indexed escalation cannot be confirmed by a text search
        the way a flat percentage can -- it must never silently CONFORMS
        for verification this checker cannot actually perform. Caught in
        independent re-review."""
        register = {"rent": {"schedule": [{"lease_year": 1, "monthly": 2000.00}],
                             "escalation": {"type": "cpi"}}}
        row = lease_qc._check_rent(register, "Base Rent for Lease Year 1 shall be $2,000.00 per month.")
        self.assertEqual(row["status"], "PARTIAL", row)

    def test_rent_fixed_amount_escalation_is_partial_not_silently_conforms(self):
        register = {"rent": {"schedule": [{"lease_year": 1, "monthly": 2000.00}],
                             "escalation": {"type": "fixed_amount", "value": 50}}}
        row = lease_qc._check_rent(register, "Base Rent for Lease Year 1 shall be $2,000.00 per month.")
        self.assertEqual(row["status"], "PARTIAL", row)

    def test_signage_freetext_description_conforms_when_realistically_implemented(self):
        """The register's signage value is human-written prose, not an
        enum -- requiring every word verbatim (including a stray '+' and
        a hyphenated 'Landlord-approved') made this row essentially
        unfailable to CONFORM against ORA's own canonical example
        register. Caught in independent review."""
        register = {"signage": "one exterior sign over entrance + entry door signage, Landlord-approved"}
        text = ("Tenant may install one exterior sign at the Building entrance and entry "
                "door signage, subject to Landlord's prior written approval.")
        row = lease_qc._check_signage(register, text)
        self.assertEqual(row["status"], "CONFORMS", row)

    def test_signage_absent_from_lease_still_reads_missing(self):
        """The loosened threshold must not turn into an unconditional
        pass -- a lease with no signage language at all is still MISSING."""
        register = {"signage": "one exterior sign over entrance + entry door signage, Landlord-approved"}
        row = lease_qc._check_signage(
            register, "This Lease Agreement is made and entered into by and between the parties.")
        self.assertEqual(row["status"], "MISSING", row)

    def test_landlord_work_freetext_items_conform_when_realistically_implemented(self):
        register = {"landlord_work": {"items": [
            "clean warehouse floor and interior; major mechanical systems "
            "(electrical, plumbing, HVAC) in working condition",
            "service front entrance door locks",
        ]}}
        text = ("Landlord shall, prior to the Commencement Date, clean the warehouse "
                "floor and interior, place all major mechanical systems including "
                "electrical, plumbing and HVAC in good working condition, and service "
                "the front entrance door locks.")
        row = lease_qc._check_landlord_work(register, text)
        self.assertEqual(row["status"], "CONFORMS", row)

    def test_landlord_work_absent_from_lease_still_reads_missing(self):
        register = {"landlord_work": {"items": [
            "clean warehouse floor and interior; major mechanical systems "
            "(electrical, plumbing, HVAC) in working condition"]}}
        row = lease_qc._check_landlord_work(
            register, "This Lease Agreement is made and entered into by and between the parties.")
        self.assertEqual(row["status"], "MISSING", row)


# --------------------------------------------------------------------------
# 7. sys.path shim ordering -- append, never insert(0, ...)
# --------------------------------------------------------------------------

class TestDevCheckoutFallbackOrdering(TempDirCase):
    """Regression guard for the dev-checkout sys.path shim shared by all
    three scanner scripts (pma_qc.py, listing_qc.py, lease_qc.py):

        sys.path.append(str(Path(__file__).resolve().parent.parent.parent / 'tools'))

    This line was `sys.path.insert(0, ...)` once. insert(0, ...) puts the
    repo-root tools/ fallback AHEAD of the script's own directory (which
    Python puts at sys.path[0] automatically at interpreter startup), so a
    packaged .skill's co-located ora_doc_qc.py copy gets silently shadowed by
    whatever sits under an install root's own tools/ directory -- the
    opposite of "lowest-priority dev-checkout fallback". Fixed to append,
    but test_ora_doc_qc_resolves_to_the_repo_root_canonical_copy (above) is
    ordering-agnostic: this repo's own dev checkout has no co-located copy to
    shadow, so that test passes identically whether the code used
    insert(0, ...) or append(...). Nothing else in the repo catches a silent
    revert.

    This test extracts the LIVE shim line straight out of lease_qc.py --
    not a hand-copied duplicate that could drift from it -- and executes it
    for real inside a synthetic tree that DOES have a co-located copy, the
    one scenario where the two orderings actually disagree. It runs as a
    real subprocess, not importlib: Python's automatic
    sys.path[0] = script's-own-directory behavior -- the entire mechanism
    under test -- is a startup-time interpreter behavior that
    importlib.import_module() does not reproduce.

    Directory depth matters: the shim's `parent.parent.parent` walks
    script -> scripts/ -> skill/ -> repo-root, so the synthetic tree below
    mirrors that exact three-level layout (repo/skill/scripts/probe.py,
    with the poisoned copy at repo/tools/) rather than the shallower
    two-level sketch this task was framed with -- a shallower tree makes the
    appended path miss the poisoned file entirely and stops testing the
    ordering.
    """

    def _extract_shim_line(self):
        src = LEASE_QC.read_text(encoding="utf-8")
        m = re.search(r"^sys\.path\.\w+\([^\n]*\)\s*$", src, re.M)
        self.assertIsNotNone(
            m, "could not find the sys.path shim line in lease_qc.py -- "
               "update this extraction regex, don't let it pass vacuously")
        return m.group(0)

    def test_dev_checkout_fallback_never_shadows_a_co_located_module(self):
        # Deliberately NOT asserting the extracted line says "append" here --
        # that would make this a source-text diff instead of a behavior test.
        # The extracted line (whatever it says) is executed for real below;
        # the SENTINEL assertion at the end is what actually proves ordering.
        shim_line = self._extract_shim_line()

        repo = self.tmp / "repo"
        scripts = repo / "skill" / "scripts"
        tools = repo / "tools"
        scripts.mkdir(parents=True)
        tools.mkdir(parents=True)

        probe = scripts / "probe.py"
        probe.write_text(
            "import sys\n"
            "from pathlib import Path\n"
            f"{shim_line}\n"
            "import ora_doc_qc\n"
            "print(ora_doc_qc.SENTINEL)\n",
            encoding="utf-8",
        )
        # Co-located copy -- what a packaged .skill ships alongside the
        # script via SHARED_ROOT_DEPS. Must win.
        (scripts / "ora_doc_qc.py").write_text('SENTINEL = "correct"\n', encoding="utf-8")
        # Repo-root tools/ copy -- the dev-checkout-only fallback target.
        # Must lose whenever a co-located copy exists.
        (tools / "ora_doc_qc.py").write_text('SENTINEL = "WRONG"\n', encoding="utf-8")

        p = subprocess.run([sys.executable, str(probe)],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(
            p.stdout.strip(), "correct",
            "dev-checkout tools/ fallback shadowed the co-located module -- "
            "lease_qc.py's sys.path shim regressed to insert(0, ...)")


# --------------------------------------------------------------------------
# v2.8 -- Class 5d (T3/T4/D1/D2), open_items carry-through, --loi-audit
# --------------------------------------------------------------------------

def _scan(path, allow_tokens=False):
    """Run the full registry through ora_doc_qc.scan() the way the CLI does."""
    import ora_doc_qc
    lease_qc.register_scan_path(path)
    return ora_doc_qc.scan(str(path), lease_qc.CHECKS, allow_tokens=allow_tokens,
                           want_footer=True)


def _ids(report):
    return {f["id"]: f for f in report["failures"]}


SIG_BLOCK = [
    "IN WITNESS WHEREOF, the parties have executed this Lease.",
    "LANDLORD: 2203 Northwood, LLC",
    "By: ______________________________",
    "Print Name: ______________________",
    "Title: ___________________________",
    "Date: ____________________________",
    "TENANT: Acme Holdings LLC",
    "Signature: ________________________",
    "Its: ______________________________",
    "Signed this ____ day of __________, 20__",
    "(SEAL) __________",
]


class TestT3UnderscoreBlanks(TempDirCase):

    def test_fires_on_blank_attn_line(self):
        p = make_docx(self.tmp / "exec_lease.docx", [
            "TENANT NOTICE ADDRESS: 100 Test Drive, Suite 5B",
            "ATTN: ______________________",
        ])
        f = _ids(_scan(p))
        self.assertIn("T3", f)
        self.assertEqual(f["T3"]["severity"], "HIGH")
        self.assertIn("ATTN", f["T3"]["detail"])
        self.assertTrue(f["T3"]["detail"].startswith("1 "), f["T3"]["detail"])

    def test_fires_on_blank_inside_a_rent_sentence(self):
        p = make_docx(self.tmp / "exec_lease.docx", [
            "Base Rent for Lease Year 1 shall be $__________ per month.",
        ])
        self.assertIn("T3", _ids(_scan(p)))

    def test_commencement_date_blank_is_not_a_signing_label(self):
        p = make_docx(self.tmp / "exec_lease.docx", ["Commencement Date: __________"])
        self.assertIn("T3", _ids(_scan(p)))

    def test_silent_on_full_signature_block(self):
        p = make_docx(self.tmp / "exec_lease.docx", SIG_BLOCK)
        self.assertNotIn("T3", _ids(_scan(p)))

    def test_silent_on_label_on_previous_line(self):
        p = make_docx(self.tmp / "exec_lease.docx", ["Landlord signs here:", "By:",
                                                    "______________________________"])
        self.assertNotIn("T3", _ids(_scan(p)))

    def test_silent_on_template_file(self):
        p = make_docx(self.tmp / "ORA_Lease_TEMPLATE.docx", ["ATTN: ______________"])
        self.assertNotIn("T3", _ids(_scan(p)))

    def test_silent_with_allow_tokens(self):
        p = make_docx(self.tmp / "exec_lease.docx", ["ATTN: ______________"])
        self.assertNotIn("T3", _ids(_scan(p, allow_tokens=True)))

    def test_footer_blanks_counted(self):
        p = make_docx(self.tmp / "exec_lease.docx", ["clean body"],
                      footer_text="Notice: ATTN: ________________")
        self.assertIn("T3", _ids(_scan(p)))

    def test_short_runs_ignored_and_detail_caps_at_six(self):
        p = make_docx(self.tmp / "exec_lease.docx",
                      ["a ____ b"] + [f"Email{i}: ________" for i in range(8)])
        f = _ids(_scan(p))
        self.assertTrue(f["T3"]["detail"].startswith("8 "), f["T3"]["detail"])
        self.assertNotIn("Email7", f["T3"]["detail"])


class TestT4ExhibitStubs(TempDirCase):

    def test_fires_on_each_phrase(self):
        for phrase in ("TO BE ATTACHED", "To Be Attached Prior To Execution",
                       "TO BE INSERTED", "to be provided", "[ATTACH site plan]",
                       "PLACEHOLDER"):
            with self.subTest(phrase=phrase):
                p = make_docx(self.tmp / "exec_lease.docx", ["EXHIBIT A", f"Site plan {phrase}."])
                f = _ids(_scan(p))
                self.assertIn("T4", f)
                self.assertEqual(f["T4"]["severity"], "BLOCK")

    def test_nbsp_folded(self):
        p = make_docx(self.tmp / "exec_lease.docx", ["EXHIBIT A", "TO\xa0BE\xa0ATTACHED"])
        self.assertIn("T4", _ids(_scan(p)))

    def test_fires_on_bare_exhibit_heading_no_body_no_media(self):
        p = make_docx(self.tmp / "exec_lease.docx", ["EXHIBIT D"], filler_first=True)
        f = _ids(_scan(p))
        self.assertIn("T4", f)
        self.assertIn("EXHIBIT D", f["T4"]["detail"])

    def test_silent_when_exhibit_has_substantive_body(self):
        body = " ".join(["Rule"] * 60)
        p = make_docx(self.tmp / "exec_lease.docx", ["EXHIBIT B", body])
        self.assertNotIn("T4", _ids(_scan(p)))

    def test_silent_when_docx_carries_embedded_drawing(self):
        p = make_docx(self.tmp / "exec_lease.docx", ["EXHIBIT A"],
                      extra_parts={"word/media/image1.png": b"\x89PNG"})
        self.assertNotIn("T4", _ids(_scan(p)))

    def test_silent_on_template(self):
        p = make_docx(self.tmp / "ORA_Lease_TEMPLATE.docx", ["EXHIBIT A", "TO BE ATTACHED"])
        self.assertNotIn("T4", _ids(_scan(p)))

    def test_inline_exhibit_reference_is_not_a_heading(self):
        p = make_docx(self.tmp / "exec_lease.docx",
                      ["The Premises are depicted on Exhibit A attached to this Lease."])
        self.assertNotIn("T4", _ids(_scan(p)))


BLI = [
    "BASIC LEASE INFORMATION",
    "Landlord: 2203 Northwood, LLC",
    "Security Deposit: $2,500.00",
    "Monthly Rent (Lease Year 1): $2,000.00",
    "Tenant's Proportionate Share: 12.5%",
    "Parking: 4 vehicles",
    "Late Fee: 10% of any payment not made when due",
    "Default Interest: 18% per annum",
    "Escalation: 3% per Lease Year, compounded",
    "Utilities: Tenant pays electric and water",
    "This Basic Lease Information is provided for convenience.",
]
BODY_OK = [
    "SERVICES AND UTILITIES.",
    "Tenant shall pay for electric and water service to the Premises as additional rent.",
    "SECURITY DEPOSIT.",
    "Tenant shall deposit a Security Deposit of $2,500.00 with Landlord.",
    "RENT.",
    "Monthly Base Rent for Lease Year 1 shall be $2,000.00 per month, increasing 3% annually.",
    "Tenant's Proportionate Share is 12.5%.",
    "Tenant may park 4 overnight vehicles at the Premises.",
    "Late fee of 10% of the overdue amount shall apply.",
    "Past-due sums bear interest at 18% per annum.",
]


class TestD1BliBodyDrift(TempDirCase):

    def test_silent_without_bli_block(self):
        p = make_docx(self.tmp / "exec_lease.docx", BODY_OK)
        self.assertNotIn("D1", _ids(_scan(p)))

    def test_passes_when_equal(self):
        p = make_docx(self.tmp / "exec_lease.docx", BLI + BODY_OK)
        f = _ids(_scan(p))
        self.assertNotIn("D1", f, f.get("D1"))

    def test_fires_on_utility_scope_drift(self):
        body = [b.replace("electric and water service", "electric, water and sewer service")
                for b in BODY_OK]
        p = make_docx(self.tmp / "exec_lease.docx", BLI + body)
        f = _ids(_scan(p))
        self.assertIn("D1", f)
        self.assertEqual(f["D1"]["severity"], "MED")
        self.assertIn("Utilities", f["D1"]["detail"])
        self.assertIn("sewer", f["D1"]["detail"])

    def test_fires_on_deposit_cents_and_names_both_values(self):
        body = [b.replace("$2,500.00", "$2,500.50") for b in BODY_OK]
        p = make_docx(self.tmp / "exec_lease.docx", BLI + body)
        f = _ids(_scan(p))
        self.assertIn("D1", f)
        self.assertIn("Security Deposit", f["D1"]["detail"])
        self.assertIn("2,500.00", f["D1"]["detail"])
        self.assertIn("2,500.50", f["D1"]["detail"])

    def test_fires_once_per_drifted_label(self):
        body = [b.replace("12.5%", "15%").replace("4 overnight", "6 overnight")
                for b in BODY_OK]
        p = make_docx(self.tmp / "exec_lease.docx", BLI + body)
        d = _ids(_scan(p))["D1"]["detail"]
        self.assertIn("Proportionate Share", d)
        self.assertIn("Parking", d)
        self.assertNotIn("Late Fee", d)

    def test_token_valued_bli_line_is_skipped(self):
        bli = [b.replace("$2,500.00", "$[SECURITY DEPOSIT]") for b in BLI]
        p = make_docx(self.tmp / "exec_lease.docx", bli + BODY_OK)
        self.assertNotIn("D1", _ids(_scan(p, allow_tokens=True)))


def _sched(rows):
    out = ["Lease Year | Annual Base Rent | Monthly Rent"]
    out += [f"Lease Year {y} | ${a} | ${m}" for y, a, m in rows]
    return out


RENT_HEAD = [
    "Demised Premises: 100 Test Drive - approximately 1,350 rentable square feet",
    "Annual Base Rent shall be $38.30 per rentable square foot.",
    "Base Rent shall escalate at 3% per Lease Year, compounded.",
]
MONTHLY_METHOD = [(1, "51,705.00", "4,308.75"), (2, "53,256.12", "4,438.01"),
                  (3, "54,853.80", "4,571.15"), (4, "56,499.36", "4,708.28"),
                  (5, "58,194.36", "4,849.53")]
ANNUAL_METHOD = [(1, "51,705.00", "4,308.75"), (2, "53,256.15", "4,438.01"),
                 (3, "54,853.83", "4,571.15"), (4, "56,499.44", "4,708.29"),
                 (5, "58,194.42", "4,849.54")]


class TestD2RentArithmetic(TempDirCase):

    def _run(self, rows, extra=()):
        p = make_docx(self.tmp / "exec_lease.docx", RENT_HEAD + list(extra) + _sched(rows))
        return _ids(_scan(p))

    def test_passes_monthly_rounded_schedule(self):
        f = self._run(MONTHLY_METHOD)
        self.assertNotIn("D2", f, f.get("D2"))

    def test_passes_annual_compounded_schedule(self):
        f = self._run(ANNUAL_METHOD)
        self.assertNotIn("D2", f, f.get("D2"))

    def test_fails_one_wrong_row(self):
        rows = list(MONTHLY_METHOD)
        rows[2] = (3, "54,853.80", "4,571.99")
        f = self._run(rows)
        self.assertIn("D2", f)
        self.assertEqual(f["D2"]["severity"], "HIGH")
        self.assertIn("Lease Year 3", f["D2"]["detail"])
        self.assertIn("4,571.99", f["D2"]["detail"])

    def test_fails_year_one_psf_mismatch(self):
        rows = [(1, "60,000.00", "5,000.00")] + MONTHLY_METHOD[1:]
        self.assertIn("D2", self._run(rows))

    def test_fails_mixed_methods_without_controls_clause(self):
        rows = [MONTHLY_METHOD[0], MONTHLY_METHOD[1], ANNUAL_METHOD[2],
                ANNUAL_METHOD[3], ANNUAL_METHOD[4]]
        self.assertIn("D2", self._run(rows))

    def test_mixed_methods_pass_when_schedule_controls(self):
        rows = [MONTHLY_METHOD[0], MONTHLY_METHOD[1], ANNUAL_METHOD[2],
                ANNUAL_METHOD[3], ANNUAL_METHOD[4]]
        self.assertNotIn("D2", self._run(
            rows, ["In the event of any discrepancy, the rent schedule controls."]))

    def test_passes_flat_schedule(self):
        head = [h for h in RENT_HEAD if "escalate" not in h]
        rows = [(y, "51,705.00", "4,308.75") for y in range(1, 4)]
        p = make_docx(self.tmp / "exec_lease.docx", head + _sched(rows))
        self.assertNotIn("D2", _ids(_scan(p)))

    def test_fails_flat_schedule_with_a_stray_row(self):
        head = [h for h in RENT_HEAD if "escalate" not in h] + ["Escalation: 0%"]
        rows = [(1, "51,705.00", "4,308.75"), (2, "52,000.00", "4,333.33")]
        p = make_docx(self.tmp / "exec_lease.docx", head + _sched(rows))
        self.assertIn("D2", _ids(_scan(p)))

    def test_space_separated_rows(self):
        p = make_docx(self.tmp / "exec_lease.docx", RENT_HEAD + [
            "Lease Year 1 $51,705.00 $4,308.75", "Lease Year 2 $53,256.12 $4,438.01"])
        f = _ids(_scan(p))
        self.assertNotIn("D2", f, f.get("D2"))

    def test_silent_without_schedule_table(self):
        p = make_docx(self.tmp / "exec_lease.docx", RENT_HEAD)
        self.assertNotIn("D2", _ids(_scan(p)))


class TestOpenItemsRow(TempDirCase):

    BASE = TestLoiConformanceMode.REGISTER
    TEXT = ("the exterior signage shall be subject to landlord approval "
            "and a suite plan is attached as exhibit a")

    def _row(self, items):
        reg = dict(self.BASE)
        if items is not None:
            reg["open_items"] = items
        rows = lease_qc.build_conformance_matrix(reg, self.TEXT)
        return {r["category"]: r for r in rows}.get("open_items")

    def test_omitted_when_absent_or_empty(self):
        self.assertIsNone(self._row(None))
        self.assertIsNone(self._row([]))

    def test_conforms_when_all_resolved_and_clause_present(self):
        r = self._row([{"item": "Exhibit A", "resolution": "attached",
                        "lease_clause": "suite plan is attached as exhibit a", "source": "LOI"}])
        self.assertEqual(r["status"], "CONFORMS", r)

    def test_partial_when_some_resolved(self):
        r = self._row([{"item": "Exhibit A", "resolution": "attached",
                        "lease_clause": "suite plan is attached as exhibit a", "source": "LOI"},
                       {"item": "Water meter basis", "resolution": None,
                        "lease_clause": None, "source": "PM"}])
        self.assertEqual(r["status"], "PARTIAL")
        self.assertIn("Water meter basis", r["detail"])

    def test_missing_when_none_resolved_and_string_form_is_unresolved(self):
        r = self._row(["Exhibit A suite plan", "dual agency consent"])
        self.assertEqual(r["status"], "MISSING")
        self.assertIn("Exhibit A suite plan", r["detail"])
        self.assertIn("dual agency consent", r["detail"])

    def test_resolution_without_clause_present_in_lease_is_unresolved(self):
        r = self._row([{"item": "Parking cap", "resolution": "4 vehicles",
                        "lease_clause": "tenant may keep ten trailers", "source": "LOI"}])
        self.assertEqual(r["status"], "MISSING")

    def test_example_register_and_schema(self):
        ex = REPO / "lease-generation" / "references" / "example-register-synthetic.json"
        reg = json.loads(ex.read_text(encoding="utf-8"))
        schema = json.loads((REPO / "lease-generation" / "references"
                             / "deal-terms-register.schema.json").read_text(encoding="utf-8"))
        self.assertIn("oneOf", schema["properties"]["open_items"]["items"])
        self.assertTrue(any(isinstance(i, dict) for i in reg["open_items"]))
        self.assertTrue(any(isinstance(i, str) for i in reg["open_items"]))
        rows = lease_qc.build_conformance_matrix(reg, "")
        self.assertEqual(rows[-1]["category"], "open_items")
        self.assertEqual(len(rows), 18)


class TestLoiAuditMode(TempDirCase):

    def setUp(self):
        super().setUp()
        self.reg = self.tmp / "register.json"
        self.reg.write_text(json.dumps(TestLoiConformanceMode.REGISTER), encoding="utf-8")
        self.lease = make_docx(self.tmp / "test_lease.docx", TestLoiConformanceMode.LEASE_BODY,
                               footer_text="Page 1 of 4")

    def test_text_report_composes_scan_matrix_and_audit_line(self):
        rc, out = run_cli("--loi-audit", str(self.reg), self.lease)
        self.assertEqual(rc, 1, out)
        self.assertIn("checks FAILED", out)
        self.assertIn("SUMMARY", out)
        self.assertRegex(out, r"AUDIT: \d+ scan failure\(s\) \[\d+ BLOCK\] \S+ \d+ matrix row\(s\) \S+ exit 1")

    def test_json_shape_and_exit_is_max(self):
        rc, out = run_cli("--loi-audit", str(self.reg), self.lease, "--json")
        payload = json.loads(out)
        self.assertEqual(set(payload), {"scan", "matrix", "exit"})
        self.assertEqual(payload["exit"], rc)
        self.assertEqual(payload["scan"][0]["checks_run"], 60)
        self.assertEqual(payload["matrix"]["lease_file"], "test_lease.docx")

    def test_exit_2_wins_over_1(self):
        rc, out = run_cli("--loi-audit", str(self.tmp / "nope.json"), self.lease)
        self.assertEqual(rc, 2, out)
        rc, out = run_cli("--loi-audit", str(self.reg), str(PDF_FIXTURE))
        self.assertEqual(rc, 2, out)

    def test_exit_is_max_of_components(self):
        rc, out = run_cli("--loi-audit", str(self.reg), self.lease, "--json")
        payload = json.loads(out)
        scan_rc = 1 if payload["scan"][0]["failures"] else 0
        mat_rc = 1 if any(r["status"] in ("PARTIAL", "MISSING", "CONFLICT")
                          for r in payload["matrix"]["rows"]) else 0
        self.assertEqual(payload["exit"], max(scan_rc, mat_rc))
        self.assertEqual(mat_rc, 1)


class TestV28ReviewFixes(TempDirCase):

    def test_d2_handles_psf_column_and_monthly_first(self):
        rows = ["Lease Year | PSF | Annual | Monthly",
                "Lease Year 1 | $38.30 | $51,705.00 | $4,308.75",
                "Lease Year 2 | $39.45 | $53,256.12 | $4,438.01"]
        p = make_docx(self.tmp / "exec_lease.docx", RENT_HEAD + rows)
        f = _ids(_scan(p))
        self.assertNotIn("D2", f, f.get("D2"))
        rows = ["Lease Year 1 | $4,308.75 | $51,705.00", "Lease Year 2 | $4,438.01 | $53,256.12"]
        p = make_docx(self.tmp / "exec_lease.docx", RENT_HEAD + rows)
        f = _ids(_scan(p))
        self.assertNotIn("D2", f, f.get("D2"))

    def test_d2_ignores_ti_allowance_psf(self):
        head = ["Tenant improvement allowance shall be $5.00 per square foot."] + RENT_HEAD
        p = make_docx(self.tmp / "exec_lease.docx", head + _sched(MONTHLY_METHOD))
        f = _ids(_scan(p))
        self.assertNotIn("D2", f, f.get("D2"))

    def test_d2_multi_year_row_only_truncates(self):
        rows = _sched(MONTHLY_METHOD[:2]) + ["Lease Years 3-5 | $55,000.00 | $4,583.33"]
        p = make_docx(self.tmp / "exec_lease.docx", RENT_HEAD + rows)
        self.assertNotIn("D2", _ids(_scan(p)))

    def test_t4_exhibit_list_is_not_a_stub(self):
        p = make_docx(self.tmp / "exec_lease.docx",
                      ["EXHIBIT A - Site Plan", "EXHIBIT B - Rules"], filler_first=True)
        f = _ids(_scan(p))
        self.assertIn("EXHIBIT B", f["T4"]["detail"])
        self.assertNotIn("EXHIBIT A", f["T4"]["detail"])

    def test_d1_default_interest_ignores_monthly_basis(self):
        body = [b.replace("interest at 18% per annum", "x") for b in BODY_OK]
        body.append("Late payments also bear a charge of interest at 1.5% per month.")
        p = make_docx(self.tmp / "exec_lease.docx", BLI + body)
        d = _ids(_scan(p)).get("D1", {}).get("detail", "")
        self.assertNotIn("Default Interest", d)

    def test_t3_label_elsewhere_on_line_does_not_excuse_a_blank(self):
        p = make_docx(self.tmp / "exec_lease.docx", ["Email: ________  By: ________"])
        d = _ids(_scan(p))["T3"]["detail"]
        self.assertTrue(d.startswith("1 "), d)
        p = make_docx(self.tmp / "exec_lease.docx",
                      ["Rent commences the ______ day of ____________, 20__"])
        self.assertIn("T3", _ids(_scan(p)))

    def test_t3_caption_after_rule_still_exempt(self):
        p = make_docx(self.tmp / "exec_lease.docx", ["______________________ Signature"])
        self.assertNotIn("T3", _ids(_scan(p)))

    def test_t3_signature_block_with_name_below_and_initials_exempt(self):
        p = make_docx(self.tmp / "exec_lease.docx", [
            "LANDLORD:", "Oxford Northwood LLC", "______________________",
            "Name: Eric Goldberg", "Title: Member",
            "Tenant Initials: ______   Landlord Initials: ______", "WITNESS: ______"])
        self.assertNotIn("T3", _ids(_scan(p)))

    def test_d2_psf_and_annual_only_table(self):
        p = make_docx(self.tmp / "exec_lease.docx", [
            "Demised Premises: approximately 12,000 rentable square feet",
            "Base Rent is $12.50 per rentable square foot, escalating 3% per Lease Year.",
            "Lease Year 1 $12.50 $150,000.00", "Lease Year 2 $12.88 $154,500.00"])
        f = _ids(_scan(p))
        self.assertNotIn("D2", f, f.get("D2"))


class TestV28MasterBenchmark(TempDirCase):

    def test_new_checks_silent_on_v26_master(self):
        if not MASTER_V26.exists():
            self.skipTest("master fixture absent")
        r = _scan(MASTER_V26)
        # v2.8 checks (T3/T4/D1/D2) stay silent on v2.6; only the v2.7 standards fire.
        self.assertEqual({f[0] if isinstance(f, (list, tuple)) else f.get("id") for f in r["failures"]}, V27_IDS, r["failures"])
        self.assertEqual(r["checks_run"], 60)


class TestV27Standards(TempDirCase):
    """F19-F21 (v2.7 standards, 2026-10-06): v2.7 master clean; v2.6 master fails
    exactly these three; each check fires on its own defect and is silent on the fix."""

    def test_v27_master_is_clean(self):
        if not MASTER_V27.exists():
            self.skipTest("v2.7 fixture absent")
        r = _scan(MASTER_V27)
        self.assertEqual(r["failures"], [], r["failures"])
        self.assertEqual(r["checks_run"], 60)

    def _v(self, cid, paras):
        p = make_docx(self.tmp / f"{cid}.docx", paras + ["Filler sentence for the extraction floor."] * 40)
        return _new_verdict_any(p, cid)

    def test_f19_fires_on_premises_only_notice_and_not_on_v27_wording(self):
        self.assertTrue(self._v("F19", ["(A) if to Landlord, at the addresses set forth below; and (B) if to Tenant, at the Demised Premises.  The party to receive notices may be changed."]))
        self.assertFalse(self._v("F19", ["(B) if to Tenant, at the Tenant notice address set forth below and, from and after the Commencement Date, also at the Demised Premises."]))

    def test_f20_fires_without_schedule_and_on_optional_bracket(self):
        base = "Commencing on the first day of the second Lease Year the Annual Base Rent shall increase by 3%."
        self.assertTrue(self._v("F20", [base]))
        self.assertTrue(self._v("F20", [base + " [OPTIONAL: ATTACH RENT SCHEDULE TABLE — IF ATTACHED, THE SCHEDULE CONTROLS]"]))
        self.assertFalse(self._v("F20", [base + " The Annual Base Rent and Monthly Rent for each Lease Year are set forth in the following schedule."]))

    def test_f21_fires_without_late_signing_clause(self):
        self.assertTrue(self._v("F21", ["The Commencement Date shall be June 1, 2026."]))
        self.assertFalse(self._v("F21", ["The Commencement Date shall be June 1, 2026.  If this Lease has not been fully executed and delivered by Landlord and Tenant on or before the fifteenth (15th) day of the calendar month preceding the month in which the Commencement Date occurs, then the Commencement Date shall instead be the first day of the first full calendar month."]))


def _new_verdict_any(path, cid):
    body, meta = extract(path, want_footer=True)
    ctx = {"t": norm(body), "raw": body, "meta": meta, "name": os.path.basename(path),
           "allow_tokens": False, "is_template": False}
    fn = {c[0]: c[4] for c in lease_qc.CHECKS}[cid]
    return fn(ctx) not in (None, False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
