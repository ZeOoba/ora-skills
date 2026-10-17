#!/usr/bin/env python3
"""ORA Master Lease jurisdiction rebase engine.

Edits the OH-anchored controlled master DOCX in place (native formatting preserved)
into a state-conformed property template. Every substitution carries an expected match
count; a mismatch aborts and names the anchor — anchor drift in a new master revision
must surface loudly, never silently (2026-08-03 propagation-audit discipline).

Usage:
  python3 rebase.py --master <master.docx> --property MD-EAS [--out DIR]
  python3 rebase.py --master <master.docx> --all [--out DIR]

Anchors keyed to master v2.4.1 (2026-08-03). On assertion failure after a master rev:
diff the masters, update the anchor here or in config/, log it in SKILL.md changelog.

v1.9 (2026-10-15): two form lines, chosen by the master's FOOTER TAG. v2.x (long-form,
ShallowBayIndustrial) -> build_rules / build_rules_home / NNN / single-tenant paths below,
unchanged. v3.x (short-form multi-tenant MG, ShallowBay_MultiTenantMG) -> build_rules_v30()
with its own asserted anchor set; only properties with a "v3_0" config entry are eligible.
Run under `python3 -I`.

v1.10 (2026-10-15): every output also passes format_parity() against its master
(per-character run formatting; fills must not bold, defined terms must not lose bold).
Power-rights masters (v2.8 NNN line, v3.1 MG line): single-tenant P7 allocation
fragment dropped; --all on a v2.8+ v2.x master emits the NNN-line properties only.
"""
import argparse, copy, json, pathlib, re, sys
from docx import Document
from docx.oxml.ns import qn

HERE = pathlib.Path(__file__).resolve().parent
CONFIG = HERE.parent / "config"
ANCHOR_STATE = "Ohio"  # the master's home state; residue check target

SAVINGS_TITLE = "Maximum Lawful Rate."
SAVINGS_BODY = ("  Notwithstanding any other provision of this Lease, the aggregate of all interest, "
    "late fees and other charges in the nature of interest payable by Tenant under this Lease shall "
    "not exceed the maximum rate or amount permitted by applicable law.  If any such charge is held "
    "to exceed the applicable lawful maximum, such charge shall be reduced to the maximum lawful "
    "amount, and any excess actually paid shall be credited against the next installments of rent coming due.")


def replace_in_paragraph(para, old, new):
    """Cross-run splice replace; returns count. Resumes past each replacement so
    appends containing their own anchor cannot loop."""
    count, search_from = 0, 0
    while True:
        runs = para.runs
        full = "".join(r.text for r in runs)
        i = full.find(old, search_from)
        if i < 0:
            return count
        search_from = i + len(new)
        j = i + len(old)
        pos, first = 0, True
        for r in runs:
            s, e = pos, pos + len(r.text)
            if e <= i or s >= j:
                pos = e
                continue
            ls, le = max(s, i) - s, min(e, j) - s
            if first:
                r.text = r.text[:ls] + new + r.text[le:]
                first = False
            else:
                r.text = r.text[:ls] + r.text[le:]
            pos = e
        count += 1


def apply(doc, rules):
    for old, new, expect in rules:
        n = sum(replace_in_paragraph(p, old, new) for p in doc.paragraphs)
        if n != expect:
            sys.exit(f"ANCHOR DRIFT: {old[:90]!r} expected {expect} match(es), found {n}. "
                     "Diff the new master against the prior revision and update this anchor.")


def insert_savings_clause(doc):
    """Clone the Counterparts paragraph (keeps list numbering + underlined-title style)."""
    if any(p.text.startswith(SAVINGS_TITLE) for p in doc.paragraphs):
        return  # idempotent
    target = next((p for p in doc.paragraphs if p.text.startswith("Counterparts; Electronic Signatures.")), None)
    if target is None:
        sys.exit("ANCHOR DRIFT: Counterparts paragraph not found — cannot place Maximum Lawful Rate clause.")
    newp = copy.deepcopy(target._p)
    target._p.addnext(newp)
    from docx.text.paragraph import Paragraph
    np = Paragraph(newp, target._parent)
    body_done = False
    for idx, r in enumerate(np.runs):
        if idx == 0:
            r.text = SAVINGS_TITLE
        elif not body_done and not r.underline:
            r.text = SAVINGS_BODY
            body_done = True
        else:
            r.text = ""
    if not body_done:
        sys.exit("Savings-clause insertion: no non-underlined body run found in cloned paragraph.")


def article(state_name):
    """'an' before vowel-sound state names (Indiana, Ohio, Iowa...); 'a Utah' — the
    only U-state is pronounced with a consonant sound."""
    return "an" if state_name[:1].upper() in "AEIO" else "a"


# --- NNN structure override -------------------------------------------------
# The master's default expense structure is modified gross with a calendar base
# year (ratified standing position #1, 2026-08-03). A property opts out of that
# default only via an explicit "lease_structure": "NNN" field in its
# config/properties.json entry, sourced from Gabriel's direction and the
# property's own established leasing practice — never applied by inference from
# an executed lease alone. 9050 Red Branch Road (MD-COL) is the first such
# override (2026-08-04): Gabriel confirmed the building runs NNN leases
# building-wide, consistent with the LINERX/Eddie Woo Park executed lease and
# ~15 years of suite leases on Muirkirk Properties' own NNN form. This does not
# alter any of the other five ratified positions (co-tenancy, 1.0x deposit, 10%
# late fee / 18% default rate + savings clause, flat Hazardous Materials ban, no
# extension option) — only the expense-recovery mechanism.

NNN_INSURANCE_DEF = (
    "shall mean all premiums and other costs paid or incurred by Landlord for the property, "
    "liability, rent-loss, and other insurance policies Landlord elects to carry on or in connection "
    "with the Project, the Building, or the Premises, as further described in the section of this "
    "Lease entitled “INSURANCE.”"
)


def nnn_text_rules():
    return [
        # v1.10 re-key (format parity): the old anchors started in / spanned bold runs, so
        # the BLI fill "Not applicable — full NNN" came out bold (anchor began in the bold
        # "Base Year:" label) and the heading's plain period was bolded. The BLI line is now
        # keyed on the plain " [BASE YEAR]" run AFTER the body sentence below has consumed
        # the only other "[BASE YEAR]" (count still asserted), and the heading anchor stops
        # before its period.
        ("\tOPERATING COSTS AND TAXES",
         "\tOPERATING COSTS, TAXES AND INSURANCE", 1),
        ("Tenant shall pay to Landlord, Tenant's Proportionate Share (hereinafter defined) of the "
         "increase over base year of all Operating Costs (hereinafter defined) and/or Taxes "
         "(hereinafter defined). Base year shall be defined as the calendar year in which the "
         "Commencement Date occurs, being the [BASE YEAR] calendar year.  ",
         "Tenant shall pay to Landlord, as additional rent, Tenant's Proportionate Share (hereinafter "
         "defined) of all Operating Costs (hereinafter defined), Taxes (hereinafter defined), and "
         "Insurance (hereinafter defined), without regard to any base year -- i.e., on a full, triple "
         "net (NNN) basis from the Commencement Date, consistent with Landlord's established leasing "
         "practice at the Building.  ",
         1),
        (" [BASE YEAR]", " Not applicable — full NNN", 1),  # v2.5 BLI line ("Base Year:" label stays bold)
        ("Landlord may from time to time deliver to Tenant a written estimate of Tenant’s "
         "Proportionate Share of the increase in Operating Costs and Taxes for the then-current "
         "calendar year",
         "Landlord may from time to time deliver to Tenant a written estimate of Tenant’s "
         "Proportionate Share of Operating Costs, Taxes, and Insurance for the then-current calendar "
         "year",
         1),
        ("Landlord shall deliver to Tenant a statement setting forth the actual Operating Costs and "
         "Taxes for that year, Tenant’s Proportionate Share of the increase over the base year, "
         "and the estimated amounts paid by Tenant.",
         "Landlord shall deliver to Tenant a statement setting forth the actual Operating Costs, "
         "Taxes, and Insurance for that year, Tenant’s Proportionate Share thereof, and the "
         "estimated amounts paid by Tenant.",
         1),
    ]


def convert_to_nnn(doc):
    """Rewrite the modified-gross OPERATING COSTS AND TAXES article into a full NNN
    (Operating Costs + Taxes + Insurance, no base year) structure. Fails loudly on
    anchor drift, same discipline as apply()."""
    apply(doc, nnn_text_rules())

    paras = doc.paragraphs
    tax_idx = next((i for i, p in enumerate(paras) if p.text.startswith("“Taxes” ")
                     or p.text.startswith("\"Taxes\" ")), None)
    opcost_idx = next((i for i, p in enumerate(paras) if p.text.startswith("“Operating Costs” ")
                        or p.text.startswith("\"Operating Costs\" ")), None)
    if tax_idx is None or opcost_idx is None:
        sys.exit("ANCHOR DRIFT: could not locate the Operating Costs / Taxes definition paragraphs "
                  "to insert the Insurance definition — diff the master and update convert_to_nnn().")
    ins_idx = tax_idx + 2
    if ins_idx >= len(paras) or paras[ins_idx].text.strip() != "":
        sys.exit(f"ANCHOR DRIFT: expected a blank spacer paragraph at index {ins_idx} (two after the "
                  "Taxes definition) to hold the new Insurance definition; found non-blank or "
                  "out-of-range content. Diff the master and update convert_to_nnn().")

    target = paras[ins_idx]
    for r in list(target.runs):
        r._element.getparent().remove(r._element)
    r0 = target.add_run("“Insurance” ")
    r0.bold = True
    r1 = target.add_run(NNN_INSURANCE_DEF)
    r1.bold = False

    model_pPr = paras[opcost_idx]._p.find(qn("w:pPr"))
    target_pPr = target._p.find(qn("w:pPr"))
    if model_pPr is not None and target_pPr is not None:
        new_pPr = copy.deepcopy(model_pPr)
        target_rPr = target_pPr.find(qn("w:rPr"))
        if target_rPr is not None:
            new_rPr = new_pPr.find(qn("w:rPr"))
            if new_rPr is not None:
                new_pPr.replace(new_rPr, copy.deepcopy(target_rPr))
        target._p.replace(target_pPr, new_pPr)




# --- Single-tenant variant override -----------------------------------------
# Encodes the OH-SingleTenant-NNN template family's deltas vs. the multi-tenant
# master, recovered 2026-08-04 by paragraph diff of the v2.4.1 variant against
# the v2.4.1 base and verified on the v2.6 rebuild (25/25 structural checks,
# lease_qc 0/51). A config entry opts in via "variant": "single-tenant" (always
# paired with "lease_structure": "NNN" for this family). The variant stays
# generic-tokenized: entity/premises/PM fills are SKIPPED and are filled at
# drafting time. Judgment calls ratified 2026-08-04: the master's broader
# capital-amortization clause supersedes the old roof/structure-specific
# sentence; the gross-up sentence and the "Tenant's Allocation" definition are
# removed (meaningless at a 100% share with exclusive parking); relocation
# clause (h) is retained as an inert option.

ST_ALLOC_DEF = (
    "  For purposes hereof, \u201cTenant\u2019s Allocation\u201d shall be equal to a portion of the total "
    "number of available parking spaces in the Project based upon the ratio of (i) the rentable "
    "square footage of the Demised Premises compared to (ii) the rentable square footage for the "
    "entire Project. "
)


def single_tenant_rules():
    return [
        # v1.10 re-keys (format parity, see format_parity()): no single-tenant anchor may
        # start in a bold BLI label ("Demised Premises:", "Tenant's Proportionate Share:")
        # or span a bold defined term ("Demised Premises", "Tenant's Proportionate
        # Share") -- the old anchors bolded the fills and un-bolded the defined term in the
        # production OH-ST-NNN template. Same text out, counts still asserted.
        ("approximately [PREMISES RSF] square feet of rentable area in the building situated at "
         "[PREMISES ADDRESS] (such rentable area being",
         "the entire building situated at [PREMISES ADDRESS], containing approximately [BUILDING RSF] "
         "square feet of rentable area, together with all adjacent paved, parking and yard areas "
         "serving it (such building and areas being", 1),
        (" \u2014 approximately [PREMISES RSF] rentable square feet",
         " \u2014 the entire building, approximately [BUILDING RSF] rentable square feet", 1),
        (" If the Building is not fully occupied, for purposes of calculating Tenant's Proportionate "
         "Share, Landlord may \"gross up\" Operating Costs to what they would have been if the Building "
         "or Project had been fully occupied. ",
         " ", 1),
        ("shall mean the proportion that the rentable square footage of "
         "the Demised Premises bears to the total rentable square footage of the Building, being "
         "[BUILDING RSF] square feet (Franklin County Auditor Parcel No. [PARCEL NO]). Tenant's "
         "Proportionate Share is estimated to be [PROPORTIONATE SHARE]%.",
         "shall mean one hundred percent (100%), Tenant leasing the "
         "entire Building, containing [BUILDING RSF] square feet (Franklin County Auditor Parcel No. "
         "[PARCEL NO]).", 1),
        (" [PROPORTIONATE SHARE]%",            # BLI line; the body token is consumed just above
         " 100% (entire Building)", 1),
        ("Tenant shall be entitled to a non-exclusive right to use the unreserved parking spaces in "
         "the Project adjacent to the Building in order to satisfy the general operational requirements "
         "of the Demised Premises in an amount not to exceed the Tenant\u2019s Allocation (hereinafter "
         "defined).  Notwithstanding the foregoing, Landlord reserves the right to designate specific "
         "spaces for Tenant\u2019s use or use by any other occupant of the Project and to prohibit "
         "Tenant\u2019s use of other designated spaces.",
         "Tenant shall have the exclusive right to use the parking areas in the Project for Tenant's "
         "employees, agents, customers and invitees, subject to the terms of this Lease.", 1),
        (ST_ALLOC_DEF, "", 1),
        ("prevented by Tenant\u2019s performance of its maintenance obligations.",
         "prevented by Tenant\u2019s performance of its maintenance obligations.  In addition, Tenant, at "
         "Tenant's sole cost and expense, shall provide all janitorial service, snow and ice removal, "
         "lawn mowing, landscaping, exterior sweeping and pest control for the Demised Premises and "
         "the Project, shall keep all parking and yard areas clean and free of debris and free from "
         "accumulation of snow and ice, and shall maintain the Demised Premises in a first-class and "
         "fully operative condition.", 1),
    ]


# P7 (power-rights EV charging, v2.8+): "Landlord may install electric-vehicle charging
# equipment in the parking areas, designate spaces for vehicles while charging, and
# charge users for charging, and such spaces shall not count against Tenant's
# Allocation while so designated, provided that Tenant retains reasonable access to
# parking for its operations."  The single-tenant conversion deletes the "Tenant's
# Allocation" definition and makes parking exclusive, which would leave an undefined
# term. Gabriel's decision (2026-10-15, "Drop allocation sentence"): keep Landlord's
# EV-install / designate / charge right and the reasonable-access proviso, and drop
# only the allocation fragment.
ST_P7_ALLOCATION_FRAGMENT = (", and such spaces shall not count against Tenant\u2019s Allocation "
                             "while so designated")


def power_rights_master(doc):
    """True for a master on or after the power-rights builds (v2.8 NNN line, v3.1 MG line)."""
    f = master_form(doc)
    return bool(f) and ((f[0] == 2 and f[1] >= 8) or (f[0] == 3 and f[1] >= 1) or f[0] > 3)


def single_tenant_power_rules():
    return [(ST_P7_ALLOCATION_FRAGMENT, "", 1)]


def convert_to_single_tenant(doc):
    """Rewrite the multi-tenant master into the single-tenant variant (entire-building
    demise, 100% share, exclusive parking, tenant site services). Fails loudly on
    anchor drift, same discipline as apply(). On a power-rights master (v2.8+) the
    P7 parking-allocation fragment is dropped too (asserted: exactly one)."""
    apply(doc, single_tenant_rules())
    if power_rights_master(doc):
        apply(doc, single_tenant_power_rules())

def build_rules(P, L):
    st = L["state"]
    es = P.get("entity_state")
    if not es:
        sys.exit(f"{P['entity']}: missing 'entity_state' in config/properties.json. The LLC's "
                 "formation state must be SOURCED (Articles of Organization, ratified LLC roster, "
                 "or an executed lease's recital) — never assumed from the property's location. "
                 "Fail-closed by design (2026-08-03 eval finding).")
    rules = [
        ("[LANDLORD ENTITY]", P["entity"], 4),  # v2.5: +1 (BLI page)
        ("a [STATE] limited liability company", f"{article(es)} {es} limited liability company", 3),  # v2.5: +1 (BLI page)
        ("the building situated at [PREMISES ADDRESS] (such rentable area",
         f"the building situated at {P['premises']} (such rentable area", 1),
        ("the building known as [BUILDING ADDRESS], containing [BUILDING RSF] square feet of rentable area",
         P["building_def"], 1),
        (f"national banks in the State of {ANCHOR_STATE} are authorized to close",
         f"national banks in the State of {st} are authorized to close", 1),
        ("bears to the total rentable square footage of the Building, being [BUILDING RSF] square feet ",
         P["share_denominator"], 1),
        ("(Franklin County Auditor Parcel No. [PARCEL NO])", L["parcel_reference"], 1),
        (f"in accordance with the laws of the State of {ANCHOR_STATE}.",
         f"in accordance with the laws of the State of {st}.", 2),  # USE + governing law
        (f"is qualified to do business in the State of {ANCHOR_STATE},",
         f"is qualified to do business in the State of {st},", 1),
        (f"the federal ESIGN Act and the {ANCHOR_STATE} Uniform Electronic Transactions Act.", L["ueta"], 1),
        ("Tenant, as a month-to-month tenant, shall continue to be subject to all of the conditions and covenants of this Lease.",
         "Tenant, as a month-to-month tenant, shall continue to be subject to all of the conditions and covenants of this Lease.  "
         f"The foregoing is in addition to, and not in limitation of, any rights and remedies of Landlord under {L['holdover_statute']}.", 1),
        ("proceed to recover possession under and by virtue of the provisions of the laws or by such other proceedings, including re-entry and possession, as may be applicable.",
         f"proceed to recover possession under and by virtue of the laws of the State of {st}, including {L['possession_statutes']}, "
         "or by such other proceedings, including re-entry and possession, as may be applicable.", 1),
        ("and in the regulations adopted and publications promulgated pursuant to said laws or any future laws or regulations",
         f"and in the regulations adopted and publications promulgated pursuant to said laws, any analogous laws of the State of {st} "
         f"(including {L['env_overlay']}), or any future laws or regulations", 1),
        ("COPY TO:[PROPERTY MANAGER]", P["pm_block"][0], 1),
        ("[MANAGER STREET ADDRESS]", P["pm_block"][1], 1),  # v2.5: master pre-tokenized
        ("[MANAGER CITY, STATE ZIP]", P["pm_block"][2], 1),  # v2.5: master pre-tokenized
        ("ATTN: [MANAGER CONTACT]", P["pm_block"][3], 1),
    ]
    # v2.5 Basic Lease Information page fills
    rules.append((" [PREMISES ADDRESS] — approximately", f" {P['premises']} — approximately", 1))
    m_bd = re.match(r"the building known as (.+), containing (.+) square feet of rentable area", P["building_def"])
    if m_bd:
        rules.append(("[BUILDING ADDRESS] — [BUILDING RSF] rentable square feet (Parcel No. [PARCEL NO])",
                      f"{m_bd.group(1)} — {m_bd.group(2)} rentable square feet {L['parcel_reference'].strip()}", 1))
    if P.get("project_def"):
        rules.append(("the Building together with the land on which it is situated and all parking areas, drives, walkways and other common areas serving it",
                      P["project_def"], 1))
    if P.get("payment_direction"):
        rules.append(("to [PROPERTY MANAGER], at [MANAGER ADDRESS] through the tenant online portal, payable to Landlord,",
                      P["payment_direction"], 1))
    if L.get("extra_no_recording"):
        rules.append(("Any such recording shall be void and shall constitute an Event of Default.",
                      "Any such recording shall be void and shall constitute an Event of Default." + L["extra_no_recording"], 1))
    return rules



def build_rules_home(P):
    """Home-state (Ohio) property: master text is already Ohio-conformed, so only
    property facts are filled -- no state overlay. Added 2026-10-06 (OH-MOR)."""
    es = P.get("entity_state")
    if not es:
        sys.exit(f"{P['entity']}: missing 'entity_state' (fail-closed).")
    parcel = f"(Franklin County Auditor Parcel No. {P['parcel']})"
    rules = [
        ("[LANDLORD ENTITY]", P["entity"], 4),
        ("a [STATE] limited liability company", f"{article(es)} {es} limited liability company", 3),
        ("the building situated at [PREMISES ADDRESS] (such rentable area",
         f"the building situated at {P['premises']} (such rentable area", 1),
        ("the building known as [BUILDING ADDRESS], containing [BUILDING RSF] square feet of rentable area",
         P["building_def"], 1),
        ("bears to the total rentable square footage of the Building, being [BUILDING RSF] square feet ",
         P["share_denominator"], 1),
        ("(Franklin County Auditor Parcel No. [PARCEL NO])", parcel, 1),
        ("COPY TO:[PROPERTY MANAGER]", P["pm_block"][0], 1),
        ("[MANAGER STREET ADDRESS]", P["pm_block"][1], 1),
        ("[MANAGER CITY, STATE ZIP]", P["pm_block"][2], 1),
        ("ATTN: [MANAGER CONTACT]", P["pm_block"][3], 1),
        (" [PREMISES ADDRESS] — approximately", f" {P['premises']} — approximately", 1),
    ]
    m_bd = re.match(r"the building known as (.+), containing (.+) square feet of rentable area", P["building_def"])
    rules.append(("[BUILDING ADDRESS] — [BUILDING RSF] rentable square feet (Parcel No. [PARCEL NO])",
                  f"{m_bd.group(1)} — {m_bd.group(2)} rentable square feet {parcel}", 1))
    if P.get("payment_direction"):
        rules.append(("to [PROPERTY MANAGER], at [MANAGER ADDRESS] through the tenant online portal, payable to Landlord,",
                      P["payment_direction"], 1))
    return rules


# --- v3.0 short-form multi-tenant MG master (added v1.9, 2026-10-15) ----------
# The v3.0 master (ORA_MasterLease_ShallowBay_MultiTenantMG_v3.0) is a ~6,500-
# word rewrite, not an edit of v2.7, so none of the v2.x anchors above exist in
# it. Its anchors below were recovered by paragraph diff of the v3.0 master
# against the four v3.0 property templates built from it on 2026-10-08
# (OH-MOR, MD-EAS, MD-SBY, MO-RAY); rebasing the master with them reproduces
# each stored template text-for-text (test_rebase.py V30ParityTests). The form
# line is read from the master's FOOTER TAG, never inferred from wording:
# "ORA Master Lease v3.x" -> this path; v2.x -> the long-form path above.

FORM_TAG_RE = re.compile(r"ORA Master Lease v(\d+)\.(\d+)")
V3_OHIO_SIGNATURE_NOTE = ("[OHIO ONLY — IF THE LEASE TERM, INCLUDING ANY RENEWAL OR EXTENSION OPTIONS, "
                          "EXCEEDS THREE (3) YEARS, ADD A NOTARIAL ACKNOWLEDGMENT FOR EACH SIGNER "
                          "(R.C. 5301.01).  DELETE THIS NOTE OTHERWISE.]")


def _footer_paragraphs(doc):
    from docx.text.paragraph import Paragraph
    for rel in doc.part.rels.values():
        if rel.reltype.endswith("/footer"):
            for p_el in rel.target_part.element.iter(qn("w:p")):
                yield Paragraph(p_el, None)


def master_form(doc):
    """(major, minor) from the footer tag, or None. Every footer part that
    carries a tag must agree -- a mixed-vintage footer is itself drift."""
    tags = {(int(m.group(1)), int(m.group(2)))
            for p in _footer_paragraphs(doc) for m in FORM_TAG_RE.finditer(p.text)}
    if len(tags) > 1:
        sys.exit(f"ANCHOR DRIFT: master footers carry mixed form tags {sorted(tags)} -- fix the master first.")
    return next(iter(tags)) if tags else None


def is_v3(doc_or_path):
    doc = doc_or_path if not isinstance(doc_or_path, (str, pathlib.Path)) else Document(str(doc_or_path))
    f = master_form(doc)
    return bool(f and f[0] == 3)


def build_rules_v30(P, L, home):
    """Asserted substitutions for the v3.0 master. `home` = Ohio property (the
    master's own state): property facts only, no state overlay."""
    V3 = P.get("v3_0")
    if V3 is None:
        sys.exit(f"{P.get('label', P.get('entity'))}: no 'v3_0' entry in config/properties.json -- this "
                 "property is not on the v3.0 multi-tenant MG line (NNN and single-tenant forms stay on "
                 "the v2.x master). Fail-closed by design.")
    es = P.get("entity_state")
    if not es:
        sys.exit(f"{P['entity']}: missing 'entity_state' (fail-closed).")
    m_bd = re.match(r"the building known as (.+), containing (.+) square feet of rentable area$", P["building_def"])
    if not m_bd:
        sys.exit(f"{P['label']}: building_def does not read 'the building known as <addr>, containing <rsf> "
                 "square feet of rentable area' -- cannot derive the v3.0 Basic Lease Information line.")
    addr, rsf = m_bd.groups()
    if V3.get("parcel_reference"):
        parcel_ref = V3["parcel_reference"]
    elif home:
        parcel_ref = f"(Franklin County Auditor Parcel No. {P['parcel']})"
    else:
        parcel_ref = L["parcel_reference"]
    proj_rsf = V3.get("project_rsf")
    pm = P["pm_block"]
    if not pm[0].startswith("COPY TO:"):
        sys.exit(f"{P['label']}: pm_block[0] must start with 'COPY TO:'.")
    pm_name = pm[0][len("COPY TO:"):].strip()
    pay = P.get("payment_direction")
    if not pay and pm[1] != "[MANAGER STREET ADDRESS]":
        sys.exit(f"{P['label']}: pm_block is filled but payment_direction is null -- the v3.0 Rent section "
                 "names the payee with the manager's address; set payment_direction (fail-closed).")
    n_pay = 0 if pay else 1          # manager-address tokens left in the Rent section when unpaid-to-PM

    rules = [
        ("[LANDLORD ENTITY]", P["entity"], 5),   # BLI, preamble, notice block, signature, Exhibit B
        ("a [LANDLORD STATE] limited liability company", f"{article(es)} {es} limited liability company", 3),
        ("[PREMISES ADDRESS]", P["premises"], 4),  # BLI, signature page, Exhibit A, Exhibit B
        # Anchors never include a bold label/defined term ("Building / Project:",
        # "Building", "Hazardous Materials"): replace_in_paragraph() puts the new
        # text in the FIRST run it touches, so an anchor that starts in a bold run
        # bolds the fill, and one that spans a bold term un-bolds it (caught by the
        # run-format parity test, 2026-10-15).
        ("[BUILDING ADDRESS] — [BUILDING RSF] rentable square feet [PARCEL REFERENCE]",
         f"{addr} — {rsf} rentable square feet"
         + (f"; Project: {proj_rsf} rentable square feet" if proj_rsf else "") + f" {parcel_ref}", 1),
        ("([PREMISES RSF] / [BUILDING RSF])",
         f"([PREMISES RSF] / {proj_rsf} rentable square feet of the Project)" if proj_rsf
         else f"([PREMISES RSF] / {rsf})", 1),
        ("[BUILDING DEFINITION]", P["building_def"], 1),
    ]
    if P.get("project_def"):
        rules.append(("the Building together with the land on which it is situated and all parking areas, "
                      "drives, walkways and other common areas serving it", P["project_def"], 1))
    if proj_rsf:   # share is of the Project (multi-building): gross-up and water follow the Project
        rules += [("to reflect a fully occupied Building.", "to reflect a fully occupied Project.", 1),
                  ("Proportionate Share of the Building’s charges", "Proportionate Share of the Project’s charges", 1)]
    if pay:
        rules.append(("to [PROPERTY MANAGER], [MANAGER STREET ADDRESS], [MANAGER CITY, STATE ZIP], or through "
                      "its tenant online portal, payable to Landlord,", pay, 1))
    rules += [
        ("(currently [PROPERTY MANAGER])", f"(currently {pm_name})", 1),
        ("COPY TO:  [PROPERTY MANAGER]", f"COPY TO:  {pm_name}", 1),
        ("[MANAGER STREET ADDRESS]", pm[1], 1 + n_pay),
        ("[MANAGER CITY, STATE ZIP]", pm[2], 1 + n_pay),
        ("ATTN: [MANAGER CONTACT]", pm[3], 1),
    ]
    if home:
        return rules
    st = L["state"]
    rules += [
        (f"bank holiday in {ANCHOR_STATE};", f"bank holiday in {st};", 1),
        (f"contractors licensed in the State of {ANCHOR_STATE}", f"contractors licensed in the State of {st}", 1),
        (f"Tenant’s insurers must be licensed in {ANCHOR_STATE}", f"Tenant’s insurers must be licensed in {st}", 1),
        (f"other than any notice required by Chapter 1923 of the {ANCHOR_STATE} Revised Code that cannot be waived.",
         f"other than any notice required by law that cannot be waived, including in {L['possession_statutes']}.", 1),
        ("Landlord may recover possession at any time by lawful process.",
         "Landlord may recover possession at any time by lawful process.  This section is in addition to, and "
         f"not in limitation of, Landlord’s rights under {L['holdover_statute']}.", 1),
        ("the Resource Conservation and Recovery Act (“",
         f"the Resource Conservation and Recovery Act, and {L['env_overlay']} (“", 1),
        (f"qualified to do business in {ANCHOR_STATE},", f"qualified to do business in {st},", 1),
        (f"governed by the laws of the State of {ANCHOR_STATE}.", f"governed by the laws of the State of {st}.", 1),
    ]
    if L.get("extra_no_recording"):
        rules.append(("any recording is void and an Event of Default.",
                      "any recording is void and an Event of Default." + L["extra_no_recording"], 1))
    return rules


def apply_signature_note_v30(doc, L):
    """The master's Ohio-only notarial note becomes the state's own note, or is
    deleted when the overlay says the state has none (v3_signature_note null).
    The key is REQUIRED for a non-home state -- fail-closed if absent."""
    if "v3_signature_note" not in L:
        sys.exit(f"{L.get('state')}: state_overlays.json has no 'v3_signature_note' (string, or null to "
                 "delete the Ohio-only note) -- required for v3.0 rebases (fail-closed).")
    hits = [p for p in doc.paragraphs if p.text == V3_OHIO_SIGNATURE_NOTE]
    if len(hits) != 1:
        sys.exit(f"ANCHOR DRIFT: Ohio-only signature note expected 1 paragraph, found {len(hits)}.")
    note = L["v3_signature_note"]
    if note is None:
        el = hits[0]._p
        el.getparent().remove(el)
    elif replace_in_paragraph(hits[0], V3_OHIO_SIGNATURE_NOTE, note) != 1:
        sys.exit("ANCHOR DRIFT: Ohio-only signature note replacement failed.")


def rebase_one_v30(doc, P, L):
    home = bool(P.get("home_state"))
    apply(doc, build_rules_v30(P, L, home))
    if not home:
        apply_signature_note_v30(doc, L)
    n = sum(replace_in_paragraph(p, "[PREMISES ADDRESS]", P["premises"]) for p in _footer_paragraphs(doc))
    if n < 1:
        sys.exit("ANCHOR DRIFT: no [PREMISES ADDRESS] token found in any footer part of the v3.0 master.")
    return doc


def _doc_text_v30(doc):
    return ("\n".join(p.text for p in doc.paragraphs),
            "\n".join(p.text for p in _footer_paragraphs(doc)))


def post_check_v30(path, P, L):
    doc = Document(str(path))
    body, foot = _doc_text_v30(doc)
    full = body + "\n" + foot
    errs = []
    for tok in ("[LANDLORD ENTITY]", "[LANDLORD STATE]", "[PREMISES ADDRESS]", "[BUILDING DEFINITION]",
                "[PARCEL REFERENCE]"):
        if tok in full:
            errs.append(f"unfilled token {tok}")
    if not P.get("home_state"):
        for residue in (ANCHOR_STATE, ANCHOR_STATE.upper(), "Revised Code", "R.C. "):
            if residue in full:
                errs.append(f"{ANCHOR_STATE} residue present: {residue!r}")
    if L["state"] not in body:
        errs.append("state name absent")
    if SAVINGS_TITLE not in body:
        errs.append("savings clause missing")
    if not re.search(r"ORA Master Lease v3\.\d+", foot):
        errs.append("footer form tag (ORA Master Lease v3.x) missing")
    if P["entity"] not in body:
        errs.append("landlord entity absent")
    if errs:
        sys.exit(f"POST-CHECK FAILED for {path.name}: {errs}")


def post_check(path, P, L):
    if is_v3(path):
        return post_check_v30(path, P, L)
    full = "\n".join(p.text for p in Document(str(path)).paragraphs)
    errs = []
    if P.get("variant") == "single-tenant":
        for tok in ("[PREMISES RSF]", "[PROPORTIONATE SHARE]", "[BASE YEAR]"):
            if tok in full:
                errs.append(f"single-tenant variant but {tok} token still present")
        for residue in ("gross up", "Allocation", "non-exclusive"):
            if residue in full:
                errs.append(f"single-tenant variant but multi-tenant residue: {residue}")
        for marker in ("the entire building situated at [PREMISES ADDRESS]",
                       "one hundred percent (100%), Tenant leasing the entire Building",
                       "janitorial service, snow and ice removal"):
            if marker not in full:
                errs.append(f"single-tenant marker missing: {marker[:50]}")
        for tok in ("[LANDLORD ENTITY]", "[PREMISES ADDRESS]"):
            if tok not in full:
                errs.append(f"generic variant should retain token {tok}")
        if SAVINGS_TITLE not in full:
            errs.append("savings clause missing")
        if P.get("lease_structure") == "NNN":
            if "OPERATING COSTS, TAXES AND INSURANCE" not in full:
                errs.append("NNN heading missing")
            if "\u201cInsurance\u201d " not in full and '"Insurance" ' not in full:
                errs.append("Insurance defined term missing")
        if errs:
            sys.exit(f"POST-CHECK FAILED for {path.name}: {errs}")
        return
    if ANCHOR_STATE in full and not P.get("home_state"):
        errs.append(f"{ANCHOR_STATE} residue present")
    for tok in ("[STATE]", "[LANDLORD ENTITY]", "[PREMISES ADDRESS]"):
        if tok in full:
            errs.append(f"unfilled token {tok}")
    if SAVINGS_TITLE not in full:
        errs.append("savings clause missing")
    if L["state"] not in full:
        errs.append("state name absent")
    if P.get("lease_structure") == "NNN":
        if "[BASE YEAR]" in full:
            errs.append("NNN property but [BASE YEAR] token still present")
        if "OPERATING COSTS, TAXES AND INSURANCE" not in full:
            errs.append("NNN property but OPERATING COSTS, TAXES AND INSURANCE heading missing")
        if "“Insurance” " not in full and '"Insurance" ' not in full:
            errs.append("NNN property but Insurance defined term missing")
    if errs:
        sys.exit(f"POST-CHECK FAILED for {path.name}: {errs}")


# --- Run-formatting (per-character rPr) parity: standard post-check (v1.10) --
# replace_in_paragraph() writes a fill into the FIRST run its anchor touches. An
# anchor that starts in a bold label therefore bolds the fill, and one that spans a
# bold defined term un-bolds it -- text-identical, visibly wrong. The v1.9 v3.0 draft
# did both ("Building", "Hazardous Materials", the BLI building value) and only a
# fixture-specific test caught it. This check runs on EVERY output against its own
# master, so no rebase -- new property, new overlay, new master -- can ship it.

# Visible character properties compared (w:rPr children). rsid/lang/proofing/kerning
# and similar non-visual properties are ignored; a colour at or below #404040 on every
# channel is treated as black (the v2.x masters carry stray #2F2F2F runs from the
# original drafting file -- visually black, and rebasing must not be blocked by them).
_VISIBLE_RPR = ("b", "i", "u", "strike", "dstrike", "caps", "smallCaps", "vertAlign", "highlight",
                "sz", "rFonts", "color", "shd", "rStyle", "vanish", "emboss", "imprint", "outline", "shadow")


def _rpr_key(rpr):
    if rpr is None:
        return ()
    props = []
    for el in rpr:
        tag = el.tag.rsplit("}", 1)[-1]
        if tag not in _VISIBLE_RPR:
            continue
        attrs = tuple(sorted((k.rsplit("}", 1)[-1], v) for k, v in el.attrib.items()))
        if tag == "color":
            val = dict(attrs).get("val", "auto")
            if val == "auto" or (re.fullmatch(r"[0-9A-Fa-f]{6}", val)
                                 and all(int(val[n:n + 2], 16) <= 0x40 for n in (0, 2, 4))):
                continue                                      # black / near-black == default
        if tag in ("b", "i", "caps", "smallCaps", "strike", "dstrike", "vanish") and \
                dict(attrs).get("val") in ("0", "false", "off"):
            continue                                          # explicit 'off' == absent
        props.append((tag, attrs))
    return tuple(sorted(props))


def _char_formats(p_el):
    """(text, [visible-format key per character]) for one w:p, over every run it
    contains (hyperlinks included)."""
    from docx.text.run import Run
    chars, keys = [], []
    for r_el in p_el.iter(qn("w:r")):
        txt = Run(r_el, None).text
        if not txt:
            continue
        key = _rpr_key(r_el.find(qn("w:rPr")))
        chars.append(txt)
        keys.extend([key] * len(txt))
    return "".join(chars), keys


def _part_paragraphs(doc):
    yield "body", [p._p for p in doc.paragraphs]
    for rel in doc.part.rels.values():
        if rel.reltype.endswith("/footer") or rel.reltype.endswith("/header"):
            yield str(rel.target_part.partname), list(rel.target_part.element.iter(qn("w:p")))


def _fmt_name(key):
    return "+".join(t for t, _a in key) or "plain"


def format_parity(master_doc, out_doc, limit=20, min_block=8):
    """Per-character run-formatting parity of a rebased output against its master.

    Paragraphs are aligned by text (difflib over each part's paragraph list). For an
    aligned pair whose text changed, the edit region is what lies between the common
    prefix and the common suffix: (1) every prefix/suffix character must keep its
    master formatting; (2) inside the region, text the master already had (matching
    blocks of >= `min_block` characters) must keep its formatting too -- a defined
    term re-emitted by a fill must not be un-bolded; (3) every other character in the
    region (the fill) must carry a formatting found on the master text it replaced.
    Unchanged paragraphs must match character for character. Wholly new paragraphs
    (the cloned savings clause, the NNN Insurance definition written into a blank
    spacer) and deleted ones (the MO signature note) have no master counterpart.
    Returns human-readable violations (empty list = parity)."""
    import difflib
    out_parts = dict(_part_paragraphs(out_doc))
    errs = []

    def ratio(a, b):
        return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio()

    for part, m_paras in _part_paragraphs(master_doc):
        o_paras = out_parts.get(part)
        if o_paras is None:
            continue
        mf = [_char_formats(p) for p in m_paras]
        of = [_char_formats(p) for p in o_paras]
        sm = difflib.SequenceMatcher(None, [t for t, _ in mf], [t for t, _ in of], autojunk=False)
        pairs = []
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
                pairs += list(zip(range(i1, i2), range(j1, j2)))
            elif op == "replace":
                for j in range(j1, j2):
                    best = max(range(i1, i2), key=lambda i: ratio(mf[i][0], of[j][0]))
                    if ratio(mf[best][0], of[j][0]) > 0.5:
                        pairs.append((best, j))
        for i, j in pairs:
            (mt, mk), (ot, ok) = mf[i], of[j]
            if not mt.strip():
                continue                                   # blank master spacer: nothing to inherit
            where = f"{part} paragraph {j} {ot[:50]!r}"
            if mt == ot:
                if mk != ok:
                    k = next(n for n in range(len(mk)) if mk[n] != ok[n])
                    errs.append(f"{where}: {mt[k:k + 30]!r} {_fmt_name(mk[k])} -> {_fmt_name(ok[k])}")
                continue
            pre = 0
            while pre < min(len(mt), len(ot)) and mt[pre] == ot[pre]:
                pre += 1
            suf = 0
            while suf < min(len(mt), len(ot)) - pre and mt[-1 - suf] == ot[-1 - suf]:
                suf += 1
            for a, b in [(n, n) for n in range(pre)] + [(len(mt) - 1 - n, len(ot) - 1 - n) for n in range(suf)]:
                if mk[a] != ok[b]:
                    errs.append(f"{where}: unchanged {mt[a:a + 30]!r} {_fmt_name(mk[a])} -> {_fmt_name(ok[b])}")
                    break
            m_mid, o_mid = mt[pre:len(mt) - suf], ot[pre:len(ot) - suf]
            mk_mid, ok_mid = mk[pre:len(mk) - suf], ok[pre:len(ok) - suf]
            kept = set()
            for blk in difflib.SequenceMatcher(None, m_mid, o_mid, autojunk=False).get_matching_blocks():
                if blk.size >= min_block:
                    for n in range(blk.size):
                        kept.add(blk.b + n)
                        if mk_mid[blk.a + n] != ok_mid[blk.b + n]:
                            errs.append(f"{where}: re-emitted {m_mid[blk.a + n:blk.a + n + 30]!r} "
                                        f"{_fmt_name(mk_mid[blk.a + n])} -> {_fmt_name(ok_mid[blk.b + n])}")
                            break
            allowed = set(mk_mid) if mk_mid else {mk[n] for n in (pre - 1, pre) if 0 <= n < len(mk)}
            bad = [n for n in range(len(o_mid)) if n not in kept and ok_mid[n] not in allowed]
            if bad:
                errs.append(f"{where}: fill {o_mid[bad[0]:bad[0] + 30]!r} is {_fmt_name(ok_mid[bad[0]])}, the "
                            f"text it replaced was {'/'.join(sorted(_fmt_name(k) for k in allowed))}")
            if len(errs) >= limit:
                return errs
    return errs


def check_format_parity(master_path, out_path):
    errs = format_parity(Document(str(master_path)), Document(str(out_path)))
    if errs:
        sys.exit(f"FORMAT PARITY FAILED for {pathlib.Path(out_path).name}: " + " | ".join(errs[:5])
                 + (f" (+{len(errs) - 5} more)" if len(errs) > 5 else "")
                 + " -- re-key the anchor so it neither starts in nor spans a differently formatted run.")


def rebase_one(master_path, P, L):
    """Single source of truth for the per-property pipeline — used by both main()
    and the test suite, so a step added here (like the NNN override) can't drift
    out of sync between the CLI path and its own tests again."""
    doc = Document(str(master_path))
    if is_v3(doc):
        if P.get("variant") or P.get("lease_structure"):
            sys.exit(f"{P.get('label')}: the v3.0 master is the multi-tenant modified-gross line only; "
                     "variant/lease_structure overrides (NNN, single-tenant) stay on the v2.x master.")
        return rebase_one_v30(doc, P, L)
    if P.get("variant") == "single-tenant":
        # Generic-tokenized variant: no entity/premises/PM fills, no state overlay
        # (the family is anchored to the master's own state). Footer token stays.
        convert_to_single_tenant(doc)
        if P.get("lease_structure") == "NNN":
            convert_to_nnn(doc)
        insert_savings_clause(doc)
        return doc
    apply(doc, build_rules_home(P) if P.get("home_state") else build_rules(P, L))
    if P.get("lease_structure") == "NNN":
        convert_to_nnn(doc)
    insert_savings_clause(doc)
    # v2.5: fill footer lease identifier. 2026-10-06 fix: walk EVERY footer part
    # (default, even, first) -- sec.footer reached only the default footer, so
    # even-page footers (and, on MD-COL, all footers) kept [PREMISES ADDRESS].
    from docx.text.paragraph import Paragraph
    for rel in doc.part.rels.values():
        if rel.reltype.endswith("/footer"):
            for p_el in rel.target_part.element.iter(qn("w:p")):
                replace_in_paragraph(Paragraph(p_el, None), "[PREMISES ADDRESS]", P["premises"])
    return doc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", required=True)
    ap.add_argument("--property", dest="prop")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    props = json.loads((CONFIG / "properties.json").read_text(encoding="utf-8"))
    states = json.loads((CONFIG / "state_overlays.json").read_text(encoding="utf-8"))
    props.pop("_comment", None)
    v3 = is_v3(a.master)
    pr = power_rights_master(Document(str(a.master)))
    if a.all and v3:
        keys = [k for k, P in props.items() if isinstance(P, dict) and "v3_0" in P]
    elif a.all and pr:
        # v1.10: from the v2.8 power-rights build on, the v2.x master is the NNN line only.
        # Properties with a "v3_0" entry moved to the MG short-form line (v3.x) and are
        # not re-emitted on the NNN line by --all (still reachable with --property).
        keys = [k for k, P in props.items() if isinstance(P, dict) and "v3_0" not in P]
        moved = [k for k, P in props.items() if isinstance(P, dict) and "v3_0" in P]
        print(f"NOTE: --all on a v2.8+ NNN-line master skips the MG-line properties {moved}")
    else:
        keys = list(props) if a.all else [a.prop]
    if not keys or keys == [None]:
        sys.exit("Specify --property KEY or --all. Known: " + ", ".join(props))
    unknown = [k for k in keys if k not in props]
    if unknown:
        sys.exit(f"Unknown property key(s) {unknown}. Known: " + ", ".join(props) +
                 ". Add new properties to config/properties.json (facts from source of record only).")

    m = re.search(r"_v(\d+\.\d+(?:\.\d+)?(?:-[A-Za-z0-9]+)?)_", pathlib.Path(a.master).name)
    ver = m.group(1) if m else "UNKNOWN"
    tag = master_form(Document(str(a.master)))
    if tag and m and tuple(int(x) for x in ver.split("-")[0].split(".")[:2]) != tag:
        sys.exit(f"ANCHOR DRIFT: master filename says v{ver} but its footer tag says v{tag[0]}.{tag[1]} -- "
                 "fix the master (or its name) before rebasing.")
    outdir = pathlib.Path(a.out); outdir.mkdir(parents=True, exist_ok=True)

    for k in keys:
        P = props[k]
        L = states.get(P["state_code"])
        if v3 and "v3_0" not in P:
            sys.exit(f"{k}: no 'v3_0' entry -- not on the v3.0 multi-tenant MG line (fail-closed).")
        if P.get("variant") == "single-tenant":
            L = L or {}
        elif P.get("home_state"):
            L = {"state": "Ohio"}
        elif not L or L.get("RESEARCH_REQUIRED"):
            sys.exit(f"{k}: state overlay {P['state_code']} is RESEARCH-REQUIRED — complete "
                     "config/state_overlays.json with fresh statutory research first (fail-closed by design).")
        doc = rebase_one(a.master, P, L)
        out = outdir / f"ORA_MasterLease_ShallowBay_{P['label']}_v{ver}_TEMPLATE.docx"
        doc.save(str(out))
        post_check(out, P, L)
        check_format_parity(a.master, out)      # v1.10: standard on every output
        print(f"OK {k} -> {out.name}")
    print("ALL REBASES PASSED")


if __name__ == "__main__":
    main()
