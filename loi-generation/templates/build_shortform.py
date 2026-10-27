"""Build templates/LOI_ShortForm_Template.docx (loi-generation v1.12 SHORT form).

Usage: python build_shortform.py <oxford-logo-512.png> <output.docx>   (requires python-docx and Pillow)
       python build_shortform.py --cropped <logo_full.png> <logo_mark.png> <output.docx>
         (reuse already-cropped logos, e.g. word/media/image1.png and image2.png unzipped from the current template)
Logo source: website-canonical/images/oxford-logo-512.png (also served at oxfordra.net/images/).
v1.13: SHORT is the only LOI format. Optional terms (Zoning, Purchase Option, Tenant Conditions) are paragraphs
whose body is a single {{..._TERM}} token — when the token resolves empty, delete that whole paragraph.
Layout follows the Lucern Capital Partners buy-side LOI adopted 2026-10-20; see references/short-form.md.
"""
import re, sys
from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement


import os, tempfile
from PIL import Image, ImageOps

D = tempfile.mkdtemp()
if sys.argv[1] == "--cropped":
    _full, _mark, OUT = sys.argv[2], sys.argv[3], sys.argv[4]
    Image.open(_full).convert("RGB").save(os.path.join(D, "logo_full.png"))
    Image.open(_mark).convert("RGB").save(os.path.join(D, "logo_mark.png"))
else:
    SRC, OUT = sys.argv[1], sys.argv[2]
    _im = Image.open(SRC).convert("RGB")
    _ink = ImageOps.invert(_im.convert("L")).point(lambda v: 255 if v > 20 else 0)
    _b = _ink.getbbox()  # full lockup
    _im.crop((_b[0] - 6, _b[1] - 6, _b[2] + 6, _b[3] + 6)).save(os.path.join(D, "logo_full.png"))
    _m = _ink.crop((0, 0, _im.width, int(_im.height * 0.53))).getbbox()  # block mark only (above wordmark)
    _im.crop((_m[0] - 4, _m[1] - 4, _m[2] + 4, _m[3] + 4)).save(os.path.join(D, "logo_mark.png"))
FONT = "Times New Roman"
GOLD = RGBColor(0xC9, 0xA9, 0x6E)
GREY = RGBColor(0x80, 0x80, 0x80)
LABEL_IN = 1.6

doc = Document()
st = doc.styles["Normal"]
st.font.name = FONT
st.font.size = Pt(11)
st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
st.paragraph_format.space_after = Pt(0)
st.paragraph_format.space_before = Pt(0)
st.paragraph_format.line_spacing = 1.0

sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
sec.left_margin = sec.right_margin = Inches(1.0)
sec.top_margin = Inches(1.2)
sec.bottom_margin = Inches(1.0)
sec.header_distance = Inches(0.28)
sec.footer_distance = Inches(0.45)
sec.different_first_page_header_footer = True

TOK = re.compile(r"(\{\{[A-Z0-9_]+\}\})")


def runs(p, text, bold=False, italic=False, underline=False, size=None, color=None):
    """Add text; any {{TOKEN}} renders gold DM Sans so loi-generation QC #1 can find it."""
    for part in TOK.split(text):
        if not part:
            continue
        r = p.add_run(part)
        r.bold, r.italic, r.underline = bold, italic, underline
        if size:
            r.font.size = Pt(size)
        if TOK.fullmatch(part):
            r.font.name = "DM Sans"
            r._element.rPr.rFonts.set(qn("w:hAnsi"), "DM Sans")
            r.font.color.rgb = GOLD
        elif color:
            r.font.color.rgb = color
    return p


def para(text="", after=0, align=None, **kw):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    if align is not None:
        p.alignment = align
    if text:
        runs(p, text, **kw)
    return p


def term(label, body, after=8):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.left_indent = Inches(LABEL_IN)
    pf.first_line_indent = Inches(-LABEL_IN)
    pf.tab_stops.add_tab_stop(Inches(LABEL_IN), WD_TAB_ALIGNMENT.LEFT)
    pf.space_after = Pt(after)
    pf.widow_control = True
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    runs(p, label + ":", underline=True)
    p.add_run("\t")
    runs(p, body)
    return p


def hyperlink(p, url, text, size, bold=False):
    part = p.part
    rid = part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
    h = OxmlElement("w:hyperlink")
    h.set(qn("r:id"), rid)
    r = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    for tag, val in (("w:rFonts", None), ("w:b", None), ("w:color", "0563C1"), ("w:u", "single"), ("w:sz", str(size * 2))):
        e = OxmlElement(tag)
        if tag == "w:rFonts":
            for a in ("w:ascii", "w:hAnsi", "w:cs"):
                e.set(qn(a), FONT)
        elif tag == "w:b":
            if not bold:
                continue
        else:
            e.set(qn("w:val"), val)
        rpr.append(e)
    r.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    r.append(t)
    h.append(r)
    p._p.append(h)


def build_footer(ftr):
    p = ftr.paragraphs[0]
    p.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT)
    sep = "  │  "
    for i, chunk in enumerate(["9510 Persimmon Tree Road, Suite 200", "Potomac, MD 20854", "301.512.6125"]):
        r = p.add_run(chunk + sep)
        r.bold = True
        r.font.size = Pt(9)
        r.font.color.rgb = GREY
    hyperlink(p, "https://www.oxfordra.net", "www.oxfordra.net", 9)
    p.add_run("\t").add_picture(f"{D}/logo_mark.png", height=Inches(0.22))


# headers: large logo on page 1, small logo thereafter (Lucern layout)
first = sec.first_page_header.paragraphs[0]
first.add_run().add_picture(f"{D}/logo_full.png", height=Inches(0.8))
other = sec.header.paragraphs[0]
other.add_run().add_picture(f"{D}/logo_full.png", height=Inches(0.45))
build_footer(sec.first_page_footer)
build_footer(sec.footer)

# ---- letter body -------------------------------------------------------
para("{{LOI_DATE}}")
para("{{SELLER_BROKER_FULL_NAME}}")
para("{{SELLER_BROKER_FIRM}}")
para("{{SELLER_BROKER_ADDRESS_1}}")
para("{{SELLER_BROKER_ADDRESS_2}}", after=14)

re_p = doc.add_paragraph()
re_p.paragraph_format.left_indent = Inches(0.75)
re_p.paragraph_format.first_line_indent = Inches(-0.75)
re_p.paragraph_format.tab_stops.add_tab_stop(Inches(0.75))
re_p.paragraph_format.space_after = Pt(11)
runs(re_p, "RE:\tAll-Cash Letter of Intent (“LOI”) to purchase {{PROPERTY_STREET_ADDRESS}}, {{PROPERTY_CITY}}, {{PROPERTY_STATE_FULL}} {{PROPERTY_ZIP}} (the “Property”)")

para("Dear {{SELLER_BROKER_SALUTATION}},", after=11)

J = WD_ALIGN_PARAGRAPH.JUSTIFY
para("Oxford Realty Advisors is a privately held, family-owned real estate investment firm founded in 2005. It owns "
     "and operates twenty-six properties, primarily shallow-bay industrial and flex, totaling more than 500,000 square "
     "feet in Maryland, Columbus, Ohio, and Kansas City, Missouri, with approximately 140 tenants. It invests only its "
     "own capital, with no outside investors, and closes all-cash.",
     after=9, align=J)

para("Oxford Realty Advisors, or its assigns (the “Buyer”), submits this all-cash, non-binding letter of intent (except as "
     "stated below) to purchase from {{SELLER_ENTITY_NAME}} (the "
     "“Seller”) the Property — a {{PROPERTY_TENANCY_PHRASE}} {{PROPERTY_USE_TYPE}} building of "
     "approximately {{PROPERTY_SF}} square feet on approximately {{PROPERTY_ACRES}} acres "
     "{{PROPERTY_ZONING_PHRASE}}{{TENANT_DISCLOSURE_PHRASE}} — on the general terms below.",
     after=9, align=J)

term("Purchase Price",
     "${{PURCHASE_PRICE_NUMERIC}}, all cash, paid to Seller in immediately available funds at Closing in exchange for "
     "free and clear title. Buyer’s obligation to close is not contingent on financing or appraisal.")

term("Deposit Terms",
     "${{EMD_NUMERIC}} initial earnest money will be deposited by Buyer with a title company of Buyer’s choosing "
     "within {{EMD_DUE_DAYS_WORDS}} business days after execution of a purchase and sale agreement (the “PSA”). "
     "The earnest money is fully refundable until expiration of the Due Diligence Period, nonrefundable thereafter "
     "(except for Seller default or failure of a Closing condition), and credited towards the Purchase Price at Closing.")

term("Due Diligence",
     "Upon execution of the PSA, Buyer will have {{STUDY_PERIOD_WORDS}} days (the “Due Diligence Period”) to "
     "inspect all aspects of the Property (including invasive testing) and may terminate for any reason with a full "
     "refund of the earnest money. If Buyer\u2019s Phase I identifies a recognized environmental condition or recommends "
     "further investigation, or Buyer elects a Phase II, the Due Diligence Period (and full refundability) extends "
     "until thirty (30) days after Buyer receives the Phase II results (or any voluntary action program "
     "determination). Within five (5) business days after "
     "acceptance of this LOI, Seller will deliver all title, survey, environmental, lease, operating, and "
     "physical-condition documents in its possession or control{{DD_DELIVERY_ADDITIONS}} and allow Buyer access to the Property.")

term("Zoning", "{{ZONING_TERM}}")

term("Closing",
     "{{CLOSING_DAYS_WORDS}} days after expiration of the Due Diligence Period. Seller will convey title by "
     "{{DEED_FORM}}, free and clear of all liens and encumbrances other than those Buyer approves in writing.")

term("Property Condition",
     "The Purchase Price assumes the Property is free of environmental, physical, and other material defects, "
     "including significant deferred maintenance{{KNOWN_CONDITION_CARVEOUT}}, and complies with current building and "
     "zoning codes. All fixtures, dock equipment, and other Seller-owned personal property at the Property convey to "
     "Buyer at no additional cost.")

term("Costs",
     "{{TRANSFER_TAX_SENTENCE}} Seller will pay for the owner\u2019s title policy and the release of any liens. Buyer "
     "will pay deed recording fees, title endorsements, any new survey, and all costs of its due diligence. "
     "Taxes, rents, and operating expenses will be prorated as of Closing by the method customary in "
     "{{PROPERTY_COUNTY}}, {{PROPERTY_STATE_FULL}}. Each party will pay its own attorney\u2019s fees. All other costs "
     "will be divided in accordance with local custom.")

term("Operations",
     "From acceptance through Closing, Seller will operate the Property in the ordinary course and will not enter into, amend, or "
     "terminate any lease or surviving service contract without Buyer’s written consent. "
     "{{OPERATIONS_CONDITIONAL_SENTENCE}}")

term("Purchase Option", "{{PURCHASE_OPTION_TERM}}")

term("Tenant Conditions", "{{TENANT_CONDITIONS_TERM}}")

term("Exclusivity",
     "From Seller’s acceptance of this LOI through the earlier of PSA execution or {{EXCLUSIVITY_DAYS_WORDS}} days after acceptance, Seller will not solicit, "
     "negotiate, or accept any other offer to purchase, lease, or recapitalize the Property, and will cease marketing "
     "the Property.")

term("Other Conditions",
     "Buyer will deliver a PSA draft within {{PSA_DRAFT_DAYS_WORDS}} days after acceptance, with customary "
     "representations, warranties, and a specific-performance remedy for Buyer. Buyer may "
     "assign to affiliates, and title may vest in Buyer-designated entities, with Seller cooperating in direct deeding "
     "at no added cost or delay to Seller.{{ENTITY_INTEREST_SENTENCE}} The parties will cooperate with any IRC \u00a71031 exchange at no cost to the "
     "cooperating party. Seller will pay any commission owed to {{SELLER_BROKER_FIRM}}; Buyer has no broker.")

term("Confidentiality",
     "Neither party will disclose the terms of this letter without the other\u2019s written consent, except to its "
     "principals, counsel, accountants, lenders, and exchange intermediaries{{CONFIDENTIALITY_TENANT_CARVEOUT}}, and as required by law.")

term("Offer & Acceptance",
     "If Seller agrees with these terms, please signify acceptance by countersigning in the space below. This offer "
     "will expire at 5:00 PM Eastern Time on {{OFFER_EXPIRATION_DATE}}. Neither party is obligated to buy or sell "
     "the Property until the PSA is executed, except that the Exclusivity and Confidentiality provisions are binding "
     "upon acceptance.", after=12).paragraph_format.keep_with_next = True

para("Regards,", after=10).paragraph_format.keep_with_next = True
para("Gabriel Goldberg").paragraph_format.keep_with_next = True
para("Authorized Representative").paragraph_format.keep_with_next = True
para("Oxford Realty Advisors", after=10).paragraph_format.keep_with_next = True

acc = para("Accepted, subject to the execution of a Purchase Agreement.", after=8)
acc.paragraph_format.left_indent = Inches(0.6)
acc.paragraph_format.keep_with_next = True  # acceptance stays with its signature lines
for left, right in (("By: _______________________", "Seller: {{SELLER_ENTITY_NAME}}"),
                    ("Title & Name: _______________", "Date: _______________________")):
    p = doc.add_paragraph()
    p.paragraph_format.left_indent = Inches(0.6)
    p.paragraph_format.tab_stops.add_tab_stop(Inches(3.2))
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True  # signature block travels with the last term and proof line
    runs(p, left + "\t" + right)

pf_line = para("Proof of funds available upon request.", align=WD_ALIGN_PARAGRAPH.CENTER, italic=True, color=GREY, size=9)
pf_line.paragraph_format.space_before = Pt(2)

doc.core_properties.title = "ORA Letter of Intent — Short Form Template"
doc.core_properties.author = "Oxford Realty Advisors"
doc.save(OUT)
print("saved", OUT)
