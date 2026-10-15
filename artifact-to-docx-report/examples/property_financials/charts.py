import sys,os,json,collections
sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),'..','..','lib'))
from ora_chart_style import *
DATA,OUT=sys.argv[1],sys.argv[2].rstrip('/')+'/'
os.makedirs(OUT,exist_ok=True)
d=json.load(open(DATA))
P=d['props']
save=make_save(OUT)
short={'1100 Rarig':'1100 Rarig','1900 Broadway':'1900 Broadway','29000 Info Lane':'29000 Info Lane','3034 Westerville':'3034 Westerville','3540 E 5th':'3540 E 5th','3883 Livingston':'3883 Livingston','9050 Red Branch':'9050 Red Branch','9620 State 350':'9620 State 350','FVC':'FVC (Sepich)','55 New Plant (EGFLLC)':'55 New Plant','1851 South Club Solar':'Club Solar (MD)','2203-2207 Northwood':'2203-07 Northwood'}
stats={}
# c1 NOI FY2025
rows=[(short[n],P[n]['periods']['FY2025']['noi'],P[n]['periods']['FY2025']['noi_margin'],P[n]['periods']['FY2025']['revenue']) for n in P]
rows.sort(key=lambda r:r[1])
tot_rev=sum(r[3] for r in rows); tot_noi=sum(r[1] for r in rows)
stats['fy25']={'rev':tot_rev,'noi':tot_noi,'n':len(rows)}
fig,ax=plt.subplots(figsize=(6.6,3.9))
cols=[GOLD if r[0] in('Club Solar (MD)',) else NAVY for r in rows]
ax.barh([r[0] for r in rows],[r[1] for r in rows],color=cols,height=.62)
for i,r in enumerate(rows): ax.text(r[1]+8000,i,f"{k(r[1])}  ·  {r[2]*100:.0f}% margin",va='center',fontsize=8)
ax.set_xlim(0,max(r[1] for r in rows)*1.38); ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f"${v/1000:,.0f}K"))
ax.set_title('FY2025 normalized NOI by asset',loc='left'); ax.grid(axis='x',color='#EEE'); ax.set_axisbelow(True)
save(fig,'c1_noi.png')
# TTM26 stats (11 entities, ex 55 New Plant)
ttm=[(n,P[n]['periods']['TTM26']) for n in P if 'TTM26' in P[n]['periods']]
stats['ttm26']={'rev':sum(x['revenue'] for _,x in ttm),'noi':sum(x['noi'] for _,x in ttm),'n':len(ttm),'capex':sum(x['capex'] for _,x in ttm)}
# c2 waterfall same-store FY25 vs FY24
v=d['portfolio']['same_store_FY2025_vs_FY2024']['view']
br=v['base_rent']['current']-v['base_rent']['prior']; rb=v['reimbursements']['current']-v['reimbursements']['prior']
rv=v['revenue']['current']-v['revenue']['prior']; oth=rv-br-rb; ox=-(v['opex']['current']-v['opex']['prior'])
steps=[('FY2024\nNOI',v['noi']['prior'],'t'),('Base\nrent',br,'d'),('Reimburse-\nments',rb,'d'),('Energy, other\n& waivers',oth,'d'),('Operating\nexpense',ox,'d'),('FY2025\nNOI',v['noi']['current'],'t')]
fig,ax=plt.subplots(figsize=(6.6,3.4)); run=0
for i,(l,val,t) in enumerate(steps):
    if t=='t': ax.bar(i,val,color=NAVY,width=.6); run=val; ax.text(i,val+40000,k(val),ha='center',fontsize=8.5,fontweight='bold'); 
    else:
        ax.bar(i,val,bottom=run if val>=0 else run+val,color=GREEN if val>=0 else RED,width=.6)
        ax.text(i,(run+val if val>=0 else run)+40000,('+' if val>=0 else '−')+k(abs(val)),ha='center',fontsize=8.5); run+=val
ax.set_xticks(range(len(steps))); ax.set_xticklabels([s[0] for s in steps],fontsize=8); ax.set_ylim(3.4e6,4.35e6)
ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f"${v/1e6:.1f}M")); ax.set_title('Same-store NOI bridge, FY2024 to FY2025 (8 assets)',loc='left'); ax.grid(axis='y',color='#EEE'); ax.set_axisbelow(True)
save(fig,'c2_bridge.png'); stats['bridge']={'br':br,'rb':rb,'oth':oth,'ox':ox}
# c3 opex category delta
ob=v['opex_by']; items=sorted([(c,x['current']-x['prior'],x['pct']) for c,x in ob.items()],key=lambda t:t[1])
fig,ax=plt.subplots(figsize=(6.6,3.3))
ax.barh([i[0] for i in items],[i[1] for i in items],color=[GREEN if i[1]<0 else RED for i in items],height=.6)
for j,i in enumerate(items):
    lab=f"{'+' if i[1]>=0 else '−'}{k(abs(i[1]))} ({i[2]*100:+.0f}%)" if abs(i[2])<5 else f"+{k(i[1])} (x{1+i[2]:.1f})"
    ax.text(i[1]+(1500 if i[1]>=0 else -1500),j,lab,va='center',ha='left' if i[1]>=0 else 'right',fontsize=8)
ax.axvline(0,color='#555',lw=.8); ax.set_xlim(-48000,60000); ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f"${v/1000:,.0f}K"))
ax.set_title('Same-store operating expense change by category, FY2025 vs FY2024',loc='left'); ax.grid(axis='x',color='#EEE'); ax.set_axisbelow(True)
save(fig,'c3_opex.png')
# c4 recovery ratio TTM26
rec=[(short[n],P[n]['periods']['TTM26']['recovery_ratio']) for n in P if 'TTM26' in P[n]['periods'] and n!='1851 South Club Solar']
rec.sort(key=lambda r:r[1])
fig,ax=plt.subplots(figsize=(6.6,3.5))
ax.barh([r[0] for r in rec],[r[1]*100 for r in rec],color=[RED if r[1]<.3 else (GOLD if r[1]<.9 else NAVY) for r in rec],height=.6)
for i,r in enumerate(rec): ax.text(r[1]*100+2,i,f"{r[1]*100:.0f}%",va='center',fontsize=8.5)
ax.axvline(100,color='#555',ls='--',lw=.8); ax.text(101,-.9,'100% = full pass-through',fontsize=7.5,color='#555')
ax.set_xlim(0,200); ax.set_title('Expense recovery ratio, TTM to Sep 2026 (reimbursements ÷ recoverable pool)',loc='left',fontsize=10); ax.grid(axis='x',color='#EEE'); ax.set_axisbelow(True)
save(fig,'c4_recovery.png'); stats['rec']=rec
# c5 occupancy
S=d['sf']; occ=[(short[n],S[n]['occ'],S[n]['sf']-(S[n].get('common_area_sf') or (400 if n=='2203-2207 Northwood' else 0)),S[n]['leased_sf']) for n in S if S[n].get('occ') is not None]
occ.sort(key=lambda r:r[1]); tsf=sum(o[2] for o in occ); tl=sum(o[3] for o in occ)
stats['occ']={'sf':tsf,'leased':tl,'pct':tl/tsf}
fig,ax=plt.subplots(figsize=(6.6,3.6))
ax.barh([o[0] for o in occ],[o[1]*100 for o in occ],color=[RED if o[1]<.9 else (GOLD if o[1]<.97 else NAVY) for o in occ],height=.6)
for i,o in enumerate(occ): ax.text(o[1]*100+.8,i,f"{o[1]*100:.1f}%  ({o[2]-o[3]:,.0f} SF vacant of {o[2]:,.0f} leasable)",va='center',fontsize=8)
ax.axvline(stats['occ']['pct']*100,color='#555',ls='--',lw=.8); ax.text(stats['occ']['pct']*100-.5,len(occ)-.35,f"Portfolio {stats['occ']['pct']*100:.1f}%",ha='right',fontsize=8,color='#555')
ax.set_xlim(60,125); ax.set_xticks([60,70,80,90,100]); ax.set_title('Occupancy by asset (leased SF ÷ total SF, rent roll 2 Oct 2026)',loc='left',fontsize=10)
save(fig,'c5_occ.png')
# c6 expiry ladder
T=d['xt']['tenants']; oc=[t for t in T if t['oc'].startswith('Occupied')]
b=collections.OrderedDict([('2026 &\nprior',[0,0,0]),('2027',[0,0,0]),('2028',[0,0,0]),('2029',[0,0,0]),('2030',[0,0,0]),('2031',[0,0,0]),('2033',[0,0,0]),('MTM/\nother',[0,0,0])])
for t in oc:
    y=(t['le'] or '')[:4]
    key='MTM/\nother' if (not y or y=='2045' or t['oc'].endswith('month-to-month')) else ('2026 &\nprior' if y<='2026' else y)
    if key not in b: key='MTM/\nother'
    b[key][0]+=1; b[key][1]+=t['sf'] or 0; b[key][2]+=(t['mr'] or 0)*12
tot_rent=sum(x[2] for x in b.values()); stats['roll']={k_.replace('\n',' '):x for k_,x in b.items()}; stats['roll_tot']=tot_rent
fig,ax=plt.subplots(figsize=(6.6,3.4))
ks=list(b); vals=[b[x][2] for x in ks]
ax.bar(ks,vals,color=[RED if x=='2027' else NAVY for x in ks],width=.62)
for i,x in enumerate(ks): ax.text(i,vals[i]+30000,f"{k(vals[i])}\n{vals[i]/tot_rent*100:.0f}% · {b[x][0]} leases",ha='center',fontsize=7.5)
ax.set_ylim(0,max(vals)*1.28); ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f"${v/1e6:.1f}M"))
ax.set_title('Lease expiry ladder by annual in-place base rent (occupied space)',loc='left'); ax.grid(axis='y',color='#EEE'); ax.set_axisbelow(True)
save(fig,'c6_roll.png')
# c7 impact
ins=[i for i in d['insights'] if i['annual_impact_usd']]
ins.sort(key=lambda i:i['annual_impact_usd'])
fig,ax=plt.subplots(figsize=(6.6,5.2))
lab=[f"{i['id']}  {i['property'][:18]}" for i in ins]
ax.barh(lab,[i['annual_impact_usd'] for i in ins],color=[RED if i['annual_impact_usd']<0 else GREEN for i in ins],height=.62)
for j,i in enumerate(ins):
    a=i['annual_impact_usd']; import re as _re; _m=_re.search(r'\[([A-Z ]+)',i['impact_basis']); tag=('Upper bound' if _m and _m.group(1).startswith('UPPER') else _m.group(1).split()[0].title()) if _m else ''
    ax.text(a+(2500 if a>=0 else -2500),j,f"{'+' if a>=0 else '−'}{k(abs(a))}  [{tag}]",va='center',ha='left' if a>=0 else 'right',fontsize=7.5)
ax.axvline(0,color='#555',lw=.8); ax.set_xlim(-190000,110000); ax.xaxis.set_major_formatter(FuncFormatter(lambda v,p:f"${v/1000:,.0f}K"))
ax.set_title('Annual dollar impact by finding (red = run-rate erosion, green = recoverable upside)',loc='left',fontsize=10); ax.grid(axis='x',color='#EEE'); ax.set_axisbelow(True)
save(fig,'c7_impact.png')
# c8 solar
s24=P['1851 South Club Solar']['periods']['FY2024']['energy_income']; s25=P['1851 South Club Solar']['periods']['FY2025']['energy_income']
fig,ax=plt.subplots(figsize=(4.6,3.3))
el=[216200,96800]; sr=[452600,467100]
ax.bar(['FY2024','FY2025'],sr,color=NAVY,width=.5,label='SREC income'); ax.bar(['FY2024','FY2025'],el,bottom=sr,color=GOLD,width=.5,label='Electricity sales')
for i,(a,b_) in enumerate(zip(sr,el)): ax.text(i,a/2,k(a),ha='center',color='white',fontsize=8.5); ax.text(i,a+b_/2,k(b_),ha='center',fontsize=8.5); ax.text(i,a+b_+14000,k(a+b_),ha='center',fontsize=9,fontweight='bold')
ax.set_ylim(0,780000); ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f"${v/1000:,.0f}K")); ax.legend(frameon=False,fontsize=8,loc='upper right'); ax.set_title('Club Solar energy income',loc='left')
save(fig,'c8_solar.png'); stats['solar']={'s24':s24,'s25':s25}
# c9 debt
D=d['xt']['debt']; L=[(short.get(n,n),x['ltv'],x['dscr'],x['loan_bal'],x['rate'],x['maturity'],x['mos']) for n,x in D.items() if x.get('loan_bal') and x.get('lender')]
L.sort(key=lambda r:r[1]); stats['loans']=L
fig,(a1,a2)=plt.subplots(1,2,figsize=(6.8,3.0))
a1.barh([l[0] for l in L],[l[1]*100 for l in L],color=[RED if l[1]>.4 else NAVY for l in L],height=.55)
a1.axvline(40,color='#555',ls='--',lw=.8); a1.text(41,3.45,'40% governor',fontsize=7.5,color='#555')
for i,l in enumerate(L): a1.text(l[1]*100+1,i,f"{l[1]*100:.0f}%",va='center',fontsize=8)
a1.set_xlim(0,70); a1.set_ylim(-.5,3.8); a1.set_title('LTV (model value)',loc='left',fontsize=10)
L2=sorted(L,key=lambda r:r[2]); a2.barh([l[0] for l in L2],[l[2] for l in L2],color=[GOLD if l[2]<2 else NAVY for l in L2],height=.55)
a2.axvline(1.25,color='#555',ls='--',lw=.8); a2.text(1.3,3.45,'1.25x governor',fontsize=7.5,color='#555')
for i,l in enumerate(L2): a2.text(l[2]+.06,i,f"{l[2]:.2f}x",va='center',fontsize=8)
a2.set_xlim(0,4.6); a2.set_ylim(-.5,3.8); a2.set_title('DSCR',loc='left',fontsize=10)
fig.tight_layout(); save(fig,'c9_debt.png')
# c10 quarterly
C=d['cube']; q=collections.defaultdict(lambda:[0,0])
for n,m in C.items():
    for mo,x in m.items():
        y,mm=mo.split('-'); key=f"{y}\nQ{(int(mm)-1)//3+1}"; q[key][0]+=x['revenue']; q[key][1]+=x['noi']
qs=sorted(q); fig,ax=plt.subplots(figsize=(6.6,3.2)); import numpy as np
x=np.arange(len(qs)); ax.bar(x-.2,[q[a][0] for a in qs],.4,color=LIGHT,label='Revenue',edgecolor='#CFC8B5'); ax.bar(x+.2,[q[a][1] for a in qs],.4,color=NAVY,label='NOI')
ax.set_xticks(x); ax.set_xticklabels(qs,fontsize=8); ax.yaxis.set_major_formatter(FuncFormatter(lambda v,p:f"${v/1e6:.1f}M")); ax.legend(frameon=False,fontsize=8,ncol=2,loc='upper left')
ax.set_title('Quarterly revenue and NOI, monthly-reporting assets (cash basis)',loc='left',fontsize=10); ax.grid(axis='y',color='#EEE'); ax.set_axisbelow(True)
save(fig,'c10_qtr.png'); stats['qtr']={a.replace('\n',' '):q[a] for a in qs}
json.dump(stats,open(OUT+'stats.json','w'),indent=1,default=str)
print(json.dumps(stats,indent=0,default=str)[:2500])

from PIL import Image
import glob,os
json.dump({os.path.basename(f):Image.open(f).size for f in glob.glob(OUT+'c*.png')},open(OUT+'dims.json','w'))
