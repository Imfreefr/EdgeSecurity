# EdgeSecurity — Edge AI Architecture

## Visão Geral

O EdgeSecurity implementa inferência de IA **local no dispositivo do cliente** (edge computing), seguindo o princípio:

```
Câmera → Dispositivo Local → Inferência → Detecção → Risco → Alerta → Supabase
```

**NÃO** envia vídeo continuamente para a nuvem. Apenas eventos estruturados (alertas) são persistidos.

---

## 1. Dois Pipelines de Inferência

| Pipeline | Onde Executa | Modelo | Framework | Uso |
|----------|--------------|--------|-----------|-----|
| **Browser (WASM)** | Navegador do usuário | `edgev1-int8.onnx` (2.7MB) | ONNX Runtime Web (WASM, SIMD) | Webcam local, demo, baixa latência |
| **Backend (Python)** | Servidor local/edge | `edgev1.pt` / `edgev1.onnx` (5.4MB) | Ultralytics YOLO11 | Câmeras IP/RTSP, multi-câmera, produção |

### Browser Pipeline (EdgeAILocal)
```
HTML5 Video → Canvas (640x640) → Web Worker → ONNX Runtime WASM → Detections
                                                              ↓
                                            RiskEngine (JS) → Alert API → Supabase
```

- **Arquivos**: `js/ai-local.js`, `js/ai-worker.js`, `js/risk-engine.js`
- **Modelo**: `edgev1-int8.onnx` (INT8 quantizado, ~2.7MB)
- **Input**: 640×640 RGB (letterbox + padding)
- **Tracking**: ByteTrack (via ONNX model metadata)
- **Classes**: `human` (pessoa/trabalhador), `forklift` (empilhadeira/máquina)
- **Thresholds**: confidence=0.4, IoU=0.5
- **FPS efetivo**: ~8 FPS (configurável via `frameTimer` em cameras.js)

### Backend Pipeline (SafetyDetector)
```
RTSP/HTTP Stream → OpenCV → Ultralytics YOLO11 → track(persist=True) → Detections
                                                                    ↓
                                                        assess_risk() → create_ai_alert() → Supabase
```

- **Arquivos**: `backend/services/detector.py`, `backend/services/risk_engine.py`
- **Modelo**: `edgev1.pt` (PyTorch) ou `edgev1.onnx` (ONNX)
- **Endpoint**: WebSocket `/ws/detection` (recebe base64 JPEG, retorna JSON)
- **Classes**: Mesma taxonomia do browser
- **Thresholds**: `AI_CONFIDENCE=0.40`, `AI_IOU=0.50` (via env)

---

## 2. Modelo YOLO (edgev1)

| Arquivo | Tamanho | Formato | Uso |
|---------|---------|---------|-----|
| `edgev1.pt` | 5.4 MB | PyTorch | Treinamento, exportação, backend |
| `edgev1.onnx` | 4.9 MB | ONNX FP32 | Backend opcional, conversão |
| `edgev1-int8.onnx` | 2.7 MB | ONNX INT8 | **Browser (WASM)** - otimizado |

### Classes Treinadas
O modelo foi treinado/fine-tuned para detectar:
- **Pessoa**: `person`, `pessoa`, `human`, `humano`, `worker`, `trabalhador`, `operador`
- **Máquina/Empilhadeira**: `machine`, `máquina`, `maquina`, `vehicle`, `veiculo`, `veículo`, `forklift`, `empilhadeira`, `objeto`

Mapeamento interno → `human` / `forklift`

---

## 3. Risk Engine (Avaliação de Risco)

### Algoritmo (Pixel-based — Requer Calibração Física)
```python
# Gap entre bounding boxes (0 = sobrepostas)
gap = box_gap(person_bbox, machine_bbox)

# Níveis (pixels)
gap <= 0      → "critical"  (caixas sobrepostas)
gap <= 40     → "high"      (muito próximas)
gap <= 90     → "medium"    (próximas)
else          → "safe"
```

> ⚠️ **Importante**: Distâncias em pixels **não** equivalem a metros. Para uso industrial, calibrar cada câmera com homografia/zonas físicas.

### Saída
```json
{
  "level": "critical|high|medium|safe",
  "pairs": [
    {
      "person_track_id": 123,
      "machine_track_id": 456,
      "gap_pixels": 12.5,
      "center_distance_pixels": 85.3,
      "level": "high"
    }
  ]
}
```

---

## 4. Geração de Alertas

### Backend (create_ai_alert)
- Só cria alerta se `level ∈ {high, critical}`
- Debounce: 5 segundos por `(camera_id, level)`
- Persiste em `alertas` table com `company_id` para isolamento multi-tenant

### Browser (EdgeAILocal)
- Mesmo debounce via `RiskEngine` no worker
- Chama `EdgeAPI.post("/alerts", {...})` para persistir no Supabase
- Beep sonoro para `high`/`critical`

---

## 5. Integração Frontend (cameras.js)

### Fluxo Webcam Local (Browser AI)
1. Usuário seleciona webcam → `startCamera()`
2. Clica "Iniciar IA" → `startAnalysis()`
3. `EdgeAILocal.connect(cameraId, drawResults, onError, onReady)`
4. Worker carrega `edgev1-int8.onnx` → `ready` event
5. `setInterval` a cada ~125ms (8 FPS):
   - Captura frame do `<video>` → canvas 640×proporcional
   - `EdgeAILocal.sendFrame(canvas, cameraId, 0.62)`
6. Worker retorna detections → `drawResults()` desenha overlays no canvas
7. Se `risk.level ∈ {high, critical}` → POST `/alerts` + beep

### Fluxo Câmera IP/RTSP (Backend AI)
1. Câmera cadastrada com `tipo: "ip"` + `endereco: "rtsp://..."`
2. Usuário clica "Visualizar" → `startIpCamera()`
3. `<img src="/api/cameras/{id}/mjpeg?token=...">` (MJPEG stream via backend)
4. Para IA: conecta no WebSocket `/ws/detection` via `EdgeAI`
5. Backend processa stream → detections via WebSocket

---

## 6. Deploy & Model Serving

### Desenvolvimento Local
```
Frontend (Vite:5500) → Backend (FastAPI:8000)
Modelo: backend/model/edgev1-int8.onnx (servido estaticamente pelo backend ou Vite)
```

### Produção (Vercel + Backend Local/Edge)
```
Frontend (Vercel: https://xxx.vercel.app)
  → assets/edgev1-int8.onnx (copiado no build via Vite plugin)
  → API calls → Backend local (FastAPI) ou Serverless (Vercel Functions)
  → WebSocket → Backend local (para câmeras IP/RTSP)
```

### Caminhos do Modelo (MODEL_URLS)
```javascript
const MODEL_URLS = [
  "/assets/edgev1-int8.onnx",           // Vercel/production (build output)
  "../backend/model/edgev1-int8.onnx",  // Local dev (Vite proxy ou backend estático)
  "backend/model/edgev1-int8.onnx",     // Local dev fallback
  "/backend/model/edgev1-int8.onnx",    // Local dev fallback
];
```

---

## 7. Configuração de Ambiente

```bash
# Backend
MODEL_PATH=backend/model/edgev1.pt        # Backend pipeline
AI_CONFIDENCE=0.40
AI_IOU=0.50
AI_LOCAL=true                             # Habilita EdgeAILocal no frontend

# Frontend (build time)
# Modelo copiado automaticamente para dist/assets/edgev1-int8.onnx
```

---

## 8. Benchmark & Performance

### Métricas Coletadas (scripts/benchmark.py)
- FPS fonte vs FPS processado
- Latência média / p95
- CPU / RAM / GPU / VRAM
- Frames recebidos / processados / descartados
- Backpressure: fila limitada (max 2 frames/câmera), drop oldest

### Degradação Controlada
Se CPU > 85% ou fila cheia:
1. Reduz FPS de inferência (ex: 8 → 4 FPS)
2. Reduz resolução de inferência (640 → 416)
3. Aumenta intervalo de análise
4. Log de alerta de capacidade

---

## 9. Próximos Passos (Roadmap)

- [ ] Calibração física por câmera (homografia → metros reais)
- [ ] Zonas de risco configuráveis (polígonos no mapa)
- [ ] Batch inference para multi-câmera no backend
- [ ] TensorRT / DirectML acceleration no backend
- [ ] Model versioning & A/B testing
- [ ] Exportação de eventos para SIEM/SOAR

---

## 10. Arquivos Relacionados

```
backend/
├── services/
│   ├── detector.py          # SafetyDetector (Ultralytics YOLO11)
│   └── risk_engine.py       # assess_risk() - pixel based
├── model/
│   ├── edgev1.pt            # PyTorch model
│   ├── edgev1.onnx          # ONNX FP32
│   └── edgev1-int8.onnx     # ONNX INT8 (browser)
├── app.py                   # /ws/detection, /api/ai/status, create_ai_alert

js/
├── ai-local.js              # EdgeAILocal (browser WASM pipeline)
├── ai-worker.js             # Web Worker + ONNX Runtime Web
├── risk-engine.js           # RiskEngine (JS mirror)
├── cameras.js               # UI integration, frame capture loop
└── api.js                   # EdgeAPI (auth, alerts POST)

migrations/
├── 001_initial_schema.sql   # alertas table with company_id
└── 002_super_admin_and_seed.sql
```