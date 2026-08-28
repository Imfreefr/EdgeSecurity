# EdgeSecurity v6.7

Versão demonstrativa para TCC, sem arquivos `.bat`.

## Inicialização

Terminal 1:
```cmd
cd backend
py -m pip install -r requirements.txt
py run.py
```

Terminal 2:
```cmd
py serve.py
```

Abra `http://127.0.0.1:5500`.

Copie `.env.example` para `.env` (ou exporte as mesmas variáveis) e ajuste conforme o ambiente antes de subir o backend — veja os comentários no próprio arquivo.

## O que há nesta versão

- FastAPI + SQLite.
- Autenticação e hash de senha.
- Permissões verificadas no backend.
- Sessões persistidas em SQLite, com heartbeat e tempo acumulado, e expiração automática por inatividade em memória (`SESSION_IDLE_TIMEOUT`).
- Proteção básica contra força bruta no login (`LOGIN_MAX_ATTEMPTS` / `LOGIN_WINDOW_SECONDS`).
- Monitor de usuários online/offline.
- Gerenciamento completo de usuários: criar, editar, bloquear/ativar e **excluir** permanentemente. Excluir uma conta de administrador só é permitido ao administrador primário (o que criou a instalação via `/api/setup`); ninguém pode excluir a própria conta.
- Tamanho da fonte (Configurações) escala proporcionalmente todo o texto do sistema, não só o `<body>`.
- URL da API configurável em runtime via `js/runtime-config.js` (`window.EDGE_API_BASE`).
- Sidebar estreita por padrão e expansão automática somente ao passar o mouse, sem botão e sem texto/ícone ES.
- Melhorias de responsividade e estados de erro/vazio.
- Câmeras locais e câmeras IP/RTSP/HTTP.
- Teste de stream com timeout.
- Stream IP convertido pelo backend para MJPEG para exibição no navegador.
- Status online/offline e última verificação da câmera.
- Estrutura preparada para a etapa posterior de YOLO26.

## Câmera IP

A câmera precisa fornecer RTSP ou HTTP. Exemplo:
`rtsp://192.168.1.100:554/stream`

O computador que executa o backend precisa alcançar a câmera pela rede.

## IA

O modelo esperado é `backend/model/edgev1.pt`. O backend carrega o YOLO com ByteTrack e aplica o motor inicial de risco.

## Próxima etapa

O modelo `edgev1.pt` é carregado diretamente pelo backend. A v6.4 não inventa detecções nem cria câmeras/alertas fictícios.

