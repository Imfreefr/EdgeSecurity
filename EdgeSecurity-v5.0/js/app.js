
(function(){
 const page=document.body.dataset.page;
 const template=document.getElementById('page-template');
 window.__PAGE_BODY__=template?template.innerHTML:'';
 const s=EdgeAuth.require();
 if(!s)return;
 const nav=[
  ["dashboard","bx bx-grid-alt","Dashboard"],
  ["cameras","bx bx-video","Câmeras"],
  ["alertas","bx bx-bell","Sistema de Alertas"],
  ["relatorios","bx bx-bar-chart-alt-2","Relatórios"],
  ["atividades","bx bx-history","Monitor de Atividades"],
  ["configuracoes","bx bx-cog","Configurações"]
 ];
 if(s.cargo==="administrador") nav.splice(2,0,["usuarios","bx bx-group","Usuários e Permissões"]);
 document.getElementById("app").innerHTML=`<div class="app-shell">
 <aside class="sidebar"><div class="sb-logo">Edge<span>Security</span></div><nav class="sb-nav">${nav.map(n=>`<button class="sb-item ${page===n[0]?"active":""}" data-go="${n[0]}"><i class="ico ${n[1]}"></i>${n[2]}</button>`).join("")}</nav>
 <div class="sb-user"><strong>${s.nome}</strong>${s.cargo==="administrador"?"Administrador":"Usuário"}</div><button class="sb-logout" id="logout"><i class="bx bx-log-out ico"></i>Sair</button></aside>
 <main class="content">${document.getElementById("app").innerHTML}</main></div><div id="toast" class="toast"></div>`;
 const content=document.querySelector(".content");
 const original=window.__PAGE_BODY__;
 if(original) content.innerHTML=original;
 document.querySelectorAll("[data-go]").forEach(b=>b.onclick=()=>location.href=b.dataset.go==="dashboard"?"dashboard.html":b.dataset.go+".html");
 document.getElementById("logout").onclick=()=>{EdgeAuth.logout();location.href="../index.html"};
 document.querySelectorAll(".admin-only").forEach(el=>{if(s.cargo!=="administrador")el.remove()});
 window.showToast=function(msg){const t=document.getElementById("toast");t.textContent=msg;t.classList.add("show");setTimeout(()=>t.classList.remove("show"),2500)};
 window.formatDate=function(v){return new Date(v).toLocaleString("pt-BR",{dateStyle:"short",timeStyle:"short"})};
 window.cameraById=id=>EdgeDB.cameras.find(c=>c.id===id);
 document.body.classList.toggle("dark",localStorage.getItem("edge_theme")==="dark");
})();
