#!/usr/bin/env python3
"""Mutation suite for lease_qc.py — "every check must be able to fail".

WHY (2026-10-15): the v3.0 property templates passed lease_qc 0 of 60 on 2026-10-08,
but eleven of those passes were EMPTY: the v2.7 trigger wording of A7, B2, B3, B8, F6,
F13, F14, F15, F16, F17 and F20 never occurs in v3.0 text, so the checks never looked
at the provisions they guard. A green scan proves nothing about a check that cannot
fail on the form being scanned. This suite makes that a CI property:

  for each canonical master fixture (v2.7 and v2.8 long-form NNN; v3.0 and v3.1
  short-form MG) and for EVERY check active on that fixture's form line (incl. the
  power-rights checks FP1-FP8 where enforced), a targeted mutation that breaks the
  provision the check guards must make EXACTLY that check (or a declared set) fail,
  while the unmutated fixture passes 0 of N.

Design:
  * MUTATIONS is a declarative table: Mutation(check, forms, ops, expect, why).
    `ops` are small text/meta edits applied in memory to the extracted body (`raw`),
    the footer, or the file name (no DOCX is written, so the whole suite runs in a
    second or two). Every op asserts that its anchor exists (MUTATION DRIFT
    otherwise), so a mutation can never pass vacuously either.
  * Each mutant is re-planned through lease_qc.plan_from_text() — the same form
    resolution and registry the CLI uses — and scanned with ora_doc_qc.run_checks().
    The failing-id set must EQUAL `expect` (default {check}); collateral failures
    are declared, never ignored.
  * Coverage: test_every_active_check_has_a_mutation fails the suite if any check
    active on any fixture has no mutation entry for that fixture, and
    test_na_checks_are_declared fails it if the registry reports an N/A check that is
    not in NOT_APPLICABLE (with its reason) or vice versa. A new check therefore
    cannot ship without a mutation entry (masterlease-revision-cycle Phase 3 rule).

Run:  python3 -I -B lease-form-qc/tests/test_lease_qc_mutations.py
      MUTATION_REPORT=1 ... prints the coverage table (fixture x active x mutated x N/A).
"""
import os
import pathlib
import re
import sys
import unittest
from collections import namedtuple

HERE = pathlib.Path(__file__).resolve().parent
SCRIPTS = HERE.parent / "scripts"
REPO = HERE.parent.parent
FIX = REPO / "masterlease-jurisdiction-rebase" / "scripts" / "fixtures"
sys.path.insert(0, str(SCRIPTS))
import lease_qc as q  # noqa: E402
from ora_doc_qc import extract, norm, run_checks  # noqa: E402

FIXTURES = {
    "v2.7": "ORA_MasterLease_ShallowBayIndustrial_v2.7_TEMPLATE.docx",
    "v2.8": "ORA_MasterLease_ShallowBayIndustrial_v2.8_TEMPLATE.docx",
    "v3.0": "ORA_MasterLease_ShallowBay_MultiTenantMG_v3.0_TEMPLATE.docx",
    "v3.1": "ORA_MasterLease_ShallowBay_MultiTenantMG_v3.1_TEMPLATE.docx",
}
# Expected active registry size per fixture (auto mode) -- pins the denominator.
ACTIVE_COUNT = {"v2.7": 60, "v2.8": 68, "v3.0": 65, "v3.1": 73}
V2, V3 = ("v2.7", "v2.8"), ("v3.0", "v3.1")
PWR = ("v2.8", "v3.1")
ALL = V2 + V3

# Checks the registry reports as N/A on a form line. Each must be listed here with
# its reason, and nothing may be listed that the registry does not report.
NOT_APPLICABLE = {
    ("v3.0", "F16"): "v3.x has no excess-rent/profit capture by ratified position (2026-10-08): "
                     "assignment is sole-discretion consent with cost reimbursement only.",
    ("v3.1", "F16"): "same as v3.0 (v3.1 = v3.0 + power-rights provisions only).",
}

Mutation = namedtuple("Mutation", "check forms ops expect why")


def M(check, forms, ops, expect=None, why=""):
    return Mutation(check, tuple(forms), tuple(ops), frozenset(expect or {check}), why)


# ---------------------------------------------------------------------------
# Ops. Each is a tuple; the first element names the op:
#   ("sub", old, new)          literal replace-all in the body; old must occur
#   ("sub", old, new, n)       ... and occur exactly n times
#   ("re", pattern, repl)      regex replace-all (re.I); must match
#   ("append", text)           append a new paragraph to the body
#   ("drop_para", snippet)     delete the one paragraph (line) containing snippet
#   ("cut_from", snippet)      truncate the body at snippet (must occur once)
#   ("drop_between", a, b)     delete from a up to (not including) b (each once)
#   ("footer_sub", old, new)   literal replace-all in the footer text; must occur
#   ("footer_append", text)    append a line to the footer text
#   ("name", basename)         scan under another file name (template vs execution copy)
#   ("fill_tokens",)           replace every [TOKEN] in body + footer with "Filled"
# ---------------------------------------------------------------------------
class MutationDrift(AssertionError):
    pass


def apply_ops(doc, ops):
    raw, footer, name = doc["raw"], doc["footer"], doc["name"]
    for op in ops:
        kind = op[0]
        if kind == "sub":
            old, new = op[1], op[2]
            n = raw.count(old)
            if n == 0 or (len(op) > 3 and n != op[3]):
                raise MutationDrift(f"sub anchor {old[:70]!r}: found {n}"
                                    + (f", expected {op[3]}" if len(op) > 3 else ""))
            raw = raw.replace(old, new)
        elif kind == "re":
            raw, n = re.subn(op[1], op[2], raw, flags=re.I)
            if n == 0:
                raise MutationDrift(f"re anchor {op[1]!r}: no match")
        elif kind == "append":
            raw = raw.rstrip("\n") + "\n" + op[1] + "\n"
        elif kind == "drop_para":
            lines = raw.split("\n")
            hit = [i for i, ln in enumerate(lines) if op[1] in ln]
            if len(hit) != 1:
                raise MutationDrift(f"drop_para {op[1][:70]!r}: found {len(hit)} paragraphs, expected 1")
            del lines[hit[0]]
            raw = "\n".join(lines)
        elif kind == "cut_from":
            if raw.count(op[1]) != 1:
                raise MutationDrift(f"cut_from {op[1][:70]!r}: found {raw.count(op[1])}, expected 1")
            raw = raw[:raw.index(op[1])]
        elif kind == "drop_between":
            a, b = op[1], op[2]
            if raw.count(a) != 1 or raw.count(b) < 1 or raw.index(b) < raw.index(a):
                raise MutationDrift(f"drop_between {a[:40]!r} .. {b[:40]!r}: anchors missing/ambiguous")
            raw = raw[:raw.index(a)] + raw[raw.index(b, raw.index(a)):]
        elif kind == "footer_sub":
            if op[1] not in footer:
                raise MutationDrift(f"footer_sub anchor {op[1]!r} not in footer")
            footer = footer.replace(op[1], op[2])
        elif kind == "footer_append":
            footer = footer + "\n" + op[1]
        elif kind == "name":
            name = op[1]
        elif kind == "fill_tokens":
            # fill every [TOKEN] and the signing-date blank, as a drafter would for an
            # execution copy; bracketed drafting notes ([COUNSEL REVIEW ...]) are not
            # tokens to fill and are kept (FP8 requires the counsel note).
            fill = lambda m: m.group(0) if _NOTE_RE.search(m.group(0)) else "Filled"  # noqa: E731
            raw = q.TOKEN_RE.sub(fill, raw)
            footer = q.TOKEN_RE.sub(fill, footer)
            raw = re.sub(r"this _{3,} day of", "this 1st day of", raw)
        else:
            raise ValueError(f"unknown op {kind}")
    return {"raw": raw, "footer": footer, "name": name, "meta": doc["meta"]}


_NOTE_RE = re.compile(r"COUNSEL|REVIEW|OPTIONAL|DELETE")
_CACHE = {}
_ACTIVE = {}


def load(form):
    if form not in _CACHE:
        path = FIX / FIXTURES[form]
        body, meta = extract(str(path), want_footer=True)
        _CACHE[form] = {"raw": body, "footer": meta["footer"], "name": path.name, "meta": meta}
    return _CACHE[form]


def scan_doc(doc, registry=None):
    """(failing ids, plan) for one in-memory document, planned exactly as the CLI plans it.
    `registry(checks) -> checks` substitutes the registry (harness self-test only)."""
    meta = dict(doc["meta"], footer=doc["footer"])
    plan = q.plan_from_text(doc["raw"], meta)
    checks = registry(plan["checks"]) if registry else plan["checks"]
    ctx = {"t": norm(doc["raw"]), "raw": doc["raw"], "meta": meta, "name": doc["name"],
           "allow_tokens": False, "is_template": "_TEMPLATE" in doc["name"].upper()}
    return {f["id"] for f in run_checks(ctx, checks)}, plan


EXEC = "ORA_Lease_ExecutionCopy_Acme.docx"        # a non-template file name (T1/T3/T4/F26 gates)
EXEC_COLLATERAL = {"v2.7": set(), "v2.8": {"T1"}, "v3.0": {"F26"}, "v3.1": {"F26", "T1"}}

# ---------------------------------------------------------------------------
# The mutation table. Grouped by check family; per-form variants where the two
# form lines word the provision differently (the v3.0 re-anchors).
# ---------------------------------------------------------------------------
MUTATIONS = [
    # ---- Class 1 deal-blocking ------------------------------------------
    M("A1", ALL, [("append", "The Building is at 10 Main Street, Columbus, Ohio 43004, and the Premises at "
                             "20 Main Street, Columbus, Ohio 43017.")],
      why="two conflicting Ohio ZIP codes"),
    M("A6", ALL, [("re", r"reconcil\w*", "review")], why="delete the reconciliation machinery"),
    M("A7", ALL, [("append", "Tenant shall pay Monthly Rent as net base rent.")],
      why="'net base rent' label on a base-year (modified gross) form"),
    M("A7", V3, [("sub", "exceed those for the Base Year stated in the Basic Lease Information", "are payable")],
      why="v3.0 anchor: the base-year expense stop removed"),
    M("A11", ALL, [("append", "Tenant shall deliver annual statements audited by a certified public accountant.")],
      why="audited CPA statements demanded"),
    M("B7", V2, [("re", r"notice address", "mailing location")], why="Tenant notice address removed"),
    M("B7", V3, [("re", r"notice address", "mailing location")], expect={"B7", "F19"},
      why="Tenant notice address removed; v3.0 F19 anchors on the same TENANT NOTICE ADDRESS line"),
    # ---- Class 2 dead / fragile cross-references -------------------------
    M("A2", V2, [("sub", "RIGHTS RESERVED BY LANDLORD.  Landlord reserves", "LANDLORD'S RESERVED RIGHTS.  "
                         "Landlord reserves", 1)],
      why="heading renamed while the 'entitled RIGHTS RESERVED BY LANDLORD' cross-reference remains"),
    M("A2", V3, [("append", "Such work is a right reserved in the section of this Lease entitled "
                            "“RIGHTS RESERVED BY LANDLORD”.")],
      why="cross-reference to a heading v3.0 does not have"),
    M("A2b", V2, [("sub", "entitled “ENTRY FOR INSPECTIONS, REPAIRS AND INSTALLATIONS,”",
                   "entitled \"INSPECTIONS, REPAIRS AND INSTALLATIONS,\"", 1)],
      why="cross-reference loses its leading 'ENTRY FOR'"),
    M("A2b", V3, [("append", "Landlord may enter as provided in the section of this Lease entitled "
                             "\"INSPECTIONS, REPAIRS AND INSTALLATIONS\".")], why="truncated cross-reference"),
    M("A3", ALL, [("append", "Tenant shall insure as required by the section of this Lease entitled "
                             "\"ALL RISK PROPERTY INSURANCE\".")], why="cross-reference to a non-existent section"),
    M("A9", ALL, [("append", "Except as set forth in the section of this Lease entitled \"DEFAULT OF TENANT\", "
                             "each party shall bear its own attorneys’ fees.")],
      why="prevailing-party carve-out pointed at the wrong section"),
    M("F7", ALL, [("append", "The obligations in this Section 12 survive.")], why="numeric self-reference"),
    # ---- Class 3 undefined operative terms -------------------------------
    M("A5a", ALL, [("sub", "“Project” means", "the Project includes", 1)], why="'Project' definition broken"),
    M("A5b", ALL, [("sub", "“Building” means", "the Building is", 1)], why="'Building' definition broken"),
    M("A5c", V2, [("sub", "“Business Day” means", "a business day is", 1),
                  ("sub", "five (5) Business Days following the date when due", "five (5) days following the date when due", 1)],
      why="'Business Day' definition broken (late-fee clause moved to calendar days so F6 stays quiet)"),
    M("A5c", V3, [("sub", "“Business Day” means", "a business day is", 1),
                  ("re", r"\(5\) Business Days (after it is due|late)", r"(5) days \1")],
      why="'Business Day' definition broken (late-fee clause moved to calendar days so F6 stays quiet)"),
    M("F6", ALL, [("sub", "“Business Day” means", "a business day is", 1)], expect={"F6", "A5c"},
      why="late fee runs on undefined Business Days (A5c necessarily fires too: same undefined term)"),
    M("F12", V2, [("sub", "“Governmental Agency” means", "governmental agency includes", 1)],
      why="'Governmental Agency' used but undefined"),
    M("F12", V3, [("sub", "“Building Standard” means", "building standard work is", 1)],
      why="'Building Standard' used but undefined"),
    # ---- Class 4 statutory citations -------------------------------------
    M("A4a", ALL, [("append", "Hazardous Materials include substances regulated under 42 U.S.C. Section 9061.")],
      why="CERCLA miscited"),
    M("A4b", ALL, [("append", "Hazardous Materials include materials regulated under 49 U.S.C. Section 1802.")],
      why="HMTA obsolete citation"),
    # ---- Class 5 Ohio law exposure / remedies ----------------------------
    M("A8", ALL, [("append", "If Tenant is or will be a corporation, each signer represents its authority.")],
      why="authority clause limited to corporations"),
    M("A10", ALL, [("append", "Delay in Commencement.  If Landlord cannot deliver possession, Rent abates.")],
      why="circular Delay in Commencement clause"),
    M("B2", V2, [("sub", "required by applicable law", "customary")], why="mitigation disclaimer unqualified"),
    M("B2", V3, [("sub", "Except to the extent required by law, Landlord has no duty to relet",
                  "Landlord has no duty to relet", 1)], why="v3.0 anchor: mitigation disclaimer unqualified"),
    M("B3", V2, [("re", r"net proceeds of any reletting|fair rental value", "amounts")],
      why="acceleration without reletting credit"),
    M("B3", V3, [("sub", "less the net proceeds of any reletting or, absent reletting, the fair rental value of "
                         "the Premises for that period", "", 1)],
      why="v3.0 anchor: acceleration without reletting credit"),
    M("B4", ALL, [("append", "Holdover rent is two hundred percent (200%) of the amount of (a) Monthly Rent and "
                             "(b) all other sums then due.")], why="holdover multiplier applied to arrears"),
    M("B5", ALL, [("sub", "responsible for replacement of the heating", "responsible for the heating", 1)],
      why="HVAC replacement allocation removed"),
    M("B6a", ALL, [("re", r"general aggregate", "overall")], why="CGL aggregate limit removed"),
    M("B6b", ALL, [("re", r"Employer.s Liability", "workplace")], why="Employer's Liability limit removed"),
    M("B6c", ALL, [("sub", "renewal certificates", "certificates"), ("sub", "annually during the Lease Term", "on request")],
      why="annual COI delivery removed"),
    M("B8", V2, [("sub", "flat rate of $", "rate of $", 1)], why="water billing mechanism removed"),
    M("B8", V3, [("sub", "within thirty (30) days after each invoice, for the cost of that service, measured by "
                         "sub-meter if the Premises are sub-metered and otherwise by Tenant’s Proportionate Share of "
                         "the Building’s charges or another equitable allocation Landlord reasonably determines",
                  "for that service", 1)], why="v3.0 anchor: water billing mechanism removed"),
    M("B11", ALL, [("sub", "any person or entity comprising Tenant", "Tenant", 1),
                   ("append", "This Lease binds any guarantor of this Lease.")],
      why="'any guarantor' language with no guaranty and no co-tenant conform"),
    M("F5", ALL, [("append", "This Lease is executed under seal.")], why="'under seal'"),
    M("F8", V2, [("sub", "maximum rate permitted by", "rate stated in", 3)], why="usury savings removed"),
    M("F8", V3, [("sub", "maximum rate permitted by", "rate stated in", 1)], why="usury savings removed"),
    # ---- Class 5a/5b/5e standard provisions -------------------------------
    M("F10", ALL, [("sub", "Venue for any action", "Any action", 1)], why="venue clause removed"),
    M("F11", ALL, [("sub", "waived pursuant to the waiver of subrogation", "released", 1)],
      why="indemnity waiver-of-subrogation carve-out removed"),
    M("F13", V2, [("sub", "shall not include amounts separately billed", "shall include amounts", 1)],
      why="separate-billing exclusion removed"),
    M("F13", V3, [("sub", ", excluding costs billed directly to any tenant", "", 1)],
      why="v3.0 anchor: directly-billed exclusion removed"),
    M("F14", V2, [("sub", "(Special Form)", "")], why="All Risk without Special Form"),
    M("F14", V3, [("sub", "all risks of physical loss (special form)", "fire and extended coverage", 1)],
      why="v3.0 anchor: no special-form standard"),
    M("F15", V2, [("sub", "manager, member, officer, employee or agent of Landlord", "person", 1)],
      why="exculpation enumeration removed"),
    M("F15", V3, [("sub", "and no member, manager, officer, employee or agent of Landlord has any personal "
                          "liability under this Lease", "", 1)], why="v3.0 anchor: exculpation enumeration removed"),
    M("F16", V2, [("sub", "of such excess", "of such amount", 1)], why="excess-rent capture removed"),
    M("F17", V2, [("sub", "preventative-maintenance contract", "service arrangement", 1)],
      why="HVAC PM contract removed"),
    M("F17", V3, [("sub", "Tenant shall keep a preventive-maintenance contract with a licensed HVAC contractor "
                          "providing service at least twice a year and give Landlord copies of the contract and "
                          "service reports on request.", "", 1)], why="v3.0 anchor: HVAC PM contract removed"),
    M("F18", ALL, [("footer_sub", "ORA Master Lease v", "Lease form ")], why="footer form tag removed"),
    M("F19", V2, [("append", "Notices shall be given, if to Tenant, at the Demised Premises.")],
      why="Tenant notices routed to the Premises only"),
    M("F19", V3, [("sub", "or to Tenant also by e-mail or at the Premises", "or, if to Tenant, at the Premises.", 1)],
      why="v3.0 anchor: Tenant notices routed to the Premises only"),
    M("F20", V2, [("re", r"RENT SCHEDULE|set forth in the following schedule", "rent table")],
      why="escalating rent without a schedule"),
    M("F20", V3, [("sub", "; the Rent Schedule controls in the event of any conflict", "", 1)],
      why="v3.0 anchor: schedule no longer controls"),
    M("F21", ALL, [("sub", "has not been fully executed and delivered by Landlord and Tenant on or before",
                    "is executed after", 1)], why="late-signing commencement clause removed"),
    # ---- Class 6 missing provisions --------------------------------------
    M("C1", ALL, [("sub", "shall not record this Lease", "may record this Lease", 1)], why="no-recording removed"),
    M("C2", ALL, [("sub", "Landlord shall not be in default", "Landlord is in default", 1)],
      why="Landlord default cure standard removed"),
    M("C3", ALL, [("re", r"force majeure", "unavoidable delay")], why="force majeure removed"),
    M("C4", ALL, [("re", r"Foreign Assets Control|OFAC", "sanctions authority")], why="OFAC rep removed"),
    M("C5", ALL, [("re", r"counterpart", "copy")], why="counterparts clause removed"),
    M("C6", ALL, [("re", r"time is of the essence", "timing matters")], why="time-of-essence removed"),
    M("C7", ALL, [("sub", "taxes and assessments levied on Tenant", "charges on Tenant", 1)],
      why="personal property tax allocation removed"),
    M("C8", ALL, [("sub", "Exhibit A", "the site plan")], why="Exhibit A premises depiction removed"),
    # ---- Class 8 typography ----------------------------------------------
    M("F1", ALL, [("append", "Landlord and his agents, employees and invitees may enter.")], why="'his agents'"),
    M("F2", ALL, [("append", "Landlord may sign a succeeding Lease or succeeding tenant agreement.")],
      why="'succeeding Lease or succeeding tenant'"),
    M("F3", ALL, [("append", "Notice may be published in a comparable publications.")], why="'a comparable publications'"),
    M("F4", ALL, [("append", "Tenant shall replace bulbs and Interior lighting fixtures.")], why="'Interior lighting'"),
    M("F9", ALL, [("append", "Tenant\xa0shall comply.")], why="non-breaking-space artifact"),
    # ---- Class 5c/5d tokens, footer fields, execution readiness ----------
    M("T1", V2, [("name", EXEC)], expect={"T1", "T3"},
      why="the raw master used as an execution copy: [TOKENS] remain (T3: its signing-date blank too)"),
    M("T1", V3, [("name", EXEC)], expect={"T1", "T4", "F26"},
      why="the raw master used as an execution copy: [TOKENS] remain (T4: its [ATTACH ...] exhibit stub; "
          "F26: its optional-module instruction)"),
    M("T2", ALL, [("sub", "[TENANT ENTITY]", "Acme Widgets LLC"),
                  ("footer_append", "FILENAME Lease Zenith Corp 10-2026 v01.docx")],
      why="footer FILENAME field resolves to a different tenant"),
] + [
    # Filled execution copies (tokens and the signing-date blank filled, as a drafter
    # would). EXEC_COLLATERAL: what a filled copy of each master still trips by design --
    # v3.x keeps the Specialized Equipment [OPTIONAL MODULE ...] instruction (F26), and
    # v2.8/v3.1 keep the backup-power module's [COUNSEL REVIEW REQUIRED BEFORE FIRST USE]
    # note, which T1 reads as a token in an execution copy while FP8 requires it
    # (see SKILL.md Class 5g open item).
    M(cid, (form,), [("name", EXEC), ("fill_tokens",)] + list(extra), expect={cid} | EXEC_COLLATERAL[form] | set(more),
      why=why)
    for form in ALL
    for cid, extra, more, why in (
        ("T1", [("append", "Permitted Use: [PERMITTED USE]")], (), "one token left unfilled in an execution copy"),
        ("T3", [("append", "ATTN: ______________")], (), "underscore blank in an execution copy"),
        ("T4", [("append", "EXHIBIT C TO BE ATTACHED PRIOR TO EXECUTION")], (), "exhibit stub in an execution copy"),
    )
] + [
    M("F26", (form,), [("name", EXEC), ("fill_tokens",)], expect={"F26"} | (EXEC_COLLATERAL[form] - {"F26"}),
      why="Specialized Equipment module instruction left in an execution copy")
    for form in V3
] + [
    M("D1", V2, [("sub", "Late Fee: 10% of any payment", "Late Fee: 12% of any payment", 1)],
      why="BLI late fee drifts from the body's ten percent (10%)"),
    M("D1", V3, [("sub", "Late Fee / Default Rate: 10% of any payment", "Late Fee / Default Rate: 12% of any payment", 1)],
      why="BLI late fee drifts from the body's ten percent (10%)"),
    M("D2", ALL, [("append", "Lease Year 1: $120,000.00 $10,500.00")],
      why="rent-schedule row whose monthly is not annual / 12"),
    # ---- v3.x form checks (F0, F22-F26) ----------------------------------
    M("F0", ("v3.0",), [("footer_sub", "v3.0", "v2.7")], why="v2.7 footer tag carried onto v3.0 structure"),
    M("F0", ("v3.1",), [("footer_sub", "v3.1", "v2.8")], why="v2.8 footer tag carried onto v3.1 structure"),
    M("F22", V3, [("append", "Tenant shall comply with the Widget Maintenance section.")],
      why="dead 'the <Name> section' cross-reference"),
    M("F22", V3, [("drop_between", "SPECIALIZED EQUIPMENT.", "ASSIGNMENT; SUBLETTING")], expect={"F22", "F26"},
      why="optional module deleted without deleting its references"),
    M("F23", ("v3.0",), [("sub", "So long as no Event of Default exists,", "Landlord may relocate Tenant to other space "
                                  "in the Project on thirty (30) days' notice. So long as no Event of Default exists,", 1)],
      why="relocation right inserted"),
    M("F23", ("v3.1",), [("sub", "So long as no Event of Default exists,", "Landlord may relocate Tenant to other space "
                                  "in the Project on thirty (30) days' notice. So long as no Event of Default exists,", 1)],
      expect={"F23", "FP1"}, why="relocation right inserted (FP1 also bars relocation on v3.x)"),
    M("F24", V3, [("sub", "Tenant shall deliver the Security Deposit", "Tenant shall deliver annual financial "
                          "statements to Landlord. Tenant shall deliver the Security Deposit", 1)],
      why="financial-statements demand inserted"),
    M("F25", V3, [("cut_from", "EXHIBIT B\nRULES")], why="embedded Exhibit B removed"),
    M("F26", V3, [("drop_between", "SPECIALIZED EQUIPMENT.", "ASSIGNMENT; SUBLETTING"),
                  ("sub", "Except as provided in the Specialized Equipment section (if included), Tenant", "Tenant", 1),
                  ("sub", "Except for any Approved Consumables used in accordance with the Specialized Equipment "
                          "section, Tenant", "Except for any Approved Consumables, Tenant", 1)],
      why="module deleted and its section cross-references cleaned, but an Approved Consumables reference left"),
    # ---- power-rights standard (enforced on v2.8 / v3.1) -----------------
    M("FP1", PWR, [("sub", "belong to Landlord or its licensees", "are shared with Tenant", 1)],
      why="energy revenue no longer Landlord's"),
    M("FP1", PWR, [("sub", "not be an eviction or entitle Tenant to any abatement", "entitle Tenant to an abatement", 1)],
      why="no-abatement covenant removed"),
    M("FP2", PWR, [("sub", "twenty-four (24) hours’ notice of any planned", "reasonable notice of any planned", 1)],
      why="24-hour shutdown notice removed"),
    M("FP2", PWR, [("re", r"utility, interconnection and access easements", "access rights")],
      why="utility/interconnection easements removed"),
    M("FP3", PWR, [("drop_para", "Tenant shall not remove any electrical service equipment")],
      why="Electrical Capacity subsection deleted"),
    M("FP3", PWR, [("sub", "  Tenant shall not remove any electrical service equipment, notwithstanding any right to "
                           "remove its trade fixtures.", "", 1)], why="capacity carve-out from removal deleted"),
    M("FP4", PWR, [("sub", "is not excluded merely because", "is excluded because", 1)],
      why="roof-repair proviso inverted"),
    M("FP4", PWR, [("sub", "all costs of, and all revenues, credits and incentives from,", "all costs of", 1)],
      why="Operating Costs exclusion of energy revenues removed"),
    M("FP5", PWR, [("sub", "Within ten (10) days after Landlord’s request, Tenant shall deliver",
                    "Within thirty (30) days after Landlord’s request, Tenant shall deliver", 1)],
      why="utility-data authorization deadline weakened"),
    M("FP6", PWR, [("sub", "in this Lease or its financing parties", "in this Lease", 1)],
      why="estoppel no longer reaches financing parties"),
    M("FP7", PWR, [("sub", "shall not count against", "shall count against", 1)],
      why="charging spaces count against Tenant's parking"),
    M("FP7", PWR, [("sub", ", provided that Tenant retains reasonable access to parking for its operations", "", 1)],
      why="Tenant's reasonable-access proviso removed"),
    M("FP8", PWR, [("sub", "UL 9540A", "UL test", 1)], why="module lacks UL 9540A"),
    M("FP8", PWR, [("sub", "back-feed", "power flow", 1)], why="module lacks the no-back-feed requirement"),
    M("FP8", PWR, [("sub", "[COUNSEL REVIEW REQUIRED BEFORE FIRST USE]", "", 1)], why="module lacks the counsel note"),
]


def active_ids(form):
    if form not in _ACTIVE:
        _ids, plan = scan_doc(load(form))
        _ACTIVE[form] = ([c[0] for c in plan["checks"]], plan)
    return _ACTIVE[form]


class MutationSuite(unittest.TestCase):

    def test_unmutated_fixtures_pass_with_expected_registry(self):
        for form in FIXTURES:
            with self.subTest(form=form):
                ids, plan = scan_doc(load(form))
                self.assertEqual(ids, set(), f"unmutated {form} master fails {sorted(ids)}")
                self.assertEqual(len(plan["checks"]), ACTIVE_COUNT[form])
                self.assertEqual(plan["power_active"], form in PWR)

    def test_each_mutation_fails_exactly_its_declared_checks(self):
        for m in MUTATIONS:
            for form in m.forms:
                with self.subTest(check=m.check, form=form, why=m.why):
                    base = load(form)
                    mutant = apply_ops(base, m.ops)
                    self.assertNotEqual((mutant["raw"], mutant["footer"], mutant["name"]),
                                        (base["raw"], base["footer"], base["name"]), "mutation changed nothing")
                    got, _plan = scan_doc(mutant)
                    self.assertEqual(got, set(m.expect),
                                     f"{form} mutation for {m.check} ({m.why}) failed {sorted(got)}, "
                                     f"declared {sorted(m.expect)}")

    def test_every_active_check_has_a_mutation(self):
        """Coverage gate: a check active on a fixture with no mutation entry that
        targets it on that fixture fails the suite -- a new check cannot ship
        without proving it can fail."""
        missing = []
        for form in FIXTURES:
            ids, _plan = active_ids(form)
            covered = {m.check for m in MUTATIONS if form in m.forms}
            missing += [f"{form}:{cid}" for cid in ids if cid not in covered]
        self.assertEqual(missing, [], "active checks with no mutation entry: " + ", ".join(missing))

    def test_mutations_target_only_active_checks(self):
        stray = []
        for form in FIXTURES:
            ids, _plan = active_ids(form)
            for m in MUTATIONS:
                if form in m.forms and m.check not in ids:
                    stray.append(f"{form}:{m.check}")
        self.assertEqual(stray, [], "mutation entries for checks not active on that form: " + ", ".join(stray))

    def test_na_checks_are_declared(self):
        for form in FIXTURES:
            with self.subTest(form=form):
                _ids, plan = active_ids(form)
                reported = {x["id"] for x in plan["na"]}
                declared = {cid for (f, cid) in NOT_APPLICABLE if f == form}
                self.assertEqual(reported, declared)
                for cid in declared:
                    self.assertTrue(NOT_APPLICABLE[(form, cid)].strip())

    def test_harness_catches_an_empty_pass(self):
        """Self-test: the exact failure mode this suite exists for. Scanning v3.0 paper
        with the v2.7 registry (what the 2026-10-08 run did) leaves the v3.0 mutations
        for the re-anchored checks undetected, and a check stubbed to always pass is
        reported as not failing its mutation."""
        blind = []
        for m in MUTATIONS:
            if "v3.0" in m.forms and m.check in q.V30_REANCHOR and m.check != "B4":
                got, _ = scan_doc(apply_ops(load("v3.0"), m.ops), registry=lambda _c: q.CHECKS)
                if m.check not in got:
                    blind.append(m.check)
        self.assertGreaterEqual(len(set(blind)), 10, sorted(set(blind)))
        stub = lambda cs: [(c[0], c[1], c[2], c[3], (lambda ctx: None)) if c[0] == "C3" else c for c in cs]  # noqa: E731
        m = next(x for x in MUTATIONS if x.check == "C3")
        got, _ = scan_doc(apply_ops(load("v2.7"), m.ops), registry=stub)
        self.assertNotIn("C3", got)

    def test_mutation_drift_is_loud(self):
        with self.assertRaises(MutationDrift):
            apply_ops(load("v2.7"), [("sub", "this text is not in the master", "x")])
        with self.assertRaises(MutationDrift):
            apply_ops(load("v2.7"), [("sub", "Exhibit A", "x", 1)])          # occurs 4 times


def coverage_table():
    rows = []
    for form in FIXTURES:
        ids, plan = active_ids(form)
        covered = {m.check for m in MUTATIONS if form in m.forms}
        n_mut = sum(1 for m in MUTATIONS if form in m.forms)
        rows.append((form, FIXTURES[form], len(ids), len([i for i in ids if i in covered]), n_mut,
                     len(plan["na"]), plan["form"]["power_rights"]))
    return rows


if __name__ == "__main__":
    if os.environ.get("MUTATION_REPORT"):
        print("| Fixture | Active checks | Checks mutated | Mutation cases | N/A | Power rights |")
        print("|---|---|---|---|---|---|")
        for form, name, n, cov, nm, na, pw in coverage_table():
            print(f"| {form} master | {n} | {cov} | {nm} | {na} | {pw} |")
    unittest.main()
