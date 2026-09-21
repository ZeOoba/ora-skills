# -*- coding: utf-8 -*-
"""
gen_rent_schedule_ops.py — proves the M-04 design: the v2.7 master carries ONE
computed-schedule placeholder paragraph under RENT (never a fixed N-line table);
this helper is the draft-time step that expands it to N lines from a register's
rent.schedule array, using docx_edit_engine.py's existing insert_after primitive
(which already accepts a *list* of PARA specs — no engine change needed).

Usage: python3 gen_rent_schedule_ops.py <register.json> > ops_fill.json
"""
import sys, json

PLACEHOLDER_MATCH = "[RENT SCHEDULE — ONE LINE PER LEASE YEAR"

def build_ops(register):
    lines = []
    for row in register["rent"]["schedule"]:
        n = row["lease_year"]
        period = row.get("period", "")
        annual = row["annual"]
        monthly = row["monthly"]
        label = "Lease Year %d" % n
        if period and "–" not in period and " to " in period:
            start, end = [s.strip() for s in period.split(" to ")]
            period_txt = "(%s – %s)" % (start, end)
        elif period:
            period_txt = "(%s)" % period
        else:
            period_txt = ""
        text = "%s %s:  Annual Base Rent $%s; Monthly Rent $%s" % (
            label, period_txt, "{:,.2f}".format(annual), "{:,.2f}".format(monthly))
        lines.append({"kind": "IND", "text": text})
    ops = [
        {"op": "insert_after", "at": {"match": PLACEHOLDER_MATCH}, "paras": lines},
        {"op": "delete", "at": {"match": PLACEHOLDER_MATCH}},
    ]
    return ops

if __name__ == "__main__":
    reg = json.load(open(sys.argv[1], encoding="utf-8"))
    print(json.dumps(build_ops(reg), indent=1))
