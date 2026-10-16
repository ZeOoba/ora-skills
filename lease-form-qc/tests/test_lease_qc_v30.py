#!/usr/bin/env python3
"""Tests for lease_qc.py v3.0 mode, --form, and the power-rights standard (FP1-FP8).

Run:  python3 -I -B lease-form-qc/tests/test_lease_qc_v30.py -v

Corpus: the ORA master/property templates, committed as fixtures so the suite runs
in CI with zero skips (tools/run_suite.sh treats any skip as a failure):
  masterlease-jurisdiction-rebase/scripts/fixtures/              (masters v2.7/v2.8/v3.0/v3.1)
  masterlease-jurisdiction-rebase/scripts/fixtures/v3.0_expected/ (four v3.0 property templates)
  lease-form-qc/tests/fixtures/                                   (two v2.7 property templates, Exhibit B v1.3)
LEASE_QC_CORPUS (a directory) is searched first when set, e.g. to re-run the
benchmarks against the staged Leases folder.
"""
import copy
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent
SCRIPTS = SKILL / "scripts"
REPO = SKILL.parent
REBASE_FIX = REPO / "masterlease-jurisdiction-rebase" / "scripts" / "fixtures"
sys.path.insert(0, str(SCRIPTS))
import lease_qc as q  # noqa: E402
from ora_doc_qc import extract, norm, run_checks  # noqa: E402

CORPUS_DIRS = ([pathlib.Path(os.environ["LEASE_QC_CORPUS"])] if os.environ.get("LEASE_QC_CORPUS") else []) + [
    REBASE_FIX, REBASE_FIX / "v3.0_expected", HERE / "fixtures"]
V27 = ["ORA_MasterLease_ShallowBayIndustrial_v2.7_TEMPLATE.docx",
       "ORA_MasterLease_ShallowBay_MD-Columbia-9050RedBranchRoad_v2.7_TEMPLATE.docx",
       "ORA_MasterLease_ShallowBay_OH-SingleTenant-NNN_v2.7_TEMPLATE.docx"]
V30 = ["ORA_MasterLease_ShallowBay_MultiTenantMG_v3.0_TEMPLATE.docx",
       "ORA_MasterLease_ShallowBay_OH-Columbus-384-420MorrisonRoad_v3.0_TEMPLATE.docx",
       "ORA_MasterLease_ShallowBay_MD-Easton-29000InformationLane_v3.0_TEMPLATE.docx",
       "ORA_MasterLease_ShallowBay_MD-Salisbury-2203-2207Northwood_v3.0_TEMPLATE.docx",
       "ORA_MasterLease_ShallowBay_MO-Raytown-9620StateRoute350_v3.0_TEMPLATE.docx"]
# Phase-1 power-rights masters (2026-10-15): the first real paper carrying FP1-FP8 wording.
V28 = "ORA_MasterLease_ShallowBayIndustrial_v2.8_TEMPLATE.docx"
V31 = "ORA_MasterLease_ShallowBay_MultiTenantMG_v3.1_TEMPLATE.docx"
EXHIBIT_B = "ORA_MasterLease_ExhibitB_RulesAndRegulations_v1.3_TEMPLATE.docx"
# Measured on the UNMODIFIED v2.9 scanner, 2026-10-15 (evidence/baseline_unmodified.json).
EXHIBIT_B_BASELINE = sorted(["A6", "B7", "A5a", "A5b", "C8", "F11", "B5", "B6a", "B6b", "B6c",
                             "C1", "C2", "C3", "C5", "F10", "C4", "C6", "C7", "F18"])


def need(name):
    """Resolve a committed corpus fixture. A missing fixture is a FAILURE, never a
    skip: a skip would hide exactly the vacuous-pass gap this suite exists to close."""
    for d in CORPUS_DIRS:
        p = d / name
        if p.exists():
            return p
    raise AssertionError(f"corpus fixture not found in {[str(d) for d in CORPUS_DIRS]}: {name}")


def scan_ids(path, form=None, power=False):
    plan = q.plan_scan(str(path), form, power)
    r = q.scan(str(path), plan["checks"], want_footer=True)
    return sorted(f["id"] for f in r["failures"]), r, plan


def ctx_from(path, edit=None, name=None):
    body, meta = extract(str(path), want_footer=True)
    if edit:
        body = edit(body)
    name = name or os.path.basename(str(path))
    return {"t": norm(body), "raw": body, "meta": meta, "name": name,
            "allow_tokens": False, "is_template": "_TEMPLATE" in name.upper()}


def run(ctx, checks):
    return sorted(f["id"] for f in run_checks(ctx, checks))


class RegistryIdentity(unittest.TestCase):
    def test_v27_registry_is_exactly_CHECKS(self):
        checks, na = q.build_registry("v2.7")
        self.assertIs(checks, q.CHECKS)
        self.assertEqual(len(q.CHECKS), 60)
        self.assertEqual(na, [])

    def test_v30_registry_shape(self):
        checks, na = q.build_registry("v3.0")
        ids = [c[0] for c in checks]
        self.assertEqual([x["id"] for x in na], ["F16"])
        self.assertNotIn("F16", ids)
        for cid in list(q.V30_REANCHOR) + ["F0", "F22", "F23", "F24", "F25", "F26"]:
            self.assertIn(cid, ids)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len(ids), 65)
        self.assertFalse(any(i.startswith("FP") for i in ids))


class Benchmarks(unittest.TestCase):
    def test_v27_docs_zero_failures_auto_and_declared(self):
        for n in V27:
            p = need(n)
            for form in (None, "v2.7"):
                with self.subTest(doc=n, form=form):
                    ids, r, plan = scan_ids(p, form)
                    self.assertEqual(ids, [])
                    self.assertEqual(plan["form"]["resolved"], "v2.7")
                    self.assertEqual(r["checks_run"], 60 if form is None else 61)

    def test_v30_docs_zero_failures_auto_and_declared(self):
        for n in V30:
            p = need(n)
            for form in (None, "v3.0"):
                with self.subTest(doc=n, form=form):
                    ids, r, plan = scan_ids(p, form)
                    self.assertEqual(ids, [])
                    self.assertEqual(plan["form"]["resolved"], "v3.0")
                    self.assertEqual([x["id"] for x in plan["na"]], ["F16"])

    def test_phase1_power_rights_masters_pass_enforced(self):
        """v2.10.1: the real v2.8 / v3.1 masters carry the APPROVED wording, incl. the
        hyphenated 'electric-vehicle', 'be an eviction or entitle Tenant to any abatement'
        and 'energy generation, storage' forms the FP1/FP4/FP7 anchors were widened for."""
        for n, fam, run_n in ((V28, "v2.7", 68), (V31, "v3.0", 73)):
            with self.subTest(doc=n):
                ids, r, plan = scan_ids(need(n))
                self.assertEqual(ids, [])
                self.assertEqual(plan["form"]["resolved"], fam)
                self.assertEqual(plan["form"]["power_rights"], "ENFORCED")
                self.assertEqual(r["checks_run"], run_n)
                raw = ctx_from(need(n))["raw"]
                for s in ("electric-vehicle", "energy generation, storage",
                          "not be an eviction or entitle Tenant to any abatement"):
                    self.assertIn(s, raw)

    def test_exhibit_b_unchanged_from_baseline(self):
        ids, r, plan = scan_ids(need(EXHIBIT_B))
        self.assertEqual(ids, EXHIBIT_B_BASELINE)
        self.assertEqual(r["checks_run"], 60)

    def test_cross_mode_fails_loudly(self):
        for n in V27:
            with self.subTest(doc=n, form="v3.0"):
                ids, _r, _p = scan_ids(need(n), "v3.0")
                self.assertIn("F0", ids)
        for n in V30:
            with self.subTest(doc=n, form="v2.7"):
                ids, _r, _p = scan_ids(need(n), "v2.7")
                self.assertIn("F0", ids)

    def test_cli_exit_codes(self):
        lq = str(SCRIPTS / "lease_qc.py")
        cases = [(V27[0], None, 0), (V30[0], None, 0), (V30[0], "v3.0", 0),
                 (V27[0], "v3.0", 1), (V30[0], "v2.7", 1)]
        for n, form, want in cases:
            with self.subTest(doc=n, form=form):
                cmd = [sys.executable, "-I", "-B", lq, str(need(n))] + (["--form", form] if form else [])
                res = subprocess.run(cmd, capture_output=True, text=True)
                self.assertEqual(res.returncode, want, res.stdout[-800:] + res.stderr)
                if want == 1:
                    self.assertIn("FORM MISMATCH", res.stdout)

    def test_footer_structure_disagreement_in_auto_mode(self):
        # A v3.0 footer stamped onto v2.7 structure: auto-mode F0.
        det = q.detect_form(ctx_from(need(V27[0]))["raw"], "ORA Master Lease v3.0 — October 2026")
        fam, detail, inc = q.resolve_form(det)
        self.assertTrue(inc)
        self.assertIsNotNone(detail)


class V30ReanchorsSeeTheProvision(unittest.TestCase):
    """Each re-anchored / new v3.0 check must FIRE when its v3.0 provision is
    broken. `v27_blind` = the unmodified v2.7 check provably did NOT fire on the
    same mutation (the vacuous pass this mode exists to close)."""

    MUTATIONS = [
        # (id, old, new, v27_blind)
        ("A7", "exceed those for the Base Year stated in the Basic Lease Information", "are payable", True),
        ("B2", "Except to the extent required by law, Landlord has no duty to relet", "Landlord has no duty to relet", True),
        ("B3", "less the net proceeds of any reletting or, absent reletting, the fair rental value of the Premises for that period", "", True),
        ("B8", "within thirty (30) days after each invoice, for the cost of that service, measured by sub-meter if the Premises are sub-metered and otherwise by Tenant’s Proportionate Share of the Building’s charges or another equitable allocation Landlord reasonably determines", "for that service", True),
        ("F13", ", excluding costs billed directly to any tenant", "", True),
        ("F14", "all risks of physical loss (special form)", "fire and extended coverage", True),
        ("F15", "and no member, manager, officer, employee or agent of Landlord has any personal liability under this Lease", "", True),
        ("F17", "Tenant shall keep a preventive-maintenance contract with a licensed HVAC contractor providing service at least twice a year and give Landlord copies of the contract and service reports on request.", "", True),
        ("F19", "or to Tenant also by e-mail or at the Premises", "or, if to Tenant, at the Premises.", False),
        ("F20", "; the Rent Schedule controls in the event of any conflict", "", True),
        ("F23", "So long as no Event of Default exists,", "Landlord may relocate Tenant to other space in the Project on thirty (30) days' notice. So long as no Event of Default exists,", False),
        ("F24", "Tenant shall deliver the Security Deposit", "Tenant shall deliver annual financial statements to Landlord. Tenant shall deliver the Security Deposit", True),
    ]

    def test_mutations(self):
        p = need(V30[0])
        v30, _ = q.build_registry("v3.0")
        v30 = [c for c in v30 if c[0] != "F0"]
        for cid, old, new, blind in self.MUTATIONS:
            with self.subTest(check=cid):
                base = ctx_from(p)
                self.assertIn(old, base["raw"], f"mutation anchor drifted for {cid}")
                self.assertNotIn(cid, run(base, v30))
                mut = ctx_from(p, lambda b, o=old, n=new: b.replace(o, n))
                self.assertIn(cid, run(mut, v30))
                if blind:
                    self.assertNotIn(cid, run(mut, q.CHECKS),
                                     f"{cid}: v2.7 check unexpectedly saw the v3.0 mutation")

    def test_exhibit_b_removed_fires_f25(self):
        p = need(V30[0])
        mut = ctx_from(p, lambda b: b[:b.index("EXHIBIT B\nRULES")])
        self.assertIn("F25", run(mut, q.V30_EXTRA))

    def test_specialized_equipment_half_deleted_fires_f22_and_f26(self):
        p = need(V30[0])

        def drop_module(b):
            s = b.index("SPECIALIZED EQUIPMENT.")
            e = b.index("ASSIGNMENT; SUBLETTING")
            return b[:s] + b[e:]
        ids = run(ctx_from(p, drop_module), q.V30_EXTRA)
        self.assertIn("F22", ids)
        self.assertIn("F26", ids)

    def test_specialized_equipment_clean_deletion_passes(self):
        p = need(V30[0])

        def drop_cleanly(b):
            s = b.index("SPECIALIZED EQUIPMENT.")
            e = b.index("ASSIGNMENT; SUBLETTING")
            b = b[:s] + b[e:]
            b = b.replace("Except as provided in the Specialized Equipment section (if included), Tenant", "Tenant")
            return b.replace("Except for any Approved Consumables used in accordance with the Specialized Equipment section, Tenant", "Tenant")
        ids = run(ctx_from(p, drop_cleanly), q.V30_EXTRA)
        self.assertNotIn("F22", ids)
        self.assertNotIn("F26", ids)

    def test_module_instruction_left_in_execution_copy_fires_f26(self):
        p = need(V30[0])
        ctx = ctx_from(p, name="Lease_Executed_Copy.docx")       # not a _TEMPLATE
        self.assertIn("F26", run(ctx, q.V30_EXTRA))


# ---- power-rights standard ------------------------------------------------

POWER_TEXT = [
    "ROOF, EXTERIOR AND ENERGY RIGHTS.  Landlord reserves the exclusive right to use the roof, the exterior walls and the parking areas of the Project, and to lease or license them to others, for solar photovoltaic systems, energy storage (battery) systems, electric vehicle charging equipment, and telecommunications and antenna equipment (together, “Energy Equipment”).  All rent, revenue, credits and incentives from Energy Equipment belong solely to Landlord.  Landlord’s exercise of these rights is without abatement of Rent.",
    "Landlord may grant utility and interconnection easements over the Project.  Landlord may schedule planned electrical shutdowns of the Building’s service on at least twenty-four (24) hours’ notice to Tenant.",
    "Tenant shall not apply to any utility for new or upgraded electrical service or for interconnection without Landlord’s prior written consent.  Any added electrical capacity serving the Premises is part of the Project.  Notwithstanding the Alterations and Liens section, Tenant need not remove any added electrical capacity when this Lease ends.",
    "Operating Costs exclude the costs of Energy Equipment and are not reduced by any revenue or income from it.  Roof repair and replacement costs remain included in Operating Costs and are not excluded merely because Energy Equipment is located on the roof.",
    "Within ten (10) days after Landlord’s request, Tenant shall sign any authorization Landlord requires to obtain the utility usage data for the Premises.",
    "Within ten (10) days after request, Tenant shall deliver an estoppel certificate or acknowledgment to any lessee or licensee of Energy Equipment and to its financing parties.",
    "Landlord may install and operate electric vehicle charging stations in the Project.  Landlord may designate charging spaces, which are excluded from Tenant’s parking allocation.  Tenant shall keep reasonable access to the Premises for its operations.",
]
FP8_TEXT = ("TENANT BACKUP POWER AND ENERGY STORAGE.  [OPTIONAL MODULE — INCLUDE ONLY IF TENANT WILL INSTALL A "
            "GENERATOR OR BATTERY SYSTEM; COUNSEL TO REVIEW BEFORE USE.]  Any battery system shall be listed to "
            "UL 9540 and tested to UL 9540A and installed in accordance with NFPA 855, and any generator shall "
            "comply with NFPA 37 and NFPA 110.  All equipment shall connect through a transfer switch that "
            "prevents any back-feed to the utility or the Building.")


def build_docx(src, dst, version="v3.1", paras=(), drop=None, relocation=False):
    """Synthetic next-build form: the v3.0 master with its footer tag set to
    `version` and `paras` inserted before RULES AND REGULATIONS."""
    from docx import Document
    from docx.oxml.ns import qn
    from docx.text.paragraph import Paragraph
    d = Document(str(src))
    anchor = next(p for p in d.paragraphs if p.text.startswith("RULES AND REGULATIONS."))
    texts = list(paras)
    if relocation:
        texts.append("RELOCATION.  Landlord may relocate Tenant to other space in the Project on thirty (30) days’ notice.")
    for txt in texts:
        if drop and drop in txt:
            txt = txt.replace(drop, "")
        el = copy.deepcopy(anchor._p)
        anchor._p.addprevious(el)
        np = Paragraph(el, anchor._parent)
        for i, r in enumerate(np.runs):
            r.text = txt if i == 0 else ""
    for rel in d.part.rels.values():
        if rel.reltype.endswith("/footer"):
            for t_el in rel.target_part.element.iter(qn("w:t")):
                if t_el.text and "v3.0" in t_el.text:
                    t_el.text = t_el.text.replace("v3.0", version)
    d.save(str(dst))
    return dst


class PowerRights(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src = need(V30[0])
        cls.td = tempfile.TemporaryDirectory()
        cls.dir = pathlib.Path(cls.td.name)

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()

    def mk(self, name, **kw):
        return build_docx(self.src, self.dir / f"ORA_MasterLease_{name}_TEMPLATE.docx", **kw)

    def test_power_active_thresholds(self):
        self.assertFalse(q.power_active((2, 7)))
        self.assertTrue(q.power_active((2, 8)))
        self.assertFalse(q.power_active((3, 0)))
        self.assertTrue(q.power_active((3, 1)))
        self.assertTrue(q.power_active((3, 2)))
        self.assertFalse(q.power_active(None))

    def test_pending_on_current_forms(self):
        for n in V27[:1] + V30[:1]:
            with self.subTest(doc=n):
                p = need(n)
                ids, r, plan = scan_ids(p)
                self.assertFalse(any(i.startswith("FP") for i in ids))
                self.assertEqual(plan["form"]["power_rights"], "PENDING")
                pend = q.pending_power(plan, str(p))
                self.assertEqual([x["id"] for x in pend], [c[0] for c in q.POWER_CHECKS])

    def test_v31_without_provisions_fails_fp1_to_fp7(self):
        ids, _r, plan = scan_ids(self.mk("bare-v31", version="v3.1"))
        self.assertEqual(plan["form"]["power_rights"], "ENFORCED")
        for cid in ("FP1", "FP2", "FP3", "FP4", "FP5", "FP6", "FP7"):
            self.assertIn(cid, ids)
        self.assertNotIn("FP8", ids)          # optional module absent = nothing to verify

    def test_v31_with_all_provisions_passes(self):
        ids, _r, _p = scan_ids(self.mk("full-v31", version="v3.1", paras=POWER_TEXT + [FP8_TEXT]))
        self.assertEqual(ids, [], ids)

    def test_force_flag_enforces_on_v30(self):
        ids, _r, plan = scan_ids(self.src, power=True)
        self.assertIn("FP1", ids)
        self.assertTrue(plan["form"]["power_rights"].startswith("ENFORCED"))

    def test_each_provision_is_required(self):
        drops = {"FP1": "without abatement of Rent", "FP2": "on at least twenty-four (24) hours’ notice to Tenant",
                 "FP3": "without Landlord’s prior written consent", "FP4": "and are not reduced by any revenue or income from it",
                 "FP5": "Within ten (10) days after Landlord’s request, ", "FP6": "and to its financing parties",
                 "FP7": ", which are excluded from Tenant’s parking allocation"}
        for cid, drop in drops.items():
            with self.subTest(check=cid):
                ids, _r, _p = scan_ids(self.mk(f"drop-{cid}", paras=POWER_TEXT + [FP8_TEXT], drop=drop))
                self.assertIn(cid, ids)

    def test_fp8_module_incomplete(self):
        for drop in ("NFPA 110", "UL 9540A", "COUNSEL TO REVIEW BEFORE USE", "transfer switch", "INCLUDE ONLY IF"):
            with self.subTest(drop=drop):
                ids, _r, _p = scan_ids(self.mk(f"fp8-{drop[:6]}", paras=POWER_TEXT + [FP8_TEXT], drop=drop))
                self.assertIn("FP8", ids)

    def test_v31_relocation_right_fails_fp1_and_f23(self):
        ids, _r, _p = scan_ids(self.mk("reloc-v31", paras=POWER_TEXT, relocation=True))
        self.assertIn("FP1", ids)
        self.assertIn("F23", ids)

    def test_v28_nnn_line_enforces_in_v27_mode(self):
        p = need(V27[0])
        from docx import Document
        from docx.oxml.ns import qn
        d = Document(str(p))
        for rel in d.part.rels.values():
            if rel.reltype.endswith("/footer"):
                for t_el in rel.target_part.element.iter(qn("w:t")):
                    if t_el.text and "v2.7" in t_el.text:
                        t_el.text = t_el.text.replace("v2.7", "v2.8")
        out = self.dir / "ORA_MasterLease_v28probe_TEMPLATE.docx"
        d.save(str(out))
        ids, _r, plan = scan_ids(out)
        self.assertEqual(plan["form"]["resolved"], "v2.7")
        self.assertIn("FP1", ids)
        self.assertNotIn("F0", ids)


class FP7SingleTenant(unittest.TestCase):
    """v2.11: FP7 on single-tenant paper. The OH-SingleTenant-NNN conversion makes parking
    exclusive and deletes the "Tenant's Allocation" definition, so the P7 allocation
    fragment is dropped by rebase (Gabriel, 2026-10-15). FP7 then requires only the
    designation right + reasonable access -- and only when BOTH single-tenant signals hold."""

    MT_PARKING = ("Tenant shall be entitled to a non-exclusive right to use the unreserved parking spaces in "
                  "the Project adjacent to the Building in order to satisfy the general operational requirements "
                  "of the Demised Premises in an amount not to exceed the Tenant’s Allocation (hereinafter "
                  "defined).  Notwithstanding the foregoing, Landlord reserves the right to designate specific "
                  "spaces for Tenant’s use or use by any other occupant of the Project and to prohibit "
                  "Tenant’s use of other designated spaces.")
    ST_PARKING = ("Tenant shall have the exclusive right to use the parking areas in the Project for Tenant's "
                  "employees, agents, customers and invitees, subject to the terms of this Lease.")
    ALLOC_DEF = ("  For purposes hereof, “Tenant’s Allocation” shall be equal to a portion of the total "
                 "number of available parking spaces in the Project based upon the ratio of (i) the rentable "
                 "square footage of the Demised Premises compared to (ii) the rentable square footage for the "
                 "entire Project. ")
    FRAG = ", and such spaces shall not count against Tenant’s Allocation while so designated"

    def fp7(self, edit):
        ctx = ctx_from(need(V28), edit)
        return run(ctx, q._with_family([c for c in q.POWER_CHECKS if c[0] == "FP7"], "v2.7"))

    def to_single_tenant(self, b, drop_fragment=True):
        for old, new in ((self.MT_PARKING, self.ST_PARKING), (self.ALLOC_DEF, "")) + (
                ((self.FRAG, ""),) if drop_fragment else ()):
            self.assertEqual(b.count(old), 1, old[:50])
            b = b.replace(old, new)
        return b

    def test_single_tenant_conversion_passes_fp7(self):
        self.assertEqual(self.fp7(self.to_single_tenant), [])

    def test_single_tenant_still_needs_designation_and_access(self):
        drop_desig = lambda b: self.to_single_tenant(b).replace(  # noqa: E731
            "designate spaces for vehicles while charging, ", "")
        self.assertEqual(self.fp7(drop_desig), ["FP7"])
        drop_access = lambda b: self.to_single_tenant(b).replace(  # noqa: E731
            ", provided that Tenant retains reasonable access to parking for its operations", "")
        self.assertEqual(self.fp7(drop_access), ["FP7"])

    def test_multi_tenant_without_the_exclusion_still_fails(self):
        # the allocation fragment dropped on MULTI-tenant paper: no single-tenant branch
        self.assertEqual(self.fp7(lambda b: b.replace(self.FRAG, "")), ["FP7"])
        # exclusive-parking wording alone (allocation still defined) does not switch the branch
        self.assertEqual(self.fp7(lambda b: b.replace(self.MT_PARKING, self.ST_PARKING).replace(self.FRAG, "")),
                         ["FP7"])

    def test_single_tenant_detector(self):
        self.assertFalse(q._single_tenant_exclusive_parking("Tenant has a non-exclusive right to use the parking areas."))
        self.assertTrue(q._single_tenant_exclusive_parking(self.ST_PARKING))
        self.assertFalse(q._single_tenant_exclusive_parking(self.ST_PARKING + " Tenant’s Allocation is 10 spaces."))


if __name__ == "__main__":
    unittest.main()
