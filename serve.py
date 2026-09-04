from __future__ import annotations

import os
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


BLOCKED_SUFFIXES = (".db", ".sqlite", ".sqlite3", ".env", ".pem", ".key")
BLOCKED_PARTS = (".git", ".venv", "venv", "__pycache__", ".impeccable")

class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if any(self.path.endswith(s) or s in self.path for s in BLOCKED_SUFFIXES):
            self.send_error(404)
            return
        if any(p in self.path.split("/") for p in BLOCKED_PARTS):
            self.send_error(404)
            return
        return super().do_GET()

    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.send_header("Content-Security-Policy", "default-src 'self' https://unpkg.com https://fonts.googleapis.com; style-src 'self' https://fonts.googleapis.com https://unpkg.com; font-src https://fonts.gstatic.com https://unpkg.com; img-src 'self' data: blob:; connect-src 'self' http://127.0.0.1:8000 http://localhost:8000")
        super().end_headers()


def local_ip() -> str:
    """Endereço LAN de melhor esforço apenas para exibição; não altera o endereço de vínculo."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("1.1.1.1", 80))
            return sock.getsockname()[0]
    except OSError:
        return "seu-IP-local"


if __name__ == "__main__":
    host = os.getenv("EDGE_HOST", "127.0.0.1")
    port = int(os.getenv("EDGE_PORT", "5500"))
    ip = local_ip()

    print("EdgeSecurity frontend iniciado.")
    print(f"Local:       http://localhost:{port}")
    print("Acesso LAN:   desativado (modo somente local).")
    print("Mantenha esta janela aberta enquanto o sistema estiver em uso.")

    ThreadingHTTPServer((host, port), Handler).serve_forever()
