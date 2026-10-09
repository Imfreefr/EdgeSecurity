"""Interface local de revisao OpenCode (stdlib apenas). Nao altera manifestos oficiais.

Uso:
  .venv/Scripts/python tools/opencode_review_server.py --manifest <copia.ndjson> --outdir <dir-isolado> --port 8787 [--dupes <outdir>/dupes.json]
Paginas: / (revisao) e /dupes (lado a lado). Decisoes em <outdir>/decisions/,
<outdir>/review-manifest.ndjson e <outdir>/dupe-decisions/.
"""
import argparse
import json
import mimetypes
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opencode_pipeline import (  # noqa: E402
    ambiguity_report, load_dupe_decisions, load_working_state,
    pending_dupe_items, save_decision, save_dupe_decision, write_manifest,
)

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>OpenCode Review Local</title>
<style>body{font-family:system-ui;margin:0;display:flex;height:100vh}aside{width:320px;overflow:auto;border-right:1px solid #ccc;padding:8px}
main{flex:1;overflow:auto;padding:8px}canvas{border:1px solid #333;cursor:crosshair}
.box{border:1px solid #ccc;margin:4px 0;padding:4px;font-size:12px}.sel{border-color:#000;background:#f4f4f4}
.amb{color:#a60;font-weight:bold}.ok{color:green}.warn{color:#a60}
#bar{background:#eee;height:10px}#bar>i{display:block;background:#090;height:100%}</style>
<aside><h3>Fila <small id=prog></small></h3><div id=bar><i style=width:0%></i></div>
<select id=f onchange="list()"><option value=pending>pendentes</option><option value=decided>decididas</option><option value=all>todas</option></select>
<a href=/dupes>duplicatas</a><div id=q></div></aside>
<main><h3 id=t></h3>
<button onclick="zoom(1.25)">+</button><button onclick="zoom(0.8)">-</button><button onclick="zoom(0)">1:1</button>
<span id=zi></span><br><canvas id=c></canvas><div id=boxes></div>
<label>Nota <input id=note size=60 placeholder="motivo da decisao"></label>
<label><input type=checkbox id=cov> cobertura completa</label>
<button onclick="save()">Salvar e avançar</button> <span id=msg></span> <span id=dirty style="display:none;color:#a60">● não salvo</span>
<p><small>Imagem: clique numa caixa p/ selecionar, arraste p/ mover, cantos p/ redimensionar, clique no vazio p/ adicionar. Teclas: &#8592;/&#8594; imagem, +/- zoom, 0-3 classe, Del remove, Enter salva. Trocar de imagem descarta o não-salvo.</small></p></main>
<script>
let ROWS=[],CUR=null,IMG=new Image(),DRAW=[],Z=1,SEL=-1,DECIDED=0,DIRTY=false,DRAG=null;
let AMB={idx:[],reasons:{},pairs:[]};
let NOTICE='';
const C=['#00ff70','#ffaa00','#00cfff','#dd77ff'];
const NAMES=['pedestre','empilhadeira','operador','carga'];
const clamp=(v,a,b)=>Math.min(b,Math.max(a,v));
fetch('/api/queue').then(r=>r.json()).then(d=>{ROWS=d.rows;DECIDED=d.decided;
 prog.textContent=d.decided+'/'+d.total;document.querySelector('#bar>i').style.width=(100*d.decided/d.total)+'%';
 list();if(ROWS.length)openImg(firstPending());});
function firstPending(){const p=ROWS.find(r=>r.status.startsWith('pending'));return (p||ROWS[0]).id;}
function list(){const f=document.getElementById('f').value;
 q.innerHTML=ROWS.filter(r=>f==='all'||(f==='pending')===r.status.startsWith('pending'))
  .map(r=>`<div><a href="#" onclick="openImg('${r.id}');return false">${r.platform_name}</a> <small>${r.status} ${r.nboxes}cx${r.amb.length?' <span class=amb>\\u26a0'+r.amb.length+'</span>':''}</small></div>`).join('');}
// NOTA: nunca chamar de 'open' — window.open e LegacyUnforgeable e o clique
// abriria o id como URL (pagina branca). 'openImg' nao colide.
function openImg(id){const row=ROWS.find(r=>r.id===id);if(!row)return;
 if(CUR&&CUR.id===id&&DRAW.length)return; // ja exibida: sem reload, sem branca
 msg.textContent='carregando '+row.platform_name+'…';msg.className='';
 IMG.onload=()=>{CUR=row;SEL=-1;CUR.amb_resolved=row.amb_resolved||[];
  t.textContent=CUR.platform_name+' '+CUR.width+'x'+CUR.height;
  c.width=IMG.naturalWidth||IMG.width;c.height=IMG.naturalHeight||IMG.height;
  Z=Math.min(1,(document.querySelector('main').clientWidth-32)/c.width);applyZoom();
  DRAW=CUR.boxes.map(b=>({...b,approved:true}));computeAmb();
  if(AMB.idx.length)t.textContent+=' \\u26a0 '+AMB.idx.length+' ambigua(s)';
  paint();form();msg.textContent=NOTICE;msg.className=NOTICE?'warn':'';NOTICE='';
  DIRTY=false;updateDirty();};
 IMG.onerror=()=>{msg.textContent='ERRO ao carregar '+row.platform_name+': imagem indisponivel (anterior preservada)';msg.className='warn';};
 IMG.src='/img?id='+encodeURIComponent(id);}
function updateDirty(){dirty.style.display=DIRTY?'inline':'none';}
function markDirty(){DIRTY=true;updateDirty();}
function applyZoom(){c.style.width=(c.width*Z)+'px';zi.textContent=Math.round(Z*100)+'%';}
function zoom(f){Z=f===0?1:Math.min(4,Math.max(.2,Z*f));applyZoom();}
// --- edicao visual direta (coordenadas sempre normalizadas YOLO) ---
function dpos(e){const r=c.getBoundingClientRect();
 return {x:(e.clientX-r.left)/r.width,y:(e.clientY-r.top)/r.height,w:r.width,h:r.height};}
function boxAt(x,y){const EPS=1e-6;
 for(let i=DRAW.length-1;i>=0;i--){const b=DRAW[i];
 if(Math.abs(x-b.xc)<=b.w/2+EPS&&Math.abs(y-b.yc)<=b.h/2+EPS)return i;}return -1;}
// Ambiguidade e DERIVADA da geometria atual (recalculada a cada edicao),
// nunca estado fixo da proposta: classe/aprovacao nao a resolvem sozinhas.
// Classe= o que o objeto e. Aprovacao= juizo inclui/exclui. Ambiguidade=
// alerta geometrico com motivo. Selecao= foco de edicao (nao e anotacao).
function computeAmb(){AMB={idx:[],reasons:{},pairs:[]};if(!CUR)return AMB;
 const P=DRAW.map(b=>[b.class_id,(b.xc-b.w/2)*CUR.width,(b.yc-b.h/2)*CUR.height,
  (b.xc+b.w/2)*CUR.width,(b.yc+b.h/2)*CUR.height]);
 const sig=(a,b)=>JSON.stringify([[a.class_id,+a.xc.toFixed(4),+a.yc.toFixed(4),+a.w.toFixed(4),+a.h.toFixed(4)],
  [b.class_id,+b.xc.toFixed(4),+b.yc.toFixed(4),+b.w.toFixed(4),+b.h.toFixed(4)]].sort());
 for(let i=0;i<P.length;i++)for(let j=0;j<i;j++){
  const A=P[i],B=P[j];
  const inter=Math.max(0,Math.min(A[3],B[3])-Math.max(A[1],B[1]))*Math.max(0,Math.min(A[4],B[4])-Math.max(A[2],B[2]));
  const union=(A[3]-A[1])*(A[4]-A[2])+(B[3]-B[1])*(B[4]-B[2])-inter;
  const iou=union>0?inter/union:0,same=A[0]===B[0];
  const person=new Set([A[0],B[0]]),isPerson=person.has(0)&&person.has(2);
  if(iou>=0.8&&(same||isPerson)){
   const reason=(same?'duplicata (mesma classe, IoU '+iou.toFixed(2)+')':'pessoa x operador (IoU '+iou.toFixed(2)+')');
   AMB.pairs.push({a:j,b:i,iou:+iou.toFixed(4),reason,sig:sig(DRAW[j],DRAW[i])});
   if(!(j in AMB.reasons))AMB.reasons[j]=reason;
   if(!(i in AMB.reasons))AMB.reasons[i]=reason;}}
 AMB.idx=Object.keys(AMB.reasons).map(Number);return AMB;}
function isResolved(sg){return (CUR.amb_resolved||[]).some(r=>r.pair_sig===sg);}
function ambOf(i){const ps=AMB.pairs.filter(p=>p.a===i||p.b===i);
 if(!ps.length)return 'ok';return ps.every(p=>isResolved(p.sig))?'resolved':'amb';}
function reasonOf(i){const p=AMB.pairs.find(p=>p.a===i||p.b===i);return p?p.reason:'';}
function resolveAmb(i){const el=document.getElementById('ambnote'+i),note=(el&&el.value||'').trim();
 if(!note){msg.textContent='justificativa obrigatória p/ resolver a ambiguidade';msg.className='warn';return;}
 CUR.amb_resolved=CUR.amb_resolved||[];
 for(const p of AMB.pairs.filter(p=>p.a===i||p.b===i))
  if(!CUR.amb_resolved.some(r=>r.pair_sig===p.sig))
   CUR.amb_resolved.push({pair_sig:p.sig,note});
 markDirty();paint();form();msg.textContent='ambiguidade registrada (salve p/ persistir)';msg.className='ok';}
function reopenAmb(i){const alive=new Set(AMB.pairs.filter(p=>p.a===i||p.b===i).map(p=>p.sig));
 CUR.amb_resolved=(CUR.amb_resolved||[]).filter(r=>!alive.has(r.pair_sig));
 markDirty();paint();form();}
function liveResolved(){const bySig={};for(const p of AMB.pairs)bySig[p.sig]=[DRAW[p.a],DRAW[p.b]];
 const alive=new Set(AMB.pairs.map(p=>p.sig)),out=[];
 for(const r of (CUR.amb_resolved||[])){if(!alive.has(r.pair_sig))continue;
  const [a,b]=bySig[r.pair_sig];
  out.push({sig:r.pair_sig,pair:[[a.class_id,a.xc,a.yc,a.w,a.h],[b.class_id,b.xc,b.yc,b.w,b.h]],note:r.note});}
 return out;}
function cornerAt(i,x,y,tol){const b=DRAW[i];
 const cs=[['nw',b.xc-b.w/2,b.yc-b.h/2],['ne',b.xc+b.w/2,b.yc-b.h/2],
           ['sw',b.xc-b.w/2,b.yc+b.h/2],['se',b.xc+b.w/2,b.yc+b.h/2]];
 for(const [n,cx,cy]of cs)if(Math.abs(x-cx)<=tol&&Math.abs(y-cy)<=tol)return n;
 return null;}
c.onmousedown=e=>{if(e.button!==0||!CUR)return;const p=dpos(e);
 const i=boxAt(p.x,p.y);
 if(i>=0){SEL=i;const b0=DRAW[i],cn=cornerAt(i,p.x,p.y,12/Math.min(p.w,p.h));
  DRAG={mode:cn?'resize':'move',idx:i,corner:cn,sx:p.x,sy:p.y,
   orig:{xc:b0.xc,yc:b0.yc,w:b0.w,h:b0.h,
    x1:b0.xc-b0.w/2,y1:b0.yc-b0.h/2,x2:b0.xc+b0.w/2,y2:b0.yc+b0.h/2}};
  form();}
 else DRAG={mode:'maybe-add',sx:p.x,sy:p.y,moved:false};};
c.onmousemove=e=>{if(!CUR)return;const p=dpos(e);
 if(!DRAG){const i=boxAt(p.x,p.y);
  c.style.cursor=i<0?'crosshair':(cornerAt(i,p.x,p.y,12/Math.min(p.w,p.h))?'nwse-resize':'move');return;}
 if(Math.hypot(p.x-DRAG.sx,p.y-DRAG.sy)>0.004)DRAG.moved=true;
 if(!DRAG.moved||DRAG.mode==='maybe-add')return;
 const b=DRAW[DRAG.idx],o=DRAG.orig;
 if(DRAG.mode==='move'){b.xc=+clamp(o.xc+p.x-DRAG.sx,b.w/2,1-b.w/2).toFixed(4);
  b.yc=+clamp(o.yc+p.y-DRAG.sy,b.h/2,1-b.h/2).toFixed(4);}
 else{let x1=o.x1,y1=o.y1,x2=o.x2,y2=o.y2;const dx=p.x-DRAG.sx,dy=p.y-DRAG.sy;
  if(DRAG.corner.includes('e'))x2=clamp(o.x2+dx,o.x1+0.01,1);
  if(DRAG.corner.includes('s'))y2=clamp(o.y2+dy,o.y1+0.01,1);
  if(DRAG.corner.includes('w'))x1=clamp(o.x1+dx,0,o.x2-0.01);
  if(DRAG.corner.includes('n'))y1=clamp(o.y1+dy,0,o.y2-0.01);
  b.xc=+((x1+x2)/2).toFixed(4);b.yc=+((y1+y2)/2).toFixed(4);
  b.w=+(x2-x1).toFixed(4);b.h=+(y2-y1).toFixed(4);}
 markDirty();computeAmb();paint();};
c.onmouseup=e=>{if(!DRAG)return;const p=dpos(e);
 if(DRAG.mode==='maybe-add'&&!DRAG.moved&&p.x>=0&&p.x<=1&&p.y>=0&&p.y<=1){
  DRAW.push({class_id:SEL>=0?DRAW[SEL].class_id:0,
   xc:+clamp(p.x,0.05,0.95).toFixed(4),yc:+clamp(p.y,0.05,0.95).toFixed(4),
   w:0.1,h:0.1,approved:true});SEL=DRAW.length-1;markDirty();}
 DRAG=null;computeAmb();paint();form();};
c.onmouseleave=()=>{if(DRAG&&DRAG.moved){DRAG=null;computeAmb();paint();form();}};
function paint(){const x=c.getContext('2d');x.drawImage(IMG,0,0);
 const sx=c.width/CUR.width,sy=c.height/CUR.height;
 DRAW.forEach((b,i)=>{const[cl,xc,yc,w,h]=[b.class_id,b.xc,b.yc,b.w,b.h];
  const x1=(xc-w/2)*CUR.width*sx,y1=(yc-h/2)*CUR.height*sy,pw=w*CUR.width*sx,ph=h*CUR.height*sy;
  if(!b.approved){x.strokeStyle='#888';x.lineWidth=1;x.setLineDash([2,3]);
   x.strokeRect(x1,y1,pw,ph);x.setLineDash([]);x.fillStyle='#888';
   x.fillText(i+':['+cl+'] '+NAMES[cl]+' \\u2717',x1,y1-4);return;}
  const st=ambOf(i);
  x.strokeStyle=st==='amb'?'#ff0000':C[cl];x.lineWidth=(i===SEL?4:(st==='amb'?3:2));
  x.setLineDash(st==='amb'?[6,3]:[]);x.strokeRect(x1,y1,pw,ph);x.setLineDash([]);
  x.fillStyle=st==='amb'?'#ff0000':C[cl];
  x.fillText(i+':['+cl+'] '+NAMES[cl]+(st==='resolved'?' \\u2713rev':''),x1,y1-4);});
 if(SEL>=0&&DRAW[SEL]&&DRAW[SEL].approved){const b=DRAW[SEL];
  x.fillStyle='#fff';x.strokeStyle='#000';x.lineWidth=1;
  for(const px of [b.xc-b.w/2,b.xc+b.w/2])for(const py of [b.yc-b.h/2,b.yc+b.h/2]){
   const dx=px*CUR.width*sx,dy=py*CUR.height*sy;
   x.fillRect(dx-4,dy-4,8,8);x.strokeRect(dx-4,dy-4,8,8);}}}
// Sem onclick no container (era a causa dos controles mortos: todo clique
// borbulhava e reconstruia o formulario no meio da interacao).
function setBox(i,k,v){const b=DRAW[i];if(!b)return;
 if(k==='class_id'){v=+v;if(![0,1,2,3].includes(v))return;b.class_id=v;}
 else{v=+v;if(!isFinite(v))return;
  b[k]=+((k==='w'||k==='h')?clamp(v,0.01,1):clamp(v,0,1)).toFixed(4);
  b.xc=+clamp(b.xc,b.w/2,1-b.w/2).toFixed(4);b.yc=+clamp(b.yc,b.h/2,1-b.h/2).toFixed(4);}
 markDirty();computeAmb();paint();}
function form(){boxes.innerHTML=DRAW.map((b,i)=>{const st=b.approved?ambOf(i):'rej';
 let extra='';
 if(st==='amb')extra=`<br><span class=amb>\\u26a0 ${reasonOf(i)}</span><br>justificativa <input id=ambnote${i} size=28 placeholder="por que nao e problema"> <button onclick="resolveAmb(${i})">resolver</button>`;
 else if(st==='resolved'){const n=(CUR.amb_resolved||[]).find(r=>AMB.pairs.some(p=>p.sig===r.pair_sig&&(p.a===i||p.b===i)));
  extra=`<br><span class=ok>\\u2713 amb. resolvida: ${((n||{}).note||'').replace(/</g,'&lt;')}</span> <button onclick="reopenAmb(${i})">reabrir</button>`;}
 return `<div class="box ${i===SEL?'sel':''}"><button onclick="SEL=${i};paint();form()">sel</button>
 <label><input type=checkbox ${b.approved?'checked':''} onchange="DRAW[${i}].approved=this.checked;markDirty();computeAmb();paint();form()">${b.approved?'aprovada':'rejeitada'}</label>
 classe <select onchange="setBox(${i},'class_id',this.value)">${[0,1,2,3].map(k=>`<option value=${k} ${k===b.class_id?'selected':''}>${k} ${NAMES[k]}</option>`).join('')}</select>
 ${['xc','yc','w','h'].map(k=>`${k}<input type=number step=0.005 min=0 max=1 value=${b[k]} style=width:75px onchange="setBox(${i},'${k}',this.value)">`).join(' ')}
 <button onclick="DRAW.splice(${i},1);SEL=-1;markDirty();computeAmb();paint();form()">x</button>${extra}</div>`;}).join('');}
async function save(){const res=liveResolved();
 const r=await fetch('/api/decide',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({image_id:CUR.id,boxes:DRAW,note:note.value,coverage_complete:cov.checked,
  amb_resolutions:res.map(o=>({pair:o.pair,note:o.note}))})});
 const j=await r.json();msg.textContent=j.ok?'salvo':'ERRO '+(j.error||r.status);msg.className=j.ok?'ok':'warn';
 if(j.ok){CUR.status='visually_reviewed_pending_final_gates';CUR.boxes=DRAW.filter(b=>b.approved);CUR.nboxes=CUR.boxes.length;CUR.amb=[];
  const prevN=(CUR.amb_resolved||[]).length;
  CUR.amb_resolved=res.map(o=>({pair_sig:o.sig,note:o.note}));DECIDED++;
  const dropped=prevN-CUR.amb_resolved.length;
  DIRTY=false;updateDirty();note.value='';list();
  prog.textContent=DECIDED+'/'+ROWS.length;
  if(dropped>0)NOTICE=' ('+dropped+' resolução(ões) órfã(s): par alterado)';
  const nx=ROWS.find(r=>r.status.startsWith('pending'));
  if(nx)openImg(nx.id);else{msg.textContent+=' — fila concluída';if(NOTICE){msg.textContent+=NOTICE;NOTICE='';}}}}
document.onkeydown=e=>{if(e.target.tagName==='INPUT'||e.target.tagName==='SELECT')return;
 const i=ROWS.indexOf(CUR);
 if(e.key==='ArrowRight'||e.key==='ArrowLeft'){const n=ROWS[(i+(e.key==='ArrowRight'?1:-1)+ROWS.length)%ROWS.length];openImg(n.id);}
 else if(e.key==='+'||e.key==='=')zoom(1.25);else if(e.key==='-')zoom(0.8);
 else if(e.key>='0'&&e.key<='3'&&SEL>=0){setBox(SEL,'class_id',+e.key);form();}
 else if((e.key==='Delete'||e.key==='Backspace')&&SEL>=0){DRAW.splice(SEL,1);SEL=-1;markDirty();computeAmb();paint();form();}
 else if(e.key==='Enter')save();};
</script>"""

DUPES_PAGE = """<!doctype html><meta charset=utf-8><title>Dupes lado a lado</title>
<style>body{font-family:system-ui;margin:8px}.pair{display:flex;gap:8px;margin:12px 0;border-top:1px solid #ccc;padding-top:8px}
img{max-width:48%;border:1px solid #333}.meta{font-size:12px}.ok{color:green}.warn{color:#a60}</style>
<h3>Duplicatas <small id=prog></small> <a href=/>revisao</a></h3><div id=list></div>
<script>
let ITEMS=[];
fetch('/api/dupes').then(r=>r.json()).then(d=>{ITEMS=d.items;prog.textContent=d.pending+' pendentes, '+d.decided+' decididos';
 list.innerHTML=ITEMS.map((it,i)=>`<div class=pair><div><img src="/img?id=${it.a.id}"><div class=meta>${it.a.platform_name}<br>${it.a.width}x${it.a.height} grupo=${it.a.group||'?'}<br>origem=${it.a.source||'?'}<br>${it.a.status} ${it.a.nboxes}cx</div></div>
 <div><img src="/img?id=${it.b.id}"><div class=meta>${it.b.platform_name}<br>${it.b.width}x${it.b.height} grupo=${it.b.group||'?'}<br>origem=${it.b.source||'?'}<br>${it.b.status} ${it.b.nboxes}cx</div></div>
 <div><b>${it.tier}</b> score=${it.score}${it.hamming!=null?' ham='+it.hamming:''}<br>
 <input id=n${i} size=30 placeholder=nota> <button onclick="dec(${i},'duplicate')">duplicata</button> <button onclick="dec(${i},'not_duplicate')">nao-duplicata</button> <span id=m${i}></span></div></div>`).join('')
 ||'<p class=ok>Nada pendente.</p>';});
async function dec(i,verdict){const it=ITEMS[i];
 const r=await fetch('/api/dupe-decide',{method:'POST',headers:{'Content-Type':'application/json'},
  body:JSON.stringify({key:it.key,verdict,note:document.getElementById('n'+i).value})});
 const j=await r.json();document.getElementById('m'+i).textContent=j.ok?'salvo':'ERRO '+(j.error||r.status);
 if(j.ok)ITEMS.splice(i,1),setTimeout(()=>location.reload(),300);}
</script>"""


class Handler(BaseHTTPRequestHandler):
    outdir = None
    rows = {}
    dupes = None  # worklist dict ou None

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _serve_img(self, q):
        row = self.rows.get((q.get("id") or [""])[0])
        if not row or not Path(row["path"]).is_file():
            return self._send(404, "{}")
        p = Path(row["path"])
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(p.name)[0] or "image/jpeg")
        self.send_header("Content-Length", str(p.stat().st_size))
        self.end_headers()
        self.wfile.write(p.read_bytes())

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/dupes":
            return self._send(200, DUPES_PAGE, "text/html; charset=utf-8")
        if u.path == "/api/queue":
            rows, decided = [], 0
            for r in self.rows.values():
                boxes = [dict(class_id=c, xc=x, yc=y, w=w, h=h)
                         for c, x, y, w, h in r.get("boxes", [])]
                if r["status"].startswith("pending"):
                    rep = ambiguity_report(r.get("boxes", []), r["width"], r["height"])
                    amb, reasons = rep["box_idx"], rep["box_reasons"]
                else:
                    amb, reasons, decided = [], {}, decided + 1
                rows.append(dict(id=r["id"], platform_name=r["platform_name"],
                                 status=r["status"], width=r["width"], height=r["height"],
                                 boxes=boxes, nboxes=len(boxes), amb=amb,
                                 amb_reasons={str(k): v for k, v in reasons.items()},
                                 amb_resolved=r.get("amb_resolved", [])))
            return self._send(200, json.dumps(dict(rows=rows, decided=decided,
                                                   total=len(rows)), ensure_ascii=False))
        if u.path == "/img":
            return self._serve_img(parse_qs(u.query))
        if u.path == "/api/dupes":
            if self.dupes is None:
                return self._send(200, json.dumps(dict(items=[], pending=0, decided=0,
                                                        note="no dupes loaded")))
            dec = load_dupe_decisions(self.outdir)
            items = pending_dupe_items(self.dupes, dec)
            return self._send(200, json.dumps(dict(items=items, pending=len(items),
                                                   decided=len(dec)), ensure_ascii=False))
        return self._send(404, "{}")

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"] or 0)))
            if path == "/api/decide":
                row = self.rows.get(body.get("image_id"))
                if not row:
                    raise ValueError("unknown image")
                dec, updated = save_decision(self.outdir, row, body.get("boxes", []),
                                              body.get("note", ""),
                                              body.get("coverage_complete", False),
                                              body.get("amb_resolutions", []))
                self.rows[updated["id"]] = updated
                write_manifest(self.outdir / "review-manifest.ndjson", list(self.rows.values()))
                return self._send(200, json.dumps(dict(ok=True, kept=len(dec["boxes"]))))
            if path == "/api/dupe-decide":
                if self.dupes is None:
                    raise ValueError("no dupes loaded")
                keys = {i["key"] for i in self.dupes["items"]}
                if body.get("key") not in keys:
                    raise ValueError("unknown pair")
                dec = save_dupe_decision(self.outdir, body["key"], body.get("verdict", ""),
                                         body.get("note", ""))
                return self._send(200, json.dumps(dict(ok=True, verdict=dec["verdict"])))
            return self._send(404, "{}")
        except ValueError as e:
            return self._send(400, json.dumps(dict(ok=False, error=str(e))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--port", type=int, default=8787)
    ap.add_argument("--dupes", default=None, help="dupes.json gerado por opencode_dupes.py")
    a = ap.parse_args()
    Handler.rows, resumed = load_working_state(a.manifest, a.outdir)
    Handler.outdir = Path(a.outdir)
    Handler.outdir.mkdir(parents=True, exist_ok=True)
    if a.dupes:
        Handler.dupes = json.loads(Path(a.dupes).read_text(encoding="utf-8"))["worklist"]
    extra = f", {len(Handler.dupes['items'])} pares" if Handler.dupes else ""
    print(f"OpenCode review: {len(Handler.rows)} registros ({resumed} retomados)"
          f"{extra} -> http://localhost:{a.port}")
    HTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
