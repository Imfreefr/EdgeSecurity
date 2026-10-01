import ast, asyncio
from pathlib import Path
from types import SimpleNamespace

source = Path("backend/app.py").read_text(encoding="utf-8-sig")
tree = ast.parse(source)
endpoint = next(n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "websocket_detection")
endpoint.decorator_list = []
class HTTPException(Exception):
    def __init__(self, *args): super().__init__(*args)
class WebSocketDisconnect(Exception): pass
class DB:
    def __init__(self, company): self.company = company
    def __enter__(self): return self
    def __exit__(self,*args): pass
    def execute(self, sql, params):
        row = {"status":"ativo"} if "SELECT status" in sql else {"company_id":self.company}
        return SimpleNamespace(fetchone=lambda:row)
class Socket:
    headers = {"origin":"https://example.test"}
    def __init__(self, messages): self.messages=iter(messages); self.closed=None; self.sent=[]
    async def accept(self): pass
    async def close(self,code): self.closed=code
    async def receive_json(self):
        try: return next(self.messages)
        except StopIteration: raise WebSocketDisconnect()
    async def send_json(self,data): self.sent.append(data)
async def check():
    for name, token, company, expected in [
        ("missing-auth",None,"a",1008),
        ("invalid-token","invalid","a",1008),
        ("foreign-camera","valid","b",1008),
        ("own-camera","valid","a",None),
    ]:
        def permission(auth,key):
            if auth != "Bearer valid": raise HTTPException()
            return {"id":"u","company_id":"a","cargo":"administrador"}
        namespace = dict(asyncio=asyncio,WebSocket=Socket,HTTPException=HTTPException,
            WebSocketDisconnect=WebSocketDisconnect,CORS_ORIGINS=["https://example.test"],
            require_permission=permission,conn=lambda:DB(company),Path=Path,
            get_detector=lambda:SimpleNamespace(model_path="model.onnx",names={0:"human"}))
        exec(compile(ast.Module(body=[endpoint],type_ignores=[]),"<endpoint>","exec"),namespace)
        socket=Socket([{"type":"auth","token":token,"camera_id":"cam"}])
        await namespace["websocket_detection"](socket)
        assert socket.closed == expected,(name,socket.closed)
        if expected is None: assert socket.sent[0]["type"] == "ready"
        print("PASS",name)
asyncio.run(check())
