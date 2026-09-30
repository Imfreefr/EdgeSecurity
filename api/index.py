import sys
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

os.environ.setdefault("DB_PATH", "/tmp/edgesecurity.db")
os.environ.setdefault("MODEL_PATH", str(ROOT / "backend" / "model" / "edgev1-int8.onnx"))
os.environ["AI_LOCAL"] = "false"

from unittest.mock import MagicMock
sys.modules.setdefault("cv2", MagicMock())
sys.modules.setdefault("ultralytics", MagicMock())

from backend.app import app

try:
    import backend.app as _m
    _m.init_db()
    with _m.conn() as db:
        if not db.execute("SELECT 1 FROM usuarios WHERE lower(email)=?", ("teste@empresateste.com",)).fetchone():
            import secrets
            from datetime import datetime, timezone, timedelta
            cid = secrets.token_hex(12)
            uid = secrets.token_hex(12)
            sid = secrets.token_hex(12)
            pid = secrets.token_hex(12)
            tid = secrets.token_hex(12)
            cnpj_raw = "98512962360333"
            cnpj_store = _m._encrypt(cnpj_raw) if _m.DATA_ENCRYPTION_KEY else cnpj_raw
            n = _m.now()
            venc = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            db.execute("INSERT INTO companies(id,razao_social,nome_fantasia,cnpj,email,telefone,endereco,cidade,estado,status,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (cid, "Empresa Teste Vercel LTDA", "Empresa Teste", cnpj_store, "contato@empresateste.com", "(11) 99999-0000", "Rua Teste, 123", "Sao Paulo", "SP", "ativa", n, n))
            db.execute("INSERT INTO usuarios(id,nome,email,senha_hash,cargo,status,criado_em,administrador_primario,company_id) VALUES(?,?,?,?,?,?,?,?,?)",
                (uid, "Admin Teste", "teste@empresateste.com", _m.hash_password("Teste1234"), "administrador", "ativo", n, True, cid))
            perms = _m.default_permissions("administrador")
            db.execute("INSERT INTO permissoes(usuario_id," + ",".join(_m.PERMISSION_KEYS) + ") VALUES(?" + ",?" * len(_m.PERMISSION_KEYS) + ")", (uid, *[bool(perms[k]) for k in _m.PERMISSION_KEYS]))
            db.execute("INSERT INTO subscriptions(id,company_id,status,valor,data_inicio,data_vencimento,ultimo_pagamento,proximo_vencimento,transacao_id,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                (sid, cid, "ativa", _m.SUBSCRIPTION_VALUE, n, venc, n, venc, tid, n, n))
            db.execute("INSERT INTO payments(id,company_id,subscription_id,valor,status,data_cobranca,data_pagamento,transacao_id,metodo,criado_em) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (pid, cid, sid, _m.SUBSCRIPTION_VALUE, "pago", n, n, tid, "pix", n))
            print("seed teste@empresateste.com criado")
except Exception as e:
    print(f"seed teste falhou: {e}")
