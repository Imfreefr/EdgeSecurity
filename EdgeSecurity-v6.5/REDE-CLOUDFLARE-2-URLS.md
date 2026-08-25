# EdgeSecurity v6.4 — dois Cloudflare Quick Tunnels

Esta versão foi preparada para o cenário em que o Cloudflare cria **duas URLs aleatórias**, uma para o frontend e outra para o backend.

Exemplo fictício:

- Frontend: `https://abc-def-123.trycloudflare.com`
- Backend: `https://xyz-456.trycloudflare.com`

O tablet acessa **somente a URL do frontend**. O JavaScript do frontend chama a URL do backend configurada em `app/js/runtime-config.js`.

## 1. Inicie o FastAPI

Terminal 1:

```cmd
cd "C:\caminho\para\EdgeSecurity-v6.4\app\backend"
py -m pip install -r requirements.txt
py -m uvicorn app:app --host 0.0.0.0 --port 8000
```

## 2. Inicie o frontend

Terminal 2:

```cmd
cd "C:\caminho\para\EdgeSecurity-v6.4\app"
py serve.py
```

## 3. Crie o tunnel do backend

Terminal 3:

```cmd
cloudflared tunnel --url http://localhost:8000
```

O terminal mostrará uma URL parecida com:

```text
https://alguma-coisa.trycloudflare.com
```

Copie essa URL.

## 4. Configure a URL do backend no frontend

Abra:

```text
app/js/runtime-config.js
```

Altere:

```javascript
window.EDGE_API_BASE = '';
```

para:

```javascript
window.EDGE_API_BASE = 'https://ALGUMA-COISA.trycloudflare.com';
```

Não coloque `/api` no final. O sistema acrescentará `/api` automaticamente.

## 5. Crie o tunnel do frontend

Terminal 4:

```cmd
cloudflared tunnel --url http://localhost:5500
```

O Cloudflare fornecerá outra URL aleatória, por exemplo:

```text
https://outra-coisa.trycloudflare.com
```

Essa é a URL que você abrirá no tablet.

## 6. Teste no tablet

Abra somente a URL do frontend:

```text
https://outra-coisa.trycloudflare.com
```

O navegador carregará o frontend por essa URL e fará as requisições da API para:

```text
https://ALGUMA-COISA.trycloudflare.com/api/...
```

## 7. CORS

Como a URL do frontend é aleatória e pode mudar a cada execução do Quick Tunnel, o backend desta versão aceita `CORS_ORIGINS=*` quando essa variável é configurada.

Para o TCC/demo, execute o FastAPI assim:

```cmd
set CORS_ORIGINS=*
py -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Em PowerShell:

```powershell
$env:CORS_ORIGINS="*"
py -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Isso evita que uma nova URL `trycloudflare.com` quebre o acesso por CORS.

## 8. WebSocket / YOLO26

`app/js/ai-api.js` também utiliza `EDGE_API_BASE`. Quando o backend estiver em HTTPS, ele converte automaticamente o endereço para `wss://.../ws/detection`.

Portanto, quando a integração do YOLO26 for feita, o tablet poderá receber a comunicação em tempo real pelo backend tunnel.

## 9. Importante sobre Quick Tunnel

Quick Tunnels são destinados a testes/desenvolvimento e geram subdomínios aleatórios `trycloudflare.com`. A URL muda quando o processo do tunnel é encerrado/recriado. Para o TCC, isso é aceitável como demonstração; para uma publicação estável, use um Named Tunnel.

Além disso, se houver um `config.yaml` no diretório `.cloudflared`, o Quick Tunnel pode não iniciar. Renomeie temporariamente esse arquivo se necessário.
