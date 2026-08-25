# EdgeSecurity v6.4 — reparo de rede

Esta versão mantém o sistema e corrige a forma como frontend, FastAPI e WebSocket descobrem o endereço do backend.

### O problema anterior

O frontend tinha `http://localhost:8000/api` fixo. Em um tablet, `localhost` aponta para o próprio tablet.

### Solução

- Em `localhost:5500`, o frontend continua usando `http://localhost:8000/api`.
- Em `IP-DO-PC:5500`, usa automaticamente `http://IP-DO-PC:8000/api`.
- Em um hostname HTTPS, como um Cloudflare Tunnel, usa `/api` no mesmo hostname.
- O WebSocket YOLO26 segue a mesma lógica e usa `wss://hostname/ws/detection` no acesso HTTPS.
- `serve.py` e FastAPI agora escutam em `0.0.0.0` por padrão.

### Arquivo importante

Veja `REDE-CLOUDFLARE.md` na raiz do pacote e `cloudflared/config.yml.example` para a configuração do Tunnel.
