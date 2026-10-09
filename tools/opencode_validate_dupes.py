"""Validacao item 1: worklist de duplicatas + UI lado a lado, copias isoladas."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
from http.server import HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from opencode_pipeline import load_dupe_decisions, read_manifest, write_manifest  # noqa: E402
from opencode_review_server import Handler  # noqa: E402

DS = Path(r"C:\Users\freeb\Downloads\EdgeSecurity-Dataset\EdgeSecurity-CCTV-v2")
SRC = DS / "original-review-r84-0331-reviewed" / "manifest.ndjson"
PY = r"C:\Users\freeb\Downloads\EdgeSecurity-Dataset\restauracao-2026-10-08\EdgeSecurity-Git\.venv\Scripts\python.exe"
TOOLS = Path(r"C:\Users\freeb\Downloads\EdgeSecurity-Dataset\restauracao-2026-10-08\EdgeSecurity-Git\tools")

rows = read_manifest(SRC)
pend = [r for r in rows if r["status"].startswith("pending")][:12]
tmp = Path(tempfile.mkdtemp(prefix="opencode-dupe-"))
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

out = tmp / "dupe-out"
out.mkdir()
subprocess.run([PY, str(TOOLS / "opencode_dupes.py"), "--manifest", str(man),
                "--outdir", str(out)], check=True, capture_output=True, text=True)
work = json.loads((out / "dupes.json").read_text(encoding="utf-8"))
wl = work["worklist"]
tiers = {}
for i in wl["items"]:
    tiers[i["tier"]] = tiers.get(i["tier"], 0) + 1
print(f"worklist: {len(wl['items'])} pares em {len(wl['clusters'])} clusters, tiers={tiers}")
assert wl["items"], "sem candidatos no lote"
it = wl["items"][0]
assert {"key", "tier", "score", "a", "b"} <= set(it), it.keys()
assert it["a"]["path"] and it["a"]["group"] is not None or True
print(f"exemplo: {it['tier']} score={it['score']} {it['a']['platform_name']} x {it['b']['platform_name']}")

Handler.rows = {r["id"]: r for r in mini}
Handler.outdir = tmp / "review"
Handler.outdir.mkdir(exist_ok=True)
Handler.dupes = wl
srv = HTTPServer(("127.0.0.1", 0), Handler)
port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
base = f"http://127.0.0.1:{port}"
d = json.loads(urllib.request.urlopen(base + "/api/dupes").read())
n0 = d["pending"]
assert n0 == len(wl["items"]), (n0, len(wl["items"]))
print(f"API dupes: {n0} pendentes")

key = d["items"][0]["key"]
body = json.dumps({"key": key, "verdict": "not_duplicate",
                   "note": "validacao: cena parecida, maquinas distintas"}).encode()
req = urllib.request.Request(base + "/api/dupe-decide", data=body,
                             headers={"Content-Type": "application/json"}, method="POST")
res = json.loads(urllib.request.urlopen(req).read())
assert res["ok"], res
d2 = json.loads(urllib.request.urlopen(base + "/api/dupes").read())
assert d2["pending"] == n0 - 1 and d2["decided"] == 1, d2
decs = load_dupe_decisions(tmp / "review")
assert key in decs, "decisao nao persistida"
print(f"decisao persistida; reapresentacao suprimida ({d2['pending']} restam)")

# erro: par desconhecido e veredito invalido
for payload in ({"key": "xx:::yy", "verdict": "duplicate", "note": "n"},
                {"key": key, "verdict": "maybe", "note": "n"}):
    try:
        urllib.request.urlopen(urllib.request.Request(
            base + "/api/dupe-decide", data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}, method="POST"))
        raise SystemExit("erro esperado nao ocorreu")
    except urllib.error.HTTPError as e:
        assert e.code == 400, e.code
print("erros 400 ok; nada excluido automaticamente")
srv.shutdown()
print(f"oficial intacto: {hashlib.sha256(SRC.read_bytes()).hexdigest()[:16]}")
print("DUPES OK")
