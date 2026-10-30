"""Automated SHORT-form QC for a filled LOI PDF (loi-generation v1.15; references/short-form.md).

Usage: python qc_shortform.py <loi.pdf> <values.json>
Exit 0 = every automated check passes. Judgment items (walk price #23, zoning verbatim #19,
conditional-term correctness #2) stay manual. Needs poppler-utils (pdftotext, pdfinfo, pdffonts).
"""
import json, re, subprocess, sys

pdf, V = sys.argv[1], json.load(open(sys.argv[2], encoding="utf-8"))
sh = lambda *a: subprocess.run(a, capture_output=True, text=True, check=True).stdout
flat = re.sub(r"\s+", " ", sh("pdftotext", "-layout", pdf, "-"))
pages = int(re.search(r"Pages:\s+(\d+)", sh("pdfinfo", pdf)).group(1))
fonts = sh("pdffonts", pdf)

ORDER = ["Purchase Price", "Deposit Terms", "Due Diligence", "Zoning", "Closing", "Property Condition", "Costs",
         "Operations", "Purchase Option", "Tenant Conditions", "Exclusivity", "Other Conditions", "Confidentiality",
         "Offer & Acceptance"]
OPTIONAL = {"Zoning": "ZONING_TERM", "Purchase Option": "PURCHASE_OPTION_TERM", "Tenant Conditions": "TENANT_CONDITIONS_TERM"}
expected = [l for l in ORDER if l not in OPTIONAL or V.get(OPTIONAL[l], "").strip()]
pos = [flat.find(l + ":") for l in expected]
max_pages = 3 if any(V.get(t, "").strip() for t in OPTIONAL.values()) else 2
BANNED = ["I hope this finds you well", "Just following up", "As discussed", "FYI", "Going forward",
          "At your earliest convenience", "Hopefully", "I think we should", "Quick question", "Sorry for the delay",
          "Notwithstanding the foregoing", "Pursuant to", "hereunder", "hereof", "thereof", "thereunto"]
checks = {
    "#1 no unresolved tokens": "{{" not in flat,
    "#4 labeled terms present and in fixed order": all(p >= 0 for p in pos) and pos == sorted(pos)
        and all(flat.find(l + ":") < 0 for l in OPTIONAL if l not in expected),
    "#5 no legacy format pages or markers": not re.search(r"EXECUTION PAGE|BUYER INFORMATION|PORTFOLIO OVERVIEW|"
        r"TEMPLATE METADATA|APPENDIX|CONDITIONAL|INDUSTRIAL · INVESTMENT", flat),
    "#9 phone 301.512.6125 once per page; never 301.983.8000": flat.count("301.512.6125") == pages and "301.983.8000" not in flat,
    "#10 address footer on every page": flat.count("9510 Persimmon Tree Road, Suite 200") == pages and "www.oxfordra.net" in flat,
    "#11 proof-of-funds line exactly once": flat.count("Proof of funds available upon request.") == 1,
    "#12 credentials canon; no value, leverage, or closed-all claim": "approximately 140 tenants" in flat
        and "family-owned" in flat and not re.search(r"portfolio value|aggregate (portfolio )?value|\$\d+(\.\d+)? ?(million|M)\b|"
        r"loan-to-value|\bLTV\b|closed (substantially )?all", flat, re.I),
    "#14 acceptance block with seller entity": "Accepted, subject to the execution of a Purchase Agreement." in flat
        and ("Seller: " + V["SELLER_ENTITY_NAME"]) in flat and "Gabriel Goldberg Authorized Representative" in flat,
    "#15 strike list clean": not re.search(r"\bshall\b", flat, re.I) and not any(b.lower() in flat.lower() for b in BANNED),
    "#16 extractable serif text (soffice export)": len(flat) > 1500 and bool(re.search(r"Times|LiberationSerif", fonts)),
    f"#17 page count within limit (≤{max_pages})": 2 <= pages <= max_pages,
    "#21 deposit window stated once": flat.count("business days after execution of a purchase and sale agreement") == 1
        and (V["EMD_DUE_DAYS_WORDS"] + " business days after execution") in flat,
}
for k, v in checks.items():
    print(("PASS " if v else "FAIL ") + k)
print(f"pages={pages}")
sys.exit(0 if all(checks.values()) else 1)
