"""Interface local de revisao OpenCode (stdlib apenas). Nao altera manifestos oficiais.

Uso:
  .venv/Scripts/python tools/opencode_review_server.py --manifest <copia.ndjson> --outdir <dir-isolado> --port 8787
Abre http://localhost:8787 . Decisoes salvas em outdir/decisions/<id>.json
e outdir/review-manifest.ndjson (copia de trabalho).
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
    load_working_state, save_decision, write_manifest,
)

PAGE = """<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>OpenCode Review Local</title>
<style>body{font-family:system-ui;margin:0;display:flex;height:100vh}aside{width:300px;overflow:auto;border-right:1px solid #ccc;padding:8px}
main{flex:1;overflow:auto;padding:8px}canvas{max-width:100%;border:1px solid #333;cursor:crosshair}
.box{border:1px solid #ccc;margin:4px 0;padding:4px;font-size:12px}.ok{color:green}.warn{color:#a60}</style>
<aside><h3>Fila</h3><div id=q></div></aside>
<main><h3 id=t></h3><canvas id=c></canvas><div id=boxes></div>
<label>Nota <input id=note size=60 placeholder="motivo da decisao"></label>
<label><input type=checkbox id=cov> cobertura completa</label>
<button onclick="save()">Salvar decisao</button> <span id=msg></span></main>
<script>
let ROWS=[],CUR=null,IMG=new Image(),DRAW=[];
const C=['#00ff70','#ffaa00','#00cfff','#dd77ff'];
fetch('/api/queue').then(r=>r.json()).then(d=>{ROWS=d.rows;
 q.innerHTML=ROWS.map(r=>`<div><a href=# onclick="open('${r.id}');return false">${r.platform_name}</a> <small>${r.status} ${r.nboxes}cx</small></div>`).join('');
 if(ROWS.length)open(ROWS[0].id);});
function open(id){CUR=ROWS.find(r=>r.id===id);
 t.textContent=CUR.platform_name+' '+CUR.width+'x'+CUR.height;
 IMG.onload=()=>{c.width=IMG.width;c.height=IMG.height;DRAW=CUR.boxes.map(b=>({...b,approved:true}));paint();form();};
 IMG.src='/img?id='+encodeURIComponent(id);}
function paint(){const x=c.getContext('2d');x.drawImage(IMG,0,0);
 const sx=c.width/CUR.width,sy=c.height/CUR.height;
 DRAW.forEach((b,i)=>{if(!b.approved)return;const[cl,xc,yc,w,h]=[b.class_id,b.xc,b.yc,b.w,b.h];
  x.strokeStyle=C[cl];x.lineWidth=2;
  x.strokeRect((xc-w/2)*CUR.width*sx,(yc-h/2)*CUR.height*sy,w*CUR.width*sx,h*CUR.height*sy);
  x.fillStyle=C[cl];x.fillText(i+':'+cl,(xc-w/2)*CUR.width*sx,(yc-h/2)*CUR.height*sy-4);});}
c.onclick=e=>{const r=c.getBoundingClientRect();
 const xc=(e.clientX-r.left)/r.width,yc=(e.clientY-r.top)/r.height;
 DRAW.push({class_id:0,xc:+xc.toFixed(4),yc:+yc.toFixed(4),w:0.1,h:0.1,approved:true});paint();form();};
function form(){boxes.innerHTML=DRAW.map((b,i)=>`<div class=box><label><input type=checkbox ${b.approved?'checked':''} onchange="DRAW[${i}].approved=this.checked;paint()"> aprovar</label>
 classe <select onchange="DRAW[${i}].class_id=+this.value;paint()">${[0,1,2,3].map(k=>`<option ${k===b.class_id?'selected':''}>${k}</option>`).join('')}</select>
 ${['xc','yc','w','h'].map(k=>`${k}<input type=number step=0.001 min=0 max=1 value=${b[k]} style=width:70px onchange="DRAW[${i}].${k}=+this.value;paint()">`).join(' ')}
 <button onclick="DRAW.splice(${i},1);paint();form()">x</button></div>`).join('');}
async function save(){const r=await fetch('/api/decide',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({image_id:CUR.id,boxes:DRAW,note:note.value,coverage_complete:cov.checked})});
 msg.textContent=(await r.json()).ok?'salvo':'ERRO '+r.status;msg.className=r.ok?'ok':'warn';}
</script>"""


class Handler(BaseHTTPRequestHandler):
    manifest = None
    outdir = None
    rows = {}

    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            return self._send(200, PAGE, "text/html; charset=utf-8")
        if u.path == "/api/queue":
            rows = [dict(id=r["id"], platform_name=r["platform_name"], status=r["status"],
                          width=r["width"], height=r["height"],
                          boxes=[dict(class_id=c, xc=x, yc=y, w=w, h=h)
                                 for c, x, y, w, h in r.get("boxes", [])],
                          nboxes=len(r.get("boxes", [])))
                    for r in self.rows.values() if r["status"].startswith("pending")]
            return self._send(200, json.dumps(dict(rows=rows), ensure_ascii=False))
        if u.path == "/img":
            q = parse_qs(u.query)
            row = self.rows.get((q.get("id") or [""])[0])
            if not row or not Path(row["path"]).is_file():
                return self._send(404, "{}")
            p = Path(row["path"])
            self.send_response(200)
            self.send_header("Content-Type", mimetypes.guess_type(p.name)[0] or "image/jpeg")
            self.send_header("Content-Length", str(p.stat().st_size))
            self.end_headers()
            self.wfile.write(p.read_bytes())
            return
        return self._send(404, "{}")

    def do_POST(self):
        if urlparse(self.path).path != "/api/decide":
            return self._send(404, "{}")
        try:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"] or 0)))
            row = self.rows.get(body.get("image_id"))
            if not row:
                raise ValueError("unknown image")
            dec, updated = save_decision(self.outdir, row, body.get("boxes", []),
                                         body.get("note", ""),
                                         body.get("coverage_complete", False))
            self.rows[updated["id"]] = updated
            write_manifest(self.outdir / "review-manifest.ndjson", list(self.rows.values()))
            return self._send(200, json.dumps(dict(ok=True, kept=len(dec["boxes"]))))
        except ValueError as e:
            return self._send(400, json.dumps(dict(ok=False, error=str(e))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--port", type=int, default=8787)
    a = ap.parse_args()
    Handler.rows, resumed = load_working_state(a.manifest, a.outdir)
    Handler.outdir = Path(a.outdir)
    Handler.outdir.mkdir(parents=True, exist_ok=True)
    print(f"OpenCode review: {len(Handler.rows)} registros ({resumed} retomados)"
          f" -> http://localhost:{a.port}")
    HTTPServer(("127.0.0.1", a.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
