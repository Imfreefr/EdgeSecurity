from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Header, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
import cv2
import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from services.detector import SafetyDetector
from services.risk_engine import assess_risk
import base64

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv('DB_PATH', str(BASE_DIR / 'edgesecurity.db')))
CORS_VALUE = os.getenv(
    'CORS_ORIGINS',
    'http://localhost:5500,http://127.0.0.1:5500'
).strip()
CORS_ORIGINS = ['*'] if CORS_VALUE == '*' else [
    origin.strip()
    for origin in CORS_VALUE.split(',')
    if origin.strip()
]

app = FastAPI(title='EdgeSecurity API', version='0.6.4')
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=['*'],
    allow_headers=['*'],
)

SESSIONS: dict[str, dict[str, Any]] = {}
CAMERA_TEST_TIMEOUT = float(os.getenv('CAMERA_TEST_TIMEOUT', '8'))
CAMERA_IDLE_TIMEOUT = int(os.getenv('CAMERA_IDLE_TIMEOUT', '35'))
MODEL_PATH = os.getenv('MODEL_PATH', str(BASE_DIR / 'model' / 'edgev1.pt'))
AI_CONFIDENCE = float(os.getenv('AI_CONFIDENCE', '0.40'))
AI_IOU = float(os.getenv('AI_IOU', '0.50'))
_detector = None
_detector_error = None
RISK_ALERT_COOLDOWN = float(os.getenv('RISK_ALERT_COOLDOWN', '10'))
_last_risk_alert: dict[tuple[str, str, str], float] = {}

def record_risk_alert(camera_id: str | None, risk: dict):
    """Persiste alertas high/critical gerados automaticamente pela IA.

    Há um cooldown por câmera/par de tracks para impedir que um único evento
    gere centenas de registros enquanto a pessoa permanece na zona de risco.
    """
    level = risk.get("level", "safe")
    if level not in {"high", "critical"}:
        return None

    camera_key = camera_id or "sem-camera"
    created = []
    current = time.time()
    for pair in risk.get("pairs", []):
        person_id = pair.get("person_track_id")
        machine_id = pair.get("machine_track_id")
        key = (camera_key, str(person_id), str(machine_id))
        last = _last_risk_alert.get(key, 0)
        if current - last < RISK_ALERT_COOLDOWN:
            continue

        _last_risk_alert[key] = current
        level_label = "Crítico" if level == "critical" else "Alto"
        machine_label = pair.get("machine_label", "empilhadeira")
        description = (
            f"Risco automático: pessoa e {machine_label} em proximidade perigosa "
            f"({pair.get('gap_pixels', 0)} px). "
            f"Track pessoa={person_id}, máquina={machine_id}."
        )
        aid = secrets.token_hex(12)
        with conn() as db:
            db.execute(
                'INSERT INTO alertas(id,camera_id,tipo,nivel,descricao,status,data_hora) VALUES(?,?,?,?,?,?,?)',
                (aid, camera_id, 'Proximidade pessoa-empilhadeira', level_label, description, 'Aberto', now())
            )
        created.append({
            "id": aid, "camera_id": camera_id, "tipo": "Proximidade pessoa-empilhadeira",
            "nivel": level_label, "descricao": description, "data_hora": now()
        })
    return created or None


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
        raise RuntimeError(f'Falha ao carregar o modelo YOLO: {exc}') from exc


PERMISSION_KEYS = [
    'visualizar_cameras', 'usar_camera_dispositivo', 'gerenciar_cameras',
    'visualizar_alertas', 'visualizar_relatorios', 'gerenciar_usuarios',
    'gerenciar_permissoes', 'acessar_configuracoes'
]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute('PRAGMA foreign_keys = ON')
    return c


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with conn() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id TEXT PRIMARY KEY, nome TEXT NOT NULL, email TEXT NOT NULL UNIQUE,
            senha_hash TEXT NOT NULL, cargo TEXT NOT NULL CHECK(cargo IN ('administrador','usuario')),
            status TEXT NOT NULL DEFAULT 'ativo', ultimo_login TEXT, ultimo_logout TEXT,
            criado_em TEXT NOT NULL, tempo_total_ativo INTEGER NOT NULL DEFAULT 0
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
            device_id TEXT, endereco TEXT, localizacao TEXT, status TEXT NOT NULL DEFAULT 'ativo', criado_em TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS usuario_cameras (
            usuario_id TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            camera_id TEXT NOT NULL REFERENCES cameras(id) ON DELETE CASCADE,
            PRIMARY KEY(usuario_id, camera_id)
        );
        CREATE TABLE IF NOT EXISTS alertas (
            id TEXT PRIMARY KEY, camera_id TEXT REFERENCES cameras(id) ON DELETE SET NULL,
            tipo TEXT NOT NULL, nivel TEXT NOT NULL, descricao TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Aberto', data_hora TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessoes (
            id TEXT PRIMARY KEY, usuario_id TEXT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
            inicio TEXT NOT NULL, ultimo_heartbeat TEXT NOT NULL, fim TEXT,
            duracao_segundos INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'online'
        );
        CREATE INDEX IF NOT EXISTS idx_sessoes_usuario ON sessoes(usuario_id);
        CREATE INDEX IF NOT EXISTS idx_sessoes_status ON sessoes(status);
        CREATE TABLE IF NOT EXISTS atividades (
            id TEXT PRIMARY KEY, usuario_id TEXT REFERENCES usuarios(id) ON DELETE SET NULL,
            acao TEXT NOT NULL, descricao TEXT NOT NULL, data_hora TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_alertas_data ON alertas(data_hora);
        CREATE INDEX IF NOT EXISTS idx_atividades_data ON atividades(data_hora);
        ''')
        # Migrações leves para instalações criadas nas versões anteriores.
        camera_cols = {r['name'] for r in db.execute('PRAGMA table_info(cameras)').fetchall()}
        for name, definition in [('ultima_verificacao','TEXT'),('ultimo_online','TEXT'),('ultimo_erro','TEXT')]:
            if name not in camera_cols:
                db.execute(f'ALTER TABLE cameras ADD COLUMN {name} {definition}')


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 120_000)
    return f'pbkdf2_sha256$120000${salt.hex()}${digest.hex()}'


def verify_password(password: str, encoded: str) -> bool:
    try:
        alg, rounds, salt_hex, digest_hex = encoded.split('$')
        candidate = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt_hex), int(rounds)).hex()
        return alg == 'pbkdf2_sha256' and hmac.compare_digest(candidate, digest_hex)
    except Exception:
        return False


def default_permissions(cargo: str) -> dict[str, bool]:
    admin = cargo == 'administrador'
    return {k: (True if k in ('visualizar_cameras','usar_camera_dispositivo','visualizar_alertas','visualizar_relatorios','acessar_configuracoes') else admin) for k in PERMISSION_KEYS}


def user_dict(row, db) -> dict[str, Any]:
    p = db.execute('SELECT * FROM permissoes WHERE usuario_id=?', (row['id'],)).fetchone()
    permissions = {k: bool(p[k]) for k in PERMISSION_KEYS} if p else default_permissions(row['cargo'])
    cams = [r['camera_id'] for r in db.execute('SELECT camera_id FROM usuario_cameras WHERE usuario_id=?', (row['id'],)).fetchall()]
    return {**dict(row), 'senha': None, 'permissoes': permissions, 'cameras': cams}


def require_user(authorization: str | None):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Autenticação necessária.')
    token = authorization[7:]
    session = SESSIONS.get(token)
    if not session:
        raise HTTPException(401, 'Sessão inválida ou expirada.')
    return session


def require_admin(authorization: str | None):
    session = require_user(authorization)
    if session['cargo'] != 'administrador':
        raise HTTPException(403, 'Acesso restrito ao administrador.')
    return session

def require_permission(authorization: str | None, key: str):
    session = require_user(authorization)
    if session['cargo'] == 'administrador':
        return session
    with conn() as db:
        row = db.execute(f'SELECT {key} FROM permissoes WHERE usuario_id=?', (session['id'],)).fetchone()
    if not row or not bool(row[key]):
        raise HTTPException(403, 'Você não possui permissão para esta operação.')
    return session


def activity(db, user_id, action, description):
    db.execute('INSERT INTO atividades(id,usuario_id,acao,descricao,data_hora) VALUES(?,?,?,?,?)', (secrets.token_hex(12), user_id, action, description, now()))


class LoginIn(BaseModel):
    username: str
    password: str


class SetupIn(BaseModel):
    nome: str = Field(min_length=1)
    email: str
    senha: str = Field(min_length=4)


class UserIn(BaseModel):
    nome: str = Field(min_length=1)
    email: str
    senha: str | None = None
    cargo: str = 'usuario'
    status: str = 'ativo'
    permissoes: dict[str, bool] = {}
    cameras: list[str] = []


class CameraIn(BaseModel):
    nome: str = Field(min_length=1)
    tipo: str = 'browser'
    device_id: str | None = None
    endereco: str | None = None
    localizacao: str | None = None
    status: str = 'ativo'

class CameraTestIn(BaseModel):
    endereco: str = Field(min_length=1)

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


class AlertIn(BaseModel):
    camera_id: str | None = None
    tipo: str
    nivel: str
    descricao: str
    status: str = 'Aberto'


@app.on_event('startup')
def startup():
    init_db()


@app.get('/api/health')
def health():
    with conn() as db:
        users = db.execute('SELECT COUNT(*) n FROM usuarios').fetchone()['n']
    return {'ok': True, 'database': str(DB_PATH), 'users': users}


@app.get('/api/setup/status')
def setup_status():
    with conn() as db:
        return {'needs_setup': db.execute('SELECT COUNT(*) n FROM usuarios').fetchone()['n'] == 0}


@app.post('/api/setup')
def setup(data: SetupIn):
    with conn() as db:
        if db.execute('SELECT COUNT(*) n FROM usuarios').fetchone()['n']:
            raise HTTPException(409, 'O administrador inicial já foi criado.')
        uid = secrets.token_hex(12)
        db.execute('INSERT INTO usuarios(id,nome,email,senha_hash,cargo,status,criado_em) VALUES(?,?,?,?,?,?,?)', (uid, data.nome.strip(), data.email.strip().lower(), hash_password(data.senha), 'administrador', 'ativo', now()))
        p = default_permissions('administrador')
        db.execute('INSERT INTO permissoes(usuario_id,' + ','.join(PERMISSION_KEYS) + ') VALUES(?' + ',?'*len(PERMISSION_KEYS) + ')', (uid, *[int(p[k]) for k in PERMISSION_KEYS]))
        activity(db, uid, 'criação', 'Administrador inicial criado')
    return {'ok': True}


@app.post('/api/auth/login')
def login(data: LoginIn):
    value = data.username.strip().lower()
    with conn() as db:
        row = db.execute('SELECT * FROM usuarios WHERE lower(email)=? OR lower(nome)=?', (value, value)).fetchone()
        if not row or row['status'] != 'ativo' or not verify_password(data.password, row['senha_hash']):
            raise HTTPException(401, 'Usuário ou senha inválidos.')
        token = secrets.token_urlsafe(32)
        now_ts = time.time()
        session_id = secrets.token_hex(16)
        SESSIONS[token] = {'id': row['id'], 'nome': row['nome'], 'email': row['email'], 'cargo': row['cargo'], 'login_at': now_ts, 'last_recorded': now_ts, 'session_id': session_id}
        stamp = now()
        db.execute('UPDATE usuarios SET ultimo_login=?, ultimo_logout=NULL WHERE id=?', (stamp, row['id']))
        db.execute("UPDATE sessoes SET status='offline', fim=?, ultimo_heartbeat=? WHERE usuario_id=? AND status='online'", (stamp, stamp, row['id']))
        db.execute("INSERT INTO sessoes(id,usuario_id,inicio,ultimo_heartbeat,status) VALUES(?,?,?,?,'online')", (session_id,row['id'],stamp,stamp))
        activity(db, row['id'], 'login', 'Usuário iniciou uma sessão')
    return {'token': token, 'user': {'id': row['id'], 'nome': row['nome'], 'email': row['email'], 'cargo': row['cargo']}}


def record_session_time(db, session: dict[str, Any]) -> int:
    """Persist the portion of the current session not yet written to SQLite."""
    current = time.time()
    last = float(session.get('last_recorded', session.get('login_at', current)))
    delta = max(0, int(current - last))
    if delta:
        db.execute('UPDATE usuarios SET tempo_total_ativo=tempo_total_ativo+? WHERE id=?', (delta, session['id']))
        db.execute("UPDATE sessoes SET duracao_segundos=duracao_segundos+?, ultimo_heartbeat=? WHERE id=? AND status='online'", (delta, now(), session.get('session_id')))
        session['last_recorded'] = current
    else:
        db.execute("UPDATE sessoes SET ultimo_heartbeat=? WHERE id=? AND status='online'", (now(), session.get('session_id')))
    return delta


@app.post('/api/auth/heartbeat')
def heartbeat(authorization: str | None = Header(default=None)):
    session = require_user(authorization)
    with conn() as db:
        added = record_session_time(db, session)
        total = db.execute('SELECT tempo_total_ativo FROM usuarios WHERE id=?', (session['id'],)).fetchone()['tempo_total_ativo']
    return {'ok': True, 'seconds_recorded': added, 'total_seconds': int(total)}


@app.post('/api/auth/logout')
def logout(authorization: str | None = Header(default=None)):
    session = require_user(authorization)
    with conn() as db:
        record_session_time(db, session)
        stamp = now()
        db.execute('UPDATE usuarios SET ultimo_logout=? WHERE id=?', (stamp, session['id']))
        db.execute("UPDATE sessoes SET status='offline', fim=?, ultimo_heartbeat=? WHERE id=?", (stamp, stamp, session.get('session_id')))
        activity(db, session['id'], 'logout', 'Usuário encerrou a sessão')
    SESSIONS.pop(authorization[7:], None)
    return {'ok': True}


@app.get('/api/me')
def me(authorization: str | None = Header(default=None)):
    session = require_user(authorization)
    with conn() as db:
        row = db.execute('SELECT * FROM usuarios WHERE id=?', (session['id'],)).fetchone()
        current = int(time.time() - float(session.get('login_at', time.time())))
        result = user_dict(row, db)
        result['sessao_atual_segundos'] = current
        result['online'] = True
        return result


@app.get('/api/users')
def users(authorization: str | None = Header(default=None)):
    require_admin(authorization)
    with conn() as db:
        return [user_dict(r, db) for r in db.execute('SELECT * FROM usuarios ORDER BY nome').fetchall()]


@app.post('/api/users')
def create_user(data: UserIn, authorization: str | None = Header(default=None)):
    admin = require_admin(authorization)
    if data.cargo not in ('administrador','usuario'):
        raise HTTPException(400, 'Cargo inválido.')
    if not data.senha or len(data.senha) < 4:
        raise HTTPException(400, 'A senha deve possuir pelo menos 4 caracteres.')
    with conn() as db:
        if db.execute('SELECT 1 FROM usuarios WHERE lower(email)=?', (data.email.strip().lower(),)).fetchone():
            raise HTTPException(409, 'Já existe um usuário com este e-mail.')
        uid = secrets.token_hex(12)
        db.execute('INSERT INTO usuarios(id,nome,email,senha_hash,cargo,status,criado_em) VALUES(?,?,?,?,?,?,?)', (uid,data.nome.strip(),data.email.strip().lower(),hash_password(data.senha),data.cargo,data.status,now()))
        perms = default_permissions(data.cargo); perms.update({k: bool(v) for k,v in data.permissoes.items() if k in PERMISSION_KEYS})
        if data.cargo == 'administrador': perms = {k: True for k in PERMISSION_KEYS}
        db.execute('INSERT INTO permissoes(usuario_id,' + ','.join(PERMISSION_KEYS) + ') VALUES(?' + ',?'*len(PERMISSION_KEYS) + ')', (uid, *[int(perms[k]) for k in PERMISSION_KEYS]))
        for cid in data.cameras:
            if db.execute('SELECT 1 FROM cameras WHERE id=?', (cid,)).fetchone(): db.execute('INSERT OR IGNORE INTO usuario_cameras VALUES(?,?)',(uid,cid))
        activity(db, admin['id'], 'criação de usuário', f'Usuário {data.email.strip().lower()} criado')
        return user_dict(db.execute('SELECT * FROM usuarios WHERE id=?',(uid,)).fetchone(), db)


@app.put('/api/users/{uid}')
def update_user(uid: str, data: UserIn, authorization: str | None = Header(default=None)):
    admin = require_admin(authorization)
    with conn() as db:
        row = db.execute('SELECT * FROM usuarios WHERE id=?',(uid,)).fetchone()
        if not row: raise HTTPException(404, 'Usuário não encontrado.')
        if db.execute('SELECT 1 FROM usuarios WHERE lower(email)=? AND id<>?', (data.email.strip().lower(),uid)).fetchone(): raise HTTPException(409,'Já existe um usuário com este e-mail.')
        if row['id']==admin['id'] and data.status!='ativo': raise HTTPException(400,'Não é possível desativar a própria conta.')
        if row['cargo']=='administrador' and row['status']=='ativo' and (data.cargo!='administrador' or data.status!='ativo'):
            n=db.execute("SELECT COUNT(*) n FROM usuarios WHERE cargo='administrador' AND status='ativo'").fetchone()['n']
            if n<=1: raise HTTPException(400,'Não é possível remover o último administrador ativo.')
        db.execute('UPDATE usuarios SET nome=?,email=?,cargo=?,status=?' + (',senha_hash=?' if data.senha else '') + ' WHERE id=?', (data.nome.strip(),data.email.strip().lower(),data.cargo,data.status,*([hash_password(data.senha)] if data.senha else []),uid))
        perms=default_permissions(data.cargo); perms.update({k:bool(v) for k,v in data.permissoes.items() if k in PERMISSION_KEYS});
        if data.cargo=='administrador': perms={k:True for k in PERMISSION_KEYS}
        db.execute('UPDATE permissoes SET ' + ','.join(f'{k}=?' for k in PERMISSION_KEYS) + ' WHERE usuario_id=?', (*[int(perms[k]) for k in PERMISSION_KEYS],uid))
        db.execute('DELETE FROM usuario_cameras WHERE usuario_id=?',(uid,))
        for cid in data.cameras: db.execute('INSERT OR IGNORE INTO usuario_cameras VALUES(?,?)',(uid,cid))
        activity(db,admin['id'],'alteração de usuário',f'Usuário {data.email.strip().lower()} atualizado')
        return user_dict(db.execute('SELECT * FROM usuarios WHERE id=?',(uid,)).fetchone(),db)


@app.patch('/api/users/{uid}/status')
def toggle_user(uid: str, authorization: str | None = Header(default=None)):
    admin=require_admin(authorization)
    with conn() as db:
        row=db.execute('SELECT * FROM usuarios WHERE id=?',(uid,)).fetchone()
        if not row: raise HTTPException(404,'Usuário não encontrado.')
        if uid==admin['id']: raise HTTPException(400,'Não é possível bloquear a própria conta.')
        if row['cargo']=='administrador' and row['status']=='ativo' and db.execute("SELECT COUNT(*) n FROM usuarios WHERE cargo='administrador' AND status='ativo'").fetchone()['n']<=1: raise HTTPException(400,'Mantenha pelo menos um administrador ativo.')
        status='bloqueado' if row['status']=='ativo' else 'ativo'
        db.execute('UPDATE usuarios SET status=? WHERE id=?',(status,uid)); activity(db,admin['id'],'status de usuário',f'Conta {row["email"]}: {status}')
        return {'status':status}


@app.get('/api/ai/status')
def ai_status():
    try:
        detector = get_detector()
        return {
            'ready': True,
            'model': detector.model_path,
            'classes': detector.names,
            'confidence': AI_CONFIDENCE,
            'iou': AI_IOU,
        }
    except Exception as exc:
        return {'ready': False, 'model': MODEL_PATH, 'error': str(exc)}


@app.websocket('/ws/detection')
async def websocket_detection(websocket: WebSocket):
    await websocket.accept()
    try:
        detector = get_detector()
        await websocket.send_json({
            'type': 'ready',
            'model': Path(detector.model_path).name,
            'classes': detector.names,
        })
        while True:
            payload = await websocket.receive_json()
            image = payload.get('image', '')
            if not image:
                await websocket.send_json({'type': 'error', 'message': 'Frame sem imagem.'})
                continue
            try:
                encoded = image.split(',', 1)[1] if ',' in image else image
                raw = base64.b64decode(encoded)
                array = __import__('numpy').frombuffer(raw, dtype=__import__('numpy').uint8)
                frame = cv2.imdecode(array, cv2.IMREAD_COLOR)
                if frame is None:
                    raise ValueError('Não foi possível decodificar o frame JPEG.')
                detections = detector.infer(frame)
                risk = assess_risk(detections)
                generated_alerts = record_risk_alert(payload.get('camera_id'), risk)
                await websocket.send_json({
                    'type': 'result',
                    'camera_id': payload.get('camera_id'),
                    'detections': detections,
                    'risk': risk,
                    'alert': (generated_alerts[-1] if generated_alerts else None),
                })
            except Exception as exc:
                await websocket.send_json({'type': 'error', 'message': f'Erro na inferência: {exc}'})
    except WebSocketDisconnect:
        return
    except Exception as exc:
        try:
            await websocket.send_json({'type': 'error', 'message': str(exc)})
        except Exception:
            pass


@app.get('/api/cameras')
def cameras(authorization: str | None = Header(default=None)):
    session=require_permission(authorization, 'visualizar_cameras')
    with conn() as db:
        if session['cargo']=='administrador': rows=db.execute('SELECT * FROM cameras ORDER BY nome').fetchall()
        else: rows=db.execute('SELECT c.* FROM cameras c JOIN usuario_cameras uc ON uc.camera_id=c.id WHERE uc.usuario_id=? ORDER BY c.nome',(session['id'],)).fetchall()
        return [dict(r) for r in rows]


@app.post('/api/cameras')
def create_camera(data: CameraIn, authorization: str | None = Header(default=None)):
    admin=require_admin(authorization)
    cid=secrets.token_hex(12)
    with conn() as db:
        db.execute('INSERT INTO cameras(id,nome,tipo,device_id,endereco,localizacao,status,criado_em) VALUES(?,?,?,?,?,?,?,?)',(cid,data.nome.strip(),data.tipo,data.device_id,data.endereco,data.localizacao,data.status,now()))
        activity(db,admin['id'],'criação de câmera',f'Câmera {data.nome.strip()} cadastrada')
        return dict(db.execute('SELECT * FROM cameras WHERE id=?',(cid,)).fetchone())


@app.post('/api/cameras/test')
def test_camera(data: CameraTestIn, authorization: str | None = Header(default=None)):
    require_admin(authorization)
    if not (data.endereco.startswith('rtsp://') or data.endereco.startswith('http://') or data.endereco.startswith('https://')):
        raise HTTPException(400, 'O endereço deve iniciar com rtsp://, http:// ou https://.')
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(test_ip_stream, data.endereco)
        try:
            result = future.result(timeout=CAMERA_TEST_TIMEOUT)
        except FutureTimeoutError:
            raise HTTPException(504, f'Tempo limite de {int(CAMERA_TEST_TIMEOUT)}s excedido ao testar a câmera.')
        except Exception:
            result = None
    if not result:
        raise HTTPException(422, 'Não foi possível abrir o stream. Verifique endereço, credenciais, rede e se a câmera disponibiliza RTSP/HTTP.')
    return {'ok': True, 'width': result[0], 'height': result[1], 'message': 'Stream acessível.'}

@app.get('/api/cameras/{cid}/mjpeg')
def camera_mjpeg(cid: str, token: str):
    session = SESSIONS.get(token)
    if not session:
        raise HTTPException(401, 'Sessão inválida ou expirada.')
    with conn() as db:
        cam = db.execute('SELECT * FROM cameras WHERE id=?', (cid,)).fetchone()
        if not cam: raise HTTPException(404, 'Câmera não encontrada.')
        if session['cargo'] != 'administrador':
            allowed = db.execute('SELECT 1 FROM usuario_cameras WHERE usuario_id=? AND camera_id=?', (session['id'], cid)).fetchone()
            if not allowed: raise HTTPException(403, 'Você não possui acesso a esta câmera.')
        if cam['tipo'] not in ('ip','rtsp','wifi'): raise HTTPException(400, 'Esta câmera não é uma fonte IP.')
        url = cam['endereco']
    cap = open_ip_camera(url or '')
    if cap is None: raise HTTPException(422, 'Não foi possível abrir o stream da câmera.')
    def frames():
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    with conn() as db: db.execute("UPDATE cameras SET status='offline', ultima_verificacao=?, ultimo_erro=? WHERE id=?", (now(),'Stream interrompido',cid))
                    break
                with conn() as db: db.execute("UPDATE cameras SET status='online', ultima_verificacao=?, ultimo_online=?, ultimo_erro=NULL WHERE id=?", (now(),now(),cid))
                ok, encoded = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
                if not ok: continue
                yield b'--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ' + str(len(encoded)).encode() + b'\r\n\r\n' + encoded.tobytes() + b'\r\n'
        finally:
            cap.release()
    return StreamingResponse(frames(), media_type='multipart/x-mixed-replace; boundary=frame', headers={'Cache-Control':'no-store, no-cache, must-revalidate, max-age=0', 'Pragma':'no-cache'})

@app.delete('/api/cameras/{cid}')
def delete_camera(cid: str, authorization: str | None = Header(default=None)):
    admin=require_admin(authorization)
    with conn() as db:
        if not db.execute('SELECT 1 FROM cameras WHERE id=?',(cid,)).fetchone(): raise HTTPException(404,'Câmera não encontrada.')
        db.execute('DELETE FROM cameras WHERE id=?',(cid,)); activity(db,admin['id'],'remoção de câmera',f'Câmera {cid} removida')
    return {'ok':True}


@app.get('/api/alerts')
def alerts(authorization: str | None = Header(default=None), camera_id: str|None=None, level: str|None=None, status: str|None=None, date: str|None=None):
    session=require_permission(authorization, 'visualizar_alertas')
    q='SELECT a.* FROM alertas a'; params=[]
    if session['cargo']!='administrador': q+=' JOIN usuario_cameras uc ON uc.camera_id=a.camera_id WHERE uc.usuario_id=?'; params.append(session['id'])
    else: q+=' WHERE 1=1'
    for col,val in [('camera_id',camera_id),('nivel',level),('status',status)]:
        if val: q+=f' AND a.{col}=?'; params.append(val)
    if date: q+=' AND substr(a.data_hora,1,10)=?'; params.append(date)
    q+=' ORDER BY a.data_hora DESC'
    with conn() as db: return [dict(r) for r in db.execute(q,params).fetchall()]


@app.post('/api/alerts')
def create_alert(data: AlertIn, authorization: str|None=Header(default=None)):
    session=require_user(authorization)
    aid=secrets.token_hex(12)
    with conn() as db:
        db.execute('INSERT INTO alertas(id,camera_id,tipo,nivel,descricao,status,data_hora) VALUES(?,?,?,?,?,?,?)',(aid,data.camera_id,data.tipo,data.nivel,data.descricao,data.status,now()))
        activity(db,session['id'],'alerta',data.descricao)
    return {'id':aid}


@app.get('/api/monitor/usuarios')
def monitor_users(authorization: str|None=Header(default=None)):
    require_admin(authorization)
    with conn() as db:
        rows = db.execute('''SELECT u.id,u.nome,u.email,u.cargo,u.status,u.ultimo_login,u.ultimo_logout,u.tempo_total_ativo,
            CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END AS online,
            COALESCE(s.duracao_segundos,0) AS sessao_atual_segundos,
            s.ultimo_heartbeat FROM usuarios u LEFT JOIN sessoes s ON s.usuario_id=u.id AND s.status='online' ORDER BY u.nome''').fetchall()
        return [dict(r) for r in rows]

@app.get('/api/activities')
def activities(authorization: str|None=Header(default=None)):
    session=require_admin(authorization)
    with conn() as db: return [dict(r) for r in db.execute('SELECT * FROM atividades ORDER BY data_hora DESC').fetchall()]


@app.get('/api/dashboard')
def dashboard(authorization: str|None=Header(default=None)):
    session=require_user(authorization)
    with conn() as db:
        if session['cargo']=='administrador':
            cams=db.execute('SELECT * FROM cameras').fetchall(); alerts_n=db.execute('SELECT * FROM alertas ORDER BY data_hora DESC LIMIT 10').fetchall(); acts=db.execute('SELECT * FROM atividades ORDER BY data_hora DESC LIMIT 10').fetchall(); users=db.execute('SELECT * FROM usuarios').fetchall()
        else:
            cams=db.execute('SELECT c.* FROM cameras c JOIN usuario_cameras uc ON uc.camera_id=c.id WHERE uc.usuario_id=?',(session['id'],)).fetchall(); ids=[r['id'] for r in cams]; alerts_n=db.execute('SELECT * FROM alertas WHERE camera_id IN ('+','.join('?'*len(ids))+') ORDER BY data_hora DESC LIMIT 10',ids).fetchall() if ids else []; acts=[]; users=[]
        return {'cameras':[dict(r) for r in cams], 'alerts':[dict(r) for r in alerts_n], 'activities':[dict(r) for r in acts], 'users':[dict(r) for r in users]}


@app.get('/api/reports')
def reports(authorization: str|None=Header(default=None)):
    session=require_permission(authorization, 'visualizar_relatorios')
    with conn() as db:
        total_c=db.execute('SELECT COUNT(*) n FROM cameras').fetchone()['n']; active_c=db.execute("SELECT COUNT(*) n FROM cameras WHERE status='online'").fetchone()['n']; total_u=db.execute('SELECT COUNT(*) n FROM usuarios').fetchone()['n']; active_u=db.execute("SELECT COUNT(*) n FROM usuarios WHERE status='ativo'").fetchone()['n']; alerts_n=db.execute('SELECT COUNT(*) n FROM alertas').fetchone()['n']; open_n=db.execute("SELECT COUNT(*) n FROM alertas WHERE status='Aberto'").fetchone()['n']; total_seconds=db.execute('SELECT COALESCE(SUM(tempo_total_ativo),0) n FROM usuarios').fetchone()['n']; levels={l:db.execute('SELECT COUNT(*) n FROM alertas WHERE nivel=?',(l,)).fetchone()['n'] for l in ['Crítico','Alto','Normal']}
        return {'cameras':total_c,'active_cameras':active_c,'users':total_u,'active_users':active_u,'online_users':db.execute("SELECT COUNT(*) n FROM sessoes WHERE status='online'").fetchone()['n'], 'alerts':alerts_n,'open_alerts':open_n,'total_seconds':total_seconds,'alert_levels':levels}
