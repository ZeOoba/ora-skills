#!/usr/bin/env python3
"""Example deal-terms registers must be fully synthetic (2026-11-08).

Audit row tenant-pii-in-shipped-example-register: lease-generation shipped a
filled example register built from a real deal, tenant identity included. It was
replaced by a synthetic register and untracked (no history rewrite). This gate
keeps a real register from coming back under any example-register filename.

Positive-marker check, so it never needs to hold the real data it guards against:
every `*example*register*.json` outside `_archive/` must
  - carry `"_synthetic": true`,
  - use a deal_id starting `EXAMPLE-`,
  - mark every party/person field (landlord, tenant, co-tenants, signatories,
    copy-to, broker firm and agents) with "example" or "fictional",
  - put every address on an "Example" street,
  - use only example.com / *.example email addresses, if any.

Extended 2026-11-12 (audit row public-psa-schema-real-deal-facts) to every
`references/*schema*.md`: an Example column must be labelled synthetic, every
party/contact/address/email row's example must be a placeholder or carry an
example/fictional marker, and no table cell may hold a non-example email, a
non-555-01xx phone, a parcel/instrument/case-number shape or a non-Example street.

Stdlib only -- run with `python tools/test_example_registers_synthetic.py`.
"""
import html
import io
import json
import re
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
_SKIP_DIRS = {".git", "_archive", "node_modules", ".pytest_cache", "_staging", ".claude", ".worktrees"}
_MARK = re.compile(r"example|fictional", re.I)
_EMAIL_OK = re.compile(r"@(?:[\w-]+\.)*example(?:\.com)?$", re.I)

PARTY_PATHS = (
    ("landlord", "entity"), ("landlord", "signatory"), ("landlord", "copy_to"),
    ("tenant", "entity"), ("tenant", "signatory"), ("tenant", "business_description"),
    ("broker", "firm"), ("broker", "landlord_agent"), ("broker", "tenant_agent"),
    ("premises", "project_name"),
)
ADDRESS_PATHS = (("landlord", "notice_address"), ("tenant", "notice_address"), ("premises", "address"))
EMAIL_PATHS = (("tenant", "notice_email"),)


def find_example_registers(root):
    out = []
    for p in sorted(root.rglob("*.json")):
        rel = p.relative_to(root)
        if any(part in _SKIP_DIRS for part in rel.parts[:-1]):
            continue
        name = p.name.lower()
        if "example" in name and "register" in name:
            out.append(p)
    return out


def _get(d, path):
    for k in path:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def problems(reg):
    """List of non-synthetic markers found in one parsed register (empty = clean)."""
    if not isinstance(reg, dict):
        return ["register is not a JSON object"]
    found = []
    if reg.get("_synthetic") is not True:
        found.append('missing "_synthetic": true')
    if not str(reg.get("deal_id", "")).startswith("EXAMPLE-"):
        found.append("deal_id does not start with EXAMPLE-")
    for path in PARTY_PATHS:
        v = _get(reg, path)
        if isinstance(v, str) and v and not _MARK.search(v):
            found.append(f"{'.'.join(path)} lacks an example/fictional marker")
    for i, v in enumerate(_get(reg, ("tenant", "co_tenants")) or []):
        if not (isinstance(v, str) and _MARK.search(v)):
            found.append(f"tenant.co_tenants[{i}] lacks an example/fictional marker")
    for path in ADDRESS_PATHS:
        v = _get(reg, path)
        if isinstance(v, str) and v and "example" not in v.lower():
            found.append(f"{'.'.join(path)} is not an Example address")
    for path in EMAIL_PATHS:
        v = _get(reg, path)
        if isinstance(v, str) and v and not _EMAIL_OK.search(v.strip()):
            found.append(f"{'.'.join(path)} is not an example.com address")
    return found


# --- Schema references with an Example column (2026-11-12) -------------------------
# Audit row public-psa-schema-real-deal-facts: psa-reconciliation's fact schema filled
# its Example column from one real executed PSA (parties, counsel emails, parcel IDs,
# deed instrument, price, escrow contact). Same positive-marker idea as the registers:
# every `references/*schema*.md` table that has an Example column must label it
# synthetic, every party/contact row's example must be a placeholder or carry an
# example/fictional marker, and no cell anywhere in the file's tables may hold a real-
# looking email, phone, parcel/instrument/case number or street address.

_PARTY_FIELD = re.compile(
    r"entity|trading name|notice name|firm|attorney|signatory|principal|contact|\bagent\b|"
    r"broker\(s\)|escrow agent|tenant name|caption|co-defendant|address|email", re.I)
# A party/contact example value is split into segments on " — " and "; ". EVERY segment
# must itself be synthetic by an ANCHORED rule -- a marker anywhere in the value (the old
# rule) let "<real name> (example)" through:
#   * starts with the word "Example" (capitalised), e.g. "Example Buyer Holdings, LLC";
#   * an Example street address: "<number> Example <Street|Way|Ave|Road>...";
#   * one or more [bracket placeholders] joined by & or /, optionally followed by a short
#     role suffix (", Esq.", ", President") and "(example)";
#   * a list of example-domain emails;
#   * exactly an empty marker (—, -, N/A, None, TBD);
#   * a role phrase starting "representing " or "<Seller|Buyer|Purchaser> pays ".
_SEGMENT_SPLIT = re.compile(r"\s+—\s+|;\s+")
_EMAIL_ADDR = r"[\w.+-]+@(?:[\w-]+\.)*example(?:\.com)?"
_SEGMENT_OK = re.compile(
    r"^(?:Example\b.*"
    r"|\d{1,6}(?:-\d{1,6})? Example (?:Street|Way|Ave\.?|Avenue|Road)\b.*"
    r"|\[[^\]]+\](?:\s*(?:&|/)\s*\[[^\]]+\])*(?:, (?:Esq\.|President|Partner|Manager))?(?: \(example\))?"
    r"|" + _EMAIL_ADDR + r"(?:\s*/\s*" + _EMAIL_ADDR + r")*"
    r"|—|-|N/A|None|TBD"
    r"|representing (?:Seller|Buyer|Purchaser)"
    r"|(?:Seller|Buyer|Purchaser) pays [a-z ]+)$")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"\(?\b\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}\b")
_PHONE_OK = re.compile(r"\(?\b\d{3}\)?[\s.-]555[\s.-]01\d{2}\b")
# parcel / instrument / case numbers: 3-digit group + 5-6 digit group, 9+ digit runs, or a
# court-docket shape ("<yy> <CV> <nnnnnn>", spaces or hyphens). No prefix exempts a match
# (an "EX-" exemption let "EX-<real id>" through) -- synthetic IDs use [placeholders].
_ID = re.compile(r"\b\d{3}-\d{5,6}\b|\b\d{9,}\b|\b\d{2,4}[ -][A-Z]{2,3}[ -]\d{5,6}\b")

# --- Local denylist of real tokens (2026-11-12) --------------------------------------
# Shape checks cannot recognise a restored real price, date or name. The real tokens
# live ONLY in a gitignored machine-local file -- never committed, not even hashed
# (short values brute-force in milliseconds). Format: tools/real-identifiers.local.json.example.
# Present: any listed term found (casefolded, whitespace-normalised) in a scanned file
# FAILS. Absent (CI, fresh clones): the check prints a visible WARNING and passes --
# a unittest skip would trip tools/run_suite.sh's zero-skip gate.
DENYLIST = REPO / "tools" / "real-identifiers.local.json"
# Scope (widened 2026-11-12): EVERY git-tracked file. Text files are read whole
# (UTF-8, else UTF-16 with BOM, else cp1252 outside _archive/); Office zips EVERYWHERE,
# _archive/ included, are read as their .xml and .rels text, both with tags removed (a
# word split across runs) and with tags turned into spaces (adjacent cells/paragraphs);
# PDFs outside _archive/ are read with PyMuPDF. Images and fonts are skipped by
# extension. Any other file that cannot be read as text outside _archive/ is UNSCANNABLE
# and FAILS the check -- never silently skipped. Other binaries under _archive/ are skipped.
_OFFICE_ZIP = {".docx", ".xlsx", ".pptx", ".docm", ".xlsm", ".dotx"}
_MEDIA = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".ttf", ".otf", ".woff", ".woff2"}


class Unscannable(Exception):
    pass


def _norm(s):
    return re.sub(r"\s+", " ", s.casefold()).strip()


def load_denylist(path=DENYLIST):
    """List of terms, or None when the local file is absent."""
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    terms = data.get("terms") if isinstance(data, dict) else None
    if not isinstance(terms, list) or not all(isinstance(t, str) and t.strip() for t in terms):
        raise ValueError(f"{path.name}: expected {{\"terms\": [non-empty strings]}}")
    return terms


def _squash(s):
    return re.sub(r"[^0-9a-z]", "", s.casefold())


def _term_re(term):
    return re.compile(r"(?<![0-9a-z])" + re.escape(_norm(term)) + r"(?![0-9a-z])")


_GLUE = r"[-_./]?"  # at most one non-space joiner; the spaced form is pass (1)'s job


def _glued_re(term):
    """Term with each internal separator replaced by an optional single joiner, word-
    bounded at the ends -- `Acme Widget` matches `AcmeWidget-City`, `acme_widget`,
    `acme-widget`, but not `acme) | | widget` across table cells."""
    parts = [p for p in re.split(r"[^0-9a-z]+", term.casefold()) if p]
    return re.compile(r"(?<![0-9a-z])" + _GLUE.join(map(re.escape, parts)) + r"(?![0-9a-z])")


def _light_squash(s):
    """Casefold and drop only slug joiners (whitespace - _ . /), keeping quotes, brackets
    and backslashes, so `re.search(r"...")` in code never fuses into a phrase."""
    return re.sub(r"[\s\-_./]+", "", s.casefold())


def _term_hit(term, norm_text, squashed_text):
    """Four passes (2026-11-12 reviews):
    (1) word-bounded on whitespace-normalised text;
    (2) a multi-part term with its internal separators optional (glued forms such as
        `acmewidget-city`), still word-bounded at both ends;
    (3) a single-word term of 6+ alphanumerics as a plain substring -- catches it
        inside a slug like `x<term>-dd-tracker`;
    (4) a multi-part term whose squashed form is 8+ characters, as an UNBOUNDED
        substring of the joiner-squashed text -- catches it glued inside a longer slug
        (`x-acme-widget-city`).
    Short single words stay word-bounded only (no false hits inside ordinary words)."""
    if _term_re(term).search(norm_text):
        return True
    low = term.casefold()
    multi = bool(re.search(r"[^0-9a-z]", low))
    sq = _squash(term)
    if multi and len(sq) >= 5 and _glued_re(term).search(norm_text):
        return True
    if re.fullmatch(r"[0-9a-z]{6,}", low) and low in norm_text:
        return True
    return multi and len(sq) >= 8 and sq in squashed_text


def denylist_hits(text, terms):
    """Indices (into terms) of every term present in text. Never returns the term."""
    n, sq = _norm(text), _light_squash(text)
    return [i for i, term in enumerate(terms) if _term_hit(term, n, sq)]


def denylist_files(root):
    """Every git-tracked file under root (falls back to a filesystem walk without git)."""
    try:
        out = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
        rels = [r for r in out.decode("utf-8", "surrogateescape").split("\0") if r]
        return [root / r for r in rels if (root / r).is_file()]
    except (OSError, subprocess.CalledProcessError):
        return sorted(p for p in root.rglob("*") if p.is_file() and ".git" not in p.parts)


def scannable_text(path, root):
    """Text to scan, None for a skipped binary; raises Unscannable for a file outside
    _archive/ that cannot be read as text."""
    rel = path.relative_to(root)
    in_archive = bool(rel.parts) and rel.parts[0] == "_archive"
    suffix = path.suffix.lower()
    data = path.read_bytes()
    if suffix in _MEDIA:
        return None
    if suffix in _OFFICE_ZIP:
        # Office zips are scanned everywhere, _archive/ included (2026-11-12: three
        # archived template copies escaped when archived Office files were skipped).
        # .rels parts are read too (hyperlink targets and external references).
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".xml"))
                rels = "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".rels"))
            # .rels content lives in attributes (Target=...), which tag-stripping drops.
            xml += "\n" + " ".join(re.findall(r'\b(?:Target|Id|Type)="([^"]*)"', rels))
        except zipfile.BadZipFile:
            raise Unscannable(str(rel))
        return html.unescape(re.sub(r"<[^>]+>", "", xml) + "\n" + re.sub(r"<[^>]+>", " ", xml))
    if suffix == ".pdf":
        if in_archive:
            return None
        try:
            import fitz  # PyMuPDF; tools-tests.yml installs it
        except ImportError:
            raise Unscannable(f"{rel} (PyMuPDF not installed)")
        with fitz.open(stream=data, filetype="pdf") as doc:
            return "\n".join(page.get_text() for page in doc)
    if data[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return data.decode("utf-16")
        except UnicodeDecodeError:
            pass
    if b"\0" in data:
        if in_archive:
            return None
        raise Unscannable(str(rel))
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None if in_archive else data.decode("cp1252", "ignore")
_STREET = re.compile(
    r"\b\d{1,6}(?:-\d{1,6})?,?\s+(?:[NSEW]\.?\s+)?(?:[A-Z][\w.']*\s+){1,4}"
    r"(?:St|Street|Rd|Road|Ave|Avenue|Blvd|Dr|Drive|Way|Pkwy|Parkway|Ln|Lane|Ct|Court|Pike|Hwy)\b\.?")


def find_schema_references(root):
    out = []
    for p in sorted(root.rglob("*.md")):
        rel = p.relative_to(root)
        if any(part in _SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if p.parent.name == "references" and "schema" in p.name.lower():
            out.append(p)
    return out


def _cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def _tables(text):
    """Yield (header_cells, [row_cells, ...]) for each pipe table in markdown text."""
    lines = text.splitlines()
    i = 0
    while i < len(lines) - 1:
        if lines[i].lstrip().startswith("|") and re.match(r"^\s*\|[\s:|-]+\|\s*$", lines[i + 1]):
            header, rows, j = _cells(lines[i]), [], i + 2
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                rows.append(_cells(lines[j]))
                j += 1
            yield header, rows
            i = j
        else:
            i += 1


def schema_problems(text):
    """Non-synthetic markers in one schema reference (empty = clean). Reports
    locations only, never the offending value (it may be the PII)."""
    found = []
    for t, (header, rows) in enumerate(_tables(text), 1):
        ex_cols = [k for k, h in enumerate(header) if h.lower().startswith("example")]
        field_col = next((k for k, h in enumerate(header) if h.lower() == "field"), None)
        for k in ex_cols:
            if not re.search(r"synthetic|fictional", header[k], re.I):
                found.append(f"table {t}: Example column header is not labelled synthetic")
        for r, row in enumerate(rows, 1):
            where = f"table {t} row {r}"
            for k, cell in enumerate(row):
                for m in _EMAIL.finditer(cell):
                    if not _EMAIL_OK.search(m.group(0)):
                        found.append(f"{where} col {k + 1}: non-example email address")
                for m in _PHONE.finditer(cell):
                    if not _PHONE_OK.match(m.group(0)):
                        found.append(f"{where} col {k + 1}: phone number outside 555-01xx")
                if _ID.search(cell):
                    found.append(f"{where} col {k + 1}: parcel/instrument/case-number shape")
                for m in _STREET.finditer(cell):
                    if "example" not in m.group(0).lower():
                        found.append(f"{where} col {k + 1}: street address not on an Example street")
            if field_col is not None and field_col < len(row) and _PARTY_FIELD.search(row[field_col]):
                for k in ex_cols:
                    if k >= len(row):
                        continue
                    segs = [s.strip() for s in _SEGMENT_SPLIT.split(row[k])]
                    if not all(_SEGMENT_OK.match(s) for s in segs):
                        found.append(f"{where}: party/contact example is not an anchored synthetic placeholder")
    return found


class TestSchemaReferenceExamples(unittest.TestCase):
    def test_at_least_one_schema_reference_is_checked(self):
        self.assertTrue(find_schema_references(REPO), "no references/*schema*.md found to check")

    def test_every_schema_reference_example_is_synthetic(self):
        for p in find_schema_references(REPO):
            with self.subTest(path=str(p.relative_to(REPO))):
                self.assertEqual(schema_problems(p.read_text(encoding="utf-8")), [])


class TestLocalDenylist(unittest.TestCase):
    def test_no_denylisted_real_token_in_scope(self):
        terms = load_denylist()
        if terms is None:
            sys.stderr.write(
                "\nWARNING: tools/real-identifiers.local.json is absent -- the real-token "
                "denylist check did NOT run (shape checks only). See "
                "tools/real-identifiers.local.json.example.\n")
            return
        self.assertTrue(terms, "local denylist is empty")
        for p in denylist_files(REPO):
            rel = str(p.relative_to(REPO))
            try:
                text = scannable_text(p, REPO)
            except Unscannable as e:
                with self.subTest(path=rel):
                    self.fail(f"unscannable file outside _archive/: {e}")
                continue
            if text is None:
                continue
            hits = denylist_hits(text, terms)
            if hits:
                with self.subTest(path=rel):
                    # Indices only -- the terms are the real data.
                    self.assertEqual(hits, [])

    def test_denylist_file_is_gitignored(self):
        ignore = (REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn("tools/real-identifiers.local.json", [l.strip() for l in ignore])

    def test_example_file_is_well_formed_and_fake(self):
        ex = REPO / "tools" / "real-identifiers.local.json.example"
        self.assertEqual(load_denylist(ex), ["Zephyrton Widget Holdings", "000-999999"])

    def test_glued_split_and_unreadable_forms_are_caught(self):
        # 2026-11-12 review R7: three ways the first widened scanner passed real data.
        terms = ["Zephyrton Widget", "Zephyrton", "Qux"]
        self.assertIn(0, denylist_hits("deal slug zephyrtonwidget-cincinnati", terms))   # glued multi-word
        self.assertIn(1, denylist_hits("task xzephyrton-dd-tracker", terms))             # single word in a slug
        self.assertIn(0, denylist_hits("run x-zephyrton-widgetco-retire", terms))         # multi-part, unbounded (8+)
        self.assertEqual(denylist_hits('re.search(r"zephyrton\\\\widget")', ["Zephyrton Widget"]), [])  # code is not a slug
        self.assertEqual(denylist_hits("the quxote file", terms), [])                     # short word stays bounded
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "skill").mkdir()
            with zipfile.ZipFile(root / "skill" / "t.docx", "w") as z:
                z.writestr("word/document.xml",
                           "<w:p><w:t>Zephyrton</w:t></w:p><w:p><w:t>Ohio</w:t></w:p><w:t>Wid</w:t><w:t>get</w:t>")
            text = scannable_text(root / "skill" / "t.docx", root)
            self.assertIn(1, denylist_hits(text, terms))                                  # paragraph boundary
            self.assertIn("Widget", text)                                                 # word split across runs
            (root / "skill" / "u16.md").write_bytes("Zephyrton".encode("utf-16"))
            self.assertIn(1, denylist_hits(scannable_text(root / "skill" / "u16.md", root), terms))
            (root / "skill" / "blob.dat").write_bytes(b"Zeph\0yrton")
            with self.assertRaises(Unscannable):
                scannable_text(root / "skill" / "blob.dat", root)

    def test_scope_is_whole_repo_with_office_text_and_archive_binaries_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "_archive").mkdir()
            (root / "skill").mkdir()
            for rel in ("skill/t.docx", "_archive/t.docx"):
                with zipfile.ZipFile(root / rel, "w") as z:
                    z.writestr("word/document.xml", "<w:t>Acme</w:t><w:t> Holdings</w:t>")
            (root / "skill" / "notes.md").write_text("plain Acme Holdings", encoding="utf-8")
            (root / "_archive" / "blob.bin").write_bytes(b"Acme\0Holdings")
            self.assertIn("Acme Holdings", scannable_text(root / "skill" / "t.docx", root))
            self.assertIn("Acme Holdings", scannable_text(root / "_archive" / "t.docx", root))  # archived Office scanned
            with zipfile.ZipFile(root / "skill" / "r.docx", "w") as z:
                z.writestr("word/_rels/document.xml.rels", '<Relationship Target="https://acme-holdings.example/x"/>')
            self.assertIn("acme-holdings", scannable_text(root / "skill" / "r.docx", root))  # .rels parts read
            self.assertIsNone(scannable_text(root / "_archive" / "blob.bin", root))
            self.assertIn("Acme", scannable_text(root / "skill" / "notes.md", root))
        tracked = {str(p.relative_to(REPO)).replace("\\", "/") for p in denylist_files(REPO)}
        self.assertIn("README.md", tracked)  # whole repo, not just a skill subtree

    def test_matcher(self):
        terms = ["Acme Holdings", "12/31/2099", "4,321"]
        self.assertEqual(denylist_hits("x ACME   holdings y", terms), [0])
        self.assertEqual(denylist_hits("expires 12/31/2099.", terms), [1])
        self.assertEqual(denylist_hits("$14,321 and 4,3210", terms), [])
        self.assertEqual(denylist_hits("$4,321.00", terms), [2])


class TestSchemaCheckerCatchesRealLookingData(unittest.TestCase):
    CLEAN = (
        "| Fact # | Field | Type | Example (synthetic) |\n"
        "|---|---|---|---|\n"
        "| P-001 | Purchaser — Contracting Entity | Text | Example Buyer Holdings, LLC (fictional) |\n"
        "| P-005 | Purchaser — Principal Email | Text | principal@buyer.example |\n"
        "| P-008 | Buyer's Counsel — Attorney | Text | [Attorney Name], Esq. (example) |\n"
        "| P-011 | Seller — Address (Notice) | Text | 100 Example Way, Anytown, OH 43000 |\n"
        "| P-015 | Broker(s) — Firm + Agent | Text | [Agent Name] — Example Brokerage Co. — representing Seller; Seller pays under separate agreement |\n"
        "| P-017 | Parcel ID #1 | Text | EXAMPLE-PARCEL-A |\n"
        "| P-036 | Escrow Agent | Text | Example Title Co. (fictional), (555) 555-0100 |\n"
        "| P-031 | Purchase Price | Number (USD) | $3,000,000.00 |\n"
    )

    def test_clean_synthetic_table_passes(self):
        self.assertEqual(schema_problems(self.CLEAN), [])

    def test_each_real_looking_cell_is_flagged(self):
        swaps = {
            "Example (synthetic)": "Example (Some Deal)",
            "Example Buyer Holdings, LLC (fictional)": "Acme Partners, LLC",
            "principal@buyer.example": "jdoe@acmelaw.net",
            "100 Example Way": "4321 W. Main Street",
            "EXAMPLE-PARCEL-A": "999-123456",
            "(555) 555-0100": "(999) 123-4567",
            "[Agent Name]": "Pat Q. Broker",
        }
        for old, bad in swaps.items():
            with self.subTest(swap=old):
                self.assertTrue(schema_problems(self.CLEAN.replace(old, bad)), f"{bad!r} was not flagged")

    def test_marker_bypasses_are_flagged(self):
        # 2026-11-12 review: a marker anywhere, or an EX- prefix, used to pass real values.
        for old, bad in {
            "Example Buyer Holdings, LLC (fictional)": "Acme Partners, LLC (example)",
            "[Attorney Name], Esq. (example)": "Pat Lawyer, Esq. (example)",
            "EXAMPLE-PARCEL-A": "EX-999-123456",
            "[Agent Name]": "Pat Broker (fictional)",
        }.items():
            with self.subTest(bypass=bad):
                self.assertTrue(schema_problems(self.CLEAN.replace(old, bad)), f"{bad!r} was not flagged")

    def test_notes_column_cells_are_scanned_too(self):
        for docket in ("99 CV 123456", "99-CV-123456"):
            with self.subTest(docket=docket):
                text = ("| Fact # | Field | Notes |\n|---|---|---|\n"
                        f"| P-089 | Case Number | {docket} |\n")
                self.assertTrue(schema_problems(text))

    def test_discovery_only_takes_references_schema_files(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "skill" / "references").mkdir(parents=True)
            (root / "_archive" / "skill" / "references").mkdir(parents=True)
            (root / "skill" / "references" / "fact-schema.md").write_text("", encoding="utf-8")
            (root / "skill" / "references" / "patterns.md").write_text("", encoding="utf-8")
            (root / "skill" / "schema.md").write_text("", encoding="utf-8")
            (root / "_archive" / "skill" / "references" / "old-schema.md").write_text("", encoding="utf-8")
            self.assertEqual([p.name for p in find_schema_references(root)], ["fact-schema.md"])


class TestShippedExampleRegisters(unittest.TestCase):
    def test_at_least_one_example_register_is_checked(self):
        # A rename that slipped past the glob must not turn this gate into a no-op.
        self.assertTrue(find_example_registers(REPO), "no example register found to check")

    def test_every_example_register_is_synthetic(self):
        for p in find_example_registers(REPO):
            with self.subTest(path=str(p.relative_to(REPO))):
                reg = json.loads(p.read_text(encoding="utf-8"))
                # Report field paths only, never the values (they may be the PII).
                self.assertEqual(problems(reg), [])

    def test_retired_real_register_is_not_back(self):
        old = REPO / "lease-generation" / "references" / "example-register-northwood-15a.json"
        self.assertFalse(old.exists(), "the retired real-data example register is back in references/")


class TestCheckerCatchesRealLookingData(unittest.TestCase):
    def _synthetic(self):
        return {
            "_synthetic": True, "deal_id": "EXAMPLE-1-ZEPHYR-2026-01",
            "landlord": {"entity": "Example Holdings, LLC (fictional)",
                         "notice_address": "1 Example Way, Anytown, OH 43000"},
            "tenant": {"entity": "Zephyr Example Corp", "co_tenants": ["Example Principal"],
                       "notice_email": "notices@zephyr.example"},
            "premises": {"address": "1 Example Way"},
            "broker": {"firm": "Example Brokerage"},
        }

    def test_clean_synthetic_register_passes(self):
        self.assertEqual(problems(self._synthetic()), [])

    def test_each_real_looking_field_is_flagged(self):
        cases = {
            ("_synthetic",): False,
            ("deal_id",): "ZEPHYR-1-2026-01",
            ("tenant", "entity"): "Zephyr Corp LLC",
            ("landlord", "notice_address"): "1 Main Street, Anytown, OH 43000",
            ("premises", "address"): "1 Main Street",
            ("tenant", "notice_email"): "owner@zephyrcorp.com",
            ("broker", "firm"): "Acme Realty",
        }
        for path, bad in cases.items():
            with self.subTest(path=path):
                reg = self._synthetic()
                node = reg
                for k in path[:-1]:
                    node = node[k]
                node[path[-1]] = bad
                self.assertTrue(problems(reg), f"{path} = {bad!r} was not flagged")

    def test_real_looking_co_tenant_is_flagged(self):
        reg = self._synthetic()
        reg["tenant"]["co_tenants"] = ["Jordan Smith"]
        self.assertTrue(problems(reg))

    def test_discovery_skips_archive_and_finds_nested(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "skill" / "references").mkdir(parents=True)
            (root / "_archive" / "old").mkdir(parents=True)
            (root / "skill" / "references" / "example-register-x.json").write_text("{}", encoding="utf-8")
            (root / "_archive" / "old" / "example-register-y.json").write_text("{}", encoding="utf-8")
            names = [p.name for p in find_example_registers(root)]
            self.assertEqual(names, ["example-register-x.json"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
