const s=EdgeAuth.current();
if(!s){ location.href='../index.html'; }
else if(s.cargo!=='super_admin'){ location.href='dashboard.html'; }
if(s) document.getElementById('admin-user').textContent=s.nome+' — '+s.email;
let adminData=null;
async function loadAdmin(){
  try{
    const dash=await EdgeAPI.get('/admin/dashboard');
    document.getElementById('admin-stats').innerHTML=[
      ['Empresas',dash.total_companies,'Total cadastradas'],
      ['Ativas',dash.ativas,'Empresas ativas'],
      ['Assinaturas ativas',dash.subs_ativas,'Pagando'],
      ['Receita 30d', 'R$ '+Number(dash.receita_mensal).toFixed(2).replace('.',','),'Pagamentos pagos'],
      ['Pendentes',dash.subs_pendentes,'Aguardando pgto'],
      ['Atrasadas',dash.subs_atrasadas,'Vencidas'],
      ['Canceladas',dash.subs_canceladas,'Canceladas'],
      ['Bloqueadas',dash.bloqueadas,'Empresas bloqueadas'],
    ].map(x=>`<div class="stat"><div class="label">${x[0]}</div><div class="value">${x[1]}</div><div class="hint">${x[2]}</div></div>`).join('');
    document.getElementById('admin-payments').innerHTML=dash.pagamentos_recentes.length?`<table><thead><tr><th>Empresa</th><th>Valor</th><th>Status</th><th>Data</th></tr></thead><tbody>${dash.pagamentos_recentes.map(p=>`<tr><td>${escapeHtml(p.nome_fantasia)}</td><td>R$ ${Number(p.valor).toFixed(2)}</td><td><span class="badge ${p.status==='pago'?'green':p.status==='pendente'?'amber':'red'}">${escapeHtml(p.status)}</span></td><td>${formatDate(p.criado_em)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">Nenhum pagamento.</div>';
  }catch(e){ showToastSafe(e.message); }
  await searchCompanies();
}
async function searchCompanies(){
  const q=document.getElementById('admin-q').value.trim();
  const status=document.getElementById('admin-status').value;
  const sub=document.getElementById('admin-sub').value;
  const params=new URLSearchParams();
  if(q) params.set('q',q);
  if(status) params.set('status',status);
  if(sub) params.set('sub_status',sub);
  try{
    const rows=await EdgeAPI.get('/admin/companies?'+params.toString());
    document.getElementById('admin-companies').innerHTML=rows.length?`<table><thead><tr><th>Empresa</th><th>CNPJ</th><th>Admin</th><th>E-mail</th><th>Empresa</th><th>Assinatura</th><th>Vencimento</th><th>Ações</th></tr></thead><tbody>${rows.map(r=>`<tr><td>${escapeHtml(r.nome_fantasia)}</td><td>${escapeHtml(r.cnpj)}</td><td>${escapeHtml(r.admin_nome||'—')}</td><td>${escapeHtml(r.admin_email||'—')}</td><td><span class="badge ${r.status==='ativa'?'green':'red'}">${escapeHtml(r.status)}</span></td><td><span class="badge ${r.sub_status==='ativa'?'green':r.sub_status==='pendente'?'amber':'red'}">${escapeHtml(r.sub_status||'—')}</span> R$ ${r.valor?Number(r.valor).toFixed(2):'—'}</td><td>${r.proximo_vencimento?formatDate(r.proximo_vencimento):'—'}</td><td><button class="btn btn-secondary btn-small" onclick="openCompany('${escapeHtml(r.id)}')">Detalhes</button></td></tr>`).join('')}</tbody></table>`:'<div class="empty">Nenhuma empresa encontrada.</div>';
  }catch(e){ showToastSafe(e.message); }
}
window.openCompany=async(id)=>{
  try{
    const d=await EdgeAPI.get('/admin/companies/'+id);
    const m=document.getElementById('admin-modal'); m.className='modal';
    const c=d.company, sub=d.subscription;
    m.innerHTML=`<div class="modal-box" style="max-width:760px;max-height:90vh;overflow:auto">
      <div class="card-head"><div><h2>${escapeHtml(c.nome_fantasia)}</h2><p>${escapeHtml(c.razao_social)} • ${escapeHtml(c.cnpj)}</p></div><button class="btn btn-secondary" onclick="closeAdminModal()">Fechar</button></div>
      <div style="display:grid;gap:14px">
        <div class="card" style="padding:14px">
          <h3 style="font-size:.85rem;font-weight:700">Dados cadastrais</h3>
          <p style="font-size:.78rem;color:#475569;margin-top:6px">${escapeHtml(c.email)} • ${escapeHtml(c.telefone||'')} • ${escapeHtml(c.cidade||'')} ${escapeHtml(c.estado||'')} • ${escapeHtml(c.endereco||'')}</p>
          <p style="font-size:.78rem;margin-top:8px"><b>Admin:</b> ${d.admin?escapeHtml(d.admin.nome)+' — '+escapeHtml(d.admin.email):'—'} • <b>Usuários:</b> ${d.total_users} • <b>Cadastro:</b> ${formatDate(c.criado_em)}</p>
          <div style="margin-top:10px;display:flex;gap:8px;flex-wrap:wrap">
            <button class="btn btn-secondary btn-small" onclick="toggleCompany('${c.id}','${c.status==='ativa'?'bloqueada':'ativa'}')">${c.status==='ativa'?'Bloquear empresa':'Ativar empresa'}</button>
          </div>
        </div>
        <div class="card" style="padding:14px">
          <h3 style="font-size:.85rem;font-weight:700">Assinatura</h3>
          ${sub?`<p style="font-size:.78rem;margin-top:6px"><b>Status:</b> <span class="badge ${sub.status==='ativa'?'green':sub.status==='pendente'?'amber':'red'}">${escapeHtml(sub.status)}</span> • <b>Valor:</b> R$ ${Number(sub.valor).toFixed(2)} • <b>Início:</b> ${sub.data_inicio?formatDate(sub.data_inicio):'—'} • <b>Último pgto:</b> ${sub.ultimo_pagamento?formatDate(sub.ultimo_pagamento):'—'} • <b>Próximo:</b> ${sub.proximo_vencimento?formatDate(sub.proximo_vencimento):'—'}</p><div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">${['pendente','ativa','atrasada','cancelada','bloqueada'].map(st=>`<button class="btn ${sub.status===st?'btn-primary':'btn-secondary'} btn-small" onclick="setSub('${sub.id}','${st}')">${st}</button>`).join('')}</div>`:'<p style="font-size:.78rem;color:#64748b">Sem assinatura.</p>'}
        </div>
        <div class="card" style="padding:14px">
          <h3 style="font-size:.85rem;font-weight:700">Pagamentos</h3>
          ${d.payments.length?`<table><thead><tr><th>Valor</th><th>Status</th><th>Transação</th><th>Data</th></tr></thead><tbody>${d.payments.map(p=>`<tr><td>R$ ${Number(p.valor).toFixed(2)}</td><td><span class="badge ${p.status==='pago'?'green':'amber'}">${escapeHtml(p.status)}</span></td><td style="font-family:monospace;font-size:.7rem">${escapeHtml(p.transacao_id||'')}</td><td>${formatDate(p.criado_em)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">Nenhum pagamento.</div>'}
        </div>
        <div class="card" style="padding:14px">
          <h3 style="font-size:.85rem;font-weight:700">Usuários (${d.users.length})</h3>
          <div style="max-height:160px;overflow:auto;margin-top:8px"><table><thead><tr><th>Nome</th><th>E-mail</th><th>Cargo</th><th>Status</th></tr></thead><tbody>${d.users.map(u=>`<tr><td>${escapeHtml(u.nome)}</td><td>${escapeHtml(u.email)}</td><td>${escapeHtml(u.cargo)}</td><td><span class="badge ${u.status==='ativo'?'green':'red'}">${escapeHtml(u.status)}</span></td></tr>`).join('')}</tbody></table></div>
        </div>
        <div class="card" style="padding:14px">
          <h3 style="font-size:.85rem;font-weight:700">Auditoria recente</h3>
          ${d.logs.length?`<table><thead><tr><th>Ação</th><th>Descrição</th><th>Data</th></tr></thead><tbody>${d.logs.map(l=>`<tr><td>${escapeHtml(l.acao)}</td><td>${escapeHtml(l.descricao)}</td><td>${formatDate(l.data_hora)}</td></tr>`).join('')}</tbody></table>`:'<div class="empty">Sem logs.</div>'}
        </div>
      </div>
    </div>`;
  }catch(e){ showToastSafe(e.message); }
};
window.closeAdminModal=()=>{ document.getElementById('admin-modal').className='modal hidden'; };
window.toggleCompany=async(id,status)=>{
  try{ await EdgeAPI.request('/admin/companies/'+id+'/status',{method:'PATCH',body:JSON.stringify({status})}); closeAdminModal(); await loadAdmin(); showToastSafe('Empresa '+status+'.'); }catch(e){ showToastSafe(e.message); }
};
window.setSub=async(sid,status)=>{
  try{ await EdgeAPI.request('/admin/subscriptions/'+sid+'/status',{method:'POST',body:JSON.stringify({status})}); showToastSafe('Assinatura -> '+status); const cur=document.getElementById('admin-modal'); if(cur) closeAdminModal(); await loadAdmin(); }catch(e){ showToastSafe(e.message); }
};
function showToastSafe(m){
  const t=document.getElementById('toast'); if(t){ t.textContent=m; t.classList.add('show'); setTimeout(()=>t.classList.remove('show'),3000); } else alert(m);
}
if(typeof escapeHtml==='undefined') window.escapeHtml=(v)=>String(v??'').replace(/[&<>'"]/g,c=>({ '&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;' })[c]);
if(typeof formatDate==='undefined') window.formatDate=(v)=>v?new Date(v).toLocaleString('pt-BR',{dateStyle:'short',timeStyle:'short'}):'—';
document.getElementById('admin-search').onclick=searchCompanies;
document.getElementById('admin-refresh').onclick=loadAdmin;
document.getElementById('admin-q').addEventListener('keydown',e=>{ if(e.key==='Enter') searchCompanies(); });
loadAdmin();
