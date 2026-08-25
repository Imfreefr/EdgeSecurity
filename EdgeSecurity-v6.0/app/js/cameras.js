(() => {
  const video = document.getElementById('camera-video');
  const canvas = document.getElementById('ai-overlay');
  const ctx = canvas.getContext('2d');
  const select = document.getElementById('camera-select');
  const start = document.getElementById('start-camera');
  const stop = document.getElementById('stop-camera');
  const detect = document.getElementById('detect-cameras');
  const register = document.getElementById('register-camera');
  const registeredList = document.getElementById('registered-cameras');
  const startAI = document.getElementById('start-ai');
  const stopAIButton = document.getElementById('stop-ai');
  const empty = document.getElementById('camera-empty');
  const label = document.getElementById('camera-device-label');
  const status = document.getElementById('camera-live-status');
  const aiStatus = document.getElementById('ai-status');
  const list = document.getElementById('device-list');
  const cameraError = document.getElementById('camera-error');
  const humanCount = document.getElementById('ai-human-count');
  const machineCount = document.getElementById('ai-machine-count');
  const riskLevel = document.getElementById('ai-risk-level');
  let stream = null, devices = [], aiRunning = false, frameTimer = null;

  function currentUser(){ const s=EdgeAuth.current(); return s ? EdgeDB.users.find(u=>u.id===s.id) : null; }
  function canUseCamera(){ const u=currentUser(); return !!u && (u.cargo==='administrador' || u.permissoes?.usar_camera_dispositivo !== false); }
  function canRegisterCamera(){ const u=currentUser(); return !!u && (u.cargo==='administrador' || u.permissoes?.gerenciar_cameras === true); }
  function registeredCameras(){ return Array.isArray(EdgeDB.cameras) ? EdgeDB.cameras : []; }
  function setCameraError(message='') {
    if (!cameraError) return;
    cameraError.textContent = message;
    cameraError.hidden = !message;
  }
  function explainCameraError(err) {
    const messages = {
      NotAllowedError: 'O navegador bloqueou a câmera. Clique no cadeado/permissão da barra de endereço e permita o acesso à câmera. Depois recarregue a página.',
      PermissionDeniedError: 'O acesso à câmera foi negado pelo navegador. Libere a permissão da câmera para este endereço e tente novamente.',
      NotFoundError: 'Nenhuma câmera foi encontrada neste dispositivo. Conecte uma webcam ou verifique se a câmera está habilitada no sistema.',
      NotReadableError: 'A câmera foi encontrada, mas está ocupada por outro aplicativo. Feche aplicativos que estejam usando a webcam e tente novamente.',
      OverconstrainedError: 'A câmera selecionada não aceitou as configurações solicitadas. O sistema tentará novamente com configurações básicas.',
      SecurityError: 'O navegador bloqueou o acesso por segurança. Abra o sistema por localhost ou HTTPS.',
      AbortError: 'O acesso à câmera foi interrompido. Tente novamente.',
      UNSUPPORTED: CameraAPI.supportError()
    };
    return messages[err?.name] || `Não foi possível acessar a câmera${err?.name ? ` (${err.name})` : ''}.`;
  }

  function renderRegistered(){
    const items=registeredCameras();
    if(!items.length){ registeredList.innerHTML='<div class="empty-state">Nenhuma câmera cadastrada.</div>'; return; }
    registeredList.innerHTML=items.map(c=>`<div class="device-row"><span><strong>${escapeHtml(c.nome)}</strong><small>${escapeHtml(c.tipo||'dispositivo')} · ${escapeHtml(c.status||'ativo')}</small></span><button class="btn btn-secondary btn-small" data-registered="${escapeHtml(c.id)}">Selecionar</button></div>`).join('');
    registeredList.querySelectorAll('[data-registered]').forEach(btn=>btn.onclick=()=>{ const c=registeredCameras().find(x=>x.id===btn.dataset.registered); if(c?.device_id){ select.value=c.device_id; startCamera(c.device_id); } });
  }

  async function registerSelected(){
    const u=currentUser();
    if(!u){showToast('Sessão inválida.');return;}
    if(!canRegisterCamera()){showToast('Você não possui permissão para cadastrar câmeras.');return;}
    const d=devices.find(x=>x.deviceId===select.value);
    if(!d){showToast('Detecte e selecione uma câmera antes de cadastrar.');return;}
    const existing=registeredCameras().find(c=>c.device_id===d.deviceId);
    if(existing){showToast('Esta câmera já está cadastrada.');return;}
    try { await EdgeAPI.post('/cameras',{nome:d.label||'Câmera do dispositivo',tipo:'browser',device_id:d.deviceId,status:'ativo'}); await EdgeData.load(); renderRegistered(); showToast('Câmera cadastrada com sucesso.'); } catch(err) { showToast(err.message); }
  }

  function setStatus(text, live = false) { status.textContent = text; status.classList.toggle('live', live); }
  function setAIStatus(text, live = false) { aiStatus.textContent = text; aiStatus.classList.toggle('live', live); }

  function drawResults(data) {
    if (!video.videoWidth) return;
    canvas.width = video.videoWidth; canvas.height = video.videoHeight;
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    const risk = data.risk?.level || 'safe';
    const line = risk === 'critical' ? 6 : risk === 'high' ? 5 : 3;
    (data.detections || []).forEach(d => {
      const [x1,y1,x2,y2] = d.bbox;
      ctx.lineWidth = line;
      ctx.strokeStyle = d.class_name === 'human' ? '#22c55e' : d.class_name === 'machine' ? '#f59e0b' : '#60a5fa';
      ctx.strokeRect(x1,y1,x2-x1,y2-y1);
      ctx.font = 'bold 16px Inter, sans-serif';
      const text = `${d.label} ${(d.confidence*100).toFixed(0)}%${d.track_id != null ? ` #${d.track_id}` : ''}`;
      ctx.fillStyle = ctx.strokeStyle; ctx.fillRect(x1, Math.max(0,y1-24), ctx.measureText(text).width+10, 24);
      ctx.fillStyle = '#08111f'; ctx.fillText(text, x1+5, Math.max(17,y1-6));
    });
    humanCount.textContent = (data.detections || []).filter(d=>d.class_name==='human').length;
    machineCount.textContent = (data.detections || []).filter(d=>d.class_name==='machine').length;
    riskLevel.textContent = ({safe:'Seguro',medium:'Atenção',high:'Alto',critical:'CRÍTICO'})[risk] || risk;
    riskLevel.dataset.level = risk;
  }

  function stopAIAnalysis() {
    aiRunning = false; if (frameTimer) clearInterval(frameTimer); frameTimer = null; EdgeAI.close();
    ctx.clearRect(0,0,canvas.width,canvas.height); startAI.disabled = !stream; stopAIButton.disabled = true;
    setAIStatus('IA desligada'); humanCount.textContent='0'; machineCount.textContent='0'; riskLevel.textContent='—'; riskLevel.dataset.level='';
  }

  function startAnalysis() {
    if (!stream) { showToast('Inicie uma câmera antes da análise.'); return; }
    const registered = registeredCameras().find(c=>c.device_id===select.value);
    if(!registered){ showToast('Cadastre esta câmera antes de iniciar a análise.'); return; }
    const cameraId = registered.id;
    setAIStatus('Conectando à IA…');
    EdgeAI.connect(cameraId, drawResults, msg => { stopAIAnalysis(); showToast(msg); setAIStatus('Erro na IA'); }, () => {
      aiRunning = true; setAIStatus('YOLO26 AO VIVO', true); startAI.disabled=true; stopAIButton.disabled=false;
      const frameCanvas = document.createElement('canvas');
      const interval = Math.max(100, Math.round(1000 / 8));
      frameTimer = setInterval(() => {
        if (!aiRunning || !video.videoWidth) return;
        frameCanvas.width = 640; frameCanvas.height = Math.round(video.videoHeight * (640/video.videoWidth));
        frameCanvas.getContext('2d').drawImage(video,0,0,frameCanvas.width,frameCanvas.height);
        EdgeAI.sendFrame(frameCanvas,cameraId,0.62);
      }, interval);
    });
  }

  function stopCamera() {
    stopAIAnalysis(); CameraAPI.stop(stream); stream=null; video.srcObject=null; video.style.display='none'; canvas.style.display='none'; empty.style.display='flex'; stop.disabled=true; startAI.disabled=true;
    setStatus('Sem transmissão'); label.textContent='Nenhuma câmera selecionada';
  }

  async function startCamera(deviceId) {
    setCameraError('');
    if (!CameraAPI.supported()) { setCameraError(CameraAPI.supportError()); showToast('Acesse o sistema por localhost ou HTTPS.'); return; }
    if (!canUseCamera()) { setCameraError('Sua conta não possui permissão para usar a câmera deste dispositivo.'); return; }
    try {
      stopAIAnalysis(); CameraAPI.stop(stream); stream=await CameraAPI.open(deviceId); video.srcObject=stream; await video.play(); video.style.display='block'; canvas.style.display='block'; empty.style.display='none'; stop.disabled=false; startAI.disabled=false; setStatus('AO VIVO',true);
      const track=stream.getVideoTracks()[0], currentId=track.getSettings().deviceId, current=devices.find(d=>d.deviceId===currentId); if(current){select.value=current.deviceId; label.textContent=current.label||'Câmera selecionada';}
      await refreshDevices();
      setCameraError('');
    } catch(err) {
      const message = explainCameraError(err);
      setCameraError(message);
      showToast(message);
      stopCamera();
    }
  }

  async function refreshDevices() {
    try {
      devices=await CameraAPI.list();
      select.innerHTML='';
      if(!devices.length){
        select.disabled=true;select.innerHTML='<option>Nenhuma câmera detectada</option>';
        list.innerHTML='<div class="empty-state">Nenhuma câmera foi disponibilizada pelo dispositivo ou navegador.</div>';
        register.disabled=true;
        return;
      }
      devices.forEach((d,i)=>{const o=document.createElement('option');o.value=d.deviceId;o.textContent=d.label||`Câmera ${i+1}`;select.appendChild(o);});
      select.disabled=false; register.disabled=!canRegisterCamera();
      list.innerHTML=devices.map((d,i)=>`<div class="device-row"><span><strong>${escapeHtml(d.label||`Câmera ${i+1}`)}</strong><small>Dispositivo de vídeo detectado pelo navegador</small></span><button class="btn btn-secondary btn-small" data-device="${escapeHtml(d.deviceId)}">Usar</button></div>`).join('');
      list.querySelectorAll('[data-device]').forEach(btn=>btn.onclick=()=>{select.value=btn.dataset.device;startCamera(btn.dataset.device);});
    } catch(err){
      if(err?.name==='UNSUPPORTED'){ setCameraError(CameraAPI.supportError()); list.innerHTML='<div class="empty-state">O navegador só disponibiliza câmeras em localhost ou HTTPS.</div>'; }
      else { setCameraError(explainCameraError(err)); }
      register.disabled=true;
    }
  }

  async function detectCameras(){
    setCameraError('');
    if(!CameraAPI.supported()){ setCameraError(CameraAPI.supportError()); showToast('Abra o EdgeSecurity por localhost ou HTTPS.'); return; }
    if(!canUseCamera()){ setCameraError('Sua conta não possui permissão para usar a câmera deste dispositivo.'); return; }
    try {
      detect.disabled=true; detect.textContent='Solicitando permissão…';
      await CameraAPI.requestPermission();
      await refreshDevices();
      if(devices.length){
        showToast(`${devices.length} câmera(s) detectada(s).`);
        if (!select.value) select.value = devices[0].deviceId;
      } else {
        setCameraError('A permissão foi concedida, mas o navegador não encontrou nenhum dispositivo de vídeo.');
      }
    } catch(err){
      setCameraError(explainCameraError(err));
      showToast(explainCameraError(err));
    } finally {
      detect.disabled=false; detect.textContent='Detectar câmeras';
    }
  }

  function escapeHtml(v){return String(v).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}

  function initializeCameraPage(){ renderRegistered(); register.disabled=true;
    if(!canUseCamera()){ start.disabled=true; detect.disabled=true; setCameraError('Sua conta não possui permissão para usar a câmera deste dispositivo.'); }
    register.onclick=registerSelected;
    detect.onclick=detectCameras;
    start.onclick=()=>startCamera(select.value||undefined);
    stop.onclick=stopCamera;
    startAI.onclick=startAnalysis;
    stopAIButton.onclick=stopAIAnalysis;
    select.onchange=()=>startCamera(select.value);
    window.addEventListener('beforeunload',stopCamera);
    if(navigator.mediaDevices?.addEventListener) navigator.mediaDevices.addEventListener('devicechange',refreshDevices);
    refreshDevices();
  }
  window.addEventListener('edge-data-ready', initializeCameraPage);
})();
