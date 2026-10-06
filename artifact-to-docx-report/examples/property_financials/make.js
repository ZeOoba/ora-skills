// Example report: Property Financials Review. Usage: node make.js <data.json> <charts_dir> <out.docx>
const [,,DATA,CHARTS,OUT]=process.argv;
const H=require('../../lib/docx_helpers.js'); H.init(CHARTS);
const {fs,docx:{Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,ImageRun,Header,Footer,PageNumber,AlignmentType,BorderStyle,WidthType,ShadingType,HeadingLevel,LevelFormat,PageBreak,VerticalAlign},C:{NAVY,GOLD,PARCH,RULE,RED,GREEN,MUTE,ZEB,FH,FB,W},fmt:{$k,$m,$,pc,sg,chg},run,para,H1,H2,H3,lede,bullet,B,cap,img,cell,table,callout,tiles,sp,none,thin}=H;
const D=JSON.parse(fs.readFileSync(DATA,'utf8')); const S=JSON.parse(fs.readFileSync(CHARTS+'/stats.json','utf8'));

// ---------- data
const P=D.props, Sx=D.sf, ins=D.insights;
const fy=(n,f)=>P[n].periods.FY2025[f]; const tt=(n,f)=>P[n].periods.TTM26?P[n].periods.TTM26[f]:null;
const names=Object.keys(P);
const leasable=n=>{const s=Sx[n];return s.sf-(s.common_area_sf||(n==='2203-2207 Northwood'?400:0))};
const vac=n=>leasable(n)-Sx[n].leased_sf;
const short={'1100 Rarig':'1100 Rarig','1900 Broadway':'1900 Broadway','29000 Info Lane':'29000 Info Lane','3034 Westerville':'3034 Westerville','3540 E 5th':'3540 E 5th','3883 Livingston':'3883 Livingston','9050 Red Branch':'9050 Red Branch','9620 State 350':'9620 State 350','FVC':'FVC (Sepich)','55 New Plant (EGFLLC)':'55 New Plant','1851 South Club Solar':'Club Solar (MD)','2203-2207 Northwood':'2203-07 Northwood'};
const ssv=D.portfolio.same_store_FY2025_vs_FY2024.view, pmv=D.portfolio.same_store_FY2025_vs_FY2024.view;
const ttmv=D.portfolio.same_store_TTM26_vs_TTM25.view, ytdv=D.portfolio.same_store_YTD26_vs_YTD25.view, pmo=D.portfolio.pm_only_FY2025_vs_FY2024.view;
const neg=ins.filter(i=>i.annual_impact_usd<0), pos=ins.filter(i=>i.annual_impact_usd>0);
const negSum=neg.reduce((a,i)=>a+i.annual_impact_usd,0), posSum=pos.reduce((a,i)=>a+i.annual_impact_usd,0);
const roll=S.roll, rt=S.roll_tot, r27=roll['2027'];
const T=D.xt.tenants, occT=T.filter(t=>t.oc.startsWith('Occupied'));
const occRent=occT.reduce((a,t)=>a+(t.mr||0)*12,0), occSF=occT.reduce((a,t)=>a+(t.sf||0),0);
const topT=[...occT].sort((a,b)=>b.mr-a.mr).slice(0,8); const topSum=topT.reduce((a,t)=>a+t.mr*12,0);
const fyN=S.fy25, tN=S.ttm26; const fyEx=fyN.noi-fy('55 New Plant (EGFLLC)','noi'), fyRevEx=fyN.rev-fy('55 New Plant (EGFLLC)','revenue');
const noiG=tN.noi/fyEx-1, revG=tN.rev/fyRevEx-1;
const CAP=0.07;
// check recovery ratio definition
const recChk=names.filter(n=>tt(n,'pool')).map(n=>[n,tt(n,'reimbursements'),tt(n,'pool'),tt(n,'recovery_ratio')]);
console.log(recChk.map(r=>r[0]+' '+(r[1]/r[2]).toFixed(2)+' vs '+r[3]).join('\n'));

const kids=[];
// ---------- COVER
kids.push(new Table({width:{size:W,type:WidthType.DXA},columnWidths:[W],rows:[new TableRow({height:{value:10200,rule:'atLeast'},children:[new TableCell({width:{size:W,type:WidthType.DXA},shading:{type:ShadingType.CLEAR,fill:NAVY,color:'auto'},verticalAlign:VerticalAlign.CENTER,margins:{top:600,bottom:600,left:700,right:600},borders:{top:none,left:none,right:none,bottom:{style:BorderStyle.SINGLE,size:36,color:GOLD}},children:[
 new Paragraph({spacing:{after:500},children:[new TextRun({text:'OXFORD REALTY ADVISORS  ·  ASSET MANAGEMENT',font:FB,size:18,bold:true,color:GOLD,characterSpacing:60})]}),
 new Paragraph({spacing:{after:60},children:[new TextRun({text:'Property Financials',font:FH,size:84,bold:true,color:'FFFFFF'})]}),
 new Paragraph({spacing:{after:360},children:[new TextRun({text:'Review',font:FH,size:84,bold:true,color:GOLD})]}),
 new Paragraph({spacing:{after:480,line:320},children:[new TextRun({text:'Performance, risk and value-creation roadmap across 12 assets, 129 occupied leases and 483,000 leasable square feet',font:FH,size:30,italics:true,color:'D8DCE8'})]}),
 new Paragraph({spacing:{after:40},children:[run('Data through 30 September 2026  ·  Cash basis  ·  Rent roll as of 2 October 2026',{size:18,color:'B8BFD0'})]}),
 new Paragraph({spacing:{after:40},children:[run('Prepared for Gabriel Goldberg  ·  5 October 2026',{size:18,color:'B8BFD0'})]}),
 new Paragraph({spacing:{after:0},children:[run('INTERNAL — NOT FOR EXTERNAL DISTRIBUTION',{size:16,bold:true,color:GOLD})]}),
]})]})]}));

// ---------- 1 EXEC SUMMARY
kids.push(H1('Executive summary'));
kids.push(lede(`The portfolio produced ${$m(fyN.noi)} of normalized NOI on ${$m(fyN.rev)} of revenue in FY2025, and the trailing twelve months show further lift. The financial case for this year is not growth in rents alone. It is stopping three revenue leaks, recovering costs that tenants should be paying, and defending a 2027 lease rollover that carries ${pc(r27[2]/rt)} of in-place rent.`));
kids.push(tiles([
 {l:'FY2025 NOI',v:$m(fyN.noi),d:`${pc(fyN.noi/fyN.rev)} margin on ${$m(fyN.rev)} revenue, 12 assets`},
 {l:'TTM Sep-26 NOI',v:$m(tN.noi),d:`${sg(noiG,1)} vs FY2025 on a like-for-like set of 11 assets`,c:GOLD},
 {l:'Occupancy',v:pc(S.occ.pct,1),d:`${(S.occ.leased/1000).toFixed(0)}K of ${(S.occ.sf/1000).toFixed(0)}K leasable SF; ${((S.occ.sf-S.occ.leased)/1000).toFixed(1)}K SF vacant`},
 {l:'In-place base rent',v:$m(occRent),d:`$${(occRent/occSF).toFixed(2)}/SF weighted across ${occT.length} occupied leases`,c:GOLD}]));
kids.push(sp(100));
kids.push(tiles([
 {l:'Same-store NOI FY25',v:sg(chg(ssv.noi)),d:`Base rent ${sg(chg(ssv.base_rent))}, reimbursements ${sg(chg(ssv.reimbursements))}, opex ${sg(chg(ssv.opex))} (8 assets)`},
 {l:'Same-store NOI TTM',v:sg(chg(ttmv.noi),1),d:`${$m(ttmv.noi.prior)} to ${$m(ttmv.noi.current)} (6 assets, Sep-26 vs Sep-25)`,c:GOLD},
 {l:'Revenue erosion found',v:$k(negSum),vc:RED,d:'Annual run-rate across Solar, FVC and Livingston',c:RED},
 {l:'Recoverable upside',v:'+'+$k(posSum),vc:GREEN,d:'15 findings; mixed evidence bases, not additive',c:GREEN}]));
kids.push(H2('What the numbers say'));
kids.push(bullet([B('Core rent growth is real. '),`Same-store base rent grew ${sg(chg(ssv.base_rent))} in FY2025 and reimbursements ${sg(chg(ssv.reimbursements))}. NOI grew only ${sg(chg(ssv.noi))} because energy income at Club Solar fell by $105K and operating expense rose ${sg(chg(ssv.opex))}.`]));
kids.push(bullet([B('Three assets are leaking income. '),`Club Solar energy income fell ${pc(1-S.solar.s25/S.solar.s24,1)} to ${$k(S.solar.s25)}. FVC annualized base rent is down 8.0% year over year. Livingston re-leased about 45% below the prior rent, and August and September base rent shows $0 in the PM exports.`]));
kids.push(bullet([B('Recoveries are the largest controllable gap. '),`Reimbursements cover 6% to 17% of the recoverable cost pool at Livingston, FVC, Rarig, 9620 State and Northwood, against 89% to 180% at Red Branch, Westerville and 3540 E 5th.`]));
kids.push(bullet([B('2027 is the year to defend. '),`${r27[0]} leases, ${(r27[1]/1000).toFixed(0)}K SF and ${$m(r27[2])} of annual base rent expire in 2027. Every renewal is also a chance to convert gross leases to NNN and reset below-market escalators.`]));
kids.push(bullet([B('Cost lines have clear owners. '),`Real estate tax is 35% of operating expense, and insurance, utilities and repairs each have an identifiable fault at one or two assets. A tax-appeal and contract-rebid program is worth roughly $78K a year on the modeled sensitivities.`]));
kids.push(callout('Bottom line',`Illustratively, capitalized at ${pc(CAP)}, the ${$k(posSum)} of recoverable upside is worth about ${$m(posSum/CAP,1)} of asset value, and the ${$k(Math.abs(negSum))} of run-rate erosion puts about ${$m(Math.abs(negSum)/CAP,1)} at risk if it persists. [FORECAST: the ${pc(CAP)} cap rate is an illustrative round figure, and the upside items are sensitivities, not commitments.]`));

// ---------- 2 PORTFOLIO PERFORMANCE
kids.push(H1('Portfolio performance'));
kids.push(lede('Rent growth is outrunning expense growth in the core. The gap to NOI growth is mostly one asset, Club Solar, and one expense line, insurance.'));
kids.push(img('c2_bridge.png',540)); kids.push(cap(`Figure 2. Same-store NOI bridge, FY2024 to FY2025 (1100 Rarig, 1900 Broadway, 29000 Info Lane, 3540 E 5th, 9050 Red Branch, FVC, 55 New Plant, Club Solar). The "energy, other and waivers" bar is derived as total revenue change less base rent and reimbursements. Axis starts at $3.4M.`));
const row=(l,x)=>[l,$(x.prior),$(x.current),$(x.current-x.prior),{t:sg(chg(x),1),color:(l==='Operating expense'||l==='Capital expenditure')?(chg(x)>0?RED:GREEN):(chg(x)>=0?GREEN:RED)}];
kids.push(H3('Same-store scorecard, three lenses'));
kids.push(table(['Metric','FY2024','FY2025','Change $','Change %'],[row('Base rent',ssv.base_rent),row('Reimbursements',ssv.reimbursements),row('Revenue',ssv.revenue),row('Operating expense',ssv.opex),row('Net operating income',ssv.noi),row('Capital expenditure',ssv.capex)],[2920,1700,1700,1700,1700],{boldFirst:true}));
kids.push(cap('FY2025 vs FY2024, 8 same-store assets including the two entity-level statements.'));
kids.push(table(['Metric','TTM Sep-25','TTM Sep-26','Change $','Change %'],[row('Base rent',ttmv.base_rent),row('Reimbursements',ttmv.reimbursements),row('Revenue',ttmv.revenue),row('Operating expense',ttmv.opex),row('Net operating income',ttmv.noi),row('Capital expenditure',ttmv.capex)],[2920,1700,1700,1700,1700],{boldFirst:true}));
kids.push(cap('Trailing twelve months to September, 6 PM-reported assets. Operating expense fell 8%, driven by a 25% drop in real estate tax that must be verified (see FVC and Rarig notes).'));
kids.push(callout('Insight',`On the trailing view, same-store NOI is up ${sg(chg(ttmv.noi),1)} while revenue is up only ${sg(chg(ttmv.revenue),1)}. Roughly all of that gain is a lower expense bill, and the largest piece, ${$k(ttmv.opex_by['Real estate & property tax'].prior-ttmv.opex_by['Real estate & property tax'].current)} of lower tax, is cash-basis timing until each county bill is reconciled. Treat the NOI lift as provisional, not run-rate.`));

kids.push(H2('Quarterly trend'));
kids.push(img('c10_qtr.png',560)); kids.push(cap('Figure 3. Quarterly revenue and NOI for the monthly-reporting assets, cash basis. Growth includes assets entering lease-up (9620 State, Westerville, Livingston, Northwood). Club Solar SREC income posts quarterly and creates the Q2 peaks.'));

// ---------- 3 ASSET SCORECARD
kids.push(H1('Asset scorecard'));
kids.push(lede('Red Branch and FVC generate 39% of FY2025 NOI. The next tier is high-margin and stable. The bottom tier is lease-up inventory where the work is occupancy and recovery, not rent.'));
const order=[...names].sort((a,b)=>fy(b,'noi')-fy(a,'noi'));
const rows=order.map(n=>{const s=Sx[n]||{};const occ=s.occ!=null?pc(s.occ,1):'n/a';const r=tt(n,'recovery_ratio');const t=tt(n,'noi');
 return [short[n],s.sf?leasable(n).toLocaleString('en-US'):'n/a',occ,$k(fy(n,'revenue')),$k(fy(n,'noi')),pc(fy(n,'noi_margin')),t?$k(t):'n/a',(n==='1851 South Club Solar'||r==null||!tt(n,'pool'))?'n/a':pc(r)]});
rows.push(['Portfolio',Math.round(S.occ.sf).toLocaleString('en-US'),pc(S.occ.pct,1),$k(fyN.rev),$k(fyN.noi),pc(fyN.noi/fyN.rev),$k(tN.noi),'']);
kids.push(table(['Asset','Leasable SF','Occ.','FY25 revenue','FY25 NOI','Margin','TTM26 NOI','Recovery'],rows,[1900,1150,800,1250,1150,850,1350,1270],{total:true,size:16,boldFirst:true}));
kids.push(cap('Occupancy from the 2 Oct 2026 rent roll. TTM NOI is not available for 55 New Plant (annual entity statement). Recovery = reimbursements ÷ recoverable pool, TTM Sep-26. Portfolio TTM NOI covers 11 assets.'));
kids.push(img('c1_noi.png',520)); kids.push(cap('Figure 1. FY2025 normalized NOI by asset. NOI excludes capital items, debt service, depreciation and entity tax. Lease-up assets (9620, Westerville, Livingston, Northwood) carry partial-year or ramping results.'));
kids.push(img('c5_occ.png',540)); kids.push(cap('Figure 4. Occupancy by asset. Red = below 90%. Common-area SF is excluded from leasable SF.'));
const v3=vac('9620 State 350')+vac('FVC')+vac('1100 Rarig');
kids.push(callout('Insight',`Three assets sit below 86% occupied: 9620 State (83.2%), FVC (85.5%) and Rarig (85.7%). Together they hold ${v3.toLocaleString('en-US')} SF of vacancy, about ${pc(v3/(S.occ.sf-S.occ.leased))} of the portfolio total. At current asking rents of $8.14 (FVC), $9.99 (9620) and $13.00 (Rarig) per SF, filling it is the single largest organic revenue lever.`));

// ---------- 4 VALUE LEVERS
kids.push(H1('Value-creation levers'));
kids.push(lede('Twenty-one findings were scored for dollar impact. Three stop income erosion, fifteen recover or save cost, and three carry lease intelligence that shapes the 2027 renewal program.'));
kids.push(img('c7_impact.png',640)); kids.push(cap('Figure 5. Annual dollar impact by finding. Tags show the evidence basis: Actual (observed), Estimate (modeled from observed data), Sensitivity (a stated % change applied to a base), Speculative, and Upper bound. Bases differ, so the bars should not be added.'));
kids.push(H2('Lever 1: stop the income erosion'));
kids.push(table(['Finding','Annual impact','What is happening','Next step'],[
 ['Club Solar energy income (REV-09)',{t:$k(-104932),color:RED,bold:true},`Total energy income fell ${pc(1-S.solar.s25/S.solar.s24,1)}, $669K to $564K. Electricity sales fell $216K to $97K while SREC income rose $453K to $467K. Operating NOI fell $123K.`,'Pull monthly production, meter reads and power-sale statements for 2024-2026; test for curtailment, meter fault or billing gap.'],
 ['FVC base rent run-rate (REV-01)',{t:$k(-92356),color:RED,bold:true},'Q3-26 annualized base rent $1.05M against $1.15M in Q3-25 (-8.0%). FVC is about 26% of trailing base rent.','Pull the rent roll by unit for Jun-Sep 2026; separate vacancy, concessions and rent cuts; set a leasing target.'],
 ['Livingston re-lease (REV-02)',{t:$k(-81450),color:RED,bold:true},'New lease $8,212.50/mo ($9.00/SF NNN, 3% steps) against $15,000/mo before. PM exports show $0 base rent in Aug and Sep 2026.','Confirm September billing and collection, and whether the prior $15,000 was gross or NNN.']],[2200,1050,3350,3120],{align:['l','r','l','l'],size:16,boldFirst:true}));
kids.push(sp(60));
kids.push(H2('Lever 2: close the recovery gap'));
kids.push(img('c4_recovery.png',600)); kids.push(cap('Figure 6. Expense recovery ratio, TTM Sep-26. Values above 100% (3540 E 5th, Westerville) mean recoveries exceed the property-level pool and need a reconciliation check.'));
const recRows=['3883 Livingston','FVC','1100 Rarig','9620 State 350','2203-2207 Northwood','29000 Info Lane'].map(n=>{const pool=tt(n,'pool'),re=tt(n,'reimbursements');return [short[n],$(pool),$(re),pc(re/pool),$(pool-re)]});
const un=['3883 Livingston','FVC','1100 Rarig','9620 State 350','2203-2207 Northwood','29000 Info Lane'].reduce((a,n)=>a+tt(n,'pool')-tt(n,'reimbursements'),0);
recRows.push(['Total, six assets','','','',$(un)]);
kids.push(table(['Asset','Recoverable pool','Reimbursed','Recovery','Unrecovered cost'],recRows,[2600,1900,1700,1500,2020],{total:true,boldFirst:true}));
kids.push(cap('TTM Sep-26. The pool is tax, insurance, utilities, grounds and repairs. Unrecovered cost is a ceiling, not a forecast: only leases that permit pass-throughs can bill it.'));
kids.push(callout('Insight',`The six lowest-recovery assets carry ${$k(un)} of unrecovered operating cost a year. Each +10 points of recovery is worth about $26.8K at FVC and $11.4K at 9620 State. The practical route is lease by lease: confirm which leases already allow pass-throughs and are not being billed, and move gross leases to NNN or modified gross with a base-year stop at every renewal. Meanwhile 3540 E 5th recovered $47.4K against $37.7K of operating cost, so a CAM, tax and insurance reconciliation there protects against a tenant audit.`));
kids.push(H2('Lever 3: cost program'));
kids.push(img('c3_opex.png',600)); kids.push(cap('Figure 7. Same-store operating expense change by category, FY2025 vs FY2024. Turnover cost rose from $5.9K to $41.6K, mostly a $41.6K suite preparation charge at Info Lane.'));
kids.push(table(['Program','Annual value','Basis','Where to start'],[
 ['Real estate tax appeals (EXP-08)','+$26.8K','5% of $536K FY25 tax [SENSITIVITY]','Info Lane (+20% YTD), Red Branch (+13% FY25), Rarig, Broadway'],
 ['Management fee rebid (EXP-07)','+$25.2K','50 bps on trailing revenue [SENSITIVITY]','9620 State at 5.0% and Livingston at 4.0% versus 3.8% overall'],
 ['Insurance blanket rebid (EXP-10)','+$13.3K','8% of $166K TTM premium [SPECULATIVE]','Align renewals; 9620 insurance up 55% TTM'],
 ['Snow, landscape, trash, janitorial RFP (EXP-09)','+$13.1K','10% of $131K TTM grounds cost [SENSITIVITY]','One RFP per metro; Red Branch snow up 55%, Info Lane snow tripled in FY25'],
 ['Broadway water and sewer (EXP-01)','+$48.9K','Annualized 2026 vs FY2025 [ESTIMATE]','Water and sewer $63K Jan-Sep vs $30.5K prior year; check leak, rate change, estimated reads'],
 ['Red Branch repairs and snow (EXP-02)','+$40.4K','YTD26 vs YTD25 [ACTUAL, 9 months]','Roof condition report before more repair spend; rebid snow']],[2850,1050,2700,3120],{align:['l','r','l','l'],size:16,boldFirst:true}));
kids.push(sp(60));
kids.push(H2('Lever 4: occupancy and vacancy cost'));
kids.push(para(`Red Branch lost $64K of base rent to contra-revenue in FY2025 (6.4% of base rent): vacancy $34.1K, commercial waivers $15.0K, bad debt $8.0K and prepaid adjustments $6.9K. It still shows $33.7K on a TTM basis. Info Lane contra-revenue is also rising, from 1.4% to 2.1% of rent ($13.4K TTM). Tie every waiver to a signed concession, put vacant suites on a leasing clock, and tighten collections on the bad-debt tenants.`));

// ---------- 5 LEASE ROLLOVER
kids.push(H1('Lease rollover and rent upside'));
kids.push(lede(`${$m(occRent)} of annual base rent sits on ${occT.length} occupied leases. The 2027 expiry class is ${pc(r27[2]/rt)} of it, and it is the portfolio's biggest negotiating window.`));
kids.push(img('c6_roll.png',620)); kids.push(cap('Figure 8. Lease expiry ladder by annual in-place base rent, occupied space only. Source: Master Tenant Rent Roll, 2 Oct 2026. MTM = month-to-month.'));
kids.push(tiles([
 {l:'2027 expirations',v:r27[0]+' leases',d:`${(r27[1]/1000).toFixed(0)}K SF, ${pc(r27[1]/occSF)} of leased SF`,c:RED,vc:RED},
 {l:'2027 base rent at stake',v:$m(r27[2]),d:`${pc(r27[2]/rt)} of in-place annual rent`},
 {l:'Value of +5% mark-to-market',v:'+'+$k(r27[2]*0.05),d:'Per year on 2027 expirations [SENSITIVITY]',c:GREEN,vc:GREEN},
 {l:'Top-8 tenant share',v:pc(topSum/rt),d:`${$m(topSum)} of in-place rent`,c:GOLD}]));
kids.push(H2('In-place rent versus current asking rent'));
const gap=[['1100 Rarig','12.14','MG','13.00 MG','+7%'],['29000 Info Lane','14.19','MG','15.20 MG','+7%'],['9050 Red Branch','12.11','NNN','13.95 NNN','+15%'],['9620 State 350','9.05','MG','9.99 plus utilities','+10%*'],['FVC (Sepich)','10.99','MG (mostly)','8.14 NNN','Confirm basis']];
kids.push(table(['Asset','In-place $/SF','In-place basis','Asking $/SF','Gap'],gap,[2400,1500,1700,2300,1820],{align:['l','r','l','l','r'],boldFirst:true}));
kids.push(cap('In-place = weighted base rent on occupied leases. Asking from oxfordra.net/available-space, 5 Oct 2026. Shown as entered with basis labels, no conversion. *9620 asking is plus utilities; confirm utilities treatment. FVC asking is NNN while in-place is mostly modified gross, so the gap is not comparable until confirmed per suite.'));
kids.push(H2('Largest tenants'));
kids.push(table(['Tenant','Asset','SF','Annual rent','% of rent','Expires'],topT.map(t=>[(t.co||t.t).replace(/, a Delaware Corporation/,'').slice(0,34),short[t.e]||t.e,(t.sf||0).toLocaleString('en-US'),$(t.mr*12),pc(t.mr*12/rt,1),t.le]),[3000,1650,900,1400,1050,1720],{align:['l','l','r','r','r','r'],size:16}));
kids.push(cap('Eurosort at 55 New Plant is the largest single exposure at 8.4% of in-place rent and expires 12/31/2027.'));
kids.push(H2('Lease intelligence'));
kids.push(table(['Lease','Terms','Reading'],[
 ['3034 Westerville\nBuckeye\'s Best Transport','18,360 SF; rent stepped $8,950.50 to $13,005.00 on 4/1/2026 ($8.50/SF); 3.5% steps; expires 9/30/2030','45% step captured; TTM NOI $135.5K vs $19.2K prior. Verify the $3,553 above schedule in May.'],
 ['3875-3883 Livingston\nMy Autonomous Transportation','10,950 SF; $8,212.50/mo ($9.00/SF NNN), 3% steps, rent from 9/1/2026; 5-year option','About 45% below the prior $15,000/mo; all-in about $11.95/SF with the NNN estimate.'],
 ['7658 Fishel\nHeritage Pool Supply','24,000 SF; flat $8,540/mo for 60 months; renewal fixed at $8,710.80 (+2%/yr) from 10/1/2026','No market reset. Lease-form lesson: renewals at the greater of fixed or fair market value, and 3% initial steps. Each $1.00/SF is $24K a year.'],
 ['3540 E 5th\nIMH LLC (Malul of London)','35,886 SF; NNN; 2.5% steps; $24,153.32/mo from Aug 2026; expires 7/31/2033; mgmt fee cap 3%','On schedule. Reconcile recoveries that exceed cost.'],
 ['55 New Plant\nEurosort','34,534 SF; $37,736/mo in 2026, 3% steps; expires 12/31/2027','FY25 rent of $440,745 ties to schedule. Start renewal or backfill now; renewal clause only partly read.'],
 ['401 Sunburst Highway\nThe Bay Area Corporation','5,100 SF; $61,560/yr initial; two 5-year renewals at the greater of fair rent or a stated minimum','Strong renewal structure; use it as the template.']],[2400,3720,3600],{align:['l','l','l'],size:16}));

// ---------- 6 CAPITAL STRUCTURE AND RISK
kids.push(H1('Capital structure and risk watch'));
kids.push(lede('Leverage is low and coverage is strong on three of four external loans. One loan is above the 40% LTV governor on model value, and one balloons within 14 months.'));
kids.push(img('c9_debt.png',640)); kids.push(cap('Figure 9. LTV and DSCR on the four externally financed assets. LTV uses the model valuation at assumed cap rates and is an estimate, not an appraisal. Governors: LTV 40%, DSCR 1.25x.'));
const loans=S.loans.map(l=>[l[0],$(l[3]),(l[4]*100).toFixed(2)+'%',l[5],l[6]+' mo',pc(l[1]),l[2].toFixed(2)+'x']);
const lt=S.loans.reduce((a,l)=>a+l[3],0);
loans.push(['Total / blended',$(lt),'','','','','']);
kids.push(table(['Asset','Balance','Rate','Maturity','To maturity','LTV','DSCR'],loans,[2200,1400,900,1400,1300,1220,1300],{align:['l','r','r','r','r','r','r'],total:true,boldFirst:true}));
kids.push(sp(80));
kids.push(bullet([B('9050 Red Branch, 4.25% to 1/1/2028. '),'Balance $1.31M at 15% LTV and 3.74x coverage. It is inside the 18-month balloon alert. The 4.25% coupon is unlikely to be matched at refinance [FORECAST], but the low leverage leaves room to upsize and return equity.']));
kids.push(bullet([B('3540 E 5th, 54% LTV and 1.48x DSCR. '),'The only asset above the 40% LTV governor on model value. Confirm the valuation basis before relying on this figure; the lease is NNN with 2.5% steps through 2033, so coverage improves each August.']));
kids.push(bullet([B('55 New Plant, no debt, idle cash. '),'Interest expense fell from $32.6K (2025) to $3.2K (2026 YTD) while interest income reached $78.3K YTD, which points to a payoff and a large entity cash balance. Redeploying it toward the acquisition plan is a direct value lever.']));
kids.push(new Paragraph({heading:HeadingLevel.HEADING_2,pageBreakBefore:true,spacing:{before:0,after:90},children:[new TextRun({text:'Model valuation snapshot',font:FH,size:30,bold:true,color:NAVY})]}));
const DB=D.xt.debt; const dnames=Object.keys(DB).sort((a,b)=>DB[b].val_o-DB[a].val_o);
const vrows=dnames.map(n=>{const x=DB[n];return [short[n]||n,x.own<1?pc(x.own):'100%',$k(x.noi_o),pc(x.cap,2),$k(x.val_o),x.loan_bal&&x.lender?$k(x.loan_bal):'none']});
const tv=dnames.reduce((a,n)=>a+DB[n].val_o,0), tn=dnames.reduce((a,n)=>a+DB[n].noi_o,0);
vrows.push(['Total','',$k(tn),pc(tn/tv,2),$k(tv),$k(lt)]);
kids.push(table(['Asset','Own.','Model NOI','Cap rate','Model value','External debt'],vrows,[2700,800,1500,1300,1720,1700],{align:['l','r','r','r','r','r'],total:true,boldFirst:true,size:16}));
kids.push(cap('Ownership-weighted. NOI and value come from the Master workbook model at assumed cap rates and a stated expense load, and differ from the normalized NOI in this report. [ESTIMATE] Not an appraisal.'));
kids.push(H2('Insurance tracker exceptions'));
const insEx={};D.xt.ins.filter(i=>i.status!=='Current'&&!['9620 State 350','Easton Tech Center POA'].includes(i.e)).forEach(i=>{const k_=i.e;insEx[k_]=insEx[k_]||{p:0,exp:i.exp,st:i.status};insEx[k_].p+=i.prem||0;});
const irow=Object.entries(insEx).sort((a,b)=>a[1].exp.localeCompare(b[1].exp)).map(([e,x])=>[short[e]||e,x.st,x.exp,$(x.p)]);
kids.push(table(['Asset','Tracker status','Policy end','Premium'],irow,[3300,2400,2000,2020],{align:['l','l','r','r'],boldFirst:true}));
kids.push(cap('Source: Notion insurance tracker (30 policy lines, $193K total premium). Status may lag renewals; confirm each renewal binder is logged. 9620 State GL and property were cancelled and replaced by a Hartford BOP running to 5/28/2027.'));
kids.push(callout('Risk',`The tracker shows expired policies at Rarig (3/19/2026), Red Branch (8/31/2026) and Westerville (9/18/2026), a cancelled floater at Club Solar (5/10/2026), and a Northwood package renewing 10/25/2026. If any of these are real lapses, they are a lender-covenant and uninsured-loss exposure far larger than the premium. Confirm coverage this week; it takes one call per asset.`,RED));

// ---------- 7 ACTION PLAN
kids.push(H1('90-day action plan'));
kids.push(lede('Sequenced by speed to cash and by cost of delay. The first thirty days confirm facts that decide whether a problem is real.'));
kids.push(table(['Window','Action','Asset','Value at stake'],[
 [{t:'Days 0-30',bold:true,color:RED},'Confirm every insurance policy is in force and logged','Rarig, Red Branch, Westerville, Solar, Northwood','Covenant and loss exposure'],
 ['','Confirm Sept rent billed and collected; confirm prior $15,000 scope','3883 Livingston','$81K/yr'],
 ['','Solar production audit: monthly output, meter reads, power-sale statements 2024-26','Club Solar','$105K/yr'],
 ['','FVC unit rent roll Jun-Sep 2026; split vacancy, concessions, rent cuts','FVC','$92K/yr'],
 ['','Water and sewer invoices, meter reads and leak check','1900 Broadway','$49K/yr'],
 [{t:'Days 30-60',bold:true,color:'7C5F24'},'Lease-by-lease CAM, tax and insurance audit; start monthly estimates','FVC, Rarig, 9620, Livingston, Northwood','$536K ceiling'],
 ['','CAM reconciliation, last two lease years; document capital pass-through','3540 E 5th','Over-bill risk $9.6K'],
 ['','File tax appeals before county deadlines; reconcile FVC and Rarig tax timing','Info Lane, Red Branch, Rarig, Broadway','$26.8K/yr'],
 ['','Roof condition report and replace-vs-repair; rebid snow with per-push and seasonal cap','9050 Red Branch','$40K/yr'],
 [{t:'Days 60-90',bold:true,color:GREEN},'Issue RFPs: snow, landscaping, trash, janitorial per metro; management fee; blanket insurance','Portfolio','$52K/yr combined'],
 ['','Open the 2027 renewal program: 47 leases, NNN conversion, mark-to-market','Portfolio','$86K per +5%'],
 ['','Red Branch refinance plan ahead of 1/1/2028; 55 New Plant renewal or backfill and cash deployment','Red Branch, 55 New Plant','Maturity and rollover risk']],[1200,4500,2200,1820],{align:['l','l','l','l'],size:16}));
kids.push(sp(100));
kids.push(callout('Decision for Gabriel',`The largest decision is how hard to push NNN conversion on the 2027 class. The upside is a permanent lift in recoveries; the cost is renewal friction with tenants at assets already below 86% occupancy. The assets with the weakest recovery and the weakest occupancy (FVC, Rarig, 9620) are where the trade-off is tightest, and the tenants at Red Branch and 3540 E 5th show the structure is achievable.`));

// ---------- APPENDIX
kids.push(H1('Appendix'));
kids.push(H2('A. Findings register'));
const sev=s=>({t:s,color:s==='High'?RED:(s==='Medium'?'7C5F24':MUTE),bold:true});
const basisTag=i=>{const m=(i.impact_basis||'').match(/\[([A-Z ]+)/);return m?(m[1].startsWith('UPPER')?'upper bound':m[1].split(' ')[0].toLowerCase()):'n/a'};
kids.push(table(['ID','Severity','Asset','Finding','Annual $','Basis'],ins.map(i=>[i.id,sev(i.severity),i.property.slice(0,16),i.title,i.annual_impact_usd?{t:(i.annual_impact_usd>0?'+':'')+$k(i.annual_impact_usd),color:i.annual_impact_usd<0?RED:GREEN}:'n/a',basisTag(i)]),[720,820,1400,4480,900,1400],{align:['l','l','l','l','r','l'],size:14,hs:14}));
kids.push(sp(60));
kids.push(new Paragraph({heading:HeadingLevel.HEADING_2,pageBreakBefore:true,spacing:{before:0,after:90},children:[new TextRun({text:'B. Data quality and method',font:FH,size:30,bold:true,color:NAVY})]}));
['All statements are cash basis. Tax, insurance and snow are lumpy by payment date; prefer FY and TTM views for them.',
 'NOI is normalized: revenue less recurring operating cost. Capital items, commissions, tenant improvements, distributions, debt service, depreciation and entity tax are excluded.',
 'Same-store excludes lease-up and partial-history assets (9620 State, Westerville, Livingston). The FY view adds the two entity-level statements (55 New Plant, Club Solar). TTM and YTD views use PM monthly exports only.',
 'Monthly data reconciles to annual P&Ls to the dollar for Rarig, Broadway, Info Lane, 3540 E 5th, Red Branch and FVC. Livingston FY2025 differs by $3.4K of opex (July 2025 missing); 9620 FY2025 revenue differs by $6.5K.',
 'FVC and the Sepich portfolio are one asset group of 109,657 SF; the report is an all-properties aggregate, so unit-level results are not available.',
 'Northwood and Club Solar monthly P&Ls were transcribed from screenshots; totals tie. Northwood closed 10/3/2024, so TTM25 is an 11-month period and no TTM comparison is shown.',
 'Lease abstracts for 3540 E 5th, 55 New Plant and 401 Sunburst come from partial OCR of scans; verify against the PDFs. Westerville, Livingston and Fishel read from text layers.',
 'Occupancy counts rent-roll rows classed Occupied; notice-given and expired space is counted vacant. Per-SF figures use current SF for every period.'].forEach(t=>kids.push(bullet(t)));
kids.push(sp(60));
kids.push(para('Sources: Property Financials Review artifact (generated 5 Oct 2026); Master Excel Template Company Wide, Property NOI and Master Tenant Rent Roll (2 Oct 2026); PM monthly exports through 30 Sep 2026; QuickBooks entity statements; executed leases; Notion insurance tracker; oxfordra.net/available-space (5 Oct 2026).',{size:16,italics:true,color:MUTE}));

const doc=new Document({creator:'Oxford Realty Advisors',title:'Property Financials Review',description:'Performance, risk and value-creation roadmap',
 styles:{default:{document:{run:{font:FB,size:20}}}},
 numbering:{config:[{reference:'b',levels:[{level:0,format:LevelFormat.BULLET,text:'•',alignment:AlignmentType.LEFT,style:{paragraph:{indent:{left:360,hanging:240}},run:{color:GOLD}}}]}]},
 sections:[{properties:{titlePage:true,page:{size:{width:12240,height:15840},margin:{top:1200,bottom:1100,left:1260,right:1260,header:560,footer:500}}},
  headers:{first:new Header({children:[new Paragraph({children:[]})]}),default:new Header({children:[new Paragraph({spacing:{after:0},border:{bottom:{style:BorderStyle.SINGLE,size:6,color:RULE,space:4}},children:[new TextRun({text:'OXFORD REALTY ADVISORS',font:FB,size:14,bold:true,color:GOLD,characterSpacing:40}),new TextRun({text:'     Property Financials Review  ·  Data through 30 Sep 2026',font:FB,size:14,color:MUTE})]})]})},
  footers:{first:new Footer({children:[new Paragraph({children:[]})]}),default:new Footer({children:[new Paragraph({alignment:AlignmentType.RIGHT,children:[new TextRun({text:'Internal  ·  Page ',font:FB,size:14,color:MUTE}),new TextRun({children:[PageNumber.CURRENT],font:FB,size:14,color:MUTE})]})]})},
  children:kids}]});
Packer.toBuffer(doc).then(b=>{fs.writeFileSync(OUT,b);console.log('written',OUT,b.length)});