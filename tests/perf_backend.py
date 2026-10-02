"""Real FastAPI/security checks with disposable SQLite tenants, never production writes.
Run: .venv/Scripts/python tests/perf_backend.py [--serve]
Only camera inference libraries are stubbed, as in the serverless entrypoint.
"""
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
temporary = tempfile.TemporaryDirectory()
os.environ.pop("DATABASE_URL", None)
os.environ.pop("SUPABASE_DB_URL", None)
os.environ.update(DB_PATH=str(Path(temporary.name) / "test.db"), EDGE_PERF_DEBUG="1",
    AUTH_SECRET="isolated-test-secret", SUPER_ADMIN_EMAIL="root@example.invalid",
    SUPER_ADMIN_PASSWORD="isolated-test-password", CORS_ORIGINS="http://127.0.0.1:5503",
    AI_LOCAL="false", COOKIE_SECURE="false")
sys.modules["cv2"] = MagicMock()
sys.modules["ultralytics"] = MagicMock()
import app as m
from fastapi.testclient import TestClient

m.init_db()
with m.conn() as db:
    for cid in ("tenant-a", "tenant-b"):
        db.execute("INSERT INTO companies(id,razao_social,nome_fantasia,cnpj,email,status,criado_em,atualizado_em) VALUES(?,?,?,?,?,'ativa',?,?)",
            (cid,cid,cid,cid,cid+"@example.invalid",m.now(),m.now()))
        db.execute("INSERT INTO subscriptions(id,company_id,status,valor,criado_em,atualizado_em) VALUES(?,?,'ativa',149.90,?,?)",(cid,cid,m.now(),m.now()))
    for uid,cid,role in (("admin-a","tenant-a","administrador"),("admin-b","tenant-b","administrador"),("member-b","tenant-b","usuario")):
        db.execute("INSERT INTO usuarios(id,nome,email,senha_hash,cargo,status,criado_em,company_id,administrador_primario) VALUES(?,?,?,?,?,'ativo',?,?,?)",
            (uid,uid,uid+"@example.invalid",m.hash_password("test-password-123"),role,m.now(),cid,role=="administrador"))
        perms=m.default_permissions(role)
        db.execute("INSERT INTO permissoes(usuario_id,"+",".join(m.PERMISSION_KEYS)+") VALUES(?"+",?"*len(m.PERMISSION_KEYS)+")",(uid,*[int(perms[k]) for k in m.PERMISSION_KEYS]))

if "--serve" in sys.argv:
    import uvicorn
    from fastapi.staticfiles import StaticFiles
    from fastapi.responses import FileResponse
    @m.app.middleware("http")
    async def static_headers(request, call_next):
        response = await call_next(request)
        # Production static files are served by Vercel, outside FastAPI middleware.
        if not request.url.path.startswith("/api/"):
            del response.headers["content-security-policy"]
        return response
    for folder in ("pages", "js", "css", "assets"):
        m.app.mount("/"+folder,StaticFiles(directory=ROOT/folder),name=folder)
    @m.app.get("/index.html")
    def login_page():
        return FileResponse(ROOT/"index.html")
    uvicorn.run(m.app,host="127.0.0.1",port=8000)
    sys.exit()

def login(client, name):
    response=client.post("/api/auth/login",json={"username":name+"@example.invalid","password":"test-password-123"})
    assert response.status_code==200,response.text
    return {"Authorization":"Bearer "+response.json()["token"]}

with TestClient(m.app) as client:
    admin=login(client,"admin-a")
    samples=[]
    for endpoint in ("/me","/cameras","/alerts","/users","/activities","/monitor/usuarios","/reports"):
        response=client.get("/api"+endpoint,headers=admin)
        assert response.status_code==200,(endpoint,response.text)
        samples.append({"endpoint":endpoint,"status":response.status_code,"queries":int(response.headers["X-Edge-DB-Queries"]),"server_timing":response.headers["Server-Timing"]})
    users=client.get("/api/users",headers=admin).json()
    assert [u["id"] for u in users]==["admin-a"]
    assert "senha_hash" not in users[0]
    other=login(client,"admin-b")
    assert {u["company_id"] for u in client.get("/api/users",headers=other).json()}=={"tenant-b"}
    assert client.put("/api/users/admin-a",headers=other,json={"nome":"unauthorized","email":"a@example.invalid","cargo":"administrador","status":"ativo","permissoes":{},"cameras":[]}).status_code==403
    member=login(client,"member-b")
    assert client.get("/api/users",headers=member).status_code==403
    with m.conn() as db:
        db.execute("UPDATE permissoes SET visualizar_cameras=0 WHERE usuario_id='member-b'")
    assert client.get("/api/cameras",headers=member).status_code==403
    with m.conn() as db:
        db.execute("UPDATE companies SET status='bloqueada' WHERE id='tenant-a'")
    assert client.get("/api/users",headers=admin).status_code==403
    with m.conn() as db:
        db.execute("UPDATE companies SET status='ativa' WHERE id='tenant-a'")
    client.cookies.clear()
    for _ in range(3):
        assert client.get("/api/me",headers=admin).status_code==200
    assert client.get("/api/users").status_code==401
    assert client.get("/api/users",headers={"Authorization":"Bearer invalid"}).status_code==401
    assert client.post("/api/auth/logout",headers=admin).status_code==200
    assert client.get("/api/me",headers=admin).status_code==401
    os.environ["EDGE_PERF_DEBUG"]="0"
    assert "Server-Timing" not in client.get("/api/health").headers
    result={"scope":"isolated SQLite, real FastAPI and auth; not production latency", "samples":samples,"security":"PASS: tenant isolation, foreign edit rejection, member role, live permission revocation, blocked company, Bearer refresh/navigation, invalid token and logout"}
    if os.getenv("EDGE_PERF_LOCAL_OUTPUT"):
        Path(os.environ["EDGE_PERF_LOCAL_OUTPUT"]).write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
