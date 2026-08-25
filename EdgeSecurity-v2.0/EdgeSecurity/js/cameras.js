(() => {
  const video = document.getElementById('camera-video');
  const select = document.getElementById('camera-select');
  const start = document.getElementById('start-camera');
  const stop = document.getElementById('stop-camera');
  const detect = document.getElementById('detect-cameras');
  const empty = document.getElementById('camera-empty');
  const label = document.getElementById('camera-device-label');
  const status = document.getElementById('camera-live-status');
  const list = document.getElementById('device-list');
  let stream = null;
  let devices = [];

  function setStatus(text, live = false) {
    status.textContent = text;
    status.classList.toggle('live', live);
  }

  function stopCamera() {
    CameraAPI.stop(stream);
    stream = null;
    video.srcObject = null;
    video.style.display = 'none';
    empty.style.display = 'flex';
    stop.disabled = true;
    setStatus('Sem transmissão');
    label.textContent = select.value && select.value !== 'Nenhuma câmera detectada' ? select.options[select.selectedIndex].text : 'Nenhuma câmera selecionada';
  }

  async function startCamera(deviceId) {
    if (!CameraAPI.supported()) {
      showToast('Este navegador ou contexto não permite acesso à câmera. Use HTTPS ou localhost.');
      return;
    }

    try {
      CameraAPI.stop(stream);
      stream = await CameraAPI.open(deviceId);
      video.srcObject = stream;
      video.style.display = 'block';
      empty.style.display = 'none';
      stop.disabled = false;
      setStatus('AO VIVO', true);

      const track = stream.getVideoTracks()[0];
      const currentId = track.getSettings().deviceId;
      const current = devices.find(d => d.deviceId === currentId);
      if (current) {
        select.value = current.deviceId;
        label.textContent = current.label || 'Câmera selecionada';
      }
      await refreshDevices();
    } catch (err) {
      const messages = {
        NotAllowedError: 'A permissão da câmera foi negada.',
        NotFoundError: 'Nenhuma câmera compatível foi encontrada.',
        NotReadableError: 'A câmera está ocupada ou não pôde ser acessada.',
        OverconstrainedError: 'A câmera selecionada não está disponível.'
      };
      showToast(messages[err.name] || `Não foi possível acessar a câmera (${err.name}).`);
    }
  }

  async function refreshDevices() {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    try {
      devices = await CameraAPI.list();
      select.innerHTML = '';

      if (!devices.length) {
        select.disabled = true;
        select.innerHTML = '<option>Nenhuma câmera detectada</option>';
        list.textContent = 'Nenhuma câmera foi disponibilizada pelo dispositivo ou pelo navegador.';
        return;
      }

      devices.forEach((device, index) => {
        const option = document.createElement('option');
        option.value = device.deviceId;
        option.textContent = device.label || `Câmera ${index + 1}`;
        select.appendChild(option);
      });
      select.disabled = false;
      list.innerHTML = devices.map((d, i) => `<div class="device-row"><span><strong>${escapeHtml(d.label || `Câmera ${i + 1}`)}</strong><small>Dispositivo de vídeo detectado pelo navegador</small></span><button class="btn btn-secondary btn-small" data-device="${escapeHtml(d.deviceId)}">Usar</button></div>`).join('');
      list.querySelectorAll('[data-device]').forEach(btn => btn.onclick = () => { select.value = btn.dataset.device; startCamera(btn.dataset.device); });
    } catch (_) {
      showToast('Não foi possível listar os dispositivos de câmera.');
    }
  }

  async function detectCameras() {
    if (!CameraAPI.supported()) {
      showToast('A API de câmera não está disponível. Use HTTPS ou localhost.');
      return;
    }
    try {
      // A permissão é necessária para que o navegador revele as câmeras disponíveis e seus nomes.
      await CameraAPI.requestPermission();
      await refreshDevices();
      if (devices.length) showToast(`${devices.length} câmera(s) detectada(s).`);
    } catch (err) {
      const messages = { NotAllowedError: 'Permissão de câmera negada.', NotFoundError: 'Nenhuma câmera encontrada.', NotReadableError: 'A câmera não pôde ser acessada.' };
      showToast(messages[err.name] || 'Não foi possível acessar a câmera.');
    }
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>'"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c]));
  }

  detect.onclick = detectCameras;
  start.onclick = () => startCamera(select.value || undefined);
  stop.onclick = stopCamera;
  select.onchange = () => startCamera(select.value);
  window.addEventListener('beforeunload', stopCamera);
  if (navigator.mediaDevices?.addEventListener) navigator.mediaDevices.addEventListener('devicechange', refreshDevices);

  refreshDevices();
})();
