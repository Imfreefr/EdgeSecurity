window.EdgeAILocal = (() => {
  let worker = null;
  let ready = false;
  let cbResult = null;
  let cbError = null;
  let cbReady = null;
  let currentCamera = null;
  let lastBeep = 0;
  const MODEL_URLS = ["../backend/model/edgev1-int8.onnx", "backend/model/edgev1-int8.onnx", "/backend/model/edgev1-int8.onnx"];
  let audioCtx = null;
  function beep(level) {
    const now = Date.now();
    if (now - lastBeep < 4000) return;
    lastBeep = now;
    try {
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      const o = audioCtx.createOscillator();
      const g = audioCtx.createGain();
      o.type = "sine";
      o.frequency.value = level === "critical" ? 880 : 660;
      g.gain.value = 0.12;
      o.connect(g).connect(audioCtx.destination);
      o.start();
      g.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.45);
      o.stop(audioCtx.currentTime + 0.5);
    } catch {}
  }
  function ensureWorker() {
    if (worker) return worker;
    worker = new Worker("js/ai-worker.js");
    worker.onmessage = (e) => {
      const { type, detections, cameraId, message, model } = e.data;
      if (type === "ready") {
        ready = true;
        cbReady?.({ model: model || "edgev1-int8.onnx", classes: ["human", "forklift"] });
      } else if (type === "result") {
        const risk = window.RiskEngine ? window.RiskEngine.assess(detections || []) : { level: "safe", pairs: [] };
        if (risk.level === "high" || risk.level === "critical") beep(risk.level);
        if (risk.level === "high" || risk.level === "critical") {
          try {
            EdgeAPI.post("/alerts", { camera_id: cameraId, tipo: "IA - Aproximação", nivel: risk.level === "critical" ? "Crítico" : "Alto", descricao: risk.level === "critical" ? "RISCO CRÍTICO: pessoa e máquina muito próximas." : "Risco de colisão detectado pela IA.", status: "Aberto" }).catch(() => {});
          } catch {}
        }
        cbResult?.({ camera_id: cameraId, detections: detections || [], risk, alert_created: null });
      } else if (type === "error") {
        cbError?.(message || "Falha na IA local.");
      }
    };
    worker.onerror = (ev) => cbError?.(ev.message || "Erro no Worker de IA.");
    return worker;
  }
  function connect(cameraId, onResult, onError, onReady) {
    cbResult = onResult;
    cbError = onError;
    cbReady = onReady;
    currentCamera = cameraId;
    const w = ensureWorker();
    w.postMessage({ type: "init", payload: { modelUrl: MODEL_URLS[0] } });
  }
  function sendFrame(canvas, cameraId, quality = 0.62) {
    if (!worker || !ready) return false;
    try {
      const w = canvas.width, h = canvas.height;
      const ctx = canvas.getContext("2d");
      const imageData = ctx.getImageData(0, 0, w, h);
      const buffer = imageData.data.buffer.slice(0);
      worker.postMessage({ type: "infer", payload: { buffer, width: w, height: h, cameraId, confidence: 0.4 } }, [buffer]);
      return true;
    } catch {
      return false;
    }
  }
  function close() {
    if (worker) {
      try { worker.terminate(); } catch {}
      worker = null;
      ready = false;
    }
  }
  function isConnected() { return ready; }
  return { connect, sendFrame, close, isConnected, beep };
})();
