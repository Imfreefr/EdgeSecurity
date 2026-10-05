# EdgeSecurity — versão Vercel

Plataforma de monitoramento de segurança com cadastro de empresas, usuários e câmeras, detecção de pessoas e empilhadeiras e avaliação de risco de aproximação.

Este README descreve a branch **`v6.4.3-vercel`**. O nome da branch identifica esta linha de desenvolvimento; não representa uma garantia de que todos os recursos foram validados em produção.

## Arquitetura

| Componente | Implementação |
| --- | --- |
| Landing page | React, Vite, GSAP, Lenis e Three.js |
| Login e páginas internas | HTML, CSS e JavaScript |
| API | Python e FastAPI |
| Banco local | SQLite |
| Banco persistente | PostgreSQL, compatível com Supabase, via psycopg |
| IA no navegador | ONNX Runtime Web, WebAssembly e Web Worker |
| Modelo do navegador | `backend/model/edgev1-int8.onnx` |
| IA no servidor local | Ultralytics e modelo `backend/model/edgev1.pt` |
| Publicação | Frontend em `dist/` e entrada Python em `api/index.py` |

A autenticação é própria da aplicação. O uso de PostgreSQL no Supabase não implica uso de Supabase Auth ou Storage. O modelo ONNX é distribuído como arquivo estático.

## Recursos

- Cadastro de empresas e gerenciamento de assinaturas.
- Perfis de administrador da empresa, usuário e super administrador.
- Permissões e atribuição de câmeras a usuários.
- Cadastro de câmeras do navegador e fontes de rede.
- Detecção local, sobreposição dos resultados no vídeo e aviso sonoro de risco.
- Registro de alertas, atividades e consultas de relatórios.
- Separação de dados por empresa, com verificações de acesso na API.

A assinatura possui valor padrão de R$ 149,90, configurável por `SUBSCRIPTION_VALUE`. O código inclui integração com Mercado Pago e modo de pagamento simulado; a presença da integração não confirma sua configuração em produção.

## Requisitos para desenvolvimento

- Python 3.11 ou superior, compatível com as dependências de `backend/requirements.txt`.
- Node.js e npm para instalar e compilar a landing page.
- Navegador com acesso à câmera, Web Workers e WebAssembly.
- Webcam disponível e permissão de acesso para testar câmeras do dispositivo.
- PostgreSQL configurado quando for necessário persistir dados em produção.

A interface e a API são serviços separados no ambiente local. Apenas publicar arquivos estáticos em uma hospedagem PHP/MySQL não executa o backend deste projeto.

## Instalação local

Execute os comandos na raiz do repositório.

### 1. Preparar o Python

No Windows, usando o Prompt de Comando:

```cmd
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r backend\requirements.txt
python -m pip install python-dotenv
copy .env.example .env
```

No Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install python-dotenv
cp .env.example .env
```

O carregamento de `.env` na raiz depende de `python-dotenv`, que é opcional no código e não está explicitamente listado nas dependências do backend. Também é possível fornecer as variáveis diretamente no ambiente do processo.

Edite `.env` antes de iniciar. Defina suas próprias credenciais `SUPER_ADMIN_EMAIL` e `SUPER_ADMIN_PASSWORD` e uma chave aleatória forte para `AUTH_SECRET`. Substitua os valores de exemplo; não publique `.env`.

Para usar SQLite localmente, deixe `DATABASE_URL` e `SUPABASE_DB_URL` vazios. `DB_PATH` define o arquivo de banco.

### 2. Compilar a landing e copiar o modelo

```bash
npm ci
npm run build
```

O build gera `dist/`, preserva as páginas internas e copia o modelo para `dist/assets/edgev1-int8.onnx`, quando o arquivo de origem existe. Confirme a presença desse arquivo para testar a IA no navegador.

### 3. Iniciar a API

Em um terminal com o ambiente virtual ativado:

```bash
python backend/run.py
```

API: <http://127.0.0.1:8000>

Verificação de disponibilidade: <http://127.0.0.1:8000/api/health>

### 4. Iniciar a interface

Em outro terminal:

```bash
python serve.py
```

- Landing: <http://127.0.0.1:5500/landing.html>
- Login: <http://127.0.0.1:5500/index.html>

O servidor utiliza a landing compilada e os arquivos de origem das páginas internas. Refaça o build após alterar a landing.

Para editar a landing com recarga automática, use `npm run dev` e abra <http://127.0.0.1:5173/landing.html>. Esse comando não inicia a API. Para usar fluxos autenticados nessa origem, ajuste `CORS_ORIGINS` no backend.

## Contas e acesso

O super administrador gerencia a plataforma; ele não cadastra câmeras como administrador de uma empresa. Para testar monitoramento, utilize uma conta vinculada a uma empresa, com as permissões necessárias e uma assinatura ativa.

O cadastro público da empresa e o fluxo de pagamento estão separados do login. `PAYMENT_MOCK=true` habilita o modo simulado para desenvolvimento.

Na entrada Vercel, a ausência de configuração PostgreSQL ativa o fallback SQLite e pode criar uma empresa e uma conta de demonstração. Esse fluxo não é provisionamento de contas de produção e seus dados não têm persistência garantida.

## Como testar a câmera

1. Acesse pelo `localhost` ou por HTTPS e entre com uma conta da empresa.
2. Abra a página de câmeras e clique em **Detectar câmeras**.
3. Autorize o acesso no navegador.
4. Selecione a câmera e cadastre-a.
5. Ative a transmissão e clique em **Iniciar detecção**.

O cadastro armazena `device_id`, identificador fornecido pelo navegador. A listagem da API devolve esse campo para reconhecer a câmera antes da detecção. Esse identificador pode mudar entre navegadores, origens ou após redefinir permissões e dados do site.

A detecção verifica a câmera da transmissão ativa. A atualização da lista preserva a seleção quando o dispositivo continua disponível.

### Câmeras de rede

O backend local possui teste de conexão e transmissão MJPEG para fontes HTTP/RTSP, utilizando OpenCV. Ele precisa alcançar o endereço da câmera.

A página atual mantém a detecção desabilitada durante a visualização de uma fonte IP. O cadastro de uma fonte de rede não significa que sua análise por IA esteja integrada nessa tela.

## IA e limitações

A IA no navegador executa o modelo ONNX em um Worker com WebAssembly. Os quadros são enviados ao Worker local; os alertas gerados são enviados à API para registro.

- O processamento depende do dispositivo, do navegador e do carregamento do modelo e do runtime.
- O intervalo de envio tenta até aproximadamente 8 quadros por segundo; a taxa real não é garantida.
- O risco é estimado por proximidade na imagem, sem medição física calibrada.
- Desempenho com várias câmeras precisa ser medido no ambiente de uso.
- A tela atual trabalha com uma transmissão ativa por vez.
- A detecção automática auxilia o monitoramento e pode produzir erros de classificação.

Existe fallback para detecção no servidor via WebSocket no código. Para utilizá-lo, é necessário um backend com suporte a conexão persistente e às dependências reais de IA.

## Publicação na Vercel

A configuração do repositório utiliza:

- Build: `npm run build`.
- Diretório público: `dist`.
- API: `api/index.py`, acessível pelo caminho `/api`.
- Frontend e API na mesma origem, conforme `js/runtime-config.js`.

Configure as variáveis no ambiente do projeto antes de publicar:

| Variável | Uso |
| --- | --- |
| `DATABASE_URL` ou `SUPABASE_DB_URL` | Conexão PostgreSQL persistente |
| `PG_POOL_MIN`, `PG_POOL_MAX` | Limites do pool por instância; ajustar ao banco e à carga |
| `AUTH_SECRET` | Assinatura dos tokens; manter estável entre instâncias |
| `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_PASSWORD` | Provisionamento do super administrador |
| `COOKIE_SECURE=true` | Cookie restrito a HTTPS |
| `CORS_ORIGINS` | Origens explícitas permitidas pelo backend |
| `PAYMENT_MOCK` | Modo de pagamento simulado ou real |
| `MP_ACCESS_TOKEN`, `PAYMENT_WEBHOOK_SECRET`, `MP_BACK_URL` | Configuração do fluxo de pagamentos |
| `DATA_ENCRYPTION_KEY` | Chave Fernet para criptografia opcional de dados sensíveis |

Para PostgreSQL, prepare o banco com os scripts em `migrations/`, na ordem numérica, em um ambiente adequado. O isolamento atual também depende das verificações de empresa e permissões feitas pela API.

**SQLite em `/tmp/edgesecurity.db` é um fallback efêmero da entrada Vercel. Não use esse arquivo como banco persistente de produção.** Confirme que o backend está usando PostgreSQL e que o driver psycopg está disponível.

A entrada Vercel substitui OpenCV e Ultralytics por mocks e desabilita a IA do servidor. Por isso, o processamento de vídeo do servidor, o teste real de fontes IP/RTSP e o fallback de detecção por WebSocket não devem ser considerados funcionais nessa modalidade. A detecção prevista nessa versão ocorre no navegador.

## Estrutura principal

| Caminho | Conteúdo |
| --- | --- |
| `src/landing/` | Componentes e animações da landing |
| `pages/`, `css/`, `js/` | Interface interna e integrações |
| `backend/app.py` | Rotas, autenticação e regras da aplicação |
| `backend/database.py` | Acesso SQLite/PostgreSQL |
| `backend/services/` | Serviços de detecção, risco e pagamento |
| `backend/model/` | Modelos de IA |
| `api/index.py` | Entrada do backend na Vercel |
| `migrations/` | Scripts SQL para PostgreSQL |
| `tests/` | Testes e scripts de verificação |
| `.env.example` | Exemplo de configuração |
| `vite.config.js`, `vercel.json` | Build e publicação |

## Verificações

Na raiz do repositório:

```bash
python tests/test_camera_registration.py
node tests/camera-state.mjs
python tests/test_ws_authorization.py
```

Esses testes verificam identidade da câmera no cadastro/listagem, filtros por empresa e atribuição, preservação da seleção, vínculo com a transmissão ativa e autorização da detecção.

`npm test` executa o teste da landing com Playwright. Ele requer o servidor da interface em execução e um navegador compatível instalado. Consulte `tests/landing.mjs`: o script usa `EDGE_TEST_URL` (padrão `http://127.0.0.1:5174`) e `EDGE_BROWSER` (padrão `msedge`).

Testes automatizados não substituem a validação com câmera física, banco persistente e configuração real de publicação.

## Correções recentes do fluxo de câmeras

- Inclusão de `device_id` nas respostas de cadastro e listagem.
- Preservação do dispositivo selecionado após atualizar a lista.
- Associação da detecção ao dispositivo da transmissão ativa.
- Prevenção da reinicialização dos controles após recarregar os dados do cadastro.

Estas correções possuem testes de regressão no repositório. Elas não representam uma auditoria completa de segurança ou desempenho.
