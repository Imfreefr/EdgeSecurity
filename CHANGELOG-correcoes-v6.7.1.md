# EdgeSecurity v6.7 — correções aplicadas

Baseado no briefing técnico enviado (`EdgeSecurity-briefing-correcoes.pdf`) + uma funcionalidade nova solicitada (exclusão de usuários).

## 1. [Crítico] Bug do "Tamanho da fonte" — corrigido (Opção A: rem + variável CSS)

- Todo `font-size` em `px` de `css/style.css`, `css/cameras.css`, `css/usuarios.css` e `css/atividades.css` foi convertido para `rem` (valor_px / 16), inclusive um caso que o PDF não citava: um `font-size` em `px` setado via JS inline (`js/atividades.js`, card de estatística), que também escapava da escala do body.
- `css/style.css` agora define `--font-scale` no `:root` e `html{font-size:calc(16px * var(--font-scale))}`; as classes `body.font-small/normal/large/xlarge` só alteram `--font-scale`.
- Resultado: trocar o tamanho da fonte em Configurações agora escala **todo** o texto do sistema (títulos, tabelas, botões, cards), não só o `<body>`.

## 2. [Alto] `api.js` ignorava `window.EDGE_API_BASE` — corrigido

- `js/api.js`: `API_BASE` agora é `(window.EDGE_API_BASE || 'http://127.0.0.1:8000') + '/api'`, respeitando o valor definido em `js/runtime-config.js`.

## 3. [Alto] Sessões sem expiração — corrigido

- Novo `SESSION_IDLE_TIMEOUT` (env var, padrão 8h): sessões em memória (`SESSIONS`) expiram após esse tempo sem nenhuma requisição autenticada, e o timer é renovado a cada request válida (inclui o heartbeat de 10s do frontend).
- Aplicado tanto em `require_user()` quanto no endpoint de streaming MJPEG (`/api/cameras/{id}/mjpeg`), que antes lia `SESSIONS` direto sem checar validade.

## 4. [Médio] `escapeHtml()` inconsistente — corrigido

- `js/usuarios.js`: `cargo`, `status` e `id` (usados em `onclick="...('${id}')"`) agora passam por `escapeHtml()`. Todos os outros arquivos já escapavam corretamente (conferido `cameras.js`, `dashboard.js`, `alertas.js`, `atividades.js`, `relatorios.js`).

## 5. [Médio] Rate limiting no login — adicionado

- Novo guard em memória: `LOGIN_MAX_ATTEMPTS` tentativas falhas por IP+usuário dentro de `LOGIN_WINDOW_SECONDS` (padrão 5/300s) bloqueiam novas tentativas com HTTP 429 e retorno de tempo de espera.

## 6. [Baixo/organização] Empacotamento

- `__pycache__/` e `edgesecurity.db` removidos do pacote de entrega.
- `.gitignore` criado (ignora `__pycache__`, `*.pyc`, `*.db`, `.env`, venvs, etc).
- `.env.example` expandido com `DB_PATH`, `SESSION_IDLE_TIMEOUT`, `LOGIN_MAX_ATTEMPTS`, `LOGIN_WINDOW_SECONDS` e comentários explicando `CORS_ORIGINS=*`.
- `README.md` atualizado com as novidades da v6.7.

## 7. [Opcional/qualidade] `require_permission` com f-string

- Comentário explicando por que o `key` interpolado é seguro (vem só de literais no código), validação extra (`if key not in PERMISSION_KEYS: raise 500`) para não regredir silenciosamente se algum dia alguém passar `key` errado.
- Comentário em `js/auth.js` documentando o trade-off consciente de guardar o token em local/sessionStorage.

## 8. [Novo — solicitado pelo usuário] Excluir usuário

- Novo endpoint `DELETE /api/users/{uid}`:
  - Qualquer administrador pode excluir contas comuns (`cargo='usuario'`).
  - **Excluir uma conta de administrador só é permitido ao administrador primário** — o usuário que criou a instalação via `/api/setup`. A checagem é feita relendo o campo `administrador_primario` do requisitante direto do banco (não confia só no token em memória).
  - Ninguém pode excluir a própria conta por esta rota.
  - Exclusão é permanente (cascata via `ON DELETE CASCADE` remove permissões, câmeras liberadas e sessões em SQLite); tokens ativos da conta excluída também são derrubados de `SESSIONS`.
  - Nova coluna `usuarios.administrador_primario` (migração automática: bancos antigos ganham a coluna e, se nenhum usuário estiver marcado, o administrador ativo mais antigo é promovido a primário automaticamente no próximo startup).
- Frontend (`pages/usuarios.html` + `js/usuarios.js`):
  - Novo botão "Excluir" na tabela de usuários, com confirmação (`confirm(...)`).
  - Botão só aparece quando a exclusão é permitida (não é a própria conta; e só é admin-primário pode excluir outro administrador) — a regra real continua sendo aplicada no backend, o frontend só evita mostrar um botão que sempre daria 403/400.
  - Coluna "Cargo" ganhou um selo "primário" ao lado do administrador que iniciou o sistema.

## Teste manual sugerido (conforme pedido no briefing)

1. Entrar em Configurações → trocar "Tamanho da fonte" entre as 4 opções → salvar → navegar por Dashboard, Câmeras, Usuários e conferir que títulos, tabelas, botões e cards mudam de tamanho junto.
2. Criar um segundo administrador; logar com ele e confirmar que **não** consegue excluir o administrador primário nem outro administrador (403), mas consegue excluir/bloquear/editar um usuário comum.
3. Logar como administrador primário e confirmar que ele consegue excluir tanto usuários comuns quanto outros administradores, mas não a própria conta.
4. Deixar uma sessão parada além do `SESSION_IDLE_TIMEOUT` (ou reduzir a env var para teste) e confirmar que a próxima chamada retorna 401.
5. Errar a senha de login 6x seguidas e confirmar o bloqueio (HTTP 429) por `LOGIN_WINDOW_SECONDS`.
