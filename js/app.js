function applyFontSize(size){
  document.documentElement.classList.remove('font-small','font-normal','font-large','font-xlarge');
  document.documentElement.classList.add('font-' + (size || 'normal'));
}
(function(){
const page=document.body.dataset.page;
const template=document.getElementById('page-template');
const original=template?template.innerHTML:'';
const s=EdgeAuth.require();
if(!s)return;
const nav=[['dashboard','bx bx-grid-alt','Dashboard'],['cameras','bx bx-video','Câmeras'],['alertas','bx bx-bell','Sistema de Alertas'],['relatorios','bx bx-bar-chart-alt-2','Relatórios'],['atividades','bx bx-history','Monitor de Atividades'],['configuracoes','bx bx-cog','Configurações']];
if(s.cargo==='administrador')nav.splice(2,0,['usuarios','bx bx-group','Usuários e Permissões']);
document.getElementById('app').innerHTML=`<div class="app-shell"><aside class="sidebar collapsed" id="sidebar"><div class="sb-top" aria-hidden="true"></div><nav class="sb-nav">${nav.map(n=>`<button class="sb-item ${page===n[0]?'active':''}" data-go="${n[0]}" title="${n[2]}" aria-label="${n[2]}"><i class="ico ${n[1]}" aria-hidden="true"></i><span class="sb-label">${n[2]}</span></button>`).join('')}</nav><div class="sb-user"><strong>${escapeHtml(s.nome)}</strong><span>${s.cargo==='administrador'?'Administrador':'Usuário'}</span></div><button class="sb-logout" id="logout" title="Sair" aria-label="Sair"><i class="bx bx-log-out ico" aria-hidden="true"></i><span class="sb-label">Sair</span></button></aside><main class="content">${original}</main></div><div id="toast" class="toast"></div>`;
document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>location.href=b.dataset.go==='dashboard'?'dashboard.html':b.dataset.go+'.html');
const sidebar=document.getElementById('sidebar');
const desktopQuery=window.matchMedia('(min-width: 821px)');
const syncSidebarMode=()=>{
if(desktopQuery.matches){ sidebar.classList.add('auto-hide');
sidebar.classList.remove('collapsed');
}
else { sidebar.classList.remove('auto-hide');
sidebar.classList.remove('collapsed');
}
};
syncSidebarMode();
desktopQuery.addEventListener?.('change',syncSidebarMode);
document.getElementById('logout').onclick=()=>EdgeAuth.logout();
document.querySelectorAll('.admin-only').forEach(el=>{if(s.cargo!=='administrador')el.remove()});
document.body.classList.toggle('dark',localStorage.getItem('edge_theme')==='dark');
applyFontSize(localStorage.getItem('edge_font')||'normal');
// Persist session usage while the page remains open. The backend flushes only the
// unrecorded portion, so repeated heartbeats never double-count the same seconds.
const heartbeat=async()=>{try{await EdgeAPI.post('/auth/heartbeat',{});
}catch(_){} };
heartbeat();
const heartbeatTimer=setInterval(heartbeat,10000);
window.addEventListener('pagehide',()=>clearInterval(heartbeatTimer));
EdgeData.load().catch(e=>showToast(e.message));
})();
