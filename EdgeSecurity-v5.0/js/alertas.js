
const session=EdgeAuth.current();
const camSelect=document.getElementById("alert-camera");
EdgeDB.cameras.filter(c=>session.cargo==="administrador"||EdgeDB.users.find(u=>u.id===session.id)?.cameras.includes(c.id)).forEach(c=>camSelect.insertAdjacentHTML("beforeend",`<option value="${c.id}">${c.nome}</option>`));
function renderAlerts(){
 const cam=camSelect.value, level=document.getElementById("alert-level").value,status=document.getElementById("alert-status").value,date=document.getElementById("alert-date").value;
 let data=EdgeDB.alerts.filter(a=>(!cam||String(a.camera_id)===cam)&&(!level||a.nivel===level)&&(!status||a.status===status)&&(!date||a.data_hora.startsWith(date)));
 document.getElementById("alerts-table").innerHTML=`<table><thead><tr><th>Data</th><th>Câmera</th><th>Tipo</th><th>Descrição</th><th>Nível</th><th>Status</th></tr></thead><tbody>${data.map(a=>`<tr><td>${formatDate(a.data_hora)}</td><td>${cameraById(a.camera_id)?.nome||"—"}</td><td>${a.tipo}</td><td>${a.descricao}</td><td><span class="level ${a.nivel==="Crítico"?"critical":a.nivel==="Alto"?"high":"normal"}">${a.nivel}</span></td><td><span class="badge ${a.status==="Aberto"?"red":"green"}">${a.status}</span></td></tr>`).join("")||`<tr><td colspan="6"><div class="empty">Nenhum alerta encontrado.</div></td></tr>`}</tbody></table>`;
}
document.querySelectorAll("#alert-camera,#alert-level,#alert-status,#alert-date").forEach(e=>e.addEventListener("change",renderAlerts));renderAlerts();
