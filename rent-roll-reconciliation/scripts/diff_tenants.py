"""
Diff a parsed rent roll (see parse_rent_roll.py) against a pulled snapshot
of the Notion Tenant Database, and report:
  - matched records with field mismatches (SF, rent, dates, escalation)
  - Notion records with no rent-roll match
  - rent-roll rows with no Notion match

Usage:
    python diff_tenants.py notion_all.json rentroll.json

notion_all.json: list of dicts with at least:
    id, Tenant Name, Property Address, Suite / Unit, SF, Monthly Rent,
    Lease Start, Lease Expiration, Next Escalation Date, Escalation Percent

rentroll.json: output of parse_rent_roll.py

This is a starting point, not a black box -- read the output and use
judgment per SKILL.md step 5/6 before writing anything. In particular,
a "no match" from this script is NOT sufficient justification to retire
a record; a "match" on name alone without SF/rent corroboration can be a
false positive (see the Bay Area Corporation / Bay Area Exteriors case
in SKILL.md history) -- always check the matched SF/rent line up too.
"""
import sys
import json
import re


def norm(s):
    if not s:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\b(llc|inc|ltd|corp|corporation|company|co|the|dba|jr|sr)\b", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_rr_index(rentroll):
    idx = []
    for r in rentroll:
        if not r.get("property") or str(r["property"]).strip().upper() in ("NONE", "PORTFOLIO TOTALS"):
            continue
        toks = set()
        for f in ("contact", "company"):
            v = norm(r.get(f))
            if v:
                toks.add(v)
        idx.append({"rec": r, "toks": toks})
    return idx


def match_rr(name, rr_idx):
    n = norm(name)
    if not n:
        return None
    for e in rr_idx:
        for t in e["toks"]:
            if t and len(t) > 2 and (n in t or t in n):
                return e["rec"]
    return None


def diff(notion, rentroll):
    rr_idx = build_rr_index(rentroll)
    matched_ids = set()
    mismatches = []
    no_match = []

    for rec in notion:
        name = rec.get("Tenant Name", "")
        if name.startswith("[Unknown") or name.startswith("⛔"):
            continue
        m = match_rr(name, rr_idx)
        if not m:
            no_match.append(rec)
            continue
        matched_ids.add(id(m))

        diffs = {}
        if m.get("sf") is not None and rec.get("SF") != m["sf"]:
            diffs["SF"] = (rec.get("SF"), m["sf"])
        if m.get("monthly_rent") is not None:
            a, b = rec.get("Monthly Rent") or 0, m["monthly_rent"] or 0
            if abs(a - b) > 0.02:
                diffs["Monthly Rent"] = (rec.get("Monthly Rent"), m["monthly_rent"])
        if m.get("lease_start") and rec.get("Lease Start") != m["lease_start"]:
            diffs["Lease Start"] = (rec.get("Lease Start"), m["lease_start"])
        if m.get("lease_end") and rec.get("Lease Expiration") != m["lease_end"]:
            diffs["Lease Expiration"] = (rec.get("Lease Expiration"), m["lease_end"])
        if m.get("escalation_date") and rec.get("Next Escalation Date") != m["escalation_date"]:
            diffs["Next Escalation Date"] = (rec.get("Next Escalation Date"), m["escalation_date"])
        if m.get("escalation_pct") is not None:
            a, b = rec.get("Escalation Percent") or 0, m["escalation_pct"] or 0
            if abs(a - b) > 0.0005:
                diffs["Escalation Percent"] = (rec.get("Escalation Percent"), m["escalation_pct"])

        if diffs:
            mismatches.append({
                "id": rec.get("id"),
                "name": name,
                "property": rec.get("Property Address"),
                "diffs": diffs,
            })

    unmatched_rr = [e["rec"] for e in rr_idx if id(e["rec"]) not in matched_ids]
    return mismatches, no_match, unmatched_rr


if __name__ == "__main__":
    notion = json.load(open(sys.argv[1]))
    rentroll = json.load(open(sys.argv[2]))

    mismatches, no_match, unmatched_rr = diff(notion, rentroll)

    print(f"=== FIELD MISMATCHES ON MATCHED RECORDS ({len(mismatches)}) ===")
    for m in mismatches:
        print(m["id"], "|", m["name"], "|", m["property"], "|", m["diffs"])

    print(f"\n=== NOTION RECORDS WITH NO RENT-ROLL MATCH ({len(no_match)}) ===")
    for r in no_match:
        print(r.get("id"), "|", r.get("Tenant Name"), "|", r.get("Property Address"),
              "|SF", r.get("SF"), "|rent", r.get("Monthly Rent"))

    print(f"\n=== RENT-ROLL ROWS WITH NO NOTION MATCH ({len(unmatched_rr)}) ===")
    for r in unmatched_rr:
        print(r.get("property"), "|", r.get("unit"), "|", r.get("contact"), "|", r.get("company"),
              "|SF", r.get("sf"), "|rent", r.get("monthly_rent"))
