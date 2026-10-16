#!/usr/bin/env python3
"""Tests for rebase.py (masterlease-jurisdiction-rebase v1.1).

Three cases required by the 2026-08-03 Master Lease conformance session close-out:
1. Parity against a known master — the real OH v2.6 controlled master rebases
   cleanly (no anchor drift, no post-check failure) into a state-conformed template.
2. article() unit cases, including the "an Ohio" / "a Utah" fix that motivated v1.1.
3. Fail-closed on a missing entity_state field and on a RESEARCH-REQUIRED state.
"""
import copy
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
CONFIG = HERE.parent / "config"
FIXTURE_MASTER = HERE / "fixtures" / "ORA_MasterLease_ShallowBayIndustrial_v2.7_TEMPLATE.docx"  # swapped from v2.6, 2026-10-06

sys.path.insert(0, str(HERE))
import rebase  # noqa: E402
from docx import Document  # noqa: E402


class ArticleTests(unittest.TestCase):
    """The v1.1 fix: 'an' before a vowel-sound state name, 'a Utah' by exception."""

    def test_vowel_initial_states_take_an(self):
        for state in ("Ohio", "Indiana", "Alabama", "Illinois", "Iowa", "Arizona"):
            with self.subTest(state=state):
                self.assertEqual(rebase.article(state), "an")

    def test_consonant_and_u_states_take_a(self):
        # Utah is the case v1.1 exists for: 'U' reads as a consonant sound, so it
        # must NOT fall into the vowel-letter bucket with Indiana/Ohio.
        for state in ("Maryland", "Missouri", "Wisconsin", "Kansas", "Tennessee", "Utah"):
            with self.subTest(state=state):
                self.assertEqual(rebase.article(state), "a")


class FailClosedTests(unittest.TestCase):
    """v1.1: entity_state is REQUIRED and sourced; RESEARCH-REQUIRED states refuse to run."""

    def test_build_rules_fails_closed_on_missing_entity_state(self):
        P = {"entity": "TEST PROPERTY, LLC", "state_code": "MD"}  # no entity_state
        L = {"state": "Maryland"}
        with self.assertRaises(SystemExit) as ctx:
            rebase.build_rules(P, L)
        self.assertIn("entity_state", str(ctx.exception))

    def test_cli_fails_closed_on_research_required_state(self):
        with tempfile.TemporaryDirectory() as td:
            td = pathlib.Path(td)
            scripts_dir = td / "scripts"
            config_dir = td / "config"
            scripts_dir.mkdir()
            config_dir.mkdir()
            shutil.copy(HERE / "rebase.py", scripts_dir / "rebase.py")

            real_overlays = json.loads((CONFIG / "state_overlays.json").read_text(encoding="utf-8"))
            self.assertTrue(
                real_overlays["IN"].get("RESEARCH_REQUIRED"),
                "fixture assumption broken: IN is expected to be RESEARCH-REQUIRED in the real config",
            )
            (config_dir / "state_overlays.json").write_text(
                json.dumps({"IN": real_overlays["IN"]}), encoding="utf-8"
            )
            (config_dir / "properties.json").write_text(
                json.dumps({
                    "TEST-IN": {
                        "state_code": "IN",
                        "entity": "TEST INDIANA, LLC",
                        "entity_state": "Indiana",
                        "label": "TEST-IN",
                        "premises": "1 Test St, Test City, Indiana",
                        "building_def": "the building known as 1 Test St, Test City, Indiana, "
                                         "containing 1,000 square feet of rentable area",
                        "project_def": None,
                        "share_denominator": "bears to the total rentable square footage of the "
                                              "Building, being 1,000 square feet ",
                        "payment_direction": None,
                        "pm_block": ["COPY TO:[PROPERTY MANAGER]", "[MANAGER STREET ADDRESS]",
                                     "[MANAGER CITY, STATE ZIP]", "ATTN: [MANAGER CONTACT]"],
                    }
                }),
                encoding="utf-8",
            )

            out_dir = td / "out"
            result = subprocess.run(
                [sys.executable, "-I", "-B", str(scripts_dir / "rebase.py"),
                 "--master", str(FIXTURE_MASTER), "--property", "TEST-IN", "--out", str(out_dir)],
                capture_output=True, text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("RESEARCH-REQUIRED", result.stdout + result.stderr)
            self.assertFalse(out_dir.exists() and any(out_dir.iterdir()),
                              "fail-closed run must not leave a partial output file")


class ParityAgainstKnownMasterTests(unittest.TestCase):
    """The real OH v2.5 controlled master rebases cleanly for every ratified property."""

    @classmethod
    def setUpClass(cls):
        if not FIXTURE_MASTER.exists():
            raise unittest.SkipTest(f"fixture master not found: {FIXTURE_MASTER}")
        cls.properties = json.loads((CONFIG / "properties.json").read_text(encoding="utf-8"))
        cls.states = json.loads((CONFIG / "state_overlays.json").read_text(encoding="utf-8"))

    def _rebase_one(self, key, out_dir):
        P = self.properties[key]
        # Single-tenant variants are anchored to the master's own state and take
        # no overlay (mirrors main()); everything else requires a ratified overlay.
        if P.get("variant") == "single-tenant":
            L = self.states.get(P["state_code"], {})
        elif P.get("home_state"):  # 2026-10-06: OH home-state property (OH-MOR), no overlay
            L = {"state": "Ohio"}
        else:
            L = self.states[P["state_code"]]
        # Routes through rebase.rebase_one() -- the same pipeline main() uses -- so a
        # step added there (e.g. the NNN override) can't drift out of sync with its
        # own test again the way it did the first time this override was added
        # (2026-08-04: this test called apply()+insert_savings_clause() directly and
        # missed the new convert_to_nnn() step main() had).
        doc = rebase.rebase_one(FIXTURE_MASTER, P, L)
        out = out_dir / f"{key}.docx"
        doc.save(str(out))
        rebase.post_check(out, P, L)
        return out, P, L

    def test_all_ratified_properties_rebase_cleanly(self):
        # Anchor-drift / post-check assertions inside rebase.py itself are the pass
        # condition here: any mismatch against the real master calls sys.exit().
        with tempfile.TemporaryDirectory() as td:
            out_dir = pathlib.Path(td)
            for key in self.properties:
                if key == "_comment":
                    continue
                with self.subTest(property=key):
                    out, P, L = self._rebase_one(key, out_dir)
                    full = "\n".join(p.text for p in Document(str(out)).paragraphs)
                    if P.get("variant") == "single-tenant":
                        # Generic OH-anchored variant: keeps Ohio and its tokens;
                        # post_check() inside _rebase_one carries the assertions.
                        self.assertIn("the entire building situated at [PREMISES ADDRESS]", full)
                        self.assertIn(rebase.SAVINGS_TITLE, full)
                        continue
                    if not P.get("home_state"):
                        self.assertNotIn("Ohio", full)
                    self.assertIn(P["entity"], full)
                    self.assertIn(L["state"], full)
                    self.assertIn(rebase.SAVINGS_TITLE, full)

    def test_md_easton_entity_state_article_applied(self):
        # Regression guard for the specific v1.1 fix: MD-EAS's entity_state is
        # Maryland ('a Maryland limited liability company'), not article-broken.
        with tempfile.TemporaryDirectory() as td:
            out, P, L = self._rebase_one("MD-EAS", pathlib.Path(td))
            full = "\n".join(p.text for p in Document(str(out)).paragraphs)
            self.assertIn("a Maryland limited liability company", full)
            self.assertNotIn("an Maryland", full)



class TestFooterFillAllParts(unittest.TestCase):
    """2026-10-06: the footer fill walked only sec.footer (default footer), leaving
    [PREMISES ADDRESS] in even/first-page footers (MD-COL printed it on every page).
    Every footer part of every rebased multi-tenant template must be filled."""

    def test_no_footer_part_keeps_the_premises_token(self):
        import json, tempfile, zipfile, re as _re
        if not FIXTURE_MASTER.exists():
            raise unittest.SkipTest(f"fixture master not found: {FIXTURE_MASTER}")
        cfg = HERE.parent / "config"
        props = json.loads((cfg / "properties.json").read_text(encoding="utf-8"))
        states = json.loads((cfg / "state_overlays.json").read_text(encoding="utf-8"))
        for key, P in props.items():
            if key.startswith("_") or not isinstance(P, dict) or P.get("variant") == "single-tenant":
                continue
            L = {"state": "Ohio"} if P.get("home_state") else states.get(P["state_code"])
            if not L or L.get("RESEARCH_REQUIRED"):
                continue
            with self.subTest(property=key), tempfile.TemporaryDirectory() as td:
                out = pathlib.Path(td) / "t.docx"
                rebase.rebase_one(FIXTURE_MASTER, P, L).save(str(out))
                with zipfile.ZipFile(out) as z:
                    for n in z.namelist():
                        if _re.match(r"word/footer\d*\.xml$", n):
                            self.assertNotIn("[PREMISES ADDRESS]", z.read(n).decode("utf-8"), n)


# ---------------------------------------------------------------------------
# v3.0 short-form multi-tenant MG master (added 2026-10-15, skill v1.9)
# ---------------------------------------------------------------------------
FIXTURE_V30 = HERE / "fixtures" / "ORA_MasterLease_ShallowBay_MultiTenantMG_v3.0_TEMPLATE.docx"
EXPECTED_V30 = HERE / "fixtures" / "v3.0_expected"   # the 2026-10-08 property templates, unmodified copies
V30_KEYS = ("OH-MOR", "MD-EAS", "MD-SBY", "MO-RAY")
# Salisbury values BEFORE the 2026-10-08 payee direction (properties.json as of v1.8).
SBY_PRE_FIX = {
    "payment_direction": "to 2203 Northwood, LLC through the tenant online portal, payable to Landlord,",
    "pm_block": ["COPY TO:Sperry Van Ness — Miller Commercial", "[MANAGER STREET ADDRESS]",
                 "Salisbury, MD 21801", "ATTN: Brady Smith"],
}


def _norm(s):
    return re.sub(r"[ \t]+", " ", s.replace("\xa0", " ")).strip()


def doc_text(path_or_doc):
    """Body paragraphs + every footer part's paragraphs, whitespace-normalized."""
    d = Document(str(path_or_doc)) if isinstance(path_or_doc, (str, pathlib.Path)) else path_or_doc
    body = [_norm(p.text) for p in d.paragraphs]
    foot = [_norm(p.text) for p in rebase._footer_paragraphs(d)]
    return body, foot


def format_signature(path):
    """Per paragraph: (pPr xml, [(rPr xml, text)...]) with runs of identical
    formatting merged -- equal signatures mean identical text AND identical
    character formatting, whatever the run segmentation."""
    from docx.oxml.ns import qn
    from lxml import etree
    out = []
    for p in Document(str(path)).paragraphs:
        ppr = p._p.find(qn("w:pPr"))
        segs = []
        for r in p.runs:
            rpr = r._r.find(qn("w:rPr"))
            key = etree.tostring(rpr) if rpr is not None else b""
            if not r.text:
                continue
            if segs and segs[-1][0] == key:
                segs[-1][1] += r.text
            else:
                segs.append([key, r.text])
        out.append((etree.tostring(ppr) if ppr is not None else b"", [tuple(s) for s in segs]))
    return out


def expected_path(P):
    return EXPECTED_V30 / f"ORA_MasterLease_ShallowBay_{P['label']}_v3.0_TEMPLATE.docx"


class V30ParityTests(unittest.TestCase):
    """Rebasing the v3.0 master must reproduce each stored v3.0 property template."""

    @classmethod
    def setUpClass(cls):
        if not FIXTURE_V30.exists():
            raise unittest.SkipTest(f"v3.0 fixture master not found: {FIXTURE_V30}")
        cls.props = json.loads((CONFIG / "properties.json").read_text(encoding="utf-8"))
        cls.states = json.loads((CONFIG / "state_overlays.json").read_text(encoding="utf-8"))
        cls.td = tempfile.TemporaryDirectory()
        cls.out = pathlib.Path(cls.td.name)

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def L_for(self, P):
        return {"state": "Ohio"} if P.get("home_state") else self.states[P["state_code"]]

    def build(self, key, P=None, master=FIXTURE_V30):
        P = P or self.props[key]
        L = self.L_for(P)
        doc = rebase.rebase_one(master, P, L)
        out = self.out / f"{key}-{id(P)}.docx"
        doc.save(str(out))
        rebase.post_check(out, P, L)
        return out

    def test_master_form_detection(self):
        self.assertEqual(rebase.master_form(Document(str(FIXTURE_V30))), (3, 0))
        self.assertTrue(rebase.is_v3(FIXTURE_V30))
        self.assertEqual(rebase.master_form(Document(str(FIXTURE_MASTER))), (2, 7))
        self.assertFalse(rebase.is_v3(FIXTURE_MASTER))

    def test_v30_keys_in_config(self):
        self.assertEqual(sorted(k for k, P in self.props.items() if isinstance(P, dict) and "v3_0" in P),
                         sorted(V30_KEYS))

    def test_parity_text_equal(self):
        for key in V30_KEYS:
            with self.subTest(property=key):
                exp = expected_path(self.props[key])
                if not exp.exists():
                    self.skipTest(f"expected template missing: {exp}")
                got_body, got_foot = doc_text(self.build(key))
                exp_body, exp_foot = doc_text(exp)
                self.assertEqual(got_body, exp_body)
                self.assertEqual(got_foot, exp_foot)

    def test_parity_character_formatting_equal(self):
        # Stronger than text: bold labels / defined terms keep their formatting
        # (an anchor spanning a bold run silently un-bolded "Building" and
        # "Hazardous Materials" before the 2026-10-15 anchor narrowing).
        for key in V30_KEYS:
            with self.subTest(property=key):
                self.assertEqual(format_signature(self.build(key)),
                                 format_signature(expected_path(self.props[key])))

    def test_salisbury_payee_fix_is_what_the_stored_template_carries(self):
        """The stored Salisbury v3.0 template already carries Gabriel's 2026-10-08
        payee direction (rent to SVN Miller Commercial Real Estate). The pre-fix
        config must produce EXACTLY the payee/PM differences and nothing else --
        proving the config fix, not a forced pass, is what closes parity."""
        P = copy.deepcopy(self.props["MD-SBY"])
        self.assertIn("SVN Miller Commercial Real Estate, 206 East Main Street, Salisbury, MD 21801",
                      P["payment_direction"])
        self.assertEqual(P["pm_block"][:3], ["COPY TO:SVN Miller Commercial Real Estate",
                                              "206 East Main Street", "Salisbury, MD 21801"])
        P.update(copy.deepcopy(SBY_PRE_FIX))
        got, _ = doc_text(self.build("MD-SBY", P))
        exp, _ = doc_text(expected_path(P))
        diff = [(i, g, e) for i, (g, e) in enumerate(zip(got, exp)) if g != e]
        self.assertEqual(len(got), len(exp))
        changed = {i for i, _g, _e in diff}
        rent = next(i for i, e in enumerate(exp) if e.startswith("Tenant shall pay the sums due at signing"))
        ins = next(i for i, e in enumerate(exp) if e.startswith("Tenant’s insurers must be licensed"))
        copy_to = next(i for i, e in enumerate(exp) if e.startswith("COPY TO:"))
        self.assertEqual(changed, {rent, ins, copy_to, copy_to + 1})
        self.assertIn("to 2203 Northwood, LLC through the tenant online portal", got[rent])
        self.assertIn("SVN Miller Commercial Real Estate", exp[rent])
        self.assertEqual(got[copy_to + 1], "[MANAGER STREET ADDRESS]")
        self.assertEqual(exp[copy_to + 1], "206 East Main Street")

    def test_cli_all_emits_only_v30_properties(self):
        with tempfile.TemporaryDirectory() as td:
            res = subprocess.run([sys.executable, "-I", "-B", str(HERE / "rebase.py"), "--master",
                                  str(FIXTURE_V30), "--all", "--out", td],
                                 capture_output=True, text=True)
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            names = sorted(p.name for p in pathlib.Path(td).iterdir())
            self.assertEqual(names, sorted(expected_path(self.props[k]).name for k in V30_KEYS))

    def test_cli_v30_master_refuses_nnn_property(self):
        with tempfile.TemporaryDirectory() as td:
            res = subprocess.run([sys.executable, "-I", "-B", str(HERE / "rebase.py"), "--master",
                                  str(FIXTURE_V30), "--property", "MD-COL", "--out", td],
                                 capture_output=True, text=True)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("v3_0", res.stdout + res.stderr)
            self.assertFalse(any(pathlib.Path(td).iterdir()))

    def test_anchor_drift_fails_loudly(self):
        # Never-loosen rule: a v3.0 master whose anchor text moved must abort
        # naming the anchor, not emit a half-conformed template.
        d = Document(str(FIXTURE_V30))
        for p in d.paragraphs:
            if "bank holiday in Ohio;" in p.text:
                rebase.replace_in_paragraph(p, "bank holiday in Ohio;", "legal holiday in Ohio;")
        drifted = self.out / "drifted_v3.0.docx"
        d.save(str(drifted))
        with self.assertRaises(SystemExit) as ctx:
            rebase.rebase_one(drifted, self.props["MD-EAS"], self.states["MD"])
        self.assertIn("ANCHOR DRIFT", str(ctx.exception))
        self.assertIn("bank holiday in Ohio;", str(ctx.exception))

    def test_duplicated_anchor_fails_loudly(self):
        d = Document(str(FIXTURE_V30))
        tgt = next(p for p in d.paragraphs if p.text.startswith("Severability."))
        tgt.add_run("  This Lease is governed by the laws of the State of Ohio.")
        dup = self.out / "dup_v3.0.docx"
        d.save(str(dup))
        with self.assertRaises(SystemExit) as ctx:
            rebase.rebase_one(dup, self.props["MO-RAY"], self.states["MO"])
        self.assertIn("expected 1 match(es), found 2", str(ctx.exception))

    def test_missing_v3_signature_note_fails_closed(self):
        L = {k: v for k, v in self.states["MD"].items() if k != "v3_signature_note"}
        with self.assertRaises(SystemExit) as ctx:
            rebase.rebase_one(FIXTURE_V30, self.props["MD-EAS"], L)
        self.assertIn("v3_signature_note", str(ctx.exception))

    def test_property_without_v3_entry_fails_closed(self):
        P = {k: v for k, v in self.props["MD-EAS"].items() if k != "v3_0"}
        with self.assertRaises(SystemExit) as ctx:
            rebase.rebase_one(FIXTURE_V30, P, self.states["MD"])
        self.assertIn("v3_0", str(ctx.exception))

    def test_v27_line_untouched_by_v30_config(self):
        # The v3_0 keys and the Salisbury payee fix must not disturb the v2.7
        # long-form path: every property still rebases the v2.7 fixture.
        for key, P in self.props.items():
            if key.startswith("_"):
                continue
            with self.subTest(property=key):
                if P.get("variant") == "single-tenant":
                    L = self.states.get(P["state_code"], {})
                else:
                    L = self.L_for(P)
                doc = rebase.rebase_one(FIXTURE_MASTER, P, L)
                out = self.out / f"v27-{key}.docx"
                doc.save(str(out))
                rebase.post_check(out, P, L)


if __name__ == "__main__":
    unittest.main()
