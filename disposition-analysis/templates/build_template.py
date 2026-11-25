"""ORA Disposition Template builder (live formulas). Four paths: A1 hold, A2 hold+refi,
B seller-financed installment sale (two variants), C cash sale + 1031, D taxable cash sale (base).
Usage: python build_template.py OUT.xlsx   — then fill blue input cells on the Inputs sheet."""
import sys
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.workbook.defined_name import DefinedName
from openpyxl.utils import get_column_letter as L
NAVY='1B2A4A'; GOLD='C9A96E'; PARCH='F5F3EF'
HF=Font(name='DM Sans',bold=True,color='FFFFFF'); BF=Font(name='DM Sans',bold=True)
NF=Font(name='DM Sans'); INF=Font(name='IBM Plex Mono',color='0000FF')
HFILL=PatternFill('solid',fgColor=NAVY); IFILL=PatternFill('solid',fgColor='FFF7E0')
wb=Workbook(); ws=wb.active; ws.title='Inputs'
def title(s,t):
    s['A1']=t; s['A1'].font=Font(name='EB Garamond',bold=True,size=14,color=NAVY)
    s['A2']='OXFORD REALTY ADVISORS · Disposition Template v1.0 · blue = input, black = formula · [FORECAST] outputs'; s['A2'].font=Font(name='DM Sans',italic=True,size=9)
title(ws,'Inputs — Hold / Refi / Seller-Finance / 1031')
names={}
def inp(row,label,val,name,fmt=None,note=''):
    ws.cell(row,1,label).font=NF; c=ws.cell(row,2,val); c.font=INF; c.fill=IFILL
    if fmt: c.number_format=fmt
    ws.cell(row,4,note).font=Font(name='DM Sans',size=9,italic=True)
    wb.defined_names[name]=DefinedName(name,attr_text=f"Inputs!$B${row}"); names[name]=f'Inputs!$B${row}'
def sec(row,t):
    c=ws.cell(row,1,t); c.font=HF; c.fill=HFILL; ws.cell(row,2).fill=HFILL; ws.cell(row,4).fill=HFILL
r=4; sec(r,'PROPERTY & LEASE'); r+=1
D='$#,##0;($#,##0)'; P='0.00%'
spec=[
('Property name','55 New Plant Ct','PropName',None,'Text'),
('Rentable SF',34534,'SF','#,##0',''),
('Base rent year 1 (t=1)',466209,'Rent1',D,'Override the 10-yr schedule on Calc row 6 if the lease has fixed steps'),
('Rent growth / yr',0.025,'RentG',P,''),
('Abatement in year 1',77701.5,'Abate1',D,''),
('Management fee % of collected rent',0.03,'Mgmt',P,''),
('Insurance (landlord cost)',9075,'Ins',D,'[UNVERIFIED] until declarations are on file'),
('Other landlord-only costs',4000,'OtherLL',D,''),
('Reserve $/SF',0.25,'ResSF','$0.00',''),
('Tenant allowance, total',69068,'Allow',D,''),
('Allowance first year (t)',4,'AllowStart','0',''),
('Allowance last year (t)',6,'AllowEnd','0',''),
('Leasing commission at t0',128635,'Comm',D,'Amortized over 10 yrs on hold paths'),
]
for lab,v,n,f,note in spec: inp(r,lab,v,n,f,note); r+=1
r+=1; sec(r,'TAX (taxpayer who reports the gain)'); r+=1
spec=[
('Adjusted basis at t0',1000000,'Basis',D,'[DATA-GAP] until CPA basis package'),
('Accumulated depreciation in chain (for §1250)',500000,'AccDep',D,'Includes carryover from relinquished property'),
('Annual depreciation',14529,'Dep',D,'From latest Form 4562 / Sch E line 18'),
('Ordinary rate (fed + NIIT + state + local)',0.505,'ORD',P,''),
('LTCG rate (fed + NIIT + state + surtax)',0.355,'LTCG',P,''),
('Unrecaptured §1250 rate',0.405,'R1250',P,''),
('§1245 recapture (cost-seg personal property)',0,'S1245',D,'Taxed at ORD in year of sale'),
]
for lab,v,n,f,note in spec: inp(r,lab,v,n,f,note); r+=1
r+=1; sec(r,'VALUATION & CAPITAL MARKETS'); r+=1
spec=[
('Cap rate (sale today and exit)',0.0725,'Cap',P,'Cite market source + date'),
('Selling costs %',0.02,'SellC',P,'Add any broker tail (e.g., JLL 2%) here'),
('Reinvestment rate on cash, pre-tax',0.05,'Reinv',P,'Taxed at ORD'),
('Refi LTV max',0.65,'LTV',P,''),
('Refi DSCR min',1.25,'DSCR','0.00"x"',''),
('Refi rate',0.07,'RefiR',P,'10-yr UST + 200 bps'),
('Refi amortization (yrs)',25,'RefiAm','0',''),
('Refi cost % of loan',0.01,'RefiC',P,''),
('Market loan rate for cash-equivalent value',0.07,'MktR',P,''),
('§453A threshold',5000000,'T453',D,''),
('§453A underpayment rate',0.07,'U453',P,''),
]
for lab,v,n,f,note in spec: inp(r,lab,v,n,f,note); r+=1
r+=1; sec(r,'SELLER-FINANCE VARIANTS'); ws.cell(r,2,'B1').font=HF; ws.cell(r,3,'B2').font=HF; ws.cell(r,3).fill=HFILL; r+=1
for lab,v1,v2,n,f in [('Price',7500000,7500000,'BPrice',D),('Down payment',1500000,2500000,'BDown',D),('Note rate (≥ AFR)',0.05,0.05,'BRate',P),('Amortization (yrs)',25,25,'BAm','0'),('Term to balloon (yrs, ≤10)',5,7,'BTerm','0'),('Selling costs %',0.02,0.02,'BSell',P)]:
    ws.cell(r,1,lab).font=NF
    for j,v in ((2,v1),(3,v2)):
        c=ws.cell(r,j,v); c.font=INF; c.fill=IFILL; c.number_format=f
    wb.defined_names[n+'1']=DefinedName(n+'1',attr_text=f"Inputs!$B${r}"); wb.defined_names[n+'2']=DefinedName(n+'2',attr_text=f"Inputs!$C${r}")
    r+=1
r+=1; sec(r,'1031 REPLACEMENT'); r+=1
for lab,v,n,f,note in [('Replacement cap rate',0.0825,'RCap',P,'Must be a screened, verified target'),('Replacement NOI growth',0.025,'RG',P,''),('Acquisition cost %',0.015,'RAcq',P,''),('Idle months before income',3,'RIdle','0',''),('Exit cost %',0.03,'RExit',P,'')]:
    inp(r,lab,v,n,f,note); r+=1
ws.column_dimensions['A'].width=44; ws.column_dimensions['B'].width=16; ws.column_dimensions['C'].width=16; ws.column_dimensions['D'].width=60

# ---------------- Calc sheet
c=wb.create_sheet('Calc'); title(c,'Annual model (years 1-10 after t0)')
Y0=3; # column C = t0, D..M = t1..t10
c.cell(4,1,'Year (t)').font=BF
for t in range(0,11):
    col=L(3+t); c[f'{col}4']=t; c[f'{col}4'].font=HF; c[f'{col}4'].fill=HFILL
row={}
def R(key,label,fn,bold=False,fmt=D,t0=None):
    rr=len(row)+5; row[key]=rr; c.cell(rr,1,label).font=BF if bold else NF
    if t0 is not None: c[f'C{rr}']=t0; c[f'C{rr}'].number_format=fmt
    for t in range(1,11):
        col=L(3+t); prev=L(2+t)
        c[f'{col}{rr}']=fn(t,col,prev); c[f'{col}{rr}'].number_format=fmt
    return rr
g=lambda k,col: f'{col}{row[k]}'
R('rent','Base rent',lambda t,col,prev: '=Rent1' if t==1 else f'={prev}{row["rent"]}*(1+RentG)')
R('ab','Abatement',lambda t,col,prev: '=-Abate1' if t==1 else '=0')
R('coll','Collected rent',lambda t,col,prev: f'={g("rent",col)}+{g("ab",col)}')
R('noi','Owner NOI (after mgmt, ins, other, reserve)',lambda t,col,prev: f'={g("coll",col)}*(1-Mgmt)-Ins-OtherLL-ResSF*SF',True)
R('alw','Tenant allowance',lambda t,col,prev: f'=IF(AND({col}$4>=AllowStart,{col}$4<=AllowEnd),Allow/(AllowEnd-AllowStart+1),0)')
c.cell(len(row)+5,1,'— A1 HOLD, NO DEBT —').font=BF; row['_a1']=len(row)+5
R('a1tax','A1 tax',lambda t,col,prev: f'=({g("noi",col)}-Dep-Comm/10)*ORD')
R('a1cf','A1 after-tax cash',lambda t,col,prev: f'={g("noi",col)}-{g("alw",col)}-{g("a1tax",col)}',True,t0='=-Comm')
c.cell(len(row)+5,1,'— A2 HOLD + REFI —').font=BF; row['_a2']=len(row)+5
R('int','A2 interest',lambda t,col,prev: f'=-CUMIPMT(RefiR/12,RefiAm*12,Loan,({col}$4-1)*12+1,{col}$4*12,0)')
R('bal','A2 loan balance EOY',lambda t,col,prev: f'=Loan+CUMPRINC(RefiR/12,RefiAm*12,Loan,1,{col}$4*12,0)')
R('a2tax','A2 tax',lambda t,col,prev: f'=({g("noi",col)}-{g("int",col)}-Dep-Comm/10-Loan*RefiC/10)*ORD')
R('a2cf','A2 after-tax cash',lambda t,col,prev: f'={g("noi",col)}-DS-{g("alw",col)}-{g("a2tax",col)}',True,t0='=-Comm+Loan*(1-RefiC)')
for v in (1,2):
    c.cell(len(row)+5,1,f'— B{v} SELLER-FINANCED SALE —').font=BF; row[f'_b{v}']=len(row)+5
    R(f'b{v}pr',f'B{v} principal received',lambda t,col,prev,v=v: f'=IF({col}$4<BTerm{v},-CUMPRINC(BRate{v}/12,BAm{v}*12,BPrice{v}-BDown{v},({col}$4-1)*12+1,{col}$4*12,0),IF({col}$4=BTerm{v},BPrice{v}-BDown{v}+CUMPRINC(BRate{v}/12,BAm{v}*12,BPrice{v}-BDown{v},1,({col}$4-1)*12,0)*({col}$4>1),0))',t0=f'=BDown{v}')
    R(f'b{v}int',f'B{v} interest received',lambda t,col,prev,v=v: f'=IF({col}$4<=BTerm{v},-CUMIPMT(BRate{v}/12,BAm{v}*12,BPrice{v}-BDown{v},({col}$4-1)*12+1,{col}$4*12,0),0)')
    R(f'b{v}cg',f'B{v} cumulative gain recognized',lambda t,col,prev,v=v: f'={prev}{row[f"b{v}cg"]}+{g(f"b{v}pr",col)}*GP{v}',t0=f'=C{row[f"b{v}pr"]}*GP{v}')
    R(f'b{v}c1250',f'B{v} cumulative §1250 recognized',lambda t,col,prev,v=v: f'=MIN({g(f"b{v}cg",col)},S1250AMT{v})',t0=f'=MIN(C{row[f"b{v}cg"]},S1250AMT{v})')
    R(f'b{v}tax',f'B{v} tax on gain',lambda t,col,prev,v=v: f'=({g(f"b{v}c1250",col)}-{prev}{row[f"b{v}c1250"]})*R1250+(({g(f"b{v}cg",col)}-{g(f"b{v}c1250",col)})-({prev}{row[f"b{v}cg"]}-{prev}{row[f"b{v}c1250"]}))*LTCG',t0=f'=C{row[f"b{v}c1250"]}*R1250+(C{row[f"b{v}cg"]}-C{row[f"b{v}c1250"]})*LTCG+S1245*ORD')
    R(f'b{v}453',f'B{v} §453A interest charge',lambda t,col,prev,v=v: f'=IF({col}$4<=BTerm{v},(BTotTax{v}-SUM($C{row[f"b{v}tax"]}:{prev}{row[f"b{v}tax"]}))*MAX(0,(BPrice{v}-BDown{v}-T453)/(BPrice{v}-BDown{v}))*U453,0)')
    R(f'b{v}cf',f'B{v} after-tax cash',lambda t,col,prev,v=v: f'={g(f"b{v}pr",col)}+{g(f"b{v}int",col)}*(1-ORD)-{g(f"b{v}tax",col)}-{g(f"b{v}453",col)}',True,t0=f'=BDown{v}-BPrice{v}*BSell{v}-Comm-C{row[f"b{v}tax"]}')
c.cell(len(row)+5,1,'— C CASH SALE + 1031 —').font=BF; row['_c']=len(row)+5
R('cnoi','C replacement NOI',lambda t,col,prev: f'=RPrice*RCap*(1+RG)^({col}$4-1)*IF({col}$4=1,1-RIdle/12,1)')
R('ctax','C tax',lambda t,col,prev: f'=({g("cnoi",col)}-Dep-RPrice*RAcq/39)*ORD')
R('ccf','C after-tax cash',lambda t,col,prev: f'={g("cnoi",col)}-{g("ctax",col)}',True,t0='=0')
c.column_dimensions['A'].width=42
for t in range(11): c.column_dimensions[L(3+t)].width=13
c.freeze_panes='C5'

# ---------------- Derived scalars on Summary
s=wb.create_sheet('Summary',0); title(s,'Summary — after-tax comparison')
scal=[
('Buyer NOI yr 1 (rent − other − reserve)','=Rent1-OtherLL-ResSF*SF','BuyerNOI'),
('Value today (buyer NOI / cap)','=BuyerNOI/Cap','V0'),
('Refi loan = MIN(LTV, DSCR) sizing','=MIN(LTV*V0,(BuyerNOI/DSCR)/(-PMT(RefiR/12,RefiAm*12,1)*12))','Loan'),
('Refi annual debt service','=-PMT(RefiR/12,RefiAm*12,Loan)*12','DS'),
('Exit value yr 10 (yr-11 buyer NOI / cap)','=(Calc!M%d*(1+RentG)-OtherLL-ResSF*SF)/Cap'%row['rent'],'TV'),
('D: taxable cash sale, amount realized','=V0*(1-SellC)-Comm','D_AR'),
('D: tax on sale','=MIN(MAX(D_AR-Basis,0),AccDep)*R1250+(MAX(D_AR-Basis,0)-MIN(MAX(D_AR-Basis,0),AccDep))*LTCG+S1245*ORD','D_Tax'),
('D: after-tax proceeds today (IRR investment base)','=D_AR-D_Tax','D0'),
('After-tax reinvestment rate','=Reinv*(1-ORD)','RA'),
('Hold: basis at yr 10','=Basis-10*Dep+Allow','Basis10'),
('Hold: liquidation tax at yr 10','=MIN(MAX(TV*(1-SellC)-Basis10,0),AccDep+10*Dep)*R1250+(MAX(TV*(1-SellC)-Basis10,0)-MIN(MAX(TV*(1-SellC)-Basis10,0),AccDep+10*Dep))*LTCG','HoldTax10'),
('C: exchange proceeds to QI','=D_AR','CExch'),
('C: replacement price','=CExch/(1+RAcq)','RPrice'),
('C: exit equity yr 10','=RPrice*(1+RG)^10*(1-RExit)','CEq'),
('C: liquidation tax yr 10','=MIN(MAX(CEq-(Basis+RPrice*RAcq-10*Dep),0),AccDep+10*Dep)*R1250+(MAX(CEq-(Basis+RPrice*RAcq-10*Dep),0)-MIN(MAX(CEq-(Basis+RPrice*RAcq-10*Dep),0),AccDep+10*Dep))*LTCG','CTax10'),
]
for v in (1,2):
    scal+= [(f'B{v}: total gain','=BPrice%d*(1-BSell%d)-Comm-Basis'%(v,v),f'BGain{v}'),
            (f'B{v}: gross-profit ratio',f'=BGain{v}/BPrice{v}',f'GP{v}'),
            (f'B{v}: §1250 portion of gain',f'=MIN(BGain{v},AccDep)',f'S1250AMT{v}'),
            (f'B{v}: total tax on gain',f'=S1250AMT{v}*R1250+(BGain{v}-S1250AMT{v})*LTCG',f'BTotTax{v}'),
            (f'B{v}: note',f'=BPrice{v}-BDown{v}',f'BNote{v}'),
            (f'B{v}: note ÷ value today',f'=BNote{v}/V0',f'BNoteLTV{v}'),
            (f'B{v}: cash-equivalent value @ market rate',f'=BDown{v}-PV(MktR/12,BTerm{v}*12,PMT(BRate{v}/12,BAm{v}*12,-BNote{v}))+(BNote{v}+CUMPRINC(BRate{v}/12,BAm{v}*12,BNote{v},1,BTerm{v}*12,0))/(1+MktR/12)^(BTerm{v}*12)',f'BCEV{v}'),
            (f'B{v}: balloon balance',f'=BNote{v}+CUMPRINC(BRate{v}/12,BAm{v}*12,BNote{v},1,BTerm{v}*12,0)',f'BBalloon{v}')]
rr=4; s.cell(rr,1,'Key derived values').font=HF; s.cell(rr,1).fill=HFILL; s.cell(rr,2).fill=HFILL; rr+=1
for lab,f,n in scal:
    s.cell(rr,1,lab).font=NF; s.cell(rr,2,f).number_format=P if ('ratio' in lab or 'rate' in lab or '÷' in lab) else D
    wb.defined_names[n]=DefinedName(n,attr_text=f"Summary!$B${rr}"); rr+=1
rr+=1
hdr=['Path','After-tax cash t0','Yr-1 after-tax','Sum yrs 1-10','2037 wealth: liquidate','2037 wealth: step-up','IRR vs taxable-sale base']
for j,h in enumerate(hdr): x=s.cell(rr,1+j,h); x.font=HF; x.fill=HFILL
rr+=1
def fvexpr(k): return f"SUMPRODUCT(Calc!D{row[k]}:M{row[k]},(1+RA)^(10-Calc!D4:M4))+Calc!C{row[k]}*(1+RA)^10"
paths=[('A1 Hold, no debt','a1cf','+TV*(1-SellC)-HoldTax10','+TV*(1-SellC)'),
       ('A2 Hold + refi','a2cf','+TV*(1-SellC)-Calc!M%d-HoldTax10'%row['bal'],'+TV*(1-SellC)-Calc!M%d'%row['bal']),
       ('B1 Seller-financed','b1cf','',''),('B2 Seller-financed','b2cf','',''),
       ('C Cash sale + 1031','ccf','+CEq-CTax10','+CEq')]
irr_row=rr+8
for i,(lab,k,liq,step) in enumerate(paths):
    s.cell(rr,1,lab).font=BF
    s.cell(rr,2,f'=Calc!C{row[k]}'); s.cell(rr,3,f'=Calc!D{row[k]}'); s.cell(rr,4,f'=SUM(Calc!D{row[k]}:M{row[k]})')
    s.cell(rr,5,f'={fvexpr(k)}{liq}'); s.cell(rr,6,f'={fvexpr(k)}{step}')
    # IRR flow helper rows on Calc bottom
    fr=60+i; c.cell(fr,1,f'IRR flows {lab}').font=NF
    c.cell(fr,3,f'=-D0+C{row[k]}')
    for t in range(1,11):
        col=L(3+t); extra = liq.replace('+','+',1) if t==10 else ''
        c[f'{col}{fr}']=f'={col}{row[k]}'+(extra if t==10 else '')
    s.cell(rr,7,f'=IRR(Calc!C{fr}:M{fr})')
    for j in range(2,7): s.cell(rr,j).number_format=D
    s.cell(rr,7).number_format=P; rr+=1
s.cell(rr,1,'D Taxable cash sale today').font=BF; s.cell(rr,2,'=D0'); s.cell(rr,5,'=D0*(1+RA)^10'); s.cell(rr,6,'=D0*(1+RA)^10')
for j in (2,5,6): s.cell(rr,j).number_format=D
rr+=2
for t in ['Read wealth columns first: IRR ignores what early cash earns. Step-up column applies only if the asset is includible in the decedent\'s estate (check grantor-trust status; Rev. Rul. 2023-2). Installment notes get no step-up (IRD, §691).',
          'Seller-finance: note is boot and cannot be exchanged; rate must be ≥ AFR; check balloon refinanceability (balloon ÷ 65% of then value) and §453A if note > threshold.',
          'Every input needs a source and date. Missing inputs are [DATA-GAP], not guesses.']:
    s.cell(rr,1,t).font=Font(name='DM Sans',size=9,italic=True); rr+=1
s.column_dimensions['A'].width=46
for j in range(2,8): s.column_dimensions[L(j)].width=20
wb.save(sys.argv[1] if len(sys.argv)>1 else 'ORA_Disposition_Template_v1.0.xlsx')
