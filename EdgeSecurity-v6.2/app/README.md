# EdgeSecurity v6.2

Versão com SQLite + FastAPI e suporte a câmeras IP/Wi-Fi por RTSP/HTTP.

## Iniciar

### 1. Backend

```cmd
cd backend
py -m pip install -r requirements.txt
py -m uvicorn app:app --host 127.0.0.1 --port 8000
```

Mantenha o terminal aberto.

### 2. Frontend

Em outro terminal, na pasta `app`:

```cmd
py serve.py
```

Abra:

`http://localhost:5500`

API:

`http://127.0.0.1:8000/docs`

## Câmera IP/Wi-Fi

A câmera precisa fornecer um stream RTSP ou HTTP. Exemplos de formato:

```text
rtsp://192.168.1.100:554/stream
http://192.168.1.100:8080/video
```

Na página **Câmeras**:

1. Informe o nome.
2. Informe a URL do stream.
3. Informe a localização, se desejar.
4. Clique em **Testar conexão**.
5. Se o teste passar, clique em **Cadastrar câmera IP**.
6. Em **Câmeras cadastradas**, clique em **Visualizar**.

O backend abre o stream com OpenCV e o disponibiliza ao navegador como MJPEG. Isso evita tentar reproduzir RTSP diretamente no navegador.

### Rede

O computador que executa o FastAPI precisa conseguir acessar o IP da câmera. Se a câmera estiver em outra rede/VLAN, o stream não será acessível até que exista roteamento/permissão de rede.

### Credenciais

Se a câmera exigir autenticação, use a URL fornecida pelo fabricante, conforme o formato aceito pelo dispositivo, por exemplo:

```text
rtsp://usuario:senha@192.168.1.100:554/stream
```

Não compartilhe essa URL publicamente, pois ela pode conter a senha.

## Observação sobre YOLO26

A v6.2 permite visualizar o stream IP, mas a análise YOLO26 do stream IP ainda deve ser integrada ao pipeline do backend. A câmera IP já fica registrada no SQLite e o endpoint MJPEG fornece a fonte de vídeo para a próxima etapa.


## v6.2

A sidebar do desktop é recolhida automaticamente e expande ao passar o mouse. O botão manual de recolhimento foi removido. O tempo de sessão é persistido por heartbeat no SQLite; consulte `backend/SESSION-TRACKING.md`.
