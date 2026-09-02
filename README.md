# EdgeSecurity v6.7.2

Plataforma local de segurança na borda — operação privada em `127.0.0.1`, sem dependência de cloud. Gestão unificada de câmeras locais + RTSP/HTTP, teste de stream com timeout, conversão MJPEG no backend e detecção YOLO `edgev1.pt` com ByteTrack.

## Inicialização

**Opção A — 1 clique (Windows):**
```cmd
INICIAR_EDGESECURITY.bat
```
Cria `.venv`, instala `backend/requirements.txt` e abre backend `:8000` + frontend `:5500`.

**Opção B — manual (raiz do projeto):**
```cmd
py -m venv .venv
.venv\Scripts\activate
py -m pip install -r backend\requirements.txt

:: Terminal 1
.\.venv\Scripts\python.exe backend\run.py

:: Terminal 2
.\.venv\Scripts\python.exe serve.py
```
Abra `http://127.0.0.1:5500` · API `http://127.0.0.1:8000` · `GET /api/ai/status` deve retornar `ready: true` quando `backend/model/edgev1.pt` estiver presente.

Copie `.env.example` para `.env` e ajuste `DB_PATH`, `SESSION_IDLE_TIMEOUT`, `LOGIN_MAX_ATTEMPTS` conforme o ambiente.

## O que há nesta versão

- **Login premium v6.7.2:** split hero (storytelling + benefícios) + card branco com badge `v6.7.2`, gradientes radiais navy, micro-animação `heroPulse` e foco acessível.
- **Fonte corrigida:** `Configurações → Aparência → Tamanho da fonte` agora escala **todo** o sistema (`html{font-size:calc(16px*var(--font-scale))}` + classes `html.font-*`, não mais `body`).
- FastAPI + SQLite, autenticação com hash, permissões no backend.
- Sessões com heartbeat a cada 10s, expiração `SESSION_IDLE_TIMEOUT` (padrão 8h), proteção brute-force `LOGIN_MAX_ATTEMPTS`.
- Monitor online/offline, CRUD completo de usuários com regra de admin primário.
- Câmeras locais + IP/RTSP/HTTP, teste com timeout, stream convertido para MJPEG.
- Sidebar hover + `focus-within` (teclado descobre labels), hierarquia tipográfica reforçada, `min-height:44px` nos controles.
- Dark mode completo, `::selection` temático, `prefers-reduced-motion` respeitado.

## Câmera IP

`rtsp://192.168.1.100:554/stream` — o host do backend precisa alcançar a câmera na rede local.

## IA

`backend/model/edgev1.pt` carregado pelo backend (YOLO + ByteTrack + `risk_engine`). Sem detecções fictícias — o protótipo usa distância em pixels e exige calibração física para uso industrial.

## Histórico

- `CHANGELOG-v6.7.2.md` — login premium + fonte + otimizações audit/critique
- `CHANGELOG-correcoes-v6.7.1.md` — correções do briefing técnico
- Tags `v6.7.2`, `v6.7.1` ... `v1.0` e branch `backup/pre-reestruturacao` preservam versões antigas (ver `git tag -l`).
