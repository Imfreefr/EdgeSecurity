EdgeAuth.require('administrador');

const USER_PERMISSIONS = [
  ['visualizar_cameras', 'Visualizar câmeras'],
  ['usar_camera_dispositivo', 'Usar câmera deste dispositivo'],
  ['gerenciar_cameras', 'Gerenciar câmeras'],
  ['visualizar_alertas', 'Visualizar alertas'],
  ['visualizar_relatorios', 'Visualizar relatórios'],
  ['gerenciar_usuarios', 'Gerenciar usuários'],
  ['gerenciar_permissoes', 'Gerenciar permissões'],
  ['acessar_configuracoes', 'Acessar configurações']
];

function defaultPermissions(cargo) {
  const admin = cargo === 'administrador';
  return {
    visualizar_cameras: true,
    usar_camera_dispositivo: true,
    gerenciar_cameras: admin,
    visualizar_alertas: true,
    visualizar_relatorios: true,
    gerenciar_usuarios: admin,
    gerenciar_permissoes: admin,
    acessar_configuracoes: true
  };
}

function renderUsers() {
  const active = EdgeDB.users.filter(u => u.status === 'ativo').length;
  const online = EdgeDB.users.filter(u => u.status === 'ativo' && u.ultimo_login && !u.ultimo_logout).length;
  document.getElementById('user-stats').innerHTML = [
    ['Usuários cadastrados', EdgeDB.users.length],
    ['Contas ativas', active],
    ['Administradores', EdgeDB.users.filter(u => u.cargo === 'administrador').length],
    ['Sessões atuais', online]
  ].map(x => `<div class="stat"><div class="label">${x[0]}</div><div class="value">${x[1]}</div><div class="hint">${x[1] === 0 ? 'Nenhum registro' : 'Dados cadastrados'}</div></div>`).join('');

  document.getElementById('users-table').innerHTML = EdgeDB.users.length ? `<table><thead><tr><th>Nome</th><th>E-mail</th><th>Cargo</th><th>Status</th><th>Permissões</th><th>Último acesso</th><th>Ações</th></tr></thead><tbody>${EdgeDB.users.map(u => {
    const perms = Object.values(u.permissoes || {}).filter(Boolean).length;
    return `<tr><td>${escapeHtml(u.nome)}</td><td>${escapeHtml(u.email)}</td><td>${u.cargo}</td><td><span class="badge ${u.status === 'ativo' ? 'green' : u.status === 'bloqueado' ? 'red' : 'amber'}">${u.status}</span></td><td>${perms}/${USER_PERMISSIONS.length}</td><td>${u.ultimo_login ? formatDate(u.ultimo_login) : 'Nunca'}</td><td><button class="btn btn-secondary btn-small" onclick="editUser('${u.id}')">Permissões</button> <button class="btn ${u.status === 'ativo' ? 'btn-danger' : 'btn-secondary'} btn-small" onclick="toggleUser('${u.id}')">${u.status === 'ativo' ? 'Bloquear' : 'Ativar'}</button></td></tr>`;
  }).join('')}</tbody></table>` : '<div class="empty-state">Nenhum usuário cadastrado. Crie uma conta para começar.</div>';
}

function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' }[c])); }

window.toggleUser = function(id) {
  const u = EdgeDB.users.find(x => String(x.id) === String(id));
  if (!u) return;
  const current = EdgeAuth.current();
  if (current && String(current.id) === String(id)) { showToast('Não é possível bloquear a própria conta.'); return; }
  if (u.cargo === 'administrador' && u.status === 'ativo' && EdgeDB.users.filter(x => x.cargo === 'administrador' && x.status === 'ativo').length <= 1) {
    showToast('Mantenha pelo menos um administrador ativo.'); return;
  }
  u.status = u.status === 'ativo' ? 'bloqueado' : 'ativo';
  EdgeDB.save(); renderUsers(); showToast(`Conta ${u.status}.`);
};

function permissionFields(selected, cargo) {
  return USER_PERMISSIONS.map(([key, label]) => `<label class="permission-check"><input type="checkbox" name="perm" value="${key}" ${selected[key] ? 'checked' : ''} ${cargo === 'administrador' && ['gerenciar_usuarios','gerenciar_permissoes'].includes(key) ? '' : ''}><span>${label}</span></label>`).join('');
}

function openUserForm(user = null) {
  const modal = document.getElementById('user-modal');
  const isEdit = !!user;
  const cargo = user?.cargo || 'usuario';
  const perms = user?.permissoes || defaultPermissions(cargo);
  modal.className = 'modal';
  modal.innerHTML = `<div class="modal-card modal-user-card"><div class="card-head"><div><h2>${isEdit ? 'Editar usuário e permissões' : 'Criar usuário'}</h2><p>${isEdit ? 'Altere somente os dados necessários desta conta.' : 'Cadastre uma conta real; nenhuma conta é criada automaticamente.'}</p></div><button class="btn btn-secondary" id="close-user">Fechar</button></div><form id="user-form" class="form-grid">
    <label>Nome<input id="u-name" required value="${escapeHtml(user?.nome || '')}"></label>
    <label>E-mail<input id="u-email" type="email" required value="${escapeHtml(user?.email || '')}"></label>
    <label>${isEdit ? 'Nova senha (opcional)' : 'Senha'}<input id="u-pass" type="password" minlength="4" ${isEdit ? '' : 'required'}></label>
    <label>Cargo<select id="u-role"><option value="usuario" ${cargo === 'usuario' ? 'selected' : ''}>Usuário</option><option value="administrador" ${cargo === 'administrador' ? 'selected' : ''}>Administrador</option></select></label>
    <fieldset class="permission-box"><legend>Permissões</legend><div class="permission-grid">${permissionFields(perms, cargo)}</div></fieldset>
    <div class="form-actions"><button class="btn btn-primary" type="submit">${isEdit ? 'Salvar alterações' : 'Cadastrar usuário'}</button></div><div id="user-form-error" class="form-error"></div>
  </form></div>`;

  document.getElementById('close-user').onclick = () => modal.className = 'modal hidden';
  document.getElementById('u-role').onchange = e => {
    const role = e.target.value;
    const current = {};
    document.querySelectorAll('input[name="perm"]').forEach(input => current[input.value] = input.checked);
    if (role === 'administrador') {
      USER_PERMISSIONS.forEach(([key]) => current[key] = true);
    } else if (!isEdit) {
      Object.assign(current, defaultPermissions('usuario'));
    }
    document.querySelector('.permission-grid').innerHTML = permissionFields(current, role);
  };

  document.getElementById('user-form').onsubmit = e => {
    e.preventDefault();
    const nome = document.getElementById('u-name').value.trim();
    const email = document.getElementById('u-email').value.trim().toLowerCase();
    const senha = document.getElementById('u-pass').value;
    const novoCargo = document.getElementById('u-role').value;
    const error = document.getElementById('user-form-error');
    const duplicate = EdgeDB.users.some(x => x.email.toLowerCase() === email && (!user || x.id !== user.id));
    if (duplicate) { error.textContent = 'Já existe um usuário com este e-mail.'; return; }
    if (!isEdit && senha.length < 4) { error.textContent = 'A senha deve possuir pelo menos 4 caracteres.'; return; }
    if (isEdit && senha && senha.length < 4) { error.textContent = 'A nova senha deve possuir pelo menos 4 caracteres.'; return; }

    const permissions = {};
    document.querySelectorAll('input[name="perm"]').forEach(input => permissions[input.value] = input.checked);
    if (novoCargo === 'administrador') USER_PERMISSIONS.forEach(([key]) => permissions[key] = true);

    if (isEdit) {
      if (user.cargo === 'administrador' && novoCargo !== 'administrador' && EdgeDB.users.filter(x => x.cargo === 'administrador' && x.status === 'ativo').length <= 1) {
        error.textContent = 'Não é possível remover o último administrador ativo.'; return;
      }
      user.nome = nome;
      user.email = email;
      user.cargo = novoCargo;
      user.permissoes = permissions;
      if (senha) user.senha = senha;
      EdgeDB.save(); modal.className = 'modal hidden'; renderUsers(); showToast('Usuário e permissões atualizados.');
      return;
    }

    const id = crypto.randomUUID ? crypto.randomUUID() : String(Date.now());
    EdgeDB.users.push({ id, nome, email, senha, cargo: novoCargo, status:'ativo', ultimo_login:null, ultimo_logout:null, tempo_total_ativo:0, criado_em:new Date().toISOString(), cameras:[], permissoes:permissions });
    EdgeDB.save(); modal.className = 'modal hidden'; renderUsers(); showToast('Usuário cadastrado com as permissões definidas.');
  };
}

window.editUser = function(id) {
  const user = EdgeDB.users.find(x => String(x.id) === String(id));
  if (user) openUserForm(user);
};

document.getElementById('add-user').onclick = () => openUserForm();
renderUsers();
