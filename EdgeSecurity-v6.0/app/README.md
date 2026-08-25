# EdgeSecurity v6 — SQLite + FastAPI

Versão demonstrativa do TCC. O sistema não cria usuários, câmeras, alertas ou relatórios fictícios.

## Estrutura
- `index.html` — autenticação/configuração inicial
- `pages/` — módulos do sistema
- `css/` — estilos
- `js/api.js` — comunicação com FastAPI
- `backend/app.py` — API e SQLite
- `backend/edgesecurity.db` — criado automaticamente na primeira execução

## Executar
1. Instale Python 3.11+.
2. Abra um terminal na pasta `backend`.
3. Instale dependências: `python -m pip install -r requirements.txt`.
4. Execute: `python -m uvicorn app:app --host 127.0.0.1 --port 8000`.
5. Em outro terminal, na raiz do projeto, execute: `python serve.py`.
6. Abra `http://localhost:5500`.

Também é possível usar `iniciar-edge-security.bat` no Windows.

## Primeiro acesso
O banco começa vazio. A tela inicial consulta a API. Se não existir usuário, você cria o primeiro administrador. Depois ele poderá cadastrar usuários, permissões e câmeras.

## Segurança da demonstração
As senhas não ficam em texto puro no SQLite; o backend usa PBKDF2-HMAC-SHA256 com salt por senha. As sessões usam tokens temporários em memória. Para produção, essa autenticação deverá ser substituída por uma solução de sessão/JWT persistente e HTTPS.

## YOLO26
O endpoint de análise por WebSocket poderá ser integrado depois. O banco já possui a tabela de alertas para receber eventos reais da IA.
