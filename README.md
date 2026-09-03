# EdgeSecurity

Plataforma local de segurança na borda — operação 100% privada, sem nuvem. Gestão unificada de câmeras locais e de rede, teste de stream com timeout, conversão MJPEG no backend e detecção ao vivo de pessoas e máquinas (`edgev1.pt` + ByteTrack).

> **Tudo em português do Brasil, código formatado e legível.** Frontend com `Prettier`, backend com `Black` (PEP 8) e comentários em PT-BR.

---

## ✨ O que há nesta versão

Esta edição consolida todas as melhorias desde a v6.7.2 em um único pacote — sem `CHANGELOG` separado:

**Navegação e animações**
- Sidebar desktop fluida: `520 ms` abrindo / `480 ms` fechando (`cubic-bezier(.22,1,.36,1)`), labels com `translateX + blur` e stagger de `28 ms` por item. No mobile, colapsa para barra superior.
- Entrada de páginas com `pageEnter` / `riseIn` / `cardIn` / `statPop` e stagger por `nth-child` (`0.07 s` entre cards, `0.04–0.22 s` entre stats).
- Hover com `lift + sombra + glow` em cards e stats, e `translateX` suave em listas, linhas de dispositivo e linhas de tabela.

**Overdrive — todas as páginas e todos os botões funcionais**
- Botões (`.btn`, `.btn-primary/secondary/danger/small`): `shimmer` diagonal no hover, `background-position` com gradiente deslizante no primário, `scale(.97)` no active e `disabled` sem brilho.
- Cards: linha superior `accent` (gradiente lavanda-roxo) que expande ao passar o mouse, fundo radial sutil e `::after` de profundidade.
- Stats: brilho radial ao hover e `scale(1.02)` no valor.
- Tabelas: linha `thead` com sublinhado gradiente ao hover e `translateX(2–3 px)` nas linhas.
- Páginas específicas: `dashboard` (palco com brilho, ícone com scale), `câmeras` (palco com scan 2,8 s + scanlines radiais, `status-pill` pulsante, métricas IA com hover), `relatórios` (gráficos com entrada `odChartIn`), `alertas/atividades/usuários/configurações` com stagger próprio.
- `prefers-reduced-motion` desliga todas as animações.

**Encanto (delight) — toques sutis**
- Vazio de câmera com entrada `delightCamIn` e botão com `bob` suave.
- Linhas de dispositivo com rotação leve no hover e `scale` no active.
- Contadores de IA com `scale` no hover e `riskPulse` no nível crítico.

**Cor estratégica (colorize)**
- Stats tintados por semântica: 6 variações de `linear-gradient` no topo + `label` colorido (lavanda-roxo, ciano, verde, âmbar, slate, vermelho).
- `card` e `filter-card` com bordas suaves, `thead` com gradiente `#f8fafc`, `badges`/`levels` com bordas explícitas e `login-hero` com ícones tintados por posição.

**Clareza (clarify) — textos humanos**
- Hero do login: “Segurança local. Sem nuvem. Sob seu controle.” e benefícios sem jargão (`127.0.0.1`, `RTSP`, `YOLO` removidos do texto visível).
- Câmeras: header “Conecte webcams e câmeras de rede”, empty states unificados (“Nenhuma câmera encontrada. Conecte uma câmera e clique em Detectar câmeras.”), labels “Câmera de rede” e “Vídeo da câmera de rede”.
- Navegação unificada: `Dashboard` → **Visão geral**, `Sistema de Alertas` → **Alertas**, `Monitor de Atividades` → **Atividades**. Títulos de páginas (`<title>`) alinhados.
- Mensagens de erro, toasts e validações reescritas em PT-BR direto (ex.: `Sessão expirada. Entre novamente.`, `A câmera só funciona no endereço local ou com HTTPS.`).

**Polimento (polish) e qualidade**
- Contraste corrigido (`#94a3b8` → `#64748b/#475569`), tipografia mínima elevada (`.level/.badge .656` → `.687 rem`), sombra do login `48 px` → `28 px`, `filter-card` `16` → `20 px`, `toast` alinhado.
- `filter-card` no dark mode agora respeita `var(--card)` (não fica branco travado).
- `Impeccable detect` com config **0 findings** (sem config: 41 → 58 corrigidos conceitualmente); padrões intencionais documentados em `.impeccable/config.json` e com `impeccable-disable`.
- Palco `camera-stage-real` descolado da borda (`margin: 18px 20px 0`, mobile `14px 12px 0`) e `ai-warning` como caixa `#fef3c7` sem `side-tab` artificial.

**Formatação e legibilidade (PT-BR)**
- **Frontend:** `Prettier 3.9.6` em `css/**/*.css`, `js/**/*.js`, `index.html` e `pages/**/*.html` — indentação consistente, aspas e quebras padronizadas.
- **Backend:** `Black` em `backend/app.py`, `backend/run.py`, `serve.py`, `verificar_ambiente.py`, `backend/services/*.py`, `backend/tools/test_model.py` — PEP 8.
- Comentários traduzidos: `api.js`, `app.js`, `ai-api.js`, `camera-api.js`, `serve.py`, `backend/app.py` (sessões, rate-limit, permissões, heartbeat) e cabeçalhos de `css/*.css`.

---

## 🚀 Como iniciar

### Opção A — 1 clique (Windows)
```cmd
INICIAR_EDGESECURITY.bat
```
Cria `.venv`, instala `backend/requirements.txt` e abre backend `:8000` + frontend `:5500` automaticamente.

### Opção B — manual (raiz do projeto)
```cmd
py -m venv .venv
.\.venv\Scripts\activate
py -m pip install -r backend\requirements.txt

:: Terminal 1 — API
.\.venv\Scripts\python.exe backend\run.py
:: Terminal 2 — Frontend
.\.venv\Scripts\python.exe serve.py
```

Abra **http://127.0.0.1:5500** · API **http://127.0.0.1:8000** · `GET /api/ai/status` deve retornar `ready: true` quando `backend/model/edgev1.pt` estiver presente.

Copie `.env.example` para `.env` e ajuste `DB_PATH`, `SESSION_IDLE_TIMEOUT`, `LOGIN_MAX_ATTEMPTS` conforme o ambiente.

---

## 🧭 Mapa do sistema

| Rota | Título | Função principal |
| --- | --- | --- |
| `index.html` | Acesso Seguro | Login / criação do administrador inicial, badge `v6.7.2`, indicador `Sistema online/offline`, hero com 3 benefícios |
| `pages/dashboard.html` | Visão geral | 4 stats, palco da primeira câmera, `Alertas recentes` e `Atividade recente` |
| `pages/cameras.html` | Câmeras | Visualização ao vivo, Detectar/Cadastrar, Câmera de rede (IP/RTSP/HTTP), Detecção ao vivo com métricas Pessoas/Máquinas/Risco, listas de cadastradas e encontradas |
| `pages/alertas.html` | Alertas | Filtros (câmera, nível, status, data) + tabela paginada de alertas |
| `pages/atividades.html` | Atividades | Stats de usuários e sessões + tabelas de usuários e histórico |
| `pages/relatorios.html` | Relatórios | 8 stats, 2 gráficos (`Tempo de utilização`, `Alertas por nível`), filtros por período e botão `Exportar relatório` (JSON) |
| `pages/configuracoes.html` | Configurações | Conta (nome/e-mail), Aparência (tema claro/escuro, tamanho da fonte), Sistema (intervalo de atualização, notificações) |
| `pages/usuarios.html` | Usuários e Permissões | Stats, tabela com cargo/status/permissões/último acesso, modal Criar/Editar com permissões e câmeras permitidas |

Sidebar: navegação `Visão geral · Câmeras · Alertas · Relatórios · Atividades · Configurações` (+ `Usuários e Permissões` para administrador), modo `hover + focus-within` e `heartbeat` de sessão a cada `10 s`.

---

## 🎥 Câmeras

- **Local (navegador):** `Detectar câmeras` → autoriza no cadeado → `Ativar` / `Cadastrar câmera selecionada`. Requer contexto seguro (localhost ou HTTPS).
- **Rede (IP/Wi-Fi):** `Câmera de rede` com `Nome`, `Endereço do vídeo` (`rtsp://`, `http://`, `https://`) e `Localização` → `Testar conexão` (timeout configurável `CAMERA_TEST_TIMEOUT`, padrão `8 s`) → `Cadastrar câmera de rede`.
- **Palco:** `camera-stage-real` (`420 px`, `18 px` de respiro do `card-head`), overlay `ai-overlay` para caixas de detecção e scanline técnica.
- **Erros legíveis:** cada `MediaDevices` error (`NotAllowed`, `NotFound`, `NotReadable`, `SecurityError`, etc.) tem mensagem em PT-BR com ação.

## 🤖 Inteligência Artificial

- Backend: `backend/model/edgev1.pt` (YOLO + ByteTrack + `services/risk_engine.py`). Sem detecções fictícias.
- Frontend: `js/ai-api.js` (WebSocket `ws://127.0.0.1:8000/ws/detection`, `sendFrame` a `8 fps`, `quality 0.62`) + `js/cameras.js` (`drawResults`, `riskLevel` com `Seguro / Atenção / Alto / CRÍTICO`).
- Aviso honesto no card: “O nível de risco é estimado pela distância na imagem. Para uso real é preciso calibrar com medidas físicas.”
- Teste local: `python backend/tools/test_model.py` (requer `edgev1.pt`).

## 👥 Usuários e permissões

- Cargos: `administrador` (tudo) e `usuário` (permissões granulares: `visualizar_cameras`, `usar_camera_dispositivo`, `gerenciar_cameras`, `visualizar_alertas`, `visualizar_relatorios`, `gerenciar_usuarios`, `gerenciar_permissoes`, `acessar_configuracoes`).
- Regra de **administrador primário**: apenas quem criou a instalação via `/api/setup` pode excluir outros administradores; ninguém exclui a si mesmo; último admin ativo não pode ser removido.
- Sessões: token Bearer em `localStorage/sessionStorage`, `SESSION_IDLE_TIMEOUT` (padrão `8 h`), `get_session_for_token` renova `last_seen`, heartbeat a cada `10 s` (flush incremental sem double-count) e limpeza em memória ao reiniciar o backend.

---

## 🎨 Design

- **Tokens:** `--navy-900/800/700`, `--blue #2f6fed`, `--cyan #22d3ee`, `--green/#red/#amber`, `--radius 14 px`, sombras `--shadow-sm/md/lg`.
- **Overdrive / Delight / Colorize:** sistema de movimento global (`--od-ease`, `--od-ease2`) com `will-change`, `stagger` e `prefers-reduced-motion: reduce` em tudo. Tabelas, filtros e modais com foco visível (`box-shadow 0 0 0 3px rgba(47,111,237,.14)`).
- **Acessibilidade:** `html.font-*` (`small/normal/large/xlarge`) escala todo o sistema via `html{font-size: calc(16px * var(--font-scale))}`, contraste AA, `min-height: 44 px` nos controles, `::selection` temático e `scrollbar` estilizada.
- **Dark mode:** completo, sem “ilhas brancas” em modais, `filter-card`, inputs e `card-head`.

## 🧹 Qualidade

- **Impeccable:** `npx impeccable detect` → `0` com config (`.impeccable/config.json` documenta padrões intencionais: `overused-font Inter`, `codex-grid-background`, `dark-glow`, `pulsing-dot`, `layout-transition`). Sem config: `41–58` achados remanescentes são falsos positivos de textura técnica.
- **Clareza:** todos os textos visíveis em PT-BR, sem hedging (“caso exista”) e sem vazamento técnico na UI.
- **Formatação:** ver seção seguinte.

---

## 🛠️ Tecnologias

- **Frontend:** HTML5, CSS3 (tokens + grid + container queries leves), JavaScript vanilla (`js/app.js`, `api.js`, `auth.js`, `camera-api.js`, `ai-api.js`, `cameras.js`, `dashboard.js`, `alertas.js`, `atividades.js`, `relatorios.js`, `configuracoes.js`, `usuarios.js`), `Boxicons`, `Inter` + `JetBrains Mono`.
- **Backend:** Python 3.12, FastAPI, Uvicorn, SQLite (`edgesecurity.db`), `cv2` + `ultralytics YOLO`, `pydantic`, `ThreadPoolExecutor` para teste de stream.
- **Ferramentas:** `Prettier 3.9.6` (frontend), `Black` (Python), `Impeccable 3.5.0` (qualidade), `serve.py` (frontend em `127.0.0.1:5500`).

## 📁 Estrutura

```
EdgeSecurity/
├── index.html                 # Login + hero
├── pages/                     # Visão geral, Câmeras, Alertas, Atividades, Relatórios, Configurações, Usuários
├── css/                       # style.css (sistema) + cameras.css, alertas.css, atividades.css, ...
├── js/                        # app.js, api.js, auth.js, cameras.js, ai-api.js, ...
├── backend/
│   ├── app.py                 # FastAPI (743+ linhas, PT-BR)
│   ├── run.py                 # Uvicorn
│   ├── services/detector.py   # YOLO
│   ├── services/risk_engine.py
│   └── model/edgev1.pt        # (colocar aqui)
├── serve.py                   # Servidor frontend local
├── verificar_ambiente.py      # Checagem de FastAPI/Uvicorn
├── INICIAR_EDGESECURITY.bat   # Atalho Windows
└── .impeccable/config.json    # Regras de qualidade
```

---

## ⚙️ Configuração

Variáveis (via `.env` ou ambiente), com padrões em `backend/app.py`:

| Variável | Padrão | Uso |
| --- | --- | --- |
| `DB_PATH` | `backend/edgesecurity.db` | Caminho do SQLite |
| `SESSION_IDLE_TIMEOUT` | `28800` (8 h) | Expiração por ociosidade |
| `CAMERA_TEST_TIMEOUT` | `8` | Timeout do teste IP |
| `CAMERA_IDLE_TIMEOUT` | `35` | Ociosidade de câmera |
| `LOGIN_MAX_ATTEMPTS` | `5` | Tentativas antes de bloquear |
| `LOGIN_WINDOW_SECONDS` | `300` | Janela do rate-limit |
| `MODEL_PATH` | `backend/model/edgev1.pt` | Modelo YOLO |
| `AI_CONFIDENCE` / `AI_IOU` | `0.40` / `0.50` | Limiares de detecção |
| `EDGE_HOST` / `EDGE_PORT` | `127.0.0.1` / `5500` | Frontend |
| `EDGE_API_HOST` / `EDGE_API_PORT` | `127.0.0.1` / `8000` | Backend |

## 🧪 Verificação

```cmd
.\.venv\Scripts\python.exe verificar_ambiente.py
:: ou
npx impeccable detect
npx prettier --check "css/**/*.css" "js/**/*.js" "index.html" "pages/**/*.html"
.\.venv\Scripts\python.exe -m black --check backend\app.py serve.py
```

## 📜 Versionamento

Histórico preservado em tags `v1.0` … `v6.7.2` e branch `backup/pre-reestruturacao` (`git tag -l`). O `CHANGELOG-v6.7.2.md` anterior foi consolidado neste `README` — a partir desta versão, o `README` é a fonte única de documentação.

---

**EdgeSecurity © 2026** · Privado por padrão · `prefers-reduced-motion` respeitado.
