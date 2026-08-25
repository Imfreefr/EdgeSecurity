/* Cliente WebSocket da análise YOLO26. O backend executa a inferência. */
window.EdgeAI = (() => {
    function httpBase() {
        const configured = localStorage.getItem('edgesecurity_ai_api') || window.EDGE_API_BASE;
        if (configured) return configured.replace(/\/$/, '');

        // Pelo Tunnel, o WebSocket usa o mesmo hostname HTTPS do frontend.
        if (location.port !== '5500' && location.hostname !== 'localhost' && location.hostname !== '127.0.0.1') {
            return location.origin;
        }

        return `${location.protocol}//${location.hostname || 'localhost'}:8000`;
    }

    let socket = null;

    function connect(cameraId, onResult, onError, onReady) {
        close();

        const base = httpBase();
        const wsBase = base
            .replace(/^http:/, 'ws:')
            .replace(/^https:/, 'wss:')
            .replace(/\/$/, '');

        socket = new WebSocket(`${wsBase}/ws/detection`);

        socket.onopen = () => {};

        socket.onmessage = event => {
            try {
                const data = JSON.parse(event.data);

                if (data.type === 'ready') onReady?.(data);
                else if (data.type === 'result') onResult?.(data);
                else if (data.type === 'error') onError?.(data.message);
            } catch (_) {
                onError?.('Resposta inválida do serviço de IA.');
            }
        };

        socket.onerror = () => onError?.('Não foi possível conectar ao serviço YOLO26.');
        socket.onclose = () => {};
    }

    function sendFrame(canvas, cameraId, quality = 0.65) {
        if (!socket || socket.readyState !== WebSocket.OPEN) return false;

        socket.send(JSON.stringify({
            camera_id: cameraId,
            image: canvas.toDataURL('image/jpeg', quality)
        }));

        return true;
    }

    function close() {
        if (!socket) return;

        try {
            socket.close();
        } catch (_) {
            // Ignore close errors during navigation.
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
        endpoint
    };
})();
