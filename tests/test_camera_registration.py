"""Exercise camera endpoints with real SQL, including tenant/assignment filters."""
import ast
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

source = ast.parse(Path('backend/app.py').read_text(encoding='utf-8-sig'))
functions = [n for n in source.body if isinstance(n, ast.FunctionDef) and n.name in ('cameras', 'create_camera')]
for function in functions:
    function.decorator_list = []
db = sqlite3.connect(':memory:')
db.row_factory = sqlite3.Row
db.executescript('''
CREATE TABLE cameras(id TEXT, nome TEXT, tipo TEXT, device_id TEXT, endereco TEXT,
localizacao TEXT, status TEXT, criado_em TEXT, company_id TEXT);
CREATE TABLE usuario_cameras(usuario_id TEXT, camera_id TEXT);
''')
@contextmanager
def connection():
    yield db
    db.commit()
session = {'id': 'user-a', 'company_id': 'company-a', 'cargo': 'administrador'}
namespace = dict(Request=object, CameraIn=object, Header=lambda **kw: None,
    require_permission=lambda *args: session, require_admin=lambda *args: session,
    conn=connection, secrets=SimpleNamespace(token_hex=lambda size: 'camera-a'),
    now=lambda: '2026-10-05', activity=lambda *args: None)
exec(compile(ast.Module(body=functions, type_ignores=[]), '<camera-endpoints>', 'exec'), namespace)
data = SimpleNamespace(nome='Webcam', tipo='browser', device_id='device-a',
    endereco=None, localizacao=None, status='ativo')
created = namespace['create_camera'](data, None)
assert created['device_id'] == 'device-a'
db.execute("INSERT INTO cameras VALUES('camera-b','Other','browser','device-b',NULL,NULL,'ativo','today','company-b')")
rows = namespace['cameras'](None)
assert [r['id'] for r in rows] == ['camera-a']
assert rows[0]['device_id'] == data.device_id
session['cargo'] = 'usuario'
assert namespace['cameras'](None) == []
db.execute("INSERT INTO usuario_cameras VALUES('user-a','camera-a')")
assert namespace['cameras'](None)[0]['device_id'] == 'device-a'
session['cargo'] = 'super_admin'
assert len(namespace['cameras'](None)) == 2
print('PASS camera create/list identity, tenant isolation, assignments, super admin')
