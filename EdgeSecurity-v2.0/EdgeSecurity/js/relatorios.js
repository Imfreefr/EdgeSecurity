function emptyChart(canvas, message) {
  const ctx = canvas.getContext('2d');
  const dpr = devicePixelRatio || 1;
  const w = canvas.clientWidth || 400;
  const h = canvas.clientHeight || 240;
  canvas.width = w * dpr; canvas.height = h * dpr; ctx.scale(dpr, dpr);
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = getComputedStyle(document.body).getPropertyValue('--muted') || '#64748b';
  ctx.font = '14px Inter'; ctx.textAlign = 'center';
  ctx.fillText(message, w / 2, h / 2);
}

function drawBarChart(canvas, labels, values) {
  if (!values.length || values.every(v => v === 0)) { emptyChart(canvas, 'Sem dados para exibir'); return; }
  const ctx = canvas.getContext('2d'), dpr = devicePixelRatio || 1;
  const w = canvas.clientWidth, h = canvas.clientHeight;
  canvas.width = w * dpr; canvas.height = h * dpr; ctx.scale(dpr, dpr); ctx.clearRect(0, 0, w, h);
  const max = Math.max(...values, 1), pad = 35, bottom = h - 30, step = (w - pad * 2) / values.length, barW = Math.min(46, step * .55);
  values.forEach((v, i) => {
    const bh = (v / max) * (h - 65), x = pad + i * step + (step - barW) / 2, y = bottom - bh;
    ctx.fillStyle = '#2f6fed'; ctx.fillRect(x, y, barW, bh);
    ctx.fillStyle = '#64748b'; ctx.font = '11px Inter'; ctx.textAlign = 'center'; ctx.fillText(labels[i], x + barW / 2, h - 10);
    ctx.fillStyle = '#0f172a'; ctx.fillText(v, x + barW / 2, y - 6);
  });
}

function renderReport() {
  const totalC = EdgeDB.cameras.length;
  const active = EdgeDB.cameras.filter(c => c.status === 'online').length;
  const users = EdgeDB.users.length;
  const activeUsers = EdgeDB.users.filter(u => u.status === 'ativo').length;
  const online = EdgeDB.users.filter(u => u.status === 'ativo' && u.ultimo_login && !u.ultimo_logout).length;
  const alerts = EdgeDB.alerts.length;
  const open = EdgeDB.alerts.filter(a => a.status === 'Aberto').length;
  const totalSeconds = EdgeDB.users.reduce((n, u) => n + Number(u.tempo_total_ativo || 0), 0);

  document.getElementById('report-stats').innerHTML = [
    ['Câmeras cadastradas', totalC], ['Câmeras ativas', active], ['Usuários cadastrados', users], ['Usuários ativos', activeUsers],
    ['Usuários online', online], ['Alertas registrados', alerts], ['Alertas abertos', open], ['Tempo total', `${(totalSeconds / 3600).toFixed(1)} h`]
  ].map(x => `<div class="stat"><div class="label">${x[0]}</div><div class="value">${x[1]}</div><div class="hint">${x[1] === 0 ? 'Sem dados cadastrados' : 'Dados registrados no sistema'}</div></div>`).join('');

  drawBarChart(document.getElementById('usage-chart'), EdgeDB.usage.map(x => x.label), EdgeDB.usage.map(x => x.hours));
  const levels = ['Crítico', 'Alto', 'Normal'];
  drawBarChart(document.getElementById('alert-chart'), levels, levels.map(l => EdgeDB.alerts.filter(a => a.nivel === l).length));
}

document.getElementById('apply-report').onclick = () => { renderReport(); showToast('Filtros aplicados.'); };
document.getElementById('export-report').onclick = () => {
  const report = { generatedAt: new Date().toISOString(), users: EdgeDB.users, cameras: EdgeDB.cameras, alerts: EdgeDB.alerts, activities: EdgeDB.activities, usage: EdgeDB.usage };
  const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' });
  const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'edgesecurity-relatorio.json'; a.click(); URL.revokeObjectURL(a.href);
};
renderReport(); window.addEventListener('resize', renderReport);
