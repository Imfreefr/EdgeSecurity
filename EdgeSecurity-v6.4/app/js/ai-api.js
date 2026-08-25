/* Cliente WebSocket da análise YOLO26. O backend executa a inferência; o navegador apenas captura e envia frames. */
window.EdgeAI = (() => {
const defaultHttp = location.protocol === 'https:' ? 'https://' + location.hostname + ':8000' : 'http://' + (location.hostname || 'localhost') + ':8000';
const configured = localStorage.getItem('edgesecurity_ai_api') || defaultHttp;
const wsBase = configured.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:').replace(/\/$/, '');
let socket = null;
function connect(cameraId, onResult, onError, onReady) {
close();
socket = new WebSocket(`${wsBase}/ws/detection`);
socket.onopen = () => {};
socket.onmessage = event => {
try {
const data = JSON.parse(event.data);
if (data.type === 'ready') onReady?.(data);
else if (data.type === 'result') onResult?.(data);
else if (data.type === 'error') onError?.(data.message);
} catch (_) { onError?.('Resposta inválida do serviço de IA.');
}
};
socket.onerror = () => onError?.('Não foi possível conectar ao serviço YOLO26.');
socket.onclose = () => {};
}
function sendFrame(canvas, cameraId, quality = 0.65) {
if (!socket || socket.readyState !== WebSocket.OPEN) return false;
socket.send(JSON.stringify({ camera_id: cameraId, image: canvas.toDataURL('image/jpeg', quality) }));
return true;
}
function close() { if (socket) { try { socket.close();
} catch (_) {} socket = null;
} }
function isConnected() { return !!socket && socket.readyState === WebSocket.OPEN;
}
function endpoint() { return configured;
}
return { connect, sendFrame, close, isConnected, endpoint };
})();
