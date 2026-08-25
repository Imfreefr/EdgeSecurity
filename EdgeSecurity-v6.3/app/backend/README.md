# EdgeSecurity — API de visão computacional

Esta API recebe quadros JPEG da câmera selecionada no navegador por WebSocket e executa YOLO26 + ByteTrack em tempo real. O navegador continua responsável pela captura da webcam; o backend é responsável pela inferência.

## 1. Instalação

Python 3.11+ recomendado.

```bash
cd backend
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Modelo treinado

Coloque o seu peso treinado em:

`backend/model/edgev1.pt`

ou defina `MODEL_PATH` no `.env`.

O sistema também aceita `pessoa`, `máquina`, `forklift` e aliases equivalentes. As classes `operador` e `objeto` são preservadas com seus nomes originais.

## 3. Executar

```bash
python run.py
```

API: `http://localhost:8000`

Health: `http://localhost:8000/api/health`

## 4. Importante para produção industrial

O motor de risco incluído é uma camada inicial de protótipo. Ele compara caixas em pixels. Isso não equivale a distância física em metros e não deve ser tratado como dispositivo de segurança certificado. Para implantação industrial, calibre cada câmera e defina zonas/limites físicos, além de uma política de falha segura e validação do sistema.

## 5. Câmeras IP/RTSP

A versão atual processa a câmera do navegador. Para uma câmera Wi-Fi/IP que forneça RTSP, o próximo passo é fazer o backend abrir o RTSP diretamente e enviar somente os resultados/stream ao navegador. Isso evita depender do navegador como capturador.


## Alertas automáticos de risco

O detector considera `human`/`pessoa` como pessoa e `forklift`/`empilhadeira` como empilhadeira. Quando uma pessoa entra nas zonas `high` ou `critical` em relação à empilhadeira, o backend grava automaticamente um alerta na tabela `alertas`. Um cooldown evita duplicação contínua do mesmo par de tracks. A interface exibe o alerta e pode usar a notificação do navegador.

A distância continua sendo em pixels e deve ser calibrada antes de qualquer alegação de distância física ou uso industrial.
