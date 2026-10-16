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


# ---------------------------------------------------------------------------
# v1.10: run-formatting parity (standard post-check) + the power-rights line
# ---------------------------------------------------------------------------
FIXTURE_V28 = HERE / "fixtures" / "ORA_MasterLease_ShallowBayIndustrial_v2.8_TEMPLATE.docx"
FIXTURE_V31 = HERE / "fixtures" / "ORA_MasterLease_ShallowBay_MultiTenantMG_v3.1_TEMPLATE.docx"
LEASE_QC = HERE.parent.parent / "lease-form-qc" / "scripts" / "lease_qc.py"
PROD_V27 = HERE.parent.parent / "lease-form-qc" / "tests" / "fixtures"   # production v2.7 templates
NNN_LINE_KEYS = ("MD-COL", "OH-ST-NNN")

# Phase-1 provision markers (exact approved wording) every power-rights output must carry.
POWER_MARKERS = {
    "P1": "exclusive right, for itself and its licensees, lessees and their financing parties",
    "P2": "utility, interconnection and access easements and licenses",
    "P2-notice": "twenty-four (24) hours\u2019 notice of any planned interruption of electrical service",
    "P3": "Tenant\u2019s electrical service is limited to the service serving the",
    "P3-carve-out": "(other than any electrical capacity, service, transformer, switchgear or metering",
    "P4": "Operating Costs exclude all costs of, and all revenues, credits and incentives from, any energy generation",
    "P5": "sign the utility\u2019s authorization allowing Landlord to obtain directly",
    "P6": "estoppel certificate or acknowledgment reasonably requested by any lessee or licensee of Landlord",
    "P7": "Landlord may install electric-vehicle charging equipment in the parking areas",
    "P8": "TENANT BACKUP POWER AND ENERGY STORAGE",
    "P8-bracket": "[OPTIONAL MODULE \u2014 INCLUDE ONLY IF TENANT WILL INSTALL A STANDBY GENERATOR",
    "P8-counsel": "[COUNSEL REVIEW REQUIRED BEFORE FIRST USE]",
}


def _L(states, P):
    if P.get("variant") == "single-tenant":
        return states.get(P["state_code"], {})
    if P.get("home_state"):
        return {"state": "Ohio"}
    return states[P["state_code"]]


class FormatParityTests(unittest.TestCase):
    """format_parity() is a standard post-check (main() runs it on every output)."""

    @classmethod
    def setUpClass(cls):
        cls.props = json.loads((CONFIG / "properties.json").read_text(encoding="utf-8"))
        cls.states = json.loads((CONFIG / "state_overlays.json").read_text(encoding="utf-8"))

    def keys_for(self, master):
        doc = Document(str(master))
        if rebase.is_v3(doc):
            return [k for k, P in self.props.items() if isinstance(P, dict) and "v3_0" in P]
        if rebase.power_rights_master(doc):
            return list(NNN_LINE_KEYS)
        return [k for k in self.props if not k.startswith("_")]

    def test_every_output_of_every_master_has_format_parity(self):
        for master in (FIXTURE_MASTER, FIXTURE_V28, FIXTURE_V30, FIXTURE_V31):
            m_doc = Document(str(master))
            for key in self.keys_for(master):
                with self.subTest(master=master.name, property=key):
                    P = self.props[key]
                    out = rebase.rebase_one(master, P, _L(self.states, P))
                    self.assertEqual(rebase.format_parity(m_doc, out), [])

    def test_bold_label_anchor_is_caught(self):
        """The pre-v1.10 NNN BLI anchor started in the bold 'Base Year:' label, so the
        fill came out bold."""
        doc = Document(str(FIXTURE_MASTER))
        rebase.apply(doc, [("Base Year: [BASE YEAR]", "Base Year: Not applicable — full NNN", 1)])
        errs = rebase.format_parity(Document(str(FIXTURE_MASTER)), doc)
        self.assertTrue(any("Not applicable" in e for e in errs), errs)

    def test_defined_term_spanned_by_an_anchor_is_caught(self):
        """The pre-v1.10 single-tenant demise anchor spanned the bold defined term
        "Demised Premises" and un-bolded it."""
        doc = Document(str(FIXTURE_MASTER))
        old = ("approximately [PREMISES RSF] square feet of rentable area in the building situated at "
               "[PREMISES ADDRESS] (such rentable area being hereinafter referred to as the \"Demised Premises\")")
        rebase.apply(doc, [(old, old.replace("approximately [PREMISES RSF]", "approx. [PREMISES RSF]"), 1)])
        errs = rebase.format_parity(Document(str(FIXTURE_MASTER)), doc)
        self.assertTrue(errs)

    def test_production_v27_templates_carried_the_defects_v1_10_fixes(self):
        """Evidence for the v1.10 re-keys: the production MD-COL / OH-ST-NNN v2.7
        templates (built before the parity check existed) are text-identical to
        today's output but carry the formatting defects; today's output does not."""
        master = Document(str(FIXTURE_MASTER))
        for key, name in (("MD-COL", "ORA_MasterLease_ShallowBay_MD-Columbia-9050RedBranchRoad_v2.7_TEMPLATE.docx"),
                          ("OH-ST-NNN", "ORA_MasterLease_ShallowBay_OH-SingleTenant-NNN_v2.7_TEMPLATE.docx")):
            with self.subTest(property=key):
                prod = Document(str(PROD_V27 / name))
                self.assertTrue(rebase.format_parity(master, prod))
                out = rebase.rebase_one(FIXTURE_MASTER, self.props[key], _L(self.states, self.props[key]))
                self.assertEqual([p.text for p in out.paragraphs], [p.text for p in prod.paragraphs])
                self.assertEqual(rebase.format_parity(master, out), [])

    def test_near_black_colour_and_non_visual_props_are_not_formatting(self):
        from lxml import etree
        w = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        mk = lambda x: etree.fromstring(f'<w:rPr xmlns:w="{w}">{x}</w:rPr>')  # noqa: E731
        self.assertEqual(rebase._rpr_key(mk('<w:color w:val="2F2F2F"/><w:lang w:val="en-US"/>')), ())
        self.assertNotEqual(rebase._rpr_key(mk('<w:color w:val="FF0000"/>')), ())
        self.assertNotEqual(rebase._rpr_key(mk("<w:b/>")), rebase._rpr_key(mk("")))
        self.assertEqual(rebase._rpr_key(mk('<w:b w:val="0"/>')), ())


class PowerRightsRebaseTests(unittest.TestCase):
    """Phase 2 (2026-10-15): the v2.8 NNN-line and v3.1 MG-line masters rebase cleanly;
    every output passes lease_qc with the power-rights checks enforced and carries every
    provision marker; single-tenant paper drops only the P7 allocation fragment."""

    @classmethod
    def setUpClass(cls):
        cls.props = json.loads((CONFIG / "properties.json").read_text(encoding="utf-8"))
        cls.states = json.loads((CONFIG / "state_overlays.json").read_text(encoding="utf-8"))
        cls.td = tempfile.TemporaryDirectory()
        cls.out = pathlib.Path(cls.td.name)
        cls.outputs = {}
        for master, tag in ((FIXTURE_V28, "v28"), (FIXTURE_V31, "v31")):
            d = cls.out / tag
            r = subprocess.run([sys.executable, "-I", "-B", str(HERE / "rebase.py"), "--master", str(master),
                                "--all", "--out", str(d)], capture_output=True, text=True)
            cls.outputs[tag] = (r, sorted(d.glob("*.docx")) if d.exists() else [])

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def test_power_rights_master_detection(self):
        self.assertFalse(rebase.power_rights_master(Document(str(FIXTURE_MASTER))))
        self.assertTrue(rebase.power_rights_master(Document(str(FIXTURE_V28))))
        self.assertFalse(rebase.power_rights_master(Document(str(FIXTURE_V30))))
        self.assertTrue(rebase.power_rights_master(Document(str(FIXTURE_V31))))

    def test_cli_all_emits_the_six_line_templates(self):
        r28, f28 = self.outputs["v28"]
        r31, f31 = self.outputs["v31"]
        self.assertEqual(r28.returncode, 0, r28.stdout + r28.stderr)
        self.assertEqual(r31.returncode, 0, r31.stdout + r31.stderr)
        self.assertEqual([f.name for f in f28], [
            "ORA_MasterLease_ShallowBay_MD-Columbia-9050RedBranchRoad_v2.8_TEMPLATE.docx",
            "ORA_MasterLease_ShallowBay_OH-SingleTenant-NNN_v2.8_TEMPLATE.docx"])
        self.assertIn("skips the MG-line properties", r28.stdout)
        self.assertEqual(len(f31), 4)
        self.assertTrue(all(f.name.endswith("_v3.1_TEMPLATE.docx") for f in f31))

    def test_every_output_passes_lease_qc_enforced_and_carries_every_marker(self):
        for path in self.outputs["v28"][1] + self.outputs["v31"][1]:
            with self.subTest(template=path.name):
                r = subprocess.run([sys.executable, "-I", "-B", str(LEASE_QC), str(path), "--json"],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr)
                rep = json.loads(r.stdout)[0]
                self.assertEqual(rep["failures"], [])
                self.assertEqual(rep["form"]["power_rights"], "ENFORCED")
                self.assertEqual(rep["checks_run"], 68 if "_v2.8_" in path.name else 73)
                body = "\n".join(p.text for p in Document(str(path)).paragraphs)
                missing = [k for k, m in POWER_MARKERS.items() if m not in body]
                self.assertEqual(missing, [])

    def test_single_tenant_drops_only_the_allocation_fragment(self):
        path = next(p for p in self.outputs["v28"][1] if "SingleTenant" in p.name)
        body = "\n".join(p.text for p in Document(str(path)).paragraphs)
        self.assertNotIn("Allocation", body)
        self.assertIn("Landlord may install electric-vehicle charging equipment in the parking areas, designate "
                      "spaces for vehicles while charging, and charge users for charging, provided that Tenant "
                      "retains reasonable access to parking for its operations.", body)
        self.assertIn("Tenant shall have the exclusive right to use the parking areas", body)
        md = next(p for p in self.outputs["v28"][1] if "Columbia" in p.name)
        self.assertIn(rebase.ST_P7_ALLOCATION_FRAGMENT, "\n".join(p.text for p in Document(str(md)).paragraphs))

    def test_single_tenant_p7_rule_is_asserted(self):
        # v2.7 has no P7 sentence: the rule is not applied there (and the v2.7 output is unchanged) ...
        P = self.props["OH-ST-NNN"]
        rebase.rebase_one(FIXTURE_MASTER, P, {})
        # ... and on a v2.8 master whose P7 fragment is missing, the run fails loudly.
        doc = Document(str(FIXTURE_V28))
        rebase.apply(doc, [(rebase.ST_P7_ALLOCATION_FRAGMENT, " (reworded)", 1)])
        rebase.apply(doc, rebase.single_tenant_rules())
        with self.assertRaises(SystemExit) as cm:
            rebase.apply(doc, rebase.single_tenant_power_rules())
        self.assertIn("ANCHOR DRIFT", str(cm.exception))

    def test_explicit_property_still_reaches_a_moved_property_on_v28(self):
        P = self.props["MD-EAS"]
        out = self.out / "md-eas-v28.docx"
        rebase.rebase_one(FIXTURE_V28, P, self.states["MD"]).save(str(out))
        rebase.post_check(out, P, self.states["MD"])


if __name__ == "__main__":
    unittest.main()
