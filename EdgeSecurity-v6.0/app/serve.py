from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

if __name__ == "__main__":
    host, port = "127.0.0.1", 5500
    print(f"EdgeSecurity frontend: http://localhost:{port}")
    print("Mantenha esta janela aberta enquanto testar a câmera.")
    ThreadingHTTPServer((host, port), Handler).serve_forever()
