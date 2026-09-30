# EdgeSecurity — Multi-Camera Benchmark

## Visão Geral

Script para testar a capacidade de processamento multi-câmera do pipeline de inferência local (backend/Ultralytics YOLO11).

Testa progressivamente: **1, 2, 4, 6, 8, 10 câmeras** simultâneas.

---

## Requisitos

```bash
cd backend
pip install -r requirements.txt
pip install psutil gputil  # Para métricas de sistema
```

> **Nota**: `gputil` requer drivers NVIDIA. Em sistemas sem GPU NVIDIA, métricas de GPU serão 0.

---

## Uso Básico

### Teste Sintético (sem câmeras físicas)
```bash
# 1 câmera, 30 segundos
python scripts/benchmark.py --cameras 1 --duration 30 --source synthetic

# 4 câmeras
python scripts/benchmark.py --cameras 4 --duration 60 --source synthetic

# 10 câmeras, FPS alvo 10
python scripts/benchmark.py --cameras 10 --duration 60 --source synthetic --fps 10
```

### Teste com Câmeras RTSP Reais
```bash
python scripts/benchmark.py --cameras 4 --duration 60 --source rtsp \
  --urls "rtsp://user:pass@192.168.1.100:554/stream1" \
         "rtsp://user:pass@192.168.1.101:554/stream1" \
         "rtsp://user:pass@192.168.1.102:554/stream1" \
         "rtsp://user:pass@192.168.1.103:554/stream1"
```

### Teste com Arquivos de Vídeo
```bash
python scripts/benchmark.py --cameras 4 --duration 60 --source video \
  --urls "video1.mp4" "video2.mp4" "video3.mp4" "video4.mp4"
```

### Teste com Webcams Locais
```bash
python scripts/benchmark.py --cameras 2 --duration 30 --source webcam
```

---

## Parâmetros

| Parâmetro | Padrão | Descrição |
|-----------|--------|-----------|
| `--cameras` | 4 | Número de câmeras simultâneas |
| `--duration` | 30 | Duração do teste em segundos |
| `--source` | synthetic | Tipo: `synthetic`, `rtsp`, `webcam`, `video` |
| `--urls` | - | Lista de URLs RTSP ou caminhos de vídeo |
| `--model` | `backend/model/edgev1.pt` | Caminho do modelo YOLO |
| `--confidence` | 0.4 | Threshold de confiança |
| `--iou` | 0.5 | Threshold IoU para NMS |
| `--fps` | 8 | FPS alvo de inferência por câmera |
| `--width` | 640 | Largura do frame |
| `--height` | 480 | Altura do frame |
| `--output` | `benchmark_results` | Diretório de saída |

---

## Métricas Coletadas

### Por Câmera
- Frames recebidos da fonte
- Frames processados pela IA
- Frames descartados (backpressure)
- Erros de inferência
- Tempo médio de inferência (ms)
- P95 tempo de inferência (ms)
- FPS efetivo processado

### Agregado
- FPS total (todas as câmeras)
- Latência média / P50 / P95 / P99
- Taxa de frames descartados

### Sistema (amostrado a cada 1s)
- CPU % (média/pico)
- RAM usado (MB, média/pico)
- GPU % (média/pico) — se NVIDIA
- VRAM usado (MB, média/pico) — se NVIDIA

### Hardware (detectado automaticamente)
- CPU: modelo, cores, frequência
- RAM total
- GPU: nome, VRAM, driver
- CUDA disponível / versão

---

## Backpressure

O benchmark implementa backpressure realista:

```
Queue por câmera (padrão: 2 frames)
     ↓
Frame chega mais rápido que inferência?
     ↓
Queue cheia → DESCARTA frame antigo (frames_dropped++)
```

Isso evita crescimento ilimitado de RAM e simula comportamento de produção.

---

## Exemplo de Saída

```
================================================================================
BENCHMARK RESULTS SUMMARY
================================================================================
Hardware: Windows-10-10.0.19045-SP0
CPU: 12 cores @ 4800 MHz
RAM: 32.0 GB
CUDA: True
GPU: NVIDIA GeForce RTX 3080

Config: 4 cameras, 60s, 8 FPS target

Aggregate:
  Frames Received:  7,200
  Frames Processed: 1,920
  Frames Dropped:   5,280 (73.3%)
  Errors:           0
  Overall FPS:      32.00
  Avg Inference:    12.50 ms
  P50 Inference:    11.80 ms
  P95 Inference:    18.20 ms
  P99 Inference:    22.50 ms

System:
  CPU:     avg=45.2%  peak=78.1%
  RAM:     avg=2,150 MB  peak=2,890 MB
  GPU:     avg=62.3%  peak=89.5%
  VRAM:    avg=3,200 MB  peak=4,100 MB

Per-Camera:
    Cam     Recv     Proc     Drop     Err    Avg ms    P95 ms  Eff FPS
      0     1800     480     1320      0    12.45     17.80      8.00
      1     1800     480     1320      0    12.60     18.10      8.00
      2     1800     480     1320      0    12.30     17.50      8.00
      3     1800     480     1320      0    12.55     18.30      8.00
================================================================================
```

---

## Interpretação

### Sintético vs Real
| Aspecto | Sintético | Real (RTSP/Webcam) |
|---------|-----------|-------------------|
| Decodificação | Não (frames numpy) | Sim (H.264/H.265 → overhead) |
| Latência rede | Zero | Variável (jitter, packet loss) |
| Reconexão | N/A | Testada |
| FPS fonte | Constante (30) | Variável |

**Apenas teste real valida completamente o cenário de produção.**

### Capacidade Estável
Um número de câmeras é considerado **estável** quando:
- CPU < 85% sustentado
- RAM não cresce indefinidamente (sem memory leak)
- Frames descartados < 10% (ou dentro do orçado pelo backpressure)
- P95 latência < 200ms
- Sem erros de CUDA OOM

---

## Relatório Final

Gera dois arquivos em `benchmark_results/`:
- `benchmark_YYYYMMDD_HHMMSS.json` — dados completos
- `benchmark_YYYYMMDD_HHMMSS_summary.csv` — resumo tabular

---

## Execução Automatizada (1→10 câmeras)

```bash
#!/bin/bash
for cams in 1 2 4 6 8 10; do
  echo "=== Testing $cams cameras ==="
  python scripts/benchmark.py --cameras $cams --duration 60 --source synthetic \
    --output benchmark_results/cams_$cams
  sleep 5  # Cooldown entre testes
done
```

---

## Troubleshooting

| Erro | Causa | Solução |
|------|-------|---------|
| `ModuleNotFoundError: ultralytics` | Deps não instaladas | `pip install -r backend/requirements.txt` |
| `CUDA out of memory` | VRAM insuficiente | Reduza `--fps`, `--cameras` ou resolução |
| `Failed to open RTSP` | URL errada / rede | Teste com `ffplay rtsp://...` primeiro |
| `gputil not found` | Métricas GPU indisponíveis | `pip install gputil` ou ignore (métricas = 0) |
| FPS muito baixo | CPU bottleneck | Reduza `--cameras` ou `--fps` |

---

## Próximos Passos

- [ ] Suporte a batch inference (processar N frames juntos)
- [ ] TensorRT / ONNX Runtime CUDA acceleration
- [ ] Métricas de precisão (mAP) com dataset anotado
- [ ] Teste de longa duração (4h+) para memory leaks
- [ ] Integração com CI/CD para regression testing