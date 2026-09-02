from __future__ import annotations

import os
import socket
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)


def local_ip() -> str:
    """Best-effort LAN address for display only; it does not change the bind address."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(('1.1.1.1', 80))
            return sock.getsockname()[0]
    except OSError:
        return 'seu-IP-local'


if __name__ == '__main__':
    host = os.getenv('EDGE_HOST', '127.0.0.1')
    port = int(os.getenv('EDGE_PORT', '5500'))
    ip = local_ip()

    print('EdgeSecurity frontend iniciado.')
    print(f'Local:       http://localhost:{port}')
    print('Acesso LAN:   desativado (modo somente local).')
    print('Mantenha esta janela aberta enquanto o sistema estiver em uso.')

    ThreadingHTTPServer((host, port), Handler).serve_forever()
