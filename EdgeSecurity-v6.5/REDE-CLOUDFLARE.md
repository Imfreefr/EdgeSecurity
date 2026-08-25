# EdgeSecurity v6.4 — acesso externo com Cloudflare Tunnel

Esta versão foi ajustada para que o navegador não dependa de `localhost:8000` quando o sistema é acessado de outro dispositivo ou por um hostname público.

## 1. Como a rede funciona

Localmente:

- Frontend: `http://localhost:5500`
- API: `http://localhost:8000`

Na rede local, por exemplo:

- Frontend: `http://IP-DO-PC:5500`
- API: `http://IP-DO-PC:8000`

No Cloudflare Tunnel, o navegador usa um único hostname:

- Frontend: `https://app.seudominio.com/`
- API: `https://app.seudominio.com/api/...`
- WebSocket: `wss://app.seudominio.com/ws/detection`

O JavaScript detecta automaticamente esse cenário. Não é necessário trocar `localhost` manualmente no tablet.

## 2. Iniciar o EdgeSecurity

Terminal 1:

```cmd
cd "C:\caminho\para\EdgeSecurity-v6.4\app\backend"
py -m pip install -r requirements.txt
py -m uvicorn app:app --host 0.0.0.0 --port 8000
```

Terminal 2:

```cmd
cd "C:\caminho\para\EdgeSecurity-v6.4\app"
py serve.py
```

O frontend agora escuta em `0.0.0.0:5500`, permitindo acesso pela LAN e pelo `cloudflared`.

## 3. Testar antes do Tunnel

No próprio PC:

- `http://localhost:5500`
- `http://localhost:8000/docs`

Pela LAN, usando o IPv4 do PC:

- `http://IP-DO-PC:5500`
- `http://IP-DO-PC:8000/docs`

No tablet, conectado à mesma rede:

- `http://IP-DO-PC:5500`

## 4. Cloudflare Tunnel recomendado

Para o TCC, prefira um **Named Tunnel** com domínio/hostname próprio. O Cloudflare permite publicar múltiplas aplicações em um mesmo Tunnel e direcionar cada rota para um serviço local. Consulte a documentação oficial de routing do Tunnel.

O arquivo `cloudflared/config.yml.example` desta versão mostra a configuração para usar **um único hostname** com roteamento por caminho:

- `/api/*` → FastAPI :8000
- `/ws/*` → FastAPI :8000
- `/docs`, `/redoc`, `/openapi.json` → FastAPI :8000
- qualquer outra rota → frontend :5500

Isso é importante porque o frontend usa URLs relativas para API/WebSocket quando está em um hostname público. O tablet não precisa conhecer a porta 8000.

## 5. Configuração do Tunnel

Depois de criar o Tunnel no painel Cloudflare, substitua no `config.yml`:

- `SEU-TUNNEL-UUID`
- caminho de `credentials-file`
- `app.seudominio.com`

Valide:

```cmd
cloudflared tunnel ingress validate
```

Teste a regra:

```cmd
cloudflared tunnel ingress rule https://app.seudominio.com/
```

Execute:

```cmd
cloudflared tunnel --config config.yml run NOME-DO-TUNNEL
```

O tablet então acessa apenas:

```text
https://app.seudominio.com
```

## 6. WebSocket / YOLO26

O cliente de IA desta versão também foi ajustado para usar automaticamente `wss://SEU-HOSTNAME/ws/detection` quando o EdgeSecurity está em HTTPS.

Cloudflare Tunnel suporta WebSockets. Portanto, o caminho já está preparado para a etapa de integração ao YOLO26.

## 7. Câmera do tablet

Ao acessar o EdgeSecurity por HTTPS, o navegador pode usar a câmera do próprio tablet, desde que o usuário conceda a permissão.

Isso é uma melhoria importante em relação ao acesso por HTTP usando um IP local: para câmera do navegador, HTTPS é o caminho recomendado.

## 8. Câmera IP/Wi-Fi

A câmera IP não precisa ser pública na Internet.

Ela deve continuar acessível pelo computador que executa o FastAPI:

```text
Câmera IP → rede local → PC → FastAPI/OpenCV → EdgeSecurity
```

O tablet recebe apenas a interface/stream disponibilizados pelo EdgeSecurity.

## 9. Segurança para o TCC

Não publique credenciais RTSP no HTML ou JavaScript.

Se o hostname ficar acessível publicamente, considere colocar Cloudflare Access na frente da aplicação ou manter a autenticação própria do EdgeSecurity. O Tunnel publica o serviço na Internet; a autenticação da aplicação continua sendo responsabilidade do projeto, a menos que você adicione uma camada de Access.
