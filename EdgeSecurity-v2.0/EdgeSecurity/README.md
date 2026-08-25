# EdgeSecurity

Painel de monitoramento com estado inicial vazio.

## Dados

O projeto não cria câmeras, alertas, atividades, usuários ou históricos fictícios. O armazenamento local começa vazio e passa a conter somente dados adicionados durante o uso.

Na primeira abertura, o sistema solicita a criação do primeiro administrador. Depois, o administrador pode cadastrar usuários pela página **Usuários e Permissões**.

## Câmera

A página **Câmeras** usa a API nativa `MediaDevices` do navegador:

- solicita permissão para câmera;
- detecta dispositivos `videoinput` disponíveis;
- permite selecionar uma câmera;
- abre o feed ao vivo em `<video>`;
- permite parar a transmissão;
- reage à conexão/desconexão de dispositivos.

Essa integração é para câmeras acessíveis pelo dispositivo/browser (webcam ou câmera virtual). Câmeras IP/RTSP não são abertas diretamente pelo navegador; para isso será necessária uma camada de backend/gateway que converta o stream para um protocolo web, como WebRTC.

## Requisitos do navegador

O acesso à câmera depende da permissão do usuário e de um contexto seguro. Para desenvolvimento, use `localhost`; em produção, use HTTPS.

## Backend

`js/mock-data.js` é apenas a camada de persistência local para desenvolvimento. Ela não contém dados de demonstração. A próxima integração deve substituir essa camada por uma API/backend e banco de dados.
