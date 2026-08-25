EdgeAuth.require('administrador');

function renderUsers() {
  const active = EdgeDB.users.filter(u => u.status === 'ativo').length;
  const online = EdgeDB.users.filter(u => u.status === 'ativo' && u.ultimo_login && !u.ultimo_logout).length;
  document.getElementById('user-stats').innerHTML = [
    ['Usuários cadastrados', EdgeDB.users.length],
    ['Contas ativas', active],
    ['Administradores', EdgeDB.users.filter(u => u.cargo === 'administrador').length],
    ['Sessões atuais', online]
  ].map(x => `<div class="stat"><div class="label">${x[0]}</div><div class="value">${x[1]}</div><div class="hint">${x[1] === 0 ? 'Nenhum registro' : 'Dados cadastrados'}</div></div>`).join('');

  document.getElementById('users-table').innerHTML = EdgeDB.users.length ? `<table><thead><tr><th>Nome</th><th>E-mail</th><th>Cargo</th><th>Status</th><th>Último acesso</th><th>Ações</th></tr></thead><tbody>${EdgeDB.users.map(u => `<tr><td>${escapeHtml(u.nome)}</td><td>${escapeHtml(u.email)}</td><td>${u.cargo}</td><td><span class="badge ${u.status === 'ativo' ? 'green' : u.status === 'bloqueado' ? 'red' : 'amber'}">${u.status}</span></td><td>${u.ultimo_login ? formatDate(u.ultimo_login) : 'Nunca'}</td><td><button class="btn btn-secondary btn-small" onclick="toggleUser('${u.id}')">${u.status === 'ativo' ? 'Bloquear' : 'Ativar'}</button></td></tr>`).join('')}</tbody></table>` : '<div class="empty-state">Nenhum usuário cadastrado. Use “Criar usuário” para adicionar o primeiro usuário comum.</div>';
}

function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c])); }

window.toggleUser = function(id) {
  const u = EdgeDB.users.find(x => String(x.id) === String(id));
  if (!u) return;
  u.status = u.status === 'ativo' ? 'bloqueado' : 'ativo';
  EdgeDB.save(); renderUsers(); showToast(`Conta ${u.status}.`);
};

function openUserForm() {
  const modal = document.getElementById('user-modal');
  modal.className = 'modal';
  modal.innerHTML = `<div class="modal-card"><div class="card-head"><div><h2>Criar usuário</h2><p>Cadastre os dados reais da conta.</p></div><button class="btn btn-secondary" id="close-user">Fechar</button></div><form id="user-form" class="form-grid"><label>Nome<input id="u-name" required></label><label>E-mail<input id="u-email" type="email" required></label><label>Senha<input id="u-pass" type="password" minlength="4" required></label><label>Cargo<select id="u-role"><option value="usuario">Usuário</option><option value="administrador">Administrador</option></select></label><div class="form-actions"><button class="btn btn-primary" type="submit">Cadastrar</button></div><div id="user-form-error" class="form-error"></div></form></div>`;
  document.getElementById('close-user').onclick = () => modal.className = 'modal hidden';
  document.getElementById('user-form').onsubmit = e => {
    e.preventDefault();
    const nome = document.getElementById('u-name').value.trim();
    const email = document.getElementById('u-email').value.trim().toLowerCase();
    const senha = document.getElementById('u-pass').value;
    const cargo = document.getElementById('u-role').value;
    const error = document.getElementById('user-form-error');
    if (EdgeDB.users.some(u => u.email.toLowerCase() === email)) { error.textContent = 'Já existe um usuário com este e-mail.'; return; }
    const id = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    EdgeDB.users.push({ id, nome, email, senha, cargo, status:'ativo', ultimo_login:null, ultimo_logout:null, tempo_total_ativo:0, cameras:[], permissoes:{ visualizar_cameras:true, gerenciar_cameras:cargo==='administrador', visualizar_alertas:true, visualizar_relatorios:true, gerenciar_usuarios:cargo==='administrador', gerenciar_permissoes:cargo==='administrador', acessar_configuracoes:true } });
    EdgeDB.save(); modal.className = 'modal hidden'; renderUsers(); showToast('Usuário cadastrado.');
  };
}

document.getElementById('add-user').onclick = openUserForm;
renderUsers();
