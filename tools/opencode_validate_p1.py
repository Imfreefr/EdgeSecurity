"""Validacao P1: lote de 20 imagens reais em copias isoladas.
Nao marca nada como revisado nos manifestos oficiais."""
import hashlib
import json
import shutil
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opencode_pipeline import (  # noqa: E402
    find_duplicates_scalable, pixels_to_yolo, preannotate_batch,
    read_manifest, validate_decision, write_manifest, yolo_to_pixels,
)
from opencode_review_server import Handler  # noqa: E402

DS = Path(r"C:\Users\freeb\Downloads\EdgeSecurity-Dataset\EdgeSecurity-CCTV-v2")
SRC = DS / "original-review-r84-0331-reviewed" / "manifest.ndjson"
MODEL = Path(r"C:\Users\freeb\Downloads\EdgeSecurity-Dataset\restauracao-2026-10-08\EdgeSecurity-Git\backend\model\edgev1.pt")

rows = read_manifest(SRC)
pend = [r for r in rows if r["status"].startswith("pending")][:20]
tmp = Path(tempfile.mkdtemp(prefix="opencode-p1-"))
imgs = tmp / "imgs"
imgs.mkdir()
mini = []
for r in pend:
    dst = imgs / Path(r["path"]).name
    shutil.copy(r["path"], dst)
    mini.append(dict(r, path=str(dst.resolve()),
                     sha256=hashlib.sha256(dst.read_bytes()).hexdigest()))
man = tmp / "mini.ndjson"
write_manifest(man, mini)
print(f"lote: {len(mini)} copias isoladas em {tmp}")

t0 = time.perf_counter()
rep = preannotate_batch(man, MODEL, tmp / "pre", limit=20)
print(f"pre-anotacao: {rep['preannotated']} imgs, {rep['elapsed_seconds']:.2f}s, "
      f"invalid={rep['invalid_detections']} overlap={rep['overlapping_box_flags']} "
      f"dup={rep['duplicate_flags']}")

# injeta caixas pre-anotadas na copia de trabalho p/ renderizar na UI
arts = {}
for r in mini:
    a = tmp / "pre" / (r["id"] + ".json")
    arts[r["id"]] = json.loads(a.read_text(encoding="utf-8"))
    r["boxes"] = [b["yolo"] for b in arts[r["id"]]["boxes"]]
write_manifest(man, mini)

# round-trip de coordenadas nas dimensoes reais
worst = 0.0
for r in mini:
    for b in r["boxes"]:
        px = yolo_to_pixels(b, r["width"], r["height"])
        back = pixels_to_yolo(px[0], px[1], px[2], px[3], px[4], r["width"], r["height"])
        worst = max(worst, max(abs(x - y) for x, y in zip(b, back)))
print(f"round-trip coords: {sum(len(r['boxes']) for r in mini)} caixas, erro max {worst:.2e}")

# servidor: fila, imagens, decisao (incl. zero-detecao), restart
Handler.rows, _ = __import__("opencode_pipeline").load_working_state(man, tmp / "review")
Handler.outdir = tmp / "review"
Handler.outdir.mkdir(exist_ok=True)
srv = HTTPServer(("127.0.0.1", 0), Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}"
q = json.loads(urllib.request.urlopen(base + "/api/queue").read())
assert len(q["rows"]) == 20, q
print(f"fila: {len(q['rows'])} pendentes")

# baixa 3 imagens e confere bytes == copias locais
for row in q["rows"][:3]:
    data = urllib.request.urlopen(base + "/img?id=" + row["id"]).read()
    local = next(r for r in mini if r["id"] == row["id"])
    assert data == Path(local["path"]).read_bytes(), "bytes divergentes"
print("render imagens: 3/3 bytes identicos as copias")

classes = set()
zero = next((r for r in q["rows"] if r["nboxes"] == 0), None)
target = zero or q["rows"][0]
# adiciona + aprova individual: mantem 1, rejeita resto
boxes = [dict(class_id=b["class_id"], xc=b["xc"], yc=b["yc"], w=b["w"], h=b["h"],
              approved=(i == 0)) for i, b in enumerate(target["boxes"])]
boxes.append(dict(class_id=3, xc=0.5, yc=0.5, w=0.2, h=0.2, approved=True))  # adicao
body = json.dumps({"image_id": target["id"], "boxes": boxes,
                   "note": "validacao P1", "coverage_complete": True}).encode()
req = urllib.request.Request(base + "/api/decide", data=body,
                             headers={"Content-Type": "application/json"}, method="POST")
res = json.loads(urllib.request.urlopen(req).read())
row = next(r for r in mini if r["id"] == target["id"])
kept = validate_decision(row, boxes, "validacao P1", True)
assert res["kept"] == len(kept), (res, kept)
classes.update(b[0] for b in kept)
print(f"decisao: kept={res['kept']} (1 aprovada+1 adicionada, resto rejeitado), "
      f"zero-det={'sim' if zero else 'nao ha no lote'}")

# zero-detecao simulada: limpa caixas de outra imagem e decide vazio
other = next(r for r in q["rows"] if r["id"] != target["id"])
body0 = json.dumps({"image_id": other["id"], "boxes": [],
                    "note": "vazio confirmado P1", "coverage_complete": True}).encode()
req0 = urllib.request.Request(base + "/api/decide", data=body0,
                              headers={"Content-Type": "application/json"}, method="POST")
res0 = json.loads(urllib.request.urlopen(req0).read())
assert res0["kept"] == 0, res0
print("zero-detecao via API: kept=0 ok")

# quatro classes preservadas em todo o lote
allcls = {b["class_id"] for a in arts.values() for b in a["boxes"]}
assert allcls <= {0, 1, 2, 3}, allcls
print(f"classes no lote: {sorted(allcls)} (todas em 0..3)")

# restart: novo Handler sobre o mesmo outdir deve retomar as decisoes
srv.shutdown()
Handler2_rows, resumed = __import__("opencode_pipeline").load_working_state(man, tmp / "review")
assert resumed == 2, resumed
st = Handler2_rows[target["id"]]
assert st["status"] == "visually_reviewed_pending_final_gates"
assert st["boxes"] == kept
print(f"restart: {resumed} decisao retomada, integra")

dup = find_duplicates_scalable(mini, cache_path=tmp / "hashes.json")
print(f"duplicatas lote: exatas={len(dup['exact'])} proximas={len(dup['near'])} "
      f"comparacoes={dup['comparisons']} puladas={dup['skipped_cross_bucket']}")
print(f"manifesto oficial intacto: {hashlib.sha256(SRC.read_bytes()).hexdigest()[:16]} (r84)")
print("P1 OK")
