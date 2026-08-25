const session = EdgeAuth.current();
const visibleCams = EdgeDB.cameras.filter(c => session.cargo === 'administrador' || (EdgeDB.users.find(u => u.id === session.id)?.cameras || []).includes(c.id));
const visibleAlerts = EdgeDB.alerts.filter(a => session.cargo === 'administrador' || visibleCams.some(c => c.id === a.camera_id));

const stats = [
  ['Câmeras disponíveis', visibleCams.length, 'Cadastradas no sistema'],
  ['Câmeras ativas', visibleCams.filter(c => c.status === 'online').length, 'Sem dados se nenhuma foi cadastrada'],
  ['Usuários online', EdgeDB.users.filter(u => u.status === 'ativo' && u.ultimo_login && !u.ultimo_logout).length, 'Sessões registradas'],
  ['Alertas abertos', visibleAlerts.filter(a => a.status === 'Aberto').length, 'Eventos registrados']
];

document.getElementById('dashboard-stats').innerHTML = stats.map(x => `<div class="stat"><div class="label">${x[0]}</div><div class="value">${x[1]}</div><div class="hint">${x[2]}</div></div>`).join('');

document.getElementById('camera-name').textContent = visibleCams[0]?.nome || 'Nenhuma câmera cadastrada';
document.getElementById('camera-location').textContent = visibleCams[0]?.localizacao || 'Adicione uma câmera para iniciar o monitoramento';
document.getElementById('camera-status').textContent = visibleCams[0] ? (visibleCams[0].status === 'online' ? 'Disponível' : 'Offline') : 'Sem dispositivo cadastrado';
document.querySelector('.live').style.display = visibleCams[0]?.status === 'online' ? '' : 'none';
document.getElementById('dashboard-camera-btn').onclick = () => location.href = 'cameras.html';

document.getElementById('recent-alerts').innerHTML = visibleAlerts.length
  ? visibleAlerts.slice(0, 4).map(a => `<div class="list-item"><div><strong>${a.tipo}</strong><br><span>${cameraById(a.camera_id)?.nome || '—'} · ${formatDate(a.data_hora)}</span></div><span class="level ${a.nivel === 'Crítico' ? 'critical' : a.nivel === 'Alto' ? 'high' : 'normal'}">${a.nivel}</span></div>`).join('')
  : '<div class="empty-state">Nenhum alerta registrado.</div>';

document.getElementById('recent-activities').innerHTML = EdgeDB.activities.length
  ? `<table><thead><tr><th>Usuário</th><th>Ação</th><th>Descrição</th><th>Data</th></tr></thead><tbody>${EdgeDB.activities.slice(0, 6).map(a => { const u = EdgeDB.users.find(x => x.id === a.usuario_id); return `<tr><td>${u?.nome || '—'}</td><td>${a.acao}</td><td>${a.descricao}</td><td>${formatDate(a.data_hora)}</td></tr>`; }).join('')}</tbody></table>`
  : '<div class="empty-state">Nenhuma atividade registrada.</div>';
