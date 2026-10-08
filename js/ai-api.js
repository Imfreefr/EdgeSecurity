/* Cliente WebSocket da detecção ao vivo. O backend executa a análise. */
window.EdgeAI = (() => {
  function httpBase() {
    return window.EDGE_API_BASE || "http://127.0.0.1:8000";
  }
  let socket = null;
  let framePending = false;

  function connect(cameraId, onResult, onError, onReady) {
    close();

    const base = httpBase();
    const wsBase = base
      .replace(/^http:/, "ws:")
      .replace(/^https:/, "wss:")
      .replace(/\/$/, "");

    socket = new WebSocket(`${wsBase}/ws/detection`);

    socket.onopen = () => socket.send(JSON.stringify({
      type: "auth", token: window.EdgeAPI?.token(), camera_id: cameraId,
    }));

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "ready") onReady?.(data);
        else if (data.type === "result") { framePending = false; onResult?.(data); }
        else if (data.type === "error") { framePending = false; onError?.(data.message); }
      } catch (_) {
        onError?.("Resposta inesperada do serviço de detecção.");
      }
    };

    socket.onerror = () =>
      onError?.(
        "Não foi possível conectar ao serviço de detecção. Verifique se o serviço está ativo.",
      );
    socket.onclose = (event) => {
      framePending = false;
      if (event.code !== 1000) onError?.("Conexão de detecção encerrada. Verifique sua sessão e o serviço local.");
    };
  }

  function sendFrame(canvas, cameraId, quality = 0.65) {
    if (!socket || socket.readyState !== WebSocket.OPEN || framePending || socket.bufferedAmount > 0) return false;

    framePending = true;
    socket.send(
      JSON.stringify({
        camera_id: cameraId,
        image: canvas.toDataURL("image/jpeg", quality),
      }),
    );

    return true;
  }

  function close() {
    framePending = false;
    if (!socket) return;

    try {
      socket.onclose = null;
      socket.close(1000);
    } catch (_) {
      // Ignora erros ao fechar durante a navegação.
    }

    socket = null;
  }

  function isConnected() {
    return !!socket && socket.readyState === WebSocket.OPEN;
  }

  function endpoint() {
    return httpBase();
  }

  return {
    connect,
    sendFrame,
    close,
    isConnected,
    endpoint,
  };
})();
