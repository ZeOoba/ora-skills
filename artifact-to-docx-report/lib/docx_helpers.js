const fs=require('fs');
const path=require('path');
// Set by init(): directory holding chart PNGs and dims.json
let CHART_DIR='.'; let DIM={};
function init(chartDir){CHART_DIR=chartDir;DIM=JSON.parse(fs.readFileSync(path.join(chartDir,'dims.json'),'utf8'));}
const {Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,ImageRun,Header,Footer,PageNumber,AlignmentType,BorderStyle,WidthType,ShadingType,HeadingLevel,LevelFormat,PageBreak,VerticalAlign}=require('docx');
const NAVY='1B2A4A',GOLD='C9A96E',PARCH='F5F3EF',RULE='DAD5C9',RED='A62525',GREEN='1B7A4B',MUTE='6F768A',ZEB='FAF8F3';
const FH='EB Garamond',FB='DM Sans';
const W=9720;
const $k=v=>(v<0?'−':'')+'$'+Math.round(Math.abs(v)/1000).toLocaleString('en-US')+'K';
const $m=(v,dp=2)=>'$'+(v/1e6).toFixed(dp)+'M';
const $=v=>(v<0?'−':'')+'$'+Math.round(Math.abs(v)).toLocaleString('en-US');
const pc=(v,dp=0)=>(v*100).toFixed(dp)+'%';
const chg=x=>x.current/x.prior-1;
const sg=(v,dp=0)=>(v>=0?'+':'−')+Math.abs(v*100).toFixed(dp)+'%';
const run=(t,o={})=>new TextRun({text:t,font:o.font||FB,size:o.size||20,bold:o.bold,italics:o.italics,color:o.color||'222222'});
const para=(t,o={})=>new Paragraph({spacing:{before:o.before??0,after:o.after??120,line:o.line||276},alignment:o.align,keepNext:o.keepNext,children:Array.isArray(t)?t:[run(t,o)]});
const H1=t=>new Paragraph({heading:HeadingLevel.HEADING_1,pageBreakBefore:true,spacing:{before:0,after:80},border:{bottom:{style:BorderStyle.SINGLE,size:12,color:GOLD,space:4}},children:[new TextRun({text:t,font:FH,size:44,bold:true,color:NAVY})]});
const H2=t=>new Paragraph({heading:HeadingLevel.HEADING_2,keepNext:true,spacing:{before:240,after:90},children:[new TextRun({text:t,font:FH,size:30,bold:true,color:NAVY})]});
const H3=t=>new Paragraph({keepNext:true,spacing:{before:160,after:60},children:[new TextRun({text:t.toUpperCase(),font:FB,size:16,bold:true,color:'7C5F24',characterSpacing:30})]});
const lede=t=>new Paragraph({spacing:{before:80,after:200,line:300},children:[new TextRun({text:t,font:FH,size:26,color:'2B3856'})]});
const bullet=(parts)=>new Paragraph({numbering:{reference:'b',level:0},spacing:{after:70,line:270},children:(Array.isArray(parts)?parts:[parts]).map(p=>typeof p==='string'?run(p):p)});
const B=(t)=>run(t,{bold:true,color:NAVY});
const cap=t=>new Paragraph({spacing:{before:40,after:180},children:[run(t,{size:16,italics:true,color:MUTE})]});
const none={style:BorderStyle.NONE,size:0,color:'FFFFFF'};
const thin={style:BorderStyle.SINGLE,size:4,color:RULE};
function img(name,wpx=640){const [w,h]=DIM[name];return new Paragraph({alignment:AlignmentType.CENTER,spacing:{before:80,after:40},keepNext:true,children:[new ImageRun({type:'png',data:fs.readFileSync(path.join(CHART_DIR,name)),transformation:{width:wpx,height:Math.round(wpx*h/w)},altText:{title:name,description:name,name}})]});}
function cell(t,w,o={}){const kids=(Array.isArray(t)?t:[t]).map(x=>typeof x==='string'?new Paragraph({alignment:o.align||AlignmentType.LEFT,spacing:{before:0,after:0,line:250},children:[run(x,{size:o.size||17,bold:o.bold,color:o.color})]}):x);
 return new TableCell({width:{size:w,type:WidthType.DXA},verticalAlign:VerticalAlign.CENTER,shading:o.fill?{type:ShadingType.CLEAR,fill:o.fill,color:'auto'}:undefined,margins:{top:o.mt??60,bottom:o.mt??60,left:90,right:90},borders:o.borders||{top:none,left:none,right:none,bottom:thin},children:kids});}
function table(head,rows,widths,o={}){const al=o.align||widths.map((_,i)=>i===0?'l':'r');const A=a=>a==='r'?AlignmentType.RIGHT:a==='c'?AlignmentType.CENTER:AlignmentType.LEFT;
 const hr=new TableRow({tableHeader:true,cantSplit:true,children:head.map((h,i)=>cell(h,widths[i],{fill:NAVY,color:'FFFFFF',bold:true,size:o.hs||15,align:A(al[i]),borders:{top:none,left:none,right:none,bottom:none}}))});
 const rs=rows.map((r,ri)=>new TableRow({cantSplit:true,children:r.map((c,i)=>{let txt=c,col,bold=false;if(c&&typeof c==='object'&&!Array.isArray(c)&&c.t!==undefined){txt=c.t;col=c.color;bold=c.bold}
   return cell(String(txt),widths[i],{fill:(o.total&&ri===rows.length-1)?'EFEBE0':(ri%2?ZEB:undefined),align:A(al[i]),size:o.size||17,color:col,bold:bold||(o.total&&ri===rows.length-1)||(i===0&&o.boldFirst)})})}));
 return new Table({width:{size:W,type:WidthType.DXA},columnWidths:widths,rows:[hr,...rs]});}
function callout(title,text,color=GOLD){return new Table({width:{size:W,type:WidthType.DXA},columnWidths:[W],rows:[new TableRow({cantSplit:true,children:[new TableCell({width:{size:W,type:WidthType.DXA},shading:{type:ShadingType.CLEAR,fill:PARCH,color:'auto'},margins:{top:130,bottom:130,left:220,right:200},borders:{top:none,bottom:none,right:none,left:{style:BorderStyle.SINGLE,size:28,color}},children:[new Paragraph({spacing:{after:50},children:[new TextRun({text:title.toUpperCase(),font:FB,size:15,bold:true,color:'7C5F24',characterSpacing:30})]}),new Paragraph({spacing:{after:0,line:270},children:Array.isArray(text)?text:[run(text,{size:19})]})]})]})]});}
function tiles(items){const n=items.length,w=Math.floor(W/n);const ws=items.map((_,i)=>i===n-1?W-w*(n-1):w);
 return new Table({width:{size:W,type:WidthType.DXA},columnWidths:ws,rows:[new TableRow({cantSplit:true,children:items.map((it,i)=>new TableCell({width:{size:ws[i],type:WidthType.DXA},shading:{type:ShadingType.CLEAR,fill:i%2?'EFEBE0':PARCH,color:'auto'},margins:{top:140,bottom:140,left:150,right:120},borders:{top:{style:BorderStyle.SINGLE,size:18,color:it.c||NAVY},left:none,right:none,bottom:none},children:[
   new Paragraph({spacing:{after:20},children:[new TextRun({text:it.l.toUpperCase(),font:FB,size:13,bold:true,color:MUTE,characterSpacing:20})]}),
   new Paragraph({spacing:{after:20},children:[new TextRun({text:it.v,font:FH,size:48,bold:true,color:it.vc||NAVY})]}),
   new Paragraph({spacing:{after:0,line:230},children:[run(it.d,{size:15,color:'46506B'})]})]}))})]});}
const sp=(a=120)=>new Paragraph({spacing:{after:a},children:[]});
module.exports={init,fs,path,docx:{Document,Packer,Paragraph,TextRun,Table,TableRow,TableCell,ImageRun,Header,Footer,PageNumber,AlignmentType,BorderStyle,WidthType,ShadingType,HeadingLevel,LevelFormat,PageBreak,VerticalAlign},
 C:{NAVY,GOLD,PARCH,RULE,RED,GREEN,MUTE,ZEB,FH,FB,W},
 fmt:{$k,$m,$,pc,sg,chg},run,para,H1,H2,H3,lede,bullet,B,cap,img,cell,table,callout,tiles,sp,none,thin};
