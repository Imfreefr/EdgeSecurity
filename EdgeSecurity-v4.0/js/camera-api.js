/* Camada da API de câmera do navegador (MediaDevices). */
window.CameraAPI = {
  supported() {
    return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && navigator.mediaDevices.enumerateDevices);
  },

  async requestPermission() {
    if (!this.supported()) throw new Error('UNSUPPORTED');
    const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    stream.getTracks().forEach(track => track.stop());
  },

  async list() {
    if (!this.supported()) throw new Error('UNSUPPORTED');
    const devices = await navigator.mediaDevices.enumerateDevices();
    return devices.filter(device => device.kind === 'videoinput');
  },

  async open(deviceId) {
    if (!this.supported()) throw new Error('UNSUPPORTED');
    return navigator.mediaDevices.getUserMedia({
      video: deviceId ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } } : { width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false
    });
  },

  stop(stream) {
    if (stream) stream.getTracks().forEach(track => track.stop());
  }
};
