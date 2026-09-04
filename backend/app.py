from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Header, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, StreamingResponse
import cv2
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator
from services.detector import SafetyDetector
from services.risk_engine import assess_risk
import base64
import json
try:
    import httpx
except ImportError:
    httpx = None

try:
    from services.payment_service import PaymentService
except Exception:
    PaymentService = None

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "edgesecurity.db")))
_raw_cors = os.getenv("CORS_ORIGINS", "http://localhost:5500,http://127.0.0.1:5500").strip()
if _raw_cors == "*":
    raise RuntimeError("CORS_ORIGINS='*' proibido — configure origens explicitas.")
CORS_ORIGINS = [o.strip() for o in _raw_cors.split(",") if o.strip()]

SUBSCRIPTION_VALUE = float(os.getenv("SUBSCRIPTION_VALUE", "149.90"))
_raw_super_email = os.getenv("SUPER_ADMIN_EMAIL", "").strip().lower()
_raw_super_pass = os.getenv("SUPER_ADMIN_PASSWORD", "")
if not _raw_super_email or not _raw_super_pass:
    _raw_super_email = "admin@edgesecurity.com"
    _raw_super_pass = secrets.token_urlsafe(16)
    print("AVISO: SUPER_ADMIN_* nao configurado — usando credencial efemera gerada, defina no .env para producao.")
SUPER_ADMIN_EMAIL = _raw_super_email
SUPER_ADMIN_PASSWORD = _raw_super_pass
SUPER_ADMIN_NAME = os.getenv("SUPER_ADMIN_NAME", "Administrador Master")
PAYMENT_MOCK = os.getenv("PAYMENT_MOCK", "true").lower() in ("1", "true", "yes")
WEBHOOK_SECRET = os.getenv("PAYMENT_WEBHOOK_SECRET", "")
MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN", "").strip()
MP_PREAPPROVAL_URL = os.getenv("MP_PREAPPROVAL_URL", "https://api.mercadopago.com/preapproval").strip()
DATA_ENCRYPTION_KEY = os.getenv("DATA_ENCRYPTION_KEY", "").strip()
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() in ("1", "true", "yes")

if PAYMENT_MOCK and MP_ACCESS_TOKEN:
    print("AVISO: PAYMENT_MOCK=true com MP_ACCESS_TOKEN definido — mock deve ser false em producao.")

app = FastAPI(title="EdgeSecurity API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type", "X-Requested-With", "X-Webhook-Signature"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    ct = request.headers.get("content-type", "")
    if "multipart/form-data" in ct:
        return JSONResponse({"detail": "Upload não permitido."}, status_code=415)
    clen = request.headers.get("content-length")
    if clen and clen.isdigit() and int(clen) > 2_000_000:
        return JSONResponse({"detail": "Payload muito grande."}, status_code=413)
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "camera=(self), microphone=(self)"
    resp.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' https://unpkg.com https://fonts.googleapis.com; style-src 'self' https://fonts.googleapis.com https://unpkg.com; font-src https://fonts.gstatic.com https://unpkg.com; img-src 'self' data: blob:; connect-src 'self' https://api.mercadopago.com"
    resp.headers["Cache-Control"] = "no-store"
    return resp

SESSIONS: dict[str, dict[str, Any]] = {}
SESSION_IDLE_TIMEOUT = int(os.getenv("SESSION_IDLE_TIMEOUT", str(8 * 60 * 60)))
CAMERA_TEST_TIMEOUT = float(os.getenv("CAMERA_TEST_TIMEOUT", "8"))
CAMERA_IDLE_TIMEOUT = int(os.getenv("CAMERA_IDLE_TIMEOUT", "35"))
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_MAX_ATTEMPTS", "5"))
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_WINDOW_SECONDS", "300"))
LOGIN_ATTEMPTS: dict[str, list[float]] = {}
MODEL_PATH = os.getenv("MODEL_PATH", str(BASE_DIR / "model" / "edgev1.pt"))
AI_CONFIDENCE = float(os.getenv("AI_CONFIDENCE", "0.40"))
AI_IOU = float(os.getenv("AI_IOU", "0.50"))
_detector = None
_detector_error = None
_last_risk_alert = {}

PERMISSION_KEYS = [
    "visualizar_cameras",
    "usar_camera_dispositivo",
    "gerenciar_cameras",
    "visualizar_alertas",
    "visualizar_relatorios",
    "gerenciar_usuarios",
    "gerenciar_permissoes",
    "acessar_configuracoes",
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    return c


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 120_000)
    return f"pbkdf2_sha256$120000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        alg, rounds, salt_hex, digest_hex = encoded.split("$")
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(rounds)).hex()
        return alg == "pbkdf2_sha256" and hmac.compare_digest(candidate, digest_hex)
    except Exception:
        return False


def default_permissions(cargo: str) -> dict[str, bool]:
    admin = cargo == "administrador"
    return {k: (True if k in ("visualizar_cameras", "usar_camera_dispositivo", "visualizar_alertas", "visualizar_relatorios", "acessar_configuracoes") else admin) for k in PERMISSION_KEYS}


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with conn() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            id TEXT PRIMARY KEY, razao_social TEXT NOT NULL, nome_fantasia TEXT NOT NULL,
            cnpj TEXT NOT NULL UNIQUE, email TEXT NOT NULL, telefone TEXT, endereco TEXT, cidade TEXT, estado TEXT,
            status TEXT NOT NULL DEFAULT 'ativa' CHECK(status IN ('ativa','bloqueada','pendente')),
            criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS usuarios (
            id TEXT PRIMARY KEY, nome TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL, cargo TEXT NOT NULL CHECK(cargo IN ('administrador','usuario','super_admin')),
            status TEXT NOT NULL DEFAULT 'ativo', ultimo_login TEXT, ultimo_logout TEXT,
            criado_em TEXT NOT NULL, tempo_total_ativo INTEGER NOT NULL DEFAULT 0,
            administrador_primario INTEGER NOT NULL DEFAULT 0,
            company_id TEXT REFERENCES companies(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            status TEXT NOT NULL CHECK(status IN ('pendente','ativa','atrasada','cancelada','bloqueada')),
            valor REAL NOT NULL, data_inicio TEXT, data_vencimento TEXT, ultimo_pagamento TEXT, proximo_vencimento TEXT,
            transacao_id TEXT, criado_em TEXT NOT NULL, atualizado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS payments (
            id TEXT PRIMARY KEY, company_id TEXT NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
            subscription_id TEXT NOT NULL REFERENCES subscriptions(id) ON DELETE CASCADE,
            valor REAL NOT NULL, status TEXT NOT NULL CHECK(status IN ('pendente','pago','recusado','cancelado')),
            data_cobranca TEXT NOT NULL, data_pagamento TEXT, transacao_id TEXT, metodo TEXT, gateway_payload TEXT, criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY, company_id TEXT REFERENCES companies(id) ON DELETE SET NULL,
            usuario_id TEXT REFERENCES usuarios(id) ON DELETE SET NULL,
            acao TEXT NOT NULL, descricao TEXT NOT NULL, ip TEXT, resultado TEXT, data_hora TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS permissoes (
            usuario_id TEXT PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
            visualizar_cameras INTEGER NOT NULL DEFAULT 1, usar_camera_dispositivo INTEGER NOT NULL DEFAULT 1,
            gerenciar_cameras INTEGER NOT NULL DEFAULT 0, visualizar_alertas INTEGER NOT NULL DEFAULT 1,
            visualizar_relatorios INTEGER NOT NULL DEFAULT 1, gerenciar_usuarios INTEGER NOT NULL DEFAULT 0,
            gerenciar_permissoes INTEGER NOT NULL DEFAULT 0, acessar_configuracoes INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS cameras (
            id TEXT PRIMARY KEY, nome TEXT NOT NULL, tipo TEXT NOT NULL,
            device_id TEXT, endereco TEXT, localizacao TEXT, status TEXT NOT NULL DEFAULT 'ativo', criado_em TEXT NOT NULL,
            company_id TEXT REFERENCES companies(id) ON DELETE CASCADE
        );
        CREATE TABLE IF NOT EXISTS usuario_cameras (
            usuario_id TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            camera_id TEXT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
            PRIMARY KEY(usuario_id, camera_id)
        );
        CREATE TABLE IF NOT EXISTS alertas (
            id TEXT PRIMARY KEY, camera_id TEXT REFERENCES cameras(id) ON DELETE SET NULL,
            tipo TEXT NOT NULL, nivel TEXT NOT NULL, descricao TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Aberto', data_hora TEXT NOT NULL,
            company_id TEXT REFERENCES companies(id) ON DELETE SET NULL
        );
        CREATE TABLE IF NOT EXISTS sessoes (
            id TEXT PRIMARY KEY, usuario_id TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            inicio TEXT NOT NULL, ultimo_heartbeat TEXT NOT NULL, fim TEXT,
            duracao_segundos INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'online'
        );
        CREATE TABLE IF NOT EXISTS atividades (
            id TEXT PRIMARY KEY, usuario_id TEXT REFERENCES usuarios(id) ON DELETE SET NULL,
            acao TEXT NOT NULL, descricao TEXT NOT NULL, data_hora TEXT NOT NULL,
            company_id TEXT REFERENCES companies(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sessoes_usuario ON sessoes(usuario_id);
        CREATE INDEX IF NOT EXISTS idx_sessoes_status ON sessoes(status);
        CREATE INDEX IF NOT EXISTS idx_alertas_data ON alertas(data_hora);
        CREATE INDEX IF NOT EXISTS idx_atividades_data ON atividades(data_hora);
        """)
        # migracoes colunas faltantes
        def has_col(table, col):
            return any(r["name"] == col for r in db.execute(f"PRAGMA table_info({table})").fetchall())
        for tbl, col, typ in [
            ("usuarios", "company_id", "TEXT"),
            ("cameras", "company_id", "TEXT"),
            ("cameras", "ultima_verificacao", "TEXT"),
            ("cameras", "ultimo_online", "TEXT"),
            ("cameras", "ultimo_erro", "TEXT"),
            ("alertas", "company_id", "TEXT"),
            ("atividades", "company_id", "TEXT"),
            ("usuarios", "administrador_primario", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            if not has_col(tbl, col):
                try:
                    db.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}")
                except Exception:
                    pass
        # migracao legado: se existem usuarios/cameras sem company_id, cria empresa default
        try:
            legacy_users = db.execute("SELECT id FROM usuarios WHERE company_id IS NULL AND cargo!='super_admin'").fetchall()
            legacy_cams = db.execute("SELECT id FROM cameras WHERE company_id IS NULL").fetchall()
            if legacy_users or legacy_cams:
                # cria empresa legada
                existing_company = db.execute("SELECT id FROM companies LIMIT 1").fetchone()
                if not existing_company:
                    cid = secrets.token_hex(12)
                    db.execute("INSERT INTO companies(id,razao_social,nome_fantasia,cnpj,email,telefone,endereco,cidade,estado,status,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (cid, "Empresa Legada", "Empresa Legada", "00000000000000", "legado@edgesecurity.local", "", "", "", "", "ativa", now(), now()))
                    sid = secrets.token_hex(12)
                    venc = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
                    db.execute("INSERT INTO subscriptions(id,company_id,status,valor,data_inicio,data_vencimento,ultimo_pagamento,proximo_vencimento,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (sid, cid, "ativa", SUBSCRIPTION_VALUE, now(), venc, now(), venc, now(), now()))
                else:
                    cid = existing_company["id"]
                for r in legacy_users:
                    db.execute("UPDATE usuarios SET company_id=? WHERE id=?", (cid, r["id"]))
                for r in legacy_cams:
                    db.execute("UPDATE cameras SET company_id=? WHERE id=?", (cid, r["id"]))
                db.execute("UPDATE alertas SET company_id=? WHERE company_id IS NULL AND camera_id IN (SELECT id FROM cameras WHERE company_id=?)", (cid,))
                db.execute("UPDATE atividades SET company_id=? WHERE company_id IS NULL", (cid,))
        except Exception:
            pass
        try:
            row = db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='usuarios'").fetchone()
            if row and "super_admin" not in (row[0] or ""):
                db.execute("PRAGMA foreign_keys=OFF")
                db.execute("ALTER TABLE usuarios RENAME TO usuarios_old")
                db.execute("""
                CREATE TABLE usuarios (
                    id TEXT PRIMARY KEY, nome TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
                    senha_hash TEXT NOT NULL, cargo TEXT NOT NULL CHECK(cargo IN ('administrador','usuario','super_admin')),
                    status TEXT NOT NULL DEFAULT 'ativo', ultimo_login TEXT, ultimo_logout TEXT,
                    criado_em TEXT NOT NULL, tempo_total_ativo INTEGER NOT NULL DEFAULT 0,
                    administrador_primario INTEGER NOT NULL DEFAULT 0,
                    company_id TEXT REFERENCES companies(id) ON DELETE CASCADE
                )""")
                cols = [r[1] for r in db.execute("PRAGMA table_info(usuarios_old)").fetchall()]
                common = [c for c in cols if c in ("id","nome","email","senha_hash","cargo","status","ultimo_login","ultimo_logout","criado_em","tempo_total_ativo","administrador_primario","company_id")]
                if common:
                    db.execute(f"INSERT INTO usuarios({','.join(common)}) SELECT {','.join(common)} FROM usuarios_old")
                try:
                    db.execute("DROP TABLE usuarios_old")
                except Exception:
                    pass
                db.execute("PRAGMA foreign_keys=ON")
        except Exception as _mig_e:
            try:
                db.execute("PRAGMA foreign_keys=ON")
            except Exception:
                pass
        # garante super_admin
        if not db.execute("SELECT 1 FROM usuarios WHERE cargo='super_admin' LIMIT 1").fetchone():
            if not db.execute("SELECT 1 FROM usuarios WHERE lower(email)=?", (SUPER_ADMIN_EMAIL,)).fetchone():
                uid = secrets.token_hex(12)
                db.execute("INSERT INTO usuarios(id,nome,email,senha_hash,cargo,status,criado_em,administrador_primario,company_id) VALUES(?,?,?,?,?,?,?,?,NULL)",
                    (uid, SUPER_ADMIN_NAME, SUPER_ADMIN_EMAIL, hash_password(SUPER_ADMIN_PASSWORD), "super_admin", "ativo", now(), 0))
                db.execute("INSERT OR IGNORE INTO permissoes(usuario_id," + ",".join(PERMISSION_KEYS) + ") VALUES(?" + ",?" * len(PERMISSION_KEYS) + ")", (uid, *[1]*len(PERMISSION_KEYS)))
        # garante exatamente um administrador_primario por empresa (para empresas com users mas sem flag)
        for comp in db.execute("SELECT id FROM companies").fetchall():
            cid = comp["id"]
            has = db.execute("SELECT 1 FROM usuarios WHERE company_id=? AND administrador_primario=1 LIMIT 1", (cid,)).fetchone()
            if not has:
                oldest = db.execute("SELECT id FROM usuarios WHERE company_id=? AND cargo='administrador' ORDER BY criado_em ASC LIMIT 1", (cid,)).fetchone()
                if oldest:
                    db.execute("UPDATE usuarios SET administrador_primario=1 WHERE id=?", (oldest["id"],))
        # atualiza assinaturas vencidas para atrasada
        try:
            for s in db.execute("SELECT id,proximo_vencimento,status FROM subscriptions WHERE status='ativa'").fetchall():
                if s["proximo_vencimento"]:
                    try:
                        venc_dt = datetime.fromisoformat(s["proximo_vencimento"].replace("Z","+00:00"))
                        if venc_dt < datetime.now(timezone.utc):
                            db.execute("UPDATE subscriptions SET status='atrasada', atualizado_em=? WHERE id=?", (now(), s["id"]))
                    except Exception:
                        pass
        except Exception:
            pass


def audit(db, company_id, usuario_id, acao, descricao, ip="", resultado="ok"):
    try:
        db.execute("INSERT INTO audit_logs(id,company_id,usuario_id,acao,descricao,ip,resultado,data_hora) VALUES(?,?,?,?,?,?,?,?)",
            (secrets.token_hex(12), company_id, usuario_id, acao, descricao, ip or "", resultado, now()))
    except Exception:
        pass


def get_detector():
    global _detector, _detector_error
    if _detector is not None:
        return _detector
    if _detector_error is not None:
        raise RuntimeError(_detector_error)
    try:
        _detector = SafetyDetector(MODEL_PATH, confidence=AI_CONFIDENCE, iou=AI_IOU)
        return _detector
    except Exception as exc:
        _detector_error = str(exc)
        raise RuntimeError(f"Falha ao carregar o modelo YOLO: {exc}") from exc


def _encrypt(v: str) -> str:
    if not v or not DATA_ENCRYPTION_KEY:
        return v
    try:
        from cryptography.fernet import Fernet
        import base64 as _b64
        key = DATA_ENCRYPTION_KEY.encode()
        if len(key) < 32:
            key = (key + b"0" * 32)[:32]
            key = _b64.urlsafe_b64encode(key[:32])
        f = Fernet(key if len(key) == 44 else _b64.urlsafe_b64encode(key[:32]))
        return f.encrypt(v.encode()).decode()
    except Exception:
        return v

def _decrypt(v: str) -> str:
    if not v or not DATA_ENCRYPTION_KEY:
        return v
    try:
        from cryptography.fernet import Fernet
        import base64 as _b64
        key = DATA_ENCRYPTION_KEY.encode()
        if len(key) < 32:
            key = (key + b"0" * 32)[:32]
            key = _b64.urlsafe_b64encode(key[:32])
        f = Fernet(key if len(key) == 44 else _b64.urlsafe_b64encode(key[:32]))
        return f.decrypt(v.encode()).decode()
    except Exception:
        return v

def _valid_cnpj(cnpj: str) -> bool:
    c = re.sub(r"\D", "", cnpj)
    if len(c) != 14 or len(set(c)) == 1:
        return False
    def calc(digs):
        w = [6,5,4,3,2,9,8,7,6,5,4,3,2] if len(digs)==13 else [5,4,3,2,9,8,7,6,5,4,3,2]
        s = sum(int(d)*w[i+len(w)-len(digs)] for i,d in enumerate(digs))
        r = s % 11
        return "0" if r < 2 else str(11 - r)
    return c[12] == calc(c[:12]) and c[13] == calc(c[:13])

SIGNUP_ATTEMPTS: dict[str, list[float]] = {}
SIGNUP_MAX = 5
SIGNUP_WINDOW = 600

def _check_signup_rate(ip: str):
    now_ts = time.time()
    lst = [t for t in SIGNUP_ATTEMPTS.get(ip, []) if now_ts - t < SIGNUP_WINDOW]
    SIGNUP_ATTEMPTS[ip] = lst
    if len(lst) >= SIGNUP_MAX:
        raise HTTPException(429, "Muitas tentativas. Tente novamente em alguns minutos.")
    lst.append(now_ts)

def user_dict(row, db) -> dict[str, Any]:
    d = dict(row)
    d.pop("senha_hash", None)
    p = db.execute("SELECT * FROM permissoes WHERE usuario_id=?", (row["id"],)).fetchone()
    permissions = {k: bool(p[k]) for k in PERMISSION_KEYS} if p else default_permissions(row["cargo"])
    cams = [r["camera_id"] for r in db.execute("SELECT camera_id FROM usuario_cameras WHERE usuario_id=?", (row["id"],)).fetchall()]
    if "cnpj" in d:
        try:
            d["cnpj"] = _decrypt(d["cnpj"])
        except Exception:
            pass
    return {**d, "permissoes": permissions, "cameras": cams, "administrador_primario": bool(row["administrador_primario"])}

def _public_company(c):
    if not c:
        return None
    d = dict(c)
    cnpj_raw = d.get("cnpj", "")
    try:
        dec = _decrypt(cnpj_raw)
        d["cnpj"] = dec[:3] + "***" + dec[-2:] if len(dec)==14 else "***"
    except Exception:
        d["cnpj"] = "***"
    return d

def _public_user(u):
    d = {k: v for k, v in dict(u).items() if k not in ("senha_hash",)}
    return d


def _extract_token(authorization: str | None, request: Request | None = None) -> str | None:
    if authorization and authorization.startswith("Bearer "):
        return authorization[7:].strip()
    if request is not None:
        ck = request.cookies.get("edge_token")
        if ck:
            return ck.strip()
    return None

def get_session_for_token(token: str) -> dict[str, Any] | None:
    if not token or len(token) < 16:
        return None
    session = SESSIONS.get(token)
    if not session:
        return None
    now_ts = time.time()
    last_seen = float(session.get("last_seen", session.get("login_at", now_ts)))
    if now_ts - last_seen > SESSION_IDLE_TIMEOUT:
        SESSIONS.pop(token, None)
        return None
    session["last_seen"] = now_ts
    return session


def subscription_status(db, company_id: str) -> dict | None:
    row = db.execute("SELECT * FROM subscriptions WHERE company_id=? ORDER BY criado_em DESC LIMIT 1", (company_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    # auto-check vencimento
    if d["status"] == "ativa" and d["proximo_vencimento"]:
        try:
            venc = datetime.fromisoformat(d["proximo_vencimento"].replace("Z", "+00:00"))
            if venc < datetime.now(timezone.utc):
                db.execute("UPDATE subscriptions SET status='atrasada', atualizado_em=? WHERE id=?", (now(), d["id"]))
                d["status"] = "atrasada"
        except Exception:
            pass
    return d


def require_user(authorization: str | None, request: Request | None = None):
    tok = _extract_token(authorization, request)
    if not tok:
        raise HTTPException(401, "Autenticação necessária.")
    session = get_session_for_token(tok)
    if not session:
        raise HTTPException(401, "Sessão inválida ou expirada.")
    session["_token"] = tok
    return session


def require_user_active(authorization: str | None = None, request: Request | None = None):
    session = require_user(authorization, request)
    if session.get("cargo") == "super_admin":
        return session
    with conn() as db:
        sub = subscription_status(db, session.get("company_id"))
        comp = db.execute("SELECT * FROM companies WHERE id=?", (session.get("company_id"),)).fetchone() if session.get("company_id") else None
        if not comp:
            raise HTTPException(403, "Empresa não encontrada.")
        if comp["status"] == "bloqueada":
            raise HTTPException(403, "Empresa bloqueada. Contate o administrador da plataforma.")
        if not sub:
            raise HTTPException(403, "Sem assinatura. Regularize o pagamento para continuar utilizando o sistema.")
        if sub["status"] == "pendente":
            raise HTTPException(403, "Pagamento pendente. Finalize sua assinatura para acessar o sistema.")
        if sub["status"] in ("atrasada", "bloqueada"):
            raise HTTPException(403, "Assinatura vencida. Regularize o pagamento para continuar utilizando o sistema.")
        if sub["status"] == "cancelada":
            raise HTTPException(403, "Sua assinatura foi cancelada.")
        if sub["status"] != "ativa":
            raise HTTPException(403, "Assinatura inativa. Regularize o pagamento.")
    return session


def require_admin(authorization: str | None = None, request: Request | None = None):
    session = require_user_active(authorization, request)
    if session["cargo"] not in ("administrador", "super_admin") and session["cargo"] != "administrador":
        raise HTTPException(403, "Acesso restrito ao administrador.")
    if session.get("cargo") == "super_admin":
        return session
    if session["cargo"] != "administrador":
        raise HTTPException(403, "Acesso restrito ao administrador.")
    return session


def require_permission(authorization: str | None = None, key: str = "", request: Request | None = None):
    if key not in PERMISSION_KEYS:
        raise HTTPException(500, "Chave de permissão inválida.")
    session = require_user_active(authorization, request)
    if session["cargo"] in ("administrador", "super_admin"):
        return session
    with conn() as db:
        row = db.execute(f"SELECT {key} FROM permissoes WHERE usuario_id=?", (session["id"],)).fetchone()
    if not row or not bool(row[key]):
        raise HTTPException(403, "Você não possui permissão para esta operação.")
    return session

def require_super_admin(authorization: str | None = None, request: Request | None = None):
    session = require_user(authorization, request)
    if session.get("cargo") != "super_admin":
        raise HTTPException(403, "Acesso não autorizado.")
    return session


def activity(db, user_id, action, description, company_id=None):
    try:
        cid = company_id
        if not cid and user_id:
            r = db.execute("SELECT company_id FROM usuarios WHERE id=?", (user_id,)).fetchone()
            if r:
                cid = r["company_id"]
        db.execute("INSERT INTO atividades(id,usuario_id,acao,descricao,data_hora,company_id) VALUES(?,?,?,?,?,?)",
            (secrets.token_hex(12), user_id, action, description, now(), cid))
    except Exception:
        db.execute("INSERT INTO atividades(id,usuario_id,acao,descricao,data_hora) VALUES(?,?,?,?,?)",
            (secrets.token_hex(12), user_id, action, description, now()))


def create_ai_alert(camera_id, risk, company_id=None):
    global _last_risk_alert
    if risk.get("level") not in {"high", "critical"}:
        return None
    key = f"{camera_id}:{risk.get('level')}"
    current = time.time()
    if current - _last_risk_alert.get(key, 0) < 5:
        return None
    _last_risk_alert[key] = current
    description = "Risco de colisão: empilhadeira próxima de pessoa detectado pela IA."
    if risk.get("level") == "critical":
        description = "RISCO CRÍTICO: empilhadeira e pessoa em zona de colisão."
    with conn() as db:
        if not company_id and camera_id:
            cr = db.execute("SELECT company_id FROM cameras WHERE id=?", (camera_id,)).fetchone()
            if cr:
                company_id = cr["company_id"]
        alert_id = secrets.token_hex(12)
        db.execute("INSERT INTO alertas(id,camera_id,tipo,nivel,descricao,status,data_hora,company_id) VALUES(?,?,?,?,?,?,?,?)",
            (alert_id, camera_id, "IA - Aproximação", "Crítico" if risk.get("level") == "critical" else "Alto", description, "Aberto", now(), company_id))
    return alert_id


class LoginIn(BaseModel):
    model_config = {"extra": "forbid"}
    username: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=4, max_length=128)
    website: str | None = Field(default=None, max_length=0)

    @field_validator("username")
    def _strip_u(cls, v): return v.strip()[:120]

class SetupIn(BaseModel):
    model_config = {"extra": "forbid"}
    nome: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=120)
    senha: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    def _email(cls, v):
        v=v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]: raise ValueError("E-mail inválido.")
        return v[:120]
    @field_validator("senha")
    def _pwd(cls, v):
        if len(v)<8 or not re.search(r"[A-Za-z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("Senha deve ter 8+ caracteres com letras e números.")
        return v
    @field_validator("nome")
    def _nome(cls, v):
        v=v.strip()
        if len(v)<2: raise ValueError("Nome muito curto.")
        return v[:80]

class UserIn(BaseModel):
    model_config = {"extra": "forbid"}
    nome: str = Field(min_length=2, max_length=80)
    email: str = Field(max_length=120)
    senha: str | None = Field(default=None, max_length=128)
    cargo: str = Field(default="usuario")
    status: str = Field(default="ativo")
    permissoes: dict[str, bool] = Field(default_factory=dict)
    cameras: list[str] = Field(default_factory=list)

    @field_validator("email")
    def _email(cls, v):
        v=v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]: raise ValueError("E-mail inválido.")
        return v
    @field_validator("cargo")
    def _cargo(cls, v):
        if v not in ("administrador","usuario"): raise ValueError("Cargo inválido.")
        return v
    @field_validator("status")
    def _status(cls, v):
        if v not in ("ativo","bloqueado"): raise ValueError("Status inválido.")
        return v
    @field_validator("senha")
    def _pwd(cls, v):
        if v is None: return v
        if len(v)<8 or not re.search(r"[A-Za-z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("Senha deve ter 8+ caracteres com letras e números.")
        return v
    @field_validator("nome")
    def _nome(cls, v): return v.strip()[:80]

class CameraIn(BaseModel):
    model_config = {"extra": "forbid"}
    nome: str = Field(min_length=1, max_length=80)
    tipo: str = Field(default="browser")
    device_id: str | None = Field(default=None, max_length=200)
    endereco: str | None = Field(default=None, max_length=500)
    localizacao: str | None = Field(default=None, max_length=80)
    status: str = Field(default="ativo")
    @field_validator("tipo")
    def _tipo(cls, v):
        if v not in ("browser","ip","rtsp","wifi"): raise ValueError("Tipo inválido.")
        return v
    @field_validator("nome")
    def _nome(cls, v): return v.strip()[:80]

class CameraTestIn(BaseModel):
    model_config = {"extra": "forbid"}
    endereco: str = Field(min_length=1, max_length=500)
    @field_validator("endereco")
    def _url(cls, v):
        v=v.strip()
        if not (v.startswith("rtsp://") or v.startswith("http://") or v.startswith("https://")):
            raise ValueError("URL deve iniciar com rtsp://, http:// ou https://.")
        return v

class AlertIn(BaseModel):
    model_config = {"extra": "forbid"}
    camera_id: str | None = Field(default=None, max_length=32)
    tipo: str = Field(min_length=1, max_length=80)
    nivel: str = Field(min_length=1, max_length=20)
    descricao: str = Field(min_length=1, max_length=500)
    status: str = Field(default="Aberto")
    @field_validator("tipo","nivel","descricao")
    def _strip(cls, v): return v.strip()[:500] if isinstance(v,str) else v

class CompanySignupIn(BaseModel):
    model_config = {"extra": "forbid"}
    razao_social: str = Field(min_length=2, max_length=120)
    nome_fantasia: str = Field(min_length=2, max_length=120)
    cnpj: str = Field(min_length=14, max_length=18)
    email: str = Field(max_length=120)
    telefone: str | None = Field(default=None, max_length=20)
    endereco: str | None = Field(default=None, max_length=200)
    cidade: str | None = Field(default=None, max_length=80)
    estado: str | None = Field(default=None, max_length=2)
    admin_nome: str = Field(min_length=2, max_length=80)
    admin_email: str = Field(max_length=120)
    admin_senha: str = Field(min_length=8, max_length=128)
    admin_senha_confirm: str = Field(min_length=8, max_length=128)
    website: str | None = Field(default=None, max_length=0)
    @field_validator("email","admin_email")
    def _email(cls, v):
        v=v.strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]: raise ValueError("E-mail inválido.")
        return v[:120]
    @field_validator("admin_senha")
    def _pwd(cls, v):
        if len(v)<8 or not re.search(r"[A-Za-z]", v) or not re.search(r"[0-9]", v):
            raise ValueError("Senha deve ter 8+ caracteres com letras e números.")
        return v
    @field_validator("cnpj")
    def _cnpj_fmt(cls, v): return v.strip()[:18]

class WebhookIn(BaseModel):
    model_config = {"extra": "forbid"}
    transacao_id: str = Field(max_length=64)
    status: str | None = Field(default=None, max_length=20)
    gateway_payload: str | None = Field(default=None, max_length=2000)
    secret: str | None = Field(default=None, max_length=200)

class CompanyStatusIn(BaseModel):
    model_config = {"extra": "forbid"}
    status: str = Field(max_length=20)

def open_ip_camera(url: str):
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        cap.release()
        return None
    return cap

def test_ip_stream(url: str):
    cap = None
    try:
        cap = open_ip_camera(url)
        if cap is None:
            return None
        ok, frame = cap.read()
        if not ok or frame is None:
            return None
        return (int(frame.shape[1]), int(frame.shape[0]))
    finally:
        if cap is not None:
            cap.release()

@app.on_event("startup")
def startup():
    init_db()

@app.get("/api/health")
def health():
    return {"ok": True}

@app.get("/api/setup/status")
def setup_status():
    with conn() as db:
        has_admin = db.execute("SELECT 1 FROM usuarios WHERE cargo='super_admin' LIMIT 1").fetchone()
        has_company = db.execute("SELECT 1 FROM companies LIMIT 1").fetchone()
        return {"needs_setup": not has_admin, "has_company": bool(has_company)}

SETUP_TOKEN = os.getenv("SETUP_TOKEN", "").strip()
SETUP_ENABLED = os.getenv("SETUP_ENABLED", "false").lower() in ("1", "true", "yes")
AI_LOCAL = os.getenv("AI_LOCAL", "true").lower() in ("1", "true", "yes")

@app.post("/api/setup")
def setup(data: SetupIn, request: Request):
    if not SETUP_ENABLED and not SETUP_TOKEN:
        raise HTTPException(403, "Criação inicial desabilitada. Configure o super_admin via .env e reinicie.")
    if SETUP_TOKEN:
        token = request.headers.get("x-setup-token", "")
        if not hmac.compare_digest(token or "", SETUP_TOKEN):
            raise HTTPException(403, "Token de configuração inválido.")
    with conn() as db:
        if db.execute("SELECT 1 FROM usuarios WHERE cargo='super_admin' LIMIT 1").fetchone():
            raise HTTPException(409, "O administrador master já foi criado.")
        uid = secrets.token_hex(12)
        db.execute("INSERT INTO usuarios(id,nome,email,senha_hash,cargo,status,criado_em,administrador_primario,company_id) VALUES(?,?,?,?,?,?,?,?,NULL)",
            (uid, data.nome.strip(), data.email.strip().lower(), hash_password(data.senha), "super_admin", "ativo", now(), 0))
        p = default_permissions("administrador")
        db.execute("INSERT INTO permissoes(usuario_id," + ",".join(PERMISSION_KEYS) + ") VALUES(?" + ",?" * len(PERMISSION_KEYS) + ")", (uid, *[int(p[k]) for k in PERMISSION_KEYS]))
        audit(db, None, uid, "criacao_super_admin", "Super admin criado via setup", request.client.host if request.client else "", "ok")
    return {"ok": True}

# ---------- EMPRESA / ASSINATURA / PAGAMENTO ----------

def clean_cnpj(v: str) -> str:
    return re.sub(r"\D", "", v or "")

def _mp_create_preapproval(company_id: str, payer_email: str, external_ref: str) -> dict | None:
    if not MP_ACCESS_TOKEN or not httpx:
        return None
    try:
        payload = {
            "reason": "EdgeSecurity - Assinatura Mensal",
            "external_reference": external_ref,
            "payer_email": payer_email,
            "auto_recurring": {"frequency": 1, "frequency_type": "months", "transaction_amount": SUBSCRIPTION_VALUE, "currency_id": "BRL"},
            "back_url": os.getenv("MP_BACK_URL", "http://localhost:5500/pages/pagamento.html"),
            "status": "pending",
        }
        headers = {"Authorization": f"Bearer {MP_ACCESS_TOKEN}", "Content-Type": "application/json"}
        with httpx.Client(timeout=12) as client:
            r = client.post(MP_PREAPPROVAL_URL, json=payload, headers=headers)
            if r.status_code in (200, 201):
                data = r.json()
                return {"mp_id": data.get("id"), "init_point": data.get("init_point"), "raw": json.dumps(data)[:2000]}
            return {"error": f"MP {r.status_code}: {r.text[:500]}"}
    except Exception as e:
        return {"error": str(e)[:500]}

@app.post("/api/companies/signup")
def company_signup(data: CompanySignupIn, request: Request):
    ip = request.client.host if request.client else "unknown"
    _check_signup_rate(ip)
    if data.website:
        raise HTTPException(400, "Requisição inválida.")
    cnpj = clean_cnpj(data.cnpj)
    if len(cnpj) != 14 or not _valid_cnpj(cnpj):
        raise HTTPException(400, "CNPJ inválido.")
    if data.admin_senha != data.admin_senha_confirm:
        raise HTTPException(400, "Senhas não conferem.")
    cnpj_store = _encrypt(cnpj) if DATA_ENCRYPTION_KEY else cnpj
    with conn() as db:
        check_cnpj = cnpj_store if DATA_ENCRYPTION_KEY else cnpj
        if DATA_ENCRYPTION_KEY:
            exists = False
            for row in db.execute("SELECT cnpj FROM companies").fetchall():
                try:
                    if _decrypt(row["cnpj"]) == cnpj:
                        exists = True
                        break
                except Exception:
                    if row["cnpj"] == cnpj:
                        exists = True
                        break
            if exists:
                raise HTTPException(409, "CNPJ já cadastrado.")
        else:
            if db.execute("SELECT 1 FROM companies WHERE cnpj=?", (cnpj,)).fetchone():
                raise HTTPException(409, "CNPJ já cadastrado.")
        if db.execute("SELECT 1 FROM usuarios WHERE lower(email)=?", (data.admin_email.strip().lower(),)).fetchone():
            raise HTTPException(409, "E-mail do administrador já cadastrado.")
        cid = secrets.token_hex(12)
        db.execute("INSERT INTO companies(id,razao_social,nome_fantasia,cnpj,email,telefone,endereco,cidade,estado,status,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (cid, data.razao_social.strip()[:120], data.nome_fantasia.strip()[:120], cnpj_store, data.email.strip().lower()[:120], (data.telefone or "")[:20], (data.endereco or "")[:200], (data.cidade or "")[:80], (data.estado or "")[:2], "ativa", now(), now()))
        uid = secrets.token_hex(12)
        db.execute("INSERT INTO usuarios(id,nome,email,senha_hash,cargo,status,criado_em,administrador_primario,company_id) VALUES(?,?,?,?,?,?,?,?,?)",
            (uid, data.admin_nome.strip()[:80], data.admin_email.strip().lower()[:120], hash_password(data.admin_senha), "administrador", "ativo", now(), 1, cid))
        p = default_permissions("administrador")
        db.execute("INSERT INTO permissoes(usuario_id," + ",".join(PERMISSION_KEYS) + ") VALUES(?" + ",?" * len(PERMISSION_KEYS) + ")", (uid, *[int(p[k]) for k in PERMISSION_KEYS]))
        sid = secrets.token_hex(12)
        db.execute("INSERT INTO subscriptions(id,company_id,status,valor,criado_em,atualizado_em) VALUES(?,?,?,?,?,?)",
            (sid, cid, "pendente", SUBSCRIPTION_VALUE, now(), now()))
        pid = secrets.token_hex(12)
        transacao_id = secrets.token_hex(12)
        db.execute("INSERT INTO payments(id,company_id,subscription_id,valor,status,data_cobranca,transacao_id,metodo,criado_em) VALUES(?,?,?,?,?,?,?,?,?)",
            (pid, cid, sid, SUBSCRIPTION_VALUE, "pendente", now(), transacao_id, "pix", now()))
        db.execute("UPDATE subscriptions SET transacao_id=? WHERE id=?", (transacao_id, sid))
        mp_info = None
        if MP_ACCESS_TOKEN:
            mp_info = _mp_create_preapproval(cid, data.admin_email.strip().lower(), cid)
            if mp_info and mp_info.get("mp_id"):
                db.execute("UPDATE payments SET gateway_payload=?, metodo='mercadopago' WHERE id=?", (json.dumps(mp_info)[:2000], pid))
                db.execute("UPDATE subscriptions SET transacao_id=? WHERE id=?", (mp_info["mp_id"], sid))
                transacao_id = mp_info["mp_id"]
        activity(db, uid, "criação de empresa", f"Empresa {data.nome_fantasia.strip()[:60]} cadastrada", cid)
        audit(db, cid, uid, "company_signup", f"Empresa cadastrada", ip, "ok")
        resp = {"ok": True, "company_id": cid, "subscription_id": sid, "payment_id": pid, "transacao_id": transacao_id, "valor": SUBSCRIPTION_VALUE, "status": "pendente", "mock": PAYMENT_MOCK and not MP_ACCESS_TOKEN}
        if mp_info and mp_info.get("init_point"):
            resp["mp_init_point"] = mp_info["init_point"]
            resp["mp_id"] = mp_info["mp_id"]
        return resp

@app.get("/api/companies/me")
def company_me(authorization: str | None = Header(default=None)):
    session = require_user_active(authorization)
    if session.get("cargo") == "super_admin":
        raise HTTPException(403, "Super admin não possui empresa.")
    with conn() as db:
        comp = db.execute("SELECT * FROM companies WHERE id=?", (session["company_id"],)).fetchone()
        if not comp:
            raise HTTPException(404, "Empresa não encontrada.")
        sub = subscription_status(db, session["company_id"])
        pays = [dict(r) for r in db.execute("SELECT id,valor,status,data_cobranca,data_pagamento,metodo,criado_em FROM payments WHERE company_id=? ORDER BY criado_em DESC LIMIT 10", (session["company_id"],)).fetchall()]
        return {"company": _public_company(comp), "subscription": sub, "payments": pays}

@app.get("/api/subscription")
def get_subscription(authorization: str | None = Header(default=None)):
    session = require_user_active(authorization)
    if session.get("cargo") == "super_admin":
        raise HTTPException(403, "Super admin não possui assinatura.")
    with conn() as db:
        sub = subscription_status(db, session["company_id"])
        if not sub:
            raise HTTPException(404, "Assinatura não encontrada.")
        return {k: v for k, v in sub.items() if k != "transacao_id"}

@app.post("/api/payments/webhook")
def payment_webhook(data: WebhookIn, request: Request):
    sig = request.headers.get("x-webhook-signature", "") or request.headers.get("X-Webhook-Signature", "")
    body_raw = data.model_dump_json()
    if WEBHOOK_SECRET:
        expected = hmac.new(WEBHOOK_SECRET.encode(), data.transacao_id.encode(), hashlib.sha256).hexdigest()
        if not sig or not hmac.compare_digest(sig, expected):
            if data.secret != WEBHOOK_SECRET:
                raise HTTPException(403, "Webhook secret inválido.")
    else:
        if MP_ACCESS_TOKEN:
            pass
        elif data.secret is not None and data.secret != "":
            raise HTTPException(403, "Webhook secret inválido.")
    with conn() as db:
        row = db.execute("SELECT * FROM payments WHERE transacao_id=?", (data.transacao_id,)).fetchone()
        if not row:
            try:
                sub = db.execute("SELECT * FROM subscriptions WHERE transacao_id=?", (data.transacao_id,)).fetchone()
                if sub:
                    row = db.execute("SELECT * FROM payments WHERE subscription_id=? ORDER BY criado_em DESC LIMIT 1", (sub["id"],)).fetchone()
            except Exception:
                row = None
        if not row:
            raise HTTPException(404, "Transação não encontrada.")
        if row["status"] == "pago":
            return {"ok": True, "already_paid": True}
        payload_store = (data.gateway_payload or "")[:2000]
        try:
            mp_status = None
            if MP_ACCESS_TOKEN and httpx and data.transacao_id and len(data.transacao_id) > 20:
                with httpx.Client(timeout=8) as client:
                    r = client.get(f"{MP_PREAPPROVAL_URL}/{data.transacao_id}", headers={"Authorization": f"Bearer {MP_ACCESS_TOKEN}"})
                    if r.status_code == 200:
                        j = r.json()
                        mp_status = j.get("status")
                        payload_store = json.dumps(j)[:2000]
                        if mp_status not in ("authorized", "active", None):
                            raise HTTPException(402, f"Assinatura Mercado Pago não autorizada: {mp_status}")
        except HTTPException:
            raise
        except Exception:
            pass
        db.execute("UPDATE payments SET status='pago', data_pagamento=?, gateway_payload=? WHERE id=?", (now(), payload_store, row["id"]))
        sub = db.execute("SELECT * FROM subscriptions WHERE id=?", (row["subscription_id"],)).fetchone()
        if sub:
            venc = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            db.execute("UPDATE subscriptions SET status='ativa', data_inicio=?, data_vencimento=?, ultimo_pagamento=?, proximo_vencimento=?, atualizado_em=? WHERE id=?",
                (now(), venc, now(), venc, now(), sub["id"]))
            db.execute("UPDATE companies SET status='ativa', atualizado_em=? WHERE id=?", (now(), sub["company_id"]))
            audit(db, sub["company_id"], None, "payment_confirm", f"Pagamento confirmado", request.client.host if request.client else "", "ok")
        return {"ok": True, "status": "pago"}

@app.post("/api/payments/{transacao_id}/confirm-mock")
def payment_confirm_mock(transacao_id: str, request: Request):
    if not PAYMENT_MOCK or MP_ACCESS_TOKEN:
        raise HTTPException(403, "Confirmação mock desabilitada em produção.")
    with conn() as db:
        row = db.execute("SELECT * FROM payments WHERE transacao_id=?", (transacao_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Transação não encontrada.")
        if row["status"] == "pago":
            return {"ok": True, "already_paid": True}
        db.execute("UPDATE payments SET status='pago', data_pagamento=?, gateway_payload=? WHERE id=?", (now(), "mock_confirm", row["id"]))
        sub = db.execute("SELECT * FROM subscriptions WHERE id=?", (row["subscription_id"],)).fetchone()
        if sub:
            venc = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
            db.execute("UPDATE subscriptions SET status='ativa', data_inicio=?, data_vencimento=?, ultimo_pagamento=?, proximo_vencimento=?, atualizado_em=? WHERE id=?",
                (now(), venc, now(), venc, now(), sub["id"]))
            db.execute("UPDATE companies SET status='ativa', atualizado_em=? WHERE id=?", (now(), sub["company_id"]))
            audit(db, sub["company_id"], None, "payment_mock_confirm", f"Pagamento mock confirmado", request.client.host if request.client else "", "ok")
        return {"ok": True, "status": "pago"}

@app.post("/api/payments/create-preapproval")
def create_preapproval(authorization: str | None = Header(default=None)):
    if not MP_ACCESS_TOKEN:
        raise HTTPException(400, "MP_ACCESS_TOKEN não configurado.")
    session = require_user(authorization)
    with conn() as db:
        cid = session.get("company_id")
        if not cid:
            raise HTTPException(400, "Sem empresa.")
        sub = db.execute("SELECT * FROM subscriptions WHERE company_id=? ORDER BY criado_em DESC LIMIT 1", (cid,)).fetchone()
        if not sub:
            raise HTTPException(404, "Assinatura não encontrada.")
        pay = db.execute("SELECT * FROM payments WHERE subscription_id=? ORDER BY criado_em DESC LIMIT 1", (sub["id"],)).fetchone()
        if not pay:
            raise HTTPException(404, "Cobrança não encontrada.")
        info = _mp_create_preapproval(cid, session["email"], cid)
        if not info or not info.get("mp_id"):
            raise HTTPException(502, info.get("error", "Falha ao criar preapproval Mercado Pago") if info else "Falha Mercado Pago")
        db.execute("UPDATE payments SET gateway_payload=?, metodo='mercadopago' WHERE id=?", (json.dumps(info)[:2000], pay["id"]))
        db.execute("UPDATE subscriptions SET transacao_id=? WHERE id=?", (info["mp_id"], sub["id"]))
        return {"ok": True, "mp_id": info["mp_id"], "init_point": info.get("init_point")}

# ---------- ADMIN MASTER ----------

@app.get("/api/admin/dashboard")
def admin_dashboard(request: Request, authorization: str | None = Header(default=None)):
    require_super_admin(authorization, request)
    with conn() as db:
        total_companies = db.execute("SELECT COUNT(*) n FROM companies").fetchone()["n"]
        ativas = db.execute("SELECT COUNT(*) n FROM companies WHERE status='ativa'").fetchone()["n"]
        bloqueadas = db.execute("SELECT COUNT(*) n FROM companies WHERE status='bloqueada'").fetchone()["n"]
        subs = {r["status"]: r["n"] for r in db.execute("SELECT status, COUNT(*) n FROM subscriptions GROUP BY status").fetchall()}
        receita = db.execute("SELECT COALESCE(SUM(valor),0) n FROM payments WHERE status='pago' AND data_pagamento >= datetime('now','-30 days')").fetchone()["n"]
        recentes = [dict(r) for r in db.execute("SELECT p.id,p.valor,p.status,p.data_cobranca,p.data_pagamento,p.metodo,p.criado_em,c.nome_fantasia FROM payments p JOIN companies c ON c.id=p.company_id ORDER BY p.criado_em DESC LIMIT 10").fetchall()]
        return {
            "total_companies": total_companies,
            "ativas": ativas,
            "bloqueadas": bloqueadas,
            "subs_ativas": subs.get("ativa", 0),
            "subs_pendentes": subs.get("pendente", 0),
            "subs_atrasadas": subs.get("atrasada", 0),
            "subs_canceladas": subs.get("cancelada", 0),
            "subs_bloqueadas": subs.get("bloqueada", 0),
            "receita_mensal": float(receita),
            "pagamentos_recentes": recentes,
            "subs_por_status": subs,
        }

@app.get("/api/admin/companies")
def admin_companies(request: Request, authorization: str | None = Header(default=None), q: str | None = None, status: str | None = None, sub_status: str | None = None):
    require_super_admin(authorization, request)
    q = (q or "")[:80]
    with conn() as db:
        sql = "SELECT c.id,c.razao_social,c.nome_fantasia,c.cnpj,c.email,c.status,c.criado_em,s.status as sub_status, s.valor, s.proximo_vencimento, s.ultimo_pagamento, u.nome as admin_nome, u.email as admin_email FROM companies c LEFT JOIN subscriptions s ON s.company_id=c.id LEFT JOIN usuarios u ON u.company_id=c.id AND u.administrador_primario=1 WHERE 1=1"
        params = []
        if q:
            like = f"%{q}%"
            sql += " AND (c.nome_fantasia LIKE ? OR c.razao_social LIKE ? OR c.email LIKE ?)"
            params += [like]*3
        if status and status in ("ativa","bloqueada","pendente"):
            sql += " AND c.status=?"
            params.append(status)
        if sub_status and sub_status in ("pendente","ativa","atrasada","cancelada","bloqueada"):
            sql += " AND s.status=?"
            params.append(sub_status)
        sql += " GROUP BY c.id ORDER BY c.criado_em DESC LIMIT 100"
        rows = db.execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["cnpj"] = (d.get("cnpj","")[:3] + "***" if d.get("cnpj") else "***")
            out.append(d)
        return out

@app.get("/api/admin/companies/{cid}")
def admin_company_detail(cid: str, request: Request, authorization: str | None = Header(default=None)):
    require_super_admin(authorization, request)
    cid = cid[:32]
    with conn() as db:
        comp = db.execute("SELECT id,razao_social,nome_fantasia,cnpj,email,telefone,cidade,estado,status,criado_em FROM companies WHERE id=?", (cid,)).fetchone()
        if not comp:
            raise HTTPException(404, "Empresa não encontrada.")
        admin = db.execute("SELECT id,nome,email,cargo,status FROM usuarios WHERE company_id=? AND administrador_primario=1 LIMIT 1", (cid,)).fetchone()
        users = [dict(r) for r in db.execute("SELECT id,nome,email,cargo,status,criado_em FROM usuarios WHERE company_id=? ORDER BY nome LIMIT 100", (cid,)).fetchall()]
        for u in users:
            u["permissoes"] = {}
        sub = db.execute("SELECT id,status,valor,criado_em,proximo_vencimento,ultimo_pagamento FROM subscriptions WHERE company_id=? ORDER BY criado_em DESC LIMIT 1", (cid,)).fetchone()
        pays = [dict(r) for r in db.execute("SELECT id,valor,status,data_cobranca,data_pagamento,metodo,criado_em FROM payments WHERE company_id=? ORDER BY criado_em DESC LIMIT 20", (cid,)).fetchall()]
        logs = [dict(r) for r in db.execute("SELECT acao,descricao,data_hora,resultado FROM audit_logs WHERE company_id=? ORDER BY data_hora DESC LIMIT 20", (cid,)).fetchall()]
        return {"company": _public_company(dict(comp)), "admin": dict(admin) if admin else None, "users": users, "subscription": dict(sub) if sub else None, "payments": pays, "logs": logs, "total_users": len(users)}

@app.patch("/api/admin/companies/{cid}/status")
def admin_company_status(cid: str, data: CompanyStatusIn, request: Request, authorization: str | None = Header(default=None)):
    require_super_admin(authorization, request)
    if data.status not in ("ativa", "bloqueada"):
        raise HTTPException(400, "Status inválido.")
    with conn() as db:
        comp = db.execute("SELECT * FROM companies WHERE id=?", (cid,)).fetchone()
        if not comp:
            raise HTTPException(404, "Empresa não encontrada.")
        db.execute("UPDATE companies SET status=?, atualizado_em=? WHERE id=?", (data.status, now(), cid))
        if data.status == "bloqueada":
            db.execute("UPDATE subscriptions SET status='bloqueada', atualizado_em=? WHERE company_id=? AND status='ativa'", (now(), cid))
        else:
            db.execute("UPDATE subscriptions SET status='ativa', atualizado_em=? WHERE company_id=? AND status='bloqueada'", (now(), cid))
        audit(db, cid, None, "admin_change_company_status", f"Empresa {cid} -> {data.status}", request.client.host if request and request.client else "", "ok")
        return {"ok": True, "status": data.status}

@app.post("/api/admin/subscriptions/{sid}/status")
def admin_subscription_status(sid: str, data: CompanyStatusIn, request: Request, authorization: str | None = Header(default=None)):
    require_super_admin(authorization, request)
    if data.status not in ("pendente","ativa","atrasada","cancelada","bloqueada"):
        raise HTTPException(400, "Status inválido.")
    sid = sid[:32]
    with conn() as db:
        sub = db.execute("SELECT * FROM subscriptions WHERE id=?", (sid,)).fetchone()
        if not sub:
            raise HTTPException(404, "Assinatura não encontrada.")
        db.execute("UPDATE subscriptions SET status=?, atualizado_em=? WHERE id=?", (data.status, now(), sid))
        audit(db, sub["company_id"], None, "admin_change_sub", f"Assinatura -> {data.status}", request.client.host if request and request.client else "", "ok")
        return {"ok": True}

@app.get("/api/admin/payments")
def admin_payments(request: Request, authorization: str | None = Header(default=None)):
    require_super_admin(authorization, request)
    with conn() as db:
        rows = db.execute("SELECT p.id,p.valor,p.status,p.data_cobranca,p.data_pagamento,p.metodo,p.criado_em,c.nome_fantasia FROM payments p JOIN companies c ON c.id=p.company_id ORDER BY p.criado_em DESC LIMIT 50").fetchall()
        return [dict(r) for r in rows]

# ---------- AUTH com verificação de assinatura ----------

def _login_rate_key(request: Request, username: str) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return f"{client_ip}:{username}"

def _check_login_rate_limit(key: str) -> None:
    now_ts = time.time()
    attempts = [t for t in LOGIN_ATTEMPTS.get(key, []) if now_ts - t < LOGIN_WINDOW_SECONDS]
    LOGIN_ATTEMPTS[key] = attempts
    if len(attempts) >= LOGIN_MAX_ATTEMPTS:
        retry_after = max(1, int(LOGIN_WINDOW_SECONDS - (now_ts - attempts[0])))
        raise HTTPException(429, f"Muitas tentativas de login. Tente novamente em {retry_after}s.")

def _register_login_failure(key: str) -> None:
    LOGIN_ATTEMPTS.setdefault(key, []).append(time.time())

@app.post("/api/auth/login")
def login(data: LoginIn, request: Request, response: Response):
    if data.website:
        raise HTTPException(400, "Requisição inválida.")
    value = data.username.strip().lower()[:120]
    rate_key = _login_rate_key(request, value)
    _check_login_rate_limit(rate_key)
    with conn() as db:
        row = db.execute("SELECT * FROM usuarios WHERE lower(email)=? OR lower(nome)=?", (value, value)).fetchone()
        if not row or row["status"] != "ativo" or not verify_password(data.password, row["senha_hash"]):
            _register_login_failure(rate_key)
            audit(db, row["company_id"] if row else None, row["id"] if row else None, "login_fail", f"Tentativa falha login {value}", request.client.host if request.client else "", "fail")
            raise HTTPException(401, "Usuário ou senha inválidos.")
        # verificacoes empresa/assinatura (exceto super_admin)
        if row["cargo"] != "super_admin":
            comp = db.execute("SELECT * FROM companies WHERE id=?", (row["company_id"],)).fetchone() if row["company_id"] else None
            if not comp:
                raise HTTPException(403, "Empresa não encontrada.")
            if comp["status"] == "bloqueada":
                raise HTTPException(403, "Empresa bloqueada. Contate o suporte.")
            sub = subscription_status(db, row["company_id"])
            if not sub:
                raise HTTPException(403, "Sem assinatura. Regularize o pagamento para continuar utilizando o sistema.")
            if sub["status"] == "pendente":
                raise HTTPException(403, "Pagamento pendente. Finalize sua assinatura para acessar o sistema.")
            if sub["status"] in ("atrasada", "bloqueada"):
                raise HTTPException(403, "Sua assinatura está vencida. Regularize o pagamento para continuar.")
            if sub["status"] == "cancelada":
                raise HTTPException(403, "Sua assinatura foi cancelada.")
            if sub["status"] != "ativa":
                raise HTTPException(403, "Assinatura inativa. Regularize o pagamento.")
        LOGIN_ATTEMPTS.pop(rate_key, None)
        token = secrets.token_urlsafe(32)
        now_ts = time.time()
        session_id = secrets.token_hex(16)
        SESSIONS[token] = {
            "id": row["id"],
            "nome": row["nome"],
            "email": row["email"],
            "cargo": row["cargo"],
            "company_id": row["company_id"],
            "login_at": now_ts,
            "last_recorded": now_ts,
            "last_seen": now_ts,
            "session_id": session_id,
            "administrador_primario": bool(row["administrador_primario"]),
        }
        stamp = now()
        db.execute("UPDATE usuarios SET ultimo_login=?, ultimo_logout=NULL WHERE id=?", (stamp, row["id"]))
        db.execute("UPDATE sessoes SET status='offline', fim=?, ultimo_heartbeat=? WHERE usuario_id=? AND status='online'", (stamp, stamp, row["id"]))
        db.execute("INSERT INTO sessoes(id,usuario_id,inicio,ultimo_heartbeat,status) VALUES(?,?,?,?,'online')", (session_id, row["id"], stamp, stamp))
        activity(db, row["id"], "login", "Usuário iniciou uma sessão", row["company_id"])
        audit(db, row["company_id"], row["id"], "login", "Login realizado", request.client.host if request.client else "", "ok")
        comp_info = None
        sub_info = None
        if row["company_id"]:
            comp_info = db.execute("SELECT id,nome_fantasia,razao_social FROM companies WHERE id=?", (row["company_id"],)).fetchone()
            sub_info = db.execute("SELECT status,proximo_vencimento,valor FROM subscriptions WHERE company_id=? LIMIT 1", (row["company_id"],)).fetchone()
        _set_auth_cookie(response, token)
        return {
            "token": token,
            "user": {
                "id": row["id"],
                "nome": row["nome"],
                "email": row["email"],
                "cargo": row["cargo"],
                "company_id": row["company_id"],
                "administrador_primario": bool(row["administrador_primario"]),
                "company": dict(comp_info) if comp_info else None,
                "subscription": dict(sub_info) if sub_info else None,
            },
        }

def record_session_time(db, session: dict[str, Any]) -> int:
    current = time.time()
    last = float(session.get("last_recorded", session.get("login_at", current)))
    delta = max(0, int(current - last))
    if delta:
        db.execute("UPDATE usuarios SET tempo_total_ativo=tempo_total_ativo+? WHERE id=?", (delta, session["id"]))
        db.execute("UPDATE sessoes SET duracao_segundos=duracao_segundos+?, ultimo_heartbeat=? WHERE id=? AND status='online'", (delta, now(), session.get("session_id")))
        session["last_recorded"] = current
    else:
        db.execute("UPDATE sessoes SET ultimo_heartbeat=? WHERE id=? AND status='online'", (now(), session.get("session_id")))
    return delta

@app.post("/api/auth/heartbeat")
def _set_auth_cookie(resp: Response, token: str):
    resp.set_cookie("edge_token", token, httponly=True, secure=COOKIE_SECURE, samesite="strict", max_age=SESSION_IDLE_TIMEOUT, path="/")

def _clear_auth_cookie(resp: Response):
    resp.delete_cookie("edge_token", path="/")

@app.post("/api/auth/heartbeat")
def heartbeat(request: Request, authorization: str | None = Header(default=None)):
    session = require_user(authorization, request)
    with conn() as db:
        added = record_session_time(db, session)
        total = db.execute("SELECT tempo_total_ativo FROM usuarios WHERE id=?", (session["id"],)).fetchone()["tempo_total_ativo"]
    return {"ok": True, "seconds_recorded": added, "total_seconds": int(total)}

@app.post("/api/auth/logout")
def logout(request: Request, response: Response, authorization: str | None = Header(default=None)):
    session = require_user(authorization, request)
    with conn() as db:
        record_session_time(db, session)
        stamp = now()
        db.execute("UPDATE usuarios SET ultimo_logout=? WHERE id=?", (stamp, session["id"]))
        db.execute("UPDATE sessoes SET status='offline', fim=?, ultimo_heartbeat=? WHERE id=?", (stamp, stamp, session.get("session_id")))
        activity(db, session["id"], "logout", "Usuário encerrou a sessão", session.get("company_id"))
        audit(db, session.get("company_id"), session["id"], "logout", "Logout", "", "ok")
    SESSIONS.pop(session.get("_token", ""), None)
    _clear_auth_cookie(response)
    return {"ok": True}

@app.get("/api/me")
def me(request: Request, authorization: str | None = Header(default=None)):
    session = require_user(authorization, request)
    with conn() as db:
        row = db.execute("SELECT * FROM usuarios WHERE id=?", (session["id"],)).fetchone()
        current = int(time.time() - float(session.get("login_at", time.time())))
        result = {k: v for k, v in user_dict(row, db).items() if k != "senha_hash"}
        result["sessao_atual_segundos"] = current
        result["online"] = True
        if session.get("company_id"):
            comp = db.execute("SELECT * FROM companies WHERE id=?", (session["company_id"],)).fetchone()
            sub = subscription_status(db, session["company_id"])
            result["company"] = _public_company(comp) if comp else None
            result["subscription"] = {k: v for k, v in sub.items() if k != "transacao_id"} if sub else None
        result.pop("senha_hash", None)
        return result

@app.get("/api/users")
def users(request: Request, authorization: str | None = Header(default=None)):
    session = require_admin(authorization, request)
    if session.get("cargo") == "super_admin":
        raise HTTPException(403, "Super admin deve usar /api/admin/companies")
    with conn() as db:
        return [_public_user(user_dict(r, db)) for r in db.execute("SELECT * FROM usuarios WHERE company_id=? ORDER BY nome LIMIT 100", (session["company_id"],)).fetchall()]

@app.post("/api/users")
def create_user(data: UserIn, request: Request, authorization: str | None = Header(default=None)):
    admin = require_admin(authorization, request)
    if admin.get("cargo") == "super_admin":
        raise HTTPException(403, "Super admin não cria usuários de empresa por esta rota.")
    if data.cargo not in ("administrador", "usuario"):
        raise HTTPException(400, "Cargo inválido.")
    if not data.senha or len(data.senha) < 4:
        raise HTTPException(400, "A senha deve possuir pelo menos 4 caracteres.")
    with conn() as db:
        if db.execute("SELECT 1 FROM usuarios WHERE lower(email)=?", (data.email.strip().lower(),)).fetchone():
            raise HTTPException(409, "Já existe um usuário com este e-mail.")
        # valida cameras pertencem a mesma empresa
        for cid in data.cameras:
            cam = db.execute("SELECT company_id FROM cameras WHERE id=?", (cid,)).fetchone()
            if not cam or cam["company_id"] != admin["company_id"]:
                raise HTTPException(403, "Câmera não pertence à sua empresa.")
        uid = secrets.token_hex(12)
        db.execute("INSERT INTO usuarios(id,nome,email,senha_hash,cargo,status,criado_em,company_id) VALUES(?,?,?,?,?,?,?,?)",
            (uid, data.nome.strip(), data.email.strip().lower(), hash_password(data.senha), data.cargo, data.status, now(), admin["company_id"]))
        perms = default_permissions(data.cargo)
        perms.update({k: bool(v) for k, v in data.permissoes.items() if k in PERMISSION_KEYS})
        if data.cargo == "administrador":
            perms = {k: True for k in PERMISSION_KEYS}
        db.execute("INSERT INTO permissoes(usuario_id," + ",".join(PERMISSION_KEYS) + ") VALUES(?" + ",?" * len(PERMISSION_KEYS) + ")", (uid, *[int(perms[k]) for k in PERMISSION_KEYS]))
        for cid in data.cameras:
            if db.execute("SELECT 1 FROM cameras WHERE id=? AND company_id=?", (cid, admin["company_id"])).fetchone():
                db.execute("INSERT OR IGNORE INTO usuario_cameras VALUES(?,?)", (uid, cid))
        activity(db, admin["id"], "criação de usuário", f"Usuário {data.email.strip().lower()} criado", admin["company_id"])
        audit(db, admin["company_id"], admin["id"], "create_user", f"Criou usuario {data.email}", "", "ok")
        return user_dict(db.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone(), db)

@app.put("/api/users/{uid}")
def update_user(uid: str, data: UserIn, request: Request, authorization: str | None = Header(default=None)):
    admin = require_admin(authorization, request)
    with conn() as db:
        row = db.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        if not row:
            raise HTTPException(404, "Usuário não encontrado.")
        if row["company_id"] != admin["company_id"] and admin.get("cargo") != "super_admin":
            raise HTTPException(403, "Você não possui acesso a este usuário.")
        if db.execute("SELECT 1 FROM usuarios WHERE lower(email)=? AND id<>?", (data.email.strip().lower(), uid)).fetchone():
            raise HTTPException(409, "Já existe um usuário com este e-mail.")
        if row["id"] == admin["id"] and data.status != "ativo":
            raise HTTPException(400, "Não é possível desativar a própria conta.")
        if row["cargo"] == "administrador" and row["status"] == "ativo" and (data.cargo != "administrador" or data.status != "ativo"):
            n = db.execute("SELECT COUNT(*) n FROM usuarios WHERE company_id=? AND cargo='administrador' AND status='ativo'", (admin["company_id"],)).fetchone()["n"]
            if n <= 1:
                raise HTTPException(400, "Não é possível remover o último administrador ativo.")
        db.execute("UPDATE usuarios SET nome=?,email=?,cargo=?,status=?" + (",senha_hash=?" if data.senha else "") + " WHERE id=?",
            (data.nome.strip(), data.email.strip().lower(), data.cargo, data.status, *([hash_password(data.senha)] if data.senha else []), uid))
        perms = default_permissions(data.cargo)
        perms.update({k: bool(v) for k, v in data.permissoes.items() if k in PERMISSION_KEYS})
        if data.cargo == "administrador":
            perms = {k: True for k in PERMISSION_KEYS}
        db.execute("UPDATE permissoes SET " + ",".join(f"{k}=?" for k in PERMISSION_KEYS) + " WHERE usuario_id=?", (*[int(perms[k]) for k in PERMISSION_KEYS], uid))
        db.execute("DELETE FROM usuario_cameras WHERE usuario_id=?", (uid,))
        for cid in data.cameras:
            cam = db.execute("SELECT company_id FROM cameras WHERE id=?", (cid,)).fetchone()
            if cam and cam["company_id"] == admin["company_id"]:
                db.execute("INSERT OR IGNORE INTO usuario_cameras VALUES(?,?)", (uid, cid))
        activity(db, admin["id"], "alteração de usuário", f"Usuário {data.email.strip().lower()} atualizado", admin["company_id"])
        return user_dict(db.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone(), db)

@app.patch("/api/users/{uid}/status")
def toggle_user(uid: str, request: Request, authorization: str | None = Header(default=None)):
    admin = require_admin(authorization, request)
    with conn() as db:
        row = db.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        if not row:
            raise HTTPException(404, "Usuário não encontrado.")
        if row["company_id"] != admin["company_id"]:
            raise HTTPException(403, "Acesso negado.")
        if uid == admin["id"]:
            raise HTTPException(400, "Não é possível bloquear a própria conta.")
        if row["cargo"] == "administrador" and row["status"] == "ativo" and db.execute("SELECT COUNT(*) n FROM usuarios WHERE company_id=? AND cargo='administrador' AND status='ativo'", (admin["company_id"],)).fetchone()["n"] <= 1:
            raise HTTPException(400, "Mantenha pelo menos um administrador ativo.")
        status = "bloqueado" if row["status"] == "ativo" else "ativo"
        db.execute("UPDATE usuarios SET status=? WHERE id=?", (status, uid))
        activity(db, admin["id"], "status de usuário", f'Conta {row["email"]}: {status}', admin["company_id"])
        return {"status": status}

@app.delete("/api/users/{uid}")
def delete_user(uid: str, request: Request, authorization: str | None = Header(default=None)):
    admin = require_admin(authorization, request)
    with conn() as db:
        row = db.execute("SELECT * FROM usuarios WHERE id=?", (uid,)).fetchone()
        if not row:
            raise HTTPException(404, "Usuário não encontrado.")
        if row["company_id"] != admin["company_id"]:
            raise HTTPException(403, "Acesso negado.")
        if uid == admin["id"]:
            raise HTTPException(400, "Não é possível excluir a própria conta.")
        if row["cargo"] == "administrador":
            requester = db.execute("SELECT administrador_primario FROM usuarios WHERE id=?", (admin["id"],)).fetchone()
            if not requester or not bool(requester["administrador_primario"]):
                raise HTTPException(403, "Apenas o administrador primário pode excluir uma conta de administrador.")
        db.execute("DELETE FROM usuarios WHERE id=?", (uid,))
        activity(db, admin["id"], "exclusão de usuário", f'Usuário {row["email"]} excluído permanentemente', admin["company_id"])
    for tok, sess in list(SESSIONS.items()):
        if sess.get("id") == uid:
            SESSIONS.pop(tok, None)
    return {"ok": True}

@app.get("/api/ai/status")
def ai_status():
    try:
        detector = get_detector()
        return {"ready": True, "model": detector.model_path, "classes": detector.names, "confidence": AI_CONFIDENCE, "iou": AI_IOU}
    except Exception as exc:
        return {"ready": False, "model": MODEL_PATH, "error": str(exc)}

@app.websocket("/ws/detection")
async def websocket_detection(websocket: WebSocket):
    await websocket.accept()
    try:
        detector = get_detector()
        await websocket.send_json({"type": "ready", "model": Path(detector.model_path).name, "classes": detector.names})
        while True:
            payload = await websocket.receive_json()
            image = payload.get("image", "")
            if not image:
                await websocket.send_json({"type": "error", "message": "Frame sem imagem."})
                continue
            try:
                encoded = image.split(",", 1)[1] if "," in image else image
                raw = base64.b64decode(encoded)
                array = __import__("numpy").frombuffer(raw, dtype=__import__("numpy").uint8)
                frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError("Não foi possível decodificar o frame JPEG.")
                detections = detector.infer(frame)
                risk = assess_risk(detections)
                # company isolation for alert
                cam_id = payload.get("camera_id")
                comp_id = None
                if cam_id:
                    with conn() as db:
                        cr = db.execute("SELECT company_id FROM cameras WHERE id=?", (cam_id,)).fetchone()
                        if cr:
                            comp_id = cr["company_id"]
                alert_id = create_ai_alert(cam_id, risk, comp_id)
                await websocket.send_json({"type": "result", "camera_id": cam_id, "detections": detections, "risk": risk, "alert_created": alert_id})
            except Exception as exc:
                await websocket.send_json({"type": "error", "message": f"Erro na inferência: {exc}"})
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass

@app.get("/api/cameras")
def cameras(request: Request, authorization: str | None = Header(default=None)):
    session = require_permission(authorization, "visualizar_cameras", request)
    with conn() as db:
        cid = session.get("company_id")
        if session.get("cargo") == "super_admin":
            rows = db.execute("SELECT id,nome,tipo,localizacao,status,criado_em FROM cameras ORDER BY nome LIMIT 100").fetchall()
        elif session["cargo"] == "administrador":
            rows = db.execute("SELECT id,nome,tipo,localizacao,status,criado_em FROM cameras WHERE company_id=? ORDER BY nome LIMIT 100", (cid,)).fetchall()
        else:
            rows = db.execute("SELECT c.id,c.nome,c.tipo,c.localizacao,c.status,c.criado_em FROM cameras c JOIN usuario_cameras uc ON uc.camera_id=c.id WHERE uc.usuario_id=? AND c.company_id=? ORDER BY c.nome LIMIT 100", (session["id"], cid)).fetchall()
        return [dict(r) for r in rows]

@app.post("/api/cameras")
def create_camera(data: CameraIn, request: Request, authorization: str | None = Header(default=None)):
    session = require_admin(authorization, request)
    if session.get("cargo") == "super_admin":
        raise HTTPException(403, "Super admin não cadastra câmeras.")
    cid = secrets.token_hex(12)
    with conn() as db:
        db.execute("INSERT INTO cameras(id,nome,tipo,device_id,endereco,localizacao,status,criado_em,company_id) VALUES(?,?,?,?,?,?,?,?,?)",
            (cid, data.nome.strip()[:80], data.tipo, (data.device_id or "")[:200], (data.endereco or "")[:500], (data.localizacao or "")[:80], data.status, now(), session["company_id"]))
        activity(db, session["id"], "criação de câmera", f"Câmera cadastrada", session["company_id"])
        return dict(db.execute("SELECT id,nome,tipo,localizacao,status,criado_em FROM cameras WHERE id=?", (cid,)).fetchone())

@app.post("/api/cameras/test")
def test_camera(data: CameraTestIn, request: Request, authorization: str | None = Header(default=None)):
    require_admin(authorization, request)
    if not (data.endereco.startswith("rtsp://") or data.endereco.startswith("http://") or data.endereco.startswith("https://")):
        raise HTTPException(400, "O endereço deve iniciar com rtsp://, http:// ou https://.")
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(test_ip_stream, data.endereco)
        try:
            result = future.result(timeout=CAMERA_TEST_TIMEOUT)
        except FutureTimeoutError:
            raise HTTPException(504, f"Tempo limite de {int(CAMERA_TEST_TIMEOUT)}s excedido ao testar a câmera.")
        except Exception:
            result = None
    if not result:
        raise HTTPException(422, "Não foi possível abrir o stream. Verifique endereço, credenciais, rede e se a câmera disponibiliza RTSP/HTTP.")
    return {"ok": True, "width": result[0], "height": result[1], "message": "Stream acessível."}

@app.get("/api/cameras/{cid}/mjpeg")
def camera_mjpeg(cid: str, request: Request, token: str | None = None, authorization: str | None = Header(default=None)):
    tok = token or _extract_token(authorization, request)
    session = get_session_for_token(tok) if tok else None
    if not session:
        raise HTTPException(401, "Sessão inválida ou expirada.")
    with conn() as db:
        cam = db.execute("SELECT * FROM cameras WHERE id=?", (cid,)).fetchone()
        if not cam:
            raise HTTPException(404, "Câmera não encontrada.")
        if session.get("cargo") != "super_admin" and cam["company_id"] != session.get("company_id"):
            raise HTTPException(403, "Você não possui acesso a esta câmera.")
        if session["cargo"] not in ("administrador", "super_admin"):
            allowed = db.execute("SELECT 1 FROM usuario_cameras WHERE usuario_id=? AND camera_id=?", (session["id"], cid)).fetchone()
            if not allowed:
                raise HTTPException(403, "Você não possui acesso a esta câmera.")
        if cam["tipo"] not in ("ip", "rtsp", "wifi"):
            raise HTTPException(400, "Esta câmera não é uma fonte IP.")
        url = cam["endereco"]
    cap = open_ip_camera(url or "")
    if cap is None:
        raise HTTPException(422, "Não foi possível abrir o stream da câmera.")
    def frames():
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    with conn() as db:
                        db.execute("UPDATE cameras SET status='offline', ultima_verificacao=?, ultimo_erro=? WHERE id=?", (now(), "Stream interrompido", cid))
                    break
                with conn() as db:
                    db.execute("UPDATE cameras SET status='online', ultima_verificacao=?, ultimo_online=?, ultimo_erro=NULL WHERE id=?", (now(), now(), cid))
                ok, encoded = cv2.imencode(".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not ok:
                    continue
                yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(encoded)).encode() + b"\r\n\r\n" + encoded.tobytes() + b"\r\n"
        finally:
            cap.release()
    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame", headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0", "Pragma": "no-cache"})

@app.delete("/api/cameras/{cid}")
def delete_camera(cid: str, authorization: str | None = Header(default=None)):
    admin = require_admin(authorization)
    with conn() as db:
        cam = db.execute("SELECT * FROM cameras WHERE id=?", (cid,)).fetchone()
        if not cam:
            raise HTTPException(404, "Câmera não encontrada.")
        if cam["company_id"] != admin["company_id"] and admin.get("cargo") != "super_admin":
            raise HTTPException(403, "Acesso negado.")
        db.execute("DELETE FROM cameras WHERE id=?", (cid,))
        activity(db, admin["id"], "remoção de câmera", f"Câmera {cid} removida", admin.get("company_id"))
    return {"ok": True}

@app.get("/api/alerts")
def alerts(request: Request, authorization: str | None = Header(default=None), camera_id: str | None = None, level: str | None = None, status: str | None = None, date: str | None = None):
    session = require_permission(authorization, "visualizar_alertas", request)
    for v in [camera_id, level, status, date]:
        if v and len(v) > 80:
            raise HTTPException(400, "Filtro inválido.")
    with conn() as db:
        cid = session.get("company_id")
        if session.get("cargo") == "super_admin":
            q = "SELECT a.id,a.tipo,a.nivel,a.descricao,a.status,a.data_hora,a.camera_id FROM alertas a WHERE 1=1"
            params = []
        elif session["cargo"] == "administrador":
            q = "SELECT a.id,a.tipo,a.nivel,a.descricao,a.status,a.data_hora,a.camera_id FROM alertas a WHERE a.company_id=?"
            params = [cid]
        else:
            q = "SELECT a.id,a.tipo,a.nivel,a.descricao,a.status,a.data_hora,a.camera_id FROM alertas a JOIN usuario_cameras uc ON uc.camera_id=a.camera_id WHERE uc.usuario_id=? AND a.company_id=?"
            params = [session["id"], cid]
        for col, val in [("camera_id", camera_id), ("nivel", level), ("status", status)]:
            if val:
                q += f" AND a.{col}=?"
                params.append(val)
        if date:
            q += " AND substr(a.data_hora,1,10)=?"
            params.append(date)
        q += " ORDER BY a.data_hora DESC LIMIT 100"
        return [dict(r) for r in db.execute(q, params).fetchall()]

@app.post("/api/alerts")
def create_alert(data: AlertIn, request: Request, authorization: str | None = Header(default=None)):
    session = require_user_active(authorization, request)
    aid = secrets.token_hex(12)
    with conn() as db:
        if data.camera_id:
            cam = db.execute("SELECT company_id FROM cameras WHERE id=?", (data.camera_id,)).fetchone()
            if cam and cam["company_id"] != session.get("company_id") and session.get("cargo") != "super_admin":
                raise HTTPException(403, "Câmera não pertence à sua empresa.")
        db.execute("INSERT INTO alertas(id,camera_id,tipo,nivel,descricao,status,data_hora,company_id) VALUES(?,?,?,?,?,?,?,?)",
            (aid, data.camera_id, data.tipo, data.nivel, data.descricao[:500], data.status, now(), session.get("company_id")))
        activity(db, session["id"], "alerta", data.descricao[:120], session.get("company_id"))
    return {"id": aid}

@app.get("/api/monitor/usuarios")
def monitor_users(request: Request, authorization: str | None = Header(default=None)):
    session = require_admin(authorization, request)
    with conn() as db:
        if session.get("cargo") == "super_admin":
            rows = db.execute("""SELECT u.id,u.nome,u.email,u.cargo,u.status,u.ultimo_login,u.ultimo_logout,u.tempo_total_ativo,
            CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END AS online,
            COALESCE(s.duracao_segundos,0) AS sessao_atual_segundos,
            s.ultimo_heartbeat FROM usuarios u LEFT JOIN sessoes s ON s.usuario_id=u.id AND s.status='online' ORDER BY u.nome""").fetchall()
        else:
            rows = db.execute("""SELECT u.id,u.nome,u.email,u.cargo,u.status,u.ultimo_login,u.ultimo_logout,u.tempo_total_ativo,
            CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END AS online,
            COALESCE(s.duracao_segundos,0) AS sessao_atual_segundos,
            s.ultimo_heartbeat FROM usuarios u LEFT JOIN sessoes s ON s.usuario_id=u.id AND s.status='online' WHERE u.company_id=? ORDER BY u.nome""", (session["company_id"],)).fetchall()
        return [dict(r) for r in rows]

@app.get("/api/activities")
def activities(request: Request, authorization: str | None = Header(default=None)):
    session = require_admin(authorization, request)
    with conn() as db:
        if session.get("cargo") == "super_admin":
            return [dict(r) for r in db.execute("SELECT id,acao,descricao,data_hora FROM atividades ORDER BY data_hora DESC LIMIT 100").fetchall()]
        return [dict(r) for r in db.execute("SELECT id,acao,descricao,data_hora FROM atividades WHERE company_id=? ORDER BY data_hora DESC LIMIT 100", (session["company_id"],)).fetchall()]

@app.get("/api/dashboard")
def dashboard(request: Request, authorization: str | None = Header(default=None)):
    session = require_user_active(authorization, request)
    with conn() as db:
        cid = session.get("company_id")
        if session.get("cargo") == "super_admin":
            cams = db.execute("SELECT id,nome,tipo,status,criado_em FROM cameras ORDER BY nome LIMIT 20").fetchall()
            alerts_n = db.execute("SELECT id,tipo,nivel,descricao,status,data_hora FROM alertas ORDER BY data_hora DESC LIMIT 10").fetchall()
            acts = db.execute("SELECT id,acao,descricao,data_hora FROM atividades ORDER BY data_hora DESC LIMIT 10").fetchall()
            users = db.execute("SELECT id,nome,email,cargo,status FROM usuarios ORDER BY nome LIMIT 20").fetchall()
        elif session["cargo"] == "administrador":
            cams = db.execute("SELECT id,nome,tipo,status,criado_em FROM cameras WHERE company_id=? ORDER BY nome LIMIT 20", (cid,)).fetchall()
            alerts_n = db.execute("SELECT id,tipo,nivel,descricao,status,data_hora FROM alertas WHERE company_id=? ORDER BY data_hora DESC LIMIT 10", (cid,)).fetchall()
            acts = db.execute("SELECT id,acao,descricao,data_hora FROM atividades WHERE company_id=? ORDER BY data_hora DESC LIMIT 10", (cid,)).fetchall()
            users = db.execute("SELECT id,nome,email,cargo,status FROM usuarios WHERE company_id=? ORDER BY nome LIMIT 20", (cid,)).fetchall()
        else:
            cams = db.execute("SELECT c.id,c.nome,c.tipo,c.status,c.criado_em FROM cameras c JOIN usuario_cameras uc ON uc.camera_id=c.id WHERE uc.usuario_id=? AND c.company_id=? ORDER BY c.nome LIMIT 20", (session["id"], cid)).fetchall()
            ids = [r["id"] for r in cams]
            alerts_n = db.execute("SELECT id,tipo,nivel,descricao,status,data_hora FROM alertas WHERE company_id=? AND camera_id IN (" + ",".join("?" * len(ids)) + ") ORDER BY data_hora DESC LIMIT 10", (cid, *ids)).fetchall() if ids else []
            acts = []
            users = []
        return {"cameras": [dict(r) for r in cams], "alerts": [dict(r) for r in alerts_n], "activities": [dict(r) for r in acts], "users": [dict(r) for r in users]}

@app.get("/api/reports")
def reports(request: Request, authorization: str | None = Header(default=None)):
    session = require_permission(authorization, "visualizar_relatorios", request)
    with conn() as db:
        cid = session.get("company_id")
        if session.get("cargo") == "super_admin":
            filt = ""
            p = []
        else:
            filt = " WHERE company_id=?"
            p = [cid]
            # para contagens que tem company_id, usa filtro; senao sem
        def count(tbl, extra=""):
            q = f"SELECT COUNT(*) n FROM {tbl}"
            pp = []
            if tbl in ("cameras","usuarios","alertas") and cid and session.get("cargo")!="super_admin":
                q += " WHERE company_id=?"
                pp = [cid]
                if extra:
                    q += f" AND {extra}"
            elif extra:
                q += f" WHERE {extra}"
            return db.execute(q, pp).fetchone()["n"]
        total_c = count("cameras")
        active_c = count("cameras","status='online'")
        total_u = count("usuarios")
        active_u = count("usuarios","status='ativo'")
        alerts_n = count("alertas")
        open_n = count("alertas","status='Aberto'")
        if session.get("cargo")=="super_admin":
            total_seconds = db.execute("SELECT COALESCE(SUM(tempo_total_ativo),0) n FROM usuarios").fetchone()["n"]
        else:
            total_seconds = db.execute("SELECT COALESCE(SUM(tempo_total_ativo),0) n FROM usuarios WHERE company_id=?", (cid,)).fetchone()["n"]
        levels = {}
        for l in ["Crítico","Alto","Normal"]:
            if session.get("cargo")=="super_admin":
                levels[l]=db.execute("SELECT COUNT(*) n FROM alertas WHERE nivel=?", (l,)).fetchone()["n"]
            else:
                levels[l]=db.execute("SELECT COUNT(*) n FROM alertas WHERE nivel=? AND company_id=?", (l,cid)).fetchone()["n"]
        if session.get("cargo")=="super_admin":
            online = db.execute("SELECT COUNT(*) n FROM sessoes WHERE status='online'").fetchone()["n"]
        else:
            online = db.execute("SELECT COUNT(*) n FROM sessoes s JOIN usuarios u ON u.id=s.usuario_id WHERE s.status='online' AND u.company_id=?", (cid,)).fetchone()["n"]
        return {"cameras": total_c, "active_cameras": active_c, "users": total_u, "active_users": active_u, "online_users": online, "alerts": alerts_n, "open_alerts": open_n, "total_seconds": total_seconds, "alert_levels": levels}
