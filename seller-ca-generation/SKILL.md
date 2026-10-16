---
name: "seller-ca-generation"
description: "Use when ORA needs a confidentiality agreement / NDA / CA before sharing property information with a prospective buyer of ORA assets (disposition, seller-side). Fills the locked v1.0 template; counterparty block is the only variable."
---

# Seller-Side CA Generation (v1.0, ratified 2026-10-14)

ORA's standing seller-side Confidentiality Agreement. Origin: Lucern Capital Partners CA (10/14/2026), hardened after a three-reviewer premise check. **The clause text is locked.** The ONLY per-deal variables are the Recipient block: legal name, notice address, signatory name, signatory title.

## Scope
- Use for: a prospective buyer wants addresses, rent rolls, leases or financials on ORA-owned property.
- Not for: ORA as buyer (counterparty's CA governs; review via legal-intelligence), mutual NDAs, JV/lender NDAs, LOIs (loi-generation), PSAs (deal-execution).

## Procedure
1. **Collect the 4 variables** from the source of record, in order: counterparty's email signature/thread, their website (WebFetch the contact/footer for HQ address), HubSpot/Notion Broker Relationships. Never fabricate. If the legal entity suffix (LLC/LP/Inc.) is only inferred (e.g., LinkedIn slug), proceed but flag it and add a line asking the counterparty to confirm in the cover email.
2. **Confidential-deal check.** The CA names no properties by design (Properties are designated later by email). Do not add property names, addresses or LLC names to the CA or cover email.
3. **Write counterparty.json** in the working directory: `{"name":"…","address":"…","signatory":"…","title":"…"}`.
4. **Write the generator** below verbatim to `build_seller_ca.js` and run: `NODE_PATH=$(npm root -g) node build_seller_ca.js counterparty.json CA_[Counterparty-Name]_[MMDDYYYY].docx`. (`--template` instead of a JSON emits the blank template with highlighted placeholders.)
5. **Verify:** convert to PDF with LibreOffice (docx skill's soffice.py), `pdftoppm` the pages and view them; `pdftotext | grep -E '\[|___'` must return only the 3 footer initial lines. Expect 3 pages.
6. **Deliver** the .docx via SendUserFile to an /outputs/ folder; archive any prior version to /outputs/archive/ (never delete).
7. **Cover email** (draft only, never send; counterparty send needs Gabriel's in-turn confirmation): reply-all on the counterparty's thread, 3–4 lines: CA attached, countersign and return, addresses and initial information to follow, confirm exact legal entity name. Use ms365 reply-all draft if Mail.ReadWrite is granted; otherwise give the text to paste.

## Locked positions (do not change without Gabriel's ratification + version bump)
- Owner = Oxford Realty Advisors, LLC on behalf of affiliated property-owning entities; affiliates are intended third-party beneficiaries; authority rep.
- Effective Date = date of last signature. Properties = designated in writing incl. email.
- §3 Representatives directed + bound by duty; prospective equity partners (other than existing investors in Recipient-managed vehicles) need Owner's email consent.
- §4 no direct/indirect contact with tenants, PMs, employees, lenders, vendors, contractors; no entry; all requests to Gabriel Goldberg.
- §5 non-solicit of identified tenants regardless of use of Evaluation Material; carve-outs: general advertising, unsolicited tenant approach, documented pre-existing discussions.
- §11 term = later of 2 yrs from Effective Date or 2 yrs from last delivery; terminates per Property on acquisition.
- §12 Maryland law; exclusive venue Montgomery County MD state courts / D. Md.
- **Rejected (do not add if a reviewer or counterparty suggests them without Gabriel's approval):** residual-knowledge clause, trade-secret indefinite tail, post-term non-solicit tail, destruction-certificate exhibit, "subject to court discretion" softening of equitable relief, one-way fee shifting.

## Counterparty markup handling
Route any returned markup through external-review-premise-check against this locked list; concessions are Gabriel's call. Fallback if pushed on the equity-partner consent gate: permit disclosure to equity partners who agree in writing to keep the material confidential.

## Open item
Owner signatory title is "Principal"; Gabriel's email signature reads "Vice President, Acquisitions". Confirm with Gabriel and update the constant in `col('OWNER',…)` if changed (version bump).

## Generator (write verbatim)
```javascript
const fs=require('fs');
// ORA Seller-Side CA generator v1.0 — usage: node build_seller_ca.js counterparty.json [out.docx]
const arg=process.argv[2];
const C=(arg&&arg!=='--template')?JSON.parse(fs.readFileSync(arg,'utf8')):
 {name:'[Recipient Legal Name]',address:'[Recipient Address]',signatory:'[Signatory Name]',title:'[Signatory Title]'};
for(const k of ['name','address','signatory','title']) if(!C[k]) throw new Error('counterparty.json missing '+k);
const esc=v=>v.replace(/\*/g,'');
const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,WidthType,BorderStyle,AlignmentType,Footer,Header,PageNumber,TabStopType}=require('docx');
const NAVY='1B2A4A',GOLD='C9A96E',SERIF='EB Garamond',SANS='DM Sans';
function runs(t,base={}){
  const out=[];const re=/(\*\*[^*]+\*\*|\[[^\]]+\])/g;let i=0,m;
  while((m=re.exec(t))){ if(m.index>i)out.push(new TextRun({text:t.slice(i,m.index),font:SERIF,size:22,...base}));
    const s=m[0]; if(s.startsWith('**'))out.push(new TextRun({text:s.slice(2,-2),bold:true,font:SERIF,size:22,...base}));
    else out.push(new TextRun({text:s,font:SERIF,size:22,highlight:'yellow',...base}));
    i=m.index+s.length;}
  if(i<t.length)out.push(new TextRun({text:t.slice(i),font:SERIF,size:22,...base}));return out;}
const P=(t,o={})=>new Paragraph({children:runs(t),alignment:AlignmentType.JUSTIFIED,spacing:{after:140,line:276},...o});
const H=(t)=>new Paragraph({keepNext:true,spacing:{before:200,after:80},children:[new TextRun({text:t.toUpperCase(),font:SANS,size:19,bold:true,color:NAVY,characterSpacing:20})]});
const S=[
['1. Purpose',['Owner is willing to furnish Recipient with certain information concerning one or more real properties owned by Owner or its affiliates and identified by Owner to Recipient in writing, including by email, from time to time (each, a "**Property**") solely so that Recipient may evaluate a potential acquisition of one or more Properties (the "**Transaction**"), subject to the terms of this Agreement.']],
['2. Evaluation Material',['"**Evaluation Material**" means all information, in any form, furnished by or on behalf of Owner, including without limitation the identity and addresses of the Properties; leases, rent rolls, and tenant information; operating statements, budgets, and other financial data; physical, environmental, and title materials; and all notes, analyses, and other materials prepared by Recipient or its Representatives that contain or reflect such information. Evaluation Material also includes the fact that Owner is considering a sale and the existence and status of discussions between the parties.','Evaluation Material does not include information that (a) is or becomes generally available to the public other than through a breach of this Agreement; (b) was lawfully in Recipient\'s possession before disclosure by Owner, as shown by written records; (c) is independently developed by Recipient without use of Evaluation Material; or (d) is lawfully received from a third party not known by Recipient to be bound by a confidentiality obligation to Owner.']],
['3. Use and Nondisclosure',['Recipient shall use Evaluation Material solely to evaluate the Transaction and shall keep it strictly confidential. Recipient may disclose Evaluation Material only to its officers, members, employees, prospective lenders and equity partners, attorneys, accountants, and consultants who need to know it for that purpose and who are informed of its confidential nature, directed to keep it confidential, and bound by professional or contractual duties of confidentiality ("**Representatives**"); provided that disclosure to any prospective equity partner, other than an existing investor in a fund or vehicle managed by Recipient, requires Owner\'s prior written consent, which may be given by email. Recipient is responsible for any breach of this Agreement by its Representatives.']],
['4. No Contact; Site Access',['Without Owner\'s prior written consent, neither Recipient nor its Representatives shall, directly or indirectly (including through affiliates, agents, or other intermediaries), contact any tenant, property manager, employee, lender, vendor, or contractor of Owner or any Property regarding the Properties or the Transaction, or enter any Property. All communications, information requests, and requests for site visits shall be directed to Gabriel Goldberg (ggoldberg@oxfordra.net) or another person Owner designates in writing.']],
['5. Non-Solicitation of Tenants',['During the term of this Agreement, Recipient shall not, and shall cause its affiliates not to, directly or indirectly solicit or induce any tenant of a Property identified in the Evaluation Material to terminate, not renew, or relocate from its premises, or otherwise interfere with any lease at a Property, whether or not Evaluation Material is used in doing so. This Section does not restrict (a) general advertising or leasing activity not targeted at such tenants; (b) responding to a tenant that contacts Recipient without solicitation; or (c) continuing discussions with a tenant that, as shown by Recipient\'s written records, were underway before Owner identified that tenant to Recipient.']],
['6. Legally Required Disclosure',['If Recipient or any Representative is required by law, regulation, or legal process to disclose Evaluation Material, Recipient shall (to the extent legally permitted) give Owner prompt written notice so that Owner may seek a protective order, and shall disclose only the portion that counsel advises is legally required.']],
['7. Return or Destruction',['Within ten (10) business days after Owner\'s written request, or upon Recipient\'s decision not to pursue the Transaction, Recipient shall return or destroy all Evaluation Material and confirm in writing that it has done so. Copies retained under legal or regulatory requirements or in routine electronic backup systems remain subject to this Agreement for so long as they are retained.']],
['8. No Representations or Obligations',['Owner makes no representation or warranty, express or implied, as to the accuracy or completeness of any Evaluation Material, and neither Owner nor its affiliates shall have any liability arising from its use. Only those representations and warranties made in a definitive purchase and sale agreement, if and when executed, shall have legal effect. This Agreement is not an offer, and neither party is obligated to proceed with any Transaction unless and until a definitive written agreement is executed. Owner may furnish or withhold any information, conduct any sale process it chooses, negotiate with any party, and terminate discussions at any time, all without liability.']],
['9. Brokers',['Each party represents that it has not engaged any broker or finder in connection with the Transaction, other than any broker identified to the other party in writing. Each party shall be responsible for any commission or fee claimed by a broker or finder engaged by it.']],
['10. Remedies',['Recipient acknowledges that a breach of this Agreement may cause Owner irreparable harm for which monetary damages would be inadequate. Owner shall be entitled to injunctive relief and specific performance, without posting bond, in addition to any other remedy available at law or in equity. The prevailing party in any action to enforce this Agreement shall be entitled to recover its reasonable attorneys\' fees and costs.']],
['11. Term',['This Agreement shall remain in effect until the later of (a) two (2) years after the Effective Date and (b) two (2) years after Owner\'s last delivery of Evaluation Material to Recipient, except that it shall terminate as to any Property upon Recipient\'s acquisition of that Property under a definitive agreement.']],
['12. General',['This Agreement is governed by the laws of the State of Maryland, without regard to conflict-of-laws principles. Each party irrevocably submits to the exclusive jurisdiction of the state courts located in Montgomery County, Maryland and the United States District Court for the District of Maryland for any action arising out of or relating to this Agreement. This Agreement constitutes the entire agreement of the parties on its subject matter, may be amended or waived only in a writing signed by both parties, and may not be assigned by Recipient without Owner\'s prior written consent. No license or other right in Evaluation Material is granted except as expressly stated. This Agreement may be executed in counterparts and by electronic signature, each of which shall be deemed an original.']],
];
const body=[
 new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:120,after:60},children:[new TextRun({text:'Confidentiality Agreement',font:SERIF,size:36,color:NAVY})]}),
 new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:280},border:{bottom:{style:BorderStyle.SINGLE,size:6,color:GOLD,space:8}},children:[new TextRun({text:'PROPERTY INFORMATION  ·  PROSPECTIVE ACQUISITION',font:SANS,size:16,color:GOLD,characterSpacing:40})]}),
 P('This Confidentiality Agreement (this "**Agreement**") is entered into as of the date on which it has been signed by both parties, as shown below (the "**Effective Date**"), by and between **Oxford Realty Advisors, LLC**, on behalf of itself and its affiliated property-owning entities (collectively, "**Owner**"), with an address at 9510 Persimmon Tree Road, Potomac, Maryland 20854, and **'+esc(C.name)+'** ("**Recipient**"), with an address at '+esc(C.address)+'. Each property-owning affiliate of Oxford Realty Advisors, LLC is an intended third-party beneficiary of this Agreement entitled to enforce it, and Oxford Realty Advisors, LLC represents that it is authorized to enter into this Agreement on their behalf.'),
];
for(const [h,ps] of S){body.push(H(h));ps.forEach(t=>body.push(P(t)));}
body.push(new Paragraph({keepNext:true,spacing:{before:240,after:240},children:runs('**IN WITNESS WHEREOF**, the parties have executed this Agreement as of the Effective Date.')}));
const none={style:BorderStyle.NONE,size:0,color:'FFFFFF'};const nb={top:none,bottom:none,left:none,right:none};
const W=4680;
const cellP=(t,o={})=>new Paragraph({keepNext:true,spacing:{after:120},children:runs(t,o)});
const col=(party,entity,name,title)=>new TableCell({width:{size:W,type:WidthType.DXA},borders:nb,margins:{right:240},children:[
 new Paragraph({keepNext:true,spacing:{after:60},children:[new TextRun({text:party,font:SANS,size:18,bold:true,color:NAVY,characterSpacing:30})]}),
 cellP(entity,{bold:true}),
 new Paragraph({keepNext:true,spacing:{before:360,after:40},border:{bottom:{style:BorderStyle.SINGLE,size:4,color:'000000',space:1}},children:[new TextRun({text:'By:',font:SERIF,size:22})]}),
 cellP('Name: '+name),cellP('Title: '+title),
 new Paragraph({keepNext:true,spacing:{before:240,after:40},border:{bottom:{style:BorderStyle.SINGLE,size:4,color:'000000',space:1}},children:[new TextRun({text:'Date:',font:SERIF,size:22})]}),
]});
body.push(new Table({width:{size:9360,type:WidthType.DXA},columnWidths:[W,W],borders:{...nb,insideHorizontal:none,insideVertical:none},rows:[new TableRow({cantSplit:true,children:[
 col('OWNER','Oxford Realty Advisors, LLC','Gabriel Goldberg','Principal'),
 col('RECIPIENT',C.name,C.signatory,C.title)]})]}));
const doc=new Document({styles:{default:{document:{run:{font:SERIF,size:22}}}},sections:[{
 properties:{page:{size:{width:12240,height:15840},margin:{top:1296,bottom:1152,left:1440,right:1440}}},
 headers:{default:new Header({children:[new Paragraph({tabStops:[{type:TabStopType.RIGHT,position:9360}],children:[
  new TextRun({text:'OXFORD REALTY ADVISORS',font:SANS,size:16,bold:true,color:NAVY,characterSpacing:60}),
  new TextRun({text:'\tCONFIDENTIAL',font:SANS,size:14,color:GOLD,characterSpacing:40})]})]})},
 footers:{default:new Footer({children:[new Paragraph({tabStops:[{type:TabStopType.RIGHT,position:9360}],border:{top:{style:BorderStyle.SINGLE,size:4,color:GOLD,space:6}},children:[
  new TextRun({text:'Owner ______   Recipient ______',font:SANS,size:14,color:'6B6B6B'}),
  ...[['\tPage '],[PageNumber.CURRENT],[' of '],[PageNumber.TOTAL_PAGES]].map(c=>new TextRun({children:c,font:SANS,size:14,color:'6B6B6B'}))]})]})},
 children:body}]});
Packer.toBuffer(doc).then(b=>fs.writeFileSync(process.argv[3]||'ORA_Seller-CA_Template.docx',b));
```