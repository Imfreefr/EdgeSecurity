(() => {
  const video = document.getElementById("camera-video");
  const canvas = document.getElementById("ai-overlay");
  const ctx = canvas.getContext("2d");
  const select = document.getElementById("camera-select");
  const start = document.getElementById("start-camera");
  const stop = document.getElementById("stop-camera");
  const detect = document.getElementById("detect-cameras");
  const register = document.getElementById("register-camera");
  const registeredList = document.getElementById("registered-cameras");
  const startAI = document.getElementById("start-ai");
  const stopAIButton = document.getElementById("stop-ai");
  const empty = document.getElementById("camera-empty");
  const label = document.getElementById("camera-device-label");
  const status = document.getElementById("camera-live-status");
  const aiStatus = document.getElementById("ai-status");
  const list = document.getElementById("device-list");
  const cameraError = document.getElementById("camera-error");
  const ipName = document.getElementById("ip-name");
  const ipUrl = document.getElementById("ip-url");
  const ipLocation = document.getElementById("ip-location");
  const testIp = document.getElementById("test-ip-camera");
  const saveIp = document.getElementById("save-ip-camera");
  const ipStatus = document.getElementById("ip-status");
  const ipError = document.getElementById("ip-error");
  let testedIp = false;
  const humanCount = document.getElementById("ai-human-count");
  const machineCount = document.getElementById("ai-machine-count");
  const riskLevel = document.getElementById("ai-risk-level");
  let stream = null,
    devices = [],
    aiRunning = false,
    frameTimer = null;
  function currentUser() {
    const s = EdgeAuth.current();
    return s ? EdgeDB.users.find((u) => u.id === s.id) : null;
  }
  function canUseCamera() {
    const u = currentUser();
    return (
      !!u &&
      (u.cargo === "administrador" ||
        u.permissoes?.usar_camera_dispositivo !== false)
    );
  }
  function canRegisterCamera() {
    const u = currentUser();
    return (
      !!u &&
      (u.cargo === "administrador" || u.permissoes?.gerenciar_cameras === true)
    );
  }
  function registeredCameras() {
    return Array.isArray(EdgeDB.cameras) ? EdgeDB.cameras : [];
  }
  function setCameraError(message = "") {
    if (!cameraError) return;
    cameraError.textContent = message;
    cameraError.hidden = !message;
  }
  function explainCameraError(err) {
    const messages = {
      NotAllowedError:
        "O navegador bloqueou a câmera. Clique no cadeado ao lado do endereço, permita a câmera e recarregue a página.",
      PermissionDeniedError:
        "Acesso à câmera negado. Libere a permissão para este endereço e tente novamente.",
      NotFoundError:
        "Nenhuma câmera encontrada neste dispositivo. Conecte uma webcam ou verifique se a câmera está ativada.",
      NotReadableError:
        "A câmera está em uso por outro aplicativo. Feche o outro app e tente novamente.",
      OverconstrainedError:
        "Esta câmera não aceitou a configuração pedida. Tentando novamente com configuração padrão.",
      SecurityError:
        "A câmera só funciona em modo local ou com HTTPS. Abra o EdgeSecurity no endereço local.",
      AbortError: "O acesso à câmera foi interrompido. Tente novamente.",
      UNSUPPORTED: CameraAPI.supportError(),
    };
    return (
      messages[err?.name] ||
      "Não foi possível acessar a câmera. Verifique a conexão e as permissões."
    );
  }
  function renderRegistered() {
    const items = registeredCameras();
    if (!items.length) {
      registeredList.innerHTML =
        '<div class="empty-state">Nenhuma câmera cadastrada.</div>';
      return;
    }
    registeredList.innerHTML = items
      .map((c) => {
        const isIp = ["ip", "rtsp", "wifi"].includes(c.tipo);
        const action = isIp
          ? `<button class="btn btn-secondary btn-small" data-ipview="${escapeHtml(c.id)}">Visualizar</button>`
          : c.device_id
            ? `<button class="btn btn-secondary btn-small" data-registered="${escapeHtml(c.id)}">Usar</button>`
            : "";
        return `<div class="device-row"><span><strong>${escapeHtml(c.nome)}</strong><small>${escapeHtml(c.tipo || "dispositivo")} · ${escapeHtml(c.endereco || c.status || "ativo")}</small></span><span class="device-actions">${action}<button class="btn btn-danger btn-small" data-delete-camera="${escapeHtml(c.id)}">Remover</button></span></div>`;
      })
      .join("");
    registeredList.querySelectorAll("[data-registered]").forEach(
      (btn) =>
        (btn.onclick = () => {
          const c = registeredCameras().find(
            (x) => x.id === btn.dataset.registered,
          );
          if (c?.device_id) {
            select.value = c.device_id;
            startCamera(c.device_id);
          }
        }),
    );
    registeredList
      .querySelectorAll("[data-ipview]")
      .forEach(
        (btn) => (btn.onclick = () => startIpCamera(btn.dataset.ipview)),
      );
    registeredList.querySelectorAll("[data-delete-camera]").forEach(
      (btn) =>
        (btn.onclick = async () => {
          if (!confirm("Remover esta câmera do cadastro?")) return;
          try {
            await EdgeAPI.del("/cameras/" + btn.dataset.deleteCamera);
            await EdgeData.load();
            renderRegistered();
            showToast("Câmera removida.");
          } catch (e) {
            showToast(e.message);
          }
        }),
    );
  }
  function setIpError(msg = "") {
    if (!ipError) return;
    ipError.textContent = msg;
    ipError.hidden = !msg;
  }
  async function testIpCamera() {
    const url = ipUrl?.value.trim();
    if (!url) {
      setIpError("Informe o endereço do vídeo da câmera (RTSP ou HTTP).");
      return;
    }
    try {
      testIp.disabled = true;
      testIp.textContent = "Testando…";
      setIpError("");
      ipStatus.textContent = "Testando…";
      ipStatus.classList.remove("live");
      await EdgeAPI.post("/cameras/test", { endereco: url });
      testedIp = true;
      saveIp.disabled = !canRegisterCamera();
      ipStatus.textContent = "Conexão OK";
      ipStatus.classList.add("live");
      showToast("Conexão verificada — vídeo disponível.");
    } catch (e) {
      testedIp = false;
      saveIp.disabled = true;
      ipStatus.textContent = "Falha na conexão";
      ipStatus.classList.remove("live");
      setIpError(e.message);
      showToast(e.message);
    } finally {
      testIp.disabled = false;
      testIp.textContent = "Testar conexão";
    }
  }
  async function saveIpCamera() {
    if (!testedIp) {
      showToast("Clique em Testar conexão antes de cadastrar.");
      return;
    }
    if (!canRegisterCamera()) {
      showToast("Sua conta não tem permissão para cadastrar câmeras.");
      return;
    }
    try {
      await EdgeAPI.post("/cameras", {
        nome: ipName.value.trim() || "Câmera de rede",
        tipo: "ip",
        endereco: ipUrl.value.trim(),
        localizacao: ipLocation.value.trim() || null,
        status: "ativo",
      });
      await EdgeData.load();
      renderRegistered();
      ipName.value = "";
      ipUrl.value = "";
      ipLocation.value = "";
      testedIp = false;
      saveIp.disabled = true;
      ipStatus.textContent = "Não testada";
      ipStatus.classList.remove("live");
      showToast("Câmera de rede cadastrada.");
    } catch (e) {
      showToast(e.message);
    }
  }
  function startIpCamera(cid) {
    const c = registeredCameras().find((x) => x.id === cid);
    if (!c) return;
    stopCamera();
    const token = EdgeAPI.token();
    if (!token) {
      showToast("Sessão expirada. Entre novamente.");
      return;
    }
    const img = document.createElement("img");
    img.id = "ip-stream";
    img.alt = "Vídeo da câmera de rede";
    img.className = "ip-stream";
    img.onerror = () => {
      setCameraError(
        "Não foi possível receber o vídeo. Verifique a conexão e o endereço da câmera.",
      );
      setStatus("Erro no vídeo");
    };
    img.onload = () => {
      empty.style.display = "none";
      video.style.display = "none";
      canvas.style.display = "none";
      setStatus("AO VIVO", true);
      label.textContent = c.nome;
      stop.disabled = false;
      startAI.disabled = true;
    };
    document.querySelector(".camera-stage-real").appendChild(img);
    img.src = `${EdgeAPI.base()}/cameras/${encodeURIComponent(cid)}/mjpeg?token=${encodeURIComponent(token)}`;
    window._ipStream = img;
  }
  async function registerSelected() {
    const u = currentUser();
    if (!u) {
      showToast("Sessão expirada. Entre novamente.");
      return;
    }
    if (!canRegisterCamera()) {
      showToast("Sua conta não tem permissão para cadastrar câmeras.");
      return;
    }
    const d = devices.find((x) => x.deviceId === select.value);
    if (!d) {
      showToast("Detecte e selecione uma câmera antes de cadastrar.");
      return;
    }
    const existing = registeredCameras().find(
      (c) => c.device_id === d.deviceId,
    );
    if (existing) {
      showToast("Esta câmera já está cadastrada.");
      return;
    }
    try {
      await EdgeAPI.post("/cameras", {
        nome: d.label || "Câmera deste dispositivo",
        tipo: "browser",
        device_id: d.deviceId,
        status: "ativo",
      });
      await EdgeData.load();
      renderRegistered();
      showToast("Câmera cadastrada com sucesso.");
    } catch (err) {
      showToast(err.message);
    }
  }
  function setStatus(text, live = false) {
    status.textContent = text;
    status.classList.toggle("live", live);
  }
  function setAIStatus(text, live = false) {
    aiStatus.textContent = text;
    aiStatus.classList.toggle("live", live);
  }
  function drawResults(data) {
    if (!video.videoWidth) return;
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const risk = data.risk?.level || "safe";
    const line = risk === "critical" ? 6 : risk === "high" ? 5 : 3;
    (data.detections || []).forEach((d) => {
      const [x1, y1, x2, y2] = d.bbox;
      ctx.lineWidth = line;
      ctx.strokeStyle =
        d.class_name === "human"
          ? "#22c55e"
          : d.class_name === "machine"
            ? "#f59e0b"
            : "#60a5fa";
      ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
      ctx.font = "bold 16px Inter, sans-serif";
      const text = `${d.label} ${(d.confidence * 100).toFixed(0)}%${d.track_id != null ? ` #${d.track_id}` : ""}`;
      ctx.fillStyle = ctx.strokeStyle;
      ctx.fillRect(
        x1,
        Math.max(0, y1 - 24),
        ctx.measureText(text).width + 10,
        24,
      );
      ctx.fillStyle = "#08111f";
      ctx.fillText(text, x1 + 5, Math.max(17, y1 - 6));
    });
    humanCount.textContent = (data.detections || []).filter(
      (d) => d.class_name === "human",
    ).length;
    machineCount.textContent = (data.detections || []).filter(
      (d) => d.class_name === "machine",
    ).length;
    riskLevel.textContent =
      { safe: "Seguro", medium: "Atenção", high: "Alto", critical: "CRÍTICO" }[
        risk
      ] || risk;
    riskLevel.dataset.level = risk;
  }
  const AI = window.EdgeAILocal || window.EdgeAI;
  function stopAIAnalysis() {
    aiRunning = false;
    if (frameTimer) clearInterval(frameTimer);
    frameTimer = null;
    try { window.EdgeAI && window.EdgeAI.close(); } catch {}
    try { window.EdgeAILocal && window.EdgeAILocal.close(); } catch {}
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    startAI.disabled = !stream;
    stopAIButton.disabled = true;
    setAIStatus("Detecção desligada");
    humanCount.textContent = "0";
    machineCount.textContent = "0";
    riskLevel.textContent = "—";
    riskLevel.dataset.level = "";
  }
  function startAnalysis() {
    if (!stream) {
      showToast("Ative uma câmera antes de iniciar a detecção.");
      return;
    }
    const registered = registeredCameras().find(
      (c) => c.device_id === select.value,
    );
    if (!registered) {
      showToast("Cadastre esta câmera antes de iniciar a detecção.");
      return;
    }
    const cameraId = registered.id;
    setAIStatus(window.EdgeAILocal ? "Carregando IA local…" : "Conectando…");
    AI.connect(
      cameraId,
      drawResults,
      (msg) => {
        if (AI === window.EdgeAILocal && window.EdgeAI) {
          setAIStatus("Tentando IA no servidor…");
          window.EdgeAI.connect(cameraId, drawResults, (m) => { stopAIAnalysis(); showToast(m); setAIStatus("Erro na detecção"); }, () => {
            aiRunning = true;
            setAIStatus("Detecção ao vivo", true);
            startAI.disabled = true;
            stopAIButton.disabled = false;
            const frameCanvas = document.createElement("canvas");
            const interval = Math.max(100, Math.round(1000 / 8));
            frameTimer = setInterval(() => {
              if (!aiRunning || !video.videoWidth) return;
              frameCanvas.width = 640;
              frameCanvas.height = Math.round(video.videoHeight * (640 / video.videoWidth));
              frameCanvas.getContext("2d").drawImage(video, 0, 0, frameCanvas.width, frameCanvas.height);
              window.EdgeAI.sendFrame(frameCanvas, cameraId, 0.62);
            }, interval);
          });
          return;
        }
        stopAIAnalysis();
        showToast(msg);
        setAIStatus("Erro na detecção");
      },
      () => {
        aiRunning = true;
        setAIStatus(window.EdgeAILocal ? "IA local ao vivo" : "Detecção ao vivo", true);
        startAI.disabled = true;
        stopAIButton.disabled = false;
        const frameCanvas = document.createElement("canvas");
        const interval = Math.max(100, Math.round(1000 / 8));
        frameTimer = setInterval(() => {
          if (!aiRunning || !video.videoWidth) return;
          frameCanvas.width = 640;
          frameCanvas.height = Math.round(
            video.videoHeight * (640 / video.videoWidth),
          );
          frameCanvas
            .getContext("2d")
            .drawImage(video, 0, 0, frameCanvas.width, frameCanvas.height);
          AI.sendFrame(frameCanvas, cameraId, 0.62);
        }, interval);
      },
    );
  }
  function stopCamera() {
    stopAIAnalysis();
    if (window._ipStream) {
      window._ipStream.src = "";
      window._ipStream.remove();
      window._ipStream = null;
    }
    stopAIAnalysis();
    CameraAPI.stop(stream);
    stream = null;
    video.srcObject = null;
    video.style.display = "none";
    canvas.style.display = "none";
    empty.style.display = "flex";
    stop.disabled = true;
    startAI.disabled = true;
    setStatus("Sem transmissão");
    label.textContent = "Nenhuma câmera selecionada";
  }
  async function startCamera(deviceId) {
    setCameraError("");
    if (!CameraAPI.supported()) {
      setCameraError(CameraAPI.supportError());
      showToast("A câmera só funciona no endereço local ou com HTTPS.");
      return;
    }
    if (!canUseCamera()) {
      setCameraError("Sua conta não tem permissão para usar esta câmera.");
      return;
    }
    try {
      stopAIAnalysis();
      CameraAPI.stop(stream);
      stream = await CameraAPI.open(deviceId);
      video.srcObject = stream;
      await video.play();
      video.style.display = "block";
      canvas.style.display = "block";
      empty.style.display = "none";
      stop.disabled = false;
      startAI.disabled = false;
      setStatus("AO VIVO", true);
      const track = stream.getVideoTracks()[0],
        currentId = track.getSettings().deviceId,
        current = devices.find((d) => d.deviceId === currentId);
      if (current) {
        select.value = current.deviceId;
        label.textContent = current.label || "Câmera selecionada";
      }
      await refreshDevices();
      setCameraError("");
    } catch (err) {
      const message = explainCameraError(err);
      setCameraError(message);
      showToast(message);
      stopCamera();
    }
  }
  async function refreshDevices() {
    try {
      devices = await CameraAPI.list();
      select.innerHTML = "";
      if (!devices.length) {
        select.disabled = true;
        select.innerHTML = "<option>Nenhuma câmera encontrada</option>";
        list.innerHTML =
          '<div class="empty-state">Nenhuma câmera encontrada. Conecte uma câmera e clique em Detectar câmeras.</div>';
        register.disabled = true;
        return;
      }
      devices.forEach((d, i) => {
        const o = document.createElement("option");
        o.value = d.deviceId;
        o.textContent = d.label || `Câmera ${i + 1}`;
        select.appendChild(o);
      });
      select.disabled = false;
      register.disabled = !canRegisterCamera();
      list.innerHTML = devices
        .map(
          (d, i) =>
            `<div class="device-row"><span><strong>${escapeHtml(d.label || `Câmera ${i + 1}`)}</strong><small>Câmera detectada neste dispositivo</small></span><button class="btn btn-secondary btn-small" data-device="${escapeHtml(d.deviceId)}">Ativar</button></div>`,
        )
        .join("");
      list.querySelectorAll("[data-device]").forEach(
        (btn) =>
          (btn.onclick = () => {
            select.value = btn.dataset.device;
            startCamera(btn.dataset.device);
          }),
      );
    } catch (err) {
      if (err?.name === "UNSUPPORTED") {
        setCameraError(CameraAPI.supportError());
        list.innerHTML =
          '<div class="empty-state">A câmera só funciona no endereço local ou com HTTPS.</div>';
      } else {
        setCameraError(explainCameraError(err));
      }
      register.disabled = true;
    }
  }
  async function detectCameras() {
    setCameraError("");
    if (!CameraAPI.supported()) {
      setCameraError(CameraAPI.supportError());
      showToast("A câmera só funciona no endereço local ou com HTTPS.");
      return;
    }
    if (!canUseCamera()) {
      setCameraError("Sua conta não tem permissão para usar esta câmera.");
      return;
    }
    try {
      detect.disabled = true;
      detect.textContent = "Solicitando permissão…";
      await CameraAPI.requestPermission();
      await refreshDevices();
      if (devices.length) {
        showToast(
          devices.length === 1
            ? "1 câmera encontrada."
            : `${devices.length} câmeras encontradas.`,
        );
        if (!select.value) select.value = devices[0].deviceId;
      } else {
        setCameraError(
          "Permissão concedida, mas nenhuma câmera foi encontrada neste dispositivo.",
        );
      }
    } catch (err) {
      setCameraError(explainCameraError(err));
      showToast(explainCameraError(err));
    } finally {
      detect.disabled = false;
      detect.textContent = "Detectar câmeras";
    }
  }
  function escapeHtml(v) {
    return String(v).replace(
      /[&<>'"]/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          "'": "&#39;",
          '"': "&quot;",
        })[c],
    );
  }
  function initializeCameraPage() {
    renderRegistered();
    register.disabled = true;
    if (!canUseCamera()) {
      start.disabled = true;
      detect.disabled = true;
      setCameraError(
        "Sua conta não possui permissão para usar a câmera deste dispositivo.",
      );
    }
    register.onclick = registerSelected;
    testIp?.addEventListener("click", testIpCamera);
    saveIp?.addEventListener("click", saveIpCamera);
    detect.onclick = detectCameras;
    start.onclick = () => startCamera(select.value || undefined);
    stop.onclick = stopCamera;
    startAI.onclick = startAnalysis;
    stopAIButton.onclick = stopAIAnalysis;
    select.onchange = () => startCamera(select.value);
    window.addEventListener("beforeunload", stopCamera);
    if (navigator.mediaDevices?.addEventListener)
      navigator.mediaDevices.addEventListener("devicechange", refreshDevices);
    refreshDevices();
  }
  window.addEventListener("edge-data-ready", initializeCameraPage);
})();
