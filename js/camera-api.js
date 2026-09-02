/* Acesso às câmeras do dispositivo pelo navegador (MediaDevices). */
window.CameraAPI = {
isLocalhost() {
return ['localhost', '127.0.0.1', '[::1]'].includes(location.hostname);
},
secureContext() {
return window.isSecureContext === true || this.isLocalhost();
},
supported() {
return this.secureContext() && !!(
navigator.mediaDevices &&
navigator.mediaDevices.getUserMedia &&
navigator.mediaDevices.enumerateDevices
);
},
supportError() {
if (!this.secureContext()) {
return 'A câmera do navegador exige um contexto seguro. Abra o EdgeSecurity por http://localhost:5500 (não abra o arquivo HTML diretamente).';
}
if (!navigator.mediaDevices?.getUserMedia) {
return 'Este navegador não disponibilizou a API de câmera. Verifique as permissões do site e use uma versão atualizada do navegador.';
}
return '';
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
const preferred = deviceId
? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
: { width: { ideal: 1280 }, height: { ideal: 720 } };
try {
return await navigator.mediaDevices.getUserMedia({ video: preferred, audio: false });
} catch (error) {
/* Algumas webcams recusam constraints de resolução/deviceId. Tenta a configuração mínima. */
if (error.name === 'OverconstrainedError' || error.name === 'NotFoundError') {
return navigator.mediaDevices.getUserMedia({ video: deviceId ? { deviceId: { exact: deviceId } } : true, audio: false });
}
throw error;
}
},
stop(stream) {
if (stream) stream.getTracks().forEach(track => track.stop());
}
};
