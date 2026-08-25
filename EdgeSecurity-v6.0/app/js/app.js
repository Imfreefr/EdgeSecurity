(function(){
 const page=document.body.dataset.page;
 const template=document.getElementById('page-template');
 const original=template?template.innerHTML:'';
 const s=EdgeAuth.require(); if(!s)return;
 const nav=[['dashboard','bx bx-grid-alt','Dashboard'],['cameras','bx bx-video','Câmeras'],['alertas','bx bx-bell','Sistema de Alertas'],['relatorios','bx bx-bar-chart-alt-2','Relatórios'],['atividades','bx bx-history','Monitor de Atividades'],['configuracoes','bx bx-cog','Configurações']];
 if(s.cargo==='administrador')nav.splice(2,0,['usuarios','bx bx-group','Usuários e Permissões']);
 document.getElementById('app').innerHTML=`<div class="app-shell"><aside class="sidebar"><div class="sb-logo">Edge<span>Security</span></div><nav class="sb-nav">${nav.map(n=>`<button class="sb-item ${page===n[0]?'active':''}" data-go="${n[0]}"><i class="ico ${n[1]}"></i>${n[2]}</button>`).join('')}</nav><div class="sb-user"><strong>${escapeHtml(s.nome)}</strong>${s.cargo==='administrador'?'Administrador':'Usuário'}</div><button class="sb-logout" id="logout"><i class="bx bx-log-out ico"></i>Sair</button></aside><main class="content">${original}</main></div><div id="toast" class="toast"></div>`;
 document.querySelectorAll('[data-go]').forEach(b=>b.onclick=()=>location.href=b.dataset.go==='dashboard'?'dashboard.html':b.dataset.go+'.html');
 document.getElementById('logout').onclick=()=>EdgeAuth.logout();
 document.querySelectorAll('.admin-only').forEach(el=>{if(s.cargo!=='administrador')el.remove()});
 document.body.classList.toggle('dark',localStorage.getItem('edge_theme')==='dark');
 document.body.classList.toggle('large',localStorage.getItem('edge_font')==='large');
 EdgeData.load().catch(e=>showToast(e.message));
})();
