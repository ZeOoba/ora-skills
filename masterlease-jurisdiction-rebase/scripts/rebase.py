#!/usr/bin/env python3
"""ORA Master Lease jurisdiction rebase engine.

Edits the OH-anchored controlled master DOCX in place (native formatting preserved)
into a state-conformed property template. Every substitution carries an expected match
count; a mismatch aborts and names the anchor — anchor drift in a new master revision
must surface loudly, never silently (2026-08-03 propagation-audit discipline).

Usage:
  python3 rebase.py --master <master.docx> --property MD-EAS [--out DIR]
  python3 rebase.py --master <master.docx> --all [--out DIR]

Anchors keyed to master v2.4 (2026-08-03). On assertion failure after a master rev:
diff the masters, update the anchor here or in config/, log it in SKILL.md changelog.
"""
import argparse, copy, json, pathlib, re, sys
from docx import Document

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


def build_rules(P, L):
    st = L["state"]
    rules = [
        ("[LANDLORD ENTITY]", P["entity"], 3),
        ("a [STATE] limited liability company", f"a {st} limited liability company", 2),
        ("the building situated at [PREMISES ADDRESS] (such rentable area",
         f"the building situated at {P['premises']} (such rentable area", 1),
        ("the building known as [BUILDING ADDRESS], containing [BUILDING RSF] square feet of rentable area",
         P["building_def"], 1),
        (f"national banks in the State of {ANCHOR_STATE} are authorized to close",
         f"national banks in the State of {st} are authorized to close", 1),
        ("Demised Premisess", "Demised Premises", 1),  # master typo; drop this rule once fixed upstream
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
        ("1480 Dublin Rd", P["pm_block"][1], 1),
        ("Columbus, OH 43215", P["pm_block"][2], 1),
        ("ATTN: [MANAGER CONTACT]", P["pm_block"][3], 1),
    ]
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


def post_check(path, P, L):
    full = "\n".join(p.text for p in Document(str(path)).paragraphs)
    errs = []
    if ANCHOR_STATE in full:
        errs.append(f"{ANCHOR_STATE} residue present")
    for tok in ("[STATE]", "[LANDLORD ENTITY]", "[PREMISES ADDRESS]"):
        if tok in full:
            errs.append(f"unfilled token {tok}")
    if SAVINGS_TITLE not in full:
        errs.append("savings clause missing")
    if L["state"] not in full:
        errs.append("state name absent")
    if errs:
        sys.exit(f"POST-CHECK FAILED for {path.name}: {errs}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--master", required=True)
    ap.add_argument("--property", dest="prop")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    props = json.loads((CONFIG / "properties.json").read_text(encoding="utf-8"))
    states = json.loads((CONFIG / "state_overlays.json").read_text(encoding="utf-8"))
    props.pop("_comment", None)
    keys = list(props) if a.all else [a.prop]
    if not keys or keys == [None]:
        sys.exit("Specify --property KEY or --all. Known: " + ", ".join(props))
    unknown = [k for k in keys if k not in props]
    if unknown:
        sys.exit(f"Unknown property key(s) {unknown}. Known: " + ", ".join(props) +
                 ". Add new properties to config/properties.json (facts from source of record only).")

    m = re.search(r"_v(\d+\.\d+(?:\.\d+)?)_", pathlib.Path(a.master).name)
    ver = m.group(1) if m else "vUNKNOWN"
    outdir = pathlib.Path(a.out); outdir.mkdir(parents=True, exist_ok=True)

    for k in keys:
        P = props[k]
        L = states.get(P["state_code"])
        if not L or L.get("RESEARCH_REQUIRED"):
            sys.exit(f"{k}: state overlay {P['state_code']} is RESEARCH-REQUIRED — complete "
                     "config/state_overlays.json with fresh statutory research first (fail-closed by design).")
        doc = Document(a.master)
        apply(doc, build_rules(P, L))
        insert_savings_clause(doc)
        out = outdir / f"ORA_MasterLease_ShallowBay_{P['label']}_v{ver}_TEMPLATE.docx"
        doc.save(str(out))
        post_check(out, P, L)
        print(f"OK {k} -> {out.name}")
    print("ALL REBASES PASSED")


if __name__ == "__main__":
    main()
