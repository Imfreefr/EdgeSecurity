"""Validacao item 2: classe 3 (carga) em copias isoladas.
Diferencia falha da UI vs ausencia de deteccao pelo modelo."""
import hashlib
import json
import shutil
import sys
import tempfile
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opencode_pipeline import (  # noqa: E402
    export_approved, load_working_state, preannotate_batch, read_manifest, write_manifest,
)
from opencode_review_server import Handler  # noqa: E402

DS = Path(r"C:\Users\freeb\Downloads\EdgeSecurity-Dataset\EdgeSecurity-CCTV-v2")
SRC = DS / "original-review-r84-0331-reviewed" / "manifest.ndjson"
MODEL = Path(r"C:\Users\freeb\Downloads\EdgeSecurity-Dataset\restauracao-2026-10-08\EdgeSecurity-Git\backend\model\edgev1.pt")

rows = read_manifest(SRC)
# pendentes que ja trazem proposta classe 3 (p Camera/yard: 0307/0308 + vizinhos)
cands = [r for r in rows if r["status"] == "pending_individual_visual_review"
         and any(b[0] == 3 for b in r.get("boxes", []))][:6]
assert cands, "sem pendentes com classe 3"
tmp = Path(tempfile.mkdtemp(prefix="opencode-cargo-"))
imgs = tmp / "imgs"
imgs.mkdir()
mini = []
for r in cands:
    dst = imgs / Path(r["path"]).name
    shutil.copy(r["path"], dst)
    mini.append(dict(r, path=str(dst.resolve()),
                     sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
man = tmp / "mini.ndjson"
write_manifest(man, mini)
print(f"lote carga: {[r['platform_name'] for r in mini]}")

# 1. o modelo detecta classe 3 nessas imagens? (copias p/ pre-anotacao)
pre_man = tmp / "pre-man.ndjson"
write_manifest(pre_man, [dict(r, boxes=[]) for r in mini])
rep = preannotate_batch(pre_man, MODEL, tmp / "pre", limit=len(mini))
model_c3 = {}
for r in mini:
    a = json.loads((tmp / "pre" / (r["id"] + ".json")).read_text(encoding="utf-8"))
    cls = sorted({b["class_id"] for b in a["boxes"]})
    model_c3[r["platform_name"]] = cls
print(f"modelo edgev1 classes por img: {model_c3}")

# 2. UI: fila expoe classe 3? editar + salvar + exportar
Handler.rows, _ = load_working_state(man, tmp / "review")
Handler.outdir = tmp / "review"
Handler.outdir.mkdir(exist_ok=True)
srv = HTTPServer(("127.0.0.1", 0), Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}"
q = json.loads(urllib.request.urlopen(base + "/api/queue").read())
shown_c3 = sum(1 for r in q["rows"] for b in r["boxes"] if b["class_id"] == 3)
print(f"UI exibe {shown_c3} caixas classe 3 em {len(q['rows'])} imgs")
assert shown_c3 > 0, "UI nao exibiu classe 3: falha da interface"

# edita uma caixa classe 3 (muda xc) e aprova so ela
target = next(r for r in q["rows"] if any(b["class_id"] == 3 for b in r["boxes"]))
boxes = []
for b in target["boxes"]:
    nb = dict(b, approved=(b["class_id"] == 3))
    if b["class_id"] == 3 and not boxes:
        nb["xc"] = round(min(0.95, b["xc"] + 0.005), 4)
    boxes.append(nb)
body = json.dumps({"image_id": target["id"], "boxes": boxes,
                   "note": "validacao cargo", "coverage_complete": True}).encode()
req = urllib.request.Request(base + "/api/decide", data=body,
                             headers={"Content-Type": "application/json"}, method="POST")
res = json.loads(urllib.request.urlopen(req).read())
assert res["ok"], res
srv.shutdown()

# 3. export: working manifest -> YOLO txt com linhas "3 "
wrows = read_manifest(tmp / "review" / "review-manifest.ndjson")
rep_e = export_approved(wrows, tmp / "yolo")
txts = list((tmp / "yolo").glob("*.txt"))
c3lines = sum(1 for t in txts for l in t.read_text().splitlines() if l.startswith("3 "))
print(f"export: {rep_e['exported']} imgs, {c3lines} linhas classe 3 em {len(txts)} txt")
assert c3lines > 0, "export sem classe 3: falha da interface"
print(f"oficial intacto: {hashlib.sha256(SRC.read_bytes()).hexdigest()[:16]}")
print("CARGO OK")
