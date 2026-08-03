#!/usr/bin/env python3
"""
lease_qc.py - Oxford Realty Advisors lease-form QC scanner.
Companion to the `lease-form-qc` skill. Scans a lease DOCX drafted on ORA paper
for the systemic defect classes documented in that skill.

Usage:  python3 lease_qc.py <lease.docx> [more.docx ...]
Exit:   0 = all PASS, 1 = one or more FAIL
"""
import sys, re, zipfile

def text_of(path):
    if path.lower().endswith('.docx'):
        with zipfile.ZipFile(path) as z:
            xml = z.read('word/document.xml').decode('utf-8', 'replace')
            has_ins = '<w:ins ' in xml
            has_del = '<w:del ' in xml
            has_strike = 'w:strike' in xml
            has_cmt = any(n.endswith('word/comments.xml') for n in z.namelist())
        t = re.sub(r'<w:p[ >]', '\n<w:p ', xml)
        t = re.sub(r'<[^>]+>', '', t)
        for a, b in [('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                     ('&quot;', '"'), ('&apos;', "'")]:
            t = t.replace(a, b)
    else:
        t = open(path, encoding='utf-8', errors='replace').read()
        has_ins = has_del = has_strike = has_cmt = False
    return re.sub(r'[ \t]+', ' ', t), (has_ins, has_del, has_strike, has_cmt)


Q = '["\u201c\u201d\u2018\u2019\u00ab\u00bb]'

def _defined(t, term):
    """True if `term` is given an operative definition, in any quote style."""
    return bool(re.search(Q + r'\s*' + term + r'\s*' + Q + r'\s*(shall\s+)?means?\b', t))

# (id, severity, label, test) -- test returns True when the DEFECT IS PRESENT
CHECKS = [
 ("A1","BLOCK","ZIP/address conflict between Sec.1 premises and Sec.4 building block",
  lambda t: len({z for z in re.findall(r'\b4\d{4}\b', t)} - {'43215'}) > 1),
 ("A6","BLOCK","Operating-cost pass-through has no billing/reconciliation machinery",
  lambda t: not re.search(r'reconcil', t, re.I)),
 ("A7","BLOCK","'net base rent' label on a base-year expense stop (NNN vs gross conflict)",
  lambda t: bool(re.search(r'net base rent', t, re.I)) and bool(re.search(r'increase over base year', t, re.I))),
 ("A11","BLOCK","Audited CPA financial statements demanded of a small tenant",
  lambda t: bool(re.search(r'audited by a certified public accountant', t, re.I))),
 ("B7","BLOCK","Tenant notice address is the Premises only (fails pre-occupancy/post-abandonment)",
  lambda t: not re.search(r'TENANT NOTICE ADDRESS|Tenant.{0,40}notice address', t, re.I)),
 ("A2","HIGH","Dead cross-reference: 'RIGHTS RESERVED BY LANDLORD' section does not exist",
  lambda t: 'RIGHTS RESERVED BY LANDLORD' in t.upper()
            and not re.search(r'^\s*RIGHTS RESERVED BY LANDLORD\.', t, re.M | re.I)),
 ("A2b","HIGH","Dead cross-reference: 'INSPECTIONS...' missing the leading 'ENTRY FOR'",
  lambda t: bool(re.search(r'entitled[,]?\s*[""]?\s*INSPECTIONS,\s*REPAIRS', t, re.I))
            or bool(re.search(r'REPAIRS AND INSTALLATION[,""]', t))),
 ("A3","HIGH","Dead cross-reference: section 'ALL RISK PROPERTY INSURANCE' does not exist",
  lambda t: bool(re.search(r'entitled[,]?\s*[""]?\s*ALL RISK PROPERTY INSURANCE', t, re.I))),
 ("A9","HIGH","Prevailing-party carve-out cites DEFAULT OF TENANT; fee rule lives in REMEDIES",
  lambda t: bool(re.search(r'Except as set forth in the section of this Lease entitled\s*[""]?DEFAULT OF TENANT', t, re.I))),
 ("A5a","HIGH","'Project' used but never defined", lambda t: 'Project' in t and not _defined(t, 'Project')),
 ("A5b","HIGH","'Building' used but never defined", lambda t: 'Building' in t and not _defined(t, 'Building')),
 ("A5c","HIGH","'Business Day' used but never defined", lambda t: 'Business Day' in t and not _defined(t, 'Business Days?')),
 ("A4a","HIGH","CERCLA miscited as 42 U.S.C. 9061 (correct: 9601)", lambda t: '9061' in t),
 ("A4b","HIGH","HMTA cited at obsolete 49 U.S.C. 1802 (recodified 1994 at 5101)",
  lambda t: bool(re.search(r'49 U\.?\s?S\.?\s?C\.?\s*(Section|§)?\s*1802', t))),
 ("A8","HIGH","Authority clause limited to corporations (tenants are LLCs/individuals)",
  lambda t: bool(re.search(r'If Tenant is or will be a corporation', t, re.I))),
 ("A10","HIGH","'Delay in Commencement' circular against a fixed Commencement Date",
  lambda t: bool(re.search(r'Delay in Commencement', t, re.I))),
 ("B2","HIGH","Mitigation disclaimer unqualified (Frenchtown v. Lemstone exposure)",
  lambda t: bool(re.search(r'no obligation to relet', t, re.I))
            and not re.search(r'required by applicable law', t, re.I)),
 ("B3","MED","Acceleration without credit for reletting proceeds / fair rental value",
  lambda t: bool(re.search(r'accelerate and recover', t, re.I))
            and not re.search(r'net proceeds of any reletting|fair rental value', t, re.I)),
 ("B4","MED","Holdover formula ambiguous (200% applied to accrued arrears)",
  lambda t: bool(re.search(r'two hundred percent \(200%\) of the amount of \(a\)', t, re.I))),
 ("B5","MED","HVAC replacement responsibility never affirmatively allocated",
  lambda t: not re.search(r'responsible for replacement of the heating', t, re.I)),
 ("B6a","MED","CGL general aggregate limit not stated", lambda t: not re.search(r'general aggregate', t, re.I)),
 ("B6b","MED","Employer's Liability limit not stated", lambda t: not re.search(r"Employer.s Liability", t, re.I)),
 ("B6c","MED","No annual COI delivery obligation (certificates only pre-possession)",
  lambda t: not re.search(r'renewal certificates|annually during the Lease Term', t, re.I)),
 ("B8","MED","Water supplied 'at Tenant's expense' with no billing mechanism",
  lambda t: bool(re.search(r'water sufficient for drinking', t, re.I))
            and not re.search(r'flat rate of \$', t, re.I)),
 ("B11","MED","Guarantor/co-tenant mismatch: 'any guarantor' language with no guaranty and no co-tenant conform",
  lambda t: bool(re.search(r'any guarantor of this Lease', t, re.I))
            and not re.search(r'Guaranty of Lease|GUARANTY', t)
            and not re.search(r'any person or entity comprising Tenant', t, re.I)),
 ("C1","MED","No no-recording clause", lambda t: not re.search(r'shall not record this Lease', t, re.I)),
 ("C2","MED","No Landlord default notice-and-cure standard", lambda t: not re.search(r'Landlord shall not be in default', t, re.I)),
 ("C3","MED","No force majeure clause", lambda t: not re.search(r'force majeure', t, re.I)),
 ("C4","LOW","No OFAC / sanctions representation", lambda t: not re.search(r'Foreign Assets Control|OFAC', t, re.I)),
 ("C5","MED","No counterparts / electronic signature clause", lambda t: not re.search(r'counterpart', t, re.I)),
 ("C6","LOW","No 'time is of the essence' clause", lambda t: not re.search(r'[Tt]ime is of the essence', t)),
 ("C7","LOW","No personal property tax allocation to Tenant", lambda t: not re.search(r'taxes and assessments levied on Tenant', t, re.I)),
 ("C8","HIGH","No Exhibit A premises depiction / stipulated square footage",
  lambda t: not re.search(r'Exhibit A', t)),
 ("F1","LOW","'his agents' - Landlord is an LLC", lambda t: 'his agents, employees and invitees' in t),
 ("F2","LOW","'succeeding Lease or succeeding tenant'", lambda t: bool(re.search(r'succeeding Lease or succeeding tenant', t, re.I))),
 ("F3","LOW","'a comparable publications'", lambda t: 'a comparable publications' in t),
 ("F4","LOW","'Interior lighting' stray mid-sentence capital", lambda t: 'Interior lighting' in t),
 ("F5","LOW","'under seal' - Ohio abolished private seals", lambda t: bool(re.search(r'under seal', t, re.I))),
 ("F7","HIGH","Fragile numeric self-reference ('this Section N') — breaks when sections shift",
  lambda t: bool(re.search(r'this Section \d+', t))),
 ("F8","LOW","Default interest lacks usury savings clause (lesser-of max lawful rate)",
  lambda t: bool(re.search(r'eighteen percent \(18%\) per annum', t))
            and not re.search(r'maximum rate permitted by', t, re.I)),
 ("F9","LOW","Non-breaking-space artifacts in operative text",
  lambda t: '\xa0' in t),
 ("F6","LOW","Late fee runs on Business Days, cure on calendar days, and 'Business Day' is undefined",
  lambda t: bool(re.search(r'five \(5\) Business Days following the date when due', t, re.I))
            and not _defined(t, 'Business Days?')),
]

SEV_ORDER = {"BLOCK": 0, "HIGH": 1, "MED": 2, "LOW": 3}

def scan(path):
    t, (ins, dele, strike, cmt) = text_of(path)
    enc = ("OOXML tracked changes" if (ins or dele)
           else "compare-tool formatting (strikethrough)" if strike else "clean")
    print(f"\n{'='*78}\n{path}")
    print(f"  revision encoding: {enc}{'  + counsel comments present' if cmt else ''}")
    fails = [c for c in CHECKS if c[3](t)]
    for cid, sev, label, _ in sorted(CHECKS, key=lambda c: SEV_ORDER[c[1]]):
        st = "FAIL" if (cid, sev, label) in [(f[0], f[1], f[2]) for f in fails] else "pass"
        if st == "FAIL":
            print(f"  [{sev:<5}] {cid:<5} FAIL  {label}")
    n = {s: sum(1 for f in fails if f[1] == s) for s in SEV_ORDER}
    print(f"  ---- {len(fails)} of {len(CHECKS)} checks failed "
          f"(BLOCK {n['BLOCK']} / HIGH {n['HIGH']} / MED {n['MED']} / LOW {n['LOW']})")
    return len(fails)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(1 if sum(scan(p) for p in sys.argv[1:]) else 0)
